# Redis para la caché y el límite de tasa

- **Estado:** en curso. Se sigue por la primera casilla sin marcar.
- **Origen:** `PROMPT_REDIS.md` (en `~/Desktop/TUKITDOC/`), que es la fuente de verdad.
- **Rama:** `feature/cache-redis`, sobre `feature/colas-rabbitmq` (`466e4ac`). PR apilado encima
  del PR #2.
- **Alcance:** la lectura de las listas, los vectores de los renglones y el límite de tasa del
  gateway. Quedan fuera el banco de QA, los diagramas de Visual Paradigm, la documentación de la
  tesis, `main`, `integracion/ramas-octubre`, `feature/colas-rabbitmq`, el almacén del
  cortacircuitos, la caché de permisos y sesiones, y Kubernetes.

## Contexto, comprobado en el código

Lo que el prompt describe se confirma, con estas precisiones:

- **Redis hoy.** El contenedor `redis:7` está solo en el perfil `infra` del compose, `.env.ejemplo`
  trae `REDIS_URL=redis://localhost:6379/0` con el comentario del cortacircuitos y de socket.io,
  ningún servicio lee la variable y ningún `pyproject.toml` depende de un cliente de Redis. El
  `.venv` no tiene `redis`. El Redis de Homebrew es la versión 8; el del compose y el de CI, la 7.
- **`_percibir_onboarding` es síncrona** y sus dos rutas (`subir_listas` y `onboarding`) son
  `async def`: la lectura bloquea el bucle de eventos mientras Gemini responde, como hoy. Para
  consultar Redis sin bloquear, el envoltorio pasa a `async`; la lectura sigue siendo la misma
  llamada síncrona. Una prueba (`test_onboarding.py`) cambia el envoltorio entero por una función
  síncrona: pasa a ser asíncrona.
- **La `Percepcion` aceptada solo trae `grados`, `paginas` e `items`** (cada uno con
  `descripcion`, `cantidad` y `confianza`). No trae el archivo, la cuenta, el correo ni el hijo:
  esos viven en la ruta. Los `items` son el texto de la lista; si una lista trajera escrito el
  nombre de un niño y el modelo lo leyera como renglón, iría en el valor. Queda como riesgo.
- **La versión de la lectura tiene cuatro piezas:** `paginas.py` (el render, con pypdfium2 a
  150 DPI), `gemini.py` (el prompt, el esquema y la validación de la respuesta), `percepcion.py`
  (las reglas de grados, páginas incompletas y rechazos) y el modelo efectivo, que sale de
  `GEMINI_MODELO` con `gemini-3.5-flash-lite` por omisión.
- **`calcular_vectores` tiene tres llamadas, no dos:** `emparejar_en_catalogo`, la ruta
  `POST /v1/catalogo/emparejar` y el ensayo `ensayos/bench_laya/generar_instancias.py`, que la
  llama desde un script síncrono. Las dos primeras son `async def`. Pasa a `async` y el ensayo la
  corre con `asyncio.run`.
- **El modelo de los vectores no es `embeder_gemini.modelo`.** Ese atributo es la constante
  `gemini-embedding-001`, pero `embeder_gemini` usa el de `GEMINI_MODELO_EMBEDDING` si está
  definido. La clave tiene que llevar el efectivo. `embeder_gemini` manda cada texto tal cual, a
  1024 dimensiones (`DIMENSION_EMBEDDING`).
- **Si el proveedor falla, hoy toda la tanda baja a léxico** (`[None] * n`), y el contrato lo
  promete así (§8: «toda línea baja a `AMBIGUO`»). Con caché se mantiene: si el proveedor falla,
  la tanda entera sale sin vectores, aunque algunos estuvieran guardados.
- **Sin `GEMINI_API_KEY` el catálogo no usa ningún embeder** (`_embeder_por_entorno`), así que con
  `make arriba` y `env -u GEMINI_API_KEY` no hay vectores que guardar. La prueba de punta a punta
  de los vectores se hace con la app de catálogo en una prueba de integración contra el Redis
  local, con el embeder falso.
- **La lista de rutas estrictas, revisada contra los routers:**
  - existen y entran: `POST /v1/listas/subir`, `POST /v1/trabajos`,
    `POST /v1/trabajos/{trabajo_id}/reintentar`, `POST /v1/admin/onboarding`,
    `POST /v1/admin/onboarding/{version_id}/preview` y `POST /v1/sesiones` (no
    `/v1/sesiones/cierre`);
  - se agregan: `POST /v1/cuenta` y `POST /v1/registro` (altas públicas, que derivan una clave y
    escriben cuentas), `POST /v1/trabajos/aplicar-canonico` (la otra forma de crear un trabajo) y
    `POST /v1/catalogo/emparejar` (hasta 500 renglones con embeddings; la web no la llama, los
    servicios la llaman directo);
  - quedan en el nivel general, por ser del flujo de pagos: `POST /v1/ordenes`,
    `POST /v1/comercio/mis-pedidos/{id}/pago` y `POST /v1/pagos/{id}/sincronizar`.
- **Ningún servicio llama a otro por el gateway:** cada `remoto.py` usa `TUKIT_*_URL`. El límite
  solo ve el tráfico de la web, la consola y lo que entre de fuera.
- **Next.js 16.3.4 pone `X-Forwarded-For` solo si no viene** (`??=` en `base-server.js`, con la
  dirección del socket). Si Next queda expuesto sin un proxy delante, el cliente escribe esa
  cabecera y la clave de IP se puede falsear; con un proxy que agregue la IP real a la derecha, la
  regla de «la primera IP sin confianza desde la derecha» da la real. Los manejadores de Next no
  ven el socket (`request.ip` ya no existe), así que reenvían lo que Next dejó.
- **El cliente de servidor es un singleton** (`origenDeDatos()`) y tiene dos `fetch` al backend:
  `pedir` y `documento`. Todas las páginas y manejadores que lo usan son `force-dynamic`, así que
  leer `headers()` de `next/headers` en cada petición no cambia cómo se renderiza nada.
- **Los mensajes de error que ve la persona son el `mensaje` del backend** (`causa.message` en la
  web y la consola, `cuerpo.mensaje` en el ingreso). Si el gateway pone la espera en el mensaje,
  todas las pantallas la muestran. `sondear` reintenta todo salvo el 404, así que reintentaría un
  429; `ResultadoPago` solo reintenta 502, 503 y 504, y no cambia.
- **Las páginas del servidor degradan por sección** con su propio `try/catch` y no hay
  `error.tsx`. Un 429 en una página la deja con secciones vacías, como cualquier fallo del
  backend. Con los números por omisión una familia no llega ahí; queda como riesgo.
- **Las pruebas por servicio de CI no corren `libs/py/tukit_comun/tests`** e instalan sus
  dependencias a mano, sin `redis`. Los `conftest.py` de identidad, inteligencia y operación ya
  borran `RABBITMQ_URL`; ninguno borra `REDIS_URL`, y el gateway no tiene `conftest.py`.
- **`arquitectura/manifiesto.toml` no declara infraestructura por servicio.** No hay nada que
  declarar ahí; la frontera nueva («solo `tukit_comun` importa `redis`») va como prueba.
- **`arquitectura/humo.py` hace unas 25 peticiones** al gateway: queda lejos del límite.

## Decisiones

Las ocho del prompt, sin cambios:

1. Redis es solo caché y límite de tasa (ADR 0007). Postgres sigue siendo la fuente de verdad y
   RabbitMQ el único broker.
2. Si Redis falla, nada se cae: espera corta, la caché calcula como hoy, el límite cuenta en
   memoria, un registro por episodio y nunca un 500.
3. Sin `REDIS_URL`, todo como hoy salvo el límite, que cuenta en memoria por proceso. `make arriba`
   pasa la URL si Redis responde, y `make arriba REDIS_URL=` arranca sin ella.
4. La lectura aceptada se guarda en `_percibir_onboarding`, con la huella del archivo y la versión
   de la percepción, 30 días. El cruce con el catálogo y los precios se recalcula siempre.
5. Los vectores se guardan en `calcular_vectores`, con el modelo, la dimensión y la huella del
   texto, 24 horas. Un lote lee todas sus claves de una vez y pide solo las que faltan.
6. El gateway limita en dos niveles, con dos claves (token e IP) que deben pasar las dos, la IP de
   `X-Forwarded-For` solo desde un proxy de confianza, conteo atómico en Redis y un 429 con
   `Retry-After`.
7. Un cliente común en `tukit_comun`, con `redis` importado solo si hay `REDIS_URL`, y un doble en
   memoria para las pruebas.
8. Aciertos, fallos y degradaciones se cuentan con las métricas y los logs de `tukit_comun`.

Y estas, tomadas al leer el código:

9. **El módulo es `tukit_comun/cache.py`.** `ClienteRedis` envuelve un *motor* con cinco
   operaciones: `leer`, `leer_varias`, `guardar_varias`, `contar` y `cerrar`. Hay dos motores:
   `MotorRedis` (redis-py asíncrono, con `GET`, `MGET`, `SET` con `EX` en una tubería, y un script
   Lua para contar) y `MotorEnMemoria` (un diccionario con vencimiento). El doble de las pruebas,
   `RedisEnMemoria` en `tukit_comun/pruebas_redis.py`, es el motor en memoria con modos «caído» y
   «lento» y un registro de llamadas. Los servicios solo usan `cliente_redis()`, que devuelve el
   cliente del proceso.
10. **La degradación.** Cada operación espera como mucho 250 ms (`TUKIT_REDIS_ESPERA_MS`). Si falla
    o vence, el cliente marca un episodio, deja de preguntarle a Redis durante 5 s y vuelve a
    probar. El primer fallo del episodio deja un WARNING con el tipo de error, sin claves; la
    vuelta deja un INFO. Mientras dura, `leer` da «no está», `guardar_varias` no hace nada y
    `contar` cuenta en el motor en memoria del proceso. Sin `REDIS_URL` el cliente está en ese
    mismo modo desde el principio, sin registrar nada, y no importa `redis`. Con `REDIS_URL` pero
    sin el paquete, registra el WARNING una vez y sigue sin Redis.
11. **Las claves** llevan el prefijo `tukit:`:
    - `tukit:percepcion:<versión>:<sha256 del archivo>`, 30 días
      (`TUKIT_CACHE_PERCEPCION_SEGUNDOS`, 2.592.000);
    - `tukit:vector:<modelo>:<dimensión>:<sha256 del texto>`, 24 horas
      (`TUKIT_CACHE_VECTORES_SEGUNDOS`, 86.400);
    - `tukit:limite:<nivel>:<ruta>:<token|ip>:<huella>`, lo que dure la ventana. La huella del
      token es su SHA-256; la de la IP también, para que ni la IP ni el token queden en claro.
12. **La versión de la percepción** son los primeros 16 caracteres del SHA-256 de los bytes de
    `paginas.py`, `gemini.py` y `percepcion.py`, la versión instalada de pypdfium2 y el modelo
    efectivo. Cualquier cambio en esos archivos, aunque sea un comentario, vuelve a leer: se
    prefiere una lectura de más a una lectura vieja.
13. **Los valores.** La percepción va como JSON con `grados`, `paginas` e `items`; al leerla se
    rearma la `Percepcion` aceptada. Un valor que no se puede leer cuenta como «no está». El vector
    va empacado en `float64` little-endian, para que el resultado con caché sea idéntico al de sin
    caché; si su largo no es el de la dimensión, cuenta como «no está».
14. **Solo se cachea con un modelo declarado.** Un embeder sin modelo conocido (los dobles de las
    pruebas, una función suelta) calcula como hoy, sin caché.
15. **El conteo es por ventana fija.** Un script Lua hace, por cada clave, `INCR`, `EXPIRE` si es
    la primera o si quedó sin vencimiento, y `PTTL`, y devuelve los pares. Es una sola ida y vuelta
    para todas las claves de la petición, y funciona igual en Redis 7 y 8.
16. **Los números por omisión**, todos configurables por entorno y con `0` para apagar un conteo:

    | Nivel | Ventana | Por token | Por IP |
    |---|---|---|---|
    | General, todo `/v1/*` | 60 s | 300 | 1.200 |
    | Estricto, por ruta | 600 s | 30 | 60 |

    Variables: `TUKIT_LIMITE_GENERAL_VENTANA`, `TUKIT_LIMITE_GENERAL_TOKEN`,
    `TUKIT_LIMITE_GENERAL_IP`, `TUKIT_LIMITE_ESTRICTO_VENTANA`, `TUKIT_LIMITE_ESTRICTO_TOKEN` y
    `TUKIT_LIMITE_ESTRICTO_IP`. Una ruta estricta cuenta en los dos niveles. El nivel estricto
    cuenta por ruta, para que los intentos de entrar no gasten el cupo de las subidas. La IP tiene
    más cupo que el token porque detrás de una IP puede haber muchas familias (un colegio, un NAT
    de operador móvil). La justificación va en el ADR 0047.
17. **La IP del cliente.** Si la conexión viene de un proxy de confianza
    (`TUKIT_PROXIES_CONFIANZA`, IP o redes separadas por comas; por omisión `127.0.0.1,::1`), se
    recorre `X-Forwarded-For` de derecha a izquierda y la IP es la primera que no es de confianza;
    si todas lo son, la de más a la izquierda. Una entrada que no es una IP corta el recorrido y se
    usa la última de confianza. Si la conexión no viene de un proxy de confianza, la cabecera se
    ignora. Las IPv4 escritas como IPv6 (`::ffff:127.0.0.1`) se normalizan.
18. **El 429.** Cuerpo `{"error": "demasiadas_peticiones", "mensaje": "...", "reintentar_en_segundos": N}`
    y `Retry-After: N`, con N el mayor tiempo que le falta a una clave pasada (mínimo 1). El
    mensaje dice la espera en segundos o en minutos. Quedan fuera del límite `/v1/servicios`,
    `/v1/webhooks/*`, las preflight `OPTIONS` y lo que no es `/v1/*` (`/salud`, `/health/*`). Una
    ruta desconocida sí cuenta: un escáner también gasta cupo.
19. **El lado de Next.js.**
    - `ClienteApi` recibe una función opcional `cabeceras` que da las cabeceras de la petición
      entrante que se reenvían, y la usa en sus dos `fetch`. `servidor.ts` la arma con
      `headers()` de `next/headers`: solo `X-Forwarded-For`. Fuera de una petición no reenvía
      nada.
    - Un 429 lleva `reintentar_en_segundos` en el `detalle` de `ErrorTukit`, del cuerpo o del
      `Retry-After`.
    - `respuestaDeError`, en la web y en la consola, pone `Retry-After` en un 429.
    - Los ayudantes del navegador (`api-navegador.ts` en las dos apps y `api-onboarding.ts`) arman
      el mensaje con la espera si el cuerpo no lo trae, y `sondear` deja de sondear con un 429.
20. **Las pruebas de integración** llevan el marcador `redis`, toman la URL de
    `TUKIT_PRUEBAS_REDIS_URL` (por omisión `redis://localhost:6379/15`), se saltan sin Redis salvo
    con `TUKIT_PRUEBAS_REDIS_OBLIGATORIO=1`, usan un prefijo por corrida y borran sus claves al
    terminar con `SCAN` y `DEL`, que solo usan las pruebas. Corren con `make prueba-redis`;
    `make prueba` las deja fuera. Los `conftest.py` de los servicios borran `REDIS_URL`, para que
    una variable exportada en la terminal no meta Redis en las pruebas unitarias.
21. **El compose.** Redis entra también al perfil `api`, sin persistencia y con un tope de memoria
    que desaloja lo menos usado (`--maxmemory 256mb --maxmemory-policy allkeys-lru --save ""`).
    Gateway, catálogo e inteligencia reciben `REDIS_URL` y dependen de él. El gateway confía
    también en la red de Docker, porque la web le llega desde fuera del compose.

## Tareas

### 0. Plan

- [x] Leer el código y confirmar o corregir el contexto.
- [x] Escribir este plan y hacer su commit.

### 1. Base común en `tukit_comun`

- [x] `redis` como dependencia de `tukit_comun`, con `uv`, en su `pyproject.toml` y en `uv.lock`.
- [x] `cache.py`: `ClienteRedis`, `MotorRedis`, `MotorEnMemoria`, `cliente_redis()`, la
      degradación por episodio y `python -m tukit_comun.cache` para que `make arriba` compruebe
      que Redis responde.
- [x] `metricas.py`: aciertos, fallos y degradaciones por uso, y rechazos del límite.
- [x] `pruebas_redis.py`: el doble `RedisEnMemoria` y lo que usan las pruebas de integración.
- [x] Pruebas unitarias con el doble: lectura, escritura, conteo, vencimiento, caído, lento, un
      registro por episodio, vuelta, sin `REDIS_URL` y sin el paquete.
- [x] Pruebas de integración contra el Redis local, con el marcador `redis`.
- [x] El marcador en `pyproject.toml`, `make prueba` sin él y `make prueba-redis`.

### 2. La lectura de la lista

- [x] `_percibir_onboarding` asíncrona, con la caché; sus dos rutas la esperan.
- [x] `gemini.modelo()` para leer el modelo efectivo en un solo sitio.
- [x] Pruebas, contando las lecturas del lector doble: el mismo archivo dos veces, otro archivo,
      un rechazo, un cambio de versión, Redis caído, Redis lento, y lo guardado sin datos de la
      persona ni del hijo.
- [x] Una prueba de integración con la app de inteligencia contra el Redis local.

### 3. Los vectores

- [x] `calcular_vectores` asíncrona, con la caché; sus tres llamadas la esperan.
- [x] `embeddings.modelo_de(embeder)` con el modelo efectivo.
- [x] Pruebas: lote mixto (el proveedor recibe solo los que faltan, en orden, y el resultado sale
      en el orden original), fallo del proveedor, Redis caído, la duración de la clave y un
      embeder sin modelo.
- [x] Una prueba de integración con la app de catálogo y el embeder falso contra el Redis local.

### 4. El límite de tasa

- [x] `tukit_gateway/limite.py`: niveles, rutas estrictas y exentas, claves, IP del cliente y 429.
- [x] `reenviar` limita antes de reenviar.
- [x] Pruebas: por debajo y por encima del límite con `Retry-After`, las dos claves, el nivel
      estricto por ruta, `X-Forwarded-For` desde un proxy de confianza y desde uno que no lo es,
      las rutas exentas, Redis caído (cuenta en memoria) y la configuración por entorno.
- [x] Prueba de integración: dos limitadores con su propia conexión comparten el contador.
- [ ] `tukit-contrato`: `cabeceras` en `ClienteApi`, `X-Forwarded-For` desde `servidor.ts` y
      `reintentar_en_segundos` en el 429.
- [ ] La web y la consola: `Retry-After` en `respuestaDeError`, el mensaje con la espera en los
      ayudantes del navegador y `sondear` sin reintentar un 429.

### 5. Infraestructura y CI

- [ ] `infra/docker-compose.yml`: Redis con los servicios que lo usan y su `REDIS_URL`.
- [ ] `.env.ejemplo`: `REDIS_URL` y las variables nuevas, con su comentario.
- [ ] `Makefile`: `arriba` con `CON_REDIS`, `abajo` y `prueba-redis`.
- [ ] `ci.yml`: el trabajo `redis` con `redis:7`; los demás no cambian.
- [ ] Fronteras: solo `tukit_comun` importa `redis`. Sus pruebas, en verde.

### 6. Documentación

- [ ] ADR 0047, su fila en el índice y el rango de `docs/README.md` a «0027 a 0047».
- [ ] `CONTRATO_API.md` a la 1.11, con «Qué cambió en 1.11», el 429 en el §11 y Redis en el §8.
- [ ] `REVISION_ARQUITECTURA.md` y lo demás que describa Redis.

### 7. Verificación y PR

- [ ] `make lint`, `make prueba`, `make prueba-colas`, `make prueba-redis`, `npm run lint` y
      `npm run typecheck`, en verde.
- [ ] Punta a punta con `make arriba` (`env -u GEMINI_API_KEY`) contra Redis y RabbitMQ locales:
      el límite con `curl` y con dos gateways; la lectura y los vectores como se dice arriba.
- [ ] Push de la rama y PR con base `feature/colas-rabbitmq`; CI en verde.

### 8. Cierre

- [ ] Todas las casillas y la sección «Resultado».

## Orden de commits

1. `docs: plan de la cache y el limite de tasa con Redis`
2. `comun: cliente de Redis con espera corta y degradacion`
3. `inteligencia: la lectura aceptada de una lista se guarda en Redis`
4. `catalogo: el vector de cada renglon se guarda en Redis`
5. `gateway: limite de tasa con dos niveles y dos claves`
6. `web: el servidor reenvia la IP y el 429 se muestra con su espera`
7. `infra: Redis en el compose, en make arriba y en CI`
8. `fronteras: solo tukit_comun habla con Redis`
9. `docs: ADR 0047, contrato 1.11 y revision de arquitectura`
10. `docs: resultado del plan de Redis`

Si una tarea pide partir o juntar commits, el orden se mantiene.

## Reservado a Juan

- Hacer Redis obligatorio. Este plan lo deja opcional en todo.
- Guardar en Redis algo que sea la única copia. Este plan solo guarda lo que se puede recalcular y
  contadores que se pueden perder.
- Tocar el flujo de pagos. Las rutas de órdenes y pagos quedan en el nivel general; decidir si
  `POST /v1/ordenes` (que reserva inventario) merece el nivel estricto.
- Los números del límite. Los de la decisión 16 no frenan a una familia normal; si la tesis o el
  banco de QA piden otros, se cambian por entorno.
