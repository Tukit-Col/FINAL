# ADR 0040 — La lista que el catálogo no recibe se guarda y se importa después, con una clave de idempotencia

- **Estado:** aceptada
- **Fecha:** 2026-10-19
- **Servicios tocados:** `inteligencia` (`routers/inteligencia.py`, `importaciones`, `trabajador`,
  `trabajos.mis_solicitudes`, `remoto`), `catalogo` (`POST /v1/admin/listas/importar`),
  `libs/ts/tukit-contrato`, `apps/web`
- **Origen:** el hallazgo H-B-01 del nivel 1 de QA de las fases 7 a 9 (corrida
  `20261019-0505-70b9108-f7-9`, escenario CH-04), corregido en la rama `arreglos/h-b-01-03`.

## Contexto

**Con el catálogo caído, la subida del acudiente daba `500` y la lista se perdía.**
`POST /v1/listas/subir` percibe el PDF de cada hijo y después importa cada (colegio, grado, año)
al catálogo con `POST /v1/admin/listas/importar`, las dos cosas dentro de la misma petición. El
`RemotoCaido` del cliente salía sin manejar: lo ya percibido, que es la etapa cara, se perdía, y el
acudiente tenía que volver a subir la lista sin saber si había entrado.

No bastaba con no dar `500`. Hacían falta tres cosas más:

- **guardar lo percibido**, para no volver a llamar al modelo;
- **reintentar solo**, con algo que ya corre, porque el acudiente no va a volver;
- **no duplicar.** Cada `POST` de importación crea una versión nueva. Un reintento después de una
  respuesta que se perdió (el catálogo escribió y la conexión se cortó) daría dos versiones de la
  misma lista. El ADR 0020 ya prohíbe reintentar un `POST` en el transporte y pide idempotencia de
  aplicación.

## Decisión

1. **Ante una caída del catálogo, la subida responde `202` igual.** La petición intenta cada
   destino en orden. En la primera caída transitoria deja de insistir, porque cada intento puede
   costar los 60 s del cliente. Es transitoria una caída sin respuesta, con el circuito abierto, o
   con un 5xx, un 408 o un 429 (`RemotoCaido.transitorio`).
   - Ese destino y los que faltan se guardan como `pendiente` en la tabla nueva
     `importacion_lista` de inteligencia, todos en una sola transacción. Cada fila lleva los
     ítems, la percepción cruda, el PDF, el contacto y las preferencias.
   - El hijo cuyo destino quedó pendiente trae `version_id: null` y `estado: "pendiente"`. Los
     demás traen su `version_id`, como siempre.
2. **Con el catálogo arriba, inteligencia no guarda nada.** La respuesta es la de antes, y la única
   copia de la lista y del PDF es la del catálogo. Una primera versión del arreglo guardaba todo
   antes de llamar al catálogo. Se cambió por dos razones:
   - dejaba en inteligencia una segunda copia de algo que puede traer el nombre de un menor,
     transcrito de la página;
   - hacía depender la subida de la base de inteligencia aun con el catálogo bien.
3. **Reintenta el `inteligencia-trabajador`**, en cada vuelta, con
   `importaciones.reintentar_pendientes`.
   - Toma una fila vencida por vez con `FOR UPDATE SKIP LOCKED`, la reserva dos minutos y llama
     al catálogo fuera de la transacción.
   - Si el catálogo sigue caído, sube `intentos` y corta la vuelta. La fila espera 5 s después
     del primer intento, el doble cada vez y como mucho 5 minutos.
   - Al importarse, la fila queda `importada`, con su `version_id`, y se vacían su carga y su PDF.
   - Un rechazo (otro 4xx) la deja `fallida`, con su diagnóstico, y no se reintenta.
4. **Cada destino lleva una clave de idempotencia, por subida y destino.**
   - `clave_de` deriva un UUID v5 de (`subida_id`, colegio, grado, año). La subida la manda en su
     intento y el reintento manda la misma.
   - El catálogo la guarda en `tarea_importacion.clave_idempotencia`, con un índice único. Si la
     clave ya entró, responde con la tarea y la versión que ya existen, con el mismo cuerpo, y no
     crea otra versión.
   - Si dos intentos con la misma clave entran a la vez, el índice frena al segundo. Su
     transacción entera se deshace y se le responde con lo del primero.
   - Sin clave, el catálogo se comporta como antes.
   - La clave es por subida y no por contenido: un acudiente que vuelve a subir la misma lista
     hace una versión nueva, igual que antes.
5. **El acudiente ve su lista como recibida.**
   - "Mis solicitudes" muestra la pendiente como `recibida`, con `tarea_id: null`, porque todavía
     no hay tarea que cancelar.
   - El portal lleva la cuenta de las diferidas a "Recibimos tu lista". La pantalla le dice al
     acudiente que la lista pasa sola a revisión y que no tiene que volver a subirla.
   - En el contrato TS, `SubidaHecha.version_id` pasa a `string | null` y gana
     `estado?: "pendiente"`.
6. **`POST /v1/admin/onboarding` no difiere: responde `503 servicio_no_disponible`.** El
   formulario del administrador necesita el `version_id` en el acto para pasar a la curaduría, y el
   administrador está mirando y puede volver a intentar. El mensaje dice que la lista no se guardó.

## Alternativas rechazadas

- **Responder `503` también en la subida.** El acudiente tendría que volver más tarde y subir la
  lista otra vez, y no hay sesión que se lo recuerde. Por eso la verificación de caos (CH-04) pide
  `202`.
- **Guardar todo antes de intentar**, como un outbox de la subida. Es la forma más simple de no
  perder nada si el proceso muere a mitad, pero deja en inteligencia una copia de cada lista y de
  su PDF también cuando el catálogo responde, que es casi siempre. Ver la decisión 2.
- **La `bandeja_salida` de inteligencia.** Es para eventos chicos que el repartidor lleva a
  `operacion`. Meter ahí un PDF y una orden de escritura al catálogo mezcla dos cosas y obliga al
  repartidor a hablar con el catálogo.
- **Un `trabajo_pipeline` con un estado nuevo.** La subida del acudiente no crea trabajo a
  propósito: el kit se arma al aprobar la versión. Un trabajo sin kit rompería las vistas que los
  cuentan.
- **Reintentar el `POST` en el transporte, con `tenacity`.** Lo prohíbe el ADR 0020, por la misma
  razón que motiva la clave: un reintento ciego duplica.
- **Una clave por contenido (el hash del PDF).** Dos acudientes del mismo curso que suben el mismo
  PDF compartirían versión y contacto, y uno que corrige su lista y la vuelve a subir no podría.

## Lo que queda abierto

- En la subida, un rechazo del catálogo (un 4xx que no es 408 ni 429) sigue dando `500`, como
  antes, y no se guarda nada.
- Si el proceso muere a mitad de la subida, la lista se pierde, como antes. Lo que se guarda es lo
  que el catálogo no recibió por no responder.
- Una fila que un reintento deja `fallida` conserva su PDF y su carga, para poder diagnosticarla.
  Nadie la purga todavía.
- En el onboarding del administrador, con el catálogo caído, se pierde la percepción de ese
  intento.
- Si un intento entró al catálogo pero su respuesta se perdió, la lista puede verse dos veces en
  "Mis solicitudes" hasta el siguiente reintento: una como `recibida` sin tarea y otra con su tarea.
- Si un administrador borra la versión antes del reintento, el reintento crea una versión nueva.

## Consecuencias

- Tabla nueva `inteligencia.importacion_lista` (migración `6a2f8c4e1d57`). El manifiesto pasa a 73
  tablas y declara la referencia cruzada de su `colegio_id` a `identidad.colegio`.
- Columna nueva `catalogo.tarea_importacion.clave_idempotencia`, con su índice único (migración
  `3e7a1c9d5b62`).
- `RemotoCaido` gana `estado` (el código HTTP, cuando el otro servicio respondió) y `transitorio`.
- Pruebas nuevas:
  - en inteligencia, `test_subida_diferida.py`, `TestOnboardingConElCatalogoCaido`
    (`test_onboarding.py`) y `test_migracion_importacion_lista.py`;
  - en catálogo, `TestImportarConClaveDeIdempotencia` (`test_api_admin.py`) y
    `test_migracion_clave_idempotencia.py`;
  - `test/subida.test.ts` en el contrato y `test/recibimos.test.ts` en el portal.

  `test_subir_listas.py` sigue igual, salvo que su doble del catálogo acepta la clave.
- El contrato pasa a 1.8 (`CONTRATO_API.md`).
