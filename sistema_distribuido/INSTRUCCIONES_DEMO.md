# Instrucciones para la Demostración de Sustentación

Este documento explica cómo usar el script `demo_sustentacion.py` para demostrar los 3 casos de prueba requeridos para la sustentación.

## Requisitos Previos

1. Asegúrate de estar en el directorio `sistema_distribuido`
2. Docker y Docker Compose deben estar instalados y funcionando
3. Python 3.6 o superior debe estar instalado

## Ejecución

### Opción 1: Ejecutar todos los casos automáticamente

```bash
cd sistema_distribuido
python3 demo_sustentacion.py
```

El script te preguntará si deseas ejecutar todos los casos. Responde `s` para continuar.

### Opción 2: Ejecutar casos individuales

Puedes modificar el script para ejecutar solo un caso específico comentando los otros en la función `main()`.

## Casos de Prueba

### Caso 1: Operaciones desde SEDE_2 con BD pequeña

**Objetivo**: Demostrar las tres operaciones (préstamo, devolución, renovación) desde la sede 2 con una base de datos pequeña para apreciar fácilmente los cambios.

**Qué hace**:
- Genera una base de datos pequeña (15 libros)
- Muestra el estado inicial de la BD
- Ejecuta un PRESTAMO desde SEDE_2 y muestra el estado después
- Ejecuta una DEVOLUCION desde SEDE_2 y muestra el estado después
- Ejecuta un PRESTAMO nuevamente y luego una RENOVACION desde SEDE_2
- Muestra el estado final de la BD

**Archivos generados**:
- `data/caso1_prestamo.txt`
- `data/caso1_devolucion.txt`
- `data/caso1_prestamo2.txt`
- `data/caso1_renovacion.txt`
- `data/caso1_sede2_completo.txt`

**Logs**: Los logs se muestran en tiempo real durante la ejecución.

### Caso 2: Sistema con carga múltiple

**Objetivo**: Ejecutar el sistema completo con múltiples PS (1-2 por sede) generando carga desde varios archivos.

**Qué hace**:
- Genera datos iniciales completos (1000 libros)
- Crea 4 archivos de solicitudes (2 para SEDE_1, 2 para SEDE_2)
- Ejecuta múltiples PS en paralelo
- Muestra logs en tiempo real de todos los servicios
- Muestra el estado final de la BD

**Archivos generados**:
- `data/caso2_sede1_0.txt`
- `data/caso2_sede1_1.txt`
- `data/caso2_sede2_0.txt`
- `data/caso2_sede2_1.txt`

### Caso 3: Sistema con fallo de GA

**Objetivo**: Ejecutar el sistema con carga y simular el fallo del Gestor de Almacenamiento (GA) durante la ejecución, demostrando que el sistema detecta el fallo y maneja el error apropiadamente.

**Qué hace**:
- Genera datos iniciales completos
- Crea 4 archivos de solicitudes
- Inicia múltiples PS en paralelo
- Detiene el GA después de que los PS empiecen a procesar
- Muestra logs de detección de fallo en tiempo real
- Verifica que el sistema maneja el error apropiadamente

**Archivos generados**:
- `data/caso3_sede1_0.txt`
- `data/caso3_sede1_1.txt`
- `data/caso3_sede2_0.txt`
- `data/caso3_sede2_1.txt`

## Características del Script

### Validación de Archivos
- Verifica que los archivos de solicitudes existen antes de ejecutar
- Valida el formato de las solicitudes (operación, libro_id, usuario_id, sede)
- Muestra mensajes claros de error si hay problemas

### Visualización Mejorada
- Colores para diferentes tipos de mensajes (éxito, error, advertencia, info)
- Separadores claros entre secciones
- Estado de BD formateado de forma legible
- Logs en tiempo real con colores según tipo de mensaje

### Logs en Tiempo Real
- Muestra logs de los contenedores durante la ejecución
- Filtra logs relevantes (por ejemplo, errores relacionados con GA)
- Colorea los logs según su tipo (ERROR, WARNING, SUCCESS)

### Manejo de Errores
- Captura y muestra errores claramente
- Verifica que los servicios estén corriendo antes de ejecutar
- Maneja interrupciones del usuario (Ctrl+C)

## Estructura de Archivos de Solicitudes

Los archivos de solicitudes deben tener el siguiente formato:

```
# Comentarios empiezan con #
PRESTAMO LIBRO_ID USUARIO_ID SEDE
DEVOLUCION LIBRO_ID USUARIO_ID SEDE
RENOVACION LIBRO_ID USUARIO_ID SEDE
```

Ejemplo:
```
# Préstamo desde SEDE_2
PRESTAMO L0001 U0001 SEDE_2
DEVOLUCION L0001 U0001 SEDE_2
PRESTAMO L0001 U0001 SEDE_2
RENOVACION L0001 U0001 SEDE_2
```

## Notas Importantes

1. **Base de Datos**: El script lee la BD desde `data/primary/libros.json` (donde el GA escribe). Si no existe, intenta leer desde `data/libros.json`.

2. **Servicios**: El script verifica que todos los servicios estén corriendo antes de ejecutar cada caso. Si algún servicio no está disponible, el script mostrará un error.

3. **Pausas Interactivas**: El script incluye pausas entre operaciones para que puedas apreciar los cambios. Presiona Enter para continuar.

4. **Limpieza**: Al final, el script limpia los servicios Docker. Si quieres mantenerlos corriendo, comenta la llamada a `limpiar_servicios()` al final de `main()`.

5. **Tiempo de Ejecución**: 
   - Caso 1: ~5 minutos (con pausas)
   - Caso 2: ~3 minutos
   - Caso 3: ~5 minutos

## Solución de Problemas

### Error: "No se encontró docker-compose.yml"
- Asegúrate de estar en el directorio `sistema_distribuido`

### Error: "Archivo no encontrado"
- Verifica que los archivos de solicitudes se hayan creado correctamente
- Revisa los logs del script para ver qué archivo está faltando

### Error: "Servicios no están corriendo"
- Verifica que Docker esté corriendo: `docker ps`
- Intenta levantar los servicios manualmente: `docker compose up -d ga gc actor_prestamo actor_devolucion actor_renovacion`

### Los logs no se muestran en tiempo real
- Esto es normal, el script muestra los logs más recientes después de la ejecución
- Para ver logs en tiempo real, usa: `docker compose logs -f`

## Personalización

Puedes modificar el script para:
- Cambiar el número de libros en la BD pequeña (función `generar_bd_pequena()`)
- Cambiar el número de archivos de solicitudes por sede
- Modificar los tiempos de espera
- Agregar más validaciones
- Cambiar los colores de la salida

## Contacto

Si tienes problemas o preguntas sobre el script, revisa los logs en el directorio `logs/` o los mensajes de error del script.

