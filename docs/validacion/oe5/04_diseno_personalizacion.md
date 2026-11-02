# Diseño del paso final de personalización (carrusel de cuadernos + front generativo) — TUKIT

Versión 0.1, 2026-10-17. Solo diseño, no se implementó nada. Marcas: **[VERIF]** = comprobado en código o datos (ruta citada); **[PROP]** = propuesta de este documento.
Rutas relativas a `tukit/`. Conteos de datos salen de `datos/` (volcado CSV), no de la BD viva: se repiten contra la BD antes de decidir.

## Actualización: ya existe un carrusel de portadas (rama mejoras/seguridad-ortografia-carrusel)

2026-10-17, solo lectura de git (`origin/mejoras/seguridad-ortografia-carrusel`, commit único d0c19b0, 2026-10-04, base 58b9e47c, 154 commits detrás de `origin/main` dfc4fd3). El resto de este documento se escribió sin saberlo. **Ojo: es otro carrusel.** El de la rama elige el *diseño de portada* (adorno); el de este documento (§3) elige el *producto* de cada línea. No se solapan.

**1. Qué puede hacer el padre hoy (en la rama)** [VERIF]
- Por cada hijo, en `/empezar`, después de `SelectorPersonaje` (`FormularioEmpezar.tsx:1215-1223`): elegir 1 de 8 diseños (espacio, galaxia, magia, marino, pastel, selva, superheroes, unicornio; `datosCuadernos.ts:3-83`) con flechas, puntos y "similares" (`SelectorCuadernos.tsx:92-118, 351-395`).
- Personalizar: color base (8 de paleta, `datosCuadernos.ts:105-114`; `SelectorCuadernos.tsx:407-415`), estilo de borde (redondeado/ondulado/recto, :459-470), texto de hasta 12 caracteres en la portada (:482), hasta 6 stickers de 8 (:189, :494-507). Vista previa en vivo con mockup + tinte + personaje del paso anterior (:245-295).
- Sin recomputación de nada: no toca precios, líneas ni presupuesto.

**2. ¿Llega al kit, al pedido, al backend?** Solo hasta la frontera: casi todo es estado de UI.
- Sale en la solicitud: `diseño_cuaderno_id` y `diseño_custom` por hijo, en `crearTrabajo` (`FormularioEmpezar.tsx:782-783`) y en `subirListas` (:825-826); tipos en `contrato.ts:111-112` y `tipos-extra.ts`.
- **El backend no los define.** `git grep` de `diseño_cuaderno`/`diseño_custom` en la rama: 0 resultados en `servicios/`. En `origin/main`, `Hijo` y `HijoSubida` (`inteligencia.py:114, 566`) no tienen esos campos y no hay `extra="forbid"`: Pydantic los ignora sin error. Resultado: se pierden en silencio.
- Los tres cambios de `VistaKits`, `LineaDeKit` y `kits/page` son solo ortografía. `/kits` y el checkout no leen la portada. Los cambios de `servicios/operacion` de la rama (SLA, festivos, retención, cifrado, auditoría IA) no son del carrusel.
- Matiz: el fix multi-hijo (`SelectorCuadernos.tsx:157-163`) llama `onChange(diseños[0].id)` al montar, así que todo hijo envía "espacio" aunque el padre no haya tocado nada. Un "diseño elegido" en datos no es una decisión del padre.

**3. Hallazgos que bloquean la demo** [VERIF]
- Los 16 SVG de `public/cuadernos/` y los 8 de `public/stickers/` pesan **0 bytes** (`git ls-tree -l`). Carátulas, mockup y stickers salen rotos (solo se ve el alt). Lo único que renderiza es el rectángulo teñido con el texto. `public/personajes/*.svg` no existe en ninguna de las dos ramas (el `onError` lo oculta).
- El texto libre de 12 caracteres es donde un padre escribirá el nombre del niño y hoy viajaría sin cifrar en `diseño_custom`. Choca con el principio de minimización del contrato (sin nombres de menores). Hay que decidir antes de persistir.
- Las claves JSON llevan `ñ` (`diseño_*`) y hay `as any` en dos sitios; conviene `diseno_*` y tipo `CustomCuaderno`.

**4. Factibilidad de fusión a `origin/main`** (`git merge-tree --write-tree`, sin tocar el árbol)
- 15 archivos en conflicto, 19 bloques. Los del front son triviales (ortografía, `next-env.d.ts` borrado en main): `FormularioEmpezar.tsx` (1), `VistaKits.tsx` (1; main tiene `url_redireccion` a `/pago/resultado` y la rama `window.location.href`: gana main), `contrato.ts` (1), `PantallaEspera`, y 5 archivos de admin (`api-navegador` 3, `MatrizComparacion`, `DecisionTrabajo`, `cola/page`).
- Los de backend **no son ortografía** y piden criterio: `reparto.py` (3) y `notificador.py` (main añade avisos de despacho/entrega; la rama, avisos PQRS), `test_repartidor.py` (2), `trabajos.py` (la rama activa por defecto la estrategia `A_CON_PADRE` del emparejador; main tiene `_tipo_del_concepto_manda`) y `test_api_identidad.py`. Riesgo: cambiar el comportamiento del optimizador/emparejador sin querer.
- La rama es un diff de 142 archivos / ~10.000 líneas (2.588 de `traza_oro.jsonl`) que mezcla seguridad, ortografía, medición del catálogo y casos de operación. **No fusionar entera para el carrusel.**
- Recomendado: extraer solo `SelectorCuadernos.tsx/.module.css`, `datosCuadernos.ts`, `tipos-extra.ts` (+ export en `indice.ts`) y las ~12 líneas de `FormularioEmpezar`/`contrato`. Esfuerzo: **0,5 a 1 día** (los archivos nuevos no chocan; se retocan a mano 2 archivos de main). Fusión completa: 2 a 3 días de resolución (backend con criterio) más regresión de seguridad/operación que este objetivo no pide.

**5. Brecha frente a la promesa VFP** ("personalizar ítems individualmente, ajustar presupuesto con recomputación en tiempo real, componentes dinámicos")
- Personalizar ítems individualmente: **no cubierto**. La portada es por hijo, no por línea ni producto. Sigue faltando todo §3-§4 (sustitución por línea, alternativas, `PUT .../sustitucion`).
- Presupuesto con recomputación en vivo: **no cubierto** (el tope de gasto ya existe en main; el recálculo al cambiar una línea es nuestro §3 "Total y cumplimiento").
- Componentes dinámicos: **parcial y solo cosmético**. Hay UI que reacciona (vista previa, stickers), pero los datos no salen del kit ni se generan.
- Lo que sí da la rama: patrón de carrusel con teclado y motion, vocabulario cerrado (8 diseños con `tags`, `personajes`, `colores`, `similares`; 8 stickers; paletas) y el punto de enganche en el formulario.

**6. Cómo apoyar el front generativo en estos 8 diseños** [PROP]
- Es la mejor materia prima para G3, sin generar píxeles: el modelo devuelve un `CustomCuaderno` sobre conjuntos cerrados. Entrada: personaje y tono ("algo suave", "con Bluey"); salida con esquema: `diseno_id` ∈ 8, `colorBase` ∈ paleta, `estiloBorde` ∈ 3, `stickers` ⊂ 8 (máx. 6), texto ≤12 validado. Esto es G2 aplicado a la portada, y encaja con la regla "el modelo no decide sku ni precio".
- Guardrails: validador determinista que rechaza cualquier valor fuera de lista (hex por regex, ids por enum); sin nombre del niño en el prompt ni en el registro; texto del padre pasa por filtro de longitud y lista de insultos antes de mostrarse; la portada nunca altera líneas, precios ni total; interruptor y presupuesto diario; el padre ve y confirma la variante (3 propuestas, no una).
- Si se quiere imagen real, un render local de SVG parametrizado (los 8 diseños como plantillas) evita IA de imagen y el riesgo de PI de §5/G3. Decisión previa: ¿la portada se imprime/forra o es un adorno? Tukit hoy compra cuadernos de catálogo; un forro o etiqueta sería otro producto.

**7. ¿Demo de 60 s?** Parcialmente. Pantallas: `/empezar` (colegio y grado, personaje, carrusel, color, texto, stickers; ~20 s) → envío → `/kits/[id]` (pestañas, total; ~25 s) → checkout (~15 s). Condiciones: (a) rellenar los 24 SVG (0,5 a 1 día) o la vista previa es un rectángulo; (b) la portada **no aparece en `/kits`**, así que el video no debe decir que llega al kit; (c) si se quiere el cierre honesto del VFP, añadir 1 a 2 días: persistir `portada` (campos en `Hijo`/`HijoSubida`, validación) y mostrarla en `/kits`.

**Qué queda para la "personalización final"**: (i) arreglar los activos; (ii) persistir y validar la portada, y mostrarla en `/kits` y en el pedido; (iii) decidir texto/menores; (iv) todo §3-§4 de abajo (sustitución por línea, total en vivo), que es lo que cumple la promesa VFP; (v) G1/G2 y la portada generativa sobre vocabulario cerrado.

**Ajuste del plan y del esfuerzo (sustituye lo que aplique en §7)**
| Cambio | Días |
|---|---|
| Web §7 "carrusel y sus estados": se reutilizan patrón de scroll, flechas, puntos, motion y a11y de `SelectorCuadernos` | 4 → 3 |
| Núcleo G0 (sustitución por línea, UI-03) | 15 → **14** |
| Nuevo bloque "Portada": extraer rama (0,5-1), 24 SVG (0,5-1), persistir/validar/mostrar en kits y pedido (1-2), decisión de texto (0,5) | **+3 a 4** (opcional, independiente del núcleo) |
| Portada generativa (G2 sobre vocabulario cerrado) | +2 a 3 sobre G2 |
Total núcleo + portada: 17 a 18 días-persona (5 a 6 días calendario con 4 personas).
Decisiones nuevas para §9: ¿portada decorativa o impresa? ¿se permite texto libre (menores)? ¿se rescata la rama por extracción? ¿quién dibuja los 24 SVG?

---

## 1. Lo que hay hoy y se reutiliza

**Web (`apps/web/src`)**
- [VERIF] `app/kits/[trabajo_id]/VistaKits.tsx`: pestañas de los 3 kits, `ResumenKit` (cuenta comprables, huecos, "gestiona el colegio"), `Checkout` con total en el pie.
- [VERIF] `app/kits/[trabajo_id]/LineaDeKit.tsx`: pinta `linea.alternativas` como lista de solo lectura ("Ver N opciones más"). No hay acción de elegir: ese es el punto de enganche del carrusel de productos (no del de portadas de la rama, ver Actualización).
- [VERIF] `app/empezar/SelectorPersonaje.tsx` + `IconosPersonaje.tsx` (`iconoDe`): selección con motion y reduced-motion. `app/catalogo/TarjetaProducto.tsx`: tarjeta de producto reutilizable.
- [VERIF] Patrón BFF: `app/api/trabajos/[trabajo_id]/ordenar/route.ts` (el navegador nunca toca el backend). `package.json` solo trae gsap, lucide-react y `@tukit/contrato`; no tiene script de tests (solo lint y typecheck).
- [VERIF] `libs/ts/tukit-contrato/src/`: `LineaKit.alternativas?: ProductoKit[]`, `ProductoKit{sku,nombre,marca,nivel,personaje,imagen_url,ofertas}` (contrato.ts:259-313); `normalizarProducto` (cliente-http.ts) cose `precio`/`precio_cop`; `motion.ts` (`prefiereMenosMovimiento`, `squish`); `tokens.css` (`--color-nivel-economico|confiable|premium`, `--color-personaje`, `--espacio-*`, `--radius-*`, `--ease-clay`, `--dur-*`).
- [VERIF] `fijarProductoLinea` ya existe en origen/cliente-http, pero apunta a la ruta admin.

**Inteligencia (`servicios/inteligencia/tukit_inteligencia`)**
- [VERIF] `optimizador.py`: NSGA-II (pymoo) con 4 ejes (costo, fidelidad = nivel de marca promedio, disponibilidad = % de líneas con precio, personaje). `CONCEPTOS_ANCLA = C001, C009, C011, C086` (línea 91). `anclar_personaje` solo reordena.
- [VERIF] `trabajos.fijar_producto_en_linea` (l.1311): actualiza `LINEA` de un kit, recalcula subtotal (`precio × techo(pedida/empaque)`) y total. Endpoint `PUT /v1/admin/trabajos/{id}/kits/{perfil}/lineas/{item_id}/producto` (routers/inteligencia.py:877). Es admin, sin dueño ni validación de compatibilidad.
- [VERIF] `aplicar_canonico` (l.1671) crea un trabajo `parent_apply` que es un puntero (`hijos[0]` con `canonico_trabajo_id`, `perfil`, `personaje`); `_lineas_aplicadas` (l.1610) arma las líneas al vuelo y `ver` las pinta. `ordenar` (l.~1102) vuelve a llamar `ver`, así que cualquier capa añadida en `_lineas_aplicadas` llega al pedido.
- [VERIF] `kit_canonico`: `_fijar_canonico` apunta a un trabajo `publicado` de un solo hijo. Ese trabajo es de pipeline y es el kit que otros padres reutilizan.

**Catálogo (`servicios/catalogo/tukit_catalogo`)**
- [VERIF] `GET /v1/catalogo/productos` filtra por `concepto, nivel, personaje, con_precio, con_ofertas`; `GET /v1/catalogo/productos/{sku}` trae todas las ofertas. El gateway enruta `/v1/catalogo` y `/v1/trabajos` (gateway/api.py:70,105).
- [VERIF] `consulta.emparejar` devuelve como máximo 3 opciones por renglón (`_elegir_por_nivel`, una por nivel) y `_cumple` exige que el producto *declare* cada atributo impuesto. `optimizador._linea_desde` guarda solo 2 alternativas (`[:2]`) con forma `{sku,nombre,nivel,precio_cop,imagen_url}`, sin marca ni personaje.
- [VERIF] `RESOLUCION` guarda por renglón `concepto_codigo` y `atributos_impuestos`; `CANDIDATO.cumple_atributos`. Es la base para validar una sustitución.
- [VERIF] El listado de productos no filtra por `es_representante_canonico` (rg sin resultados en routers y repositorio): hoy devolvería también la "profundidad".

## 2. Cuántos cuadernos tiene un kit (verificación de "los 7")

- [VERIF] `datos/listas/items_lista.csv`: 175 listas (colegio, grado); 153 tienen al menos un renglón `util` con "cuaderno" en el texto (regex, no concepto resuelto). Todos caen en un único concepto, `C001 cuaderno` (`admite_personaje = true`).
- [VERIF] Líneas de cuaderno por lista: mediana 2, media 2,5, máximo 7. 14 listas tienen 4 o más; solo una tiene 7 (2.6 Jardín). Unidades (suma de `cantidad`): mediana 9, media 8,6, máximo 18.
- [VERIF] Specs distintas por lista (texto normalizado): mediana 2, máximo 5. Los 7 de Jardín son 3 specs (cuadriculado 100 h, cuadriculado 50 h, ferrocarril 50 h) repetidas.
- Lectura: "7" es el máximo de líneas o el orden de las unidades típicas (9), no lo normal. Lo normal es 2 líneas y 9 cuadernos. El diseño parte de líneas, no de unidades, y agrupa las líneas con la misma spec.
- [VERIF] Catálogo C001 en el volcado: 40 productos activos, 17 representantes canónicos; niveles 31 confiable / 7 económico / 2 premium; 15 con personaje; 40/40 con imagen.
- [VERIF] Solo 20 de 40 declaran `hojas` o `rayado`. Combinaciones: cuadriculado 80 h ×9, cuadriculado 100 h ×5, rayado 50 h ×2, cuadriculado 50 h ×1, ferrocarril 100 h ×1, ferrocarril 50 h ×0. Por la regla `_cumple`, los 20 sin atributos no pueden sustituir una línea con spec.
- **Consecuencia [PROP]:** con la spec exigida, el pool real de alternativas es de 0 a unos 9 productos, a menudo 1 o 2. Un carrusel largo no existe para la mayoría de líneas. Primera tarea: medir el pool por spec con la BD viva y completar atributos de C001 (curación en catálogo).

## 3. Diseño UX del carrusel [PROP]

**Unidad de trabajo.** Una línea de la lista, no una unidad. Arriba, "Cuadernos (N)": cada línea del kit con foto, spec en lenguaje llano ("cuadriculado · 100 hojas · cosido"), cantidad y producto actual. Se toca una línea para abrir su carrusel. No hay carrusel dentro de carrusel. Si varias líneas comparten spec, un interruptor "Usar el mismo en las N líneas iguales" (apagado por defecto).

**Carrusel.** Móvil primero: hoja inferior (bottom sheet), tarjetas con `scroll-snap-x`, tarjeta de 82 % del ancho para asomar la siguiente; escritorio: 3 tarjetas visibles. Tarjeta = foto, nombre, marca, insignia de nivel (colores de tokens), personaje si aplica, precio unitario, precio de la línea (`precio × unidades a comprar`, porque el empaque cambia), diferencia contra el actual ("+$3.200"/"−$1.100", con signo y texto, no solo color), insignia "Cumple la lista" con las specs que coincidieron. La tarjeta actual va primero, marcada "Tu elección". Botón "Elegir este" con área ≥ 44 px.

**Estados.** Cargando (esqueletos); sin alternativas ("Esta es la única opción que cumple con lo que pide el colegio", sin carrusel); error del catálogo (se conserva lo elegido, "Reintentar"); producto sin precio (visible, no elegible: "Sin precio confirmado hoy"); aplicando (botón ocupado, total en "actualizando"); precio cambió entre abrir y elegir (aviso con el precio nuevo y confirmación); aplicado (total y diferencia actualizados, "Deshacer" 10 s, aviso en `aria-live="polite"`); línea consolidada entre hermanos (en v1 bloqueada con explicación: `consolidar` liga las unidades al sku elegido, optimizador.py:677).

**Orden de las alternativas.** Filtro duro primero, orden después, y siempre explicado.
1. Filtro duro (no es ranking): mismo concepto, cumple `atributos_impuestos`, tiene precio vigente, activo, preferentemente representante canónico. Lo que no cumple no aparece.
2. Orden según el kit que mira el padre: Ahorrador = precio ascendente; Premium = nivel descendente y luego precio; Fan = coincide con el personaje pedido, luego precio. Esto reusa los mismos criterios de `elegir_por_perfil`.
3. Desempate: marca de la lista si el texto la nombra (peso `marca_exigida` de las preferencias, FormularioEmpezar.tsx:71-85), luego número de tiendas con oferta, luego sku (determinista).
4. Etiquetas calculadas por regla: "Más barato", "Misma marca", "Con Bluey". Nada de puntajes opacos.

**Total y cumplimiento.** Total en el pie con vista previa optimista (`nuevo_subtotal − subtotal_actual`) y valor definitivo del servidor. `ResumenKit` debe seguir mostrando los mismos "En tu carrito" y "No los tenemos"; una sustitución nunca los cambia. Invariantes que el servidor verifica y el cliente muestra: líneas comprables iguales antes y después, cada línea sustituida con `cumple_atributos`, total = suma de subtotales. El criterio del dossier "100 % de los ítems cubiertos" se mantiene.

**Accesibilidad.** Región con rol `region` y `aria-roledescription="carrusel"`; flechas anterior/siguiente como botones reales; teclado: ←/→ mueven foco entre tarjetas, Enter elige, Esc cierra y devuelve el foco a la línea; foco atrapado en la hoja; `alt` con nombre y marca (hoy las fotos usan `alt=""`); contraste de insignias contra tokens; sin autoplay; `prefiereMenosMovimiento()` desactiva rebote y animación de total; objetivo táctil ≥ 44 px; precios con separador de miles (`formatearPesos`); lector anuncia "Cambio aplicado, total $X".

## 4. Cambios de API [PROP]

1. **Catálogo**: `GET /v1/catalogo/productos/compatibles?concepto=C001&atributos={json}&solo_representantes=true&con_precio=true`. Aplica `_cumple` donde ya vive (el servicio dueño de la regla). Se añade el parámetro `solo_representantes` al listado general.
2. **Inteligencia**: `GET /v1/trabajos/{id}/lineas/{item_id}/alternativas` (token del dueño). Lee concepto y atributos de `RESOLUCION`, llama al catálogo, calcula `unidades_a_comprar`, subtotal, `delta_cop`, `cumple` y la etiqueta de orden. Devuelve `{actual, alternativas[], pool_total}`.
3. **Inteligencia**: `PUT /v1/trabajos/{id}/lineas/{item_id}/sustitucion {sku}` y `DELETE` del mismo recurso. Revalida en servidor (concepto, atributos, precio vigente, línea no informativa ni consolidada, trabajo del usuario) y responde con el kit recalculado.
4. **Capa de sustituciones por `item_id`** en `parent_apply`: `hijos[0].sustituciones = {item_id: sku}`. `_lineas_aplicadas` hoy indexa los swaps por **concepto** (`swaps.get(concepto)`), así que con varias líneas C001 pondría el mismo producto en todas; la capa nueva se aplica después del personaje y gana sobre él. Al ser puntero, el kit canónico de otros padres no se toca.
5. **Trabajos de pipeline** (flujo PDF): escribir `LINEA` en sitio es peligroso porque ese trabajo puede ser el canónico de otros (kit_canonico). Copy-on-write: la primera sustitución crea un `parent_apply` hijo que apunta al trabajo. En v1 se soporta solo `parent_apply`.
6. **Contrato TS**: `alternativasDeLinea`, `fijarSustitucion`, `quitarSustitucion` en origen/cliente-http/simulado; rutas BFF en `app/api/trabajos/[trabajo_id]/lineas/[item_id]/...`; `LineaKit` gana `sustituida?`, `cumple_lista?`, `delta_cop?`.
7. **Checkout**: sin cambio de ruta (`ordenar` usa `ver`). Añadir prueba de que el pedido congela la sustitución y que `precio_cambiado` de Comercio se muestra bien.
8. **Corrección previa [PROP]**: `_anclas_de_personaje` usa `producto_de_personaje` (`por_pagina=1`, sin atributos) y reemplaza todas las líneas C001 por un solo producto del personaje. Con listas de cuaderno cuadriculado y ferrocarril esto puede romper el cumplimiento hoy. Debe respetar `atributos_impuestos` o dejar la línea neutral.
9. **Eventos**: `sustitucion_aplicada|deshecha|rechazada` a `bandeja_salida` (patrón de outbox existente) para las métricas del §6.

## 5. Plan del front generativo [PROP]

**Marco.** [VERIF] `docs/FLUJO_EXTREMO_A_EXTREMO.md` (T5, A9, pregunta 3) y `ADENDA_REQUISITOS_SRS.md:1207` dejan el front generativo con chat **sin requisito, alcance diferido**, 8–15 jornadas; `UI-03` (intercambiar un ítem por alternativa con precio actualizado) sí tiene requisito y es el 80 % del valor. Este diseño cubre `UI-03` con el carrusel y agrega lo generativo por capas, cada una apagable. [VERIF] La encuesta P21 pone el personaje en 1,87 frente a 2,85 del precio: lo generativo centrado en personaje es la capa de menor retorno.

**Regla central.** El modelo nunca decide un sku, un precio, un total ni si algo cumple la lista. Solo redacta o compone sobre datos que el API ya validó.

| Capa | Qué se genera | Modelo | Latencia / costo | Fallback |
|---|---|---|---|---|
| G0 | Nada: reglas y plantillas (etiquetas, diferencias) | ninguno | 0 | es el estado base |
| G1 | Una frase por alternativa ("Cuesta $1.100 menos y es de la misma marca") | `gemini-3.5-flash-lite` ([VERIF] ya integrado en `gemini.py`, variable `GEMINI_MODELO`) | Lote en la publicación del kit, con caché por (sku_actual, sku_alt, perfil): 0 ms en línea. Pocos cientos de pares; costo despreciable, tarifa a confirmar [VERIF pendiente] | Plantilla de G0 |
| G2 | "Especificación de interfaz" en JSON (orden de atributos, tabla o tarjetas, qué insignias resaltar) según preferencias y dispositivo | mismo modelo, salida con esquema | Objetivo p95 < 1,2 s, con caché por perfil + spec; se muestra G0 y se reemplaza solo si llega a tiempo | Layout por defecto |
| G3 | Vista previa ilustrativa personalizada (rótulo con el nombre, forro) | modelo de imagen o render local | Spike; no entra a producción sin decisión | Foto real del catálogo |
| G4 | Chat que traduce "uno más barato" o "con Bluey" a parámetros del endpoint de alternativas | modelo con llamada a herramienta | 8–15 jornadas (doc del equipo) | Carrusel |

**Guardrails.**
- Salida con esquema JSON; el cliente renderiza solo bloques de una lista blanca (sin HTML, estilos ni JS del modelo). Un verificador determinista revisa que los números y nombres de la frase aparezcan en los datos de entrada; si no, se descarta y sale la plantilla.
- Entradas sin datos personales: se usan `sku`, specs y deltas. [VERIF] el contrato ya prohíbe nombres de menores (referencias sintéticas). El nombre del niño en un rótulo (G3) se compone en el navegador y no se envía a ningún modelo (menores, Ley 1581).
- Tiempo máximo de 800 ms en línea; corte de presupuesto diario; interruptor por capa; registro de prompt/respuesta con hash, sin texto del padre.
- Cumplimiento de la lista: el único escritor es `PUT .../sustitucion`, que revalida; G1–G4 solo pueden proponer skus que el endpoint de alternativas ya devolvió (comparación por id). Prueba de propiedad: tras N sustituciones aleatorias, comprables iguales, todas con `cumple`, total = suma.
- G3: no generar imágenes de producto. El padre compra el producto del catálogo; una imagen sintética de un cuaderno o personaje licenciado engaña sobre lo que llega y tiene riesgo de propiedad intelectual. Cualquier vista generada va rotulada "Ilustración, no es el producto" y solo si hay un producto personalizable real (etiquetas, forros), que hoy el catálogo no tiene.

## 6. Cómo evaluarlo con padres [PROP]

Se monta sobre `Nestle/research/03_plan_validacion_presencial.md` (piloto Salitre, SUS ≥ 68, NASA-TLX, NPS, think-aloud) como una tarea más de la sesión, sin sesión aparte.
- **Tarea**: "Cambia el cuaderno de la línea X por uno más barato sin salirte de lo que pide el colegio" y "deja tu kit con el personaje de tu hijo en el cuaderno".
- **Métricas de uso**: éxito de tarea (Wilson, n = 30), tiempo, errores, toques para completar, SEQ (1–7), tasa de deshacer, líneas cambiadas por kit, delta de precio medio, abandono en la hoja.
- **Cumplimiento (sistema)**: 100 % de kits con las invariantes del §3 tras la sesión; cualquier violación es defecto bloqueante.
- **Comprensión y confianza**: pregunta "¿por qué te mostramos esta opción?" (acierta o no) y confianza 1–7 en la frase; **G0 frente a G1** intra-sujeto con orden contrabalanceado y prueba pareada (Wilcoxon); se reporta con IC, sin declarar victoria con n = 30 si el IC cruza 0.
- **G3, si existe**: porcentaje que cree que la imagen es el producto real (meta < 5 %).
- **Criterio de salida de G1/G2**: no empeorar tiempo ni SUS frente a G0 y mejorar al menos confianza o comprensión; si no, se queda en G0.

## 7. Esfuerzo (equipo de 4, días-persona) [PROP]

| Bloque | Días |
|---|---|
| Catálogo: endpoint compatibles, `solo_representantes`, medición de pool por spec, completar atributos de C001 | 3 |
| Inteligencia: capa de sustituciones por `item_id`, 3 endpoints, validaciones, eventos, corrección de `_anclas_de_personaje`, pruebas | 4 |
| Contrato TS, rutas BFF, modo simulado | 1,5 |
| Web: lista de cuadernos, carrusel y sus estados, hoja móvil, accesibilidad, total en vivo (reutiliza patrón de `SelectorCuadernos`, ver Actualización) | 3 |
| Integración con checkout, consolidación, prueba de propiedad de cumplimiento, revisión axe y manual en móvil | 2,5 |
| **Núcleo (G0, cubre UI-03)** | **14** → 4 días calendario con 4 personas (era 15) |
| Opcional, independiente: bloque Portada (extraer rama, 24 SVG, persistir y mostrar) | +3 a 4 |
| G1 (lote, caché, verificador, plantilla de respaldo) | +2 |
| G2 (esquema de interfaz, renderizador de lista blanca, caché) | +4 a 5 |
| G3 (spike más revisión legal): ahora = portada generativa sobre los 8 diseños, vocabulario cerrado | +2 a 3 |
| G4 (chat con herramientas) | +8 a 15 (cifra del documento del equipo) |

El documento del equipo estima 2 días para el intercambio (A6); aquí son 14 porque cuenta varias líneas por concepto, validación de cumplimiento y capa de sustituciones, que A6 no incluía.

## 8. Riesgos

- **Pool vacío**: sin atributos en la mitad de C001 y sin ferrocarril 50 h, la mayoría de líneas tendrá 0 a 2 alternativas. Mitigación: medir antes, curar atributos, copy honesto para "única opción".
- **Cumplimiento roto** por el reemplazo por concepto del personaje (§4.8) o por una sustitución sin validar. Mitigación: único escritor con revalidación y prueba de propiedad.
- **Corromper el kit canónico** si se escribe `LINEA` de un trabajo apuntado por `kit_canonico`. Mitigación: capa por puntero y copy-on-write.
- **Consolidación entre hermanos**: cambiar el sku de una línea consolidada altera ahorros y unidades. v1 la bloquea.
- **Precio viejo**: entre elegir y pagar el precio cambia. Mitigación: revalidar al elegir y en `ordenar`.
- **Latencia y costo de LLM** en el camino de compra: se evita con lote y caché; nada síncrono en la ruta crítica.
- **Alucinación o afirmaciones de calidad** en G1/G2: verificador determinista y plantilla.
- **PI y menores** en G3 (personajes licenciados, nombre del niño): no generar productos; nombres solo en el navegador.
- **Sin pruebas automáticas en `apps/web`** (solo lint y typecheck): hace falta decidir un runner antes de poner lógica de total en el cliente.
- **Alcance**: el documento del equipo recomienda v2 para el chat; construirlo sin requisito rompe la trazabilidad del SRS. Se necesita un requisito nuevo si G2 o G4 entran.

## 9. Decisiones que necesito de ti
1. ¿v1 = carrusel (G0) y G1, dejando G2 a G4 como v2, según la recomendación (a) del documento del equipo?
2. ¿Se bloquea toda sustitución que no cumpla la spec (propuesto) o se deja pasar con aviso explícito?
3. ¿Se acepta empezar solo por `parent_apply` y dejar el flujo PDF con copy-on-write para después?
4. ¿Quién completa los atributos de C001 en catálogo y cuándo?
5. (Rama del carrusel de portadas) ¿La portada es decorativa o se imprime/forra? ¿Se permite texto libre en ella (nombre de menor)? ¿Se rescata por extracción (recomendado) y quién dibuja los 24 SVG vacíos?
