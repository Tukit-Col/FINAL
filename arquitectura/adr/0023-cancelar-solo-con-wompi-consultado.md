# ADR 0023 — Un pedido pendiente se cancela solo después de consultar a Wompi; vence a las 24 horas y hay uno por kit

- **Estado:** aceptada
- **Fecha:** 2026-10-03
- **Servicios tocados:** `comercio`, `apps/web` ("Mis pedidos")
- **Requisitos:** `FU-01` (orden con precio congelado), `FU-08` (el precio no se mueve después de
  confirmar), `SC-05` (re-verificación); ADR 0012 (precio congelado)

## Contexto

Cada clic en **Pagar** creaba un pedido nuevo. Un acudiente que cerraba el modal, o al que le
rechazaban el pago, acumulaba pedidos en `pendiente_pago`, cada uno con su reserva de inventario
viva, y la única forma de pagar era volver al kit y crear otro. "Mis pedidos" no tenía acciones.

Agregar **Cancelar** abre un riesgo que no se ve en las pruebas con la pasarela falsa: PSE puede
estar en curso sin que Tukit lo sepa (el acudiente no volvió y no hay webhook). `cancelado` es un
estado terminal; si la aprobación llega después, Wompi cobró y el pedido no se entrega, y nadie se
entera. El mismo riesgo aparece si se cancelan pedidos duplicados en automático.

Pagar desde "Mis pedidos" un pedido viejo tiene su propio problema: se cobraría el precio
congelado al crearlo, que puede llevar días, y la reserva de inventario sigue tomada mientras
tanto.

## Decisión

1. **`POST /v1/ordenes/{id}/cancelar`** cancela un pedido `pendiente_pago`, pero antes **busca en
   Wompi, con la llave privada, cada intento que siga `iniciado`** (`GET /v1/transactions?reference=`).
   Con la llave privada Wompi solo devuelve transacciones de este comercio.
   - Un pago **aprobado** se aplica en el acto y no se cancela: `409 pedido_ya_pagado`.
   - Un pago **en curso** bloquea la cancelación: `409 pago_en_curso`.
   - Si Wompi **no responde**, no se cancela: `502 pasarela_no_disponible`.
   - Si no hay nada, se cancela y la reserva pasa a `liberada`.
2. **Red de seguridad:** si aun así llega una aprobación para un pedido cancelado, el pedido no se
   mueve, el pago queda `aprobado` y se escribe una **`incidencia`** en la bandeja de salida. Se usa
   ese tipo porque el repartidor lo entrega (al acudiente le llega "Hubo una novedad con tu
   pedido"); un tipo nuevo lo descartaría en silencio.
3. **Un pedido se puede pagar durante 24 horas** desde su `creado_en`. Después, `POST /pago`
   responde `409 pedido_vencido` y la UI ofrece rearmar el kit, donde el precio se re-verifica
   contra el catálogo. **No hay columna nueva**: la vigencia sale de la fecha de creación. Un pedido
   vencido sí se puede cancelar, para liberar su reserva.
4. **Un pedido pendiente por kit.** `POST /v1/ordenes` con `trabajo_id`:
   - si el mismo acudiente tiene un pendiente **idéntico y vigente** para ese kit (mismos productos,
     cantidades y precios, misma entrega), lo **reutiliza** y el pago nuevo es otro intento sobre él;
   - si cambió algo, **cancela los pendientes anteriores con la misma consulta a Wompi**; uno con
     pago en curso o aprobado, o con Wompi caído, se deja como está.
   Las órdenes sin kit no se deduplican.
5. La lógica vive en `comercio`, que es el dueño del pedido; `inteligencia` no cambia.

## Alternativas rechazadas

- **Cancelar sin consultar a Wompi.** Es lo obvio y es el defecto: cobra sin entregar en el caso
  que más se demora, PSE.
- **Una columna `vence_en`.** Duplica un dato que se deriva de `creado_en` y abre la puerta a que
  los dos digan cosas distintas. Si un día la vigencia cambia por pedido, se agrega entonces.
- **Proceso que expire pedidos en segundo plano.** Libera reservas sin intervención, pero es otro
  trabajador con su propia consulta a Wompi y su propio horario. Queda fuera mientras la cancelación
  y la deduplicación cubran el caso.
- **Deduplicar en `inteligencia`**, que arma la orden. No es el dueño del pedido y tendría que
  preguntarle a `comercio` todo lo que necesita para decidir.

## Consecuencias

- "Mis pedidos" deja de acumular duplicados por kit, y pagar o cancelar ahí no requiere formulario.
- Un pedido vencido que nadie cancela sigue reteniendo su reserva. Se libera al cancelarlo o al
  rearmar ese kit.
- Si un pago se aprueba entre la consulta a Wompi y el `UPDATE` que cancela, el `UPDATE` exige
  `pendiente_pago` y no pisa el pago aplicado; si llega después, lo cubre la incidencia. Operación ve
  ese caso en su tablero como pedido cancelado con pago aprobado y decide entre reembolsar o
  despachar.
- La cancelación hace una llamada a Wompi por intento pendiente. Con pocos intentos por pedido el
  costo es despreciable.
