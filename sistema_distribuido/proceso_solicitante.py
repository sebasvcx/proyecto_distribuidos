#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proceso Solicitante (PS) - Sistema Distribuido de Préstamo de Libros
Envía solicitudes de préstamo, renovación y devolución al Gestor de Carga
"""

import zmq
import json
import time
import os
from datetime import datetime
import logging
from metricas import Metricas, obtener_timestamp_ms, medir_tiempo_respuesta

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - PS - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ProcesoSolicitante:
    def __init__(self):
        self.context = zmq.Context()
        self.req_socket = None
        self.contador_solicitudes = 0
        self.contador_exitosos = 0
        self.contador_errores = 0
        
        # Leer variables de entorno
        self.gc_host = os.getenv('GC_HOST', 'gc')
        self.gc_port = int(os.getenv('GC_PORT', '5001'))
        
        # Inicializar sistema de métricas
        self.metricas = Metricas()
        
    def conectar_gestor_carga(self):
        """Conecta al Gestor de Carga usando REQ socket"""
        try:
            self.req_socket = self.context.socket(zmq.REQ)
            gc_address = f"tcp://{self.gc_host}:{self.gc_port}"
            self.req_socket.connect(gc_address)
            logger.info(f"Conectado al Gestor de Carga en {gc_address}")
            
            # Pequeña pausa para asegurar la conexión
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error conectando al Gestor de Carga: {e}")
            raise
    
    def leer_solicitudes(self, archivo_solicitudes):
        """Lee las solicitudes desde el archivo de texto"""
        solicitudes = []
        
        try:
            if not os.path.exists(archivo_solicitudes):
                logger.error(f"Archivo de solicitudes no encontrado: {archivo_solicitudes}")
                return solicitudes
            
            with open(archivo_solicitudes, 'r', encoding='utf-8') as f:
                for numero_linea, linea in enumerate(f, 1):
                    linea = linea.strip()
                    if not linea or linea.startswith('#'):
                        continue
                    
                    # Parsear línea: OPERACION LIBRO_ID USUARIO_ID [SEDE] [search_criteria]
                    # Formatos soportados:
                    # - PRESTAMO LIBRO_ID USUARIO_ID SEDE
                    # - PRESTAMO LIBRO_ID USUARIO_ID SEDE titulo:TITULO
                    # - RENOVACION LIBRO_ID USUARIO_ID SEDE
                    # - DEVOLUCION LIBRO_ID USUARIO_ID SEDE
                    partes = linea.split()
                    if len(partes) >= 3:
                        operacion = partes[0].upper()
                        libro_id = partes[1] if partes[1] != 'None' else None
                        usuario_id = partes[2]
                        sede = partes[3] if len(partes) > 3 and not partes[3].startswith('titulo:') else "SEDE_1"
                        
                        # Parsear search_criteria si existe
                        search_criteria = None
                        for parte in partes[3:]:
                            if parte.startswith('titulo:'):
                                search_criteria = {"titulo": parte.split(':', 1)[1]}
                                break
                        
                        solicitud = {
                            "op": operacion,
                            "libro_id": libro_id,
                            "usuario_id": usuario_id,
                            "sede": sede,
                            "search_criteria": search_criteria,
                            "linea": numero_linea
                        }
                        solicitudes.append(solicitud)
                    else:
                        logger.warning(f"Línea {numero_linea} mal formateada: {linea}")
            
            logger.info(f"Leídas {len(solicitudes)} solicitudes desde {archivo_solicitudes}")
            return solicitudes
            
        except Exception as e:
            logger.error(f"Error leyendo archivo de solicitudes: {e}")
            return solicitudes
    
    def enviar_solicitud(self, solicitud):
        """Envía una solicitud al Gestor de Carga y registra métricas si es préstamo"""
        try:
            # Crear mensaje JSON
            mensaje = {
                "op": solicitud["op"],
                "libro_id": solicitud["libro_id"],
                "usuario_id": solicitud["usuario_id"],
                "sede": solicitud["sede"]
            }
            
            # Agregar search_criteria si existe
            if solicitud.get("search_criteria"):
                mensaje["search_criteria"] = solicitud["search_criteria"]
            
            mensaje_json = json.dumps(mensaje, ensure_ascii=False)
            
            # Medir tiempo de respuesta para préstamos
            inicio_ms = None
            if solicitud["op"] == "PRESTAMO":
                inicio_ms = obtener_timestamp_ms()
            
            # Enviar solicitud
            self.req_socket.send(mensaje_json.encode('utf-8'))
            logger.info(f"Solicitud #{self.contador_solicitudes + 1} enviada: {mensaje_json}")
            
            # Recibir respuesta
            respuesta_bytes = self.req_socket.recv()
            respuesta_str = respuesta_bytes.decode('utf-8')
            respuesta = json.loads(respuesta_str)
            
            logger.info(f"Respuesta recibida: {respuesta_str}")
            
            # Registrar métricas para préstamos
            if solicitud["op"] == "PRESTAMO" and inicio_ms:
                fin_ms = obtener_timestamp_ms()
                tiempo_respuesta_ms = medir_tiempo_respuesta(inicio_ms, fin_ms)
                libro_id = respuesta.get("libro_id") or solicitud.get("libro_id") or "N/A"
                exito = respuesta.get("status") == "OK"
                self.metricas.registrar_prestamo(tiempo_respuesta_ms, libro_id, exito)
                logger.info(f"Tiempo de respuesta: {tiempo_respuesta_ms:.2f} ms")
            
            # Procesar respuesta
            if respuesta.get("status") == "OK":
                self.contador_exitosos += 1
                logger.info(f"Solicitud procesada exitosamente")
            else:
                self.contador_errores += 1
                logger.error(f"Error en solicitud: {respuesta.get('message', 'Error desconocido')}")
            
            self.contador_solicitudes += 1
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON: {e}")
            self.contador_errores += 1
            return False
        except Exception as e:
            logger.error(f"Error enviando solicitud: {e}")
            self.contador_errores += 1
            return False
    
    def procesar_solicitudes(self, archivo_solicitudes):
        """Procesa todas las solicitudes del archivo"""
        logger.info("Iniciando procesamiento de solicitudes...")
        
        # Leer solicitudes
        solicitudes = self.leer_solicitudes(archivo_solicitudes)
        
        if not solicitudes:
            logger.warning("No hay solicitudes para procesar")
            return
        
        logger.info(f"Procesando {len(solicitudes)} solicitudes...")
        
        # Procesar cada solicitud
        for i, solicitud in enumerate(solicitudes, 1):
            try:
                logger.info(f"Procesando solicitud {i}/{len(solicitudes)}: {solicitud['op']} - {solicitud['libro_id']} - {solicitud['usuario_id']}")
                
                # Enviar solicitud
                exito = self.enviar_solicitud(solicitud)
                
                if exito:
                    logger.info(f"Solicitud {i} completada")
                else:
                    logger.error(f"Solicitud {i} falló")
                
                # Pausa entre solicitudes (simular carga de trabajo real)
                if i < len(solicitudes):  # No pausar después de la última solicitud
                    logger.info("Esperando 1 segundo antes de la siguiente solicitud...")
                    time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Interrupción detectada, deteniendo procesamiento...")
                break
            except Exception as e:
                logger.error(f"Error procesando solicitud {i}: {e}")
                self.contador_errores += 1
                continue
        
        # Mostrar estadísticas finales
        self.mostrar_estadisticas()
    
    def mostrar_estadisticas(self):
        """Muestra estadísticas del procesamiento"""
        logger.info("===== ESTADÍSTICAS FINALES =====")
        logger.info(f"Total de solicitudes enviadas: {self.contador_solicitudes}")
        logger.info(f"Solicitudes exitosas: {self.contador_exitosos}")
        logger.info(f"Solicitudes con error: {self.contador_errores}")
        
        if self.contador_solicitudes > 0:
            porcentaje_exito = (self.contador_exitosos / self.contador_solicitudes) * 100
            logger.info(f"Porcentaje de éxito: {porcentaje_exito:.1f}%")
        
        logger.info("================================")
        
        # Mostrar métricas de préstamos
        self.metricas.mostrar_estadisticas()
    
    def iniciar(self, archivo_solicitudes="data/solicitudes.txt"):
        """Inicia el Proceso Solicitante"""
        try:
            logger.info("Iniciando Proceso Solicitante...")
            logger.info(f"Archivo de solicitudes especificado: {archivo_solicitudes}")
            
            # Conectar al Gestor de Carga
            self.conectar_gestor_carga()
            
            # Procesar solicitudes
            self.procesar_solicitudes(archivo_solicitudes)
            
        except KeyboardInterrupt:
            logger.info("Deteniendo Proceso Solicitante...")
        except Exception as e:
            logger.error(f"Error fatal en Proceso Solicitante: {e}")
        finally:
            self.detener()
    
    def detener(self):
        """Detiene el Proceso Solicitante"""
        if self.req_socket:
            self.req_socket.close()
        if self.context:
            self.context.term()
        
        logger.info("Proceso Solicitante detenido")

def main():
    """Función principal"""
    import sys
    
    # Debug: mostrar argumentos recibidos (usar print para asegurar que se vea)
    print(f"DEBUG: Argumentos recibidos: {sys.argv}", file=sys.stderr)
    logger.info(f"Argumentos recibidos: {sys.argv}")
    
    ps = ProcesoSolicitante()
    
    # Aceptar archivo como argumento de línea de comandos
    if len(sys.argv) > 1:
        archivo_solicitudes = sys.argv[1]
        print(f"DEBUG: Usando archivo de argumento: {archivo_solicitudes}", file=sys.stderr)
        logger.info(f"Usando archivo de argumento: {archivo_solicitudes}")
        ps.iniciar(archivo_solicitudes)
    else:
        print("DEBUG: No se proporcionó archivo, usando por defecto: data/solicitudes.txt", file=sys.stderr)
        logger.info("No se proporcionó archivo, usando por defecto: data/solicitudes.txt")
        ps.iniciar()

if __name__ == "__main__":
    main()
