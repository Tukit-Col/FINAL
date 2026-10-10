# Plan — feature/maps-and-feats (puntos 5, 4, 1 y 2)

Rama `feature/maps-and-feats` (desde `feature/integracion-total` @ `a565aeb`). Plan aprobado el 2026-10-10; las casillas
se marcan a medida que cada tarea queda verde.

Línea base confirmada (2026-10-10): `make fronteras` 58 pass / 1 skip, `make prueba` 1507, contrato 9, web 12,
admin 17, `npm run lint` verde.

## Contexto

Son cuatro pedidos (se respeta la numeración del usuario y no hay punto 3):

- **1.** La dirección del checkout se autocompleta con Google Places (New). Además se agregan localidad, indicaciones y `place_id`, y el admin recibe un enlace a Maps.
- **2.** El acudiente tiene una página propia por pedido, `/pedidos/[id]`, con su línea de tiempo calculada en Comercio.
- **4.** El staff puede subir desde `/cola` la lista de cualquier colegio de Bogotá. Si el colegio aún no existe, nace al aprobar la lista.
- **5.** Los colegios muestran logo. El directorio queda en una sola copia dentro de `@tukit/contrato`, cada entrada con `imageURL`.

Hoy pasa lo siguiente:

- El checkout manda solo `{destinatario, direccion, ciudad}`. `EntregaCheckout` descarta cualquier otro campo.
- "Mis pedidos" enlaza a un ancla `#pedido-<id>`.
- `POST /v1/admin/onboarding` exige `colegio_id` y no envía `colegio_datos`.
- El directorio vive solo en `apps/web/public` y no trae logos.

### Hallazgos que cambian el plan

- **CACS.** En la base local NO existe el colegio `bccf0294-…` "Colegio Agustiniano Ciudad Salitre". Lo que hay en `tukit_identidad` es el colegio "Colegio CACS", `17127bcf-9134-58a4-aae4-6a2bc6f7bf32`, con `dane=311001093652` y 14 listas. Esto tiene tres consecuencias:
  - La reconducción por DANE se hace contra el `dane` de los colegios existentes. Si en `/cola` se elige "COLEGIO AGUSTINIANO CIUDAD SALITRE", el sistema reconduce a CACS.
  - El logo de la página de CACS en el admin saldrá del `imageURL` del directorio por DANE, porque CACS tiene `logo_url` nulo.
  - La ruta rápida de `/empezar` del recorrido se hace con CACS.
- **El onboarding de admin no exige staff.** No llama `_exigir_staff`. Queda fuera del alcance y se reporta: el BFF del admin no reenvía token a este endpoint, así que cambiarlo rompería el flujo.

### Logos (verificados con `curl -sIL`: 200 + `content-type: image/png`, y mirados a ojo)

| Colegio | DANE | `imageURL` |
|---|---|---|
| COLEGIO AGUSTINIANO CIUDAD SALITRE | 311001093652 | `https://agustinianosalitre.edu.co/wp-content/uploads/2023/05/cropped-Escudo-Agustiniano-Final.png` |
| COLEGIO AGUSTINIANO NORTE | 311769000751 | `https://agustinianonorte.edu.co/wp-content/uploads/2020/03/cropped-logo-150x150-1.png` |
| COLEGIO AGUSTINIANO SUBA | 311769000661 | `https://agustinianosuba.edu.co/wp-content/uploads/2025/06/cropped-logo-agustinianosuba.png` |
| COLEGIO AGUSTINIANO TAGASTE | 311001109265 | `https://www.agustinianotagaste.edu.co/wp-content/uploads/2020/08/Escudo_CAT.png` |
| COLEGIO AGUSTINIANO DE SAN NICOLAS | 311001010811 | `null` (ver abajo) |

San Nicolás queda en `null` porque no tiene sitio propio. Busqué en agustinosrecoletos.com.co, infoescuelas y direccion.com.co, y solo apareció su página de Facebook, cuyas imágenes están en fbcdn, que está prohibido. Antes de escribir el JSON se vuelven a verificar las cuatro URLs.

## Orden y commits

1. **Base.** Corro `git status` y confirmo la rama y la línea base. Luego guardo este plan en `docs/`.
2. **Commit A, punto 5.** Directorio único con logos y la regla del logo.
3. **Commit B, punto 4.** Subir lista de cualquier colegio desde `/cola`.
4. **Commit C, punto 1.** Google Places en el checkout, localidad e indicaciones, y el admin con Maps.
5. **Commit D, punto 2.** `/pedidos/[id]` con la línea de tiempo.
6. **Commit E, docs.** `CONTRATO_API.md` 1.8, ADR 0039 y 0040, README y `.env.ejemplo`.
7. **Verificación final, recorrido real e informe.** Si hace falta un ajuste, va en un commit de cierre.

En cada commit hago `git add` con rutas explícitas, nunca `.sf/`, y cierro el mensaje con la línea `Co-Authored-By` de rigor.

---

## Tareas

### 0. Base
- [x] Correr `git status` y `git branch --show-current`, y confirmar que solo aparece `?? .sf/`.
- [x] Correr la línea base: `make fronteras`, `make prueba`, `npm run lint` y los tests de contrato, web y admin. Anotar los números.
- [x] Guardar el plan en `docs/superpowers/plans/2026-10-10-maps-and-feats.md`.

### 5. Directorio único y logos (commit A)
- [x] Mover el directorio con `git mv apps/web/public/directorio-colegios.json libs/ts/tukit-contrato/datos/directorio-colegios.json`.
  - Un script de una vez agrega `"imageURL": null` a las 3164 entradas y pone las 4 URLs de arriba.
  - Se escribe con el mismo `json.dumps(..., ensure_ascii=False, indent=0)` de `_main`, para que regenerar no produzca diff.
- [x] En `libs/ts/tukit-contrato/package.json`, exportar `"./directorio-colegios.json"`.
- [x] Crear el módulo puro `libs/ts/tukit-contrato/src/colegios-busqueda.ts`. Solo lleva `import type` de `./catalogo`, porque así lo exige `node --test`.
  - `EntradaDirectorio {dane, nombre, localidad, imageURL: string | null}`.
  - `normalizarBusqueda`, movida desde `FormularioEmpezar`: pliega mayúsculas y acentos.
  - `inicialesColegio`, movida desde `FormularioEmpezar.iniciales`.
  - `imagenesPorDane(directorio)`, que devuelve un `Map`.
  - `logoDeColegio({logo_url, dane}, imagenes)`: primero el `logo_url` de Identidad, luego el `imageURL` por DANE, y si no hay ninguno, `null`. Con `null`, la UI pinta las iniciales.
  - `prepararBusqueda(colegios, directorio)` y `buscarColegios(preparada, consulta, tope = 30)` devuelven `{colegios: {colegio, etiqueta}[], directorio: EntradaDirectorio[]}`. Es la lógica actual del buscador de `/empezar`, igual:
    - Se activa desde 3 letras.
    - Una entrada del directorio cuyo DANE ya es de un colegio pasado como parámetro se reconduce a ese colegio, con la etiqueta compuesta "DIRECTORIO · Tukit".
    - Los colegios que no están en el directorio salen con su nombre.
    - El resto del directorio se corta en 30.
  - Se reexporta desde `indice.ts`.
- [x] Tests en `libs/ts/tukit-contrato/test/colegios-busqueda.test.ts`:
  - normalización;
  - mezcla y orden;
  - reconducción por DANE;
  - tope de 30;
  - menos de 3 letras;
  - iniciales;
  - regla del logo, con `logo_url` gana, `imageURL` por DANE y sin ninguno.
- [x] Crear `src/app/directorio-colegios.json/route.ts` en `apps/web` y en `apps/admin`. Hace `import directorio from "@tukit/contrato/directorio-colegios.json"`, tiene `export const dynamic = "force-static"` y responde con `GET` → `Response.json(directorio)`. Así hay una copia única, ningún import entre apps, y `/empezar` sigue buscando en el navegador.
  - Antes de escribirlo leo `node_modules/next/dist/docs` sobre route handlers estáticos.
- [x] Componente cliente `LogoColegio`, uno por app, porque no se importa entre apps.
  - Rutas: `apps/web/src/components/LogoColegio.tsx` y `apps/admin/src/components/LogoColegio.tsx`.
  - Recibe `src | null`, `nombre` y `className`.
  - Usa `<img>`. Con `onError` cae a las iniciales de `inicialesColegio`.
- [x] Aplicar la regla del logo en `/empezar`:
  - Los aliados con `logoDeColegio`.
  - Las filas del directorio con su `imageURL`.
  - La tarjeta del elegido.
  - `FormularioEmpezar` pasa a usar `prepararBusqueda`/`buscarColegios`. El comportamiento no cambia.
- [x] Aplicar la regla en el admin: `TarjetaColegio` de `/colegios` y la cabecera de `colegios/[colegio]/page.tsx`. Ambas son páginas de servidor, importan el JSON del contrato y calculan `imagenesPorDane`.
- [x] Identidad:
  - `generar_json_busqueda(texto, imagenes: dict[str, str | None] | None = None)` agrega `imageURL` a cada registro.
  - `_main` lee el destino si ya existe y conserva el `imageURL` de cada DANE.
  - Se corrige el nombre del módulo en el docstring.
  - Tests en `servicios/identidad/tests/test_directorio_bogota.py`: los dos casos, con `tmp_path` y `monkeypatch` de `sys.argv`.
- [x] Comprobar que `_main` sobre la fuente y el JSON nuevo reproduce byte a byte el archivo commiteado.
- [x] Borrar la copia de `apps/web/public` (la saca el `git mv`). Verificar que no queda ninguna referencia a la ruta vieja.
- [x] Verde parcial: contrato, web, `make prueba` de identidad, `npm run lint` y typecheck. Hacer el commit A.

### 4. Subir lista de cualquier colegio desde /cola (commit B)
- [x] Inteligencia, en `routers/inteligencia.py`:
  - Extraer de `HijoSubida` la base `ColegioElegido(BaseModel)`. Lleva `colegio_id`, `colegio_dane` y `colegio_nombre`, con los mismos límites de hoy, y el método `resolver_colegio()`, movido sin copiarlo. `HijoSubida` hereda de ella.
  - Extraer el relleno con el DUEB a `async def _completar_con_directorio(colegio_datos)`, y que `subir_listas` lo use.
- [x] `POST /v1/admin/onboarding`:
  - Acepta `colegio_id`, o `colegio_dane` + `colegio_nombre`, o solo `colegio_nombre`. Cualquier campo de más se ignora.
  - Sin colegio responde 422 `colegio_requerido`, campo `colegio`. Un largo inválido responde 422 (`colegio_invalido`).
  - Decisión: la designación se resuelve ANTES de percibir, para no gastar una lectura del PDF en una subida sin colegio. En la ruta del admin, un DANE sin nombre se rechaza (400 `colegio_requerido`), porque la cola no tendría cómo mostrarlo.
  - Resuelve con `ColegioElegido.resolver_colegio()`, completa con `datos_directorio(dane)` y le pasa `colegio_datos` a `importar_lista`. `origen` sigue siendo `onboarding`.
  - Si solo llega `colegio_id`, el comportamiento es idéntico al de hoy.
- [x] Tests en `servicios/inteligencia/tests/test_onboarding.py`, con el doble de catálogo y un `IdentidadDoble` con directorio:
  - DANE: deriva el id y manda `colegio_datos` con los datos del DUEB.
  - Solo nombre: id libre y nombre normalizado.
  - Solo `colegio_id`: sin `colegio_datos`.
  - Sin colegio: 422.
  - Tests unitarios de `resolver_colegio`.
- [x] Catálogo e Identidad: completar los tests que falten para cubrir la cadena "onboarding sin contacto y con `colegio_datos`".
  - `test_api_admin.py`: importar con `origen=onboarding` y `colegio_datos`, que `colegio_nombre` aparezca en la revisión, cerrar, y que salga `colegio_verificado` con `contacto_referencia=None`.
  - `test_poller.py`: con esa carga, se crea el colegio con el nombre elegido, su DANE y la "Sede principal".
  - Se agrega solo lo que no esté ya cubierto.
  - Hecho: el cierre con `colegio_verificado` sin contacto y el alta en el poller ya estaban cubiertos; se agregó en `test_api_admin.py` que el onboarding de un colegio nuevo entra a la cola con su nombre, sin contacto, y la revisión trae `colegio_datos`.
- [x] Contrato:
  - Nuevo tipo `ColegioDesignado = {colegio_id} | {colegio_dane, colegio_nombre} | {colegio_nombre}`.
  - `OrigenDatos.onboarding(colegio: string | ColegioDesignado, …)`. Un string se sigue tratando como `colegio_id`, así que el cambio es compatible.
  - `cliente-http.ts` arma el `FormData` según el tipo.
- [x] Ruta `apps/admin/src/app/api/onboarding/route.ts`:
  - Lee las tres formas y valida que llegue al menos una.
  - Como defensa, reconduce del lado del servidor: si llega `colegio_dane` y un colegio existente tiene ese DANE, manda su `colegio_id`. El helper es puro, en `apps/admin/src/lib/designar-colegio.ts`, con test en `apps/admin/test/`.
- [x] UI, nuevo `apps/admin/src/components/BuscadorColegioOnboarding.tsx`, que reemplaza el `<select>` de `FormularioOnboarding`:
  - Combobox accesible. Carga perezosa de `/directorio-colegios.json`, la ruta del admin.
  - Mezcla todos los colegios de Identidad, marcando "Aliado" o "En Tukit", y luego el directorio con nombre, localidad, DANE y logo.
  - Al final, "No lo encuentro: usar '…' tal cual".
  - Usa `buscarColegios` del contrato.
  - Muestra el elegido con "Cambiar". Los estilos usan tokens, reutilizando `Onboarding.module.css`.
  - `api-onboarding.ts` manda la designación.
- [x] Verde parcial: inteligencia, catálogo, identidad, contrato y admin. Hacer el commit B.

### 1. Google Places en el checkout (commit C)
- [x] Contrato, nuevo `src/localidades.ts`, autocontenido:
  - `LOCALIDADES_BOGOTA`, las 20 con su nombre visible, y el tipo `LocalidadBogota`.
  - `localidadCanonica(texto)`: ignora acentos, mayúsculas, espacios y el prefijo "Localidad de". Así "Santafé" da "Santa Fe".
  - `esBogota(ciudad)`.
  - `direccionDesdeComponentes(componentes: {longText, shortText, types}[])` devuelve `{ciudad, localidad, departamento}`:
    - `ciudad` sale de `locality`, o si no hay, de `administrative_area_level_2`.
    - `departamento` sale de `administrative_area_level_1`.
    - `localidad` solo se llena en Bogotá. Busca, en este orden, en `sublocality_level_1`, `sublocality`, `administrative_area_level_3`, `administrative_area_level_2` y `neighborhood`, y se queda con la primera que case con el catálogo. Si ninguna casa, queda `""`.
  - `enlaceGoogleMaps({direccion, ciudad, google_place_id})`: arma `https://www.google.com/maps/search/?api=1&query=…&query_place_id=…`. Agrega la ciudad a la búsqueda solo si la dirección no la trae, y `query_place_id` solo si hay id.
  - `Entrega` gana los campos opcionales `departamento`, `indicaciones`, `localidad` y `google_place_id`, y `Envio` gana `localidad` y `google_place_id`.
- [x] Tests en `test/localidades.test.ts`:
  - Bogotá con y sin `sublocality`.
  - "Localidad de Chapinero".
  - Acentos y "Santafé".
  - Soacha y Chía, que dan localidad vacía.
  - Componentes faltantes o vacíos.
  - Las 20 localidades.
  - El enlace de Maps con y sin `place_id`.
- [x] Comercio:
  - Migración `servicios/comercio/migraciones/versions/20261010_<hhmm>_envio_guarda_localidad_y_place_id.py`, escrita a mano con la plantilla. `down_revision="a58b45f8b14c"`. Agrega `localidad String(64)` y `google_place_id String(512)`, ambas nullables.
  - En `modelos/entrega.py`, las columnas del `Envio`.
  - `DireccionEntrega` acepta `localidad`, de máximo 64, y `google_place_id`, de máximo 512.
  - `insertar_orden` los guarda con el mismo patrón `getattr`.
  - `_serializar_envio` los serializa.
- [x] Decisión sobre la firma de la orden. `firma_orden` y `contenido_de` comparan `(destinatario, direccion, ciudad, localidad, departamento, indicaciones)`, con `None` igual a `""`.
  - El porqué va en un comentario en `_resolver_pendientes_del_kit` y en `firma_orden`. El envío es una copia congelada (ADR 0015): reutilizar un pendiente con otra localidad u otro apartamento despacharía con datos viejos. Que no case cuesta poco, porque se cancela el pendiente y se crea otro.
  - `google_place_id` queda fuera: apunta al mismo texto de la dirección.
  - Tests en `test_checkout.py`:
    - Misma entrega pero otra localidad: cancela y crea.
    - Igual con localidad: reutiliza.
    - Se guardan y se serializan `localidad`, `place_id` e `indicaciones`.
    - Un largo de más da 422.
- [x] Inteligencia:
  - `EntregaCheckout` agrega los opcionales `departamento`, `indicaciones`, `localidad` y `google_place_id`, con los mismos largos que Comercio.
  - `ordenar_trabajo` usa `model_dump(exclude_none=True)`, así el cuerpo viejo no cambia.
  - En `trabajos.ordenar`, el tipo de `entrega` pasa a `dict[str, str]`.
  - `remoto.py` solo reenvía el cuerpo. Se verifica, sin cambios.
  - Test en `test_trabajos.py`: los campos llegan a Comercio, y sin ellos el cuerpo es idéntico al de hoy.
- [x] Web, `kits/[trabajo_id]/page.tsx`:
  - Lee la llave como `process.env.GOOGLE_MAPS_API_KEY?.trim() || null`, sin `NEXT_PUBLIC_`.
  - La pasa por props a `VistaKits` → `Checkout`.
- [x] Dependencias en `apps/web`: `npm install @googlemaps/js-api-loader` y `npm install -D @types/google.maps`.
  - Toca `apps/web/package.json` y `package-lock.json`.
  - Si no hay red, uso el bootstrap oficial dentro de `lib/places.ts` y declaro los tipos mínimos. Lo anoto como decisión.
- [x] `apps/web/src/lib/places.ts`:
  - `cargarPlaces(llave)`, memoizado. Hace `setOptions({key, v: "weekly", language: "es", region: "CO"})` y luego `importLibrary("places")`.
  - Escucha `window.gm_authFailure` para marcar la llave como inválida.
  - Ante cualquier fallo devuelve `null`. Nunca lanza.
- [x] `apps/web/src/app/kits/[trabajo_id]/CampoDireccion.tsx`, un combobox ARIA:
  - Atributos `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant` y `aria-autocomplete="list"`. Lista con `role="listbox"`.
  - Pide sugerencias desde 3 caracteres, con 250 ms de debounce. Flechas, Enter y Escape.
  - Hay un `AutocompleteSessionToken` por búsqueda. La llamada es `AutocompleteSuggestion.fetchAutocompleteSuggestions({input, sessionToken, includedRegionCodes: ["co"], locationBias: círculo de Bogotá, language: "es", region: "co"})`.
  - Al elegir: `toPlace().fetchFields({fields: ["formattedAddress", "addressComponents"]})`. Fija la dirección y aplica `direccionDesdeComponentes`. Después se crea un token nuevo.
  - Editar el texto después borra el `place_id`.
  - La atribución es el texto "Google Maps" con `translate="no"` al pie de la lista. Lleva el color que Google exige, con un comentario de por qué no es un token.
  - Sin llave, o si Google falla, el campo es un `<input>` libre, y un fallo de Google jamás bloquea el pago.
- [x] Checkout en `VistaKits.tsx`. Los campos quedan así:
  - Recibe.
  - Dirección.
  - "Apartamento, torre, interior o indicaciones", opcional, que va a `indicaciones`.
  - Ciudad, editable.
  - Localidad: un `<select>` con las 20. Es obligatorio si `esBogota(ciudad)`; fuera de Bogotá se vacía y se deshabilita.
  - Departamento, editable y opcional.

  `pagar` manda todo. Los estilos van en `Kits.module.css`, con tokens.
- [x] Admin, `logistica/[pedido]/page.tsx`:
  - Dirección con el enlace "Ver en Google Maps" (`enlaceGoogleMaps`, `target="_blank" rel="noopener noreferrer"`).
  - Filas de Localidad y Ciudad.
  - En el tablero `/logistica`, la `FilaPedido` muestra la localidad.
- [x] `apps/web/.env.local`: agregar al final solo la línea `GOOGLE_MAPS_API_KEY=`. Hago `tail -c1` antes y no toco nada más.
- [x] Verde parcial: comercio, inteligencia, contrato, web, typecheck y lint. Luego `make bd-migrar` y `make bd-deriva`, con `TUKIT_DB_HOST=127.0.0.1`. Hacer el commit C.

### 2. Página del pedido (commit D)
- [x] Comercio, nuevo `dominio/linea_de_tiempo.py`, una función pura:

  ```
  linea_de_tiempo(estado, creado_en, pagos, historial, envio, ahora) ->
    {
      pasos: [{paso, estado: hecho|actual|futuro, fecha|None, repartidor_nombre?}],
      especial: None | {tipo: "incidencia", tipo_incidencia, fecha} | {tipo: "cancelado", fecha},
      entrega_estimada,
      pago_pendiente: None | {vence_en, vencido},
    }
  ```

  - Los pasos son `creado`, `pagado`, `en_preparacion`, `despachado`, `en_reparto` y `entregado`.
  - La posición es el estado actual.
    - En `incidencia`, es el `estado_desde` de la última incidencia del historial.
    - En `cancelado`, es el `estado_desde` de la última cancelación del historial. Si no hay una, la posición es `pagado` cuando hubo un pago aprobado o reembolsado, y `creado` cuando no.
  - Los pasos hasta la posición son `hecho`, el de la posición es `actual` y los demás son `futuro`, sin fecha.
  - Así no es lineal: tras `incidencia → en_preparacion`, los pasos posteriores vuelven a `futuro`.
  - Fechas, sin inventar ninguna:
    - `creado` usa `pedido.creado_en`.
    - `pagado` usa el `actualizado_en` del pago aprobado.
    - El resto usan la última entrada del historial que llega a ese estado.
    - `entregado` cae a `envio.entregado_en` si el historial no la trae.
    - Si no hay dato, la fecha va en `None`.
  - El paso de despacho lleva solo `repartidor_nombre`.
  - `pago_pendiente` sale de `VIGENCIA_PAGO` y `vencido`.
  - Por construcción, la función nunca recibe `actor_*`, `nota` ni el celular.
- [x] Tests en `tests/test_dominio_linea_de_tiempo.py`:
  - cada estado;
  - incidencia en reparto y vuelta a preparación;
  - cancelado con y sin historial;
  - pendiente vigente y vencido;
  - fechas nulas;
  - que el despacho solo traiga el nombre.
- [x] Repositorio: `vistas_para_linea_de_tiempo(pedido_id)` (pagos, historial y envío recortados en el SELECT). `ver_mi_pedido` agrega `linea_de_tiempo` y no quita nada.
  - Tests de endpoint en `test_checkout.py` o `test_logistica.py`, avanzando con el staff hasta `despachado` con nota y celular:
    - el acudiente ve la línea de tiempo;
    - el JSON no contiene `actor_id`, `actor_correo`, la nota ni el celular;
    - un pedido ajeno da 404;
    - sin token, 401.
- [x] Contrato:
  - Tipos `PasoLineaDeTiempo`, `LineaDeTiempoPedido` y `PedidoDelAcudiente = Pedido & {linea_de_tiempo}` en `comercio.ts`.
  - `miPedido` devuelve `PedidoDelAcudiente` en `origen.ts` y `cliente-http.ts`.
  - `ETIQUETA_PASO_PEDIDO`.
- [x] Web, componentes compartidos:
  - Extraer `Resumen` y `Entrega` de `ResultadoPago.tsx` a `apps/web/src/components/pedido/ResumenPedido.tsx` y `EntregaPedido.tsx`, con sus estilos movidos a un módulo propio.
  - `ResultadoPago` los usa. `Entrega` muestra también la localidad y las indicaciones.
- [x] Web, `app/pedidos/[pedido_id]/`:
  - `page.tsx` con `force-dynamic`. Sin sesión, `redirect("/ingresar?destino=/pedidos/<id>")`. Si es ajeno o no existe, `notFound()` y su propio `not-found.tsx`.
  - `LineaDeTiempoPedido.tsx` va primero. Es una `<ol>` vertical; el paso actual lleva `aria-current="step"` y los futuros se ven atenuados.
    - Las fechas se muestran en es-CO con zona America/Bogota.
    - Los bloques especiales muestran la incidencia (`ETIQUETA_TIPO_INCIDENCIA`) o el cancelado.
    - Muestra la entrega estimada.
    - Si el pago está pendiente, muestra `AccionesPedido` con `vencido` tal como viene del backend, y dice si ya venció.
  - Luego van el resumen, el método de pago y la entrega.
  - Los estilos usan tokens.
- [x] Dashboard:
  - Las filas de "Mis pedidos" enlazan a `/pedidos/<id>` con un stretched link. `AccionesPedido` queda por encima, en `z-index`, y no se anidan botones dentro de enlaces.
  - "Ver mi pedido" e "Ir a pagar" en solicitudes, y los enlaces de `ResultadoPago`, van a `/pedidos/<id>`.
- [x] Verde parcial: comercio, contrato y web. Hacer el commit D.

### Docs (commit E)
- [x] `arquitectura/CONTRATO_API.md`:
  - Sube a 1.8, con la tabla "Qué cambió en 1.8".
  - Documenta `envio.localidad` y `envio.google_place_id`, `entrega` ampliada en checkout y órdenes, `linea_de_tiempo` en `GET /v1/comercio/mis-pedidos/{id}`, y las tres formas de colegio en `POST /v1/admin/onboarding`.
  - Documenta `imageURL` del directorio y `/directorio-colegios.json` en las dos apps.
- [x] ADR 0039 "Direcciones con Google Places (New)", en formato Nygard. Cubre:
  - la llave de servidor pasada como prop;
  - la degradación a campos manuales;
  - lo que se guarda: `place_id` sí, coordenadas no, por los términos de Google;
  - las sesiones y los campos Essentials;
  - las cuotas y el presupuesto.
- [x] ADR 0040 "Alta de colegios no aliados desde la cola". Cubre el directorio como fuente única en el contrato, la regla del logo y la reconducción por DANE. Agrego las dos filas en `arquitectura/adr/README.md`.
- [x] README, sección frontend: qué es `GOOGLE_MAPS_API_KEY`, qué APIs requiere y cómo restringirla. `apps/web/.env.ejemplo` lleva la línea comentada.
- [x] Hacer el commit E.

### Verificación final
- [ ] Revisar `git diff feature/integracion-total...HEAD` buscando:
  - datos de staff que lleguen al acudiente;
  - URLs de backend en el navegador;
  - campos de Places que no sean Essentials;
  - `console.log` o código muerto;
  - textos sin tilde;
  - estilos sin tokens.
- [ ] Correr todos los comandos de "hecho": `make fronteras`, `make prueba`, ruff check y format, typecheck (antes borro `.next`), lint, los tests de contrato, web y admin, `bd-migrar`, `bd-deriva` y `make humo`.
- [ ] Recorrido real: `make arriba`, `npm run dev:web` y `npm run dev:admin`, con el navegador o por HTTP.
  - (1) Checkout manual sin llave hasta `/pago/simulado`, por la ruta rápida de `/empezar` con CACS.
  - (2) `/dashboard` lleva a `/pedidos/<id>`.
  - (3) Avanzar desde `/logistica` cambia la línea de tiempo.
  - (4) El admin ve dirección, localidad, ciudad y el enlace de Maps.
  - (5) Subir desde `/cola` una lista de un colegio del directorio que no exista, con una imagen inventada de un solo grado. Entra con su nombre y aparece `CompletarColegio`. Luego "Borrar versión", sin aprobar.
  - (6) Logo en una página Agustiniano.
  - Al final, `make abajo`, apago los dev servers y confirmo que `git status` queda limpio salvo `.sf/`.
- [ ] Escribir el "Informe final" en el plan y como último mensaje.

## Decisiones tomadas solas
- **La localidad se guarda con su nombre canónico visible.** El backend solo valida el largo: un checkout viejo tiene que seguir cerrando, y la regla de que sea obligatoria en Bogotá vive en el frontend.
- **Firma de la orden.** Compara todos los campos congelados del envío (`CAMPOS_FIRMA_ENTREGA` en `dominio/pagos.py`: destinatario, dirección, ciudad, localidad, departamento, indicaciones, teléfono y documento), salvo `place_id`, con `None` igual a `""`. Teléfono y documento entraron aunque el plan no los nombraba: reutilizar un pendiente con otro teléfono despacharía con el dato viejo.
- **Un largo de más en Comercio da 400, no 422.** Es la convención de la casa para errores de cuerpo en Comercio; el test lo afirma así.
- **`@types/google.maps` quedó en 3.66.5.** La 3.66.6 es más joven que la política de antigüedad de npm y la instalación la rechazó.
- **Sin llave no se carga nada de Google.** La librería se pide al primer foco del campo de dirección, no al abrir el checkout; si Google rechaza la llave (`gm_authFailure`), el campo vuelve a ser texto libre.
- **Al elegir una sugerencia**, lo que Google no trajo (ciudad o departamento) conserva lo que el acudiente ya había escrito; la localidad siempre se reemplaza, y si no casa queda vacía para elegirla del desplegable.
- **`make bd-deriva` reporta deriva ajena en inteligencia (3) y operación (6).** Son objetos de `d0c19b0` (`mejoras/seguridad-ortografia-carrusel`) en la base compartida; arreglarlos exige `DROP`, que está prohibido. Comercio, catálogo e identidad salen sin deriva.
- **El enlace de Maps agrega la ciudad** cuando la dirección escrita a mano no la trae.
- **La reconducción por DANE se hace dos veces.** Una en el buscador, que es puro, y otra en la ruta del admin.
- **Auth del onboarding.** No se agrega `_exigir_staff`; se reporta.
- **San Nicolás queda con logo `null`.**
- **El directorio vive en `libs/ts/tukit-contrato/datos/`** y se sirve con un Route Handler estático en cada app. Las páginas de servidor importan el JSON y las funciones puras lo reciben por parámetro.
- **En `/empezar` el buscador sigue recibiendo solo los aliados**, como hoy. En `/cola` recibe todos los colegios de Identidad.
- **Un pedido cancelado no tiene paso en curso.** Los pasos alcanzados quedan hechos y el resto en futuro; el bloque "cancelado" lo explica.
- **Cancelados sin fecha.** El historial solo lo escriben los avances del staff; el webhook, el barredor y el retracto no dejan fila. Un cancelado por vencimiento o retracto sale con `fecha: null` y la UI no muestra fecha.
- **"Pago confirmado" solo toma la fecha de un pago aprobado.** El `actualizado_en` de uno reembolsado es la fecha del reembolso.
- **Un paso alcanzado sin fecha dice "Sin fecha registrada"**, para pedidos movidos antes de que existiera el historial.
- **Ajeno, inexistente o id que no es UUID dan el mismo not-found**, para no confirmar que un id ajeno existe. Una sesión vencida (401) vuelve a `/ingresar?destino=/pedidos/<id>`.
- **La fila de "Mis pedidos" es un stretched link** sobre el código del pedido; `AccionesPedido` sigue en su propia fila, fuera del enlace. El ancla `#pedido-<id>` se conserva.
- **En el resultado del pago, "Rechazado" también lleva a `/pedidos/<id>`** (antes iba al panel), donde están las acciones de pagar y cancelar.

## Verificación
Comandos del bloque "hecho", con su salida real. El recorrido de las seis pruebas va con el navegador; si no está disponible, con HTTP (`curl` a las rutas Next y a los servicios), y lo declaro así en el informe.
