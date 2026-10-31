# ADR 0046 — Los eventos y los trabajos viajan por RabbitMQ, y la base queda como respaldo

- **Estado:** aceptada
- **Servicios tocados:** `libs/py/tukit_comun` (`topologia`, `mensajes`, `publicador`,
  `consumidor`, `broker`), `catalogo`, `comercio` e `inteligencia` (publicadores), `operacion`
  (`repartidor`), `identidad` (`poller`), `inteligencia` (`poller`, `trabajador`, `trabajos`)
- **Origen:** el plan `docs/diseno/planes/colas-rabbitmq.md`, en la rama `feature/colas-rabbitmq`.
  Extiende el ADR 0022 (la bandeja alimenta el broker) y el 0024 (el trabajador durable).

## Contexto

**Las colas vivían en Postgres.** Cada servicio escribe sus eventos en su `bandeja_salida`, en la
misma transacción del cambio (ADR 0022). Tres procesos los sacaban de la base del productor con
`FOR UPDATE SKIP LOCKED`:

- el repartidor de operación, de las bandejas de comercio y de inteligencia. Para un
  `kits_publicados` leía además `trabajo_pipeline.usuario_id`, porque la carga no traía el
  destinatario;
- los sondeadores de colegios (identidad) y de listas (inteligencia), de la de catálogo.

El trabajador sondeaba `trabajo_pipeline` cada 5 s (ADR 0024).

**Eso tenía tres costos:**

1. **Tres procesos con un motor a la base de otro servicio,** la única excepción a «una base, un
   dueño». La regla 3 de las fronteras no la veía: `url_desde_entorno` deriva el nombre de la base
   dentro de la librería.
2. **Un evento tardaba hasta un intervalo de sondeo** en llegar, y cada consumidor nuevo sería otra
   lectura cruzada.
3. **`BrokerSink` publicaba a `tukit.eventos` y nadie consumía.** Publicaba después de drenar, sin
   el origen ni el id del evento, así que ningún consumidor podía deduplicar.

Además, el sondeador de listas no era idempotente: un `lista_verificada` repetido creaba otro
trabajo y otro kit.

RabbitMQ ya era el broker elegido (ADR 0007 y 0022) y ya estaba en el compose. Faltaban los
consumidores.

## Decisión

1. **La bandeja se queda; cambia quién la vacía.** Sigue siendo la garantía de que un evento
   guardado no se pierde.
   - Cada productor (catálogo, comercio e inteligencia) corre su publicador:
     `tukit_<servicio>.publicador`, sobre `tukit_comun.publicador`.
   - El publicador toma sus eventos con `SKIP LOCKED`, los publica con confirmación del publicador
     y marca cada uno publicado solo cuando el broker lo confirma.
   - Si una publicación falla a mitad, guarda lo ya confirmado y la vuelta siguiente sigue desde
     ahí.
   - Lee solo la base propia.
2. **El mensaje lleva un sobre.** Es un JSON con `evento_id`, `origen`, `tipo`, `agregado_tipo`,
   `agregado_id`, `carga` y `correlacion_id`.
   - El par `origen`, `evento_id` identifica el evento en todo el sistema; el `message_id` es
     `<origen>:<id>`.
   - El consumidor lo convierte en un `Evento` con la forma de una fila de bandeja, así que cada
     manejador es el mismo con broker y sin él.
3. **La topología vive en `tukit_comun.topologia`,** y la declaran los dos extremos, así que da
   igual quién arranca primero.
   - Un exchange topic durable, `tukit.eventos`, con el tipo como routing key.
   - Por consumidor, tres colas clásicas durables: la principal, `<cola>.reintentos` y
     `<cola>.descartados`. La de reintentos no tiene consumidor: su TTL de 10 s le devuelve el
     mensaje a la principal.
   - `x-queue-type: classic` va explícito, para que valga igual en 3.13 y en 4.x.

   | Cola | Tipos | Consumidor |
   |---|---|---|
   | `operacion.avisos` | `kits_publicados`, `pedido_pagado`, `incidencia`, `pedido_despachado`, `pedido_en_reparto`, `pedido_entregado` | repartidor |
   | `identidad.colegios` | `colegio_verificado` | sondeador de colegios |
   | `inteligencia.listas` | `lista_verificada`, `lista_aprobada` | sondeador de listas |
   | `inteligencia.trabajos` | `trabajo_encolado` | trabajador |

4. **Un consumidor común, `tukit_comun.consumidor`.** Cada proceso aporta solo su
   `manejar(evento)`.
   - El mensaje se confirma después de procesarlo y guardarlo.
   - `REINTENTAR`, o un error de programación, lo manda a reintentos con el intento en la cabecera
     `tukit-intentos`.
   - Al quinto intento va a descartados, con el motivo en `tukit-motivo` y un registro de error.
   - Un sobre ilegible va directo a descartados.
   - Una caída de Postgres o del broker no gasta intentos: el mensaje vuelve a la cola y el proceso
     espera con `bucle_resiliente` (ADR 0041), sobre `connect_robust`.
5. **Al menos una vez, con consumidores que toleran repetidos.**
   - Operación ya mira el evento en su `notificacion` (ADR 0042).
   - Identidad es idempotente por naturaleza: un colegio que ya existe solo completa los campos
     vacíos.
   - Inteligencia anota cada evento en `evento_procesado`, por origen e id. Para `lista_verificada`,
     la marca entra en la misma transacción que crea el trabajo, así que un repetido no arma un
     segundo kit aunque el proceso caiga a mitad.
6. **`kits_publicados` lleva `usuario_id` en la carga.** Con broker, el repartidor no lee
   `trabajo_pipeline`. El campo va en los dos modos, para que un evento escrito sin broker sirva si
   después se enciende.
7. **`trabajo_pipeline` sigue siendo la tabla y la cola de verdad.**
   - Con broker, `crear` (sin `en_proceso`) y `lanzar` (cuando el trabajo vuelve a `encolado`)
     escriben `trabajo_encolado` en la bandeja de Inteligencia, en la misma transacción.
   - El trabajador reclama la fila del aviso con un `UPDATE ... WHERE estado = 'encolado'`. Si no la
     reclama (otro la tomó, se canceló o ya terminó), el aviso queda atendido.
   - Un barrido corre al arrancar y una vez por minuto. Toma los `encolado` que llevan más de un
     minuto sin moverse y los colgados.
   - Atiende un aviso a la vez (`prefetch=1`).
8. **El modo lo decide `RABBITMQ_URL`, en cada proceso.**
   - Sin ella, todo sigue como antes: los consumidores sondean, `trabajo_encolado` no se escribe y
     el publicador se niega a arrancar.
   - Con ella, ningún consumidor abre un motor a una base ajena.
   - El manifiesto declara las tres lecturas cruzadas en `[[lecturas_cruzadas]]` con
     `modo = "sin_broker"`. La regla 3b de las fronteras exige que toda llamada a
     `url_desde_entorno` esté en un módulo declarado así, y que su `escuchar_cola` no llegue a
     ella.
9. **Lo encienden `make arriba` y el compose.**
   - `make arriba` pregunta si el broker responde (`python -m tukit_comun.broker`). Si responde,
     lanza los procesos con la URL y los tres publicadores. Si no, cae al sondeo y lo dice.
   - El compose levanta RabbitMQ sin perfil.
   - CI corre las pruebas de las colas en un trabajo propio, contra
     `rabbitmq:3.13-management-alpine`, la imagen del banco de QA.

## Alternativas rechazadas

- **Publicar en la transacción del cambio, sin bandeja.** Es el dual-write que el ADR 0022 cierra:
  un servicio que guarda y cae antes de publicar pierde el evento.
- **Dejar a los consumidores drenando la bandeja ajena y que publiquen al broker.** Era lo que
  hacía `BrokerSink`, y no quita la lectura cruzada.
- **Un solo publicador para las tres bandejas.** Abriría motores a tres bases ajenas: la misma
  excepción, en otro proceso.
- **Una cola por tipo de evento, o un exchange por servicio.** Con una cola por consumidor, atada
  por tipos, el consumidor decide qué escucha y uno nuevo no toca a los productores.
- **Reintentar con `nack(requeue=True)`.** Un mensaje que siempre falla volvería al frente sin
  espera, en bucle. Además, una cola clásica no cuenta las entregas (`x-delivery-count` es de las
  quorum). La cola de reintentos con TTL da la espera, y la cabecera propia da la cuenta.
- **Colas quorum.** Sirven en un clúster, y el piloto tiene un nodo. Además, su límite de entregas
  no se comporta igual en 3.13 y en 4.x.
- **El plugin de mensajes diferidos.** No viene en la imagen oficial ni en el banco de QA.
- **Que el trabajador deje de mirar la tabla.** Sin barrido, un trabajo cuyo aviso no llegó (por
  ejemplo, uno creado antes de encender el broker) se quedaría `encolado` para siempre. El barrido
  cuesta una consulta por minuto.
- **Una tabla de deduplicación en Identidad.** Diría lo mismo que el colegio ya dice, como se
  razonó en el ADR 0042.
- **Hacer RabbitMQ obligatorio y quitar el sondeo.** Sin broker siguen corriendo las pruebas por
  servicio, CI y el desarrollo. Quitar el respaldo es una decisión aparte.

## Lo que queda abierto

- **El modo es de todo el sistema, no de cada proceso.** Con una configuración mezclada, los dos
  caminos se pisan:
  - un sondeador sin URL marca publicado lo que drena, y el publicador ya no lo lleva al broker;
  - un repartidor sin URL marca `trabajo_encolado` sin publicarlo, y el trabajo lo toma el barrido
    al cabo de un minuto.

  `make arriba` y el compose le dan la misma URL a todos.
- **Sin publicador, nada sale.** Con broker, si el publicador de un servicio no corre, sus eventos
  esperan en la bandeja. Los trabajos los recoge el barrido, pero los avisos no salen. El perfil
  `api` del compose no tiene procesos de fondo.
- **Un mensaje en descartados se queda ahí.** No hay herramienta para devolverlo a su cola: se
  mueve a mano desde la consola de gestión.
- **Cambiar los argumentos de una cola,** como el TTL de reintentos, exige borrarla antes.
  RabbitMQ responde `PRECONDITION_FAILED` y el proceso termina, porque es configuración y no una
  caída.
- **Una credencial mala de RabbitMQ deja reintentando a los consumidores y a los publicadores,** no
  solo al repartidor (ver el ADR 0041).
- **El RabbitMQ 4.4 de Homebrew tarda unos 5 s en aceptar cada conexión.** Por eso la comprobación
  de `make arriba` espera hasta 15 s.
- **`BrokerSink` queda sin uso.** Quitarlo es otra limpieza.

## Consecuencias

- Módulos nuevos en `tukit_comun`: `topologia`, `mensajes`, `publicador`, `consumidor` y
  `pruebas_colas`. `broker` gana `responde` y `python -m tukit_comun.broker`.
- Tres procesos nuevos, con su objetivo en el `Makefile`: `publicador-catalogo`,
  `publicador-comercio` y `publicador-inteligencia`.
- Migración `3c7d9e1f5a28` en inteligencia: crea `evento_procesado` sobre `6a2f8c4e1d57`, con su
  reversa. El manifiesto pasa a 74 tablas.
- El contrato sube a 1.10 por el §10. La API HTTP no cambia.
- Pruebas:
  - unitarias, con dobles y sin broker: `libs/py/tukit_comun/tests/test_colas.py`, una por
    publicador y `test_*_cola.py` en cada consumidor;
  - de integración, con el marcador `rabbitmq`, en `test_colas_rabbitmq.py`. `make prueba-colas` y
    el trabajo `colas` de CI las corren, y `make prueba` las deja fuera;
  - de fronteras: la regla 3b y sus pruebas de activación.
