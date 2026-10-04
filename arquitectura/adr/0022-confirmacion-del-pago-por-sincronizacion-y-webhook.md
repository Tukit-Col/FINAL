# ADR 0022 — El pago se confirma preguntándole a Wompi, y webhook y sincronización comparten un aplicador idempotente

- **Estado:** aceptada
- **Fecha:** 2026-10-02
- **Servicio tocado:** `comercio`
- **Requisitos:** `FU-03`, `SG-03`; contrato §9 (webhook idempotente contra
  `evento_pasarela_procesado`)

## Contexto

El §9 confiaba la confirmación del pago al webhook de Wompi. En desarrollo el webhook no llega:
Wompi no alcanza `localhost`, y exigir un túnel para que un pedido pase a `pagado` hace que la
demostración dependa de una pieza que no es del sistema. Sin webhook, el pedido se quedaba en
`pendiente_pago` para siempre.

La implementación además encontró tres defectos en lo que había:

- **El candado de idempotencia usaba un id que Wompi no manda.** Los eventos reales no traen id
  de evento; el código caía al id de transacción. Dos eventos de la misma transacción con estados
  distintos (`PENDING` y luego `APPROVED`) chocaban, y el segundo, el que importa, se descartaba
  como repetido.
- **No se validaba el monto** reportado contra el monto congelado del pago.
- **Un pago aprobado podía retroceder.** Un `PENDING` tardío o un `DECLINED` posterior pisaban un
  `aprobado`, y el pedido quedaba `pagado` con su pago en `rechazado`.

## Decisión

1. La confirmación sale de **preguntarle a Wompi, de servidor a servidor**, por la transacción
   (`GET /v1/transactions/{id}`). El navegador solo aporta el id: `POST /v1/pagos/{id}/sincronizar`.
   El webhook se conserva como segundo camino.
2. Los dos caminos usan **un solo aplicador** (`_aplicar_resultado` en `comercio/api.py`): candado,
   búsqueda del pago por referencia, validación de monto, actualización del pago, transición del
   pedido y aviso `pedido_pagado` en la bandeja, en la misma transacción.
3. La clave de idempotencia es **`<transacción>:<ESTADO>`**: cada cambio de estado cuenta una vez y
   un reenvío del mismo estado no. Llegar por los dos caminos no aplica dos veces.
4. **Los estados finales del pago no retroceden**: `aprobado` y `reembolsado` no se pisan, y un
   `PENDING` tardío no revive un pago `rechazado`. El `UPDATE` también exige que el pago no esté en
   un estado final, para cerrar la carrera entre dos escritores.
5. **Un monto distinto del congelado no aprueba**: el pago queda `rechazado` y el pedido no se
   mueve.
6. **Una referencia por intento** (`tukit-<pago_id>`), para poder reintentar tras un rechazo sin
   chocar con el índice único.
7. Si el webhook y la sincronización llegan a la vez, el segundo `INSERT` del candado choca con el
   índice único y la sincronización **reintenta una vez** en una sesión nueva, donde el resultado es
   `repetido` con el estado vigente.
8. La consulta pública exige moneda `COP` y, si Wompi dice de qué comercio es la transacción, que
   sea el nuestro (`merchant.public_key`). Se confirmó en sandbox que Wompi sí envía ese campo.

## Alternativas rechazadas

- **Solo webhook, con túnel obligatorio en desarrollo.** Es lo que pedía el §9. Hace que un pago de
  prueba dependa de que el túnel esté arriba y registrado en el panel de Wompi.
- **Confiar en el estado que trae el navegador al volver.** Wompi lo dice expresamente: el retorno
  es informativo y no se valida con él. Cualquiera podría escribir `?status=APPROVED` en la URL.
- **Dos aplicadores, uno por camino.** Cada uno tendría su propia idea de idempotencia, y el que
  llega segundo no sabría que el otro ya aplicó.

## Consecuencias

- Un pago de prueba se confirma en `localhost` sin túnel; el webhook queda como respaldo cuando
  hay URL pública.
- `GET /v1/transactions/{id}` es público: cualquier comercio podría crear una transacción con una
  referencia nuestra. La verificación de moneda y comercio lo cubre en sandbox. En producción la
  verificación del comercio tiene que ser obligatoria, no "si viene el campo".
- Una anulación real posterior a una aprobación (`VOIDED`) no se refleja: el pago aprobado no
  retrocede. Los reembolsos están fuera de alcance; cuando entren, entran por su propio camino y no
  por un evento tardío.
- Cualquiera puede llamar a la sincronización con un id real ajeno: inserta una fila en el candado
  y hace una llamada a Wompi. Es de bajo impacto y la limitación de tasa es trabajo de la puerta.
