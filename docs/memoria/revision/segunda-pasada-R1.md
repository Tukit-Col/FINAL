# Segunda pasada R1 (2026-11-05)

PDF revisado: `docs/memoria/main.pdf` (92 páginas, del 5-nov a las 16:12, commit 4f5e6d3). Página N impresa = página N+10 del PDF. Rango: Introducción en pp. 1–2 y Descripción general en pp. 3–8. Solo lectura.

Resumen: de los 26 ALTO y MEDIO de la primera pasada, 21 están resueltos, 4 parciales y 1 sin resolver (el 26, que además empeoró). Hay 5 hallazgos nuevos (2 altos). Lo más grave: la tabla de entregables ya no sale en el PDF, porque quedó dentro de un `\iffalse` en `anexo_tablas.tex:6-248`. Además, OE3 y OE4 no siguen la redacción aprobada en la VFP v4.

## (1) Estado de los hallazgos ALTO y MEDIO

| # | Sev. | Estado | Pág. nueva | Evidencia |
|---|---|---|---|---|
| 1 | ALTO | Resuelto | 4 | "el equipo de Tukit carga y publica la lista oficial…"; "Un canal para que el colegio publique sus propias listas quedó como trabajo futuro." |
| 2 | ALTO | Resuelto | 4 | "En la prueba ESC-D4, el armado de kits tuvo un percentil 95 de 0,31 s frente al límite de 8 s". |
| 3 | ALTO | Resuelto | 3–5 | "Oportunidad, Problema" va de la p. 3 (línea 13) a la p. 5 (línea 19, antes de "Descripción del Proyecto"): unas 2,4 páginas. |
| 4 | ALTO | Parcial | 4 | El párrafo económico pasó a pasado ("costó", "dejó", "fue"), pero la Propuesta y la Justificación siguen en presente: "Tukit es un sistema…", "El sistema recibe…", "Intervienen dos actores…", "El sistema es pertinente porque simplifica…", "Técnicamente es viable…". |
| 5 | ALTO | Resuelto | 4 | "La propuesta pertenece a la ingeniería de software, con componentes de inteligencia artificial y de optimización multiobjetivo." |
| 6 | ALTO | Resuelto | 5 (y Cap. VII) | `oe5.tex:17` ahora dice "seis acudientes del Colegio Agustiniano Ciudad Salitre, el colegio piloto", lo que concuerda con "padres del sector Salitre" del objetivo general y con HECHOS (fila OE5). |
| 7 | ALTO | Resuelto | 1, 4 | Introducción: "(el pago es simulado en esta versión)"; Propuesta: "y pagar, en modo simulado en esta versión". |
| 8 | ALTO | Resuelto | Resumen | `oe5.tex:20-21`: "los seis pagos se observaron porque su segunda grabación muestra el pago aprobado"; HECHOS lo confirma. El resumen ya es coherente. |
| 9 | MEDIO | Parcial | 1, 3 | La Introducción todavía repite Fenalco 35 % y 70 %, 1,17 millones, Sweller, las cuatro tiendas y TeacherLists, que el Contexto vuelve a dar en la p. 3. Ahora la repetición es más corta. |
| 10 | MEDIO | Resuelto | 1 | "\citep{teacherlists_retail_2026}, pero, hasta donde se revisó (Capítulo III), ninguna…". |
| 11 | MEDIO | Resuelto | 1 | "generación aumentada por recuperación (RAG) [Lewis et al.]". |
| 12 | MEDIO | Resuelto | 2 | "seis unidades desplegables"; HECHOS (fila Desplegables) ahora dice 6, con la ingesta reemplazada. |
| 13 | MEDIO | Resuelto | 5 | Cifras recalculadas y reproducibles ("script `docs/negocio/punto_equilibrio.py`", que existe). 91.401 − 62.049 = 29.352, es decir, los $29.353 con redondeo; 1,2 M / 29.353 = 41 y 15 M / 29.353 = 512, así que cuadran. Siguen sin fila en HECHOS. |
| 14 | MEDIO | Resuelto | 4 | "permitiría… aunque el despliegue fue local y no se ejercitó el escalado independiente". |
| 15 | MEDIO | Resuelto | 3 | "Iyengar y Lepper encontraron que…"; se quitó "paralizar la decisión". |
| 16 | MEDIO | Resuelto | 4 | "El perfil socioeconómico de la pregunta se operacionalizó como el presupuesto y el tope de gasto…". |
| 17 | MEDIO | Resuelto | 3 | Queda un solo párrafo de apertura, que enlaza con la Introducción ("La introducción mostró que…"). |
| 18 | MEDIO | Parcial | 6–8 | La p. 6 ahora dice qué método cubre cada OE, incluido el OE5 (ISO/IEC 25010 con protocolo registrado). Pero la Tabla 2 (`tab:crispdm-oe`) sigue sin filas para OE2 y OE5, y el texto de 3.1 no explica por qué, aunque la Tabla 1 asigna al OE5 la etapa "Evaluación". |
| 19 | MEDIO | Resuelto | 8 | La Tabla 2 dice "4.719 ítems"; HECHOS (fila Listas de útiles) explica la relación con los 3.608 del OE1. |
| 20 | MEDIO | Resuelto | 8 | La referencia a `tab:kits` salió del párrafo (la tabla ahora está en el cuerpo, `resultados.tex:202`) y la de constantes dice "Tabla 26 (Anexo X.3)". |
| 21 | MEDIO | Resuelto | 2 | "Los anexos solo guardan material de reproducción y auditoría." |
| 22 | MEDIO | Resuelto | 3 | Los competidores quedan en una sola oración corta con las cuatro citas. |
| 23 | MEDIO | Parcial | 4 | La oración de costos se reescribió, pero `descripcionGeneral.tex:83-87` sigue siendo una oración de unas 79 palabras ("Presentar pocas alternativas… beneficia a cada actor: …; …; y…"). |
| 24 | MEDIO | Resuelto | Resumen | "El trabajo caracterizó el dominio con entrevistas y una encuesta, eligió la arquitectura entre tres alternativas con ATAM…". |
| 25 | MEDIO | Resuelto | Resumen | "solo uno de cinco eligió el kit sin ayuda". |
| 26 | MEDIO | **No resuelto (empeoró)** | 6 | Ahora la tabla no está ni en el cuerpo ni en el anexo. Ver N1. |

## Hallazgos nuevos

| # | Pág. | Sección / archivo:línea | Lente | Severidad | Hallazgo | Evidencia (cita corta) | Sugerencia (≤1 frase) |
|---|---|---|---|---|---|---|---|
| N1 | 6 | Marco metodológico, entregables… / descripcionGeneral.tex:155; anexo_tablas.tex:6 y 198 | rúbrica | ALTO | La tabla de entregables, estándares y justificación que pide la plantilla ya no aparece en el PDF: `tab:entregables` quedó dentro de `\iffalse … \fi`, y nada en el cuerpo la reemplaza. La subsección se titula "entregables" y no los lista. `tab:anexos` da rutas, pero no estándar ni justificación por entregable. | `anexo_tablas.tex:6`: "\iffalse % … y entregables: ahora en el cuerpo"; `pdftotext` no encuentra "Entregables, objetivos" | Devolver la tabla al final de la subsección 3, como la pide la plantilla ("debe resumirse en la siguiente tabla"). |
| N2 | 5–6 | Objetivos Específicos / descripcionGeneral.tex:137-146 | rúbrica | ALTO | OE3 y OE4 no coinciden con la VFP v4 (`docs/entrega/VFP_ISIS2610G19_v4.docx`). OE3 cambió "búsqueda vectorial densa" por "búsqueda híbrida, léxica y semántica" y perdió NL2C. OE4 recibió NL2C y no trae "la afinidad de personaje", los cuatro perfiles ni "la pasarela de pagos para el cierre transaccional", que la VFP v4 sí trae. Un jurado compara los objetivos con los de la propuesta aprobada. | VFP v4, OE3: "…mecanismo de búsqueda vectorial densa…, incluyendo… (NL2C) mediante invocación de funciones…" | Copiar OE3 y OE4 tal como están aprobados (v3 o v4, según cuál sea la vigente) y explicar en otro lugar la búsqueda híbrida y el cambio de NL2C a OE4. Decisión de la conductora. |
| N3 | 8 | Tabla 2, fila OE3 Evaluación / descripcionGeneral.tex:241 | cifra | MEDIO | "Análisis del umbral de certeza τ, declarado sin calibrar" se quedó corto frente a Resultados, que ahora trae precisión-cobertura, ROC con AUC y validación cruzada (`resultados.tex:140-147`). También HECHOS (fila "Calibración (precisión, cobertura, AUC): No se citan") está atrasado respecto al commit 4774a0a. | "declarado sin calibrar" vs. "El AUC fue de \calTauAUC{}…; bastaría un τ entre…" | Decir "τ = 0,75 conservador; análisis de precisión-cobertura en Sec. VII.1" y actualizar la fila de HECHOS. |
| N4 | 7 | Tabla 1, fila Validación / descripcionGeneral.tex:200-203 | hilo | MEDIO | Los métodos del OE5 en la Tabla 1 no incluyen RTLX, que da una de las dos cifras principales del resumen (63 → 9), ni ISO/IEC 25010 ni el protocolo registrado que la p. 6 asigna al OE5. `hart_nasa_2006` está en el `.bib` y no se cita en el rango. | "Pruebas funcionales, no funcionales y de carga; SUS [..], NPS [..] y verbalización concurrente" | Agregar "RTLX \citep{hart_nasa_2006}" y "ISO/IEC 25010" a la celda. |
| N5 | 4, 8 | Justificación / descripcionGeneral.tex:91; Tabla 2 / línea 229 | claridad | BAJO | "ESC-D4" y "SRS" aparecen sin definirse en el rango (el lector no sabe que ESC-D4 es un escenario de calidad del diseño ni qué es el SRS). | "En la prueba ESC-D4, el armado de kits…" | "el escenario de calidad ESC-D4 (Cap. V)"; "especificación de requerimientos (SRS)". |

## (2) ¿Algo obliga a ir al anexo para entender el texto?

No. Las tres remisiones al anexo que quedan son opcionales:
- La Tabla 2 (OE4 Modelado) dice "Sec. VI.7 y X.8": el NL2C completo está en el anexo, pero el cuerpo lo resume (`desarrolloSolucion.tex:420-428`) y la Tabla 2 ya define NL2C.
- Los ciclos de calibración dicen "Tabla 26 (Anexo X.3)": es solo el registro de constantes, para auditoría.
- La Introducción dice que "los anexos solo guardan material de reproducción y auditoría", y eso se cumple en este rango.

Las siglas MAUT, NL2C, CGS-10, B2B2C, RAG, Pareto y τ se definen en la frase donde aparecen. Faltan ESC-D4 y SRS (N5). El único contenido que el texto promete y que no se encuentra en ningún lado es la tabla de entregables (N1).

## (3) Hilo de apertura y cierre, y la metodología visible

- **Introducción:** abre con el problema y cierra con una guía de lectura que asigna a cada capítulo su fase, su OE, su método y su etapa de CRISP-DM (IV = F1, OE1, Design Thinking y comprensión del negocio, IEEE 830; V = F2, OE2, ATAM, IEEE 1016; VI = F3 y F4, OE3 y OE4, CRISP-DM de datos a despliegue; VII = F5, OE5, ISO 25010 y protocolo). Cumple.
- **Cap. II:** abre retomando la Introducción ("La introducción mostró…") y anuncia lo que trae. Cierra con "El Capítulo III abre el contexto que sustenta estas fases". Cumple.
- **Subsecciones:** el Contexto termina en la oportunidad, la Formulación termina en la pregunta ("De ahí surge la pregunta…") y los Objetivos abren con "Cada objetivo corresponde a una fase…". Cumple.
- **Metodología (fase, método y etapa):** se ve en tres lugares: el párrafo de la p. 6, que da un método por OE; la Tabla 1, con fase, OE, etapa de CRISP-DM, métodos y resultado; y la Tabla 2, con la etapa por OE. Hay dos huecos: la Tabla 2 no tiene OE2 ni OE5 y no dice por qué (18, parcial), y la fila del OE5 en la Tabla 1 no nombra RTLX ni ISO 25010 (N4).
