#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actor de Devolución - Sistema Distribuido de Préstamo de Libros
Suscribe a eventos de devolución y actualiza la base de datos a través de GA
"""

import zmq
import json
import time
import os
from datetime import datetime
import logging
from utils_failover import FailoverManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ACTOR_DEV - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ActorDevolucion:
    def __init__(self):
        self.context = zmq.Context()
        self.sub_socket = None
        self.contador_devoluciones = 0
        self.running = True
        
        # Leer variables de entorno
        self.gc_host = os.getenv('GC_HOST', 'gc')
        self.gc_pub_port = int(os.getenv('GC_PUB_PORT', '5002'))
        self.ga_host = os.getenv('GA_HOST', 'ga')
        self.ga_port = int(os.getenv('GA_PORT', '5003'))
        
        # Inicializar failover manager para comunicarse con GA
        self.failover_manager = FailoverManager(
            ga_host=self.ga_host,
            ga_port=self.ga_port,
            timeout=5,
            retry_interval=30
        )
        
    def conectar_gestor_carga(self):
        """Conecta al Gestor de Carga usando SUB socket"""
        try:
            self.sub_socket = self.context.socket(zmq.SUB)
            gc_address = f"tcp://{self.gc_host}:{self.gc_pub_port}"
            self.sub_socket.connect(gc_address)
            
            # Suscribirse al topic "devolucion"
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, b"devolucion")
            
            logger.info(f"Conectado al Gestor de Carga en {gc_address}")
            logger.info("Suscrito al topic 'devolucion'")
            
            # Pequeña pausa para asegurar la conexión
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error conectando al Gestor de Carga: {e}")
            raise
    
    def procesar_devolucion(self, evento):
        """Procesa un evento de devolución usando GA"""
        try:
            libro_id = evento.get('libro_id', '')
            usuario_id = evento.get('usuario_id', '')
            sede = evento.get('sede', 'SEDE_1')
            timestamp = evento.get('timestamp', '')
            
            logger.info(f"Procesando devolución: Libro {libro_id} - Usuario {usuario_id} - Sede {sede}")
            
            # Verificar conexión con GA
            health = self.failover_manager.verificar_y_reconectar()
            if not health.get('ok'):
                logger.error("GA no está disponible para procesar devolución")
                return False
            
            # Enviar operación de devolución a GA
            resultado = self.failover_manager.enviar_operacion(
                "RETURN_BOOK",
                {
                    "libro_id": libro_id,
                    "usuario_id": usuario_id,
                    "sede": sede
                }
            )
            
            if not resultado:
                logger.error("Error comunicándose con GA para procesar devolución")
                return False
            
            if resultado.get('success'):
                self.contador_devoluciones += 1
                logger.info(f"Devolución procesada exitosamente (#{self.contador_devoluciones}): {resultado.get('message')}")
                return True
            else:
                logger.warning(f"Error en devolución: {resultado.get('message')}")
                return False
            
        except Exception as e:
            import traceback
            logger.error(f"Error procesando devolución: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def escuchar_eventos(self):
        """Escucha eventos de devolución del Gestor de Carga"""
        logger.info("Iniciando escucha de eventos de devolución...")
        
        while self.running:
            try:
                # Recibir mensaje (topic + datos)
                mensaje = self.sub_socket.recv_multipart(zmq.NOBLOCK)
                
                if len(mensaje) >= 2:
                    topic = mensaje[0].decode('utf-8')
                    datos_json = mensaje[1].decode('utf-8')
                    
                    logger.info(f"Evento recibido - Topic: {topic}")
                    logger.info(f"Datos: {datos_json}")
                    
                    # Parsear evento
                    evento = json.loads(datos_json)
                    
                    # Procesar solo eventos de devolución
                    if topic == "devolucion" and evento.get('operacion') == 'DEVOLUCION':
                        self.procesar_devolucion(evento)
                    else:
                        logger.warning(f"Evento inesperado recibido: {topic} - {evento.get('operacion', 'N/A')}")
                
            except zmq.Again:
                # No hay mensajes disponibles, continuar
                time.sleep(0.1)
                continue
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando evento JSON: {e}")
                continue
            except Exception as e:
                logger.error(f"Error escuchando eventos: {e}")
                time.sleep(1)
    
    def iniciar(self):
        """Inicia el Actor de Devolución"""
        try:
            logger.info("Iniciando Actor de Devolución...")
            
            # Conectar al Gestor de Carga
            self.conectar_gestor_carga()
            
            logger.info("Actor de Devolución iniciado correctamente")
            logger.info(f"Conectado a GA en {self.ga_host}:{self.ga_port}")
            logger.info("Esperando eventos de devolución...")
            
            # Iniciar escucha de eventos
            self.escuchar_eventos()
            
        except KeyboardInterrupt:
            logger.info("Deteniendo Actor de Devolución...")
            self.detener()
        except Exception as e:
            logger.error(f"Error fatal en Actor de Devolución: {e}")
            self.detener()
    
    def detener(self):
        """Detiene el Actor de Devolución"""
        self.running = False
        
        if self.failover_manager:
            self.failover_manager.cerrar()
        
        if self.sub_socket:
            self.sub_socket.close()
        if self.context:
            self.context.term()
        
        logger.info(f"Total de devoluciones procesadas: {self.contador_devoluciones}")
        logger.info("Actor de Devolución detenido")

def main():
    """Función principal"""
    actor = ActorDevolucion()
    actor.iniciar()

if __name__ == "__main__":
    main()
