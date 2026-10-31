# ADR 0047 — Redis guarda lo que se puede recalcular y cuenta el límite de tasa del gateway

- **Estado:** aceptada
- **Servicios tocados:** `libs/py/tukit_comun` (`cache`, `pruebas_redis`, `metricas`, `http`),
  `inteligencia` (`cache_lecturas`, `api`, `gemini`), `catalogo` (`cache_vectores`, `consulta`,
  `embeddings`), `gateway` (`limite`, `api`), `libs/ts/tukit-contrato` (`espera`, `cliente-http`,
  `servidor`), `apps/web` y `apps/admin`
- **Origen:** el plan `docs/diseno/planes/cache-redis.md`, en la rama `feature/cache-redis`.
  Aplica el ADR 0007 de la tesis (Redis solo como caché y límite de tasa) y convive con el 0046
  (RabbitMQ es el único broker).

## Contexto

**Leer una lista cuesta una llamada a Gemini por página, y se repetía.** `percibir()` renderiza el
PDF y lee cada página con el modelo. Las familias de un mismo colegio suben el mismo archivo, y
cada subida se volvía a leer entera, por las dos rutas que pasan por `_percibir_onboarding`: la
subida de la web y el onboarding de la consola.

**El vector de un renglón también se repetía.** `calcular_vectores` le pedía al proveedor, en cada
emparejamiento, el vector de textos que ya había calculado («2 cuadernos cuadriculados de 100
hojas»). El SAD pide una caché de vectores de consulta que, si Redis no responde, degrade a
calcular sin ella.

**Nada limitaba la tasa.** El gateway solo ruteaba y reenviaba. ESC-09 cortaba el tamaño (10 MB en
el navegador) y las páginas (40, antes del modelo), pero no cuántas subidas hacía una persona. Una
ruta como `POST /v1/listas/subir` es la más cara del sistema, y `POST /v1/sesiones` deriva una
clave en cada intento.

**Redis estaba en el compose y nadie lo usaba.** El contenedor vivía en el perfil `infra`, y
`REDIS_URL` estaba en `.env.ejemplo` sin que ningún servicio la leyera.

**La IP de la conexión no identifica a nadie.** La web le llega al gateway desde el servidor de
Next.js, así que contar por la IP de la conexión pondría a todas las familias en un solo contador.
Next.js 16 pone `X-Forwarded-For` solo si no viene (`??=`), con la dirección del socket.

## Decisión

1. **Redis solo guarda lo que se puede recalcular y contadores que se pueden perder.** Postgres
   sigue siendo la fuente de verdad y RabbitMQ el único broker. Ninguna orden, pago, sesión o
   permiso vive en Redis.
2. **Un cliente común, `tukit_comun.cache`.** Los servicios solo usan `cliente_redis()`, el cliente
   del proceso.
   - `ClienteRedis` envuelve un motor: `MotorRedis` (redis-py asíncrono) o `MotorEnMemoria` (un
     diccionario con vencimiento). Ofrece `leer`, `leer_varias`, `guardar`, `guardar_varias`,
     `contar` y `cerrar`.
   - Las claves llevan el prefijo `tukit:`.
   - Solo usa `GET`, `MGET`, `SET` con `EX` en una tubería y un script Lua con `INCR`, `EXPIRE` y
     `PTTL`, así que vale igual en Redis 7 (compose y CI) y 8 (Homebrew).
   - `redis` es dependencia de `tukit_comun` y se importa solo si hay `REDIS_URL`. Una frontera
     (regla 6) prohíbe importarlo fuera de `tukit_comun`.
3. **Si Redis falla, nada se cae.**
   - Cada operación espera como mucho 250 ms (`TUKIT_REDIS_ESPERA_MS`).
   - Un fallo o una espera vencida abren un episodio: durante 5 s el cliente no le pregunta a
     Redis, y después vuelve a probar.
   - El primer fallo del episodio deja un WARNING con el tipo de error y sin claves; la vuelta deja
     un INFO.
   - Mientras dura, `leer` da «no está», guardar no hace nada y `contar` cuenta en la memoria del
     proceso. Un Redis caído nunca da un 500.
   - Sin `REDIS_URL`, el cliente está en ese modo desde el principio, sin registrar nada. Con la URL
     pero sin el paquete, avisa una vez y sigue igual.
4. **La lectura aceptada de una lista se guarda** en `_percibir_onboarding`, que aprovechan las dos
   rutas.
   - Clave: `tukit:percepcion:<versión>:<SHA-256 del archivo>`. Dura 30 días
     (`TUKIT_CACHE_PERCEPCION_SEGUNDOS`): una lista vale un año lectivo, y un mes cubre la
     temporada de compras.
   - La versión son 16 caracteres del SHA-256 de los bytes de `paginas.py` (el render), `gemini.py`
     (el prompt, el esquema y la validación) y `percepcion.py` (las reglas), más la versión de
     pypdfium2 y el modelo efectivo de `GEMINI_MODELO`. Cualquier cambio en esas piezas, hasta un
     comentario, vuelve a leer: se prefiere una lectura de más a una vieja.
   - Valor: un JSON con los `grados`, las `paginas` y los `items` de la `Percepcion`, que es todo lo
     que trae una aceptada. No lleva el archivo, la cuenta, el correo ni el hijo, que viven en la
     ruta.
   - Solo se guardan las aceptadas. Un archivo vacío, ilegible o con demasiadas páginas se rechaza
     como antes, y no se guarda.
   - Un valor que no se puede leer cuenta como «no está».
   - El cruce con el catálogo y los precios se recalcula siempre, así que la reverificación de
     precio (ESC-10) no cambia.
5. **El vector de cada renglón se guarda** en `calcular_vectores`, que aprovechan el emparejamiento
   de la consulta y la ruta `POST /v1/catalogo/emparejar`.
   - Clave: `tukit:vector:<modelo>:<dimensión>:<SHA-256 del texto que va al proveedor>`. Dura 24 horas
     (`TUKIT_CACHE_VECTORES_SEGUNDOS`), el valor del SDD.
   - Valor: el vector en `float64` little-endian, así que el resultado con caché es idéntico al de
     sin caché. Un valor de otro largo cuenta como «no está».
   - Un lote lee todas sus claves con un `MGET` y le manda al proveedor solo las que faltan, en un
     lote y en orden. El resultado sale en el orden original.
   - Si el proveedor falla, no se guarda nada y la tanda entera baja a léxico, como promete el §8
     del contrato.
   - Solo se guarda con un modelo declarado (`embeddings.modelo_de`). Con el de Gemini es el de
     `GEMINI_MODELO_EMBEDDING`, si está definido, y no la constante del módulo.
6. **El gateway limita la tasa** antes de reenviar, en `tukit_gateway/limite.py`.

   | Nivel | Rutas | Ventana | Por token | Por IP |
   |---|---|---|---|---|
   | General | todo `/v1/*` | 60 s | 300 | 1.200 |
   | Estricto | cada ruta cara o sensible, por separado | 600 s | 30 | 60 |

   - Las estrictas son estas, con `POST`:
     - `/v1/listas/subir`;
     - `/v1/trabajos`, `/v1/trabajos/{id}/reintentar` y `/v1/trabajos/aplicar-canonico`;
     - `/v1/admin/onboarding` y `/v1/admin/onboarding/{id}/preview`;
     - `/v1/sesiones`, `/v1/cuenta` y `/v1/registro`;
     - `/v1/catalogo/emparejar`.

     Una estricta cuenta también en el general. Cada estricta tiene su cupo, así que los intentos
     de entrar no gastan el de las subidas.
   - Quedan fuera `/v1/servicios`, `/v1/webhooks/*` (Wompi reintenta y no es un cliente), las
     preflight `OPTIONS` y lo que no es `/v1/*` (`/salud`, `/health/*`). Una ruta desconocida sí
     cuenta: un escáner también gasta cupo.
   - Cada petición cuenta dos claves por nivel, y tienen que pasar las dos: la del token (`Bearer`),
     si hay, y la de la IP. Inventar un token en cada petición no da cupo, porque la IP sigue
     contando.
   - Clave: `tukit:limite:<nivel>:<ruta>:<token|ip>:<SHA-256>`. Ni el token ni la IP quedan en
     claro, y el registro del 429 dice el nivel, la ruta y el tipo, sin la huella.
   - El conteo es por ventana fija. Un script Lua hace, por cada clave, `INCR` y `PTTL`, y un
     `EXPIRE` si es la primera o si quedó sin vencimiento. Es una sola ida y vuelta por petición, y
     es atómico: dos gateways comparten el contador. Sin Redis, cuenta en la memoria del proceso.
   - Pasado un tope responde 429 con `Retry-After: N` y el cuerpo de los otros errores del gateway:
     `{"error": "demasiadas_peticiones", "mensaje": "...", "reintentar_en_segundos": N}`. N es lo que
     le falta a la clave pasada que más tarda, mínimo 1, y el mensaje lo dice en segundos o en
     minutos.
   - Todos los números se cambian por entorno (`TUKIT_LIMITE_GENERAL_VENTANA`, `..._TOKEN`, `..._IP`,
     y los tres `TUKIT_LIMITE_ESTRICTO_*`). Un `0` apaga el conteo.
7. **Los números no frenan a una familia y sí a un script.**
   - Una familia sube una lista por hijo, la corrige y vuelve a subirla unas pocas veces: 30 por ruta
     estricta en 10 minutos le sobran.
   - Una página de la web le hace pocas peticiones al gateway, y la pantalla de espera sondea cada
     1 a 8 s, menos de 60 por minuto. Las 300 por minuto del general son cinco por segundo
     sostenidas: una persona no llega, y un script sí, en segundos.
   - La IP tiene cuatro veces el cupo del token en el general, y el doble en el estricto, porque
     detrás de una IP puede haber muchas familias: la sala de cómputo de un colegio, el NAT de un
     operador móvil.
   - `arquitectura/humo.py` hace unas 25 peticiones, lejos del límite.
8. **La IP del cliente sale de `X-Forwarded-For` solo si la conexión viene de un proxy de
   confianza.**
   - Los proxies son `TUKIT_PROXIES_CONFIANZA`, IP o redes separadas por comas, y por omisión la
     máquina local (`127.0.0.1,::1`), donde corre la web.
   - Se recorre la cabecera de derecha a izquierda, y la IP es la primera que no es de confianza.
     Si todas lo son, es la de más a la izquierda.
   - Una entrada que no es una IP corta el recorrido, y se usa la última de confianza.
   - Si la conexión no viene de un proxy de confianza, la cabecera se ignora: la escribió el
     cliente.
   - Las IPv4 escritas como IPv6 (`::ffff:127.0.0.1`) se normalizan.
   - Esta regla es la única. El gateway lanza uvicorn sin `proxy_headers`: por omisión, uvicorn
     confía en `127.0.0.1` (`FORWARDED_ALLOW_IPS`) y reescribe la dirección de la conexión antes
     del límite, así que una lista que no confiara en la máquina local no serviría. Lo encontró la
     prueba de punta a punta, y lo fija una prueba con la pila que arma uvicorn.
9. **Next.js reenvía la IP y muestra el 429.**
   - El cliente de servidor de `tukit-contrato` reenvía el `X-Forwarded-For` de la petición entrante
     en sus dos `fetch`. Lo lee de `headers()`.
   - Los manejadores pasan el 429 con su `Retry-After`.
   - La web y la consola muestran el `mensaje` con la espera. Si el 429 llega sin cuerpo, lo arman
     del `Retry-After` con la misma función pura (`espera.ts`).
   - No reintentan solas. La pantalla de espera deja de sondear, dice que la solicitud sigue
     avanzando y ofrece un botón para volver a consultar.
10. **El modo lo decide `REDIS_URL`, en cada proceso.**
    - Catálogo, inteligencia y el gateway la leen.
    - `make arriba` la pasa si `python -m tukit_comun.cache` dice que Redis responde, como hace
      con `RABBITMQ_URL`. `make arriba REDIS_URL=` arranca sin ella.
    - En el compose, Redis entra también al perfil `api`, sin persistencia y con
      `--maxmemory 256mb --maxmemory-policy allkeys-lru`. Los tres servicios lo esperan arrancado,
      sin exigirlo.
11. **Se cuenta con las métricas de `tukit_comun`:**
    - `tukit.cache.aciertos` y `tukit.cache.fallos`, por `uso` (`percepcion` o `vector`);
    - `tukit.redis.degradaciones`, por `uso`, que también puede ser `limite`;
    - `tukit.limite.rechazos`, por `nivel`.

## Alternativas rechazadas

- **Guardar la respuesta entera de la subida, con el kit y los precios.** Saltaría la
  reverificación de precio (ESC-10) y guardaría datos de la cuenta. La lectura es la parte cara y
  la que no depende de quién sube.
- **Una versión de la percepción escrita a mano,** una constante que alguien sube cuando cambia el
  prompt. Se olvida, y una lectura vieja sobreviviría 30 días. La huella de los archivos no se
  olvida.
- **Guardar también los rechazos.** Un archivo ilegible hoy puede leerse con el modelo de mañana, y
  un rechazo cuesta menos que una lectura.
- **Contar solo por token, o solo por IP.** Solo por token, rotar tokens falsos esquiva el límite.
  Solo por IP, una familia que abusa frena a todo su colegio.
- **Contar por la IP de la conexión.** Todas las familias llegan desde el servidor de Next.js.
- **Validar el token en el gateway para contar por cuenta.** Sería una llamada a identidad por
  petición, y el gateway no valida tokens. Con la huella del token y el cupo de la IP basta.
- **Ventana deslizante o cubeta de fichas.** La deslizante exacta necesita un conjunto ordenado por
  clave y más memoria por petición. La cubeta necesita un Lua más largo y el reloj del servidor. La
  ventana fija deja pasar hasta el doble en el borde, y para frenar un script alcanza.
- **Limitar en Next.js.** La consola, la web y lo que entre de fuera pasan por el gateway, y Next.js
  no lo ve todo.
- **Fallar cerrado si Redis cae** (un 503 en vez de contar en memoria). Haría de Redis un requisito
  para atender, y eso es una decisión reservada.
- **`fakeredis` en las pruebas.** El motor en memoria ya hacía falta para degradar. Con el doble
  `RedisEnMemoria` (caído, lento y con registro de llamadas), las pruebas no suman una dependencia
  que imita a Redis.
- **`redis` como dependencia de cada servicio.** Repartiría la degradación y las esperas en tres
  sitios. Con un solo cliente, una frontera lo vigila.
- **Persistencia en Redis.** No guarda nada que valga la pena recuperar al reiniciar.

## Lo que queda abierto

- **La ventana fija deja pasar hasta el doble del tope** en el cambio de ventana.
- **Sin Redis, cada gateway cuenta por su lado.** Con N réplicas, el tope real es N veces el
  configurado. Cuando un episodio de degradación empieza, el contador en memoria arranca de cero.
- **Si Next.js queda expuesto sin un proxy delante, la IP se puede falsear.** El cliente escribe
  `X-Forwarded-For` y Next.js la deja pasar (`??=`). Con un proxy que agregue la IP real a la
  derecha, la regla da la real.
- **60 por IP en el nivel estricto** podrían no alcanzar si muchas familias suben sus listas desde
  la sala de un colegio en los mismos 10 minutos. Se cambia por entorno.
- **Las rutas de órdenes y pagos quedan en el nivel general.** `POST /v1/ordenes` reserva
  inventario; si merece el estricto es una decisión del flujo de pagos.
- **La versión de la percepción mira tres archivos, pypdfium2 y el modelo.** Un cambio en otro
  módulo que esos importen, o en el SDK de Gemini, no la mueve.
- **Si una lista trae escrito el nombre de un niño y el modelo lo lee como renglón,** queda en el
  valor guardado durante 30 días.
- **Un proveedor que cambie un modelo sin cambiarle el nombre** daría vectores viejos hasta 24
  horas.
- **Una página del servidor que recibe un 429 degrada por sección,** como con cualquier fallo del
  backend. Con los números por omisión una familia no llega ahí.
- **El bloque de Redis del compose no se ha levantado con Docker,** igual que el resto de los
  perfiles `api` e `infra`. CI sí usa `redis:7`.

## Consecuencias

- Módulos nuevos:
  - `tukit_comun.cache`, con `python -m tukit_comun.cache` para que `make arriba` y CI comprueben
    que Redis responde;
  - `tukit_comun.pruebas_redis`;
  - `tukit_inteligencia.cache_lecturas`;
  - `tukit_catalogo.cache_vectores`;
  - `tukit_gateway.limite`;
  - `espera.ts` en `tukit-contrato`.
- Cambios de firma: `_percibir_onboarding` y `calcular_vectores` pasan a `async`, y sus llamadas
  las esperan. El ensayo `bench_laya/generar_instancias.py` corre la segunda con `asyncio.run`.
- `redis>=8.1.0` entra a `tukit_comun`, en su `pyproject.toml` y en `uv.lock`.
- El contrato sube a 1.11: el 429 en el §11 y la caché en el §8.
- Infraestructura:
  - `make arriba` con `CON_REDIS`, y `make prueba-redis`;
  - Redis en el perfil `api` del compose;
  - un trabajo `redis` en CI, con `redis:7`, que corre además las pruebas unitarias del cliente
    común.
- Pruebas:
  - unitarias, con el doble y sin Redis: `test_cache.py`, `test_cache_lecturas.py`,
    `test_cache_vectores.py` y `test_limite.py`;
  - de integración, con el marcador `redis`, contra la base 15 y con un prefijo por corrida.
    `make prueba-redis` y el trabajo `redis` de CI las corren, y `make prueba` las deja fuera;
  - de fronteras: la regla 6 y sus pruebas de activación.
