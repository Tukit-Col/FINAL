# ADR 0033 — El pago se abre con el widget de Wompi, con la configuración por `postMessage`

- **Estado:** aceptada
- **Fecha:** 2026-10-02
- **Servicios tocados:** `comercio` (firma los datos), `apps/web` (abre el widget)
- **Requisitos:** `FU-03` (Wompi: PSE, Nequi y tarjeta), `SG-03` (no se guardan medios de pago),
  `UI-05`

## Contexto

`FU-03` ya nombraba a Wompi y el §9 del contrato dejaba la integración tras un puerto
`PasarelaPago`. Lo que no estaba decidido era *cómo* llega el acudiente al formulario de pago.
Wompi ofrece tres caminos: su API de transacciones (Tukit pinta el formulario y tokeniza la
tarjeta), su Web Checkout alojado (se redirige a `checkout.wompi.co/p/?…` con los parámetros en
la URL) y su widget (un modal que se abre encima de la página con `new WidgetCheckout({...})`).

El primer adaptador intentaba la API sin medio de pago, y Wompi la rechaza: esa API exige el
medio y, para tarjeta, un token creado en el navegador. Se pasó al Web Checkout, y la prueba
con llaves reales encontró lo que la documentación no dice: **el CDN de `checkout.wompi.co`
responde 403 cuando la URL lleva un `redirect-url` a `localhost` o a una IP privada**. Se
verificó parámetro por parámetro: todos pasan menos ese, y un dominio público (incluido uno de
túnel) sí pasa. Con el Web Checkout, entonces, el acudiente no puede volver a un Tukit que corre
en la máquina del equipo, que es donde se desarrolla y se demuestra.

El widget tiene el mismo problema escondido. Por omisión serializa toda su configuración en la
URL de su iframe (`bootstrapTransport: "query"`), así que un `redirectUrl` a `localhost` vuelve a
disparar el 403: el iframe no carga y el modal se queda girando. Solo con
`bootstrapTransport: "postmessage"` la configuración viaja por mensaje entre la página y el
iframe y la URL queda limpia.

Y el `redirectUrl` no se puede quitar: PSE se lleva la pestaña entera al banco, el modal y su
callback desaparecen, y sin `redirectUrl` el comprobante de Wompi deja al acudiente ahí, sin
camino de vuelta. La API de Wompi acepta y guarda `localhost` como retorno; el bloqueo es solo de
la URL del checkout.

## Decisión

1. El pago se abre con el **widget de Wompi** en un modal sobre la página del kit o de "Mis
   pedidos". Con tarjeta y Nequi el acudiente no sale de Tukit.
2. **`comercio` arma y firma los datos del widget** (`datos_widget` en `pasarela.py`): llave
   pública, monto en centavos, referencia, firma de integridad y correo. El secreto de
   integridad nunca llega al navegador.
3. Los datos llevan **`redirectUrl` a `/pago/resultado`**, para PSE.
4. El navegador abre el widget **siempre con `bootstrapTransport: "postmessage"`**
   (`opcionesWidget` en `apps/web/src/lib/wompi.ts`), fijado por una prueba.
5. Lo que el callback o el retorno entregan es **informativo**: solo trae el id de la
   transacción, y la confirmación sale del servidor (ADR 0034).
6. Solo **sandbox**: con `WOMPI_MODO=sandbox`, `comercio` no arranca si alguna llave no empieza
   por `pub_test_`, `prv_test_`, `test_events_` o `test_integrity_`. No hay modo de producción.

## Alternativas rechazadas

- **API de transacciones con formulario propio.** Control total del diseño a cambio de un
  formulario y un flujo por medio de pago (PSE pide banco y tipo de persona, Nequi espera la
  confirmación en el teléfono) y de manejar tokens de tarjeta. Más trabajo y más superficie
  sensible para el mismo resultado en pruebas.
- **Web Checkout alojado por redirección.** Fue la primera implementación. Funciona solo con un
  retorno público, lo que obliga a abrir la app por un túnel para probar un pago. Se usó un día
  y se retiró.
- **Widget sin `redirectUrl`.** Resuelve el 403 y rompe PSE: el acudiente queda varado en el
  comprobante de Wompi.

## Consecuencias

- El acudiente paga desde `localhost` sin túnel, con los tres medios.
- `bootstrapTransport` es una opción del widget que la documentación pública de Wompi no
  menciona; se encontró leyendo `widget.js`. Si Wompi la cambia, el síntoma es el modal que gira
  sin fin, y la prueba de `apps/web/test/wompi.test.ts` es la que documenta por qué existe.
- Si el navegador no tiene `crypto.getRandomValues`, el widget cae solo al transporte por URL y
  el 403 vuelve. Todos los navegadores actuales lo tienen.
- Producción necesita otra decisión: llaves reales, un retorno público y la verificación del
  comercio obligatoria en la consulta de transacciones (ADR 0034).
