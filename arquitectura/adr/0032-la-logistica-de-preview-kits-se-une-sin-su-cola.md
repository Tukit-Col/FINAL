# ADR 0032 — La logística de `preview-kits` se une a los pagos; su cola y su vista previa no

- **Estado:** aceptada
- **Fecha:** 2026-10-04
- **Origen:** `feature/integracion-total`

## Contexto

`feature/preview-kits` traía dos cosas distintas en la misma rama:

1. **Logística de pedidos**: el tablero y el detalle del back-office con sesión de operador o
   admin, el reparto propio (repartidor, incidencias), un historial de cada avance con el correo
   de quien lo hizo, avisos al acudiente desde operación y una puerta que solo deja pasar
   `avanzar` bajo `/v1/ordenes`.
2. **Un rediseño de la cola del admin**: una sola cola por lista, una vista previa que se
   promueve a kit del grado al aprobar la lista y el kit del papá armado desde ella.

El rediseño de la cola se descartó: se mantienen las colas de esta rama y su flujo canónico
(`lista_aprobada` arma el Ahorrador y el Premium del grado, ADR 0030). La logística sí se quiere,
y tiene que convivir con los pagos de Wompi (ADR 0021 a 0023 de la carpeta local), que la rama
no conocía.

## Decisión

- **Se une toda la logística.** Comercio, operación, la puerta, el manifiesto, el contrato TS de
  pedidos, la pantalla de logística del admin y el panel del acudiente leyendo sus pedidos con
  su sesión.
- **Se descarta el rediseño de la cola.** Los archivos que solo tocaba el rediseño vuelven a su
  versión de esta rama, y los que agregaba se quitan. Donde una misma pieza mezclaba las dos
  cosas (la página de inicio del admin, el cliente HTTP del contrato) se tomó la versión de esta
  rama y se le aplicó solo el commit de logística.
- **Se rescatan los arreglos que no dependen del rediseño**, después de comprobar con sus propias
  pruebas que el defecto existía aquí: validar una línea sin producto ya no da `500` ni confirma
  otro producto (`422 sin_producto_que_validar`, y el `sku` que no era candidato se registra);
  "sin coincidencia" deja la línea sin producto ni precio en todos los kits; la nota de validar ya
  no se pierde; el producto que sale de una línea pasa a sus alternativas.
- **El acudiente paga, cancela y ve sus pedidos por `/v1/comercio/mis-pedidos/{id}`**, con su
  Bearer, y Comercio comprueba que el pedido sea suyo (uno ajeno es `404`). La puerta ya no
  expone `/v1/ordenes/{id}/pago` ni `/cancelar`, que el panel usaba; abrirlas de nuevo habría
  dejado pagar o cancelar el pedido de otro con solo conocer su id.
- **Inteligencia le pasa a Comercio el token del acudiente** para saber si un kit tiene pedidos
  antes de cancelar la solicitud, porque `mis-pedidos` ya no acepta `?usuario_id=`.
- **La reserva vence a las 24 horas**, igual que el pedido. El barredor de la saga (ADR 0023 del
  backbone) la vencía a los 30 minutos y cancelaba el pedido sin consultar a Wompi: un PSE en
  curso habría quedado cobrado sobre un pedido cancelado.

## Alternativas rechazadas

- **Cherry-pick de los commits de logística en vez de unir la rama.** Deja la rama como no unida
  y el próximo merge volvería a traer el rediseño. Se prefirió unirla y revertir el rediseño en
  el mismo commit.
- **Volver a abrir `/v1/ordenes/{id}/pago` y `/cancelar` en la puerta.** Son rutas sin sesión;
  la puerta las cerró justamente por eso.
- **Que el barredor consulte a Wompi antes de cancelar.** Es lo correcto a largo plazo, pero el
  barredor corre sin pasarela y la consulta ya existe en `cancelar`. Con el mismo plazo que el
  pedido, el barredor solo toca lo que ya no se puede pagar; si aun así llega una aprobación, la
  `incidencia` `pago_tras_cancelacion` lo atrapa.

## Consecuencias

- El contrato pasa a 1.7 (`CONTRATO_API.md`).
- `apps/web` reenvía el Bearer de la cookie a Comercio en sus tres rutas de pedidos.
- Las migraciones de Comercio de la rama (historial del pedido, correo del actor) quedan en la
  cadena después de `dc2ff5819083`.
- La numeración de esta carpeta choca con los ADR 0019 a 0026 del backbone, que viven en el
  repositorio de la tesis: hay que renumerar los locales al incorporarlos.
