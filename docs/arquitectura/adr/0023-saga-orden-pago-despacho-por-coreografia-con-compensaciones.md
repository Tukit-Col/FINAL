# ADR 0023. La transacción orden→pago→despacho es una saga por coreografía, con compensaciones explícitas

- **Estado:** propuesta
- **Fecha:** 2026-09-25
- **Decide:** equipo ISIS2610-G19
- **Objetivos afectados:** OE2 (consistencia entre servicios sin transacción distribuida), OE3
  (integridad del flujo de compra), OE4 (recuperación ante fallo parcial)
- **Relacionada con:** ADR 0022 (los pasos de la saga viajan por el outbox y el broker), ADR 0011 (el
  webhook idempotente de Wompi es el paso T3), ADR 0019 (las transiciones viven en `dominio/`)

## Contexto

La compra cruza dos servicios y una pasarela externa, y **no puede** envolverse en una transacción de
base de datos: Comercio reserva inventario y crea el pedido, Wompi cobra (efecto lateral externo,
irreversible salvo reembolso), y Operación despacha. Hay tres bases distintas (ADR 0014) y un tercero
fuera del sistema. Un `COMMIT` de dos fases no aplica sobre una pasarela HTTP.

Las piezas correctas ya existen, solo que dispersas y no nombradas como saga:

- **Máquina de estados de pedido y pago** con una guardia de transiciones válidas (`transicion_valida`,
  `comercio/api.py:35`) — ya impide saltos ilegales de estado.
- **La consecuencia del pago sobre el pedido ya es una función pura** (`_pedido_tras_pago`,
  `api.py:524-533`): dado el resultado del cobro, decide el nuevo estado del pedido.
- **La compensación del cobro ya existe**: `retractar_orden` (`api.py:650-659`) reembolsa.
- **El paso de confirmación ya es idempotente**: el webhook de Wompi
  (`evento_pasarela_procesado`, `api.py:559-607`) deduplica reintentos de la pasarela (ADR 0011).

Lo que falta es (a) nombrarlo como saga y hacer explícitos sus pasos y compensaciones, y (b) **una
compensación que hoy no existe**: si el pago nunca llega, la reserva de inventario queda tomada para
siempre. No hay liberación por vencimiento.

## Decisión

**El flujo se modela como una saga por coreografía**, con las transiciones como funciones puras en
`comercio/tukit_comercio/dominio/saga.py` (reusando `transicion_valida` y moviendo `_pedido_tras_pago`
a `dominio/pagos.py`), y los pasos avanzando por eventos del outbox/broker (ADR 0022), no por un
orquestador central.

**Pasos (T = transacción local, C = compensación):**

| Paso | Acción | Compensación |
| --- | --- | --- |
| **T1** | Reservar inventario + crear pedido (`crear_orden`) | **C1: liberar la reserva por vencimiento** — *gap actual, se añade* |
| **T2** | Iniciar el cobro contra la pasarela | C2 = C1 si T2 nunca confirma (la reserva vence) |
| **T3** | Confirmar por webhook idempotente → emite `pedido_pagado` al outbox | **C3: reembolso** (`retractar_orden`, ya existe) si un paso posterior obliga a deshacer |
| **T4** | Despachar (Operación drena `pedido_pagado`) | — |

**Coreografía, no orquestación.** Cada servicio reacciona a los eventos que le competen y emite el
suyo; nadie centraliza el flujo. Es lo correcto para **una** saga corta y estable entre dos servicios:
un orquestador sería un tercer componente con estado para coordinar dos. *(Contrasta con la ADR 0024:
el pipeline de Inteligencia sí es orquestado, porque es largo, ramificado y de un solo servicio — dos
problemas distintos, dos respuestas distintas.)*

**La compensación que se añade — C1, liberación de reserva por vencimiento.** La `reserva_inventario`
gana un vencimiento; un barredor (drenado con el mismo `SKIP LOCKED` de la ADR 0022) libera las
reservas cuyo pago no confirmó dentro del TTL. Cierra el único agujero de consistencia real del flujo:
inventario bloqueado por una compra que nunca se pagó.

**T4 es *at-least-once*, no compensable.** Notificar/despachar tras el pago no se "deshace": si falla,
se reintenta (el outbox lo garantiza, ADR 0022). Solo los pasos con efecto reversible tienen
compensación; los idempotentes-reintentables no la necesitan.

**Las transiciones se prueban como funciones puras** (ADR 0019): cada par `(estado, evento)` →
`assert` sobre el estado resultante, sin FastAPI ni Postgres. La invariante de que no se cobra a un
precio cambiado (FU-08) y la de que no se despacha sin pago confirmado se vuelven tests de tabla.

## Consecuencias

**A favor.** La consistencia del flujo de compra queda garantizada sin transacción distribuida:
avanza con confirmaciones y retrocede con compensaciones, ambas explícitas y probadas. Se cierra el
gap de la reserva colgada. La lógica más delicada del negocio pasa a ser una tabla de transiciones
testeable en milisegundos. Reusa cuatro piezas que ya existían.

**En contra.** La coreografía reparte el flujo entre servicios: para entender la saga completa hay que
leer los manejadores de eventos de Comercio y Operación, no un solo archivo. Se acepta a cambio de no
introducir un orquestador con estado para dos servicios; el diagrama de estados en
`REVISION_ARQUITECTURA.md` (Parte B) documenta el flujo completo en un solo lugar para compensarlo.

**Deuda que se declara.** El TTL de la reserva es un número que hay que calibrar contra el tiempo real
que tarda un acudiente en pagar en la pasarela; arranca conservador (holgado) y se ajusta con datos de
piloto, no a ciegas.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| **Saga orquestada** (un coordinador central) | Un tercer componente con estado para coordinar dos servicios en un flujo corto y estable. La coreografía por eventos ya lleva el estado en cada servicio; el orquestador es peso que este flujo no pide. (Sí aplica al pipeline de la ADR 0024, que es largo y de un servicio.) |
| **Transacción distribuida / 2PC** | Imposible sobre una pasarela HTTP externa e irreversible; además acopla las tres bases que la ADR 0014 separó a propósito. |
| **Dejar la reserva sin vencimiento** (lo de hoy) | Inventario bloqueado para siempre por compras que nunca se pagan. Es el único gap de consistencia real del flujo; no cerrarlo es dejar la saga incompleta. |
| **Compensar T4 en vez de reintentar** | El despacho/notificación es idempotente y reintentable; "deshacer una notificación" no tiene sentido. Reintento at-least-once es la forma correcta para pasos sin efecto reversible. |
