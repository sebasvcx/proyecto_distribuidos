#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilidades de Failover - Sistema Distribuido de Préstamo de Libros
Funciones para health checks y conmutación entre réplicas
"""

import zmq
import json
import time
import logging
import os

logger = logging.getLogger(__name__)

class FailoverManager:
    """Gestiona el failover entre réplicas primaria y secundaria"""
    
    def __init__(self, ga_host="ga", ga_port=5003, timeout=5, retry_interval=30):
        """
        Inicializa el gestor de failover
        
        Args:
            ga_host: Host del GA
            ga_port: Puerto del GA
            timeout: Timeout para health checks (segundos)
            retry_interval: Intervalo entre reintentos de reconexión (segundos)
        """
        self.ga_host = ga_host
        self.ga_port = ga_port
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.using_primary = True
        self.last_health_check = None
        self.context = None
        self.ga_socket = None
    
    def crear_socket_ga(self):
        """Crea un socket REQ para comunicarse con GA"""
        if not self.context:
            self.context = zmq.Context()
        
        if self.ga_socket:
            self.ga_socket.close()
        
        self.ga_socket = self.context.socket(zmq.REQ)
        self.ga_socket.setsockopt(zmq.RCVTIMEO, self.timeout * 1000)  # Timeout en ms
        self.ga_socket.setsockopt(zmq.LINGER, 0)
        
        ga_address = f"tcp://{self.ga_host}:{self.ga_port}"
        self.ga_socket.connect(ga_address)
        
        logger.info(f"Socket GA creado: {ga_address}")
    
    def health_check(self):
        """
        Realiza un health check al GA
        
        Returns:
            Dict con resultado: {"ok": bool, "status": str, "message": str}
        """
        try:
            if not self.ga_socket:
                self.crear_socket_ga()
            
            # Enviar solicitud de health check
            solicitud = {
                "operacion": "HEALTH_CHECK"
            }
            
            self.ga_socket.send(json.dumps(solicitud).encode('utf-8'))
            
            # Recibir respuesta
            respuesta_bytes = self.ga_socket.recv()
            respuesta_str = respuesta_bytes.decode('utf-8')
            respuesta = json.loads(respuesta_str)
            
            self.last_health_check = time.time()
            self.using_primary = True
            
            if respuesta.get('status') == 'healthy':
                logger.debug("Health check exitoso: GA está saludable")
                return {
                    "ok": True,
                    "status": "healthy",
                    "message": "GA está operativo",
                    "primary_ok": respuesta.get('primary_ok', False),
                    "secondary_ok": respuesta.get('secondary_ok', False)
                }
            else:
                logger.warning(f"Health check: GA en estado degradado - {respuesta.get('status')}")
                return {
                    "ok": True,  # Aún responde, aunque esté degradado
                    "status": "degraded",
                    "message": "GA está degradado pero operativo",
                    "primary_ok": respuesta.get('primary_ok', False),
                    "secondary_ok": respuesta.get('secondary_ok', False)
                }
        
        except zmq.Again:
            logger.warning(f"Timeout en health check a GA ({self.ga_host}:{self.ga_port})")
            self.using_primary = False
            return {
                "ok": False,
                "status": "timeout",
                "message": f"Timeout conectando a GA en {self.ga_host}:{self.ga_port}"
            }
        except zmq.ZMQError as e:
            logger.error(f"Error ZMQ en health check: {e}")
            self.using_primary = False
            return {
                "ok": False,
                "status": "error",
                "message": f"Error de conexión: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error en health check: {e}")
            self.using_primary = False
            return {
                "ok": False,
                "status": "error",
                "message": f"Error inesperado: {str(e)}"
            }
    
    def enviar_operacion(self, operacion, datos, max_retries=3):
        """
        Envía una operación al GA con reintentos
        
        Args:
            operacion: Nombre de la operación (GET_BOOK, LOAN_BOOK, etc.)
            datos: Dict con los datos de la operación
            max_retries: Número máximo de reintentos
        
        Returns:
            Dict con la respuesta del GA o None si falla
        """
        solicitud = {
            "operacion": operacion,
            **datos
        }
        
        for intento in range(max_retries):
            try:
                if not self.ga_socket:
                    self.crear_socket_ga()
                
                # Enviar solicitud
                self.ga_socket.send(json.dumps(solicitud).encode('utf-8'))
                
                # Recibir respuesta
                respuesta_bytes = self.ga_socket.recv()
                respuesta_str = respuesta_bytes.decode('utf-8')
                
                # Verificar que la respuesta es un string JSON válido
                if not respuesta_str or not isinstance(respuesta_str, str):
                    logger.error(f"Respuesta inválida del GA: {type(respuesta_str)}")
                    raise ValueError(f"Respuesta inválida del GA: {type(respuesta_str)}")
                
                try:
                    respuesta = json.loads(respuesta_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parseando respuesta JSON del GA: {e}, respuesta: {respuesta_str[:200]}")
                    raise
                
                # Verificar que la respuesta es un diccionario
                if not isinstance(respuesta, dict):
                    logger.error(f"Respuesta del GA no es un diccionario: {type(respuesta)}, valor: {respuesta}")
                    raise ValueError(f"Respuesta del GA no es un diccionario: {type(respuesta)}")
                
                self.last_health_check = time.time()
                self.using_primary = True
                
                return respuesta
            
            except zmq.Again:
                logger.warning(f"Timeout en operación {operacion} (intento {intento + 1}/{max_retries})")
                if intento < max_retries - 1:
                    time.sleep(1)  # Esperar antes de reintentar
                    self.crear_socket_ga()  # Recrear socket
                else:
                    logger.error(f"Fallo definitivo en operación {operacion} después de {max_retries} intentos")
                    self.using_primary = False
                    return None
            
            except zmq.ZMQError as e:
                logger.error(f"Error ZMQ en operación {operacion}: {e}")
                if intento < max_retries - 1:
                    time.sleep(1)
                    self.crear_socket_ga()
                else:
                    self.using_primary = False
                    return None
            
            except Exception as e:
                logger.error(f"Error inesperado en operación {operacion}: {e}")
                if intento < max_retries - 1:
                    time.sleep(1)
                else:
                    return None
        
        return None
    
    def verificar_y_reconectar(self):
        """Verifica la conexión y reconecta si es necesario"""
        if self.last_health_check is None or (time.time() - self.last_health_check) > self.retry_interval:
            resultado = self.health_check()
            if not resultado.get('ok'):
                logger.warning("GA no responde, intentando reconectar...")
                time.sleep(2)
                self.crear_socket_ga()
                return self.health_check()
        return {"ok": True}
    
    def cerrar(self):
        """Cierra las conexiones"""
        if self.ga_socket:
            self.ga_socket.close()
            self.ga_socket = None
        if self.context:
            self.context.term()
            self.context = None

def verificar_ga_disponible(ga_host="ga", ga_port=5003, timeout=5):
    """
    Función de utilidad para verificar si GA está disponible
    
    Args:
        ga_host: Host del GA
        ga_port: Puerto del GA
        timeout: Timeout en segundos
    
    Returns:
        bool: True si GA está disponible, False en caso contrario
    """
    try:
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.RCVTIMEO, timeout * 1000)
        socket.setsockopt(zmq.LINGER, 0)
        
        socket.connect(f"tcp://{ga_host}:{ga_port}")
        
        solicitud = {"operacion": "HEALTH_CHECK"}
        socket.send(json.dumps(solicitud).encode('utf-8'))
        
        respuesta_bytes = socket.recv()
        respuesta = json.loads(respuesta_bytes.decode('utf-8'))
        
        socket.close()
        context.term()
        
        return respuesta.get('status') in ['healthy', 'degraded']
    
    except Exception as e:
        logger.debug(f"GA no disponible: {e}")
        return False

