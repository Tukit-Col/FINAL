# ADR 0049 — Sin llave de Google, la dirección se busca en OpenStreetMap y se confirma en un mapa

- **Estado:** aceptada
- **Fecha:** 2026-11-02
- **Servicios tocados:** `apps/web` (checkout de `kits/[trabajo_id]`, ruta `/api/direccion/buscar`), `libs/ts/tukit-contrato`, `inteligencia` (`EntregaCheckout`), `comercio` (`envio`, firma de la orden, supresión)

## Contexto

El ADR 0044 dejó la dirección como texto libre cuando no hay `GOOGLE_MAPS_API_KEY`, y hoy no la hay.
Una acudiente lo señaló en una sesión de validación: no tenía cómo elegir una dirección real, y el
repartidor recibía lo que ella tecleara. El admin ya geocodifica con Nominatim (OpenStreetMap) para
su mapa de entregas, así que la pieza y la política de uso ya estaban resueltas del lado del servidor.

## Decisión

1. **Con llave de Google, todo sigue igual (ADR 0044). Sin llave, `CampoDireccionOsm`.** El
   acudiente escribe la dirección, pulsa **Buscar** (o Enter), elige un resultado y confirma el punto
   en un mapa Leaflet moviendo el pin (arrastre, toque en el mapa o flechas del teclado).
2. **Nominatim detrás de un proxy de servidor, sin autocompletado por tecla.** La política del
   servicio público (operations.osmfoundation.org/policies/nominatim) prohíbe el autocompletado, pide
   un User-Agent con contacto y una petición por segundo. `GET /api/direccion/buscar` cumple las tres
   para todos los visitantes juntos: cola de una fila con 1,1 s entre salidas, `User-Agent` con
   `TUKIT_NOMINATIM_CONTACTO` (sin contacto no se consulta), caché de 10 minutos (también de búsquedas
   vacías), una sola petición para dos visitantes con la misma búsqueda y 429 si la cola se llena.
   Sesgo a Bogotá con `viewbox` + `countrycodes=co`, sin `bounded`: Soacha y Chía también salen.
3. **Nominatim y no Photon.** Photon (photon.komoot.io) sí permite autocompletar sobre OSM, pero
   responde en un formato propio y casi nunca trae la localidad de Bogotá, que es lo que la
   logística agrupa. Nominatim trae `address.suburb = "Localidad Chapinero"` y es el servicio que el
   admin ya usa: una fuente, un contacto, un conjunto de reglas. Se paga con una búsqueda explícita
   en lugar de sugerencias mientras se escribe.
4. **Las coordenadas sí se guardan.** El ADR 0044 las descartó porque los términos de Google no las
   dejan guardar; la licencia ODbL de OpenStreetMap sí. El `envio` gana `latitud` y `longitud`
   (migración `c7a41e9d02f5`, nulables). Viajan juntas o ninguna, y dentro de la caja de Colombia
   (Inteligencia y Comercio responden 400 si no). Solo cruzan las del pin confirmado: de Google nunca.
5. **Son dato personal.** Un domicilio con menores: la supresión del titular las pone en `NULL`, igual
   que el texto de la dirección y el `place_id`.
6. **Mover el pin cambia la orden.** `latitud` y `longitud` entran a `CAMPOS_FIRMA_ENTREGA`: con el
   mismo texto y otro punto no se reutiliza el pendiente, porque despacharía al punto viejo. Editar el
   texto a mano suelta el pin y la localidad, como ya hacía con el `place_id`.
7. **Nada bloquea el pago.** Servicio caído, sin contacto configurado, sin resultados o Leaflet que no
   carga: el campo sigue siendo texto libre y el aviso lo dice. Leaflet solo se carga en el cliente
   (`dynamic`, `ssr: false`) y solo cuando ya hay un resultado elegido.
8. **Accesibilidad y móvil.** Combobox/listbox ARIA como el de Google y el de `/empezar`; estado en
   una región `aria-live`; botón y opciones de al menos 44 px; el mapa mide `clamp(220px, 45vh, 320px)`
   de alto y 100 % de ancho, sin ensanchar el formulario. Atribución "© OpenStreetMap" en la lista de
   resultados y sobre el mapa.
9. **Logística abre el punto exacto.** `enlaceGoogleMaps` usa `latitud,longitud` cuando existen y cae a
   la búsqueda por texto (con `place_id`) si no.

## Alternativas rechazadas

- **Autocompletar por tecla con Nominatim.** Prohibido por su política; el bloqueo de IP dejaría sin
  búsqueda a todos los acudientes.
- **Photon.** Ver el punto 3.
- **Alojar Nominatim propio.** Es infraestructura de un servidor con decenas de GB para un volumen de
  decenas de búsquedas al día.
- **Geocodificar desde el navegador.** La IP y el límite de una petición por segundo serían de cada
  visitante, sin caché compartida ni forma de hacer cumplir la política.
- **`react-leaflet` en `apps/web`.** Un mapa con un pin no justifica la capa; se usa `leaflet` directo.

## Consecuencias

- Hay que definir `TUKIT_NOMINATIM_CONTACTO` en `apps/web/.env.local` (el admin ya lo usa con el
  mismo nombre). Sin él, el checkout queda como antes: texto libre.
- La caché y la cola viven en la memoria de un proceso. Con varias réplicas de `apps/web` el límite
  sería por réplica; para un solo proceso (hoy) es global. Si se escala, pasa a Redis (ADR 0047).
- Las direcciones de pedidos anteriores no tienen punto; logística sigue con el enlace por texto.
- OpenStreetMap no es tan completo como Google en numeración de predio: muchas búsquedas devuelven la
  calle y no el portón. Por eso el paso de confirmar en el mapa es parte de la decisión.
