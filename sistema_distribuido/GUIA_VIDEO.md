# 🎬 Guía Específica para Video Demostrativo - Proyecto Actual

## ⏱️ Estructura del Video (10 minutos máximo)

---

## 1️⃣ DISTRIBUCIÓN DE COMPONENTES EN MÁQUINAS (2 minutos)

### Archivos a mostrar:

1. **`docker-compose.yml`** (líneas 1-175)
   - Mostrar los 6 servicios definidos
   - Explicar la red `red_distribuida`
   - Mostrar los puertos expuestos

2. **Diagrama de arquitectura** (opcional pero recomendado)
   - `diagramas/diagrama_componentes.png` o `diagramas/diagrama_arquitectura.png`

### Funciones del demo a ejecutar:

**Opción 3 del menú: "Iniciar servicios (GA, GC, Actores) y mostrar IPs"**

```bash
./demo_interactivo.sh
# Seleccionar opción 3
```

### Qué mostrar en pantalla:

1. **Antes de ejecutar:**
   - Abrir `docker-compose.yml` y mostrar:
     - Los 6 servicios: `ga`, `gc`, `actor_prestamo`, `actor_devolucion`, `actor_renovacion`, `ps`
     - La red `red_distribuida`
     - Los puertos: 5001, 5002, 5003, 5004

2. **Durante la ejecución (opción 3):**
   - El script mostrará automáticamente:
     - Estado de contenedores con `docker compose ps`
     - **IPs de cada contenedor** (esto es CRÍTICO)
     - Logs de inicialización de cada servicio

3. **Después de ejecutar:**
   - En otra terminal, ejecutar:
   ```bash
   docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
   ```

### Qué decir:

> "Nuestro sistema está distribuido en 6 procesos independientes ejecutados en contenedores Docker, simulando máquinas separadas:
> 
> - El **GA** (Gestor de Almacenamiento) en el puerto 5003, gestiona las réplicas primaria y secundaria
> - El **GC** (Gestor de Carga) en los puertos 5001 y 5002, coordina todas las operaciones
> - Tres actores especializados: **Actor Préstamo** (puerto 5004), **Actor Devolución** y **Actor Renovación**
> - El **PS** (Proceso Solicitante) que actúa como cliente
> 
> Como pueden ver, cada contenedor tiene su propia IP en la red Docker, y todos se comunican usando ZeroMQ mediante paso de mensajes TCP."

---

## 2️⃣ LIBRERÍAS Y PATRONES USADOS (2 minutos)

### Archivos de código a mostrar:

1. **`gestor_carga.py`** (líneas 96-120)
   - Mostrar la función `inicializar_sockets()`
   - Resaltar:
     - Línea 100: `zmq.REP` (socket REP)
     - Línea 107: `zmq.PUB` (socket PUB)
     - Línea 115: `zmq.REQ` (socket REQ)

2. **`actor_prestamo.py`** (líneas 48-54)
   - Mostrar `inicializar_socket()` con `zmq.REP`

3. **`actor_devolucion.py`** (líneas 48-53)
   - Mostrar `inicializar_socket()` con `zmq.SUB` y `SUBSCRIBE`

4. **`docker-compose.yml`** (línea 50)
   - Mostrar `GC_MODE=serial` (explicar que puede ser `multithread`)

5. **`utils_failover.py`** (líneas 38-53)
   - Mostrar cómo se crea el socket REQ para comunicarse con GA

### Qué mostrar en pantalla:

**Secuencia recomendada:**

1. **Abrir `gestor_carga.py`** y mostrar:
   ```python
   # Línea 100
   self.rep_socket = self.context.socket(zmq.REP)
   # Línea 107
   self.pub_socket = self.context.socket(zmq.PUB)
   # Línea 115
   self.req_actor_prestamo = self.context.socket(zmq.REQ)
   ```

2. **Abrir `actor_devolucion.py`** y mostrar:
   ```python
   # Línea 48
   self.sub_socket = self.context.socket(zmq.SUB)
   # Línea 53
   self.sub_socket.setsockopt(zmq.SUBSCRIBE, b"devolucion")
   ```

3. **Abrir `docker-compose.yml`** y mostrar:
   ```yaml
   # Línea 50
   - GC_MODE=serial
   ```

4. **Mostrar el flujo de comunicación:**
   - Abrir `README.md` y mostrar la sección "Patrones de Comunicación" (líneas 19-25)

### Qué decir:

> "Usamos dos patrones principales de ZeroMQ:
> 
> **REQ/REP para comunicación síncrona:**
> - PS ↔ GC (puerto 5001) - todas las solicitudes
> - GC ↔ Actor Préstamo (puerto 5004) - préstamos
> - Actores ↔ GA (puerto 5003) - operaciones de base de datos
> 
> **PUB/SUB para comunicación asíncrona:**
> - GC → Actor Renovación y Actor Devolución (puerto 5002)
> 
> Como pueden ver en el código, el GC inicializa un socket REP para recibir solicitudes, un socket PUB para publicar eventos, y un socket REQ para comunicarse con el Actor Préstamo.
> 
> También implementamos paralelismo interno en el GC con un pool de workers cuando `GC_MODE=multithread`, para comparar rendimiento con el modo serial."

---

## 3️⃣ DEMOSTRACIÓN DE OPERACIONES REALES (3 minutos)

### Archivos a mostrar:

1. **`data/solicitudes.txt`** (primeras 10-15 líneas)
   - Mostrar ejemplos de PRESTAMO, RENOVACION, DEVOLUCION

2. **`data/primary/libros.json`** (antes y después)
   - Mostrar un libro específico antes de procesar
   - Mostrar el mismo libro después de procesar

### Funciones del demo a ejecutar:

**Secuencia recomendada:**

1. **Opción 1: "Ver estado inicial y réplicas"**
   - Muestra el estado inicial de la base de datos
   - Verifica que las réplicas estén sincronizadas

2. **Opción 3: "Iniciar servicios"** (si no está ejecutado)

3. **Opción 4: "Ejecutar solicitudes"**
   - Esta es la función CRÍTICA para esta sección
   - Muestra en tiempo real las solicitudes siendo procesadas

4. **Opción 6: "Ver resultados finales"**
   - Muestra el estado final de la base de datos
   - Verifica sincronización de réplicas

### Qué mostrar en pantalla:

**Paso 1: Estado inicial**
- Ejecutar opción 1 del demo
- Mostrar el resumen de metadata (total libros, ejemplares disponibles, etc.)
- Abrir `data/primary/libros.json` y mostrar un libro específico (ej: L0001)

**Paso 2: Archivo de solicitudes**
- Abrir `data/solicitudes.txt` y mostrar:
  ```
  RENOVACION L0001 U0231 SEDE_1
  DEVOLUCION L0002 U0456 SEDE_1
  PRESTAMO L0003 U0789 SEDE_1
  ```

**Paso 3: Ejecutar solicitudes**
- Ejecutar opción 4 del demo
- El script mostrará en tiempo real:
  - "PS -> GC: Solicitud de PRESTAMO"
  - "GC -> Actor Préstamo: Reenvío de préstamo"
  - "GC -> Actores: Evento publicado (PUB/SUB)"
  - Mensajes de éxito/error

**Paso 4: Verificar cambios**
- Ejecutar opción 6 del demo
- Abrir `data/primary/libros.json` y mostrar el mismo libro (L0001)
- Comparar `ejemplares_disponibles` antes y después

**Paso 5: Logs detallados (opcional pero recomendado)**
- Ejecutar opción 5 del demo
- Mostrar la comunicación entre contenedores

### Qué decir:

> "Aquí mostramos las tres operaciones obligatorias: préstamo, renovación y devolución.
> 
> **Préstamo** es completamente síncrono: PS envía a GC, GC reenvía a Actor Préstamo, el actor consulta GA, y la respuesta vuelve por el mismo camino.
> 
> **Renovación y devolución** usan eventos asíncronos: PS envía a GC, GC responde inmediatamente confirmando recepción, y luego publica el evento. Los actores correspondientes reciben el evento y actualizan GA.
> 
> Como pueden ver, después de procesar las solicitudes, la base de datos se actualiza correctamente y las réplicas permanecen sincronizadas."

---

## 4️⃣ TRATAMIENTO DE FALLA DEL GA/BD (2 minutos) - CRÍTICO

### Archivos a mostrar:

1. **`utils_failover.py`** (líneas 55-123)
   - Mostrar la función `health_check()`
   - Mostrar el manejo de excepciones (líneas 100-123)

2. **`actor_prestamo.py`** (líneas 40-46, 80-87)
   - Mostrar cómo se inicializa el `FailoverManager`
   - Mostrar cómo se verifica la conexión antes de operar

### Funciones del demo a ejecutar:

**Opción 8: "Probar failover (simular fallo de GA)"**

Esta función está diseñada específicamente para esta demostración.

### Qué mostrar en pantalla:

**Secuencia paso a paso:**

1. **Preparación:**
   - Asegurarse de que los servicios estén corriendo (opción 3)
   - Abrir dos terminales:
     - Terminal A: para ejecutar comandos
     - Terminal B: para ver logs en tiempo real

2. **Terminal B - Monitorear logs:**
   ```bash
   docker compose logs -f actor_prestamo actor_devolucion actor_renovacion
   ```

3. **Terminal A - Mostrar código de failover:**
   - Abrir `utils_failover.py` y mostrar la función `health_check()`
   - Explicar cómo detecta timeouts y errores

4. **Terminal A - Simular fallo:**
   ```bash
   docker compose stop ga
   ```

5. **Terminal B - Mostrar detección:**
   - Los logs mostrarán mensajes como:
     - "Timeout en health check a GA"
     - "GA no está disponible"
     - "Error: Gestor de Almacenamiento no disponible"

6. **Terminal A - Intentar operación:**
   - Ejecutar opción 4 del demo nuevamente (o manualmente):
   ```bash
   docker compose run --rm ps
   ```
   - Mostrar que el sistema detecta el fallo

7. **Terminal A - Recuperar GA:**
   ```bash
   docker compose start ga
   ```

8. **Terminal B - Mostrar reconexión:**
   - Los logs mostrarán que los actores se reconectan
   - Mostrar mensajes de reconexión exitosa

9. **Terminal A - Verificar sincronización:**
   - Ejecutar opción 6 del demo
   - O manualmente:
   ```bash
   diff data/primary/libros.json data/secondary/libros.json
   ```

### Alternativa usando la opción 8 del demo:

Si prefieres usar la función integrada del demo:

1. Ejecutar opción 8 del demo
2. El script te preguntará si deseas simular el fallo
3. Responder "s" (sí)
4. El script detendrá GA y mostrará los logs
5. El script te preguntará si deseas recuperar GA
6. Responder "s" (sí)
7. El script reiniciará GA y mostrará los logs de reconexión

### Qué decir:

> "Aquí simulamos la falla del GA, que es el componente crítico que gestiona la base de datos.
> 
> Los actores ejecutan health checks periódicos usando la función `health_check()` del `FailoverManager`. Cuando GA no responde, detectan el fallo mediante timeouts y excepciones ZMQ.
> 
> Como pueden ver en los logs, cuando detenemos GA, los actores detectan inmediatamente el problema y registran advertencias. Si intentamos realizar una operación, el sistema responde con un error controlado.
> 
> Al restaurar GA, los actores se reconectan automáticamente y el sistema vuelve a operar normalmente. Las réplicas se mantienen sincronizadas gracias a la replicación asíncrona que implementa GA.
> 
> Esto demuestra failover automático y resiliencia del sistema."

---

## 5️⃣ GENERACIÓN DE CARGA (1 minuto)

### Archivos a mostrar:

1. **`data/solicitudes.txt`** (completo)
   - Mostrar todas las solicitudes
   - Contar cuántas hay

2. **`logs/metricas.csv`** (después de ejecutar)
   - Mostrar las métricas registradas

### Funciones del demo a ejecutar:

**Opción 4: "Ejecutar solicitudes"** (ya ejecutada en sección 3)

**Opción 7: "Ver métricas de rendimiento"**

### Qué mostrar en pantalla:

1. **Archivo de solicitudes:**
   - Abrir `data/solicitudes.txt`
   - Mostrar que contiene múltiples solicitudes
   - Contar: `wc -l data/solicitudes.txt` (excluyendo comentarios)

2. **Ejecutar procesamiento:**
   - Ejecutar opción 4 del demo (o ya está ejecutado)
   - Mostrar cómo se procesan todas las solicitudes automáticamente

3. **Métricas:**
   - Ejecutar opción 7 del demo
   - O manualmente:
   ```bash
   cat logs/metricas.csv
   ```
   - Mostrar las columnas: timestamp, operacion, tiempo_respuesta_ms, exito, etc.

4. **Análisis rápido:**
   - Mostrar estadísticas básicas:
   ```bash
   python3 -c "
   import csv
   import statistics
   with open('logs/metricas.csv', 'r') as f:
       reader = csv.DictReader(f)
       prestamos = [row for row in reader if row.get('operacion') == 'PRESTAMO']
       tiempos = [float(row['tiempo_respuesta_ms']) for row in prestamos]
       print(f'Total préstamos: {len(prestamos)}')
       print(f'Tiempo promedio: {statistics.mean(tiempos):.2f} ms')
   "
   ```

### Qué decir:

> "Los procesos solicitantes leen solicitudes desde el archivo `solicitudes.txt`, lo que permite generar carga realista para medir rendimiento.
> 
> Como pueden ver, el sistema procesa automáticamente todas las solicitudes del archivo y registra métricas detalladas en `logs/metricas.csv`, incluyendo tiempo de respuesta, éxito de la operación, y estadísticas en ventanas de 2 minutos.
> 
> Esto nos permite analizar el rendimiento del sistema bajo carga y comparar diferentes configuraciones, como el modo serial versus multithread del GC."

---

## 📋 RESUMEN: Orden de Ejecución Recomendado

### Para grabar el video de forma fluida:

1. **Preparación (antes de grabar):**
   ```bash
   cd sistema_distribuido
   # Asegurarse de que los datos iniciales existen
   python generar_datos_iniciales.py
   ```

2. **Sección 1 - Distribución (2 min):**
   - Mostrar `docker-compose.yml`
   - Ejecutar opción 3 del demo
   - Mostrar `docker ps`

3. **Sección 2 - Patrones (2 min):**
   - Mostrar código de `gestor_carga.py` (REP, PUB, REQ)
   - Mostrar código de `actor_devolucion.py` (SUB)
   - Mostrar `docker-compose.yml` (GC_MODE)

4. **Sección 3 - Operaciones (3 min):**
   - Ejecutar opción 1 (estado inicial)
   - Mostrar `data/solicitudes.txt`
   - Ejecutar opción 4 (procesar solicitudes)
   - Ejecutar opción 6 (resultados)
   - Mostrar cambios en `data/primary/libros.json`

5. **Sección 4 - Failover (2 min):**
   - Mostrar código de `utils_failover.py`
   - Ejecutar opción 8 del demo
   - O hacerlo manualmente con dos terminales

6. **Sección 5 - Carga (1 min):**
   - Mostrar `data/solicitudes.txt` completo
   - Ejecutar opción 7 (métricas)
   - Mostrar `logs/metricas.csv`

---

## 🎯 Puntos Críticos para Obtener Calificación Máxima

✅ **Debes mostrar:**
- Arquitectura distribuida real (6 contenedores con IPs)
- Patrones ZeroMQ implementados (código fuente)
- Ejecución de operaciones (logs en tiempo real)
- Failover real (detener GA y mostrar detección)
- Logs del actor detectando fallos
- Métricas y generación de carga

❌ **NO te limites a:**
- Solo explicar sin demostrar
- Mostrar diagramas sin código real
- Decir que funciona sin probarlo
- Omitir el failover (es crítico)

---

## 📝 Notas Adicionales

- El `demo_interactivo.sh` tiene colores y formato que se verán bien en video
- Los logs se muestran con timestamps y son fáciles de seguir
- Las IPs se muestran automáticamente en la opción 3
- El failover se puede demostrar de dos formas: usando opción 8 o manualmente
- Las métricas se generan automáticamente al ejecutar solicitudes

---

**¡Buena suerte con el video! 🎬**

