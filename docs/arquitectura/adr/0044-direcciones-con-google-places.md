# ADR 0044 — La dirección del checkout se autocompleta con Google Places (New), y sin Google sigue siendo un campo libre

- **Estado:** aceptada
- **Fecha:** 2026-10-10
- **Servicios tocados:** `apps/web` (checkout de `kits/[trabajo_id]`), `inteligencia` (`EntregaCheckout`), `comercio` (`envio`, firma de la orden), `apps/admin` (logística)

## Contexto

El checkout pedía la dirección como texto libre, más una ciudad, y logística la leía tal cual.
Para repartir en Bogotá eso no alcanza. Una dirección escrita a mano llega con abreviaturas
distintas ("Cra", "Kr", "Carrera"), sin localidad, y sin dónde poner la torre o el apartamento,
que terminaban pegados a la calle. El repartidor la copiaba en Google Maps a mano.

Google Places (New) sugiere direcciones reales mientras se escribe y devuelve sus componentes:
ciudad, departamento y, en Bogotá, casi siempre la localidad. Pero cuesta dinero por uso, exige
una llave que viaja al navegador, y sus términos limitan qué se puede guardar.

## Decisión

1. **La llave es de servidor y viaja por props.** `GOOGLE_MAPS_API_KEY` (sin `NEXT_PUBLIC_`) la
   lee la página de servidor del kit y se la pasa al checkout. No queda incrustada en el bundle
   de todas las páginas: solo llega a quien abre un checkout. Como toda llave de Maps
   JavaScript, el navegador la ve. Por eso se restringe por referrer y por API en Google Cloud,
   y esa restricción es la defensa real.
2. **Sin llave, o si Google falla, el campo es texto libre.** La librería se carga al primer
   foco del campo, no al abrir el checkout. Cualquier fallo devuelve `null` y el campo queda
   como antes: sin red, llave rechazada (`gm_authFailure`), API sin habilitar o sin
   facturación. Maps jamás bloquea el pago. Ciudad, localidad y departamento son siempre
   editables, y la localidad tiene un desplegable con las 20 de Bogotá
   (`LOCALIDADES_BOGOTA` en `@tukit/contrato`).
3. **Se guarda el `place_id`, no las coordenadas.** Los términos de Google permiten guardar el
   `place_id` sin límite y no permiten guardar coordenadas más allá de un caché temporal. El
   envío guarda `google_place_id` y logística arma con él un enlace de búsqueda de Google Maps
   (`query_place_id`), que no se cobra. No se piden ni se reciben coordenadas: `inteligencia`
   descarta cualquier campo que no esté en `EntregaCheckout`. Editar la dirección después de
   elegir una sugerencia borra el `place_id`, porque ya no apunta a lo escrito.
4. **El costo se contiene en el cliente.**
   - **Sesiones.** Un `AutocompleteSessionToken` por búsqueda, que se cierra con un único
     `fetchFields` al elegir y se renueva después. Con la tarifa de Google vigente al escribir
     esto, las sugerencias de una sesión que termina en un Place Details no se cobran aparte.
   - **Solo campos Essentials.** El `fetchFields` pide `formattedAddress` y `addressComponents`,
     nada de Pro ni Enterprise (horarios, fotos, reseñas).
   - **Menos peticiones.** Sugerencias desde 3 caracteres, con 250 ms de espera entre teclas,
     solo en Colombia (`includedRegionCodes: ["co"]`). Bogotá es un sesgo
     (`locationBias`), no una restricción: Soacha y Chía también se sugieren.
   - **Cuota y presupuesto.** Se bajan las cuotas diarias de las dos APIs y se pone una alerta
     de presupuesto. La alerta solo avisa; la cuota es lo que corta el gasto.
5. **La atribución de Google se muestra.** Al pie de las sugerencias, porque no hay un mapa que
   la lleve.

## Alternativas rechazadas

- **`NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`.** Queda en el bundle de todas las páginas, y cambiarla
  exige recompilar. La llave sigue siendo visible en el checkout, pero solo ahí, y se cambia
  reiniciando el servidor.
- **El widget `PlaceAutocompleteElement`.** Trae su propio campo y su propio estilo. No encaja
  con el formulario, con el combobox accesible que ya usa `/empezar`, ni con la regla de
  degradar a un `<input>` común.
- **Guardar latitud y longitud** para rutear. Los términos no lo permiten más allá de un caché
  temporal, y hoy el reparto es propio y abre Maps con el enlace.
- **Validar la localidad en el servidor contra el catálogo de 20.** Un checkout viejo o un
  cliente sin JavaScript dejaría de cerrar. El servidor solo valida largos, y la regla
  "obligatoria en Bogotá" vive en el formulario.
- **Geocodificar del lado del servidor.** Duplica el costo y la llave, para un dato que el
  acudiente ya eligió en el navegador.

## Consecuencias

- Logística recibe dirección normalizada, localidad, indicaciones y un enlace a Maps. La firma
  que decide si un pendiente se reutiliza compara todos los campos congelados de la entrega,
  salvo `google_place_id`.
- Sin llave, el checkout funciona igual que antes, con dos campos más (indicaciones y
  localidad). Desarrollo y CI no necesitan la llave.
- Activar Maps es operación, no código: un proyecto de Google Cloud con facturación, las APIs
  "Maps JavaScript API" y "Places API (New)", una llave restringida, cuotas y alerta. El README
  lo explica.
- Si Google cambia sus tarifas o el alcance de Essentials, el costo cambia sin tocar el código.
  Se revisa en la consola de facturación.
