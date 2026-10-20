# ADR 0041 — Los procesos de fondo se recuperan solos de una caída de Postgres o de RabbitMQ

- **Estado:** aceptada
- **Fecha:** 2026-10-19
- **Servicios tocados:** `libs/py/tukit_comun` (`resiliencia`), `comercio` (`barredor`),
  `identidad` (`poller`), `inteligencia` (`poller`, `trabajador`), `operacion` (`repartidor`)
- **Origen:** el hallazgo H-B-02 del nivel 1 de QA de las fases 7 a 9 (corrida
  `20261019-0505-70b9108-f7-9`, escenarios CH-12 y CH-15), corregido en la rama
  `arreglos/h-b-01-03`.

## Contexto

**Cinco procesos corren en bucle:** `comercio-barredor`, `identidad-poller`, `inteligencia-poller`,
`inteligencia-trabajador` y `operacion-repartidor`. Los cinco eran
`while True: await correr_una_vez(); await asyncio.sleep(intervalo)`, sin un solo `except`.

- **Con Postgres caído (CH-12),** el primer `begin()` lanzaba `ConnectionRefusedError`.
- **Con RabbitMQ caído (CH-15),** el repartidor recibía el error de conexión de aiormq. Es el único
  proceso que publica con `BrokerSink`.
- **En Docker,** el nombre del contenedor muerto deja de resolver, así que ahí lo esperable es
  `socket.gaierror`.

En los tres casos el proceso terminaba con código 1 y no volvía. Cuando la dependencia regresaba,
nadie liberaba reservas vencidas, ni daba de alta colegios, ni armaba el kit de una lista
aprobada, ni procesaba trabajos, ni avisaba.

**La recuperación tiene que ser del producto.** Un `restart: always` de Compose la escondería en
la infraestructura, no existe igual en todos los entornos, y reiniciar en bucle un proceso con un
bug esconde el bug.

## Decisión

1. **Una sola pieza común: `bucle_resiliente`, en `tukit_comun.resiliencia`.** Va sobre
   `tenacity`, que ya se usaba para los GET.
   - Corre la vuelta. Si cae por una caída transitoria, espera 1 s, el doble cada vez y como mucho
     30 s, y la repite.
   - Tras una vuelta buena, duerme el intervalo del proceso, y la espera vuelve a empezar.
   - Cada caída deja un WARNING con el proceso, el intento, la espera y la excepción.
2. **Qué es una caída lo decide `es_caida_transitoria`.** Mira el error y sus causas explícitas
   (el `.orig` de SQLAlchemy y el `raise ... from`). Es una caída:
   - un `OSError` de red, que incluye `ConnectionRefusedError`, `TimeoutError`, `socket.gaierror`
     y el `AMQPConnectionError` de aiormq;
   - un `DBAPIError` con `connection_invalidated`;
   - por el nombre de la clase, los errores de conexión de asyncpg (`OperatorInterventionError`,
     `PostgresConnectionError` y `TooManyConnectionsError`) y el `ChannelInvalidStateError` de
     aiormq. Va por nombre y no por import porque asyncpg es opcional y aio-pika solo se carga
     donde se publica.
3. **Un error de programación sigue terminando el proceso.** Un `ValueError`, una restricción
   violada o una tabla que no existe no son caídas, y suben como antes. Tampoco se sigue
   `__context__`: un error lanzado mientras se manejaba una caída es un bug.
4. **Cada vuelta reconecta.** El barredor, los pollers y el repartidor abren sus motores y su sink
   en cada vuelta y los cierran al terminarla. El trabajador reusa su motor, que tiene
   `pool_pre_ping`.
5. **Cada `main()` llama a `configurar_registro("<proceso>")`.** Así el WARNING sale en JSON con
   `TUKIT_LOG_JSON`, como el de los servicios HTTP (ADR 0021).
6. **Los bucles buscan `asyncio.sleep` al correr, no al definirse** (`dormir or asyncio.sleep`).
   Así terminan las pruebas que lo sustituyen.

## Alternativas rechazadas

- **`restart: always` o un supervisor.** Ver el contexto. Además, en local los procesos se lanzan
  con `make`, sin supervisor.
- **Un `try/except Exception` en cada bucle.** Serían cinco copias, y atrapar todo esconde los bugs
  detrás de reintentos.
- **Reintentar dentro de cada consulta.** Las vueltas ya son idempotentes (`SKIP LOCKED`, la
  bandeja de salida, las reservas por TTL). Repetir la vuelta entera es más simple y reconecta
  todo de una vez.
- **Un tope largo, de minutos.** Un proceso que espera minutos a una base que ya volvió deja
  eventos sin entregar sin que nada lo explique. Con 30 s, el repartidor vuelve a avisar a más
  tardar medio minuto después de que vuelve la base.

## Lo que queda abierto

- Un trabajo que quedó `procesando` durante la caída lo retoma la vuelta de colgados del
  trabajador, pasados 15 minutos (`_COLGADO_DESDE`).
- Que en Docker el error sea `socket.gaierror` queda por confirmar en la verificación: la corrida
  no guardó trazas. Las pruebas cubren ese error y `ConnectionRefusedError`.
- `es_caida_transitoria` trata como transitorio todo `OSError` que no sea de archivos. Eso incluye
  el `AuthenticationError` de aiormq, así que una credencial mala de RabbitMQ deja el repartidor
  reintentando con WARNING en vez de morir.

## Consecuencias

- Pruebas nuevas:
  - `libs/py/tukit_comun/tests/test_bucle_resiliente.py`: la clasificación, las esperas, que la
    espera vuelve a empezar, el WARNING y que un `ValueError` o una cancelación terminan el bucle;
  - una por servicio, contra el `_bucle` real, con una dependencia que falla las primeras veces y
    después responde: `test_barredor_resiliente.py`, `test_poller_resiliente.py` (identidad),
    `test_procesos_resilientes.py` (inteligencia) y `test_repartidor_resiliente.py`.
- No cambia ninguna tabla ni el contrato.
