# Enmienda a la WBS v3 (alineación con el producto final y con la VFP v4)

Documento de trabajo, no es una versión aprobada de la WBS. Fuente: `WBS/WBS_Tukit_ISIS2610G19_v3.docx` (y su csv). No se modificó el original. Patrón: Texto actual (cita textual) / Texto de reemplazo / Por qué. Los números de línea son los del texto convertido y sirven solo para ubicar. Los códigos de tarea (F4-9.1, etc.) se conservan.

## W1. Nombres de los cuatro objetivos de optimización

**W1.a Tarea F4-9.1 (línea 296)**

Texto actual: "Motor NSGA-II/MOKP en pymoo con TODAS las restricciones: 4 objetivos (min costo, max fidelidad de marca, max calidad, max cobertura) + restricciones (cobertura, stock, categoría, presupuesto) + semilla fija; pesos desde PerfilSocioeconomico + P9"

Texto de reemplazo: "Motor NSGA-II/MOKP en pymoo (fail-loud) con 4 objetivos (min costo, max fidelidad de marca, max disponibilidad, max afinidad de personaje) + restricciones por construcción (disponibilidad y categoría filtran candidatos) + restricciones del solucionador (cobertura mínima) + semilla fija. Enumeración exacta hasta 4.096 combinaciones y NSGA-II por encima. El presupuesto se aplica después del frente (ADR 0029)."

Por qué: el código define costo, fidelidad, disponibilidad y personaje (ADR 0030). "Calidad" y "cobertura" eran los nombres del diseño inicial. Los pesos ya no salen del optimizador sino de la selección a posteriori (W1.c).

**W1.b Tarea F4-9.2 (línea 304) y su hecho mínimo (línea 310)**

Texto actual: "Frente de Pareto → 3 kits (Ahorrador/Fan/Premium) + hipervolumen + pruebas unitarias del motor" y "Hecho mínimo: 3 kits (Ahorrador/Fan/Premium) extraídos vía PseudoWeights + hipervolumen reportado..."

Texto de reemplazo: "Frente de Pareto → 4 kits (Ahorrador/Fan/Premium/A tu Medida) + hipervolumen + pruebas unitarias del motor" y "Hecho mínimo: 4 kits extraídos del frente + hipervolumen reportado + suite pytest (objetivos, restricciones, reproducibilidad)..."

Por qué: ADR 0030 agrega el perfil A tu Medida (presupuesto declarado por el padre). La guía "Cómo empezar" (línea 306) usa PseudoWeights con tres vectores; se reemplaza por la regla de recomendación del producto (W1.c).

**W1.c Selección a posteriori (nuevo, añadir a F4-9.2)**

Texto de reemplazo: "Selección a posteriori con MAUT: U = w_precio·u_costo + (w_marca+w_calidad)·u_fidelidad + w_personaje·u_personaje, con los pesos de la encuesta P21 (0,285 / 0,273 / 0,255 / 0,187). Regla de recomendación: Fan si pidió personaje; si no, A tu Medida cuando ese kit existe, es decir, cuando eligió el punto medio de gasto o declaró un tope (con el tope declarado o, sin tope, a mitad de camino entre Ahorrador y Premium); si no existe, Premium cuando el sobreprecio aceptado es de al menos 10 % y MAUT lo prefiere; en otro caso Ahorrador; y si el elegido se pasa del tope, el de mayor fidelidad que cabe."

Por qué: reemplaza los pesos supuestos 0,35/0,30/0,25/0,10. Se declara el supuesto de independencia preferencial. MAUT ya está en el código (`elegir_recomendado_maut`, fusionado en `validacion/oe5`, a664810).

**W1.d Cobertura como "hecho mínimo" de F4-12.1 y cantidad de kits en F4-10.1 (línea 322)**

Texto actual: "vista de 3 kits (choice architecture, máx. 3)" y, en la línea 380, "registro→lista→match→3 kits→resolución→checkout mock→..."

Texto de reemplazo: "vista de 4 kits (Ahorrador, Fan, Premium, A tu Medida) con el recomendado destacado" y "registro→lista→match→4 kits→resolución→checkout Wompi sandbox→..."

Por qué: consistencia con los cuatro perfiles. Si el equipo prefiere mostrar solo los kits aplicables a la solicitud, ajustar "4 kits" a "hasta 4 kits".

## W2. Cantidad de listas: 20 frente a 17

**W2.a Tarea DW-4.4 (línea 124) y F3 (línea 274)**

Texto actual: "De-riesga la calidad de los datos de arranque (Excel ruidoso, 20 listas)." y "Script/notebook que corre el pipeline E2E sobre al menos 20 listas reales..."

Texto de reemplazo: "...(Excel ruidoso, 17 listas)." y "...sobre las 17 listas reales del consolidado..."

Por qué: las líneas 28, 72, 80 y 122 de la misma WBS dicen 17 listas ("consolidado de 17 listas de útiles"). Conteo desde los datos del repositorio (`tukit/datos/listas/colegios.csv` e `items_lista.csv`): 17 colegios con lista y 4.719 ítems. La cifra única para todos los documentos es 17; se retira el 20 y el 18. Los conteos del catálogo curado se citan solo del manifiesto final.

## W3. Checkout mock frente a Wompi sandbox

**W3.a Tarea F4-11.2 (línea 350), guía (línea 352), hecho mínimo (línea 356) y herramientas (línea 354)**

Texto actual: "checkout (mock, MUST) + seguimiento de pedido (estados simulados) + panel colegio B2B..." y "Checkout mock (MUST): 3 pasos (resumen→pago simulado→confirmación), `Pedido` con `estado: pendiente|confirmado`, sin pasarela real." y "4 pantallas SRS operativas (checkout mock, seguimiento con estados simulados, ...)".

Texto de reemplazo: "checkout con Wompi en sandbox (widget, ADR 0033; webhook de eventos, ADR 0034; modo por defecto simulado con WOMPI_MODO) + seguimiento de pedido por estados de la orden + derecho de retracto como caso (Ley 1480, art. 47) + panel de administración con detalle de orden y tickets, carga y revisión de listas B2B por el operador (el panel propio del colegio queda como alcance reducido y trabajo futuro)." Hecho mínimo: "checkout Wompi sandbox operativo, seguimiento, retracto, páginas legales (Ley 1581 y Ley 1480), mapa OSM y panel admin integrados al flujo del colegio piloto."

Por qué: el producto en `validacion/oe5` integra el widget y el webhook de Wompi. Dejar "mock" subestima lo entregado. La línea 354 nombra "React + API REST propia (Node/FastAPI)"; el stack real es Next.js y FastAPI, ajustar ahí.

**W3.b Tareas F4-12.1 y F4-12.2 (líneas 368 y 378)**

Texto actual: "Integración E2E completa (percepción→matching→optimización→web→checkout mock)" y "MVP web funcional (recomendador embebido, todas las pantallas núcleo del SRS)".

Texto de reemplazo: "...→checkout Wompi sandbox)" y se agrega "con NL2C (generative UI con guardrails) detrás de doble feature flag".

Por qué: el flujo E2E real termina en Wompi sandbox. NL2C forma parte del OE3 y está fusionado en `validacion/oe5`; se redacta como objetivo y entregable, sin cifras finales (ronda 3 en curso).

## W4. Fase 5: muestra e instrumentos

**W4.a Tareas F5-11.1 (línea 388), F5 hecho mínimo (línea 396), F5-13.2 (línea 416)**

Texto actual: "reclutamiento estratificado (meta n≥20; adelantado)", "lista de reclutamiento estratificada con n≥20 confirmados, antes de programar la primera sesión", "n<20 = exploratorio declarado".

Texto de reemplazo: "reclutamiento (mínimo n≥5 por ronda, ideal n≥20, Nielsen 1994)", "lista de reclutamiento con al menos 5 confirmados por ronda y meta de 20", "n<20 = exploratorio declarado; IC y pruebas se reportan con el n real".

Por qué: alinea con el SPMP (ENMIENDA_SPMP S5) y la VFP v4. Fechas reales: ronda 1 (formativa) 31-oct-2026 y ronda 2 (sumativa) 2-nov-2026; el plan decía 29 y 30 de octubre y se registra como cambio de cronograma.

**W4.b Tarea F5-12.1 (líneas 398 a 404)**

Texto actual: "SUS + NPS + NASA-TLX + baseline medible" y "3 instrumentos (SUS/NPS/NASA-TLX) listos para imprimir/digitalizar".

Texto de reemplazo: "SUS + NPS + pensamiento en voz alta + conteo de interacciones discretas como medida principal de carga cognitiva + RTLX (Raw TLX) como medida complementaria" y "3 instrumentos (SUS, NPS, RTLX) más la hoja de conteo de interacciones".

Por qué: se usa el RTLX (Hart, 2006) en lugar del NASA-TLX completo de 15 pares; los parámetros de las subescalas se mantienen (6, 0 a 100). Coincide con la enmienda al SRS (UI-07).

**W4.c Tarea F5-11.1 gate ético (línea 390)**

Texto de reemplazo: añadir "Datos de investigación eliminados 12 meses después de la aprobación del trabajo de grado; grabaciones hasta 30 días."

Por qué: plazos declarados en el consentimiento y en las páginas legales.

## W5. Despliegue y empaquetado

**W5.a Búsqueda de "Kubernetes", "React Native", "PSE", "ePayco"**

Resultado de la revisión: la WBS v3 no contiene paquetes con esos términos (ya excluyó app nativa, última milla y despliegue productivo; coincide con el riesgo R-06 del SPMP). No hay ítem que citar. Si se agrega una fila de despliegue, proponer: "Despliegue local con Minikube de los siete desplegables (identidad, catálogo, inteligencia, comercio, operación, puerta de enlace, ingesta) y cinco bases de datos".

Por qué: documenta el despliegue real sin inventar un paquete que no existía.

## W6. Totales

Texto actual (línea 483): "Total de tareas del WBS (14 semanas, S3–S14...): 45."

Texto de reemplazo: sin cambio si no se agregan filas. Si se agrega la fila de despliegue (W5.a) el total pasa a 46 y se recalcula la carga por integrante.

Por qué: evitar un total desfasado.

## Preguntas abiertas

1. Conteo del catálogo curado: citar solo del manifiesto final.
2. Si la tarea de detalle de orden y tickets debe figurar como fila propia (hoy está dentro de F4-11.2).
3. F4-11.2 incluye "panel colegio B2B" y F4-10.1 un "swap con recomputación de precio en vivo": en el producto no existe el panel del colegio (lo opera el administrador) y el ajuste de presupuesto en vivo es parcial. Se registran como alcance reducido, con justificación y trabajo futuro, y no se afirma que existan.
