# ADR 0042 — Un evento da un solo aviso, aunque la bandeja lo entregue otra vez

- **Estado:** aceptada
- **Fecha:** 2026-10-19
- **Servicios tocados:** `operacion` (`repartidor`, `notificacion`)
- **Origen:** el hallazgo H-B-03 del nivel 1 de QA de las fases 7 a 9 (corrida
  `20261019-0505-70b9108-f7-9`, escenario CH-15), corregido en la rama `arreglos/h-b-01-03`.

## Contexto

**En CH-15, un solo pago avisó dos veces `pedido_pagado` al acudiente.** El repartidor drena las
bandejas de salida de inteligencia y de comercio con `drenar` (ADR 0022).

1. Por cada evento, envía el aviso y guarda la `notificacion` en la base de operación, que es otra
   base y otra transacción.
2. Después `drenar` marca el evento en la bandeja y lo publica al broker, dentro de la transacción
   de la bandeja, que abarca toda la pasada.
3. Si publicar falla (RabbitMQ caído), esa transacción vuelve atrás entera y la siguiente pasada
   trae el mismo evento: un segundo correo y una segunda fila.

La entrega es *at-least-once* a propósito (ADR 0022), y por eso el consumidor tiene que ser
idempotente. El repartidor no lo era: `notificacion` no sabía de qué evento salía, así que no había
dónde mirar.

## Decisión

1. **La `notificacion` guarda su evento:** `evento_origen` (la bandeja, `inteligencia` o
   `comercio`) y `evento_id` (el id de la fila en esa bandeja). Cada bandeja numera por su cuenta,
   así que el evento es el par.
2. **Antes de resolver el contacto o de enviar, el repartidor mira si ese evento ya tiene un aviso
   `enviada`** (`RepoNotificaciones.ya_avisado`). Si lo tiene, devuelve `HECHO` sin enviar, y
   `drenar` marca el evento y lo publica cuando el broker vuelve. Así se evita el segundo envío, no
   solo la segunda fila.
3. **La reentrega sigue para lo que no se avisó.** Un envío fallido deja su fila `fallida`, y el
   evento se reintenta y sale, como antes.
4. **Un índice único parcial lo respalda en la base:** `uq_notificacion_evento_enviada`, sobre
   (`evento_origen`, `evento_id`), con `WHERE estado = 'enviada'`.
   - Es parcial para que convivan varios intentos `fallida` del mismo evento.
   - Deja pasar las notificaciones de antes de estas columnas, que no tienen evento.
   - Vive en el modelo y en la migración del servicio, no en `infra/postgres/indices`.

## Alternativas rechazadas

- **Marcar y publicar el evento antes de enviar.** Si el envío fallara después, el evento ya
  estaría marcado y el aviso no saldría nunca: se cambiaría un aviso doble por uno perdido.
- **Que `drenar` no vuelva atrás cuando falla la publicación.** La pasada entera vuelve atrás a
  propósito (ADR 0022), y hay pruebas que lo fijan. Cambiarlo toca a todos los drenadores para
  arreglar un consumidor.
- **Un índice único sin condición sobre el evento.** No dejaría registrar un intento nuevo después
  de uno `fallida`, y el historial de intentos es lo que muestra que un aviso costó dos.
- **Una tabla de deduplicación aparte**, como `evento_pasarela_procesado` en comercio. La
  notificación ya es el registro de que el aviso salió, y una segunda tabla diría lo mismo en otro
  lugar.

## Lo que queda abierto

- Si el repartidor muere entre el envío y el commit de su `notificacion`, el aviso puede salir otra
  vez: el proveedor de correo y la base no comparten transacción.
- El índice es la última defensa. `SKIP LOCKED` impide que dos repartidores tomen el mismo evento,
  así que no debería saltar. Si saltara, el `IntegrityError` no es una caída transitoria (ADR 0041)
  y terminaría el repartidor. Es preferible a avisar dos veces, pero se vería como un proceso caído.

## Consecuencias

- Migración `3f0bbbca4e60` en `operacion`: agrega las dos columnas y el índice, y su downgrade los
  quita.
- Pruebas nuevas: `test_aviso_idempotente.py` y `test_migracion_evento_notificacion.py`. Además,
  `test_repartidor_resiliente.py` pide un solo envío y una sola fila `pedido_pagado` tras una caída
  de RabbitMQ, que es lo que mide CH-15.
- Para el acudiente, lo único que cambia es que recibe un aviso por pago.
