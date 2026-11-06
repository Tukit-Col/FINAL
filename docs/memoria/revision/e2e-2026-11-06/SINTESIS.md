# Síntesis de la revisión end-to-end (2026-11-06)

## 1. Veredicto

La memoria se lee de corrido en su estructura: cada capítulo abre mirando al anterior y casi todos cierran hacia el siguiente, y los cinco OE tienen trazabilidad de objetivo a conclusión. Faltan dos puentes (cierre del Capítulo II y apertura del VIII) y el orden de las secciones casi nunca se anuncia al abrir. El problema más repetido es la jerga sin definir en el primer uso (más de 90 hallazgos), seguido de contrastes con negación y de seis contradicciones internas que sí cambian lo que el lector entiende (CRISP-DM en OE5, "solo Tukit parte de la lista oficial", suma 4.719, "dos actores", n de las tareas del OE5, "indicativa" frente a "cumplido").
Frente a una maestría, el rigor estadístico y de arquitectura está a la altura o por encima (IC, bootstrap, ATAM con tres alternativas, 49 ADR, amenazas a la validez). Queda por debajo en estado del arte académico y en la muestra de usuarios (n = 6) y de percepción (10 documentos). El criterio más débil de la rúbrica es Entorno y herramientas (parcial); Expresión escrita está cubierto con ajustes, que son esta lista.

## 2. Top 10 cambios

| ID | Dónde | Qué cambia y por qué | Páginas |
|---|---|---|---|
| T1 | descripcionGeneral:271, 287, introduccion:62 (A1, A2) | Quitar la etapa CRISP-DM asignada a OE5 y corregir "solo OE3 y OE4" (la tabla trae OE1). Contradice el texto y la regla de metodología. | 0 |
| T2 | descripcionGeneral:170, introduccion:53, conclusiones:9, abstract (A4, A5, I2, J1, J3) | Un solo patrón de metodología por OE (Design Thinking+IEEE 830; RUP+IEEE 1016+ATAM; SCRUM+CRISP-DM; ISO 25010+protocolo), sin "contenedora". Dejarlo completo en Cap. II y corto en los demás. | -0,2 |
| T3 | contextoProyecto:90-98 y 193 (B1, B3) | Borrar el párrafo duplicado y corregir "solo Tukit parte de la lista" (la tabla marca cumple a TeacherLists y 1st Day). | -0,3 |
| T4 | conclusiones:58, analisisProblema:268 (I1, C18) | 3.608 + 1.109 = 4.717, no 4.719. Verificar contra la hoja canónica antes de tocar el texto. | 0 |
| T5 | desarrolloSolucion:12, 418 y orden de \input (E1, E32) | Referencia errónea y optimización insertada después de la web. Mover el \input antes de la web (hilo.md) o poner el puente; se elige una. | 0 |
| T6 | desarrolloSolucion:370, oe5:60, 89, resultados:273 (E29, H14, H15, G27) | Conciliar n por tarea, SUS con n=6, "las cuatro se hicieron" y "indicativa" frente a "cumplido". Es donde un jurado más pregunta. | +0,2 |
| T7 | analisisProblema:165, 212, 254 (C9, C14, C17) | Explicar los códigos PE/PV antes de la tabla, partir el párrafo técnico y dejar claro cuál flujo es el construido. | +0,3 |
| T8 | descripcionGeneral:89, 105, 304, disenoSolucion:105 (A22, D11, A33) | Definir ESC-D4, p95, 429, disyuntor y CGS-10 antes de usarlos. | +0,2 |
| T9 | resultados:4, 168, 177, 232 y oe5:12 (G1, G20, G21, G26, H11) | Apertura con orden, y definir hipervolumen, SUS, RTLX, NPS, C1-C3 en el primer uso. | +0,5 |
| T10 | introduccion:40, 46, contextoProyecto:52, conclusiones:29-30 (A7, A8, B7, I7-I9) | Definir NSGA-II, RAG, B2B2C, contribución y punto de equilibrio; partir los párrafos de mezcla. | +0,4 |

## 3. Brechas de maestría

Se cierran sin datos nuevos:
- Estado del arte académico: añadir 3 o 4 citas y una tabla corta con limitaciones (candidatas con URL en benchmark-maestria.md: HiMARS 2604.07572, COMO-MAB 1803.04039, Block-SCL 2207.02008, OCR-or-Not 2603.02789, DART 2609.12349). Abrir cada PDF antes de citar. Costo: +0,5 página.
- Impacto ambiental y tecnológico, hoy más corto que el social y el económico: dos o tres frases en conclusiones:30, con hechos ya citados.
- Aclarar que la comisión del 15 % es supuesto (ya lo dice el texto; hacerlo visible).

Solo se pueden declarar como límite:
- SUS con n = 6 frente a 103 de DART.
- Conjunto de percepción de 10 documentos con oro armado desde un motor.
- Un solo colegio, un solo revisor para τ, pago simulado, sin tesis de maestría comparable con ATAM y SUS (búsqueda manual pendiente).

## 4. Hallazgos por archivo (deduplicados)

Cada fila resume el hallazgo. El texto LaTeX propuesto de cada uno está en el informe de su capítulo; en hallazgos.json va solo el resumen. IDs: A descripcionGeneral/introduccion, B contextoProyecto, C analisisProblema, D disenoSolucion, E desarrolloSolucion, F optimizacion, G resultados, H calidad y oe5, I conclusiones, J abstract.

Se fusionan por duplicado: A4/A5/I2/J1/J3 (metodología por OE, aplicar el mismo texto), A22/D11, A33/E7/G6 (CGS-10 y oro: definir una vez en Cap. II y remitir), E18/E25/F11 (τ y pesos: la derivación queda solo en optimizacion.tex).

Choques entre propuestas:
- C18 e I1: la propuesta de C18 repite 4.719 = 3.608 + 1.109; no aplicar hasta resolver T4.
- I18 dice que C3 se alcanzó en T6 y T1; oe5.tex (H15) dice que no se alcanzó en T1. Gana oe5.tex.
- E32 propone un puente; hilo.md propone mover el \input. Elegir una.
- A1 propone "cuando corresponde" en introduccion:62; H1 y G1 asignan evaluación CRISP-DM solo a OE3 y OE4: coherente con T1.
- D27 quita la revocación parcial; confirmar con la autora si prefiere desarrollarla.
- A3: "OE3 y OE4" para el Sistema Tukit; hilo.md ubica el asistente NL2C en OE4 y el objetivo literal en OE3. Decidir antes de editar la tabla (A27/A32).

| ID | Sev | Tipo | Archivo:línea | Resumen |
|---|---|---|---|---|
| A1 | alta | coherencia | descripcionGeneral:271 | Tabla fases: OE5 sin etapa CRISP-DM (usa ISO 25010 + protocolo); introduccion L62 "cuando corresponde" |
| A2 | media | coherencia | descripcionGeneral:287 | La tabla CRISP-DM cubre OE1 (solo comprension), OE3, OE4; OE2 con ATAM, OE5 con ISO 25010 |
| A3 | baja | coherencia | descripcionGeneral:193,219 | Celdas de objetivo vacias: "OE1 a OE5" y "OE3 y OE4" |
| A4 | alta | rigor | descripcionGeneral:170 | Quitar "contenedora"; definir SCRUM/Kanban/RUP/ATAM/CRISP-DM y asignar metodo por OE (texto completo en tarea) |
| A5 | alta | repeticion | introduccion:53 | Parrafo metodologia corto con metodo por OE, remite al Cap. II; define SRS, SDD, plan |
| A6 | media | jerga | introduccion:31 | Definir multimodal y renglon (una linea por util pedido) |
| A7 | media | jerga | introduccion:40 | Definir NSGA-II (algoritmo genetico que mejora un grupo de kits) |
| A8 | media | hilo | introduccion:46 | Partir parrafo L43-51: RAG, servicios (cinco + gateway = seis; septimo ingesta), piloto en un colegio |
| A9 | media | rigor | descripcionGeneral:16 | Comercio electronico: cifra COP 105 billones es de todo el comercio, no de utiles |
| A10 | baja | hilo | descripcionGeneral:17 | Quitar frase que habla del documento; puente a decision/psicologia |
| A11 | media | jerga | descripcionGeneral:19 | Definir carga cognitiva y memoria de trabajo |
| A12 | media | rigor | descripcionGeneral:22 | Puente Iyengar-Lepper a lista escolar |
| A13 | media | rigor | descripcionGeneral:24 | "Los actores" -> comercios que venden utiles, remite al Cap. III |
| A14 | media | coherencia | descripcionGeneral:26 | TeacherLists: "hasta donde se reviso" |
| A15 | baja | jerga | descripcionGeneral:28 | Reactivo/proactivo y "constituyo" -> lenguaje llano |
| A16 | media | rigor | descripcionGeneral:33 | "Ninguno" -> "hasta donde se reviso (Cap. III)"; definir renglon |
| A17 | media | repeticion | descripcionGeneral:37 | "dimensiones" -> "etapas" |
| A18 | baja | ia | descripcionGeneral:47 | "madurez reciente" -> citas concretas |
| A19 | baja | jerga | descripcionGeneral:66 | "operacionalizo" -> "se tradujo en dos datos" |
| A20 | media | coherencia | descripcionGeneral:69 | "dos actores" -> de los cuatro del Cap. IV; definir PWA |
| A21 | media | rigor | descripcionGeneral:80 | "simplifico... por completo" -> "busca simplificar", remite a Cap. VII |
| A22 | media | jerga | descripcionGeneral:89 | Definir ESC-D4 y percentil 95 antes de la cifra |
| A23 | media | jerga | descripcionGeneral:92 | Definir microservicios y PostgreSQL/RabbitMQ/Redis/pymoo |
| A24 | media | jerga | descripcionGeneral:97 | Definir kit canonico, contribucion, punto de equilibrio |
| A25 | baja | coherencia | descripcionGeneral:102 | 29.353 vs resta 29.352: aclarar decimales (no cambiar cifra) |
| A26 | media | rigor | descripcionGeneral:103 | 1.340 familias: indicar metodo (matricula e hijos por familia) |
| A27 | media | jerga | descripcionGeneral:165 | Definir busqueda densa/lexica y NL2C; quitar contraste con negacion |
| A28 | baja | conector | descripcionGeneral:162 | Aposicion -> "quedaron fuera tres funciones: ..." |
| A29 | media | jerga | descripcionGeneral:205 | Definir MoSCoW, FODA, SAD, 4+1 |
| A30 | media | jerga | descripcionGeneral:228 | Definir SUS y NPS; anadir protocolo registrado de antemano (aplicados, n=6) |
| A31 | media | jerga | descripcionGeneral:263 | Definir corpus de oro y kappa de Cohen |
| A32 | media | jerga | descripcionGeneral:285 | Definir MAUT y NL2C |
| A33 | media | jerga | descripcionGeneral:304 | Definir conjunto de oro CGS-10 |
| A34 | media | jerga | descripcionGeneral:312 | Definir F1, tau, precision-cobertura |
| A35 | media | jerga | descripcionGeneral:318 | Definir P21 (columna de ordenamiento de criterios) |
| A36 | media | jerga | descripcionGeneral:324 | Definir optimo exacto, hipervolumen, auditorias de kits |
| A37 | media | ia | descripcionGeneral:340 | Quitar contraste "aprendizaje por refuerzo"; el sistema cambia solo cuando el equipo ajusta |
| A38 | media | hilo | descripcionGeneral:343 | Cierre: despliegue = trabajo futuro; puente al Cap. III |
| B1 | alta | repeticion | contextoProyecto:90 | Borrar parrafo duplicado L90-98; conservar el de Soluciones en Colombia con apertura "ninguna parte de la lista oficial" |
| B2 | media | hilo | contextoProyecto:100 | Mover parrafo academico a subsubseccion Trabajo academico; quitar relleno "tecnicas valiosas" |
| B3 | alta | coherencia | contextoProyecto:193 | "solo Tukit parte de la lista" contradice tabla (TeacherLists, 1st Day cumplen); reescribir cierre |
| B4 | media | coherencia | contextoProyecto:84 | "todas" -> "ambas" |
| B5 | media | hilo | contextoProyecto:4 | Intro anuncia orden; define CRISP-DM y Design Thinking |
| B6 | media | coherencia | contextoProyecto:36 | Cinco retos vs seis filas; quitar "cuerpo de conocimiento" y "apuesta" |
| B7 | alta | jerga | contextoProyecto:52 | Definir multimodal, RAG, NSGA-II, Pareto, hipervolumen, 3^n |
| B8 | media | jerga | contextoProyecto:132 | Definir OCR y Docling |
| B9 | baja | coherencia | contextoProyecto:123 | "seis formas": Textract y Watson cuentan como una |
| B10 | media | conector | contextoProyecto:141 | Conector causal "Como ninguna alternativa..." |
| B11 | baja | ia | contextoProyecto:150 | Quitar "conviene mirar"; Tukit cumple cinco, no controla inventario |
| B12 | media | hilo | contextoProyecto:71 | Apertura de Analisis del Contexto |
| B13 | baja | ia | contextoProyecto:49 | Contraste con negacion filtrado colaborativo |
| C1 | alta | hilo | analisisProblema:4 | Apertura con orden, quitar "estructural", definir resolucion |
| C2 | media | hilo | analisisProblema:14 | Apertura de Requerimientos |
| C3 | media | rigor | analisisProblema:21 | "posicion mas estrategica" -> "central" |
| C4 | media | jerga | analisisProblema:53 | Parentesis P21 -> frase propia |
| C5 | baja | repeticion | analisisProblema:54 | Quitar clausula repetida de preguntas |
| C6 | baja | jerga | analisisProblema:64 | Definir estrato 4 |
| C7 | alta | coherencia | analisisProblema:86 | Celda de requerimiento contiene conclusion; reemplazar por "Reducir el esfuerzo de comprar..." |
| C8 | media | jerga | analisisProblema:117 | Expandir SRS |
| C9 | alta | jerga | analisisProblema:165 | Explicar codigos PE/PV/CO antes de la tabla; aclarar RNF02 parcial |
| C10 | media | hilo | analisisProblema:182 | Abrir restricciones anunciando las tres; puente al final |
| C11 | baja | rigor | analisisProblema:190 | Nombrar derechos (consulta y reclamo) |
| C12 | baja | ia | analisisProblema:193,263 | "Es mejor porque" -> reformular (dos sitios) |
| C13 | media | jerga | analisisProblema:206 | Definir Wompi, ADR, idempotente, aviso firmado |
| C14 | alta | jerga | analisisProblema:212 | Partir parrafo de restricciones tecnicas y definir terminos |
| C15 | alta | hilo | analisisProblema:225 | Apertura de Especificacion Funcional |
| C16 | media | jerga | analisisProblema:242 | Definir multimodal, recuperacion hibrida; conectores entre etapas |
| C17 | alta | coherencia | analisisProblema:254 | Diseno preveia umbral; sistema construido revisa lista completa |
| C18 | alta | coherencia | analisisProblema:268 | Conciliar 4.719/3.608/3.610. OJO: la propuesta suma 3.608+1.109 = 4.717 (ver conflicto) |
| C19 | baja | ia | analisisProblema:238 | Contraste con negacion nino/nina |
| D1 | alta | hilo | disenoSolucion:4 | Apertura: expandir RUP, ATAM, SDD, anunciar orden de secciones |
| D2 | media | ia | disenoSolucion:4 | "Resultado central" -> "Como resultado"; definir desplegables |
| D3 | media | jerga | disenoSolucion:10 | Definir impulsor |
| D4 | media | ia | disenoSolucion:10 | Contraste con negacion -> "Ninguno depende de la carga" |
| D5 | media | jerga | disenoSolucion:38 | Quitar "un solo byte"; explicar asimetria de recuperacion |
| D6 | media | hilo | disenoSolucion:51 | Apertura de la seccion y definir puerta de enlace |
| D7 | media | jerga | disenoSolucion:51 | Sustituibilidad y ADR antes de definirse |
| D8 | media | conector | disenoSolucion:55 | Puente "El catalogo tambien cambio" |
| D9 | media | ia | disenoSolucion:57 | Quitar etiqueta en negrita y doble negacion; definir monolito |
| D10 | media | jerga | disenoSolucion:63 | Definir escenario de calidad, sensibilidad, trade-offs |
| D11 | alta | jerga | disenoSolucion:105 | Definir ESC-D4, p95, 429, disyuntor, funcion de aptitud antes de la tabla |
| D12 | baja | rigor | disenoSolucion:109 | Indicar que 429 es lo esperado |
| D13 | media | coherencia | disenoSolucion:122 | Anunciar tres vistas; pie de figura UML -> C4 |
| D14 | media | jerga | disenoSolucion:133 | Definir RabbitMQ, evento, procesos en segundo plano |
| D15 | media | jerga | disenoSolucion:144 | Definir bandeja de salida, entrega al menos una vez, idempotente |
| D16 | baja | jerga | disenoSolucion:146 | Definir Docker Compose, Redis, Jaeger, pgvector |
| D17 | baja | hilo | disenoSolucion:163 | Definir vista de proceso |
| D18 | baja | ia | disenoSolucion:172 | Reescribir descripcion del pago, definir webhook |
| D19 | alta | hilo | disenoSolucion:187 | Apertura de la seccion de datos; definir contexto delimitado, adaptadores |
| D20 | media | jerga | disenoSolucion:187 | Definir tenencia, referencia logica, cabecera |
| D21 | media | jerga | disenoSolucion:189 | Definir ambito, falla cerrada; quitar "endurecimiento productivo" |
| D22 | media | ia | disenoSolucion:196 | Contraste "Un repositorio no es un desplegable" |
| D23 | media | hilo | disenoSolucion:209 | Definir ADR aqui y remitir desde L51 |
| D24 | baja | repeticion | disenoSolucion:220 | Fila ADR 0001: nombrar los tres impulsores sin negacion |
| D25 | media | conector | disenoSolucion:232 | Conector y definir widget |
| D26 | media | ia | disenoSolucion:236 | "Dejaron de ser afirmaciones..." -> doce pruebas automaticas |
| D27 | media | coherencia | disenoSolucion:236 | Revocacion parcial del consentimiento no se desarrolla; reescribir (confirmar con autora) |
| E1 | alta | coherencia | desarrolloSolucion:12 | Referencia a secciones incorrecta (sec:optimizacion-cal) |
| E2 | media | jerga | desarrolloSolucion:27 | Definir pymoo, Amdahl, latencia |
| E3 | media | jerga | desarrolloSolucion:31 | Definir ADR, orquestacion, Temporal/Airflow, LangGraph |
| E4 | baja | repeticion | desarrolloSolucion:49 | Reescribir frase de tabla rag-fases |
| E5 | media | jerga | desarrolloSolucion:50 | "linea no integrada" -> prototipo no integrado |
| E6 | media | jerga | desarrolloSolucion:66 | Definir tau y abstencion en tabla |
| E7 | media | jerga | desarrolloSolucion:86 | Definir CGS-10 y oro |
| E8 | baja | ia | desarrolloSolucion:90 | Quitar "mirense"; nombrar el sesgo |
| E9 | baja | jerga | desarrolloSolucion:123 | Definir F1, oro propio, OCR |
| E10 | media | jerga | desarrolloSolucion:141 | "endurecimiento" y depuracion; definir Redis |
| E11 | baja | jerga | desarrolloSolucion:159 | Definir HNSW y trigramas |
| E12 | media | ia | desarrolloSolucion:161 | Contraste con negacion embeddings; definir MTEB |
| E13 | alta | jerga | desarrolloSolucion:166 | Definir RRF, codificador cruzado, AUC |
| E14 | alta | coherencia | desarrolloSolucion:168 | Rescate por coseno no coincide con el algoritmo (nucleo ausente, cos>=0,86, parte de 0,55) |
| E15 | media | jerga | desarrolloSolucion:171 | Explicar PE-04 y ML-09 del SRS |
| E16 | media | jerga | desarrolloSolucion:187 | Definir tau |
| E17 | media | ia | desarrolloSolucion:191 | Contraste con negacion tau |
| E18 | media | repeticion | desarrolloSolucion:193 | Remitir a Sec. optimizacion-cal en vez de repetir |
| E19 | baja | jerga | desarrolloSolucion:236 | "sintagma" -> sustantivo principal |
| E20 | media | hilo | desarrolloSolucion:240 | Dos pisos (0,55 y 0,5) aclarados |
| E21 | baja | ia | desarrolloSolucion:241 | "garantia que la tesis afirma", "se cuele" |
| E22 | media | hilo | desarrolloSolucion:284 | Apertura de subseccion optimizacion; definir frente de Pareto |
| E23 | media | jerga | desarrolloSolucion:297 | Definir Ahorrador/Premium/Fan/A tu Medida |
| E24 | media | rigor | desarrolloSolucion:302 | "Dossier OE1" no es fuente; quitar contraste |
| E25 | media | repeticion | desarrolloSolucion:311 | Pesos: derivacion solo en optimizacion; definir P21 |
| E26 | media | ia | desarrolloSolucion:322 | Apertura de la web simplificada |
| E27 | baja | jerga | desarrolloSolucion:354 | Hash -> commit del repositorio |
| E28 | media | ia | desarrolloSolucion:358 | Quitar "merecen una linea"; definir widget, idempotente, Nominatim |
| E29 | alta | rigor | desarrolloSolucion:370 | Tabla OE5: T1 n=6, T7 n=2, resto n=5; nombrar ISO 25010 y protocolo |
| E30 | media | jerga | desarrolloSolucion:384 | Definir MAUT e hipervolumen en tabla |
| E31 | baja | conector | desarrolloSolucion:393 | Completar frase truncada PE-04 |
| E32 | alta | hilo | desarrolloSolucion:418 | Puente antes de \input optimizacion (ver conflicto con hilo.md: mover el input) |
| E33 | media | hilo | desarrolloSolucion:423 | Asistente: por que existe |
| E34 | media | rigor | desarrolloSolucion:426 | Nombrar regla de los tres (3/81) |
| F1 | media | coherencia | optimizacion:4 | Resolucion asigna concepto, no producto |
| F2 | baja | repeticion | optimizacion:14 | Quitar repeticion de apertura |
| F3 | media | ia | optimizacion:28 | Contraste con negacion; cifras del corpus aparte |
| F4 | baja | jerga | optimizacion:51 | "surtible" -> disponible |
| F5 | baja | jerga | optimizacion:102 | Definir heuristica por perfil y distancia de apinamiento |
| F6 | media | conector | optimizacion:120 | Conector para el Fan |
| F7 | media | conector | optimizacion:148 | Partir parrafo de costos |
| F8 | media | hilo | optimizacion:171 | Definir a y b antes de usarlos |
| F9 | baja | jerga | optimizacion:186 | Definir bootstrap |
| F10 | media | jerga | optimizacion:198 | Definir pliegues e hipervolumen relativo |
| F11 | media | hilo | optimizacion:212 | Sensibilidad de pesos con frase propia |
| F12 | baja | hilo | optimizacion:225 | "fraccion menor" -> menor que el hipervolumen exacto |
| F13 | baja | ia | optimizacion:230 | Quitar frase que habla del documento |
| G1 | alta | hilo | resultados:4 | Apertura con orden de subsecciones; quitar "el capitulo encontro" |
| G2 | media | jerga | resultados:26 | Definir tau, F1, razon de hipervolumen, p95 antes de la tabla |
| G3 | media | jerga | resultados:40 | Definir motor de lectura |
| G4 | baja | jerga | resultados:38 | Definir arbol de utilidad |
| G5 | media | jerga | resultados:41 | Definir P y R de F1 |
| G6 | media | jerga | resultados:44 | Definir oro y CGS-10, sesgo visible |
| G7 | media | rigor | resultados:72 | Lectura separa ventaja sobre reglas (clara) y sobre Google Vision (menos segura) |
| G8 | media | jerga | resultados:76 | Definir temperatura 0, semilla, ESC-D1 |
| G9 | media | jerga | resultados:89 | Definir MRR@10 en palabras |
| G10 | media | jerga | resultados:94 | Definir pgvector, lexica, densa, RRF; conector con sistema construido |
| G11 | media | conector | resultados:101 | Definir p50 y MTEB; quitar contraste |
| G12 | media | rigor | resultados:106 | Definir Recall@10; por que no se usa ningun valor |
| G13 | media | jerga | resultados:112 | Definir SPMP; quitar contraste |
| G14 | baja | jerga | resultados:137 | Definir sensibilidad vs cobertura |
| G15 | baja | ia | resultados:141 | "Se destaca" -> "Se prefiere" |
| G16 | alta | coherencia | resultados:143 | Definir pliegues retenidos; debilidad de la validacion; 0,75 se mantiene |
| G17 | media | hilo | resultados:149 | Presentar el 83 %; definir sublistas y curaduria |
| G18 | media | ia | resultados:156 | Lectura concreta (97 de 100 vs 87) |
| G19 | baja | jerga | resultados:157 | "no hay acuerdo" -> no se midio; espejo de 838 productos |
| G20 | alta | jerga | resultados:168 | Definir frente optimo, hipervolumen, punto de referencia, p95 |
| G21 | alta | jerga | resultados:177 | Definir Ahorrador, ADR 0029, presupuesto |
| G22 | baja | jerga | resultados:181 | Definir voraz y aleatorio |
| G23 | media | hilo | resultados:186 | Conector "En cambio" para hogar extremo |
| G24 | alta | conector | resultados:191 | Puente a auditoria; definir cumple y hueco |
| G25 | media | hilo | resultados:221 | Lectura: cobros 49 a 58; puente al asistente |
| G26 | alta | hilo | resultados:232 | Asistente: reordenar Pregunta/Metodo/Metrica/Datos; definir inyeccion y regla de tres |
| G27 | alta | coherencia | resultados:273 | Conciliar "indicativa y no concluyente" con C1 y C2 cumplidos: resultados formativos |
| G28 | baja | ia | resultados:279 | Cierre sobreafirma ("queda evaluado") |
| H1 | alta | hilo | calidad:8 | Partir el Metodo en cinco familias de escenarios |
| H2 | alta | hilo | calidad:19 | Separar Resultado en pruebas, carga, seguridad, hallazgos |
| H3 | alta | jerga | calidad:21 | Carga: definir L-02, p95; separar equipos |
| H4 | media | jerga | calidad:28 | Explicar 401/404 y politicas por fila |
| H5 | media | jerga | calidad:33 | Explicar xfail estricto y registro |
| H6 | alta | rigor | calidad:41 | Recorrido funcional solo hasta el pago simulado |
| H7 | media | jerga | calidad:46 | Definir Probada/Parcial; T4, T6, C3 se definen en Sec. oe5 |
| H8 | media | hilo | calidad:70 | Lectura: solo una de ocho caracteristicas probada por completo |
| H9 | media | ia | oe5:4 | Pregunta sin contraste negado; puente |
| H10 | media | jerga | oe5:5 | Definir preregistrado y nivel de aceptacion |
| H11 | alta | jerga | oe5:12 | Definir SUS, RTLX, NPS, C1-C3 |
| H12 | media | coherencia | oe5:19 | Seis pagos vs T6 con cinco sesiones |
| H13 | media | coherencia | oe5:30 | Enumeracion paralela de tres problemas; T8 |
| H14 | alta | rigor | oe5:60 | SUS n=6 con p=0,0004: salvaguarda y definir d_z |
| H15 | alta | coherencia | oe5:89 | "Las cuatro se hicieron": precisar alcance; C3 solo en T6 |
| H16 | media | jerga | oe5:99 | Definir SEQ; agrupar desviaciones |
| I1 | alta | coherencia | conclusiones:58 | 3.608+1.109=4.717 no 4.719: verificar fuente (no cambiar cifra) |
| I2 | alta | hilo | conclusiones:9 | Apertura con orden y metodo por OE (RUP, SCRUM) |
| I3 | media | jerga | conclusiones:11 | Definir puntos de entrada, politicas por fila |
| I4 | media | jerga | conclusiones:13 | Definir funciones de aptitud y manifiesto |
| I5 | media | ia | conclusiones:17 | Apertura sin eslogan; orden del impacto |
| I6 | media | coherencia | conclusiones:27 | De seis a cinco: ACU-04 solo registro |
| I7 | alta | jerga | conclusiones:29 | Definir RTLX y SUS |
| I8 | alta | hilo | conclusiones:30 | Puente a modelo de negocio; B2B2C; partir parrafo |
| I9 | media | jerga | conclusiones:30 | Definir contribucion y punto de equilibrio |
| I10 | media | rigor | conclusiones:30 | "capacidad de pago heterogenea" sin fuente: citar o quitar |
| I11 | baja | ia | conclusiones:30 | "se acota" -> "solo valen para Colombia" |
| I12 | baja | ia | conclusiones:31 | Limite social de la muestra |
| I13 | baja | ia | conclusiones:58 | Cierre literario -> explicacion llana |
| I14 | alta | rigor | conclusiones:60 | OE2: anadir RUP; definir SDD, 4+1, 42010, ADR |
| I15 | media | rigor | conclusiones:62 | OE3: anadir SCRUM; definir percepcion, resolucion, oro, coseno |
| I16 | media | jerga | conclusiones:64 | OE4: anadir SCRUM; definir frente exacto, hipervolumen, NSGA-II |
| I17 | alta | hilo | conclusiones:66 | Mover limites de OE3 y OE4 a sus parrafos |
| I18 | alta | rigor | conclusiones:66 | C3 y por que OE5 Cumplido. OJO: propuesta dice C3 alcanzado en T1; oe5.tex dice que no (ver conflicto) |
| I19 | media | hilo | conclusiones:68 | Reescribir cierre "como suma de" |
| I20 | media | coherencia | conclusiones:73 | Definir VFP v4; razon por linea 2, 4 y 5 |
| I21 | media | jerga | conclusiones:75 | Quitar "endurecimiento productivo"; aclarar 85 incluye 3 |
| I22 | media | jerga | conclusiones:76 | Frase sin verbo; definir T4, CO-01, CO-02 |
| I23 | baja | ia | conclusiones:77 | Contraste "limite de cobertura"; definir plan lector |
| I24 | baja | hilo | conclusiones:78 | Razon de la linea de calibracion |
| J1 | media | ia | abstract_resumen:7 | Ingles: "encompassing" -> metodo por OE con ISO 25010 |
| J2 | baja | jerga | abstract_resumen:7 | Glosar Pareto front y prompt injection |
| J3 | media | ia | abstract_resumen:23 | "hibrida contenedora" -> metodo por OE |
| J4 | baja | conector | abstract_resumen:20 | Conector y glosa catalogo canonico |
| J5 | baja | jerga | abstract_resumen:25 | Glosar Pareto, hipervolumen, inyeccion |
| J6 | baja | jerga | abstract_resumen:28 | Glosar SUS y RTLX |

## 5. Balance de páginas

Hoy el cuerpo es 59 de 60. Las definiciones en primer uso suman entre +3 y +4 páginas en total (una por capítulo en promedio); la tabla del top 10 muestra solo las de mayor efecto. Los recortes de repeticion.md ahorran cerca de una página, así que el neto es +2 a +3 sin más cortes y excede el límite.
Recortes que compensan (en orden):
1. conclusiones:28-29 y 66 repiten oe5.tex (6 líneas).
2. Seis frente a siete desplegables, explicado 4 veces: dejar el porqué en Diseño y el cómo en Desarrollo (7 líneas).
3. Contribución y punto de equilibrio duplicados entre descripcionGeneral:98-106 y conclusiones:30 (5 líneas).
4. Corpus de 3.608 renglones en conclusiones:20-21 y 58 (4 líneas).
5. Párrafo duplicado de contextoProyecto:90-98 (T3, ya contado).
6. Tabla de ADR (disenoSolucion:220) y anexos si sigue arriba de 60: mover tablas de cobertura al anexo.
Regla: definir en una sola frase, en el primer uso, y remitir después; así las definiciones cuestan menos de lo estimado. Compilar tras cada capítulo para medir el cuerpo real.
