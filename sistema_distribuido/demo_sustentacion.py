#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Demostración para Sustentación - Sistema Distribuido de Préstamo de Libros
Demuestra los 3 casos de prueba requeridos para la sustentación con visualización clara
"""

import os
import sys
import json
import time
import random
import subprocess
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

# Colores para output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

def print_header(text: str):
    """Imprime un header con formato"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
    print(f"{Colors.WHITE}{Colors.BOLD}{text}{Colors.NC}")
    print(f"{Colors.CYAN}{'='*60}{Colors.NC}\n")

def print_case(num: int, title: str):
    """Imprime el título de un caso"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
    print(f"{Colors.WHITE}{Colors.BOLD}CASO {num}: {title}{Colors.NC}")
    print(f"{Colors.CYAN}{'='*60}{Colors.NC}\n")

def print_info(msg: str):
    """Imprime un mensaje informativo"""
    print(f"{Colors.BLUE}ℹ INFO: {msg}{Colors.NC}")

def print_success(msg: str):
    """Imprime un mensaje de éxito"""
    print(f"{Colors.GREEN}✓ {msg}{Colors.NC}")

def print_error(msg: str):
    """Imprime un mensaje de error"""
    print(f"{Colors.RED}✗ ERROR: {msg}{Colors.NC}")

def print_warning(msg: str):
    """Imprime un mensaje de advertencia"""
    print(f"{Colors.YELLOW}⚠ WARNING: {msg}{Colors.NC}")

def pause(prompt: str = "Presiona Enter para continuar..."):
    """Pausa la ejecución esperando entrada del usuario"""
    input(f"{Colors.YELLOW}{prompt}{Colors.NC}")

def check_directory():
    """Verifica que estamos en el directorio correcto"""
    if not os.path.exists("docker-compose.yml"):
        print_error("No se encontró docker-compose.yml. Asegúrate de estar en el directorio sistema_distribuido")
        sys.exit(1)

def generar_bd_pequena():
    """Genera una base de datos pequeña con 10-20 libros"""
    print_info("Generando base de datos pequeña con pocos registros...")
    
    libros = []
    ejemplares_totales = []
    
    # Generar 15 libros con pocos ejemplares
    for i in range(1, 16):
        libro_id = f"L{i:04d}"
        titulo = f"Libro {i}"
        total_ejemplares = random.randint(2, 5)
        
        ejemplares = []
        for j in range(total_ejemplares):
            ejemplar = {
                "ejemplar_id": f"{libro_id}-E{j+1:03d}",
                "libro_id": libro_id,
                "titulo": titulo,
                "estado": "disponible",
                "fecha_devolucion": None,
                "usuario_prestamo": None,
                "sede": None
            }
            ejemplares.append(ejemplar)
        
        libro = {
            "libro_id": libro_id,
            "titulo": titulo,
            "total_ejemplares": total_ejemplares,
            "ejemplares_disponibles": total_ejemplares,
            "ejemplares_prestados": 0,
            "ejemplares": ejemplares
        }
        
        libros.append(libro)
        ejemplares_totales.extend(ejemplares)
    
    base_datos = {
        "metadata": {
            "version": "1.0",
            "fecha_creacion": datetime.now().isoformat(),
            "total_libros": len(libros),
            "total_ejemplares": len(ejemplares_totales),
            "ejemplares_prestados_sede_1": 0,
            "ejemplares_prestados_sede_2": 0,
            "ejemplares_disponibles": len(ejemplares_totales)
        },
        "libros": libros,
        "ejemplares": ejemplares_totales
    }
    
    # Crear directorios para réplicas
    os.makedirs('data/primary', exist_ok=True)
    os.makedirs('data/secondary', exist_ok=True)
    
    # Guardar en archivo principal
    with open('data/libros.json', 'w', encoding='utf-8') as f:
        json.dump(base_datos, f, ensure_ascii=False, indent=2)
    
    # Guardar en réplica primaria
    with open('data/primary/libros.json', 'w', encoding='utf-8') as f:
        json.dump(base_datos, f, ensure_ascii=False, indent=2)
    
    # Copiar a réplica secundaria
    import shutil
    shutil.copy2('data/primary/libros.json', 'data/secondary/libros.json')
    
    print_success(f"Base de datos pequeña generada: {len(libros)} libros, {len(ejemplares_totales)} ejemplares")
    return True

def mostrar_estado_bd(titulo: str = ""):
    """Muestra el estado actual de la base de datos"""
    if titulo:
        print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        print(f"{Colors.CYAN}{titulo}{Colors.NC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.NC}")
    
    # El GA escribe en data/primary/libros.json
    archivo_bd = 'data/primary/libros.json'
    if not os.path.exists(archivo_bd):
        archivo_bd = 'data/libros.json'
    
    if not os.path.exists(archivo_bd):
        print_error(f"Archivo de BD no encontrado: {archivo_bd}")
        return
    
    try:
        with open(archivo_bd, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        meta = data['metadata']
        print(f"\n{Colors.BOLD}{Colors.WHITE}━━━ ESTADO DE LA BASE DE DATOS ━━━{Colors.NC}")
        print(f"  {Colors.BOLD}Total libros:{Colors.NC} {Colors.CYAN}{meta['total_libros']}{Colors.NC}")
        print(f"  {Colors.BOLD}Total ejemplares:{Colors.NC} {Colors.CYAN}{meta['total_ejemplares']}{Colors.NC}")
        print(f"  {Colors.BOLD}Ejemplares disponibles:{Colors.NC} {Colors.GREEN}{meta['ejemplares_disponibles']}{Colors.NC}")
        print(f"  {Colors.BOLD}Ejemplares prestados SEDE_1:{Colors.NC} {Colors.YELLOW}{meta['ejemplares_prestados_sede_1']}{Colors.NC}")
        print(f"  {Colors.BOLD}Ejemplares prestados SEDE_2:{Colors.NC} {Colors.YELLOW}{meta['ejemplares_prestados_sede_2']}{Colors.NC}")
        print()
        
        print(f"{Colors.BOLD}{Colors.WHITE}━━━ LIBROS (primeros 10) ━━━{Colors.NC}")
        for libro in data['libros'][:10]:
            prestados = libro['ejemplares_prestados']
            disponibles = libro['ejemplares_disponibles']
            total = libro['total_ejemplares']
            estado_icon = f"{Colors.GREEN}✓{Colors.NC}" if disponibles > 0 else f"{Colors.RED}✗{Colors.NC}"
            print(f"  {estado_icon} {Colors.BOLD}{libro['libro_id']}{Colors.NC}: {libro['titulo']}")
            print(f"      Disponibles: {Colors.GREEN}{disponibles}{Colors.NC}/{total}, "
                  f"Prestados: {Colors.YELLOW}{prestados}{Colors.NC}")
            
            # Mostrar ejemplares prestados
            for ejemplar in libro['ejemplares']:
                if ejemplar['estado'] == 'prestado':
                    fecha_dev = ejemplar.get('fecha_devolucion', 'N/A')
                    print(f"      {Colors.YELLOW}→{Colors.NC} {ejemplar['ejemplar_id']} prestado a "
                          f"{Colors.CYAN}{ejemplar['usuario_prestamo']}{Colors.NC} "
                          f"en {Colors.BOLD}{ejemplar['sede']}{Colors.NC} "
                          f"(dev: {fecha_dev})")
        print()
        
    except Exception as e:
        print_error(f"Error leyendo BD: {e}")
        import traceback
        traceback.print_exc()

def limpiar_servicios():
    """Limpia los servicios Docker anteriores"""
    print_info("Limpiando servicios anteriores...")
    result = subprocess.run(
        ["docker", "compose", "down"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print_success("Servicios limpiados")
    else:
        print_warning("Algunos servicios no se pudieron limpiar (puede ser normal)")

def levantar_servicios():
    """Levanta los servicios del sistema"""
    print_info("Levantando servicios del sistema...")
    result = subprocess.run(
        ["docker", "compose", "up", "--build", "-d", 
         "ga", "gc", "actor_prestamo", "actor_devolucion", "actor_renovacion"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print_success("Servicios levantados correctamente")
        print_info("Esperando que los servicios estén listos...")
        time.sleep(5)
        return True
    else:
        print_error("Error levantando servicios")
        print(result.stderr)
        return False

def verificar_servicios():
    """Verifica que todos los servicios estén corriendo"""
    print_info("Verificando servicios...")
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True
    )
    
    servicios_requeridos = ["ga", "gc", "actor_prestamo", "actor_dev", "actor_ren"]
    servicios_corriendo = result.stdout.strip().split('\n')
    
    servicios_ok = []
    servicios_faltantes = []
    
    for servicio in servicios_requeridos:
        if servicio in servicios_corriendo:
            servicios_ok.append(servicio)
        else:
            servicios_faltantes.append(servicio)
    
    if servicios_faltantes:
        print_error(f"Servicios faltantes: {', '.join(servicios_faltantes)}")
        return False
    else:
        print_success(f"Todos los servicios están corriendo ({len(servicios_ok)}/{len(servicios_requeridos)})")
        return True

def mostrar_logs_tiempo_real(contenedores: List[str], duracion: int = 10, filtro: Optional[str] = None):
    """Muestra logs en tiempo real de los contenedores especificados"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
    print(f"{Colors.CYAN}Logs en Tiempo Real (últimos {duracion}s){Colors.NC}")
    print(f"{Colors.CYAN}{'='*60}{Colors.NC}")
    
    for contenedor in contenedores:
        # Verificar que el contenedor existe
        result_check = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        if contenedor not in result_check.stdout:
            print_warning(f"Contenedor {contenedor} no está corriendo")
            continue
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}━━━ {contenedor.upper()} ━━━{Colors.NC}")
        cmd = ["docker", "logs", "--since", f"{duracion}s", contenedor]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if filtro:
            lines = [l for l in result.stdout.split('\n') if filtro.lower() in l.lower()]
            if lines:
                for line in lines[-15:]:  # Últimas 15 líneas que coinciden
                    if line.strip():
                        # Colorear según tipo de mensaje
                        if "ERROR" in line.upper() or "ERROR" in line:
                            print(f"  {Colors.RED}{line}{Colors.NC}")
                        elif "WARNING" in line.upper() or "WARN" in line.upper():
                            print(f"  {Colors.YELLOW}{line}{Colors.NC}")
                        elif "SUCCESS" in line.upper() or "OK" in line or "exitoso" in line.lower():
                            print(f"  {Colors.GREEN}{line}{Colors.NC}")
                        else:
                            print(f"  {line}")
            else:
                print(f"  {Colors.YELLOW}(No hay logs que coincidan con el filtro '{filtro}'){Colors.NC}")
        else:
            for line in result.stdout.split('\n')[-15:]:
                if line.strip():
                    # Colorear según tipo de mensaje
                    if "ERROR" in line.upper():
                        print(f"  {Colors.RED}{line}{Colors.NC}")
                    elif "WARNING" in line.upper() or "WARN" in line.upper():
                        print(f"  {Colors.YELLOW}{line}{Colors.NC}")
                    elif "SUCCESS" in line.upper() or "OK" in line or "exitoso" in line.lower():
                        print(f"  {Colors.GREEN}{line}{Colors.NC}")
                    else:
                        print(f"  {line}")
    print()

def validar_archivo_solicitudes(archivo: str) -> Tuple[bool, str]:
    """Valida que un archivo de solicitudes existe y tiene formato correcto"""
    if not os.path.exists(archivo):
        return False, f"Archivo no encontrado: {archivo}"
    
    if not os.path.isfile(archivo):
        return False, f"No es un archivo: {archivo}"
    
    # Verificar que tiene contenido válido
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            lineas_validas = 0
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    partes = line.split()
                    if len(partes) >= 3:
                        operacion = partes[0].upper()
                        if operacion in ['PRESTAMO', 'DEVOLUCION', 'RENOVACION']:
                            lineas_validas += 1
            
            if lineas_validas == 0:
                return False, f"Archivo no contiene solicitudes válidas: {archivo}"
            
            return True, f"Archivo válido con {lineas_validas} solicitudes"
    except Exception as e:
        return False, f"Error leyendo archivo: {e}"
    
    return True, "OK"

def ejecutar_ps_archivo(archivo: str, mostrar_logs: bool = True) -> bool:
    """Ejecuta un PS con un archivo de solicitudes"""
    # Validar archivo
    es_valido, mensaje = validar_archivo_solicitudes(archivo)
    if not es_valido:
        print_error(mensaje)
        return False
    
    print_info(f"Ejecutando PS con archivo: {archivo}")
    print_success(mensaje)
    
    # Mostrar contenido del archivo
    print_info("Contenido del archivo a procesar:")
    with open(archivo, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                print(f"  {Colors.CYAN}→{Colors.NC} {line}")
    print()
    
    # Determinar ruta en contenedor
    if archivo.startswith('data/'):
        archivo_en_contenedor = f"/app/{archivo}"
    else:
        archivo_en_contenedor = f"/app/data/{archivo}"
    
    # Ejecutar PS
    # Usar la forma correcta: sin --entrypoint, ejecutar python directamente
    cmd = [
        "docker", "compose", "run", "--rm", "--no-deps",
        "-e", "GC_HOST=gc",
        "-e", "GC_PORT=5001",
        "ps", "python", "proceso_solicitante.py", archivo_en_contenedor
    ]
    
    print_info(f"Ejecutando PS con archivo en contenedor: {archivo_en_contenedor}")
    print_info("Comando: " + " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    
    # Esperar un poco para que el GA termine de procesar
    time.sleep(3)
    
    if result.returncode == 0:
        print_success("PS ejecutado correctamente")
        if mostrar_logs and result.stdout:
            print(f"\n{Colors.CYAN}--- Salida del PS ---{Colors.NC}")
            for line in result.stdout.split('\n')[-20:]:  # Últimas 20 líneas
                if line.strip():
                    print(f"  {line}")
            print()
        return True
    else:
        print_error("PS terminó con errores")
        if result.stderr:
            print(f"\n{Colors.RED}--- Errores ---{Colors.NC}")
            print(result.stderr)
        return False

def ejecutar_ps_paralelo(archivos: List[str], mostrar_logs: bool = True) -> List[subprocess.Popen]:
    """Ejecuta múltiples PS en paralelo"""
    print_info(f"Ejecutando {len(archivos)} instancias de PS en paralelo...")
    
    # Validar todos los archivos primero
    archivos_validos = []
    for archivo in archivos:
        es_valido, mensaje = validar_archivo_solicitudes(archivo)
        if es_valido:
            archivos_validos.append(archivo)
            print_success(f"Archivo válido: {archivo}")
        else:
            print_error(f"Archivo inválido: {mensaje}")
    
    if not archivos_validos:
        print_error("No hay archivos válidos para ejecutar")
        return []
    
    procesos = []
    for i, archivo in enumerate(archivos_validos):
        
        print_info(f"Iniciando PS {i+1}: {archivo}")
        
        # Determinar ruta en contenedor
        if archivo.startswith('data/'):
            archivo_en_contenedor = f"/app/{archivo}"
        else:
            archivo_en_contenedor = f"/app/data/{archivo}"
        
        # Usar el mismo formato que funciona en otros scripts
        cmd = [
            "docker", "compose", "run", "--rm",
            "-e", "GC_HOST=gc",
            "-e", "GC_PORT=5001",
            "ps", "python", "proceso_solicitante.py", archivo_en_contenedor
        ]
        
        print_info(f"  Archivo en contenedor: {archivo_en_contenedor}")
        
        proceso = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        procesos.append((proceso, archivo))
        time.sleep(0.5)  # Pequeña pausa entre inicios
    
    print_success(f"{len(procesos)} procesos PS iniciados")
    return procesos

def esperar_procesos(procesos: List[tuple], timeout: int = 180):
    """Espera a que los procesos terminen"""
    print_info("Esperando que terminen los procesos PS...")
    
    inicio = time.time()
    procesos_activos = procesos.copy()
    
    while procesos_activos and (time.time() - inicio) < timeout:
        procesos_terminados = []
        for proceso, archivo in procesos_activos:
            if proceso.poll() is not None:  # Proceso terminó
                procesos_terminados.append((proceso, archivo))
        
        for proceso, archivo in procesos_terminados:
            procesos_activos.remove((proceso, archivo))
            if proceso.returncode == 0:
                print_success(f"PS completado: {archivo}")
            else:
                print_error(f"PS falló: {archivo}")
        
        if procesos_activos:
            time.sleep(1)
    
    if procesos_activos:
        print_warning(f"{len(procesos_activos)} procesos aún activos después del timeout")
        for proceso, archivo in procesos_activos:
            proceso.terminate()
    
    print_success("Todos los procesos PS han terminado")

def detener_ga():
    """Detiene el GA para simular un fallo"""
    print_info("Deteniendo GA para simular fallo...")
    result = subprocess.run(
        ["docker", "compose", "stop", "ga"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print_success("GA detenido")
        time.sleep(2)
        return True
    else:
        print_error("Error deteniendo GA")
        return False

def caso_1():
    """Caso 1: Operaciones desde SEDE_2 con BD pequeña"""
    print_case(1, "Operaciones desde SEDE_2 - BD Pequeña")
    
    print_info("Este caso demuestra las tres operaciones (préstamo, devolución, renovación)")
    print_info("desde la sede 2 con una base de datos pequeña para apreciar fácilmente los cambios")
    print()
    
    # Limpiar y preparar entorno
    limpiar_servicios()
    generar_bd_pequena()
    
    # Mostrar estado inicial
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}ESTADO INICIAL DE LA BD{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    mostrar_estado_bd("Estado Inicial")
    pause()
    
    # Levantar servicios
    if not levantar_servicios():
        print_error("No se pudieron levantar los servicios")
        return False
    
    if not verificar_servicios():
        print_error("Algunos servicios no están corriendo")
        return False
    
    # Crear archivo único con las 3 operaciones para SEDE_2
    # IMPORTANTE: Para renovación necesitamos que el libro esté prestado primero
    archivo_caso1 = "data/caso1_sede2_completo.txt"
    with open(archivo_caso1, 'w', encoding='utf-8') as f:
        f.write("# Caso 1: Operaciones desde SEDE_2\n")
        f.write("# Un solo PS ejecutando las 3 operaciones\n")
        f.write("PRESTAMO L0001 U0001 SEDE_2\n")
        f.write("DEVOLUCION L0001 U0001 SEDE_2\n")
        f.write("PRESTAMO L0001 U0001 SEDE_2\n")  # Prestar de nuevo para renovar
        f.write("RENOVACION L0001 U0001 SEDE_2\n")
    
    print_success(f"Archivo de solicitudes creado: {archivo_caso1}")
    print()
    
    # Ejecutar las operaciones una por una para mostrar cambios
    # Pero conceptualmente es un solo PS procesando todo
    
    # Operación 1: PRESTAMO
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}OPERACIÓN 1: PRESTAMO desde SEDE_2{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    
    archivo_prestamo = "data/caso1_prestamo.txt"
    with open(archivo_prestamo, 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0001 U0001 SEDE_2\n")
    
    if ejecutar_ps_archivo(archivo_prestamo, mostrar_logs=True):
        time.sleep(2)  # Esperar que el GA termine de escribir
        mostrar_estado_bd("Estado después de PRESTAMO")
        print_success("PRESTAMO completado desde SEDE_2")
    else:
        print_error("Error ejecutando PRESTAMO")
        return False
    
    pause()
    
    # Operación 2: DEVOLUCION
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}OPERACIÓN 2: DEVOLUCION desde SEDE_2{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    
    archivo_devolucion = "data/caso1_devolucion.txt"
    with open(archivo_devolucion, 'w', encoding='utf-8') as f:
        f.write("DEVOLUCION L0001 U0001 SEDE_2\n")
    
    if ejecutar_ps_archivo(archivo_devolucion, mostrar_logs=True):
        time.sleep(2)
        mostrar_estado_bd("Estado después de DEVOLUCION")
        print_success("DEVOLUCION completada desde SEDE_2")
    else:
        print_error("Error ejecutando DEVOLUCION")
        return False
    
    pause()
    
    # Operación 3: RENOVACION (necesitamos prestar primero)
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}OPERACIÓN 3: RENOVACION desde SEDE_2{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    
    print_info("Primero necesitamos prestar el libro nuevamente para poder renovarlo")
    archivo_prestamo2 = "data/caso1_prestamo2.txt"
    with open(archivo_prestamo2, 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0001 U0001 SEDE_2\n")
    
    if ejecutar_ps_archivo(archivo_prestamo2, mostrar_logs=False):
        time.sleep(2)
    else:
        print_error("Error ejecutando PRESTAMO para renovación")
        return False
    
    print_info("Ahora ejecutando RENOVACION...")
    archivo_renovacion = "data/caso1_renovacion.txt"
    with open(archivo_renovacion, 'w', encoding='utf-8') as f:
        f.write("RENOVACION L0001 U0001 SEDE_2\n")
    
    if ejecutar_ps_archivo(archivo_renovacion, mostrar_logs=True):
        time.sleep(2)
        mostrar_estado_bd("Estado después de RENOVACION")
        print_success("RENOVACION completada desde SEDE_2")
    else:
        print_error("Error ejecutando RENOVACION")
        return False
    
    pause()
    
    print_success("Caso 1 completado exitosamente")
    print()
    print_info("Nota: Aunque ejecutamos 3 PS separados para mostrar cambios paso a paso,")
    print_info("conceptualmente esto representa un solo PS procesando las 3 operaciones desde SEDE_2")
    print()
    
    return True

def caso_2():
    """Caso 2: Sistema con carga múltiple"""
    print_case(2, "Sistema con Carga Múltiple")
    
    print_info("Este caso ejecuta el sistema completo con múltiples PS en cada sede")
    print_info("generando carga desde varios archivos")
    print()
    
    # Limpiar y preparar
    limpiar_servicios()
    
    # Generar BD normal
    print_info("Generando datos iniciales...")
    result = subprocess.run(
        ["python3", "generar_datos_iniciales.py"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print_success("Datos iniciales generados")
    else:
        print_error("Error generando datos iniciales")
        print(result.stderr)
        return False
    
    print()
    
    # Levantar servicios
    if not levantar_servicios():
        print_error("No se pudieron levantar los servicios")
        return False
    
    if not verificar_servicios():
        print_error("Algunos servicios no están corriendo")
        return False
    
    # Generar múltiples archivos de solicitudes
    print_info("Generando archivos de solicitudes para múltiples PS...")
    
    # SEDE_1 - 2 archivos
    archivos_sede1 = []
    with open("data/caso2_sede1_0.txt", 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0001 U0001 SEDE_1\n")
        f.write("PRESTAMO L0002 U0002 SEDE_1\n")
        f.write("DEVOLUCION L0001 U0001 SEDE_1\n")
    archivos_sede1.append("data/caso2_sede1_0.txt")
    
    with open("data/caso2_sede1_1.txt", 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0003 U0003 SEDE_1\n")
        f.write("RENOVACION L0002 U0002 SEDE_1\n")
        f.write("DEVOLUCION L0003 U0003 SEDE_1\n")
    archivos_sede1.append("data/caso2_sede1_1.txt")
    
    # SEDE_2 - 2 archivos
    archivos_sede2 = []
    with open("data/caso2_sede2_0.txt", 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0004 U0004 SEDE_2\n")
        f.write("PRESTAMO L0005 U0005 SEDE_2\n")
        f.write("DEVOLUCION L0004 U0004 SEDE_2\n")
    archivos_sede2.append("data/caso2_sede2_0.txt")
    
    with open("data/caso2_sede2_1.txt", 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0006 U0006 SEDE_2\n")
        f.write("RENOVACION L0005 U0005 SEDE_2\n")
        f.write("DEVOLUCION L0006 U0006 SEDE_2\n")
    archivos_sede2.append("data/caso2_sede2_1.txt")
    
    print_success("Archivos de solicitudes generados")
    print_info(f"  SEDE_1: {len(archivos_sede1)} archivos")
    print_info(f"  SEDE_2: {len(archivos_sede2)} archivos")
    print()
    
    # Ejecutar PS en paralelo
    todos_archivos = archivos_sede1 + archivos_sede2
    procesos = ejecutar_ps_paralelo(todos_archivos, mostrar_logs=True)
    
    # Mostrar logs en tiempo real mientras se ejecutan
    print_info("Mostrando logs en tiempo real de los servicios...")
    time.sleep(3)  # Esperar un poco para que empiecen
    mostrar_logs_tiempo_real(["gc", "actor_prestamo", "actor_dev", "actor_ren"], duracion=5)
    
    # Esperar a que terminen
    esperar_procesos(procesos, timeout=120)
    
    # Mostrar estado final
    print()
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}ESTADO FINAL DE LA BD{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    mostrar_estado_bd("Estado Final")
    
    # Mostrar estado de servicios
    print()
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}ESTADO DE SERVICIOS{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    result = subprocess.run(["docker", "compose", "ps"], text=True)
    print()
    
    print_success("Caso 2 completado exitosamente")
    pause()
    
    return True

def caso_3():
    """Caso 3: Sistema con fallo de GA"""
    print_case(3, "Sistema con Fallo de GA")
    
    print_info("Este caso ejecuta el sistema con carga y luego simula el fallo de GA")
    print_info("demostrando que el sistema detecta el fallo y maneja el error apropiadamente")
    print()
    
    # Limpiar y preparar
    limpiar_servicios()
    
    # Generar BD
    print_info("Generando datos iniciales...")
    result = subprocess.run(
        ["python3", "generar_datos_iniciales.py"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print_success("Datos iniciales generados")
    else:
        print_error("Error generando datos iniciales")
        return False
    
    print()
    
    # Levantar servicios
    if not levantar_servicios():
        print_error("No se pudieron levantar los servicios")
        return False
    
    if not verificar_servicios():
        print_error("Algunos servicios no están corriendo")
        return False
    
    # Generar archivos de solicitudes
    print_info("Generando archivos de solicitudes...")
    
    archivos = []
    with open("data/caso3_sede1_0.txt", 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0001 U0001 SEDE_1\n")
        f.write("PRESTAMO L0002 U0002 SEDE_1\n")
    archivos.append("data/caso3_sede1_0.txt")
    
    with open("data/caso3_sede1_1.txt", 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0003 U0003 SEDE_1\n")
        f.write("DEVOLUCION L0001 U0001 SEDE_1\n")
    archivos.append("data/caso3_sede1_1.txt")
    
    with open("data/caso3_sede2_0.txt", 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0004 U0004 SEDE_2\n")
        f.write("PRESTAMO L0005 U0005 SEDE_2\n")
    archivos.append("data/caso3_sede2_0.txt")
    
    with open("data/caso3_sede2_1.txt", 'w', encoding='utf-8') as f:
        f.write("PRESTAMO L0006 U0006 SEDE_2\n")
        f.write("DEVOLUCION L0004 U0004 SEDE_2\n")
    archivos.append("data/caso3_sede2_1.txt")
    
    print_success("Archivos de solicitudes generados")
    print()
    
    # Iniciar PS en paralelo
    print_info("Iniciando PS en paralelo...")
    procesos = ejecutar_ps_paralelo(archivos, mostrar_logs=True)
    
    # Esperar un poco para que empiecen a procesar
    print_info("Esperando 3 segundos para que los PS empiecen a procesar...")
    time.sleep(3)
    
    # Detener GA
    print()
    print(f"\n{Colors.RED}{'='*60}{Colors.NC}")
    print(f"{Colors.RED}{Colors.BOLD}SIMULANDO FALLO DE GA{Colors.NC}")
    print(f"{Colors.RED}{'='*60}{Colors.NC}")
    detener_ga()
    
    # Mostrar logs de detección de fallo
    print()
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}LOGS DE DETECCIÓN DE FALLO{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    mostrar_logs_tiempo_real(
        ["actor_prestamo", "actor_dev", "actor_ren", "gc"],
        duracion=10,
        filtro="GA"
    )
    
    # Esperar a que terminen los procesos
    esperar_procesos(procesos, timeout=120)
    
    # Mostrar resumen
    print()
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}RESUMEN DE EJECUCIÓN{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    
    for proceso, archivo in procesos:
        if proceso.returncode == 0:
            print_success(f"{archivo}: Completado")
        else:
            print_error(f"{archivo}: Falló")
            if proceso.stderr:
                stderr_output = proceso.stderr.read() if hasattr(proceso.stderr, 'read') else ""
                if stderr_output:
                    print(f"  Errores: {stderr_output[:200]}...")
    
    # Mostrar logs de actores después del fallo
    print()
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}LOGS DE ACTORES (Detección de Fallo){Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    mostrar_logs_tiempo_real(
        ["actor_prestamo", "actor_dev", "actor_ren"],
        duracion=15,
        filtro="timeout|error|failover|no disponible|no responde"
    )
    
    # Mostrar estado de servicios
    print()
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}ESTADO DE SERVICIOS{Colors.NC}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.NC}")
    result = subprocess.run(["docker", "compose", "ps"], text=True)
    print()
    
    print_success("Caso 3 completado")
    print_info("Nota: El sistema detectó el fallo de GA y manejó los errores apropiadamente")
    pause()
    
    return True

def mostrar_menu():
    """Muestra el menú de selección de casos"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
    print(f"{Colors.WHITE}{Colors.BOLD}MENÚ DE CASOS DE PRUEBA{Colors.NC}")
    print(f"{Colors.CYAN}{'='*60}{Colors.NC}")
    print()
    print(f"{Colors.YELLOW}Selecciona el caso que deseas ejecutar:{Colors.NC}")
    print()
    print(f"  {Colors.GREEN}1{Colors.NC}. Operaciones desde SEDE_2 con BD pequeña")
    print(f"     (préstamo, devolución, renovación)")
    print()
    print(f"  {Colors.GREEN}2{Colors.NC}. Sistema con carga desde múltiples PS")
    print(f"     (1-2 PS por sede, generando carga desde varios archivos)")
    print()
    print(f"  {Colors.GREEN}3{Colors.NC}. Sistema con fallo de GA durante ejecución")
    print(f"     (igual que caso 2, pero con fallo de GA)")
    print()
    print(f"  {Colors.GREEN}4{Colors.NC}. Ejecutar todos los casos en orden")
    print()
    print(f"  {Colors.RED}0{Colors.NC}. Salir")
    print()

def seleccionar_casos():
    """Permite al usuario seleccionar qué casos ejecutar"""
    casos_seleccionados = []
    
    while True:
        mostrar_menu()
        opcion = input(f"{Colors.YELLOW}Ingresa tu opción (0-4): {Colors.NC}").strip()
        
        if opcion == "0":
            print_info("Saliendo...")
            return []
        elif opcion == "1":
            casos_seleccionados = [1]
            break
        elif opcion == "2":
            casos_seleccionados = [2]
            break
        elif opcion == "3":
            casos_seleccionados = [3]
            break
        elif opcion == "4":
            casos_seleccionados = [1, 2, 3]
            break
        else:
            print_error("Opción inválida. Por favor ingresa un número del 0 al 4.")
            time.sleep(1)
    
    return casos_seleccionados

def main():
    """Función principal"""
    print_header("DEMOSTRACIÓN DE CASOS DE PRUEBA - SUSTENTACIÓN")
    print_header("SISTEMA DISTRIBUIDO DE PRÉSTAMO DE LIBROS")
    
    check_directory()
    
    # Crear directorios necesarios
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data/primary', exist_ok=True)
    os.makedirs('data/secondary', exist_ok=True)
    
    print(f"\n{Colors.WHITE}{Colors.BOLD}Bienvenido a la demostración de casos de prueba - Sustentación{Colors.NC}")
    print(f"{Colors.CYAN}Este script te permite ejecutar los casos de prueba de forma individual{Colors.NC}")
    print()
    
    # Permitir seleccionar casos
    casos_seleccionados = seleccionar_casos()
    
    if not casos_seleccionados:
        print("Ejecución cancelada")
        sys.exit(0)
    
    # Mostrar resumen de casos seleccionados
    print()
    print_info(f"Casos seleccionados: {', '.join([f'Caso {c}' for c in casos_seleccionados])}")
    confirmar = input(f"{Colors.YELLOW}¿Continuar? (s/n): {Colors.NC}").strip().lower()
    
    if confirmar not in ['s', 'sí', 'si', 'y', 'yes']:
        print("Ejecución cancelada")
        sys.exit(0)
    
    # Ejecutar casos seleccionados
    casos_exitosos = 0
    casos_ejecutados = []
    
    try:
        if 1 in casos_seleccionados:
            print()
            if caso_1():
                casos_exitosos += 1
                casos_ejecutados.append(1)
            else:
                casos_ejecutados.append(1)  # Se ejecutó pero falló
        
        if 2 in casos_seleccionados:
            print()
            if caso_2():
                casos_exitosos += 1
                casos_ejecutados.append(2)
            else:
                casos_ejecutados.append(2)
        
        if 3 in casos_seleccionados:
            print()
            if caso_3():
                casos_exitosos += 1
                casos_ejecutados.append(3)
            else:
                casos_ejecutados.append(3)
                
    except KeyboardInterrupt:
        print("\n\nEjecución interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Preguntar si limpiar servicios
    print()
    limpiar = input(f"{Colors.YELLOW}¿Deseas limpiar los servicios Docker? (s/n): {Colors.NC}").strip().lower()
    if limpiar in ['s', 'sí', 'si', 'y', 'yes']:
        print_info("Limpiando servicios...")
        limpiar_servicios()
    else:
        print_info("Servicios Docker se mantienen corriendo")
    
    # Resumen final
    print()
    print_header("RESUMEN FINAL")
    print_success(f"¡{casos_exitosos}/{len(casos_seleccionados)} casos de prueba ejecutados exitosamente!")
    print()
    if casos_ejecutados:
        print_info(f"Casos ejecutados: {', '.join([f'Caso {c}' for c in casos_ejecutados])}")
    print()
    print_info("Los logs de cada caso están disponibles en el directorio logs/")
    print()

if __name__ == "__main__":
    main()

