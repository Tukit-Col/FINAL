# Las colas pasan a RabbitMQ, con la base como respaldo

- **Estado:** en curso. Cada casilla se marca cuando su tarea queda en verde.
- **Origen:** `PROMPT_RABBITMQ.md` (en `~/Desktop/TUKITDOC/`), que es la fuente de verdad.
- **Rama:** `feature/colas-rabbitmq`, sobre `integracion/ramas-octubre` (`77bb105`). PR apilado
  encima del PR #1.
- **Alcance:** las bandejas de salida y `trabajo_pipeline`. Quedan fuera el banco de QA, los
  diagramas de Visual Paradigm, la documentación de la tesis, `main` e `integracion/ramas-octubre`.

## Contexto, comprobado en el código

Lo que el prompt describe se confirma, con estas precisiones:

- **El repartidor lee dos cosas ajenas, no una.** Además de las bandejas de Comercio e
  Inteligencia, para un `kits_publicados` lee `trabajo_pipeline.usuario_id` en la base de
  Inteligencia (`_usuario_del_trabajo`), porque la carga del evento no trae el destinatario. Sin
  leer bases ajenas, la carga tiene que traerlo: `emitir_evento` le agrega `usuario_id`.
- **`BrokerSink` publica después de consumir, no en lugar de consumir.** El repartidor drena la
  bandeja, avisa y, si hay `RABBITMQ_URL`, publica la carga a `tukit.eventos`. El cuerpo es solo
  la carga: no lleva el origen ni el id del evento, así que un consumidor no podría deduplicar.
- **El sondeador de listas no es idempotente.** Un `lista_verificada` repetido crea otro trabajo
  y otro kit. Hoy tampoco lo es del todo: si el proceso cae en mitad de `procesar`, la transacción
  de la bandeja de Catálogo vuelve atrás y la pasada siguiente crea un segundo trabajo. El
  `lista_aprobada` sí lo es: compara la versión con la del canónico vigente.
- **El sondeador de colegios sí es idempotente por naturaleza.** Crea el colegio si no existe,
  completa solo los campos vacíos y matricula al hijo que esperaba con una operación que no
  duplica. Un evento repetido deja la base igual.
- **Hay dos puntos que encolan un trabajo para el trabajador:** `trabajos.crear` sin `en_proceso`
  (lo que llama `POST /v1/trabajos`) y `trabajos.lanzar` cuando el trabajo pasa a `encolado` desde
  `fallido` (reintentar) o desde `espera_revision` (devolver). Los demás `crear` (preview,
  sondeador, canónicos) nacen `procesando` y se procesan en el acto.
- **`encolado → cancelado` es una transición legal** (`modelos/base.py`), así que un trabajo se
  puede cancelar antes de que el trabajador lo tome.
- **El compose y `.env.ejemplo` no usan las mismas credenciales.** El compose crea el usuario
  `tukit` y `.env.ejemplo` apunta a `guest`. La imagen oficial deja entrar a `guest` desde fuera
  del contenedor, así que el compose pasa a `guest`, como `.env.ejemplo`, CI y el RabbitMQ local.
- **`make arriba` no usa el compose.** Lanza los procesos con `nohup` contra el Postgres que haya
  (contenedor o local). Por eso RabbitMQ entra a `make arriba` como la URL que exporta a los
  procesos, más una comprobación de que el broker responde.
- **CI no tiene `aio-pika` en las pruebas por servicio** y no corre las pruebas de
  `libs/py/tukit_comun/tests`. El código nuevo importa `aio_pika` dentro de las funciones que
  hablan con el broker, y las pruebas con dobles no lo necesitan.
- **El `Makefile` no lee `.env`.** `RABBITMQ_URL` solo llega a un proceso si está en el entorno,
  así que `make prueba` corre sin broker salvo que quien la lance la tenga exportada. Las pruebas
  que dependen del modo la borran con `monkeypatch`.

## Decisiones

Las ocho del prompt, sin cambios:

1. Las `bandeja_salida` se quedan. Cada productor (Catálogo, Comercio, Inteligencia) publica la
   suya con confirmación del publicador, y marca el evento publicado solo tras la confirmación.
2. Cada consumidor escucha su cola durable, atada al exchange por routing key, y confirma el
   mensaje después de procesarlo y guardarlo. Con RabbitMQ ningún consumidor lee una base ajena.
3. Entrega al menos una vez. Operación ya deduplica (ADR 0042). Identidad es idempotente por
   naturaleza. Inteligencia guarda qué eventos procesó, por origen e id.
4. Un mensaje que falla siempre va a una cola de descartados tras un número acotado de intentos.
5. `trabajo_pipeline` sigue siendo la tabla. Crearlo escribe su aviso en la bandeja de
   Inteligencia en la misma transacción; el trabajador reclama la fila y mantiene un barrido de
   los pendientes viejos.
6. Sin `RABBITMQ_URL`, todo como hoy. Con ella, el camino es RabbitMQ.
7. El barredor no cambia.
8. La reconexión usa `bucle_resiliente` y `connect_robust`.

Y estas, tomadas al leer el código:

9. **El sobre del mensaje.** El cuerpo es un JSON con `evento_id`, `origen`, `tipo`,
   `agregado_tipo`, `agregado_id`, `carga` y `correlacion_id`. Las propiedades AMQP repiten lo que
   sirve para mirar la cola sin abrir el cuerpo: `message_id` = `<origen>:<id>`, `type` = tipo,
   `app_id` = origen, `correlation_id`, entrega persistente. El consumidor arma con el sobre un
   `Evento` que se parece a una fila de bandeja (`id`, `tipo`, `agregado_tipo`, `agregado_id`,
   `carga`, `intentos`), para que los manejadores de hoy sirvan en los dos modos.
10. **La topología vive en un solo lugar** (`tukit_comun.topologia`): el exchange topic durable
    `tukit.eventos` y, por consumidor, tres colas clásicas durables. La principal manda lo que
    rechaza a `<cola>.descartados`. Los reintentos esperan en `<cola>.reintentos`, que tiene un
    TTL y devuelve el mensaje a la principal cuando vence. Las colas declaran
    `x-queue-type: classic` de forma explícita, para que un 4.x con otro tipo por omisión no
    cambie la semántica. Quien publica y quien consume declaran la misma topología, así que da
    igual cuál arranca primero.

    | Cola | Routing keys | Consumidor |
    |---|---|---|
    | `operacion.avisos` | `kits_publicados`, `pedido_pagado`, `incidencia`, `pedido_despachado`, `pedido_en_reparto`, `pedido_entregado` | repartidor |
    | `identidad.colegios` | `colegio_verificado` | sondeador de colegios |
    | `inteligencia.listas` | `lista_verificada`, `lista_aprobada` | sondeador de listas |
    | `inteligencia.trabajos` | `trabajo_encolado` | trabajador |

    Una prueba fija que las claves de `operacion.avisos` son las plantillas del repartidor.
11. **El intento se cuenta en una cabecera** (`tukit-intentos`) que el consumidor sube al
    reenviar a reintentos. Al llegar al tope (5 por omisión), el mensaje se rechaza sin
    reencolar y RabbitMQ lo deja en `descartados`, con un registro de error. Una caída de
    Postgres o del broker no gasta intentos: el mensaje vuelve a la cola y el proceso espera con
    `bucle_resiliente`.
12. **Los publicadores son procesos aparte**, uno por servicio productor
    (`tukit_catalogo.publicador`, `tukit_comercio.publicador`, `tukit_inteligencia.publicador`),
    sobre un núcleo común. Sondean su propia bandeja (cada segundo, por omisión): la bandeja es la
    garantía de la decisión 1, y leer la base propia no cruza ninguna frontera. Sin
    `RABBITMQ_URL`, el publicador se niega a arrancar y lo dice.
13. **El modo lo decide `RABBITMQ_URL`** en cada proceso, como `sink_desde_entorno` hoy. Los
    consumidores sin URL siguen exactamente el código de hoy (la ruta de sondeo no se toca). Con
    URL consumen su cola y no abren motores a bases ajenas.
14. **`trabajo_encolado` solo se escribe con `RABBITMQ_URL`.** Sin broker nadie lo lee, y
    escribirlo cambiaría lo que hay en la bandeja de Inteligencia sin broker. Se escribe en
    `trabajos.crear` (sin `en_proceso`) y en `trabajos.lanzar` cuando el trabajo pasa a
    `encolado`, en la misma transacción. Si el aviso falta, el barrido lo cubre.
15. **El trabajador reclama la fila del aviso** con un `UPDATE ... WHERE id = :id AND estado =
    'encolado'`. Si no la reclama (otro la tomó, se canceló, ya terminó), el aviso se da por
    atendido. El barrido, con broker, toma solo los `encolado` que llevan más de un minuto sin
    moverse, cada minuto, y los colgados cada doce vueltas como hoy. Las importaciones diferidas
    (ADR 0040) siguen igual.
16. **Inteligencia deduplica con la tabla `evento_procesado`** (origen, evento_id, procesado_en),
    con su migración sobre la cabeza `6a2f8c4e1d57`. Para `lista_verificada`, la marca entra en la
    misma transacción que crea el trabajo: un repetido no puede crear un segundo trabajo aunque el
    proceso caiga a mitad.
17. **El repartidor, con broker, saca el destinatario de la carga** también para
    `kits_publicados`. Un evento viejo sin `usuario_id` va a reintentos y termina en descartados,
    visible. Sin broker sigue leyendo `trabajo_pipeline`.
18. **`BrokerSink` se queda** pero deja de tener uso: sin broker devuelve `None` y con broker el
    repartidor ya no drena. Quitarlo es otra limpieza.

## Tareas

### 0. Plan

- [x] Leer el código y confirmar o corregir el contexto.
- [x] Escribir este plan y hacer su commit.

### 1. Base común en `tukit_comun`

- [x] `topologia.py`: exchange, colas, reintentos y descartados; declaración idempotente.
- [x] `mensajes.py`: el sobre (de fila a mensaje y de mensaje a `Evento`).
- [x] `publicador.py`: drena la bandeja propia con SKIP LOCKED, publica con confirmación, marca
      tras confirmar, guarda lo confirmado si algo falla a mitad, y corre sobre `bucle_resiliente`.
- [x] `consumidor.py`: prefetch, confirmación y rechazo, reintentos acotados, descartados,
      deduplicación por origen e id (registro en memoria y en tabla), correlación, modo «hasta
      vaciar» para una pasada y modo continuo.
- [x] `resiliencia.py`: las caídas de conexión de aiormq cuentan como transitorias.
- [x] Pruebas unitarias con dobles, sin broker.
- [x] Pruebas de integración contra el RabbitMQ local, con el marcador `rabbitmq`, que se saltan
      si no hay broker y usan nombres propios que borran al terminar. Corren con
      `make prueba-colas`; `make prueba` las deja fuera.

### 2. Productores

- [ ] `tukit_catalogo.publicador`, `tukit_comercio.publicador` y `tukit_inteligencia.publicador`.
- [ ] Objetivos `publicador-catalogo`, `publicador-comercio` y `publicador-inteligencia` en el
      `Makefile`.
- [ ] `kits_publicados` lleva `usuario_id` en la carga.
- [ ] Pruebas por servicio.

### 3. Consumidores

- [ ] Repartidor: consume `operacion.avisos` con broker; sin él, sondea como hoy.
- [ ] Sondeador de colegios: consume `identidad.colegios`; prueba de un evento repetido.
- [ ] Sondeador de listas: consume `inteligencia.listas`; tabla `evento_procesado`, su migración y
      su reversa; prueba de un evento repetido.
- [ ] Pruebas de que con broker ninguno abre un motor a una base ajena.

### 4. Trabajos del pipeline

- [ ] `trabajo_encolado` en `crear` y `lanzar`, en la misma transacción, solo con broker.
- [ ] El trabajador consume `inteligencia.trabajos` y reclama la fila; el barrido sigue.
- [ ] Pruebas: un aviso que llega dos veces, un aviso perdido que recoge el barrido y una
      cancelación antes de procesar.

### 5. Infraestructura y CI

- [ ] Compose: RabbitMQ fuera del perfil `infra`, con `guest`, y `RABBITMQ_URL` en el entorno de
      los servicios.
- [ ] `Makefile`: `make arriba` exporta `RABBITMQ_URL`, comprueba el broker, lanza los
      publicadores y cae al sondeo si el broker no responde; `abajo` los detiene.
- [ ] `.env.ejemplo` al día.
- [ ] `ci.yml`: un trabajo nuevo con `rabbitmq:3.13-management-alpine` que corre las pruebas de
      integración de las colas. Los demás trabajos no cambian.
- [ ] Fronteras: el manifiesto declara las lecturas cruzadas como respaldo sin broker, y una
      prueba exige que cada lectura cruzada del código esté declarada así.

### 6. Documentación

- [ ] ADR 0046, su fila en el índice y el rango «0027 a 0046» en `docs/README.md`.
- [ ] `CONTRATO_API.md` 1.10: el viaje de los eventos (§10) y «Qué cambió en 1.10».
- [ ] `REVISION_ARQUITECTURA.md` y lo demás que describa las colas.

### 7. Verificación y PR

- [ ] `make lint` y `make prueba` en verde, sin pruebas nuevas saltadas.
- [ ] Pruebas de integración contra el RabbitMQ local en verde.
- [ ] Viaje de punta a punta de un evento contra el RabbitMQ local.
- [ ] Push y PR con base `integracion/ramas-octubre`; CI en verde.

### 8. Cierre

- [ ] Todas las casillas y la sección «Resultado».

## Orden de commits

1. `docs: plan de las colas en RabbitMQ`
2. `comun: topologia y sobre de los mensajes de las colas`
3. `comun: publicador de bandeja con confirmacion`
4. `comun: consumidor con reintentos, descartados y deduplicacion`
5. `comun: pruebas de integracion de las colas contra RabbitMQ`
6. `productores: catalogo, comercio e inteligencia publican su bandeja`
7. `operacion: el repartidor consume su cola con RabbitMQ`
8. `identidad: el sondeador de colegios consume su cola con RabbitMQ`
9. `inteligencia: el sondeador de listas consume su cola y no repite eventos`
10. `inteligencia: el trabajador recibe el aviso de cada trabajo por RabbitMQ`
11. `infra: RabbitMQ en el compose, en make arriba y en CI`
12. `fronteras: las lecturas cruzadas quedan como respaldo sin broker`
13. `docs: ADR 0046, contrato 1.10 y revision de arquitectura`
14. `docs: resultado del plan de las colas`

Si una tarea pide partir o juntar commits, el orden se mantiene.

## Reservado a Juan

- Hacer RabbitMQ obligatorio y quitar el sondeo de respaldo.
- Cambiar la API HTTP pública. Este plan no la cambia.
- Tocar el flujo de pagos más allá de cómo viaja `pedido_pagado`. Este plan no lo toca.

## Resultado

Pendiente.
