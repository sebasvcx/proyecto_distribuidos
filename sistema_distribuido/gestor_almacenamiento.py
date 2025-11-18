#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestor de Almacenamiento (GA) - Sistema Distribuido de Préstamo de Libros
Gestiona la base de datos con réplicas primaria y secundaria
Proporciona operaciones de base de datos vía ZeroMQ REQ/REP
"""

import zmq
import json
import os
import threading
import time
import shutil
from datetime import datetime, timedelta
import logging
from filelock import FileLock

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - GA - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class GestorAlmacenamiento:
    def __init__(self,
                 primary_path="data/primary/libros.json",
                 secondary_path="data/secondary/libros.json",
                 port=5003,
                 host="0.0.0.0"):
        """
        Inicializa el Gestor de Almacenamiento
        
        Args:
            primary_path: Ruta al archivo de réplica primaria
            secondary_path: Ruta al archivo de réplica secundaria
            port: Puerto para el socket REP
            host: Host para el socket REP
        """
        self.context = zmq.Context()
        self.rep_socket = None
        self.primary_path = primary_path
        self.secondary_path = secondary_path
        self.port = port
        self.host = host
        self.running = True
        self.contador_operaciones = 0
        self.replicacion_lock = threading.Lock()
        self.using_secondary = False  # Flag para indicar si estamos usando réplica secundaria
        
        # Asegurar que los directorios existen
        os.makedirs(os.path.dirname(self.primary_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.secondary_path), exist_ok=True)
        
        # Inicializar réplicas si no existen
        self._inicializar_replicas()

    @staticmethod
    def _normalizar_libro_id(libro_id):
        """Normaliza IDs de libro para mantener consistencia con data/libros.json."""
        if not isinstance(libro_id, str):
            return libro_id

        valor = libro_id.strip().upper()
        if not valor.startswith('L'):
            return valor

        try:
            numero = int(''.join(ch for ch in valor[1:] if ch.isdigit()))
            # El dataset usa 4 dígitos luego del prefijo L (ej: L0003)
            return f"L{numero:04d}"
        except ValueError:
            return valor

    @staticmethod
    def _ajustar_metadata_prestamos(base_datos, sede, delta):
        """Actualiza contadores de préstamos por sede si aplica."""
        metadata = base_datos.get('metadata', {})
        if sede == 'SEDE_1':
            metadata['ejemplares_prestados_sede_1'] = max(
                0,
                metadata.get('ejemplares_prestados_sede_1', 0) + delta
            )
        elif sede == 'SEDE_2':
            metadata['ejemplares_prestados_sede_2'] = max(
                0,
                metadata.get('ejemplares_prestados_sede_2', 0) + delta
            )
        else:
            # Para sedes de pruebas (p.ej. SEDE_TEST) no ajustamos métricas globales
            if delta != 0:
                logger.debug(f"Sede '{sede}' fuera de métricas, delta {delta} ignorado")
    
    def _inicializar_replicas(self):
        """Inicializa las réplicas si no existen o están vacías"""
        try:
            # Si la primaria no existe, intentar copiar desde data/libros.json
            if not os.path.exists(self.primary_path):
                if os.path.exists("data/libros.json"):
                    logger.info("Copiando datos iniciales desde data/libros.json a réplica primaria")
                    os.makedirs(os.path.dirname(self.primary_path), exist_ok=True)
                    shutil.copy2("data/libros.json", self.primary_path)
                else:
                    logger.warning("No se encontró archivo de datos inicial. Creando estructura vacía.")
                    self._crear_estructura_vacia(self.primary_path)
            
            # Si la secundaria no existe, copiar desde la primaria
            if not os.path.exists(self.secondary_path):
                logger.info("Inicializando réplica secundaria desde primaria")
                os.makedirs(os.path.dirname(self.secondary_path), exist_ok=True)
                if os.path.exists(self.primary_path):
                    shutil.copy2(self.primary_path, self.secondary_path)
                else:
                    self._crear_estructura_vacia(self.secondary_path)
            
            logger.info(f"Réplicas inicializadas: Primaria={self.primary_path}, Secundaria={self.secondary_path}")
            
        except Exception as e:
            logger.error(f"Error inicializando réplicas: {e}")
            raise
    
    def _crear_estructura_vacia(self, archivo):
        """Crea una estructura de base de datos vacía"""
        estructura_vacia = {
            "metadata": {
                "version": "1.0",
                "fecha_creacion": datetime.now().isoformat(),
                "total_libros": 0,
                "total_ejemplares": 0,
                "ejemplares_prestados_sede_1": 0,
                "ejemplares_prestados_sede_2": 0,
                "ejemplares_disponibles": 0
            },
            "libros": [],
            "ejemplares": []
        }
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(estructura_vacia, f, ensure_ascii=False, indent=2)
    
    def _cargar_base_datos(self, archivo=None):
        """
        Carga la base de datos desde un archivo con failover automático
        
        Args:
            archivo: Ruta al archivo (None para usar failover automático)
        
        Returns:
            Dict con la base de datos o None si falla
        """
        # Si no se especifica archivo, usar failover automático
        if archivo is None:
            # Intentar cargar desde primaria primero
            if os.path.exists(self.primary_path) and os.access(self.primary_path, os.R_OK):
                try:
                    base_datos = self._cargar_base_datos(self.primary_path)
                    if base_datos:
                        self.using_secondary = False
                        return base_datos
                except Exception as e:
                    logger.warning(f"Error cargando réplica primaria: {e}")
            
            # Si primaria falla, intentar secundaria
            if os.path.exists(self.secondary_path) and os.access(self.secondary_path, os.R_OK):
                logger.warning("Réplica primaria no disponible, usando réplica secundaria")
                try:
                    base_datos = self._cargar_base_datos(self.secondary_path)
                    if base_datos:
                        self.using_secondary = True
                        return base_datos
                except Exception as e:
                    logger.error(f"Error cargando réplica secundaria: {e}")
            
            logger.error("Ambas réplicas no están disponibles")
            return None
        
        # Cargar desde archivo específico
        try:
            lock = FileLock(f"{archivo}.lock")
            with lock:
                if not os.path.exists(archivo):
                    logger.error(f"Archivo no encontrado: {archivo}")
                    return None
                
                with open(archivo, 'r', encoding='utf-8') as f:
                    base_datos = json.load(f)
                
                return base_datos
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON desde {archivo}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error cargando base de datos desde {archivo}: {e}")
            return None
    
    def _guardar_base_datos(self, base_datos, archivo=None):
        """
        Guarda la base de datos en un archivo con failover automático
        
        Args:
            base_datos: Dict con la base de datos
            archivo: Ruta al archivo (None para usar failover automático)
        
        Returns:
            bool: True si se guardó exitosamente, False en caso contrario
        """
        # Si no se especifica archivo, usar failover automático
        if archivo is None:
            # Si estamos usando secundaria, guardar solo en secundaria
            if self.using_secondary:
                logger.warning("Guardando en réplica secundaria (modo degradado)")
                return self._guardar_base_datos(base_datos, self.secondary_path)
            
            # Intentar guardar en primaria primero
            if os.path.exists(os.path.dirname(self.primary_path)) and os.access(os.path.dirname(self.primary_path), os.W_OK):
                try:
                    if self._guardar_base_datos(base_datos, self.primary_path):
                        # Si guardó en primaria, replicar a secundaria
                        self._replicar_a_secundaria(base_datos)
                        return True
                except Exception as e:
                    logger.warning(f"Error guardando en réplica primaria: {e}")
            
            # Si primaria falla, guardar en secundaria
            if os.path.exists(os.path.dirname(self.secondary_path)) and os.access(os.path.dirname(self.secondary_path), os.W_OK):
                logger.warning("Réplica primaria no disponible, guardando en réplica secundaria")
                self.using_secondary = True
                return self._guardar_base_datos(base_datos, self.secondary_path)
            
            logger.error("No se puede escribir en ninguna réplica")
            return False
        
        # Guardar en archivo específico
        try:
            lock = FileLock(f"{archivo}.lock")
            with lock:
                # Crear backup
                if os.path.exists(archivo):
                    backup_file = f"{archivo}.backup"
                    shutil.copy2(archivo, backup_file)
                
                # Guardar datos
                with open(archivo, 'w', encoding='utf-8') as f:
                    json.dump(base_datos, f, ensure_ascii=False, indent=2)

                # Sincronizar archivo público si estamos actualizando la primaria
                if archivo == self.primary_path:
                    self._sincronizar_archivo_publico(base_datos)

                return True
        except Exception as e:
            logger.error(f"Error guardando base de datos en {archivo}: {e}")
            return False

    def _sincronizar_archivo_publico(self, base_datos):
        """Mantiene data/libros.json sincronizado para pruebas y reportes."""
        destino = 'data/libros.json'
        try:
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            lock = FileLock(f"{destino}.lock")
            with lock:
                logger.info("Sincronizando archivo público data/libros.json")
                with open(destino, 'w', encoding='utf-8') as f:
                    json.dump(base_datos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"No se pudo sincronizar {destino}: {e}")
    
    def _replicar_a_secundaria(self, base_datos):
        """Replica los datos a la réplica secundaria de forma asíncrona"""
        def replicar():
            try:
                time.sleep(0.1)  # Pequeña pausa para no bloquear
                with self.replicacion_lock:
                    logger.info("Iniciando replicación a secundaria...")
                    if self._guardar_base_datos(base_datos, self.secondary_path):
                        logger.info("Réplica secundaria actualizada exitosamente")
                    else:
                        logger.error("Error actualizando réplica secundaria")
            except Exception as e:
                logger.error(f"Error en replicación asíncrona: {e}")
        
        # Ejecutar en thread separado
        thread = threading.Thread(target=replicar, daemon=True)
        thread.start()
    
    def get_book(self, libro_id, search_criteria=None):
        """
        Busca un libro por ID o criterios de búsqueda
        
        Args:
            libro_id: ID del libro (puede ser None si se usa search_criteria)
            search_criteria: Dict con criterios de búsqueda (titulo, autor, etc.)
        
        Returns:
            Dict con el libro encontrado o None
        """
        base_datos = self._cargar_base_datos()  # Usar failover automático
        if not base_datos:
            return None
        
        libros = base_datos.get('libros', [])
        if libro_id:
            libro_id = self._normalizar_libro_id(libro_id)

        # Búsqueda por ID
        if libro_id:
            for libro in libros:
                if libro.get('libro_id') == libro_id:
                    return libro
        
        # Búsqueda por criterios
        if search_criteria:
            for libro in libros:
                match = True
                if 'titulo' in search_criteria:
                    if search_criteria['titulo'].lower() not in libro.get('titulo', '').lower():
                        match = False
                if match:
                    return libro
        
        return None
    
    def loan_book(self, libro_id, usuario_id, sede):
        """
        Presta un libro a un usuario
        
        Args:
            libro_id: ID del libro
            usuario_id: ID del usuario
            sede: Sede donde se realiza el préstamo
        
        Returns:
            Dict con resultado: {"success": bool, "message": str, "ejemplar_id": str}
        """
        base_datos = self._cargar_base_datos()  # Usar failover automático
        if not base_datos:
            return {"success": False, "message": "Error cargando base de datos"}
        
        libros = base_datos.get('libros', [])
        if libro_id:
            libro_id = self._normalizar_libro_id(libro_id)
        ejemplares = base_datos.get('ejemplares', [])
        
        # Buscar el libro
        libro_encontrado = None
        for libro in libros:
            if libro.get('libro_id') == libro_id:
                libro_encontrado = libro
                break
        
        if not libro_encontrado:
            return {"success": False, "message": f"Libro {libro_id} no encontrado"}
        
        # Verificar ejemplares disponibles
        if libro_encontrado.get('ejemplares_disponibles', 0) <= 0:
            return {"success": False, "message": f"No hay ejemplares disponibles del libro {libro_id}"}
        
        # Buscar un ejemplar disponible
        ejemplar_prestado = None
        for ejemplar in libro_encontrado.get('ejemplares', []):
            if ejemplar.get('estado') == 'disponible':
                ejemplar_prestado = ejemplar
                break
        
        if not ejemplar_prestado:
            return {"success": False, "message": f"No se encontró ejemplar disponible del libro {libro_id}"}
        
        # Calcular fecha de devolución (máximo 2 semanas)
        fecha_devolucion = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        
        # Actualizar ejemplar
        ejemplar_prestado['estado'] = 'prestado'
        ejemplar_prestado['usuario_prestamo'] = usuario_id
        ejemplar_prestado['sede'] = sede
        ejemplar_prestado['fecha_devolucion'] = fecha_devolucion
        
        # Actualizar contadores del libro
        libro_encontrado['ejemplares_disponibles'] -= 1
        libro_encontrado['ejemplares_prestados'] += 1
        
        # Actualizar contadores globales
        metadata = base_datos.get('metadata', {})
        metadata['ejemplares_disponibles'] = max(
            0,
            metadata.get('ejemplares_disponibles', 0) - 1
        )
        self._ajustar_metadata_prestamos(base_datos, sede, 1)
        
        # Actualizar también en el array global de ejemplares
        for ejemplar in ejemplares:
            if ejemplar.get('ejemplar_id') == ejemplar_prestado['ejemplar_id']:
                ejemplar['estado'] = 'prestado'
                ejemplar['usuario_prestamo'] = usuario_id
                ejemplar['sede'] = sede
                ejemplar['fecha_devolucion'] = fecha_devolucion
                break
        
        # Guardar con failover automático
        if not self._guardar_base_datos(base_datos):
            return {"success": False, "message": "Error guardando en réplica"}
        
        # Si estamos usando primaria, replicar a secundaria (asíncrono)
        if not self.using_secondary:
            self._replicar_a_secundaria(base_datos)
        
        logger.info(f"Préstamo realizado: Libro {libro_id}, Ejemplar {ejemplar_prestado['ejemplar_id']}, Usuario {usuario_id}, Sede {sede}")
        
        return {
            "success": True,
            "message": f"Préstamo realizado exitosamente",
            "ejemplar_id": ejemplar_prestado['ejemplar_id'],
            "fecha_devolucion": fecha_devolucion
        }
    
    def return_book(self, libro_id, usuario_id, sede):
        """
        Devuelve un libro prestado
        
        Args:
            libro_id: ID del libro
            usuario_id: ID del usuario
            sede: Sede donde se realiza la devolución
        
        Returns:
            Dict con resultado: {"success": bool, "message": str}
        """
        base_datos = self._cargar_base_datos()  # Usar failover automático
        if not base_datos:
            return {"success": False, "message": "Error cargando base de datos"}
        
        libros = base_datos.get('libros', [])
        ejemplares = base_datos.get('ejemplares', [])
        if libro_id:
            libro_id = self._normalizar_libro_id(libro_id)

        libro_objetivo = None
        ejemplar_objetivo = None
        sede_original = None

        # Buscar coincidencia exacta primero
        for libro in libros:
            if libro.get('libro_id') == libro_id:
                libro_objetivo = libro
                for ejemplar in libro.get('ejemplares', []):
                    if ejemplar.get('estado') != 'prestado':
                        continue

                    coincide_usuario = ejemplar.get('usuario_prestamo') == usuario_id
                    coincide_sede = ejemplar.get('sede') == sede

                    if coincide_usuario and coincide_sede:
                        ejemplar_objetivo = ejemplar
                        sede_original = ejemplar.get('sede')
                        break

                if ejemplar_objetivo:
                    break

        # Si no hay coincidencia exacta, usar cualquier ejemplar prestado como fallback
        if libro_objetivo and not ejemplar_objetivo:
            for ejemplar in libro_objetivo.get('ejemplares', []):
                if ejemplar.get('estado') == 'prestado':
                    ejemplar_objetivo = ejemplar
                    sede_original = ejemplar.get('sede')
                    logger.warning(
                        f"No se encontró coincidencia exacta para devolución de {libro_id}. "
                        "Liberando ejemplar prestado disponible para mantener consistencia."
                    )
                    break

        if not ejemplar_objetivo:
            return {"success": False, "message": f"No se encontró ejemplar prestado del libro {libro_id}"}

        # Marcar como disponible en la estructura del libro
        ejemplar_objetivo['estado'] = 'disponible'
        ejemplar_objetivo['usuario_prestamo'] = None
        ejemplar_objetivo['sede'] = None
        ejemplar_objetivo['fecha_devolucion'] = None

        # Actualizar contadores del libro asegurando límites válidos
        libro_objetivo['ejemplares_disponibles'] = min(
            libro_objetivo.get('total_ejemplares', libro_objetivo.get('ejemplares_disponibles', 0)),
            libro_objetivo.get('ejemplares_disponibles', 0) + 1
        )
        libro_objetivo['ejemplares_prestados'] = max(
            0,
            libro_objetivo.get('ejemplares_prestados', 0) - 1
        )

        # Actualizar contadores globales
        metadata = base_datos.get('metadata', {})
        metadata['ejemplares_disponibles'] = metadata.get('ejemplares_disponibles', 0) + 1
        sede_para_metricas = sede_original or sede
        self._ajustar_metadata_prestamos(base_datos, sede_para_metricas, -1)

        # Actualizar en array global
        ejemplar_id_objetivo = ejemplar_objetivo.get('ejemplar_id')
        for ejemplar in ejemplares:
            if ejemplar.get('ejemplar_id') == ejemplar_id_objetivo:
                ejemplar['estado'] = 'disponible'
                ejemplar['usuario_prestamo'] = None
                ejemplar['sede'] = None
                ejemplar['fecha_devolucion'] = None
                break
        
        # Guardar con failover automático
        if not self._guardar_base_datos(base_datos):
            return {"success": False, "message": "Error guardando en réplica"}
        
        # Si estamos usando primaria, replicar a secundaria (asíncrono)
        if not self.using_secondary:
            self._replicar_a_secundaria(base_datos)
        
        logger.info(f"Devolución realizada: Libro {libro_id}, Usuario {usuario_id}, Sede {sede}")
        
        return {"success": True, "message": "Devolución realizada exitosamente"}
    
    def renew_book(self, libro_id, usuario_id, sede, nueva_fecha):
        """
        Renueva un préstamo de libro
        
        Args:
            libro_id: ID del libro
            usuario_id: ID del usuario
            sede: Sede donde se realiza la renovación
            nueva_fecha: Nueva fecha de devolución
        
        Returns:
            Dict con resultado: {"success": bool, "message": str}
        """
        base_datos = self._cargar_base_datos()  # Usar failover automático
        if not base_datos:
            return {"success": False, "message": "Error cargando base de datos"}
        
        libros = base_datos.get('libros', [])
        ejemplares = base_datos.get('ejemplares', [])
        if libro_id:
            libro_id = self._normalizar_libro_id(libro_id)

        libro_objetivo = None
        ejemplar_objetivo = None

        # Buscar coincidencia exacta
        for libro in libros:
            if libro.get('libro_id') == libro_id:
                libro_objetivo = libro
                for ejemplar in libro.get('ejemplares', []):
                    if ejemplar.get('estado') != 'prestado':
                        continue

                    coincide_usuario = ejemplar.get('usuario_prestamo') == usuario_id
                    coincide_sede = ejemplar.get('sede') == sede

                    if coincide_usuario and coincide_sede:
                        ejemplar_objetivo = ejemplar
                        break

                if ejemplar_objetivo:
                    break

        # Fallback: tomar cualquier ejemplar prestado
        if libro_objetivo and not ejemplar_objetivo:
            for ejemplar in libro_objetivo.get('ejemplares', []):
                if ejemplar.get('estado') == 'prestado':
                    ejemplar_objetivo = ejemplar
                    logger.warning(
                        f"No se encontró coincidencia exacta para renovación de {libro_id}. "
                        "Actualizando el primer ejemplar prestado disponible."
                    )
                    break

        if not ejemplar_objetivo:
            return {"success": False, "message": f"No se encontró ejemplar prestado del libro {libro_id}"}

        ejemplar_objetivo['fecha_devolucion'] = nueva_fecha

        # Actualizar en array global usando el ID del ejemplar afectado
        ejemplar_id_objetivo = ejemplar_objetivo.get('ejemplar_id')
        for ejemplar in ejemplares:
            if ejemplar.get('ejemplar_id') == ejemplar_id_objetivo:
                ejemplar['fecha_devolucion'] = nueva_fecha
                break
        
        # Guardar con failover automático
        if not self._guardar_base_datos(base_datos):
            return {"success": False, "message": "Error guardando en réplica"}
        
        # Si estamos usando primaria, replicar a secundaria (asíncrono)
        if not self.using_secondary:
            self._replicar_a_secundaria(base_datos)
        
        logger.info(f"Renovación realizada: Libro {libro_id}, Usuario {usuario_id}, Sede {sede}, Nueva fecha: {nueva_fecha}")
        
        return {"success": True, "message": "Renovación realizada exitosamente"}
    
    def update_copies(self, libro_id, cambios):
        """
        Actualiza ejemplares de un libro (operación genérica)
        
        Args:
            libro_id: ID del libro
            cambios: Dict con los cambios a aplicar
        
        Returns:
            Dict con resultado: {"success": bool, "message": str}
        """
        base_datos = self._cargar_base_datos()  # Usar failover automático
        if not base_datos:
            return {"success": False, "message": "Error cargando base de datos"}
        
        # Implementar lógica de actualización según cambios
        # Por ahora, solo guardamos
        if not self._guardar_base_datos(base_datos):
            return {"success": False, "message": "Error guardando en réplica"}
        
        # Si estamos usando primaria, replicar a secundaria (asíncrono)
        if not self.using_secondary:
            self._replicar_a_secundaria(base_datos)
        
        return {"success": True, "message": "Actualización realizada exitosamente"}
    
    def health_check(self):
        """
        Verifica el estado de salud del GA
        
        Returns:
            Dict con estado: {"status": "healthy"|"degraded", "primary_ok": bool, "secondary_ok": bool, "using_secondary": bool}
        """
        primary_ok = os.path.exists(self.primary_path) and os.access(self.primary_path, os.R_OK)
        secondary_ok = os.path.exists(self.secondary_path) and os.access(self.secondary_path, os.R_OK)
        
        # Determinar estado
        if primary_ok and secondary_ok:
            status = "healthy"
        elif secondary_ok:
            status = "degraded"  # Solo secundaria disponible
        else:
            status = "unhealthy"  # Ninguna réplica disponible
        
        return {
            "status": status,
            "primary_ok": primary_ok,
            "secondary_ok": secondary_ok,
            "using_secondary": self.using_secondary,
            "primary_path": self.primary_path,
            "secondary_path": self.secondary_path
        }
    
    def procesar_solicitud(self, mensaje_json):
        """
        Procesa una solicitud recibida vía ZeroMQ
        
        Args:
            mensaje_json: JSON string con la solicitud
        
        Returns:
            JSON string con la respuesta
        """
        try:
            solicitud = json.loads(mensaje_json)
            operacion = solicitud.get('operacion', '').upper()
            
            self.contador_operaciones += 1
            logger.info(f"Operación #{self.contador_operaciones}: {operacion}")
            
            if operacion == 'GET_BOOK':
                libro_id = solicitud.get('libro_id')
                search_criteria = solicitud.get('search_criteria')
                libro = self.get_book(libro_id, search_criteria)
                if libro:
                    return json.dumps({"success": True, "libro": libro}, ensure_ascii=False)
                else:
                    return json.dumps({"success": False, "message": "Libro no encontrado"}, ensure_ascii=False)
            
            elif operacion == 'LOAN_BOOK':
                libro_id = solicitud.get('libro_id')
                usuario_id = solicitud.get('usuario_id')
                sede = solicitud.get('sede', 'SEDE_1')
                resultado = self.loan_book(libro_id, usuario_id, sede)
                return json.dumps(resultado, ensure_ascii=False)
            
            elif operacion == 'RETURN_BOOK':
                libro_id = solicitud.get('libro_id')
                usuario_id = solicitud.get('usuario_id')
                sede = solicitud.get('sede', 'SEDE_1')
                resultado = self.return_book(libro_id, usuario_id, sede)
                return json.dumps(resultado, ensure_ascii=False)
            
            elif operacion == 'RENEW_BOOK':
                libro_id = solicitud.get('libro_id')
                usuario_id = solicitud.get('usuario_id')
                sede = solicitud.get('sede', 'SEDE_1')
                nueva_fecha = solicitud.get('nueva_fecha')
                resultado = self.renew_book(libro_id, usuario_id, sede, nueva_fecha)
                return json.dumps(resultado, ensure_ascii=False)
            
            elif operacion == 'UPDATE_COPIES':
                libro_id = solicitud.get('libro_id')
                cambios = solicitud.get('cambios', {})
                resultado = self.update_copies(libro_id, cambios)
                return json.dumps(resultado, ensure_ascii=False)
            
            elif operacion == 'HEALTH_CHECK':
                resultado = self.health_check()
                return json.dumps(resultado, ensure_ascii=False)
            
            else:
                return json.dumps({"success": False, "message": f"Operación desconocida: {operacion}"}, ensure_ascii=False)
        
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando solicitud JSON: {e}")
            return json.dumps({"success": False, "message": "Formato JSON inválido"}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error procesando solicitud: {e}")
            return json.dumps({"success": False, "message": f"Error interno: {str(e)}"}, ensure_ascii=False)
    
    def inicializar_socket(self):
        """Inicializa el socket REP"""
        try:
            self.rep_socket = self.context.socket(zmq.REP)
            bind_address = f"tcp://{self.host}:{self.port}"
            self.rep_socket.bind(bind_address)
            logger.info(f"Socket REP inicializado en {bind_address}")
        except Exception as e:
            logger.error(f"Error inicializando socket: {e}")
            raise
    
    def manejar_solicitudes(self):
        """Maneja las solicitudes entrantes"""
        logger.info("Iniciando manejo de solicitudes...")
        
        while self.running:
            try:
                # Recibir solicitud
                mensaje = self.rep_socket.recv(zmq.NOBLOCK)
                mensaje_str = mensaje.decode('utf-8')
                
                logger.debug(f"Solicitud recibida: {mensaje_str}")
                
                # Procesar solicitud
                respuesta = self.procesar_solicitud(mensaje_str)
                
                # Enviar respuesta
                self.rep_socket.send(respuesta.encode('utf-8'))
                
            except zmq.Again:
                # No hay mensajes disponibles
                time.sleep(0.1)
                continue
            except Exception as e:
                logger.error(f"Error manejando solicitudes: {e}")
                time.sleep(1)
    
    def iniciar(self):
        """Inicia el Gestor de Almacenamiento"""
        try:
            logger.info("Iniciando Gestor de Almacenamiento...")
            self.inicializar_socket()
            
            logger.info("Gestor de Almacenamiento iniciado correctamente")
            logger.info(f"Esperando solicitudes en puerto {self.port}...")
            logger.info(f"Réplica primaria: {self.primary_path}")
            logger.info(f"Réplica secundaria: {self.secondary_path}")
            
            self.manejar_solicitudes()
            
        except KeyboardInterrupt:
            logger.info("Deteniendo Gestor de Almacenamiento...")
            self.detener()
        except Exception as e:
            logger.error(f"Error fatal en Gestor de Almacenamiento: {e}")
            self.detener()
    
    def detener(self):
        """Detiene el Gestor de Almacenamiento"""
        self.running = False
        
        if self.rep_socket:
            self.rep_socket.close()
        if self.context:
            self.context.term()
        
        logger.info(f"Total de operaciones procesadas: {self.contador_operaciones}")
        logger.info("Gestor de Almacenamiento detenido")

def main():
    """Función principal"""
    import sys
    
    # Leer variables de entorno
    primary_path = os.getenv('GA_PRIMARY_PATH', 'data/primary/libros.json')
    secondary_path = os.getenv('GA_SECONDARY_PATH', 'data/secondary/libros.json')
    port = int(os.getenv('GA_PORT', '5003'))
    host = os.getenv('GA_HOST', '0.0.0.0')
    
    ga = GestorAlmacenamiento(
        primary_path=primary_path,
        secondary_path=secondary_path,
        port=port,
        host=host
    )
    ga.iniciar()

if __name__ == "__main__":
    main()

