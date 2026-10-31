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
    ignora. Las IPv4 escritas como IPv6 (`::ffff:127.0.0.1`) se normalizan. El gateway lanza
    uvicorn con `proxy_headers=False`, para que esta regla sea la única; ver la decisión 23.
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
    - Los ayudantes del navegador (`api-navegador.ts` en las dos apps, y `api-onboarding.ts`,
      `api-listas.ts` y `api-catalogo.ts` en la consola) arman el mensaje con la espera si el
      cuerpo no lo trae, con la misma función pura (`conEspera`, en `espera.ts`).
    - `sondear` deja de sondear con un 429, y la pantalla de espera muestra el mensaje y un botón
      para volver a consultar: sin él, la pantalla se quedaría quieta sin decir nada.
20. **Las pruebas de integración** llevan el marcador `redis`, toman la URL de
    `TUKIT_PRUEBAS_REDIS_URL` (por omisión `redis://localhost:6379/15`), se saltan sin Redis salvo
    con `TUKIT_PRUEBAS_REDIS_OBLIGATORIO=1`, usan un prefijo por corrida y borran sus claves al
    terminar con `SCAN` y `DEL`, que solo usan las pruebas. Corren con `make prueba-redis`;
    `make prueba` las deja fuera. Los `conftest.py` de los servicios borran `REDIS_URL`, para que
    una variable exportada en la terminal no meta Redis en las pruebas unitarias. Las pruebas de
    los servicios leen lo que quedó en Redis con `lo_guardado` (valor y vencimiento por clave), de
    `pruebas_redis.py`, y no importan `redis`: así la frontera nueva no tiene excepciones.
21. **El compose.** Redis entra también al perfil `api`, sin persistencia y con un tope de memoria
    que desaloja lo menos usado (`--maxmemory 256mb --maxmemory-policy allkeys-lru --save ""`).
    Gateway, catálogo e inteligencia reciben `REDIS_URL` y lo esperan arrancado, sin exigirlo
    (`required: false`). El gateway confía también en la red de Docker (`172.16.0.0/12`), porque
    la web le llega desde fuera del compose.
22. **CI.** Un trabajo `redis` nuevo, con `redis:7` como servicio, instala las dependencias de
    `colas` más `redis`, comprueba que Redis responde con `python -m tukit_comun.cache`, corre las
    pruebas unitarias del cliente común (`test_cache.py`, que ningún trabajo corría) y las marcadas
    con `redis`, con `TUKIT_PRUEBAS_REDIS_OBLIGATORIO=1`. Los demás trabajos no cambian: sin el
    paquete, las pruebas marcadas se saltan solas. Las de `colas` y no las de `pruebas`, porque
    recoger `libs` importa `test_bucle_resiliente.py`, que importa `aiormq` (llega con `aio-pika`):
    la primera corrida de CI se cayó ahí, al recoger.
23. **uvicorn no lee `X-Forwarded-For` en el gateway.** La prueba de punta a punta lo encontró: con
    `TUKIT_PROXIES_CONFIANZA=192.0.2.1` y 5 por IP, seis peticiones desde la máquina local con
    seis `X-Forwarded-For` distintos dieron seis 200. uvicorn trae `proxy_headers` encendido y
    confía en `127.0.0.1` (`FORWARDED_ALLOW_IPS`), así que reescribía la dirección de la conexión
    con la cabecera antes del límite. Con la lista por omisión daba la misma IP, y por eso las
    pruebas con `ASGITransport` no lo veían. `tukit_gateway.api.main` lanza uvicorn con
    `proxy_headers=False`, y una prueba arma la pila de uvicorn con los argumentos de `main` y
    comprueba el 429. Solo cambia de dónde sale la IP del límite: nada más en el gateway lee la
    dirección del cliente, ni el esquema.

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
- [x] `tukit-contrato`: `cabeceras` en `ClienteApi`, `X-Forwarded-For` desde `servidor.ts` y
      `reintentar_en_segundos` en el 429.
- [x] La web y la consola: `Retry-After` en `respuestaDeError`, el mensaje con la espera en los
      ayudantes del navegador y `sondear` sin reintentar un 429.

### 5. Infraestructura y CI

- [x] `infra/docker-compose.yml`: Redis con los servicios que lo usan y su `REDIS_URL`.
- [x] `.env.ejemplo`: `REDIS_URL` y las variables nuevas, con su comentario.
- [x] `Makefile`: `arriba` con `CON_REDIS`, `abajo` y `prueba-redis`.
- [x] `ci.yml`: el trabajo `redis` con `redis:7`; los demás no cambian.
- [x] Fronteras: solo `tukit_comun` importa `redis`. Sus pruebas, en verde.

### 6. Documentación

- [x] ADR 0047, su fila en el índice y el rango de `docs/README.md` a «0027 a 0047».
- [x] `CONTRATO_API.md` a la 1.11, con «Qué cambió en 1.11», el 429 en el §11.1 y Redis en el §8.
- [x] `REVISION_ARQUITECTURA.md` y lo demás que describa Redis (el `README.md` de la raíz).

### 7. Verificación y PR

- [x] `make lint`, `make prueba`, `make prueba-colas`, `make prueba-redis`, `npm run lint` y
      `npm run typecheck`, en verde.
- [x] Punta a punta con `make arriba` (`env -u GEMINI_API_KEY`) contra Redis y RabbitMQ locales:
      el límite con `curl` y con dos gateways; la lectura y los vectores como se dice arriba.
- [x] Push de la rama y PR con base `feature/colas-rabbitmq`; CI en verde.

### 8. Cierre

- [x] Todas las casillas y la sección «Resultado».

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
10. `gateway: la puerta es la unica que lee X-Forwarded-For`, lo que encontró la prueba de punta a
    punta (decisión 23)
11. `docs: la verificacion del plan de Redis, en verde`
12. `ci: el trabajo de Redis instala aio-pika para recoger las pruebas de libs`, lo que encontró la
    primera corrida de CI (decisión 22)
13. `docs: resultado del plan de Redis`

Si una tarea pide partir o juntar commits, el orden se mantiene.

## Reservado a Juan

- Hacer Redis obligatorio. Este plan lo deja opcional en todo.
- Guardar en Redis algo que sea la única copia. Este plan solo guarda lo que se puede recalcular y
  contadores que se pueden perder.
- Tocar el flujo de pagos. Las rutas de órdenes y pagos quedan en el nivel general; decidir si
  `POST /v1/ordenes` (que reserva inventario) merece el nivel estricto.
- Los números del límite. Los de la decisión 16 no frenan a una familia normal; si la tesis o el
  banco de QA piden otros, se cambian por entorno.

## Resultado

### Qué cambió

- **`tukit_comun`:**
  - dos módulos nuevos: `cache` (el cliente, sus dos motores, `cliente_redis()`, `responde` y
    `python -m tukit_comun.cache`) y `pruebas_redis` (el doble y lo que usan las pruebas de
    integración);
  - `metricas` gana los aciertos, los fallos y las degradaciones por uso, y los rechazos del
    límite por nivel;
  - `crear_app` cierra el cliente al apagar;
  - `redis>=8.1.0`, en su `pyproject.toml` y en `uv.lock`.
- **Inteligencia:** `cache_lecturas`. `_percibir_onboarding` pasa a `async`, con la caché, y sus
  dos rutas la esperan. `gemini.modelo()` da el modelo efectivo.
- **Catálogo:** `cache_vectores`. `calcular_vectores` pasa a `async`, con la caché, y la esperan
  la consulta, la ruta de emparejamiento y el ensayo `bench_laya`. `embeddings.modelo_de` da el
  modelo efectivo.
- **Gateway:** `limite.py`, y `reenviar` limita antes de reenviar. `main` lanza uvicorn sin
  `proxy_headers`.
- **Identidad, comercio, operación e ingesta:** nada.
- **`tukit-contrato`:** `espera.ts`, `cabeceras` en `ClienteApi`, el `X-Forwarded-For` desde
  `servidor.ts` y la espera de un 429 en `ErrorTukit`.
- **Web:** `respuestaDeError` con `Retry-After`, el mensaje con la espera en `api-navegador.ts` y
  la pantalla de espera, que deja de sondear y ofrece volver a consultar.
- **Consola:** `respuestaDeError` y sus cuatro ayudantes del navegador.
- **Infraestructura y CI:**
  - el compose;
  - en el `Makefile`: `arriba` con `CON_REDIS`, `abajo` y `prueba-redis`;
  - `.env.ejemplo` y el marcador `redis` en `pyproject.toml`;
  - el trabajo «Cache y limite contra Redis».
- **Fronteras:** la regla 6.
- **Documentación:** ADR 0047, contrato 1.11, revisión de arquitectura y `README.md`.

Son 57 archivos, 18 de ellos nuevos. Sin `REDIS_URL`, la caché calcula como antes. Hay dos cambios
de comportamiento, y los dos tocan solo el límite:

- El límite cuenta en la memoria de cada gateway, como pide la decisión 3.
- uvicorn ya no reescribe la dirección del cliente con `X-Forwarded-For`, porque una prueba
  demostró que eso dejaba pasar IP inventadas (decisión 23). Solo lo nota el límite, y el
  registro de acceso de uvicorn, que ahora muestra la dirección de la conexión.

### Cómo se probó

| Pruebas | Antes | Después |
|---|---|---|
| Fronteras | 72, y 1 saltada | 75, y la misma saltada |
| Suite (`make prueba`) | 2.042 | 2.179, en unos 21 s |
| Integración con RabbitMQ (`make prueba-colas`) | 6 de 6 | 6 de 6, en 77 s |
| Integración con Redis (`make prueba-redis`) | no había | 11 de 11, en 2 s contra el 8.10 local |
| `tukit-contrato` (`node --test`) | 36 | 44 |
| Web (`node --test`) | 30 | 30 |

`make lint`, `make tipos`, `npm run lint` y `npm run typecheck` quedaron en verde.

**De dónde salen las pruebas nuevas:**

- **Suite (137):** 30 del cliente común (`test_cache.py`), 18 de la lectura guardada, 19 de los
  vectores y 70 del límite.
- **Fronteras (3):** la regla 6 y dos de activación.
- **Redis (11):** 8 del cliente común y una por servicio: dos subidas del mismo PDF a la app de
  inteligencia, dos listas a la de catálogo con el embeder falso y dos limitadores que comparten
  el contador.
- **`tukit-contrato` (8):** `espera.test.ts`.

**De punta a punta.** Se corrió con los procesos de `make arriba`, arrancados con
`env -u GEMINI_API_KEY`, y tres gateways más. Usó cinco bases `tukit_rds_*`, un vhost propio y la
base 15 de Redis, y todo se borró al terminar.

| Caso | Resultado |
|---|---|
| 1.205 `GET` desde una IP | 1.200 × 200 y 5 × 429 en 14 s, con `Retry-After: 47`. A esa IP le siguen respondiendo `/v1/servicios` y `/salud`, y otra IP pasa |
| 61 `POST /v1/sesiones` desde una IP | 60 × 401 y el 429, con `Retry-After: 599` y «10 minutos». La misma IP sigue teniendo cupo en `/v1/registro` |
| `POST /v1/trabajos` con un token desde 31 IP | 30 × 400 y el 429 |
| `POST /v1/trabajos` con un token nuevo en cada petición desde una IP | 60 × 400 y el 429 |
| Dos gateways, alternando | 30 + 30 × 401 y el 429 en la siguiente. El contador compartido queda en 61 |
| Seis `X-Forwarded-For` distintos con `TUKIT_PROXIES_CONFIANZA=192.0.2.1` y 5 por IP | Seis 200: uvicorn leía la cabecera por su lado (decisión 23). Con el arreglo, 5 × 200 y el 429 |
| Gateway con `REDIS_URL` a un puerto sin nada | 60 × 401 y el 429 contado en memoria, un WARNING y ningún 500. Otra IP pasa |
| 61 `POST /api/sesion` a `next dev` con una IP en `X-Forwarded-For` | 60 × 401 y el 429, con su `Retry-After` y el cuerpo del gateway. Otra IP pasa. La clave de esa IP cuenta 61, y la de Next.js (`127.0.0.1`) no existe |
| Las claves de Redis | Ninguna lleva un token, un correo o una IP en claro. El registro del 429 dice el nivel, la ruta y el tipo |

**Lo que no se pudo correr de punta a punta.** Sin la llave, `make arriba` no tiene Gemini ni
embeder, y usar los dobles desde la API pediría cambiar código de producción. Por eso la lectura
guardada y los vectores se probaron con las apps contra el Redis local, en las pruebas de
integración de arriba.

**Redis lleno.** Se probó contra una instancia propia de 2 MB, en otro puerto y con
`noeviction`, que se borró al terminar. Las escrituras dan `OutOfMemoryError`. El cliente abre un
episodio con un WARNING, el límite cuenta en memoria y nada se cae. Mientras dura el episodio
tampoco se lee lo guardado.

**CI.** En la primera corrida falló el trabajo de Redis, al recoger. `test_bucle_resiliente.py`
importa `aiormq`, que solo instalaba el trabajo de las colas. El trabajo de Redis ahora instala
también `aio-pika` (decisión 22). Con eso pasan los 13 trabajos:

- el de Redis corre las 30 pruebas del cliente común y las 11 de integración contra `redis:7`, en
  7 s;
- el del gateway corre 140 y salta 2: la de Redis, que no tiene el paquete, y la que arma la pila
  de uvicorn, que no tiene uvicorn. La que comprueba `proxy_headers=False` sí corre.

### Escenarios de caos de Redis para el banco de QA

1. **Caído desde el arranque.** Los procesos arrancan con `REDIS_URL` y cada uno deja un WARNING.
   La subida lee con el doble, el emparejamiento pide todos los vectores y el límite cuenta en
   memoria, sin ningún 500.
2. **Caído en mitad del tráfico.** Se apaga Redis con carga. Solo la primera petición de cada
   episodio debe pagar la espera de 250 ms, y las de los 5 s siguientes no le preguntan a Redis.
   Debe quedar un WARNING por episodio y proceso, y un INFO al volver. El contador en memoria
   empieza de cero, así que hay que medir cuánto deja pasar a un script que ya iba en el tope.
3. **Lento.** Con una latencia mayor que 250 ms (`CLIENT PAUSE` en una instancia propia, o un
   proxy con latencia), cada operación se rinde a los 250 ms y abre un episodio. Con una latencia
   menor nada se degrada, pero cada petición la paga. Hay que medir el p95 de la subida y del
   emparejamiento con 100, 200 y 400 ms.
4. **Lleno, con `noeviction`.** Es la política por omisión de Redis y la del local. Las escrituras
   fallan y el cliente degrada, como se probó arriba. Hay que medir cuántas lecturas de más le
   pide al doble de Gemini un Redis lleno, porque durante cada episodio tampoco se lee lo
   guardado.
5. **Lleno, con `allkeys-lru`.** Es la política del compose. Redis desaloja lo menos usado, y eso
   puede incluir un contador del límite. Hay que llenarlo de vectores mientras un script empuja
   contra el límite, y medir si el script consigue más que el tope.
6. **Reiniciado con la caché vacía.** Sin persistencia, un reinicio borra las lecturas, los
   vectores y los contadores.
   - La primera subida de cada lista vuelve a leer, y el primer emparejamiento pide todos sus
     vectores. Hay que medir las llamadas al doble y lo que tarda en volver la tasa de aciertos.
   - Los contadores vuelven a cero, como en el escenario 2.
7. **Un gateway sin Redis.** Dos gateways, uno con Redis y otro sin él: el segundo cuenta por su
   lado y el tope real sube. Hay que medirlo con un script repartido entre los dos.
8. **Un valor corrupto.** Basura en una clave `tukit:percepcion:*` o `tukit:vector:*` cuenta como
   «no está», se recalcula y se sobrescribe. Lo cubren pruebas unitarias; el banco lo repite con
   un Redis de verdad.
9. **Un contador sin vencimiento.** Un `PERSIST` sobre un contador: el siguiente conteo le devuelve
   la ventana. Lo cubre una prueba de integración.
10. **Una URL o una credencial mala.** Un `REDIS_URL` con otra contraseña, o con un host que no
    resuelve, se comporta como caído. Hay que comprobar que no deja un registro por petición.
11. **Las dos versiones.** La batería, contra `redis:7` (el compose y CI) y contra 8.x (el local).
12. **Muchas familias detrás de una IP.** Se simula la sala de cómputo de un colegio para medir si
    los 60 por IP del nivel estricto alcanzan.

### Riesgos abiertos

- **La ventana fija deja pasar hasta el doble del tope** en el cambio de ventana. Las peticiones
  rechazadas siguen sumando al contador (llegó a 62 con un tope de 60), pero no alargan la
  ventana.
- **Sin Redis, cada gateway cuenta por su lado,** y un episodio empieza el contador en memoria de
  cero.
- **`allkeys-lru` puede desalojar un contador,** y un reinicio los borra todos.
- **Si Next.js queda expuesto sin un proxy delante, la IP se puede falsear,** porque Next.js deja
  pasar el `X-Forwarded-For` del cliente.
- **La confianza del compose en `172.16.0.0/12` está revisada a ojo,** y el compose no se levantó
  con Docker. Si Docker presenta la conexión de la web desde otra red, todas las familias cuentan
  como una sola IP. Al levantarlo, el registro del 429 y las claves lo muestran.
- **La versión de la percepción mira tres archivos, pypdfium2 y el modelo.** Un cambio en otro
  módulo que esos importen, o en el SDK de Gemini, no la mueve.
- **Un proveedor que cambie un modelo sin cambiarle el nombre** daría vectores viejos hasta 24
  horas.
- **Un embeder que devuelve otro número de vectores** cuenta como un fallo del proveedor: no se
  guarda nada y la tanda baja a léxico.
- **Si una lista trae escrito el nombre de un niño y el modelo lo lee como renglón,** queda 30 días
  en el valor guardado.
- **El ensayo `bench_laya` corre `calcular_vectores` con un `asyncio.run` por lista.** Con
  `REDIS_URL`, la conexión queda atada al primer bucle, y las listas siguientes degradan a
  calcular sin caché. Hoy el ensayo corre sin la URL.
- **`next` no es dependencia par de `@tukit/contrato`,** aunque `servidor.ts` importa
  `next/headers`.
- **Ningún trabajo de CI corre npm.** El lint, los tipos y las pruebas de TypeScript solo se
  corren a mano.
- **Una página del servidor que recibe un 429 degrada por sección,** como con cualquier fallo del
  backend.
- **La prueba con la pila de uvicorn no corre en CI,** que no instala uvicorn. Corre en
  `make prueba`.
- **`make arriba REDIS_URL=...` también le pasa la URL a identidad,** que no la usa.

### Para Juan

- **Lo reservado sigue sin hacer:**
  - Redis no es obligatorio: sin él, todo funciona.
  - Nada de lo que guarda es la única copia.
  - El flujo de pagos no cambia. Las rutas de órdenes y pagos quedan en el nivel general, y
    decidir si `POST /v1/ordenes` pasa al estricto es tuyo.
  - Los números no frenan a una familia normal y se cambian por entorno. Si 60 por IP en el
    estricto alcanzan para un colegio es el escenario 12.
- **Dos cambios sin `REDIS_URL`, los dos en el límite:** el conteo en memoria (decisión 3) y
  uvicorn sin `proxy_headers` (decisión 23).
- **No se instaló nada.** Falta Docker para levantar el compose.
- **El PR #3 va apilado sobre el #2.** Cuando el #2 se una, se reapunta.
