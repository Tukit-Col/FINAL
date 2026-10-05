# GAPS_UI — hallazgos del recorrido manual por la UI (modo `api`, backend vivo)

Recorrido con backend real (`make backend`, gateway :8010), frontends en modo
`api` (`apps/{web,admin}/.env.local` → `TUKIT_API_URL=http://127.0.0.1:8010`),
y los tres usuarios sembrados (`demo1234`). Cada entrada:
**ruta · persona · esperado · observado · severidad · causa (archivo:línea)**.

Esto captura huecos **UX/comportamiento** encontrados haciendo clic. Es
distinto de los *flags de divergencia de documentación* (ver abajo del todo),
que son afirmaciones de la tesis que el código invalida.

---

## Estado del entorno (baseline)

- Backend: los 6 procesos responden `arriba: true` (identidad :8011, catálogo
  :8012, inteligencia :8013, comercio :8014, operación :8015, gateway :8010).
- Login por gateway (`POST /v1/sesiones`): **200** para los tres perfiles
  (`mama@ejemplo.com`, `operador@tukit.co`, `rectoria@colegio.edu.co`).
- Frontend web (:3000): **200**, arranca en modo `api`.
- Frontend admin (:3001): **500** en la home — ver G-01.

---

## G-05 — El selector de colegio mostraba 1 de 17 colegios  ✅ ARREGLADO

- **Ruta/pantalla:** `/empezar` (web) y `/onboarding`, `/colegios` (admin).
- **Persona:** Acudiente y Operador/Admin.
- **Esperado:** el acudiente ve su colegio para subir el archivo aunque no sea
  aliado; el onboarding del admin ve sobre todo los NO aliados.
- **Observado:** el selector listaba **1 de 17** colegios (solo "Colegio Bahia
  Solano", el único con una lista revisada). Sin poder elegir colegio, la ruta
  "subir archivo" nunca se alcanzaba → **no salían los chips de grado ni el
  formulario "Sugerir mi colegio"** (G-04 y la queja del recorrido eran, en
  realidad, ESTE bug aguas arriba). El onboarding del admin quedaba casi vacío.
- **Causa (probada con datos):** `cliente-http.ts::colegios()` derivaba los
  grados de `/v1/listas?revisada=true` **y además filtraba fuera** todo colegio
  con `grados.length === 0` (`.filter((c) => c.grados.length > 0)`). Como la
  semilla deja casi todas las listas sin revisar (1 revisada en el backend), el
  filtro escondía 16 colegios. Contradecía el propósito de la ruta de archivo,
  que existe justo para el colegio aún no aliado, y difería del modo `simulado`
  (que no filtra). El onboarding del admin lo dice explícito en su comentario:
  "es_partner aquí escondería los que más falta hacen".
- **Arreglo aplicado:** se elimina el `.filter(...)` en `colegios()`; se
  devuelven **todos** los colegios. `es_partner` (= `grados.length > 0`) sigue
  distinguiendo aliado de no aliado para las etiquetas. En `/empezar` la
  etiqueta ahora dice "Sin lista verificada · sube el archivo" para los no
  aliados en vez de "0 grados verificados". Verificado en vivo: el SSR de
  `/empezar` renderiza los 17 colegios (antes 1). Typecheck del contrato limpio.

---

## G-06 — "Deja seleccionar dos personajes" era caché del navegador, NO el código  ✅ SIN CAMBIO DE CÓDIGO

- **Ruta/pantalla:** `/empezar`, selector de personaje.
- **Persona:** Acudiente.
- **Observado:** la rejilla de personajes dejaba marcar dos a la vez.
- **Investigación (método sistemático, evidencia > suposición):**
  1. El `git diff` confirma que la lógica de selección única (`soloPedidos`)
     está en disco: `siguiente = yaEsta ? soloPedidos : [...soloPedidos, nombre]`.
  2. El **chunk servido por el dev server** (`curl` a
     `/_next/static/chunks/_1bkvjay._.js`) contiene esa misma lógica (3
     ocurrencias de `soloPedidos`/`surtidosSet`).
  3. Los datos reales del backend (`/v1/catalogo/personajes`) dan 8 franquicias
     surtidas, **todo minúscula, sin duplicados** tras `toLowerCase()`.
  4. Réplica en Node de la lógica servida contra esos datos reales: **nunca**
     hay más de una ficha activa en la rejilla; al tocar otra, la anterior se
     reemplaza.
- **Causa (probada):** el navegador corría un **bundle viejo** (la versión
  pre-arreglo con `[...elegidos, nombre]`, que sí acumulaba). Los `WebSocket …
  /_next/hmr failed` que salían en consola explican por qué la pestaña nunca
  recibió el hot-update. Reiniciar el server no refresca una pestaña con JS
  viejo en caché.
- **Arreglo:** **hard-refresh** de la pestaña (⌘⇧R) o cerrar y reabrir. No hay
  cambio de código: el que hay ya es correcto. (Lo mismo aplica al síntoma "la
  ficha se queda grande": el `clearProps`/`overwrite` ya están en el código
  servido; era el mismo bundle viejo.)

---

## G-08 — El back-office (admin) no tenía forma de cerrar sesión  ✅ ARREGLADO

- **Ruta/pantalla:** toda la app admin (:3001), donde aterrizan operador y admin.
- **Persona:** Operador / Admin.
- **Esperado:** poder cerrar sesión desde el back-office.
- **Observado:** no se podía salir. La app admin **no tenía ningún mecanismo de
  logout**: sin `SalirBoton`, sin ruta `/api/sesion`, sin lectura de cookie.
  `CabeceraAdmin` era pura navegación y `layout.tsx` no tocaba la sesión.
- **Investigación (evidencia > suposición):**
  1. La web (:3000) sí cierra bien (verificado en vivo: login 200, `DELETE
     /api/sesion` → 200, `Set-Cookie tukit_sesion=; Expires=1970`).
  2. El backend `POST /v1/sesiones/cierre` devuelve **204** y es correctamente
     **sin estado** (ADR 0016: el token es autocontenido, la cookie la borra
     quien la puso). **No hay bug en el microservicio de identidad.**
  3. El dir `apps/admin/src/app/api` tenía catalogo/colegios/listas/onboarding/
     productos/trabajos, pero **ninguna ruta `sesion`**. Ese era el hueco.
- **Causa:** la cookie `tukit_sesion` es httpOnly (el cliente no puede borrarla
  solo) y la pone la web al entrar; al saltar al back-office (:3001, otro
  origen) viaja, pero el admin nunca tuvo el DELETE que la borra de su lado.
- **Arreglo aplicado (espeja el patrón verificado de la web):**
  - `apps/admin/src/lib/sesion.ts` — `COOKIE_SESION = "tukit_sesion"` (mismo
    nombre que la web, o el DELETE no encontraría la cookie del otro origen).
  - `apps/admin/src/app/api/sesion/route.ts` — `DELETE` lee la cookie, llama
    `cerrarSesion(token)` en try/catch (idempotente), borra la cookie y
    devuelve `{ok:true, url}` con el destino de retorno.
  - `urlWeb()` nuevo en `contrato/servidor.ts` (simétrico a `urlAdmin()`): el
    destino de salida es el login de la web (`:3000/ingresar`). Se resuelve en
    el servidor porque el back-office no expone URLs `NEXT_PUBLIC_`.
  - `apps/admin/src/components/SalirBoton.tsx` — botón de cliente; `DELETE
    /api/sesion` y luego `window.location.href = url` (salto cross-origin, no
    el router de Next). Montado en `CabeceraAdmin` a la derecha de la nav.
  - Verificado en vivo: login 200 → `DELETE :3001/api/sesion` → **200**,
    `{ok:true, url:"http://localhost:3000/ingresar"}`, `Set-Cookie
    tukit_sesion=; Expires=1970`. Typecheck admin limpio.

---

## G-00 — Next 16 bloquea los recursos de dev fuera de `localhost`  ✅ ARREGLADO

- **Ruta/pantalla:** toda la app web (:3000) y admin (:3001) al entrar por
  `127.0.0.1` o la IP de red.
- **Persona:** todas.
- **Esperado:** las animaciones GSAP corren y los controles de cliente
  (chips de colegio/grado, selector de personaje) responden.
- **Observado:** `WebSocket ... /_next/hmr failed` en bucle y
  `Blocked cross-origin request to Next.js dev resource /_next/hmr`. El JS de
  cliente no cargaba → la línea de tiempo de la portada no animaba y NADA
  interactivo respondía (elegir colegio no revelaba los grados, no se podían
  tocar los personajes).
- **Severidad:** **alta** — rompía toda la interactividad en pruebas locales.
- **Arreglo:** `allowedDevOrigins: ["127.0.0.1"]` en `apps/web/next.config.ts`
  y `apps/admin/next.config.ts`. Requiere **reiniciar** `next dev`. Solo afecta
  al servidor de desarrollo; no toca producción.

---

## G-01 — La consola de revisión (admin) no abre en modo `api`  ✅ ARREGLADO

- **Ruta/pantalla:** `/` (cola de revisión), app admin :3001
- **Persona:** Operador
- **Esperado:** la cola lista los trabajos en `espera_revision` para revisar.
- **Observado:** HTTP 500 — `TypeError: entradas is not iterable`
  (`apps/admin/src/app/page.tsx:28`, dentro de `ordenar()`).
- **Severidad:** **alta** — bloquea toda la app de admin en modo `api`; no se
  puede caminar ni Operador ni buena parte del panel institucional.
- **Causa (contrato desalineado, no un bug del backend):**
  - Backend `GET /v1/admin/cola` devuelve
    `{total, pagina, por_pagina, trabajos:[{trabajo_id, estado, creado_en, hijos, lineas_a_revisar}]}`
    (verificado por gateway y directo a :8013, ambos **200**).
  - El tipo del contrato `ColaAdmin` espera
    `{entradas:[{trabajo_id, estado, recibido_en, hijos, lineas_pendientes, lineas_totales, colegios, grados}]}`
    (`libs/ts/tukit-contrato/src/contrato.ts:315-328`).
  - El cliente HTTP hace *cast* del JSON crudo a `ColaAdmin` **sin normalizar**
    (`libs/ts/tukit-contrato/src/cliente-http.ts:455-457`), a diferencia de
    otros métodos que sí normalizan (`trabajoAdmin`, `producto`). Resultado:
    `entradas === undefined` → el spread `[...entradas]` revienta.
  - Campos que el backend no entrega y la tabla consume: `recibido_en`
    (=`creado_en`), `lineas_pendientes` (=`lineas_a_revisar`), y `lineas_totales`,
    `colegios`, `grados` (no existen en la respuesta de la cola).
- **Arreglo aplicado:** se normaliza en `cliente-http.ts::cola()` mapeando la
  forma del backend a `ColaAdmin` (igual que `trabajoAdmin`/`producto`), en vez
  del cast crudo que dejaba `entradas` undefined. `colegios`/`grados`/
  `lineas_totales` no viajan en la cola —viven en catálogo y unirlos aquí
  cruzaría la frontera de servicios—, así que se reportan vacíos en vez de
  fingir el dato; `lineas_pendientes` = `lineas_a_revisar`. Typecheck admin
  limpio, home :3001 → 200.

---

## G-02 — "estuche" resuelve a *kit de artes*, no a *cartuchera*  ⚠️ curaduría

- **Ruta/pantalla:** flujo del acudiente (emparejamiento), vía
  `POST /v1/catalogo/emparejar`
- **Persona:** Acudiente
- **Esperado:** el sinónimo documentado "estuche" → **C009 cartuchera**
  (el concepto existe y empareja perfecto: `parecido≈1.13`).
- **Observado:** "estuche" y "estuche escolar" → **C070 kit de artes**
  (`parecido≈0.90`), estado `reconocido`. El canal semántico **sí dispara**
  (con `GEMINI_API_KEY` puesto), pero el vecino más cercano por embedding es el
  concepto equivocado.
- **Severidad:** **media** — no rompe el flujo (resuelve a *algo*), pero
  empareja mal un caso documentado; afecta la calidad del kit del acudiente.
- **Causa:** curaduría/embeddings, **no** el pipeline. Tras el arreglo de
  Parte A el canal semántico está vivo (el `producto_id`, `imagen_url`,
  `unidad_base` ahora llegan poblados en la respuesta, cosa que el `_indice`
  lisiado anterior no hacía). El sinónimo estuche→cartuchera vive en
  `descubrir.py` pero el embedding del renglón cae más cerca de C070. Revisar
  el texto de embedding de C009/C070 o reforzar el ancla léxica del sinónimo.

---

## G-03 — El sembrado de acceso no es idempotente ante filas legacy  ⚠️ operativo

- **Ruta/pantalla:** N/A (script de arranque `tukit_identidad.sembrar_acceso`)
- **Persona:** operador de despliegue
- **Esperado:** re-sembrar deja las 6 cuentas demo con clave `demo1234`
  (el docstring promete "idempotente, `ON CONFLICT DO UPDATE`").
- **Observado:** `IntegrityError: duplicate key ... usuario_correo_key
  (correo)=(papa@ejemplo.com) already exists`. El upsert conflictúa por `id`
  (`ON CONFLICT (id)`), pero una fila legacy tenía el mismo `correo` bajo un
  `id` **aleatorio** (pre-`derivar()`). Como el INSERT es un lote atómico, la
  colisión de `correo` revirtió TODO el lote: ninguna cuenta quedó con la clave
  fresca, y el login daba **401**.
- **Severidad:** **media** — un entorno con datos previos no puede re-sembrar
  credenciales; el login queda roto silenciosamente.
- **Resuelto en este entorno:** se borró la fila legacy (`DELETE ... WHERE
  correo='papa@ejemplo.com'`; FKs a `usuario.id` son `ON DELETE CASCADE`) y se
  re-sembró — las 6 cuentas ahora entran con **200**.
- **Arreglo sugerido:** en `sembrar_acceso.py:152-159`, añadir
  `on_conflict_do_update(index_elements=["correo"], ...)` además del de `id`, o
  derivar el `id` del correo de forma estable (ya lo hace `derivar("usuario",
  correo)` — el problema es solo la fila legacy con id aleatorio).

---

## G-04 — Casi ningún colegio muestra grados en `/empezar`  ℹ️ POR DISEÑO (dato)

- **Ruta/pantalla:** `/empezar`, paso 1, ruta "Usar la lista que ya tiene el
  colegio".
- **Persona:** Acudiente.
- **Observado:** al elegir un colegio no aparecen chips de grado (salvo Bahia
  Solano · "Once").
- **Causa (no es bug):** `cliente-http.ts::colegios()` deriva los grados SOLO
  de `/v1/listas?revisada=true` —la ruta rápida a optimización solo aplica a
  listas verificadas por una persona—. La semilla deja **1 de 178** listas
  revisadas, así que solo ese colegio/grado habilita la ruta "lista oficial".
- **Camino correcto (confirmado por el usuario):** dejar todo en
  `revisada=false` y entrar por **"Subir el archivo que me mandaron"**, que
  además ofrece el bloque "Sugerir mi colegio" (colegio+grado en un formulario
  antes de enviar). Para habilitar un grado por la ruta oficial se revisa una
  versión con `make bd-revisar ARGS='--revisar <version>'`.

---

## G-05 — En "subir archivo" no había forma de elegir el grado  ✅ ARREGLADO

- **Ruta/pantalla:** `/empezar`, paso 1, ruta "Subir el archivo que me mandaron".
- **Persona:** Acudiente.
- **Observado:** al elegir un colegio sin listas verificadas no aparecían chips
  de grado, así que no se podía fijar el grado ni habilitar "Sugerir mi colegio"
  (que está bloqueado hasta tener colegio+grado). Solo funcionaba con el único
  colegio revisado.
- **Causa:** el bloque de grado se pintaba solo con `colegio.grados` (grados
  VERIFICADOS). En la ruta de archivo el grado no depende de eso: sale del PDF.
- **Arreglo:** en `FormularioEmpezar.tsx` el bloque de grado ahora ofrece
  `GRADOS_CANONICOS` (nueva constante client-safe en `contrato.ts`, deduplicada
  con la copia que ya tenía `cliente-http.ts`) cuando la entrada es "archivo", y
  los grados verificados cuando es "lista oficial". Cambiar de ruta resetea el
  grado (verificados ⊂ canónicos).

---

## G-06 — El selector de personaje dejaba elegir varios  ✅ ARREGLADO

- **Ruta/pantalla:** `/empezar`, paso 1, selector de personaje.
- **Persona:** Acudiente.
- **Observado:** se podían marcar dos franquicias surtidas a la vez.
- **Causa:** `alternar` acumulaba en una lista (multi-select). El kit Fan se
  arma alrededor de UN personaje (`optimizador.recomendar`).
- **Arreglo:** en `SelectorPersonaje.tsx`, tocar una ficha reemplaza la elección
  de la rejilla en vez de sumar (single-select); los pedidos escritos a mano
  siguen aparte.

---

## G-07 — La ficha de personaje se quedaba grande al deseleccionar  ✅ ARREGLADO

- **Ruta/pantalla:** `/empezar`, paso 1, selector de personaje.
- **Persona:** Acudiente.
- **Observado:** al deseleccionar, la ficha no volvía a su tamaño.
- **Causa:** la animación de entrada `gsap.from(..., {scale:0.8})` dejaba un
  `transform` inline en cada ficha que pisaba el estado en reposo del CSS.
- **Arreglo:** `clearProps: "transform"` al final de la animación de entrada,
  para devolver el control del reposo/hover al CSS (`.fichaActiva` es lo único
  que marca la selección).

---

## G-09 — "Pagar" se quedaba en *Llevándote a la pasarela…*  ✅ ARREGLADO

- **Ruta/pantalla:** `/kits/[trabajo_id]`, formulario "¿A dónde te lo llevamos?".
- **Persona:** Acudiente.
- **Esperado:** al pulsar **Pagar** se abre la pasarela de pago.
- **Observado:** el botón cambiaba a "Llevándote a la pasarela…" y no pasaba nada más.
- **Causa:** con `WOMPI_MODO=falso` la pasarela devolvía como "url de pago" la misma
  página del kit; con `sandbox`, `WompiSandbox.crear_transaccion` llamaba a
  `POST /v1/transactions` de Wompi sin medio de pago, que Wompi rechaza.
- **Arreglo aplicado:** rama `feature/pagos-wompi-sandbox`. Hoy el pago se abre con el
  widget de Wompi y el modo falso lleva a `/pago/simulado`. Contrato §9; ADR 0033.

---

## G-10 — El checkout de Wompi responde 403 si el retorno es `localhost`  ✅ ARREGLADO

- **Ruta/pantalla:** `checkout.wompi.co/p/?…`, al salir del kit.
- **Persona:** Acudiente.
- **Esperado:** el checkout alojado de Wompi abre y, al pagar, devuelve a Tukit.
- **Observado:** 403 de CloudFront ("Request blocked") en el navegador.
- **Causa (probada parámetro por parámetro):** el único que lo dispara es `redirect-url`
  apuntando a `localhost`, `127.0.0.1` o una IP privada, codificado o no. Un dominio
  público, incluido uno de túnel, pasa.
- **Arreglo aplicado:** se cambió al widget de Wompi, que abre el pago en un modal y no
  necesita salir de Tukit. Se probó antes un túnel (`cloudflared`) y se retiró. ADR 0033.

---

## G-11 — Después de pagar con PSE no había cómo volver a Tukit  ✅ ARREGLADO

- **Ruta/pantalla:** `transaction-redirect.wompi.co/check`, tras el banco.
- **Persona:** Acudiente.
- **Esperado:** al terminar en el banco, volver a Tukit y ver el resultado.
- **Observado:** el comprobante de Wompi ("¡Pago aprobado!") sin botón para regresar. En
  Tukit el pedido seguía `pendiente_pago`, aunque Wompi lo había aprobado.
- **Causa:** PSE se lleva la pestaña entera al banco (el widget hace
  `window.location.href = url`), así que el modal y su aviso a la página se pierden. Sin
  `redirectUrl`, Wompi no tiene a dónde devolver.
- **Arreglo aplicado:** los datos del widget llevan `redirectUrl` a `/pago/resultado`, y esa
  página confirma con el servidor. El pedido varado de la prueba se confirmó a mano con
  `POST /v1/pagos/{id}/sincronizar`.

---

## G-12 — El modal de Wompi se quedaba cargando  ✅ ARREGLADO

- **Ruta/pantalla:** `/kits/[trabajo_id]` y "Mis pedidos" en `/dashboard`.
- **Persona:** Acudiente.
- **Esperado:** al pulsar Pagar se abre el formulario de Wompi.
- **Observado:** velo oscuro con el indicador girando, sin fin.
- **Causa:** el widget, por omisión, mete toda su configuración en la URL de su iframe
  (`bootstrapTransport: "query"`). Desde G-11 esa configuración lleva un `redirectUrl` a
  `localhost`, y el CDN de Wompi responde 403 (G-10): el iframe no carga nunca.
- **Arreglo aplicado:** el widget se abre con `bootstrapTransport: "postmessage"`
  (`apps/web/src/lib/wompi.ts`), fijado por `apps/web/test/wompi.test.ts`. Lo introdujo el
  arreglo de G-11 y se encontró al día siguiente.

---

## G-13 — Las acciones de "Mis pedidos" no cabían en la tarjeta  ✅ ARREGLADO

- **Ruta/pantalla:** `/dashboard`, sección "Mis pedidos".
- **Persona:** Acudiente.
- **Esperado:** Pagar, Rearmar kit y Cancelar a la vista en cada pedido pendiente.
- **Observado:** la quinta columna se apilaba en vertical y se cortaba por la derecha
  ("Venc…", "Rea…", "Can…").
- **Causa:** cinco columnas no caben en el ancho de la tarjeta del panel.
- **Arreglo aplicado:** la tabla vuelve a cuatro columnas; las acciones van en una franja a
  todo el ancho bajo el pedido, y "Vencido" pasa a la columna Estado.

---

## G-14 — El botón Pagar de "Mis pedidos" se veía como texto plano  ✅ SIN CAMBIO DE CÓDIGO

- **Ruta/pantalla:** `/dashboard`, sección "Mis pedidos".
- **Persona:** Acudiente.
- **Observado:** "Pagar" sin fondo ni forma de botón.
- **Investigación:** el CSS compilado en `.next/dev/static/chunks` sí traía la regla del
  botón con su degradado. La pestaña tenía los estilos de antes del cambio.
- **Resolución:** recargar la página. Igual que G-06, era el navegador y no el código.

---

## Pendiente de recorrer

- **Acudiente (:3000):** armar lista → resolución → los tres kits
  (Ahorrador/Premium/Fan) → inicio de checkout. Vigilar el display
  `fidelidad` vs `resolucion_auto` (semántica cambiada en Parte B). El tramo
  **checkout → pago → resultado → "Mis pedidos"** se recorrió el 2026-10-02 y 03
  con Wompi sandbox (tarjeta aprobada y rechazada, PSE): ver G-09 a G-14.
- **Operador (:3001):** cola de revisión, validación de líneas, ruta rápida
  (`resueltos`). Desbloqueado (G-01 arreglado); pendiente de recorrer a mano.
- **Colegio admin (:3001):** publicar/curar lista oficial, panel institucional.
  Desbloqueado; pendiente de recorrer a mano.

---

## Flags de divergencia de documentación (reportar, NO editar los docs)

Afirmaciones de la tesis que los cambios de código (Partes A/B) invalidan:

1. **OE3 "el canal híbrido afecta el resultado del match"** — era **falso en
   producción** hasta Parte A. La ruta HTTP `POST /v1/catalogo/emparejar` usaba
   un `_indice()` que no seleccionaba la columna `embedding` ni pasaba vector de
   consulta, así que el coseno semántico era siempre 0. Ahora el canal está vivo
   (verificado: `GEMINI_API_KEY` puesto, `producto_id`/`imagen_url` poblados).
2. **Cualquier cifra de frente NSGA-II / hipervolumen para kits GRANDES** bajo
   la codificación float-floor anterior **no reproduce** tras pasar a
   codificación entera (Parte B). Los ejemplos pequeños (enumerados,
   `espacio ≤ 4096` → `_frente_exacto`) **sí** reproducen byte a byte.
3. **Cualquier doc de contrato/UI que describa `objetivos.fidelidad` como la
   fracción auto-resuelta** — la semántica cambió: ahora `fidelidad` = nivel de
   marca (el eje que se optimiza en el frente), y la fracción auto-resuelta se
   movió a `resolucion_auto` (Parte B). Ambas claves se emiten ahora.
