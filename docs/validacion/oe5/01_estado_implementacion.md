# TUKIT: estado real de implementacion (auditoria 2026-10-17, actualizada tras fetch)

Repo: `/Users/mariapaula.rodriguez/Documents/university/TUKIT/tukit` (rutas abajo relativas a el).
VERIFIED = visto en codigo. UNVERIFIED = no se ejecuto o no se pudo comprobar. Nada se levanto ni se corrio (solo lectura).

## Actualizacion tras fetch (origin/main dfc4fd3)
Base: `origin/main` pasó de 58b9e47 a dfc4fd3 (+154 commits, incluye el merge de `feature/integracion-total`). Todo lo de abajo se
leyó con `git show/grep origin/main` (sin checkout). Las secciones 0-7 siguen escritas contra el árbol viejo; donde chocan con
esta lista, manda esta lista (marcadas "[ACTUALIZADO]" en el cuerpo).

**Cambió (era falta, ahora hay):**
- Cambio por ítem del padre: HECHO. `LineaDeKit.tsx` tiene botón "Cambiar por otra opción · N" que abre tarjetas con diferencia de
  precio y botón elegir; llama `PUT /api/trabajos/{id}/kits/{perfil}/lineas/{item}/producto` -> `PUT /v1/trabajos/{id}/kits/{perfil}/lineas/{item_id}/producto`
  (`routers/inteligencia.py` ~l.285, `trabajos.cambiar_producto_del_acudiente`). Solo entre lo que la línea ya ofrece (sugerido o
  `sustitutos`); se guarda en el trabajo del padre (`cambios`), nunca en el kit canónico. Commit cad82a7 (4-oct). Sigue SIN carrusel:
  son tarjetas en lista.
- Cuatro kits, no tres: `Ahorrador / Fan / A tu Medida / Premium` (`ORDEN_PERFIL` en `VistaKits.tsx`; migración `20261004_2200_perfil_a_tu_medida.py`).
  "A tu Medida" = "la mejor marca que cabe en lo que quieres gastar" y sale del punto medio de prioridad. Hay selector de kits (tabs) y
  rótulo "Te recomendamos este" / "Tu elección".
- Bug "1 kit bajo 'tus tres kits'": CORREGIDO. `VistaKits.tsx:90` dice "Tu kit está listo" si `origen==="parent_apply"` y "Tus kits están listos" si no;
  y `trabajos.ver()` (~l.1125) ahora pinta los kits del canónico (Ahorrador+Premium + el Fan armado para el padre) en la ruta rápida.
- Presupuesto: PARCIAL. Sí hay campo de tope en pesos en `/empezar` (`presupuesto_por_hijo`, solo con prioridad "punto medio",
  `FormularioEmpezar.tsx` l.481-622, 1272-1287) y aviso "se pasa del tope que pusiste" en el kit (`VistaKits.tsx:179`). NO hay ajuste en
  vivo con recomputación en `/kits`. Corrige "el front ya no pide presupuesto".
- Pago: ahora hay flujo completo en la web. `WOMPI_MODO` sigue en `falso` por omisión (`.env.ejemplo:67`), pero ya no es un `window.alert`:
  `VistaKits` abre el widget de Wompi (`lib/wompi.ts`, tarjeta/Nequi/PSE) o, con pasarela falsa, redirige a `/pago/simulado` (botones Aprobar/Rechazar)
  y de ahí a `/pago/resultado` (`ResultadoPago.tsx`, 394 lín: "¡Pago aprobado!", "Tu pago no fue aprobado", reintentar), que confirma con el servidor
  (`api/pagos/[transaccion_id]/sincronizar`). `dashboard/AccionesPedido.tsx`: Pagar y Cancelar un pedido pendiente (`api/pedidos/[id]/pagar|cancelar`).
  Con `sandbox` siguen haciendo falta 4 llaves de prueba (UNVERIFIED que existan).
- Entrega: backend igual (estados pagado -> en_preparacion -> despachado -> en_reparto -> entregado). Ahora SÍ hay UI de operador: admin
  `/logistica/[pedido]` (221 lín) con `AccionesPedido.tsx` que llama `avanzarPedido`; el modelo pasó a reparto propio (`repartidor_nombre`, `entrega_estimada`;
  transportadora/guía quedan como legado). Para el padre: solo la etiqueta de estado en "Mis pedidos" y 4 pasos estáticos ("Lo que sigue") en `/pago/resultado`;
  no hay página de pedido ni muestra repartidor (rg `repartidor_nombre` en `apps/web`: 0). La página `/pedidos/[id]` existe solo en `feature/maps-and-feats`.
- Admin: `/clientes` y `/logistica/[pedido]` ya están en main; `/portal` sigue igual.

**Sin cambio (sigue siendo falta):** panel/portal del colegio (`portal/page.tsx` sigue siendo el aviso "pendiente de portar", ADR 0008; rol colegio_admin/docente
redirige a /ingresar si no); panel de privacidad (cero UI web; identidad no tiene rutas de exportar/suprimir, solo `modelos/privacidad.py`);
WhatsApp (solo `WaLink` = enlace `wa.me` en `operacion/notificador.py`; sin API Business; Correo por SMTP o consola); carrito multi-kit; app nativa.

**Números:** servicios HTTP en disco: 6 (gateway 8010, identidad 8011, catalogo 8012, inteligencia 8013, comercio 8014, operacion 8015); `ingesta` sigue declarado y sin carpeta.
Manifiesto: `total_tablas_esperado = 72` (era 71). Procesos de fondo (Makefile): repartidor, poller, trabajador, poller-identidad, barredor + `instantanea-metricas`
(sin cambio, 5 bucles + 1 puntual). `README.md` raíz sigue desactualizado (habla de "cuatro procesos HTTP", tabla de 4 puertos). Funciones `test_*` (conteo textual, NO ejecutadas):
gateway 22, identidad 178, catalogo 605, inteligencia 297, comercio 151, operacion 45, libs+ensayos 67. Datos: 667 productos canónicos (eran 609), 17 colegios, 4.719 ítems de lista.

**`docs/PENDIENTES.md` (161 lín, revisión 2026-10-08):** no habla de UI. Abiertos: re-medir el benchmark Laya con el optimizador vigente (v7, ADR 0039); traer docs del repo externo
`Arquitectura/` (ADR 0001-0026, SRS); portada del documento de algoritmos; frente exacto por programación dinámica; pesos por omisión vs encuesta (0,35/0,30/0,25/0,10 vs 0,285/0,273/0,255/0,187);
rescate semántico coseno ≥0,93 sin revisión; acoplamiento en el objetivo; grafo de sustituibilidad vacío; calibrar τ (0,75 a mano); percepción en paralelo; hogares de varios hijos;
personaje con dos grafías (24 de 76 con mayúsculas). Sección 3 dice "nada está publicado" y menciona 218 commits de ventaja (texto viejo respecto al merge de integracion-total).

**Ramas sin fusionar (vs origin/main):**
| Rama | Qué suma | Merge con main |
|---|---|---|
| `feature/afinar-kits-agustiniano` (39 adelante, 0 atrás, hasta 15-oct) | Solo catálogo/curaduría: 1.050 productos (main 667), 384 ofertas nuevas, atributos exigidos por renglón en el editor de la cola, auditoría v4 "758 de 885 comprables cumplen (85,6 %)" (v3: 617 = 69,6 %), ADR 0040, `ensayos/kits_offline.py`. Web: 1 línea en `TarjetaProducto.tsx` | limpio (avance rápido) |
| `feature/maps-and-feats` (12 adelante, 27 atrás, 10-oct) | `/pedidos/[id]` con línea de tiempo calculada en Comercio, dirección con Google Places (necesita llave), localidad e indicaciones, directorio de colegios con logo, subir lista de cualquier colegio de Bogotá desde `/cola` | solo choques de docs (ADR 0039/0040 se pisan con los de main/afinar) |
| `a/fases-2-6-integracion` (41 adelante, 3 atrás, 11-oct) | Solo pruebas: caracterización por servicio, e2e Playwright (web y admin), `datos/golden`, ensayos de integración, gate de cobertura en CI. Sin cambios de producto | solo `ci.yml` |
| `mejoras/seguridad-ortografia-carrusel` (1 commit d0c19b0, 4-oct, basada en el viejo 58b9e47, 154 atrás) | `SelectorCuadernos` (8 diseños + 8 stickers SVG) en `/empezar`, páginas `/privacidad`, `/terminos`, `/cookies` + `BannerCookies`, job de retención y SLA en operación, tildes en ~40 archivos | CONFLICTOS en `FormularioEmpezar.tsx`, `VistaKits.tsx`, `contrato.ts`, `trabajos.py`, admin y tests |
Ojo con el carrusel: elige el diseño de la PORTADA del cuaderno por hijo (`diseño_cuaderno_id` / `diseño_custom`), solo viaja en el contrato TS; ningún archivo de `servicios/`
lo lee. No es el carrusel de productos del VFP ni sustituye el cambio por ítem. Las páginas de privacidad/cookies son texto legal estático, no el panel de consulta/exportación/supresión.

**Rama para grabar el demo de 60 s:** `origin/main` (en una copia/worktree aparte, no en tu árbol). Tiene el flujo completo: elegir personaje -> 4 kits -> cambiar un ítem -> pagar
(simulado o sandbox) -> resultado -> dashboard. Si quieres que el catálogo luzca más lleno, `afinar-kits-agustiniano` se le puede avanzar encima sin conflictos. `maps-and-feats` suma la
página de pedido, pero depende de una llave de Google. No grabes desde la rama del carrusel (desfasada, conflictiva).

## 0. Que arbol se auditó (importante) [ACTUALIZADO: ver arriba; esto describe el árbol local viejo]
- VERIFIED: el working tree esta en `feat/backbone-resiliencia-eventos-observabilidad` (HEAD 3418586, 29-sep). Local `main` (58b9e47, 30-sep) es MAS NUEVO: trae el mismo backbone (0ab8b50, mismo contenido con otro hash por reescritura de historia) mas el trabajo de "friend/nuevos-usuarios-lista".
- Lo que main tiene y la rama NO: registro de acudiente nuevo (`apps/web/src/app/api/registro/route.ts`), matriculas por hijo (`api/cuenta/matriculas/route.ts`, `identidad/dominio/matriculas.py`), pantalla admin `/clientes`, metricas por colegio, colegio identificado por DANE (migracion `20260927_0050_colegio_gana_dane.py`), "Mis solicitudes" por contacto. `git diff HEAD main`: 103 archivos.
- Ramas locales: `main`, `oe4-optimizador`, `feat/onboarding-hitl-oe3-oe4`, `integracion/friend-a-backbone`, `fix/grade-page-editar-simulado-arch`, 2 backups. Remotas: ver tabla de ramas arriba.
- Las rutas de las secciones 1-7 son del working tree viejo; la fuente de verdad ahora es `origin/main` dfc4fd3.

## 1. Flujo real del acudiente en apps/web (Next.js 16, PWA con `public/manifest.webmanifest`)
Todo habla con el backend real via gateway :8010. `apps/web/.env.ejemplo`: "La app siempre habla con el backend real"; el origen simulado ya no existe (`libs/ts/tukit-contrato/src/` solo tiene `cliente-http.ts`, `origen.ts`, sin `origen-simulado`). VERIFIED.

| Paso | Ruta | Estado |
|---|---|---|
| Landing | `/` (`app/page.tsx`, 206 lin) CTA a `/empezar` | REAL, estatica |
| Colegio + grado + hijos | `/empezar` (`FormularioEmpezar.tsx` 952 lin; 1290 en main) | REAL. Buscador de colegios con logo; solo colegios con lista revisada (`revisada=true`); grado como chips |
| Subir lista propia | misma pantalla, `api/listas/subir/route.ts` | REAL (backend; extraccion con Gemini `gemini-3.5-flash-lite`, `inteligencia/gemini.py`). Si el colegio no existe: formulario "Sugerir mi colegio" (`api/sugerencias`) |
| Personaje | `SelectorPersonaje.tsx` + `IconosPersonaje.tsx` | REAL (ver seccion 3) |
| Prioridad de gasto | paso 3 del formulario, 3 opciones: "Lo mas economico", "Un punto medio", "Puedo estirarme un poco" (pesos precio/marca/calidad/personaje) | REAL, mapea a perfil |
| Cola / espera | `/esperando/[trabajo_id]` (`PantallaEspera.tsx`, sondeo) | REAL. Ruta lenta: pipeline + revision humana en admin antes de mostrar |
| Ruta rapida | `/empezar` desvia a `aplicarCanonico` si (colegio,grado) tiene kit canonico aprobado y es un solo hijo; salta a `/kits/{id}` | REAL (`api/trabajos/aplicar-canonico/route.ts`, `inteligencia/trabajos.py: aplicar_canonico`) |
| Kits | `/kits/[trabajo_id]` (`VistaKits.tsx` 327 lin, `LineaDeKit.tsx`) | REAL [ACTUALIZADO: 4 kits Ahorrador/Fan/A tu Medida/Premium, tabs, "Tu kit está listo" en ruta rápida, botón "Cambiar por otra opción" por línea]. Tarjetas con total, "Te recomendamos este" y razon, secciones por clase de linea, consolidaciones entre hermanos |
| Carrito | NO EXISTE como pantalla. El "carrito" es el kit elegido + barra de total + boton de pago | N/A |
| Checkout | formulario dentro de `/kits` (destinatario, direccion, ciudad, correo) -> `api/trabajos/[id]/ordenar` -> inteligencia -> comercio `crear_orden` + `iniciar_pago` | REAL; ahora con widget Wompi o `/pago/simulado` -> `/pago/resultado` (ver Pago) |
| Panel | `/dashboard`: hijos, "Mis solicitudes" con tira de etapas, "Mis pedidos" (id, fecha, estado, total) | REAL, lee `GET /v1/comercio/mis-pedidos` |
| Ayuda | `/ayuda` + `api/casos` crea ticket en operacion | REAL |
| Catalogo | `/catalogo` explorador publico | REAL |
| Portal colegio | `/portal` | PLACEHOLDER: dice "en construccion... No te fabricamos una falsa" (`app/portal/page.tsx`) |

### Pago: mock por defecto, Wompi sandbox implementado pero no activado [ACTUALIZADO: UI de pago completa, ver bloque de arriba]
- VERIFIED `servicios/comercio/tukit_comercio/pasarela.py:332-`: `WOMPI_MODO` por omision `falso` -> `PasarelaFalsa` (ids deterministas, firma webhooks con el algoritmo real, devuelve `url_redireccion=None`). `WOMPI_MODO=sandbox` -> `WompiSandbox` (exige 4 llaves; firma de integridad SHA256 y verificacion de eventos implementadas).
- [OBSOLETO] Antes: con pasarela falsa el UI mostraba `window.alert`. Ahora (origin/main): falsa -> redirige a `/pago/simulado`; Wompi -> widget modal; ambos terminan en `/pago/resultado` con pantalla de éxito/rechazo.
- VERIFIED webhook `POST /v1/webhooks/wompi` (`routers/comercio.py:347`) pasa pedido a `pagado` y emite `pedido_pagado`; barredor libera reservas sin pagar por TTL (`barredor.py`).
- UNVERIFIED: que haya llaves sandbox reales cargadas o ngrok; la nota de memoria (e2e-test-runtime-topology) dice que para confirmar pago falso hay que POSTear un webhook sintetico. La Memoria TG dice "checkout mock" (OE4): esta desactualizada frente al codigo, que ya tiene el camino completo.

### Entrega
- VERIFIED backend: maquina de estados `pagado -> en_preparacion -> despachado -> en_reparto -> entregado` (+incidencia, cancelado), `comercio/dominio/despacho.py`; `POST /v1/ordenes/{id}/avanzar` exige transportadora y guia para despachar; retracto `POST /v1/ordenes/{id}/retracto`; seguimiento `GET /v1/ordenes/{id}`.
- [CORREGIDO en origin/main] Admin `/logistica/[pedido]` ya tiene botones (`AccionesPedido.tsx` -> `avanzarPedido`); `/logistica` sigue siendo el tablero. Reparto propio (`repartidor_nombre`, `entrega_estimada`). El acudiente ve solo el estado en "Mis pedidos" y 4 pasos estáticos en `/pago/resultado`; página de seguimiento `/pedidos/[id]` solo en `feature/maps-and-feats`.
- Notificaciones: `operacion/notificador.py` = `WaLink` (arma un enlace `wa.me/<cel>?text=`, no envia nada), `Correo` (SMTP; sin `TUKIT_SMTP_HOST` imprime en consola), `NotificadorFalso`. VERIFIED: NO hay WhatsApp Business API. El correo "kit listo"/"pedido pagado" solo sale si corre `make repartidor` (memoria + Makefile:365).

### Hallazgo UX (VERIFIED en codigo, no visto en pantalla)
[CORREGIDO en origin/main] Antes, la ruta rápida (`parent_apply`) traía un solo kit bajo el título "Tus tres kits". Ahora `ver()` pinta los kits del canónico y el título es "Tu kit está listo" cuando `origen==="parent_apply"`.

## 2. Backend (servicios/)
Manifiesto `arquitectura/manifiesto.toml`: 7 componentes, 5 bases, `total_tablas_esperado = 71` [ACTUALIZADO: 72 en origin/main]. En disco hay 6 procesos HTTP (el 7o, `ingesta`, esta declarado pero NO existe `servicios/ingesta`; sus scrapers viven en `catalogo`). El `README.md` raiz esta DESACTUALIZADO (dice "dos de siete portados", tabla de 4 puertos). VERIFIED.

| Servicio | Puerto | Que hace | Tamaño / tests |
|---|---|---|---|
| gateway | 8010 | Unica URL del front; ruteo por prefijo (`RUTAS` en `tukit_gateway/api.py`) | 272 lin / 10 tests |
| identidad | 8011 | Colegios, grados, contactos, cuentas, sesiones, matriculas, directorio de colegios Bogota, privacidad; poller `colegio_verificado` | 3.4k lin / 126 tests |
| catalogo | 8012 | Productos canonicos, conceptos, ofertas por tienda, listas oficiales, curaduria admin, volcado/enriquecimiento, scrapers | 14.4k lin / 518 tests |
| inteligencia | 8013 | Trabajos (pipeline durable), percepcion Gemini, resolucion, optimizador NSGA-II, revision humana, kit canonico, checkout hacia comercio, metricas | 6.9k lin / 185 tests |
| comercio | 8014 | Ordenes con precios congelados, inventario/reservas, pasarela, webhook, entrega, retracto | 2.8k lin / 57 tests |
| operacion | 8015 | Casos/PQRS, notificaciones, auditoria, telemetria | 2.1k lin / 39 tests |

Trabajadores de fondo (Makefile): `trabajador`, `repartidor` (bandeja de eventos), `poller` (inteligencia), `poller-identidad`, `barredor`, `instantanea-metricas`. Backbone opcional (RabbitMQ, Redis, Jaeger) bajo `make infra-arriba` (`libs/py/tukit_comun`: `bandeja.py`, `broker.py`, `resiliencia.py`, `telemetria.py`). Conteo de tests = funciones `test_*` (rg), NO ejecutadas: UNVERIFIED que pasen hoy.
Datos semilla (`datos/`): 609 productos canonicos (CSV), 99 conceptos, 5 tiendas (Exito, Grancentral, Panamericana, Libreria Nacional, Buscalibre), 17 colegios, 175 listas (colegio,grado), 4.719 items, mediana 26 items por lista (rango 5-74).

## 3. Kit / optimizador / personalizacion
- NSGA-II: VERIFIED `inteligencia/optimizador.py` (979 lin): pymoo `NSGA2`, SBX+PM+RoundingRepair, 4 objetivos (costo, fidelidad de marca, disponibilidad, personaje), poblacion 40-200 y generaciones 30-120 escaladas, semilla fija (reproducible). pymoo es dependencia dura. Si el espacio <= 4096 combinaciones enumera el frente exacto; si no, NSGA-II. Los 3 kits son 3 proyecciones del frente (`_proyectar`). La heuristica queda solo para lineas con 1 candidato y como linea base de hipervolumen en tests.
- Presupuesto: cota dura en `recomendar`, no en el frente. Recomendacion: Ahorrador por omision; Premium solo con calidad primero y 10% de sobreprecio declarado; Fan solo con personaje explicito (`tests/test_optimizador.py`). [CORREGIDO] El front SÍ vuelve a pedir un tope (`presupuesto_por_hijo`, solo con prioridad punto medio -> kit "A tu Medida"); no hay ajuste en vivo en `/kits`.
- Items por kit: una lista tiene mediana 26 items (datos). Un caso vivo en memoria: 65 lineas, 48 comprables (17 digitales/casa), 3 kits distintos (Ahorrador/Fan ~650.759 COP, Premium ~1.582.343 COP). UNVERIFIED (viene de memoria, no lo recalcule sin servidor).
- Personaje: VERIFIED 7 franquicias completas con las 4 anclas (cuaderno C001, cartuchera C009, carpeta C011, maleta C086): bluey, cars, frozen, minnie, paw patrol, spiderman, stitch (`IconosPersonaje.tsx` l.284; `datos/catalogo/metricas_catalogo.json` con_personaje; disney 3/4 incompleta; lego, minecraft, jurassic, snoopy, halo se obvian). Campo libre permitido, pero se marca como "pedido" sin garantia de stock. `anclar_personaje` sube las 4 lineas del personaje al tope del kit.
- Marca: el padre NO elige marca. Elige prioridad (3 niveles) que se traduce en pesos; los productos traen `nivel` economico/confiable/premium. No hay selector de marca en la UI web. VERIFIED (`grep marca` en FormularioEmpezar solo da pesos y copy).
- [CORREGIDO en origin/main] Cambio por item en la web: SÍ (tarjetas con botón elegir, `PUT /v1/trabajos/{id}/kits/{perfil}/lineas/{item}/producto`, solo entre las opciones de la línea). Sigue sin carrusel. (Texto viejo: NO, lista de solo lectura.) El intercambio por linea en admin: `PUT /v1/admin/trabajos/{id}/kits/{perfil}/lineas/{item_id}/producto` (`routers/inteligencia.py:878`) + `LineaRevision.tsx` + `PersonajeFan.tsx` (cambia las 4 anclas del Fan). VERIFIED.
- Personaje en el flujo del padre: el personaje elegido se inyecta en las 4 anclas del Fan (commit a4bbc8d "inyectar el personaje pedido en las anclas del Fan") tanto en pipeline como en ruta rapida (`_anclas_de_personaje`). Regla de usuario: personaje -> Fan; si no, precio/equilibrio -> Ahorrador, calidad -> Premium.

## 4. Paneles admin / colegio
- apps/admin (:3001, VERIFIED paginas): `/` panel; `/cola` cola de verificacion (listas sin revisar + trabajos de acudiente en espera); `/onboarding/[version_id]` aprobar lista nueva; `/trabajos/[id]` ConsolaRevision con MatrizComparacion de los 3 kits, cambio de producto por linea, PersonajeFan, decision aprobar/rechazar; `/colegios` y `/colegios/[colegio]` (datos, grados, metricas, acudientes) y `/colegios/[c]/[grado]` con "Kits NSGA aprobados" (`KitsCanonicos.tsx`); `/catalogo` curaduria CRUD de productos/conceptos/huecos; `/logistica` tablero de pedidos (+ detalle con acciones, origin/main); `/tickets` casos (lectura); `/clientes` ya está en origin/main; `/logistica/[pedido]` con acciones de avance.
- Panel colegio: NO existe. `apps/colegio` no esta en el repo; `/portal` es un cartel de "en construccion". Las metricas por colegio se ven en el admin, no para el colegio.
- Hay revision humana obligatoria: ningun kit llega al padre sin aprobacion admin (`kits/page.tsx` redirige a `/esperando` si no esta publicado). Hito 2-aprobaciones (lista, luego kit canonico) verificado en vivo segun memoria 2026-09-28 (UNVERIFIED hoy).

## 5. Verificacion de las notas de memoria
- e2e-test-runtime-topology: VERIFIED pago cableado (`ordenar/route.ts`, `Checkout` en VistaKits), Wompi `falso` por omision, gateway con `/v1/ordenes` y `/v1/webhooks/wompi`. UNVERIFIED la cadena E2E del 28-sep (no se reejecuto). Ojo: dice "6 HTTP services"; coincide con 6 en disco.
- linea-write-path: VERIFIED endpoint, `fijar_producto_en_linea`, `PersonajeFan.tsx`, `fijarProductoLinea` en contrato y admin.
- kit-canonico-publish-cache: VERIFIED `aplicar_canonico`, `grados_canonicos`, ruta `aplicar-canonico`, panel `KitsCanonicos`, migracion `parent_apply` (`inteligencia/migraciones/.../20260928_1245_origen_parent_apply.py` existe en main).
- empezar-frontend-overhaul: VERIFIED medallon de iconos, filtro `revisada`, sugerencia de colegio. DESACTUALIZADA en main: el `SelectorColegio` fue reemplazado por un buscador unico con DANE.
- personaje-personalizacion-decisions: VERIFIED las 7 franquicias; disney sigue con 3 productos en `metricas_catalogo.json` (no 4): sigue sin entrar.
- p4-admin-hitl-completion: "region-4 preview desde onboarding" pendiente; `AprobarLista.tsx` existe. UNVERIFIED si se cerro (no mire el componente en detalle).
- Drift detectado: `README.md` raiz (estado "2 de 7") y Memoria TG ("checkout mock", 70 tablas vs 71 en el manifiesto) no coinciden con el codigo.

## 6. Demo de 60 s hoy
Camino bueno (todo REAL con backend arriba: `make reanudar` desde la RAIZ, `make repartidor`, `make poller`; web y admin con `TUKIT_ORIGEN_DATOS=api TUKIT_API_URL=http://localhost:8010`):
1. `/` landing -> `/empezar`: buscador de colegios con logos, chips de grado, rejilla de 7 personajes con medallones de plastilina y animacion GSAP rebote (la pantalla mas vistosa).
2. Prioridad de gasto (+ tope en pesos) -> `/kits/{id}` con 3-4 kits y botón "Cambiar por otra opción" por línea [ACTUALIZADO], chapa "Te recomendamos este", razon, lineas con foto/marca/nivel y ofertas por tienda, consolidacion entre hermanos. Ruta rápida ya OK en origin/main (título corregido); sigue conviniendo pre-aprobar el trabajo.
3. Barra de total + formulario de pago. Con Wompi falso ahora sale `/pago/simulado` (Aprobar/Rechazar) y `/pago/resultado`, presentable; con `WOMPI_MODO=sandbox` + 4 llaves, widget real (UNVERIFIED).
4. Cierre: `/dashboard` (Mis solicitudes con tira de etapas + Mis pedidos) o admin `/trabajos/[id]` MatrizComparacion y `/colegios/.../[grado]` "Kits NSGA aprobados".
Las pantallas de espera y cola dependen de procesos de fondo; para video, pre-aprobar el trabajo.

## 7. NO construido (VERIFIED por ausencia en codigo)
- Carrusel de productos [ACTUALIZADO: el cambio por ítem del padre YA existe como tarjetas; falta el carrusel visual; el SelectorCuadernos de la rama mejoras es de portada, no de producto].
- Seleccion de marca por el padre (solo prioridad ponderada).
- Pago real de punta a punta confirmado: adaptador Wompi y pantalla de resultado existen, default sigue falso; PSE/Nequi vía widget Wompi (no probado).
- Seguimiento de entrega para el padre en main: sin página de pedido ni repartidor visible (la página existe en `maps-and-feats`). `avanzar` ya tiene UI en admin.
- WhatsApp real: solo enlace `wa.me`; sin API Business ni envio automatico. Correo solo por consola sin SMTP.
- Panel/portal del colegio (`apps/colegio`).
- Carrito multi-kit o edicion de cantidades (un kit por orden).
- Uniformes fuera de alcance ("Los uniformes todavia no los surtimos", `VistaKits.tsx`); textos escolares dependen de oferta libre (libro_libre 74 items; edicion_exclusiva y venta_directa_editorial son informativos, no se cobran).
- App nativa descopeada (ADR 0009): PWA con manifest.
- Servicio `ingesta` aparte (declarado, no existe).
- Pruebas de usuario/OE5 (SUS, NPS, k6, ZAP): instrumental, sin ejecutar segun memoria (UNVERIFIED).
