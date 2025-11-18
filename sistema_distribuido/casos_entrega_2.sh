#!/bin/bash

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Función para mostrar header
show_header() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${WHITE}  CASOS DE PRUEBA - ENTREGA 2${NC}"
    echo -e "${WHITE}  SISTEMA DISTRIBUIDO DE LIBROS${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# Función para mostrar caso
show_case() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${WHITE}CASO $1: $2${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# Función para mostrar información
show_info() {
    echo -e "${BLUE}INFO: $1${NC}"
}

# Función para mostrar éxito
show_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Función para mostrar error
show_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Función para pausa
pause() {
    echo -e "${YELLOW}Presiona Enter para continuar...${NC}"
    read
}

# Función para limpiar pantalla
clear_screen() {
    clear
    show_header
}

# Función para verificar que estamos en el directorio correcto
check_directory() {
    if [ ! -f "docker-compose.yml" ]; then
        show_error "No se encontró docker-compose.yml. Asegúrate de estar en el directorio sistema_distribuido"
        exit 1
    fi
}

# Función para generar BD pequeña (10-20 libros)
generar_bd_pequena() {
    show_info "Generando base de datos pequeña con pocos registros..."
    
    python3 << 'PYTHON_EOF'
import json
import random
from datetime import datetime, timedelta

# Generar 15 libros con pocos ejemplares
libros = []
ejemplares_totales = []

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
import os
os.makedirs('data/primary', exist_ok=True)
os.makedirs('data/secondary', exist_ok=True)

# Guardar en archivo principal (para referencia)
with open('data/libros.json', 'w', encoding='utf-8') as f:
    json.dump(base_datos, f, ensure_ascii=False, indent=2)

# Guardar en réplica primaria (GA lee/escribe desde aquí)
with open('data/primary/libros.json', 'w', encoding='utf-8') as f:
    json.dump(base_datos, f, ensure_ascii=False, indent=2)

# Copiar a réplica secundaria
import shutil
shutil.copy2('data/primary/libros.json', 'data/secondary/libros.json')

print(f"Base de datos pequeña generada: {len(libros)} libros, {len(ejemplares_totales)} ejemplares")
print(f"Guardada en: data/libros.json, data/primary/libros.json, data/secondary/libros.json")
PYTHON_EOF

    if [ $? -eq 0 ]; then
        show_success "Base de datos pequeña generada correctamente"
        return 0
    else
        show_error "Error generando base de datos pequeña"
        return 1
    fi
}

# Función para mostrar estado de BD
mostrar_estado_bd() {
    local titulo="$1"
    
    if [ -n "$titulo" ]; then
        echo -e "${CYAN}--- $titulo ---${NC}"
    fi
    
    python3 << 'PYTHON_EOF'
import json
import sys
import os

# El GA escribe en data/primary/libros.json, así que leemos desde ahí
# Si no existe, intentamos data/libros.json como fallback
archivo_bd = 'data/primary/libros.json'
if not os.path.exists(archivo_bd):
    archivo_bd = 'data/libros.json'

# Debug: mostrar qué archivo estamos leyendo
print(f"Leyendo desde: {archivo_bd}", file=sys.stderr)

try:
    # Forzar lectura fresca del archivo
    with open(archivo_bd, 'r') as f:
        data = json.load(f)
    
    meta = data['metadata']
    print(f"Total libros: {meta['total_libros']}")
    print(f"Total ejemplares: {meta['total_ejemplares']}")
    print(f"Ejemplares disponibles: {meta['ejemplares_disponibles']}")
    print(f"Ejemplares prestados SEDE_1: {meta['ejemplares_prestados_sede_1']}")
    print(f"Ejemplares prestados SEDE_2: {meta['ejemplares_prestados_sede_2']}")
    print()
    print("Libros (primeros 10):")
    for libro in data['libros'][:10]:
        prestados = libro['ejemplares_prestados']
        disponibles = libro['ejemplares_disponibles']
        total = libro['total_ejemplares']
        print(f"  {libro['libro_id']}: {libro['titulo']} - Disponibles: {disponibles}/{total}, Prestados: {prestados}")
        
        # Mostrar ejemplares prestados
        for ejemplar in libro['ejemplares']:
            if ejemplar['estado'] == 'prestado':
                print(f"    → {ejemplar['ejemplar_id']} prestado a {ejemplar['usuario_prestamo']} en {ejemplar['sede']}")
except Exception as e:
    print(f"Error leyendo BD: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
    echo
}

# Función para limpiar servicios
limpiar_servicios() {
    show_info "Limpiando servicios anteriores..."
    docker compose down > /dev/null 2>&1
    show_success "Servicios limpiados"
}

# Función para levantar servicios
levantar_servicios() {
    show_info "Levantando servicios del sistema..."
    docker compose up --build -d ga gc actor_prestamo actor_devolucion actor_renovacion
    
    if [ $? -eq 0 ]; then
        show_success "Servicios levantados correctamente"
        show_info "Esperando que los servicios estén listos..."
        sleep 5
        return 0
    else
        show_error "Error levantando servicios"
        return 1
    fi
}

# Función para ejecutar PS con archivo específico
ejecutar_ps_archivo() {
    local archivo="$1"
    local nombre_log="$2"
    
    if [ ! -f "$archivo" ]; then
        show_error "Archivo no encontrado: $archivo"
        return 1
    fi
    
    show_info "Ejecutando PS con archivo: $archivo"
    
    # Verificar que el archivo existe antes de ejecutar
    if [ ! -f "$archivo" ]; then
        show_error "Archivo no encontrado: $archivo"
        return 1
    fi
    
    # Mostrar contenido del archivo para debug
    show_info "Contenido del archivo a procesar:"
    cat "$archivo" | sed 's/^/  /'
    echo
    
    # El volumen monta ./data:/app/data, así que data/archivo.txt -> /app/data/archivo.txt
    # Pero si el archivo ya tiene "data/" en el path, solo necesitamos /app/
    if [[ "$archivo" == data/* ]]; then
        archivo_en_contenedor="/app/$archivo"
    else
        archivo_en_contenedor="/app/data/$archivo"
    fi
    
    show_info "Ejecutando PS con archivo en contenedor: $archivo_en_contenedor"
    # Usar --no-deps y sobrescribir el comando completo para asegurar que se pase el argumento
    # El problema es que docker-compose tiene un command por defecto, así que debemos sobrescribirlo completamente
    docker compose run --rm --no-deps -e GC_HOST=gc -e GC_PORT=5001 --entrypoint python ps proceso_solicitante.py "$archivo_en_contenedor" > "$nombre_log" 2>&1
    local resultado=$?
    
    # Esperar un poco más para que el GA termine de procesar y escribir
    sleep 3
    
    if [ $resultado -eq 0 ]; then
        show_success "PS ejecutado correctamente"
    else
        show_error "PS terminó con errores (ver $nombre_log)"
    fi
    
    return $resultado
}

# Función para ejecutar múltiples PS en paralelo
ejecutar_ps_paralelo() {
    local archivos=("$@")
    local procesos=()
    local logs=()
    
    show_info "Ejecutando ${#archivos[@]} instancias de PS en paralelo..."
    
    for i in "${!archivos[@]}"; do
        archivo="${archivos[$i]}"
        log_file="logs/ps_${i}_$(basename $archivo).log"
        logs+=("$log_file")
        
        show_info "Iniciando PS $((i+1)): $archivo"
        docker compose run --rm -e GC_HOST=gc -e GC_PORT=5001 ps python proceso_solicitante.py "$archivo" > "$log_file" 2>&1 &
        procesos+=($!)
    done
    
    show_info "Esperando que terminen los procesos PS..."
    for pid in "${procesos[@]}"; do
        wait $pid
    done
    
    show_success "Todos los procesos PS han terminado"
    
    # Mostrar resumen de logs
    echo
    echo -e "${CYAN}Resumen de ejecución:${NC}"
    for log in "${logs[@]}"; do
        if [ -f "$log" ]; then
            exitosos=$(grep -c "procesada exitosamente\|exitoso" "$log" 2>/dev/null || echo "0")
            errores=$(grep -c "ERROR\|Error" "$log" 2>/dev/null || echo "0")
            echo "  $(basename $log): $exitosos exitosos, $errores errores"
        fi
    done
}

# Función para verificar que servicios están corriendo
verificar_servicios() {
    show_info "Verificando servicios..."
    
    local servicios_ok=0
    local servicios_total=5
    
    docker ps --format "{{.Names}}" | grep -q "^ga$" && servicios_ok=$((servicios_ok+1))
    docker ps --format "{{.Names}}" | grep -q "^gc$" && servicios_ok=$((servicios_ok+1))
    docker ps --format "{{.Names}}" | grep -q "^actor_prestamo$" && servicios_ok=$((servicios_ok+1))
    docker ps --format "{{.Names}}" | grep -q "^actor_dev$" && servicios_ok=$((servicios_ok+1))
    docker ps --format "{{.Names}}" | grep -q "^actor_ren$" && servicios_ok=$((servicios_ok+1))
    
    if [ $servicios_ok -eq $servicios_total ]; then
        show_success "Todos los servicios están corriendo ($servicios_ok/$servicios_total)"
        return 0
    else
        show_error "Algunos servicios no están corriendo ($servicios_ok/$servicios_total)"
        return 1
    fi
}

# Función para detener GA
detener_ga() {
    show_info "Deteniendo GA para simular fallo..."
    docker compose stop ga
    
    if [ $? -eq 0 ]; then
        show_success "GA detenido"
        sleep 2
        return 0
    else
        show_error "Error deteniendo GA"
        return 1
    fi
}

# Función para mostrar logs de detección de fallo
mostrar_logs_fallo() {
    show_info "Mostrando logs de detección de fallo (últimos 20 segundos)..."
    echo
    
    echo -e "${CYAN}--- Actor Préstamo ---${NC}"
    docker compose logs --since 20s actor_prestamo 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde" | tail -5 || echo "  (sin logs nuevos)"
    echo
    
    echo -e "${CYAN}--- Actor Devolución ---${NC}"
    docker compose logs --since 20s actor_devolucion 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde" | tail -5 || echo "  (sin logs nuevos)"
    echo
    
    echo -e "${CYAN}--- Actor Renovación ---${NC}"
    docker compose logs --since 20s actor_renovacion 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde" | tail -5 || echo "  (sin logs nuevos)"
    echo
}

# CASO 1: Operaciones desde SEDE_2 con BD pequeña
caso_1() {
    show_case "1" "Operaciones desde SEDE_2 - BD Pequeña (5 min)"
    
    show_info "Este caso demuestra las tres operaciones (préstamo, devolución, renovación) desde la sede 2"
    show_info "con una base de datos pequeña para apreciar fácilmente los cambios"
    echo
    
    # Limpiar y preparar entorno
    limpiar_servicios
    generar_bd_pequena
    
    # Mostrar estado inicial
    echo -e "${YELLOW}=== ESTADO INICIAL DE LA BD ===${NC}"
    mostrar_estado_bd "Estado Inicial"
    pause
    
    # Levantar servicios
    if ! levantar_servicios; then
        show_error "No se pudieron levantar los servicios"
        return 1
    fi
    
    # Crear archivo de solicitudes para SEDE_2 (todas las operaciones)
    archivo_caso1="data/caso1_sede2.txt"
    cat > "$archivo_caso1" << EOF
# Caso 1: Operaciones desde SEDE_2
PRESTAMO L0001 U0001 SEDE_2
DEVOLUCION L0001 U0001 SEDE_2
RENOVACION L0001 U0001 SEDE_2
EOF
    
    show_success "Archivo de solicitudes creado: $archivo_caso1"
    echo
    
    # Para mostrar cambios después de cada operación, ejecutamos una a la vez
    # pero todas desde SEDE_2 como un solo PS conceptual
    
    # Ejecutar PRESTAMO
    echo -e "${YELLOW}=== OPERACIÓN 1: PRESTAMO desde SEDE_2 ===${NC}"
    echo "PRESTAMO L0001 U0001 SEDE_2" > "data/caso1_prestamo.txt"
    if ejecutar_ps_archivo "data/caso1_prestamo.txt" "logs/caso1_prestamo.log"; then
        # Mostrar resumen del log - buscar solo la solicitud actual
        if [ -f "logs/caso1_prestamo.log" ]; then
            echo
            show_info "Resumen de ejecución:"
            # Buscar líneas con la solicitud actual (L0001 U0001 SEDE_2 para préstamo)
            grep -E "PRESTAMO.*L0001.*U0001.*SEDE_2|Solicitud.*L0001|L0001.*U0001|exitoso|Error|ERROR" "logs/caso1_prestamo.log" | head -10 | sed 's/^/  /'
            # Si no encuentra nada específico, mostrar las últimas líneas relevantes
            if [ $? -ne 0 ] || [ -z "$(grep -E "PRESTAMO.*L0001|Solicitud.*L0001" logs/caso1_prestamo.log)" ]; then
                echo "  Mostrando últimas líneas del log:"
                tail -10 "logs/caso1_prestamo.log" | grep -E "INFO|ERROR|Solicitud|Respuesta" | tail -5 | sed 's/^/  /'
            fi
            echo
        fi
        # Esperar adicional para que el GA termine de escribir
        show_info "Esperando que el GA termine de procesar y escribir cambios..."
        sleep 2
        mostrar_estado_bd "Estado después de PRESTAMO"
        echo -e "${GREEN}✓ PRESTAMO completado desde SEDE_2${NC}"
    else
        show_error "Error ejecutando PRESTAMO"
        if [ -f "logs/caso1_prestamo.log" ]; then
            show_info "Últimas líneas del log:"
            tail -10 "logs/caso1_prestamo.log" | sed 's/^/  /'
        fi
    fi
    pause
    
    # Ejecutar DEVOLUCION
    echo -e "${YELLOW}=== OPERACIÓN 2: DEVOLUCION desde SEDE_2 ===${NC}"
    echo "DEVOLUCION L0001 U0001 SEDE_2" > "data/caso1_devolucion.txt"
    if ejecutar_ps_archivo "data/caso1_devolucion.txt" "logs/caso1_devolucion.log"; then
        # Esperar adicional para que el GA termine de escribir
        show_info "Esperando que el GA termine de procesar y escribir cambios..."
        sleep 2
        mostrar_estado_bd "Estado después de DEVOLUCION"
        echo -e "${GREEN}✓ DEVOLUCION completada desde SEDE_2${NC}"
    else
        show_error "Error ejecutando DEVOLUCION"
    fi
    pause
    
    # Ejecutar RENOVACION (primero necesitamos prestar de nuevo)
    echo -e "${YELLOW}=== OPERACIÓN 3: RENOVACION desde SEDE_2 ===${NC}"
    show_info "Primero necesitamos prestar el libro nuevamente para poder renovarlo"
    echo "PRESTAMO L0001 U0001 SEDE_2" > "data/caso1_prestamo2.txt"
    if ejecutar_ps_archivo "data/caso1_prestamo2.txt" "logs/caso1_prestamo2.log"; then
        sleep 2
    else
        show_error "Error ejecutando PRESTAMO para renovación"
    fi
    
    echo -e "${YELLOW}Ahora ejecutando RENOVACION...${NC}"
    echo "RENOVACION L0001 U0001 SEDE_2" > "data/caso1_renovacion.txt"
    if ejecutar_ps_archivo "data/caso1_renovacion.txt" "logs/caso1_renovacion.log"; then
        # Esperar adicional para que el GA termine de escribir
        show_info "Esperando que el GA termine de procesar y escribir cambios..."
        sleep 2
        mostrar_estado_bd "Estado después de RENOVACION"
        echo -e "${GREEN}✓ RENOVACION completada desde SEDE_2${NC}"
    else
        show_error "Error ejecutando RENOVACION"
    fi
    pause
    
    show_success "Caso 1 completado"
    echo
}

# CASO 2: Sistema con carga desde múltiples PS
caso_2() {
    show_case "2" "Sistema con Carga Múltiple (3 min)"
    
    show_info "Este caso ejecuta el sistema completo con múltiples PS en cada sede"
    show_info "generando carga desde varios archivos"
    echo
    
    # Limpiar y preparar
    limpiar_servicios
    
    # Generar BD normal o pequeña
    show_info "Generando datos iniciales..."
    python3 generar_datos_iniciales.py > /dev/null 2>&1
    show_success "Datos iniciales generados"
    echo
    
    # Levantar servicios
    if ! levantar_servicios; then
        show_error "No se pudieron levantar los servicios"
        return 1
    fi
    
    # Generar múltiples archivos de solicitudes
    show_info "Generando archivos de solicitudes para múltiples PS..."
    
    # SEDE_1 - 2 archivos
    cat > "data/caso2_sede1_0.txt" << EOF
PRESTAMO L0001 U0001 SEDE_1
PRESTAMO L0002 U0002 SEDE_1
DEVOLUCION L0001 U0001 SEDE_1
EOF
    
    cat > "data/caso2_sede1_1.txt" << EOF
PRESTAMO L0003 U0003 SEDE_1
RENOVACION L0002 U0002 SEDE_1
DEVOLUCION L0003 U0003 SEDE_1
EOF
    
    # SEDE_2 - 2 archivos
    cat > "data/caso2_sede2_0.txt" << EOF
PRESTAMO L0004 U0004 SEDE_2
PRESTAMO L0005 U0005 SEDE_2
DEVOLUCION L0004 U0004 SEDE_2
EOF
    
    cat > "data/caso2_sede2_1.txt" << EOF
PRESTAMO L0006 U0006 SEDE_2
RENOVACION L0005 U0005 SEDE_2
DEVOLUCION L0006 U0006 SEDE_2
EOF
    
    show_success "Archivos de solicitudes generados"
    echo
    
    # Ejecutar PS en paralelo
    archivos_ps=(
        "data/caso2_sede1_0.txt"
        "data/caso2_sede1_1.txt"
        "data/caso2_sede2_0.txt"
        "data/caso2_sede2_1.txt"
    )
    
    ejecutar_ps_paralelo "${archivos_ps[@]}"
    
    # Mostrar estado final
    echo
    echo -e "${YELLOW}=== ESTADO FINAL DE LA BD ===${NC}"
    mostrar_estado_bd "Estado Final"
    
    # Mostrar estado de servicios
    echo
    echo -e "${YELLOW}=== ESTADO DE SERVICIOS ===${NC}"
    docker compose ps
    echo
    
    show_success "Caso 2 completado"
    pause
}

# CASO 3: Sistema con fallo de GA
caso_3() {
    show_case "3" "Sistema con Fallo de GA (5 min)"
    
    show_info "Este caso ejecuta el sistema con carga y luego simula el fallo de GA"
    show_info "demostrando que el sistema detecta el fallo y maneja el error apropiadamente"
    echo
    
    # Limpiar y preparar
    limpiar_servicios
    
    # Generar BD
    show_info "Generando datos iniciales..."
    python3 generar_datos_iniciales.py > /dev/null 2>&1
    show_success "Datos iniciales generados"
    echo
    
    # Levantar servicios
    if ! levantar_servicios; then
        show_error "No se pudieron levantar los servicios"
        return 1
    fi
    
    # Verificar servicios
    verificar_servicios
    echo
    
    # Generar archivos de solicitudes
    show_info "Generando archivos de solicitudes..."
    
    cat > "data/caso3_sede1_0.txt" << EOF
PRESTAMO L0001 U0001 SEDE_1
PRESTAMO L0002 U0002 SEDE_1
EOF
    
    cat > "data/caso3_sede1_1.txt" << EOF
PRESTAMO L0003 U0003 SEDE_1
DEVOLUCION L0001 U0001 SEDE_1
EOF
    
    cat > "data/caso3_sede2_0.txt" << EOF
PRESTAMO L0004 U0004 SEDE_2
PRESTAMO L0005 U0005 SEDE_2
EOF
    
    cat > "data/caso3_sede2_1.txt" << EOF
PRESTAMO L0006 U0006 SEDE_2
DEVOLUCION L0004 U0004 SEDE_2
EOF
    
    show_success "Archivos de solicitudes generados"
    echo
    
    # Iniciar PS en background
    show_info "Iniciando PS en paralelo..."
    archivos_ps=(
        "data/caso3_sede1_0.txt"
        "data/caso3_sede1_1.txt"
        "data/caso3_sede2_0.txt"
        "data/caso3_sede2_1.txt"
    )
    
    procesos=()
    logs=()
    
    for i in "${!archivos_ps[@]}"; do
        archivo="${archivos_ps[$i]}"
        log_file="logs/caso3_ps_${i}.log"
        logs+=("$log_file")
        
        docker compose run --rm -e GC_HOST=gc -e GC_PORT=5001 ps python proceso_solicitante.py "$archivo" > "$log_file" 2>&1 &
        procesos+=($!)
        show_info "PS $((i+1)) iniciado (PID: $!)"
    done
    
    # Esperar un poco para que empiecen a procesar
    show_info "Esperando 3 segundos para que los PS empiecen a procesar..."
    sleep 3
    
    # Detener GA
    echo
    show_info "SIMULANDO FALLO DE GA..."
    detener_ga
    
    # Mostrar logs de detección
    echo
    mostrar_logs_fallo
    
    # Esperar a que terminen los procesos
    show_info "Esperando que terminen los procesos PS..."
    for pid in "${procesos[@]}"; do
        wait $pid 2>/dev/null
    done
    
    show_success "Procesos PS terminados"
    echo
    
    # Mostrar resumen
    echo -e "${YELLOW}=== RESUMEN DE EJECUCIÓN ===${NC}"
    for log in "${logs[@]}"; do
        if [ -f "$log" ]; then
            echo -e "${CYAN}Log: $(basename $log)${NC}"
            exitosos=$(grep -c "procesada exitosamente\|exitoso" "$log" 2>/dev/null || echo "0")
            errores=$(grep -c "ERROR\|Error\|timeout\|no disponible" "$log" 2>/dev/null || echo "0")
            echo "  Exitosos: $exitosos, Errores: $errores"
            if [ $errores -gt 0 ]; then
                echo "  Últimos errores:"
                grep -iE "ERROR|Error|timeout|no disponible" "$log" | tail -3 | sed 's/^/    /'
            fi
            echo
        fi
    done
    
    # Mostrar logs de actores después del fallo
    echo
    echo -e "${YELLOW}=== LOGS DE ACTORES (Detección de Fallo) ===${NC}"
    mostrar_logs_fallo
    
    # Mostrar estado de servicios
    echo
    echo -e "${YELLOW}=== ESTADO DE SERVICIOS ===${NC}"
    docker compose ps
    echo
    
    show_success "Caso 3 completado"
    show_info "Nota: El sistema detectó el fallo de GA y manejó los errores apropiadamente"
    pause
}

# Función principal
main() {
    clear_screen
    
    check_directory
    
    # Crear directorios necesarios
    mkdir -p logs
    mkdir -p data/primary
    mkdir -p data/secondary
    
    echo -e "${WHITE}Bienvenido a la demostración de casos de prueba - Entrega 2${NC}"
    echo -e "${CYAN}Este script ejecutará los 3 casos de prueba requeridos para la sustentación${NC}"
    echo
    echo -e "${YELLOW}Casos a ejecutar:${NC}"
    echo "  1. Operaciones desde SEDE_2 con BD pequeña (5 min)"
    echo "  2. Sistema con carga desde múltiples PS (3 min)"
    echo "  3. Sistema con fallo de GA (5 min)"
    echo
    echo -e "${YELLOW}¿Deseas ejecutar todos los casos? (s/n)${NC}"
    read -r respuesta
    
    if [[ "$respuesta" != "s" && "$respuesta" != "S" ]]; then
        echo "Ejecución cancelada"
        exit 0
    fi
    
    # Ejecutar casos
    caso_1
    caso_2
    caso_3
    
    # Limpiar
    echo
    show_info "Limpiando servicios..."
    limpiar_servicios
    
    echo
    show_success "¡Todos los casos de prueba han sido ejecutados exitosamente!"
    echo
    show_info "Los logs de cada caso están disponibles en el directorio logs/"
    echo
}

# Ejecutar función principal
main

