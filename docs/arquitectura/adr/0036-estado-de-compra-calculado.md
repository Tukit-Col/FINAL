# ADR 0036 — El estado de compra de una solicitud se calcula cruzando pedidos, no se guarda

- **Estado:** aceptada
- **Fecha:** 2026-10-03
- **Servicio tocado:** `apps/web` (panel del acudiente)

## Contexto

En el panel, "Mis solicitudes" (las listas subidas y los trabajos de `inteligencia`) y "Mis
pedidos" (de `comercio`) no se hablaban. Un acudiente que ya había pagado su kit seguía viendo la
solicitud como "Listo: ver mis kits", como si faltara algo. La pregunta fue si al pagar la
solicitud debería cerrarse.

Cerrarla, en el sentido de guardar un estado nuevo en el trabajo, tiene tres problemas. Si el
pedido se cancela o se reembolsa, la solicitud tendría que reabrirse, y dos estados guardados en
dos servicios se desincronizan. El acudiente perdería acceso a los kits que compró, que sirven
para revisar qué traía la lista o para recomprar el año siguiente. Y una solicitud puede cubrir más
de un hijo, así que comprar no siempre la agota. Además, el trabajo es de `inteligencia` y el
pedido es de `comercio`: que uno escriba en el otro cruza una frontera del manifiesto.

## Decisión

El estado de compra **se calcula al pintar el panel**, cruzando por `trabajo_id` los pedidos que
el panel ya carga (`compraDeSolicitud` en `apps/web/src/lib/pagar-pedido.ts`):

- **Comprado:** el kit tiene un pedido pagado o en camino (`pagado`, `en_preparacion`,
  `despachado`, `en_reparto`, `entregado`); se enlaza el más reciente.
- **Pago pendiente:** no lo tiene, pero hay uno `pendiente_pago` y vigente (ADR 0035).
- Si no, la solicitud se muestra como siempre.

Nada se escribe en `inteligencia` ni en `comercio`. Los kits siguen visibles en modo consulta.

## Alternativas rechazadas

- **Un estado `cerrada` o `comprada` en el trabajo.** Obliga a `comercio` a avisarle a
  `inteligencia` en cada cambio de pedido, incluidos cancelaciones y reembolsos, y a manejar el
  desfase cuando el aviso no llega.
- **Ocultar la solicitud al pagar.** Quita el acceso a los kits y no deja rastro en el panel de que
  la compra salió de esa solicitud.

## Consecuencias

- Un pedido cancelado devuelve la solicitud a "Listo" sin escribir nada.
- El cruce cuesta lo que ya costaba cargar el panel: los pedidos se leían de todas formas.
- Si un día la solicitud necesita un estado de compra fuera del panel (un correo, un reporte), el
  cruce se repite ahí o se expone desde `comercio`; no se resuelve guardándolo en el trabajo.
