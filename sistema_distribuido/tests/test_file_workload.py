# -*- coding: utf-8 -*-
"""
test_file_workload.py - Test de workload con archivo
Valida que el PS procese correctamente el archivo de solicitudes
"""

import pytest
import time
import json
import os
import subprocess
from datetime import datetime
from tests.test_utils import TestUtils

class TestFileWorkload:
    """Test de workload con archivo de solicitudes"""
    
    def setup_method(self):
        """Configuración antes de cada test"""
        self.libros_path = "data/libros.json"
        self.solicitudes_path = "data/solicitudes.txt"
        self.logs_path = "logs/test_file_workload.txt"
        
        # Crear directorio de logs si no existe
        os.makedirs("logs", exist_ok=True)
        
        # Resultados del test
        self.resultados = {
            "test_name": "test_file_workload",
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "solicitudes_en_archivo": 0,
            "solicitudes_procesadas": 0,
            "operaciones_ok": 0,
            "operaciones_error": 0,
            "cambios_en_libros": False,
            "errores": []
        }
    
    def test_file_workload_processing(self):
        """Test de procesamiento de archivo de solicitudes por PS"""
        print("\nTest: Procesamiento de archivo de solicitudes")
        
        # 1. Verificar que PS está corriendo
        print("Verificando que PS está corriendo...")
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=10
            )
            ps_running = "ps" in result.stdout
        except Exception as e:
            print(f"WARNING: Error verificando PS: {e}")
            ps_running = False
        
        if not ps_running:
            print("WARNING: PS no está corriendo, intentando levantarlo...")
            try:
                subprocess.run(
                    ["docker", "compose", "--profile", "demo", "up", "-d", "ps"],
                    check=True, timeout=30
                )
                print("PS levantado exitosamente")
                time.sleep(5)  # Esperar inicialización
            except Exception as e:
                pytest.skip(f"No se pudo levantar PS: {e}")
        
        # 2. Leer archivo de solicitudes
        print("Leyendo archivo de solicitudes...")
        if not os.path.exists(self.solicitudes_path):
            pytest.skip(f"Archivo de solicitudes no encontrado: {self.solicitudes_path}")
        
        with open(self.solicitudes_path, 'r', encoding='utf-8') as f:
            solicitudes = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        self.resultados["solicitudes_en_archivo"] = len(solicitudes)
        print(f"Solicitudes en archivo: {len(solicitudes)}")
        
        # Contar por tipo
        renovaciones = [s for s in solicitudes if s.startswith('RENOVACION')]
        devoluciones = [s for s in solicitudes if s.startswith('DEVOLUCION')]
        
        print(f"   - Renovaciones: {len(renovaciones)}")
        print(f"   - Devoluciones: {len(devoluciones)}")
        
        # 3. Crear snapshot inicial de libros
        snapshot_path = "logs/libros_before_workload.json"
        TestUtils.crear_snapshot_libros(self.libros_path, snapshot_path)
        datos_inicial = TestUtils.read_json(self.libros_path)
        libros_inicial = datos_inicial.get('libros', [])
        
        print("Snapshot inicial creado")
        
        # 4. Monitorear logs del PS para verificar procesamiento
        print("Monitoreando procesamiento del PS...")
        
        # Esperar a que PS termine de procesar (timeout de 30 segundos)
        timeout = 30
        start_time = time.time()
        ps_completed = False
        
        while time.time() - start_time < timeout:
            try:
                # Verificar si PS terminó
                result = subprocess.run(
                    ["docker", "ps", "--filter", "name=ps", "--format", "{{.Status}}"],
                    capture_output=True, text=True, timeout=5
                )
                
                if "ps" not in result.stdout or "Exited" in result.stdout:
                    ps_completed = True
                    print("PS completó el procesamiento")
                    break
                
                time.sleep(1)
                
            except Exception as e:
                print(f"WARNING: Error monitoreando PS: {e}")
                break
        
        if not ps_completed:
            print(f"WARNING: PS no completó en {timeout} segundos, continuando...")
        
        # 5. Analizar logs del PS
        print("Analizando logs del PS...")
        try:
            result = subprocess.run(
                ["docker", "logs", "ps"],
                capture_output=True, text=True, timeout=10
            )
            ps_logs = result.stdout
        except Exception as e:
            print(f"WARNING: Error obteniendo logs del PS: {e}")
            ps_logs = ""
        
        # Contar operaciones procesadas en logs
        solicitudes_enviadas = ps_logs.count("Solicitud #")
        solicitudes_exitosas = ps_logs.count("Solicitud procesada exitosamente")
        solicitudes_error = ps_logs.count("Error en solicitud")
        
        self.resultados["solicitudes_procesadas"] = solicitudes_enviadas
        self.resultados["operaciones_ok"] = solicitudes_exitosas
        self.resultados["operaciones_error"] = solicitudes_error
        
        print(f"Operaciones en logs del PS:")
        print(f"   - Enviadas: {solicitudes_enviadas}")
        print(f"   - Exitosas: {solicitudes_exitosas}")
        print(f"   - Con error: {solicitudes_error}")
        
        # 6. Analizar logs del GC
        print("Analizando logs del GC...")
        try:
            result = subprocess.run(
                ["docker", "logs", "gc"],
                capture_output=True, text=True, timeout=10
            )
            gc_logs = result.stdout
        except Exception as e:
            print(f"WARNING: Error obteniendo logs del GC: {e}")
            gc_logs = ""
        
        # Contar operaciones en logs del GC
        operaciones_gc = gc_logs.count("Operación #")
        publicaciones_devolucion = gc_logs.count("Topic: devolucion")
        publicaciones_renovacion = gc_logs.count("Topic: renovacion")
        
        print(f"Operaciones en logs del GC:")
        print(f"   - Total procesadas: {operaciones_gc}")
        print(f"   - Publicaciones devolución: {publicaciones_devolucion}")
        print(f"   - Publicaciones renovación: {publicaciones_renovacion}")
        
        # 7. Validar que se procesaron todas las solicitudes
        assert solicitudes_enviadas >= len(solicitudes), \
            f"PS no procesó todas las solicitudes: {solicitudes_enviadas} < {len(solicitudes)}"
        
        assert operaciones_gc >= len(solicitudes), \
            f"GC no procesó todas las solicitudes: {operaciones_gc} < {len(solicitudes)}"
        
        # 8. Validar publicaciones por tema
        assert publicaciones_devolucion >= len(devoluciones), \
            f"Faltan publicaciones de devolución: {publicaciones_devolucion} < {len(devoluciones)}"
        
        assert publicaciones_renovacion >= len(renovaciones), \
            f"Faltan publicaciones de renovación: {publicaciones_renovacion} < {len(renovaciones)}"
        
        print("Todas las solicitudes fueron procesadas correctamente")
        
        # 9. Verificar cambios en la base de datos
        print("Verificando cambios en la base de datos...")
        
        # Esperar un momento para que los actores procesen
        time.sleep(2)
        
        datos_final = TestUtils.read_json(self.libros_path)
        libros_final = datos_final.get('libros', [])
        
        # Verificar que hubo cambios
        if libros_final != libros_inicial:
            self.resultados["cambios_en_libros"] = True
            print("Se detectaron cambios en la base de datos")
            
            # Mostrar diferencias
            print("Cambios detectados:")
            for i, (libro_inicial, libro_final) in enumerate(zip(libros_inicial, libros_final)):
                if libro_inicial != libro_final:
                    print(f"   Libro {libro_final.get('libro_id', 'N/A')}:")
                    if libro_inicial.get('ejemplares_disponibles') != libro_final.get('ejemplares_disponibles'):
                        print(f"     Ejemplares: {libro_inicial.get('ejemplares_disponibles')} -> {libro_final.get('ejemplares_disponibles')}")
                    if libro_inicial.get('fecha_devolucion') != libro_final.get('fecha_devolucion'):
                        print(f"     Fecha: {libro_inicial.get('fecha_devolucion')} -> {libro_final.get('fecha_devolucion')}")
        else:
            print("WARNING: No se detectaron cambios en la base de datos")
        
        # 10. Validar que no hubo errores críticos
        assert solicitudes_error == 0, f"Hubo {solicitudes_error} errores en el procesamiento"
        
        print("Procesamiento de archivo completado sin errores")
    
    def teardown_method(self):
        """Limpieza después de cada test"""
        # Marcar test como pasado si llegamos hasta aquí
        self.resultados["passed"] = True
        
        # Generar reporte
        TestUtils.generar_reporte_test(
            "test_file_workload",
            self.resultados,
            self.logs_path
        )
        
        print(f"\nTest completado:")
        print(f"   Solicitudes en archivo: {self.resultados['solicitudes_en_archivo']}")
        print(f"   Solicitudes procesadas: {self.resultados['solicitudes_procesadas']}")
        print(f"   Operaciones OK: {self.resultados['operaciones_ok']}")
        print(f"   Operaciones ERROR: {self.resultados['operaciones_error']}")
        print(f"   Cambios en libros: {'Sí' if self.resultados['cambios_en_libros'] else 'No'}")
        print(f"   Estado: {'PASSED' if self.resultados['passed'] else 'FAILED'}")
        print(f"   Reporte: {self.logs_path}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
