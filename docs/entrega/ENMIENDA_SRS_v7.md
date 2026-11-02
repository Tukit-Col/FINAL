# Enmienda al SRS v6 para producir la v7 (alineación con el producto final y con la VFP v4)

Documento de trabajo, no es una versión aprobada del SRS. Fuente: `SRS/SRS_ISIS2610G19_v6.docx` (última fila de versión: v6.0, sep. 2026). No se modificó el original. Patrón: Texto actual (cita textual) / Texto de reemplazo / Por qué. Los números de línea son los del texto convertido y sirven solo para ubicar. Se propone una fila v7.0 en el control de versiones, con la fecha real de edición y sin retrodatar. El SRS v6 ya nombra a Wompi (ADR 0011), así que no necesita el cambio de pasarela del SPMP.

## R1. UI-07: la carga cognitiva se mide con interacciones y RTLX, no solo con NASA-TLX

**R1.a Requisito UI-07 (línea 678)**

Texto actual: "La carga cognitiva percibida por el padre al usar Tukit debe ser menor que la del proceso de compra tradicional. Se medirá con NASA-TLX en el estudio de usabilidad de la Fase 5."

Texto de reemplazo: "La carga cognitiva del padre al usar Tukit debe ser menor que la del proceso de compra tradicional. La medida principal es el conteo de interacciones discretas (clics, toques y campos completados) para completar la compra, registrado en las sesiones de la Fase 5 y comparado con el flujo de referencia. La medida complementaria es el RTLX (Raw TLX, seis subescalas de 0 a 100, Hart 2006), aplicado tras cada tarea."

Por qué: el conteo de interacciones es observable y no depende de que el participante recuerde el flujo tradicional; el RTLX es una escala validada y más corta que el NASA-TLX completo de 15 pares (Hart y Staveland, 1988). Es lo que la VFP v4 y la enmienda de la WBS declaran.

**R1.b Criterio de aceptación de UI-07 (mismo renglón, línea 678)**

Texto actual: "Los padres del estudio piloto reportan carga cognitiva percibida menor al comprar con Tukit vs. su método habitual. Resultado cualitativo aceptable."

Texto de reemplazo: "El número de interacciones discretas con Tukit es menor que el del flujo de referencia, y el RTLX se reporta con su intervalo de confianza. Con n menor que 20 el resultado se declara exploratorio."

Por qué: el criterio cualitativo no distinguía entre medidas; ahora hay un criterio verificable con el n real.

**R1.c Matriz de verificación (línea 1133) y de trazabilidad (línea 1407)**

Texto actual: "UI-07 NASA-TLX menor que método tradicional A, Análisis estadístico de cuestionarios piloto Fase 5" y "UI-07 RNF F5 Carga cognitiva apps/web Fase 5 A NASA-TLX vs método tradicional".

Texto de reemplazo: "UI-07 Interacciones discretas y RTLX menores que el método tradicional" y "UI-07 ... Fase 5 A Interacciones y RTLX vs método tradicional".

Por qué: consistencia con R1.a.

**R1.d Objetivo general (línea 199)**

Texto actual: "midiendo su efecto sobre la carga cognitiva (NASA-TLX), la usabilidad (SUS ≥68) y la satisfacción del usuario"

Texto de reemplazo: "midiendo su efecto sobre la carga cognitiva (interacciones discretas y RTLX), la usabilidad (SUS ≥68) y la satisfacción del usuario (NPS)"

Por qué: consistencia con R1.a.

## R2. Línea 1142: la encuesta (n = 60) no es la muestra de usabilidad

Texto actual: "Se realizarán sesiones de prueba de usabilidad con padres del Agustiniano Ciudad Salitre (N = 65 recibidas, n = 60 analizables; muestra de un solo colegio, sesgada hacia estrato 4) utilizando NASA-TLX (carga cognitiva) y SUS (usabilidad)."

Texto de reemplazo: "Se realizarán dos rondas de pruebas de usabilidad con padres: una formativa (31 de octubre) y una sumativa (2 de noviembre), con pensamiento en voz alta, SUS, NPS, conteo de interacciones discretas y RTLX. La muestra mínima es de 5 participantes por ronda y la ideal de 20 (Nielsen, 1994). La encuesta de requerimientos del Agustiniano Ciudad Salitre (N = 65 recibidas, n = 60 analizables; muestra de un solo colegio, sesgada hacia estrato 4) es un instrumento distinto y no es la muestra de usabilidad."

Por qué: el renglón presenta la encuesta de 60 como si fuera la muestra de la prueba. Fechas reales confirmadas por la coordinación: 31-oct-2026 y 2-nov-2026. El plan del 29 y 30 de octubre se anota en la fila v7.0 como cambio de cronograma.

## R3. Total de requisitos: 131 frente a 132

Texto actual (línea 52, fila v6.0): "La columna Modulo de los 131 requisitos pasa a llamarse Servicio..."

Texto de reemplazo: en la fila v7.0, "El SRS contiene 132 requisitos (67 RF, 49 RNF y 16 RML)". La fila v6.0 no se reescribe; se agrega la aclaración en v7.0: "la v6.0 decía 131 por un error de conteo".

Por qué: verificado contando los identificadores únicos de la tabla 39 del docx: 132 (RF 67, RNF 49, RML 16). Buscar otras apariciones de "131" en el SRS y en el índice del docx antes de aplicar; la búsqueda por texto solo encontró esta.

## R4. Estados de resolución y número de kits

**R4.a NR-01 (línea 614) y AD-01 (línea 688)**

Texto actual: "asignando un estado: COINCIDENCIA, COINCIDENCIA_PARCIAL, o SIN_COINCIDENCIA." y "ítems con estado COINCIDENCIA_PARCIAL o SIN_COINCIDENCIA."

Texto de reemplazo: "asignando un estado: RESUELTO_AUTO, AMBIGUO, SIN_MATCH o HUECO_CATALOGO." y "ítems con estado AMBIGUO o SIN_MATCH."

Por qué: son los estados del código (resolvedor híbrido léxico más coseno, umbral τ por defecto 0,75). Equivalencias: COINCIDENCIA = RESUELTO_AUTO; COINCIDENCIA_PARCIAL = AMBIGUO; SIN_COINCIDENCIA = SIN_MATCH o HUECO_CATALOGO (el hueco es un ítem sin producto en el catálogo curado).

**R4.b OP-01 (línea 640), UI-02 (línea 668), DP-03 (línea 774), alcance (líneas 361, 477, 528), verificación (líneas 1125 y 1131)**

Texto actual: "El sistema debe generar exactamente 3 kits diferenciados: Ahorrador, Fan y Premium, con precios y composición visiblemente distintos entre sí." y "La PWA debe mostrar los 3 kits (Ahorrador, Fan, Premium)..."

Texto de reemplazo: "El sistema debe generar los kits aplicables entre cuatro perfiles diferenciados: Ahorrador, Fan, Premium y A tu Medida (este último cuando el padre declara un tope de presupuesto), con precios y composición visiblemente distintos entre sí." y "La PWA debe mostrar los kits (Ahorrador, Fan, Premium y A tu Medida)...". Reemplazar "los tres kits" por "los kits" en DP-03, línea 477 y línea 528.

Por qué: ADR 0030. Confirmar en el producto si siempre se muestran los cuatro o solo los aplicables, y ajustar la redacción "exactamente".

**R4.c OP-07 (línea 652)**

Texto actual: "El sistema debe recomendar uno de los tres kits generados por OP-01 ... derivando la recomendacion del perfil socioeconomico declarado (PS-01 a PS-05) y de la restriccion de presupuesto si el padre la fijo."

Texto de reemplazo: "El sistema debe recomendar uno de los kits generados por OP-01 con una regla explícita: Fan si pidió personaje; si no, A tu Medida cuando ese kit existe, es decir, cuando eligió el punto medio de gasto o declaró un tope (con el tope declarado o, sin tope, a mitad de camino entre Ahorrador y Premium); si no existe, Premium cuando el sobreprecio aceptado es de al menos 10 % y MAUT lo prefiere; en otro caso Ahorrador; y si el elegido se pasa del tope, el de mayor fidelidad que cabe. La utilidad MAUT se calcula a posteriori sobre el frente con los pesos de la encuesta (P21: 0,285 precio, 0,273 marca, 0,255 calidad, 0,187 personaje), bajo el supuesto declarado de independencia preferencial."

Por qué: sustituye los pesos supuestos 0,35/0,30/0,25/0,10 por los medidos. Los pesos P21 ya están en el código (`PESOS_POR_OMISION`, a664810).

## R5. Requisitos nuevos o a revisar por el producto final (propuestos, sin IDs asignados)

1. Retracto: el padre puede retractarse en 5 días hábiles y recibir el reembolso en 30 días calendario (Ley 1480 de 2011, art. 47). Texto actual de referencia (línea 726): "gestion de devoluciones, retracto y reversion del pago en los terminos de la Ley 1480 de 2011". Reemplazo: añadir los plazos y la gestión como caso de la orden en el panel admin.
2. Páginas legales de términos y privacidad (Ley 1581 de 2012, Decreto 1377 de 2013, Ley 1480), con datos de investigación eliminados 12 meses después de la aprobación del trabajo de grado y grabaciones hasta 30 días.
3. NL2C: el padre expresa preferencias en lenguaje natural; el sistema las traduce a R = {filtros duros, pesos NSGA, preferencias PRM} mediante un plan validado (Pydantic con campos extra prohibidos), interfaz generativa armada por el servidor y validada de nuevo en la web, doble feature flag y límite de tasa en la puerta de enlace (ADR 0047). Sin cifras finales de utilidad ni de tasa de éxito de ataque: la ronda 3 está en curso con un criterio modificado. NL2C está fusionado en `validacion/oe5`.
4. Detalle de orden en el panel admin, tickets y mapa OSM de entrega.

Por qué: son funciones entregadas en `validacion/oe5` sin requisito que las respalde. Se enuncian aquí para que el equipo asigne los IDs y la prioridad MoSCoW.

## R6. Línea 403: PWA offline-first y orden de medios de pago

Texto actual: "La PWA debe funcionar en modo offline-first para visualizacion de kits ya generados (Service Worker con cache local)." y "PSE como medio de pago preferente, en la primera posicion de la lista de medios".

Texto de reemplazo: mantener PSE preferente (comisión cercana a 1,49 % frente a cerca de 2,99 % de tarjeta; verificar vigencia). Marcar offline-first como "parcial: pendiente de verificar en el producto" si no hay Service Worker con caché de kits.

Por qué: no se confirmó en el código que el modo sin conexión esté entregado; no se afirma lo no verificado. Capacitor no está en el código; el SRS no lo menciona y no requiere cambio.

## R7. Normativa: se retira la Resolución 019805 de 2025 (y la Circular 002) como fuente

Texto actual (línea 457, y referencia [14], línea 303): "el articulo 14 de la Resolucion 019805 del 30 de septiembre de 2025 del Ministerio de Educacion Nacional ... La Circular 002 del 8 de enero de 2026 del mismo Ministerio lo reitera" y "Resolucion 019805 del 30 de septiembre de 2025 (Manual de Autoevaluacion y Clasificacion ...), art. 14; Circular 002 del 8 de enero de 2026, num. 6 y 7; y Ley 1269 de 2008, art. 1".

Texto de reemplazo: citar solo la Ley 1269 de 2008, art. 1 (parágrafo 1° del art. 203 de la Ley 115 de 1994): entrega de la lista completa en la matrícula, aprobada por el Consejo Directivo, sin exigir que los padres entreguen los materiales al colegio. Quitar la Resolución 019805 y la Circular 002 del texto, de la referencia [14] y de la fila v5.0 del control de versiones solo si se acuerda reescribir esa fila; en v7.0 se anota el retiro.

Por qué: la Resolución 019805 no está en el portal del Ministerio y la memoria ya la retiró; no se mantiene nada sin verificar. La Ley 1269 sí se verificó (Secretaría del Senado). La Circular 002 tampoco se pudo verificar en esta revisión.

## R8. Capacitor (línea 865, PT-02)

Texto actual: "El artefacto empaquetado con Capacitor, cuando se publique, hereda ese mismo umbral..."

Texto de reemplazo: "Si en el futuro se empaqueta con Capacitor (trabajo futuro, no existe en el código), el artefacto heredará el umbral de versiones de la PWA."

Por qué: evitar que el SRS dé por existente un artefacto que no existe.

## Preguntas abiertas

1. Si el producto muestra siempre cuatro kits o solo los aplicables.
2. Fusión de MAUT (S2) en `validacion/oe5`.
3. Offline-first no verificado.
4. Panel de colegio B2B (Módulo 7, CO-01 y CO-02): no existe en el producto; pasa a alcance reducido con trabajo futuro, y el SRS lo marca [NÚCLEO]. Decisión de la coordinación: registrarlo como reducción, no afirmarlo.
5. Panel de privacidad (PV-02): se mantiene como entregable; está en implementación.
