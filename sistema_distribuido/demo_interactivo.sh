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
    echo -e "${WHITE}  SISTEMA DISTRIBUIDO DE LIBROS${NC}"
    echo -e "${WHITE}         ETAPA 2${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# Función para mostrar paso
show_step() {
    echo -e "${YELLOW}PASO $1: $2${NC}"
    echo
}

# Función para mostrar información
show_info() {
    echo -e "${BLUE}INFO: $1${NC}"
}

# Función para mostrar éxito
show_success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

# Función para mostrar error
show_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

# Función para mostrar comunicación
show_communication() {
    echo -e "${PURPLE}COMUNICACIÓN: $1${NC}"
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

# Función para obtener IPs de contenedores
get_container_ips() {
    echo -e "${CYAN}Obteniendo IPs de los contenedores...${NC}"
    echo
    
    # Obtener IPs de todos los contenedores
    GA_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ga 2>/dev/null)
    GC_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gc 2>/dev/null)
    PS_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ps 2>/dev/null)
    ACTOR_PRESTAMO_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' actor_prestamo 2>/dev/null)
    ACTOR_DEV_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' actor_dev 2>/dev/null)
    ACTOR_REN_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' actor_ren 2>/dev/null)
    
    echo -e "${WHITE}IPs de los contenedores (6 servicios):${NC}"
    echo -e "   ${GREEN}Gestor de Almacenamiento (GA):${NC} $GA_IP (puerto 5003)"
    echo -e "   ${GREEN}Gestor de Carga (GC):${NC} $GC_IP (puertos 5001, 5002)"
    echo -e "   ${GREEN}Actor Préstamo:${NC} $ACTOR_PRESTAMO_IP (puerto 5004)"
    echo -e "   ${GREEN}Actor Devolución:${NC} $ACTOR_DEV_IP"
    echo -e "   ${GREEN}Actor Renovación:${NC} $ACTOR_REN_IP"
    echo -e "   ${GREEN}Proceso Solicitante (PS):${NC} $PS_IP"
    echo
}

# Función para verificar datos iniciales
check_initial_data() {
    show_info "Verificando datos iniciales..."
    
    if [ ! -f "data/libros.json" ]; then
        show_error "No se encontró data/libros.json"
        show_info "Generando datos iniciales..."
        python generar_datos_iniciales.py
        if [ $? -eq 0 ]; then
            show_success "Datos iniciales generados"
        else
            show_error "Error generando datos iniciales"
            return 1
        fi
    fi
    
    if [ ! -f "data/primary/libros.json" ] || [ ! -f "data/secondary/libros.json" ]; then
        show_info "Réplicas no encontradas, inicializando..."
        python generar_datos_iniciales.py
        if [ $? -eq 0 ]; then
            show_success "Réplicas inicializadas"
        else
            show_error "Error inicializando réplicas"
            return 1
        fi
    fi
    
    return 0
}

# Función para mostrar estado inicial
show_initial_state() {
    show_step "1" "Verificando estado inicial del sistema"
    
    # Verificar datos iniciales
    if ! check_initial_data; then
        pause
        return
    fi
    
    echo -e "${WHITE}Estado inicial de la base de datos:${NC}"
    echo -e "${CYAN}Metadata del sistema:${NC}"
    python -c "
import json
with open('data/libros.json', 'r') as f:
    data = json.load(f)
    meta = data['metadata']
    print(f'  Total libros: {meta[\"total_libros\"]}')
    print(f'  Total ejemplares: {meta[\"total_ejemplares\"]}')
    print(f'  Ejemplares disponibles: {meta[\"ejemplares_disponibles\"]}')
    print(f'  Ejemplares prestados SEDE_1: {meta[\"ejemplares_prestados_sede_1\"]}')
    print(f'  Ejemplares prestados SEDE_2: {meta[\"ejemplares_prestados_sede_2\"]}')
"
    echo
    
    echo -e "${WHITE}Verificando réplicas:${NC}"
    if [ -f "data/primary/libros.json" ] && [ -f "data/secondary/libros.json" ]; then
        if diff -q data/primary/libros.json data/secondary/libros.json > /dev/null 2>&1; then
            show_success "Réplicas primaria y secundaria están sincronizadas"
        else
            show_error "Réplicas no están sincronizadas"
        fi
    else
        show_error "Réplicas no encontradas"
    fi
    echo
    
    echo -e "${WHITE}Solicitudes a procesar:${NC}"
    if [ -f "data/solicitudes.txt" ]; then
        cat data/solicitudes.txt
        echo
        PRESTAMOS=$(grep -v '^#' data/solicitudes.txt | grep -i 'PRESTAMO' | wc -l)
        RENOVACIONES=$(grep -v '^#' data/solicitudes.txt | grep -i 'RENOVACION' | wc -l)
        DEVOLUCIONES=$(grep -v '^#' data/solicitudes.txt | grep -i 'DEVOLUCION' | wc -l)
        echo -e "${CYAN}Resumen:${NC} $PRESTAMOS préstamos, $RENOVACIONES renovaciones, $DEVOLUCIONES devoluciones"
    else
        show_error "No se encontró data/solicitudes.txt"
    fi
    echo
    
    pause
}

# Función para preparar entorno
prepare_environment() {
    show_step "2" "Preparando entorno"
    
    show_info "Verificando Docker..."
    if ! docker --version > /dev/null 2>&1; then
        show_error "Docker no está instalado o no está funcionando"
        exit 1
    fi
    show_success "Docker funcionando correctamente"
    
    show_info "Verificando Docker Compose..."
    if ! docker compose --version > /dev/null 2>&1; then
        show_error "Docker Compose no está disponible"
        exit 1
    fi
    show_success "Docker Compose funcionando correctamente"
    
    show_info "Limpiando contenedores anteriores..."
    docker compose down > /dev/null 2>&1
    show_success "Entorno limpio"
    
    pause
}

# Función para iniciar servicios
start_services() {
    show_step "3" "Iniciando servicios distribuidos (Etapa 2)"
    
    # Verificar datos iniciales
    if ! check_initial_data; then
        pause
        return
    fi
    
    show_info "Construyendo y levantando todos los servicios..."
    show_info "Iniciando: GA, GC, Actor Préstamo, Actor Devolución, Actor Renovación"
    docker compose up --build -d ga gc actor_prestamo actor_devolucion actor_renovacion
    
    if [ $? -eq 0 ]; then
        show_success "Todos los servicios iniciados correctamente"
    else
        show_error "Error al iniciar los servicios"
        exit 1
    fi
    
    echo
    show_info "Esperando que los servicios estén listos..."
    sleep 5
    
    # Mostrar estado de contenedores
    echo -e "${WHITE}Estado de los contenedores:${NC}"
    docker compose ps
    echo
    
    # Obtener y mostrar IPs
    get_container_ips
    
    # Mostrar logs de inicialización
    echo -e "${WHITE}Logs de inicialización:${NC}"
    echo -e "${CYAN}--- Gestor de Almacenamiento (GA) ---${NC}"
    docker compose logs ga | tail -5
    echo
    echo -e "${CYAN}--- Gestor de Carga (GC) ---${NC}"
    docker compose logs gc | tail -5
    echo
    echo -e "${CYAN}--- Actor Préstamo ---${NC}"
    docker compose logs actor_prestamo | tail -5
    echo
    echo -e "${CYAN}--- Actores (Devolución y Renovación) ---${NC}"
    docker compose logs actor_devolucion actor_renovacion | tail -5
    echo
    
    pause
}

# Función para ejecutar solicitudes
run_requests() {
    show_step "4" "Ejecutando solicitudes del sistema"
    
    show_info "Iniciando Proceso Solicitante..."
    echo -e "${WHITE}Enviando solicitudes al sistema (PRESTAMO, RENOVACION, DEVOLUCION)...${NC}"
    echo
    
    # Ejecutar PS y capturar output con análisis mejorado
    docker compose run --rm ps 2>&1 | while IFS= read -r line; do
        if [[ $line == *"Solicitud #"* ]] || [[ $line == *"enviada:"* ]]; then
            if [[ $line == *"PRESTAMO"* ]]; then
                show_communication "PS -> GC: Solicitud de PRESTAMO"
            else
                show_communication "PS -> GC: $line"
            fi
        elif [[ $line == *"Respuesta recibida"* ]]; then
            show_communication "GC -> PS: Respuesta recibida"
        elif [[ $line == *"Reenviando préstamo"* ]]; then
            show_communication "GC -> Actor Préstamo: Reenvío de préstamo"
        elif [[ $line == *"Evento recibido"* ]]; then
            show_communication "GC -> Actor: Evento publicado"
        elif [[ $line == *"Tiempo de respuesta"* ]]; then
            show_success "$line"
        elif [[ $line == *"procesada exitosamente"* ]] || [[ $line == *"exitoso"* ]]; then
            show_success "$line"
        elif [[ $line == *"ERROR"* ]] || [[ $line == *"Error"* ]]; then
            show_error "$line"
        else
            echo "$line"
        fi
    done
    
    echo
    show_info "Métricas guardadas en logs/metricas.csv"
    pause
}

# Función para mostrar logs detallados
show_detailed_logs() {
    show_step "5" "Mostrando comunicación detallada entre contenedores"
    
    echo -e "${WHITE}Análisis de comunicación entre contenedores (Etapa 2):${NC}"
    echo
    
    # Mostrar logs del GA
    echo -e "${CYAN}--- Gestor de Almacenamiento (GA) ---${NC}"
    docker compose logs ga | grep -E "(Operación|Préstamo|Devolución|Renovación|réplica)" | tail -10 | while IFS= read -r line; do
        if [[ $line == *"Préstamo realizado"* ]]; then
            show_success "GA: $line"
        elif [[ $line == *"réplica"* ]]; then
            show_info "GA: $line"
        else
            echo "$line"
        fi
    done
    echo
    
    # Mostrar logs del GC con análisis
    echo -e "${CYAN}--- Gestor de Carga (Coordinador) ---${NC}"
    docker compose logs gc | grep -E "(Solicitud recibida|Reenviando préstamo|Evento enviado|Respuesta enviada|Health check)" | tail -10 | while IFS= read -r line; do
        if [[ $line == *"Solicitud recibida"* ]]; then
            show_communication "PS -> GC: Solicitud recibida"
        elif [[ $line == *"Reenviando préstamo"* ]]; then
            show_communication "GC -> Actor Préstamo: Reenvío"
        elif [[ $line == *"Evento enviado"* ]]; then
            show_communication "GC -> Actores: Evento publicado (PUB/SUB)"
        elif [[ $line == *"Respuesta enviada"* ]]; then
            show_communication "GC -> PS: Respuesta enviada"
        fi
    done
    echo
    
    # Mostrar logs de Actor Préstamo
    echo -e "${CYAN}--- Actor Préstamo (REQ/REP) ---${NC}"
    docker compose logs actor_prestamo | grep -E "(Solicitud recibida|Préstamo|exitoso|Error)" | tail -10 | while IFS= read -r line; do
        if [[ $line == *"exitoso"* ]]; then
            show_success "Actor Préstamo: $line"
        elif [[ $line == *"Error"* ]]; then
            show_error "Actor Préstamo: $line"
        else
            echo "$line"
        fi
    done
    echo
    
    # Mostrar logs de actores
    echo -e "${CYAN}--- Actor de Renovación (PUB/SUB) ---${NC}"
    docker compose logs actor_renovacion | grep -E "(Evento recibido|procesada exitosamente|GA)" | tail -5 | while IFS= read -r line; do
        if [[ $line == *"Evento recibido"* ]]; then
            show_communication "GC -> Actor Ren: Evento de renovacion"
        elif [[ $line == *"procesada exitosamente"* ]]; then
            show_success "Actor Ren: $line"
        fi
    done
    echo
    
    echo -e "${CYAN}--- Actor de Devolución (PUB/SUB) ---${NC}"
    docker compose logs actor_devolucion | grep -E "(Evento recibido|procesada exitosamente|GA)" | tail -5 | while IFS= read -r line; do
        if [[ $line == *"Evento recibido"* ]]; then
            show_communication "GC -> Actor Dev: Evento de devolucion"
        elif [[ $line == *"procesada exitosamente"* ]]; then
            show_success "Actor Dev: $line"
        fi
    done
    echo
    
    pause
}

# Función para mostrar resultados
show_results() {
    show_step "6" "Verificando resultados del procesamiento"
    
    echo -e "${WHITE}Estado final de la base de datos:${NC}"
    
    # Mostrar solo los primeros 10 libros para no saturar la pantalla
    echo -e "${CYAN}Mostrando primeros 10 libros del catálogo:${NC}"
    cat data/libros.json | python -c "
import json
import sys
data = json.load(sys.stdin)
print('Metadata del sistema:')
print(f'  Total libros: {data[\"metadata\"][\"total_libros\"]}')
print(f'  Total ejemplares: {data[\"metadata\"][\"total_ejemplares\"]}')
print(f'  Ejemplares disponibles: {data[\"metadata\"][\"ejemplares_disponibles\"]}')
print(f'  Ejemplares prestados sede 1: {data[\"metadata\"][\"ejemplares_prestados_sede_1\"]}')
print(f'  Ejemplares prestados sede 2: {data[\"metadata\"][\"ejemplares_prestados_sede_2\"]}')
print()
print('Primeros 10 libros:')
for i, libro in enumerate(data['libros'][:10]):
    print(f'  {libro[\"libro_id\"]}: {libro[\"titulo\"]} - Disponibles: {libro[\"ejemplares_disponibles\"]}/{libro[\"total_ejemplares\"]}')
"
    echo
    
    # Verificar réplicas
    echo -e "${WHITE}Estado de réplicas:${NC}"
    if [ -f "data/primary/libros.json" ] && [ -f "data/secondary/libros.json" ]; then
        if diff -q data/primary/libros.json data/secondary/libros.json > /dev/null 2>&1; then
            show_success "Réplicas primaria y secundaria están sincronizadas"
        else
            show_error "Réplicas no están sincronizadas"
            show_info "Diferencias encontradas entre réplicas"
        fi
    else
        show_error "Réplicas no encontradas"
    fi
    echo
    
    # Generar información dinámica basada en datos reales
    echo -e "${WHITE}Análisis de solicitudes del sistema:${NC}"
    
    # Contar solicitudes reales del archivo
    if [ -f "data/solicitudes.txt" ]; then
        SOLICITUDES_TOTAL=$(grep -v '^#' data/solicitudes.txt | grep -v '^$' | wc -l)
        PRESTAMOS=$(grep -v '^#' data/solicitudes.txt | grep -i 'PRESTAMO' | wc -l)
        RENOVACIONES=$(grep -v '^#' data/solicitudes.txt | grep -i 'RENOVACION' | wc -l)
        DEVOLUCIONES=$(grep -v '^#' data/solicitudes.txt | grep -i 'DEVOLUCION' | wc -l)
        SEDE_1=$(grep -v '^#' data/solicitudes.txt | grep 'SEDE_1' | wc -l)
        SEDE_2=$(grep -v '^#' data/solicitudes.txt | grep 'SEDE_2' | wc -l)
        
        echo -e "   ${CYAN}Total de solicitudes en archivo:${NC} $SOLICITUDES_TOTAL"
        echo -e "   ${GREEN}Préstamos:${NC} $PRESTAMOS"
        echo -e "   ${YELLOW}Renovaciones:${NC} $RENOVACIONES"
        echo -e "   ${YELLOW}Devoluciones:${NC} $DEVOLUCIONES"
        echo -e "   ${BLUE}Sede 1:${NC} $SEDE_1 solicitudes"
        echo -e "   ${BLUE}Sede 2:${NC} $SEDE_2 solicitudes"
    fi
    echo
    
    # Verificar estado de pruebas si existen
    if [ -f "logs/resumen_pruebas.txt" ]; then
        echo -e "${WHITE}Estado de pruebas del sistema:${NC}"
        TESTS_PASADOS=$(grep "Tests pasados:" logs/resumen_pruebas.txt | cut -d' ' -f3)
        echo -e "   ${GREEN}Tests ejecutados:${NC} $TESTS_PASADOS"
        
        if grep -q "TODOS LOS TESTS PASARON" logs/resumen_pruebas.txt; then
            echo -e "   ${GREEN}Estado general:${NC} Sistema completamente operativo"
        else
            echo -e "   ${YELLOW}Estado general:${NC} Sistema en pruebas"
        fi
        echo
    fi
    
    # Mostrar información de contenedores si están corriendo
    if docker compose ps --format json 2>/dev/null | grep -q "running"; then
        echo -e "${WHITE}Estado de contenedores:${NC}"
        CONTAINERS_RUNNING=$(docker compose ps --format json 2>/dev/null | grep '"State":"running"' | wc -l)
        echo -e "   ${GREEN}Contenedores activos:${NC} $CONTAINERS_RUNNING"
        echo -e "   ${GREEN}Comunicación distribuida:${NC} Funcionando"
    else
        echo -e "${WHITE}Estado de contenedores:${NC}"
        echo -e "   ${YELLOW}Contenedores:${NC} No están ejecutándose"
        echo -e "   ${YELLOW}Comunicación distribuida:${NC} No disponible"
    fi
    echo
    
    pause
}

# Función para mostrar métricas
show_metrics() {
    show_step "7" "Mostrando métricas de rendimiento"
    
    if [ ! -f "logs/metricas.csv" ]; then
        show_error "No se encontró archivo de métricas. Ejecuta solicitudes primero."
        pause
        return
    fi
    
    echo -e "${WHITE}Métricas de Préstamos:${NC}"
    echo
    
    python3 -c "
import csv
import statistics
import os

if not os.path.exists('logs/metricas.csv'):
    print('No hay métricas disponibles')
    exit(0)

with open('logs/metricas.csv', 'r') as f:
    reader = csv.DictReader(f)
    prestamos = [row for row in reader if row.get('operacion') == 'PRESTAMO']
    
    if not prestamos:
        print('No hay préstamos registrados')
        exit(0)
    
    tiempos = [float(row['tiempo_respuesta_ms']) for row in prestamos]
    exitosos = [row for row in prestamos if row.get('exito') == 'SI']
    
    print(f'Total de préstamos procesados: {len(prestamos)}')
    print(f'Préstamos exitosos: {len(exitosos)}')
    print(f'Préstamos fallidos: {len(prestamos) - len(exitosos)}')
    print()
    print('Tiempos de respuesta:')
    print(f'  Promedio: {statistics.mean(tiempos):.2f} ms')
    if len(tiempos) > 1:
        print(f'  Desviación estándar: {statistics.stdev(tiempos):.2f} ms')
        print(f'  Mínimo: {min(tiempos):.2f} ms')
        print(f'  Máximo: {max(tiempos):.2f} ms')
    
    # Últimos 2 minutos
    if prestamos:
        ultimo = prestamos[-1]
        print()
        print('Última ventana de 2 minutos:')
        print(f'  Préstamos en ventana: {ultimo.get(\"total_prestamos_2min\", \"N/A\")}')
        print(f'  Tiempo promedio: {ultimo.get(\"tiempo_promedio_ms\", \"N/A\")} ms')
        print(f'  Desviación estándar: {ultimo.get(\"desviacion_estandar_ms\", \"N/A\")} ms')
" 2>/dev/null || show_error "Error leyendo métricas"
    
    echo
    pause
}

# Función para probar failover
test_failover() {
    show_step "8" "Prueba de Failover"
    
    echo -e "${WHITE}Esta prueba simula el fallo de GA y verifica la detección automática${NC}"
    echo
    
    # Verificar que GA está corriendo usando método robusto
    # Usar docker ps directamente que es más confiable que docker compose ps
    GA_CONTAINER=$(docker ps --filter "name=^ga$" --format "{{.Names}}" 2>/dev/null)
    if [ -z "$GA_CONTAINER" ] || [ "$GA_CONTAINER" != "ga" ]; then
        show_error "GA no está corriendo. Inicia los servicios primero (opción 3)."
        pause
        return
    fi
    
    show_info "Estado actual de GA:"
    docker compose ps ga
    echo
    
    show_info "Mostrando estado de conexión de actores..."
    echo -e "${CYAN}--- Logs recientes de actores (últimos 30 segundos) ---${NC}"
    echo -e "${CYAN}--- Actor Préstamo ---${NC}"
    docker compose logs --since 30s actor_prestamo 2>/dev/null | grep -iE "GA|conectado|health" | tail -3 || echo "  (sin logs recientes)"
    echo
    echo -e "${CYAN}--- Actor Devolución ---${NC}"
    docker compose logs --since 30s actor_devolucion 2>/dev/null | grep -iE "GA|conectado|health" | tail -3 || echo "  (sin logs recientes)"
    echo
    echo -e "${CYAN}--- Actor Renovación ---${NC}"
    docker compose logs --since 30s actor_renovacion 2>/dev/null | grep -iE "GA|conectado|health" | tail -3 || echo "  (sin logs recientes)"
    echo
    
    echo -e "${YELLOW}¿Deseas simular el fallo de GA? (s/n)${NC}"
    read -r respuesta
    
    if [[ "$respuesta" == "s" ]] || [[ "$respuesta" == "S" ]]; then
        # Capturar timestamp antes de detener GA
        TIMESTAMP_ANTES=$(date +%s)
        
        show_info "Deteniendo GA..."
        docker compose stop ga
        show_success "GA detenido"
        echo
        
        show_info "Esperando 2 segundos..."
        sleep 2
        
        # Mostrar logs recientes (solo los nuevos después del fallo)
        show_info "Logs recientes de actores (últimos 15 segundos):"
        echo -e "${CYAN}--- Actor Préstamo ---${NC}"
        docker compose logs --since 15s actor_prestamo 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde" | tail -5 || echo "  (sin logs nuevos)"
        echo
        echo -e "${CYAN}--- Actor Devolución ---${NC}"
        docker compose logs --since 15s actor_devolucion 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde" | tail -5 || echo "  (sin logs nuevos)"
        echo
        echo -e "${CYAN}--- Actor Renovación ---${NC}"
        docker compose logs --since 15s actor_renovacion 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde" | tail -5 || echo "  (sin logs nuevos)"
        echo
        
        show_info "Nota: Los actores solo detectan el fallo cuando intentan una operación."
        echo
        echo -e "${YELLOW}¿Deseas enviar una solicitud de prueba para ver el fallo en acción? (s/n)${NC}"
        read -r respuesta_test
        
        if [[ "$respuesta_test" == "s" ]] || [[ "$respuesta_test" == "S" ]]; then
            show_info "Enviando solicitud de prueba mientras GA está detenido..."
            echo -e "${CYAN}Ejecutando solicitud de préstamo de prueba...${NC}"
            echo
            
            # Verificar que GA esté detenido antes de continuar
            if docker ps --filter "name=^ga$" --format "{{.Names}}" 2>/dev/null | grep -q "^ga$"; then
                show_error "GA se levantó automáticamente. Deteniéndolo nuevamente..."
                docker compose stop ga
                sleep 2
            fi
            
            # Crear una solicitud de prueba temporal SOLO con PRESTAMO (requiere GA)
            TEST_FILE="data/test_failover.txt"
            echo "PRESTAMO L001 U001 SEDE_1" > "$TEST_FILE"
            show_info "Archivo de prueba creado con solicitud de PRESTAMO (requiere GA)"
            echo
            
            # Construir la imagen de gc si no existe (tiene la misma estructura que ps)
            IMAGE_NAME="sistema_distribuido-gc"
            if ! docker images | grep -q "$IMAGE_NAME"; then
                show_info "Construyendo imagen necesaria..."
                docker compose build gc > /dev/null 2>&1
            fi
            
            # Crear script temporal para ejecutar PS con el archivo correcto
            TEMP_SCRIPT="/tmp/run_ps_test.py"
            cat > "$TEMP_SCRIPT" << 'EOF'
import sys
sys.path.insert(0, '/app')
from proceso_solicitante import ProcesoSolicitante
ps = ProcesoSolicitante()
ps.iniciar('/app/data/test_failover.txt')
EOF
            
            # Ejecutar PS usando docker run directamente para evitar que compose levante dependencias
            show_info "Ejecutando PS sin levantar dependencias..."
            show_info "Nota: Esta solicitud de PRESTAMO requiere GA, debería fallar..."
            echo
            CURRENT_DIR=$(pwd)
            docker run --rm \
                --network red_distribuida \
                -e GC_HOST=gc \
                -e GC_PORT=5001 \
                -v "$CURRENT_DIR/data:/app/data" \
                -v "$CURRENT_DIR/logs:/app/logs" \
                -v "$TEMP_SCRIPT:/tmp/run_ps_test.py" \
                "$IMAGE_NAME" \
                python /tmp/run_ps_test.py 2>&1 | head -40 | while IFS= read -r line; do
                if [[ $line == *"Error"* ]] || [[ $line == *"timeout"* ]] || [[ $line == *"no disponible"* ]] || [[ $line == *"ERROR"* ]] || [[ $line == *"falló"* ]]; then
                    show_error "$line"
                elif [[ $line == *"exitoso"* ]] || [[ $line == *"OK"* ]] || [[ $line == *"SUCCESS"* ]]; then
                    show_success "$line"
                elif [[ $line == *"Solicitud"* ]] || [[ $line == *"Respuesta"* ]]; then
                    show_communication "$line"
                else
                    echo "$line"
                fi
            done
            
            rm -f "$TEST_FILE" "$TEMP_SCRIPT"
            echo
            
            # Verificar que GA siga detenido después de la prueba
            if docker ps --filter "name=^ga$" --format "{{.Names}}" 2>/dev/null | grep -q "^ga$"; then
                show_error "GA se levantó durante la prueba. Deteniéndolo..."
                docker compose stop ga
            else
                show_success "GA permaneció detenido durante la prueba"
            fi
            echo
            
            show_info "Logs de actores después del intento de operación:"
            echo -e "${CYAN}--- Actor Préstamo (últimos 10 segundos) ---${NC}"
            docker compose logs --since 10s actor_prestamo 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde|Error|disponible|Gestor de Almacenamiento" | tail -15 || echo "  (sin logs nuevos)"
            echo
            echo -e "${CYAN}--- Actor Devolución (últimos 10 segundos) ---${NC}"
            docker compose logs --since 10s actor_devolucion 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde|Error|disponible|Gestor de Almacenamiento" | tail -15 || echo "  (sin logs nuevos)"
            echo
            echo -e "${CYAN}--- Actor Renovación (últimos 10 segundos) ---${NC}"
            docker compose logs --since 10s actor_renovacion 2>/dev/null | grep -iE "GA|timeout|error|failover|no disponible|no responde|Error|disponible|Gestor de Almacenamiento" | tail -15 || echo "  (sin logs nuevos)"
            echo
        fi
        
        echo -e "${YELLOW}¿Deseas recuperar GA? (s/n)${NC}"
        read -r respuesta2
        
        if [[ "$respuesta2" == "s" ]] || [[ "$respuesta2" == "S" ]]; then
            show_info "Reiniciando GA..."
            docker compose start ga
            show_success "GA reiniciado"
            echo
            
            show_info "Esperando que GA esté listo..."
            sleep 5
            
            show_info "Logs de reconexión (últimos 10 segundos):"
            echo -e "${CYAN}--- Actor Préstamo ---${NC}"
            docker compose logs --since 10s actor_prestamo 2>/dev/null | grep -iE "GA|conectado|reconectar|health|exitoso" | tail -5 || echo "  (sin logs nuevos)"
            echo
            echo -e "${CYAN}--- Actor Devolución ---${NC}"
            docker compose logs --since 10s actor_devolucion 2>/dev/null | grep -iE "GA|conectado|reconectar|health|exitoso" | tail -5 || echo "  (sin logs nuevos)"
            echo
            echo -e "${CYAN}--- Actor Renovación ---${NC}"
            docker compose logs --since 10s actor_renovacion 2>/dev/null | grep -iE "GA|conectado|reconectar|health|exitoso" | tail -5 || echo "  (sin logs nuevos)"
        fi
    fi
    
    echo
    pause
}

# Función para mostrar arquitectura
show_architecture() {
    show_step "9" "Explicando arquitectura del sistema (Etapa 2)"
    
    echo -e "${WHITE}Arquitectura del Sistema Distribuido - Etapa 2:${NC}"
    echo
    echo -e "${CYAN}1. Componentes (6 servicios):${NC}"
    echo -e "   ${GREEN}GA${NC} - Gestor de Almacenamiento (réplicas primaria/secundaria)"
    echo -e "   ${GREEN}GC${NC} - Gestor de Carga (coordinador)"
    echo -e "   ${GREEN}Actor Préstamo${NC} - Procesa préstamos (REQ/REP)"
    echo -e "   ${GREEN}Actor Devolución${NC} - Procesa devoluciones (PUB/SUB)"
    echo -e "   ${GREEN}Actor Renovación${NC} - Procesa renovaciones (PUB/SUB)"
    echo -e "   ${GREEN}PS${NC} - Proceso Solicitante (cliente)"
    echo
    echo -e "${CYAN}2. Patrones de Comunicación:${NC}"
    echo -e "   ${YELLOW}REQ/REP (Síncrono):${NC}"
    echo -e "      - PS <-> GC (puerto 5001)"
    echo -e "      - GC <-> Actor Préstamo (puerto 5004)"
    echo -e "      - Actores <-> GA (puerto 5003)"
    echo -e "   ${YELLOW}PUB/SUB (Asíncrono):${NC}"
    echo -e "      - GC -> Actores (puerto 5002) para devolución/renovación"
    echo
    echo -e "${CYAN}3. Flujo de Operaciones:${NC}"
    echo -e "   ${GREEN}Préstamo (REQ/REP):${NC}"
    echo -e "      PS -> GC -> Actor Préstamo -> GA -> Actor Préstamo -> GC -> PS"
    echo -e "   ${GREEN}Devolución/Renovación (PUB/SUB):${NC}"
    echo -e "      PS -> GC (respuesta inmediata) -> GC publica evento -> Actor -> GA"
    echo
    echo -e "${CYAN}4. Características Técnicas:${NC}"
    echo -e "   - Réplicas primaria/secundaria con sincronización asíncrona"
    echo -e "   - Failover automático con health checks"
    echo -e "   - Sistema de métricas con exportación a CSV"
    echo -e "   - Búsqueda de libros por código o criterios"
    echo -e "   - Validación de préstamos (máximo 2 semanas)"
    echo -e "   - Comunicación TCP entre contenedores"
    echo -e "   - Logs detallados con timestamps en español"
    echo
    
    pause
}

# Función para limpiar
cleanup() {
    show_step "10" "Limpiando el sistema"
    
    show_info "Deteniendo contenedores..."
    docker compose down
    show_success "Sistema detenido correctamente"
    echo
}

# Función para mostrar menú
show_menu() {
    clear_screen
    echo -e "${WHITE}Selecciona una opción (Sistema Etapa 2):${NC}"
    echo
    echo -e "${GREEN}1.${NC} Ver estado inicial y réplicas"
    echo -e "${GREEN}2.${NC} Preparar entorno"
    echo -e "${GREEN}3.${NC} Iniciar servicios (GA, GC, Actores) y mostrar IPs"
    echo -e "${GREEN}4.${NC} Ejecutar solicitudes (PRESTAMO, RENOVACION, DEVOLUCION)"
    echo -e "${GREEN}5.${NC} Mostrar logs detallados de comunicación"
    echo -e "${GREEN}6.${NC} Ver resultados finales y sincronización de réplicas"
    echo -e "${GREEN}7.${NC} Ver métricas de rendimiento"
    echo -e "${GREEN}8.${NC} Probar failover (simular fallo de GA)"
    echo -e "${GREEN}9.${NC} Explicar arquitectura (Etapa 2)"
    echo -e "${GREEN}10.${NC} Limpiar sistema"
    echo -e "${RED}11.${NC} Salir"
    echo
    echo -n -e "${YELLOW}Ingresa tu opción (1-11): ${NC}"
}

# Función principal
main() {
    clear_screen
    
    echo -e "${WHITE}Bienvenido al Sistema Distribuido de Libros - Etapa 2${NC}"
    echo -e "${CYAN}Este script te guiará paso a paso para demostrar el funcionamiento${NC}"
    echo -e "${CYAN}Incluye: PRESTAMO, réplicas, failover y métricas${NC}"
    echo
    
    while true; do
        show_menu
        read -r option
        
        case $option in
            1)
                show_initial_state
                ;;
            2)
                prepare_environment
                ;;
            3)
                start_services
                ;;
            4)
                run_requests
                ;;
            5)
                show_detailed_logs
                ;;
            6)
                show_results
                ;;
            7)
                show_metrics
                ;;
            8)
                test_failover
                ;;
            9)
                show_architecture
                ;;
            10)
                cleanup
                ;;
            11)
                echo -e "${GREEN}Hasta luego!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Opción inválida. Intenta de nuevo.${NC}"
                pause
                ;;
        esac
    done
}

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.yml" ]; then
    show_error "No se encontró docker-compose.yml. Asegúrate de estar en el directorio correcto."
    exit 1
fi

# Ejecutar función principal
main
