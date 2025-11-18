# -*- coding: utf-8 -*-
"""
Utilidades comunes para los tests del sistema distribuido
"""

import zmq
import json
import time
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional, Callable
import logging

# Configurar logging para tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestUtils:
    """Utilidades para testing del sistema distribuido"""
    
    @staticmethod
    def esperar_slow_joiner(sleep_time: float = 1.0) -> None:
        """
        Espera para el 'slow joiner' de ZeroMQ SUB sockets
        """
        logger.info(f"Esperando {sleep_time}s para slow joiner de ZeroMQ...")
        time.sleep(sleep_time)
    
    @staticmethod
    def send_req(gc_endpoint: str, payload: Dict[str, Any]) -> Tuple[str, float]:
        """
        Envía solicitud REQ al GC y mide tiempo de respuesta
        
        Args:
            gc_endpoint: Endpoint del GC (ej: "tcp://gc:5001")
            payload: Datos a enviar
            
        Returns:
            Tuple[status, ack_ms]: Status de respuesta y tiempo en ms
        """
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        
        try:
            socket.connect(gc_endpoint)
            
            # Medir tiempo de respuesta
            start_time = time.time()
            socket.send(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
            response_bytes = socket.recv()
            end_time = time.time()
            
            ack_ms = (end_time - start_time) * 1000
            response = json.loads(response_bytes.decode('utf-8'))
            
            logger.info(f"REQ enviado: {payload}")
            logger.info(f"RES recibida: {response} (took {ack_ms:.2f}ms)")
            
            return response.get('status', 'UNKNOWN'), ack_ms
            
        finally:
            socket.close()
            context.term()
    
    @staticmethod
    def read_json(path: str) -> Dict[str, Any]:
        """
        Lee archivo JSON de forma segura
        
        Args:
            path: Ruta al archivo JSON
            
        Returns:
            Dict con el contenido del JSON
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo no encontrado: {path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON {path}: {e}")
            return {}
    
    @staticmethod
    def wait_for_file_change(path: str, predicate: Callable[[Dict], bool], 
                           timeout: float = 10.0) -> bool:
        """
        Espera hasta que un archivo JSON cambie y cumpla una condición
        
        Args:
            path: Ruta al archivo JSON
            predicate: Función que evalúa si el cambio es válido
            timeout: Tiempo máximo de espera en segundos
            
        Returns:
            True si el cambio ocurrió dentro del timeout
        """
        logger.info(f"Esperando cambio en {path} (timeout: {timeout}s)")
        
        start_time = time.time()
        initial_content = TestUtils.read_json(path)
        
        while time.time() - start_time < timeout:
            current_content = TestUtils.read_json(path)
            
            if current_content != initial_content:
                if predicate(current_content):
                    logger.info(f"Cambio detectado en {path} y condición cumplida")
                    return True
                else:
                    logger.info(f"Cambio detectado en {path} pero condición no cumplida")
            
            time.sleep(0.1)
        
        logger.warning(f"Timeout esperando cambio en {path}")
        return False
    
    @staticmethod
    def crear_snapshot_libros(path: str, snapshot_path: str) -> None:
        """
        Crea snapshot del archivo libros.json
        
        Args:
            path: Ruta al archivo original
            snapshot_path: Ruta donde guardar el snapshot
        """
        try:
            libros = TestUtils.read_json(path)
            with open(snapshot_path, 'w', encoding='utf-8') as f:
                json.dump(libros, f, ensure_ascii=False, indent=2)
            logger.info(f"Snapshot creado: {snapshot_path}")
        except Exception as e:
            logger.error(f"Error creando snapshot: {e}")
    
    @staticmethod
    def contar_operaciones_en_logs(logs: str, operacion: str) -> int:
        """
        Cuenta operaciones en logs de texto
        
        Args:
            logs: Contenido de logs como string
            operacion: Tipo de operación a contar (RENOVACION, DEVOLUCION)
            
        Returns:
            Número de operaciones encontradas
        """
        count = 0
        for line in logs.split('\n'):
            if f'operacion": "{operacion}"' in line or f"Operación.*{operacion}" in line:
                count += 1
        return count
    
    @staticmethod
    def validar_fecha_renovacion(fecha_str: str, dias_adicionales: int = 7) -> bool:
        """
        Valida que una fecha de renovación sea correcta (+7 días)
        
        Args:
            fecha_str: Fecha en formato string
            dias_adicionales: Días adicionales esperados
            
        Returns:
            True si la fecha es válida
        """
        try:
            fecha_renovacion = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            fecha_esperada = datetime.now() + timedelta(days=dias_adicionales)
            
            # Tolerancia de ±1 día
            diferencia = abs((fecha_renovacion - fecha_esperada).days)
            return diferencia <= 1
            
        except Exception as e:
            logger.error(f"Error validando fecha {fecha_str}: {e}")
            return False
    
    @staticmethod
    def generar_reporte_test(test_name: str, resultados: Dict[str, Any], 
                           log_path: str) -> None:
        """
        Genera reporte de test en archivo
        
        Args:
            test_name: Nombre del test
            resultados: Diccionario con resultados
            log_path: Ruta donde guardar el reporte
        """
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f"=== REPORTE DE TEST: {test_name} ===\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
                
                for key, value in resultados.items():
                    f.write(f"{key}: {value}\n")
                
                f.write(f"\nEstado: {'PASSED' if resultados.get('passed', False) else 'FAILED'}\n")
            
            logger.info(f"Reporte guardado: {log_path}")
            
        except Exception as e:
            logger.error(f"Error generando reporte: {e}")

class SubscriberTester:
    """Helper para testing de PUB/SUB"""
    
    def __init__(self, gc_endpoint: str = "tcp://gc:5002"):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.gc_endpoint = gc_endpoint
        self.events_received = []
        self.running = False
        self.thread = None
    
    def conectar(self, topics: list) -> None:
        """Conecta y suscribe a topics"""
        self.socket.connect(self.gc_endpoint)
        
        for topic in topics:
            self.socket.setsockopt(zmq.SUBSCRIBE, topic.encode('utf-8'))
            logger.info(f"Suscrito a topic: {topic}")
        
        # Esperar slow joiner
        TestUtils.esperar_slow_joiner()
    
    def iniciar_escucha(self) -> None:
        """Inicia escucha en thread separado"""
        self.running = True
        self.thread = threading.Thread(target=self._escuchar)
        self.thread.start()
        logger.info("Iniciada escucha de eventos")
    
    def _escuchar(self) -> None:
        """Loop de escucha de eventos"""
        while self.running:
            try:
                mensaje = self.socket.recv_multipart(zmq.NOBLOCK)
                if len(mensaje) >= 2:
                    topic = mensaje[0].decode('utf-8')
                    datos = json.loads(mensaje[1].decode('utf-8'))
                    
                    evento = {
                        'topic': topic,
                        'timestamp': datetime.now().isoformat(),
                        'data': datos
                    }
                    
                    self.events_received.append(evento)
                    logger.info(f"Evento recibido: {topic} - {datos.get('operacion', 'N/A')}")
                
            except zmq.Again:
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"Error en escucha: {e}")
                break
    
    def detener(self) -> None:
        """Detiene la escucha"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        
        self.socket.close()
        self.context.term()
        logger.info("Escucha detenida")
    
    def obtener_eventos(self, operacion: str = None) -> list:
        """Obtiene eventos recibidos, opcionalmente filtrados por operación"""
        if operacion:
            return [e for e in self.events_received if e['data'].get('operacion') == operacion]
        return self.events_received.copy()
