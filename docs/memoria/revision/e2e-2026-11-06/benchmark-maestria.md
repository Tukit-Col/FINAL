# Benchmark de nivel maestría (2026-11-06)

## Alcance y limitaciones del método
- WebSearch no funcionó en este entorno (error del proxy). Se usó la API de arXiv (export.arxiv.org) y las páginas abs de arXiv. De cada paper solo se leyó el resumen y metadatos de la página abs, no el PDF. Todo lo marcado "no consta" significa que la página abs no lo dice, no que el paper no lo tenga. Antes de citar alguno en la memoria hay que abrir el PDF.
- No se encontró una tesis de maestría que combine ATAM/C4/4+1 con SUS (cuatro consultas a arXiv sin resultados; los repositorios universitarios no se abrieron). Para la dimensión (d) se usan dos papers de sistema con SUS como referencia parcial. Queda pendiente buscar a mano en repositorios (p. ej. Javeriana, Uniandes, DiVA, TU Delft) una tesis real con ATAM + SUS.

## Referencias abiertas
| Id | Tema | Referencia | URL |
|---|---|---|---|
| R1 | (a) multiobjetivo NSGA-II en recomendación | Lotfian, Kabgani. HiMARS: Hybrid multi-objective algorithms for recommender systems | https://arxiv.org/abs/2604.07572 |
| R2 | (a) bundles multiobjetivo | Combinatorial Multi-Objective Multi-Armed Bandit Problem (COMO-MAB; menciona bundle recommendation) | https://arxiv.org/abs/1803.04039 |
| R3 | (b) product matching | Almagro et al. Block-SCL: Blocking Matters for Supervised Contrastive Learning in Product Matching | https://arxiv.org/abs/2207.02008 |
| R4 | (c) extracción de documentos con MLLM | Shen, Yuan, Ghosh, Mai, Dahlmeier. OCR or Not? Rethinking Document Information Extraction in the MLLMs Era | https://arxiv.org/abs/2603.02789 |
| R5 | (c) extracción de líneas de ítem | Cesista et al. Retrieval Augmented Structured Generation: Business Document Information Extraction As Tool Use | https://arxiv.org/abs/2405.20245 |
| R6 | (d) sistema + SUS | Kian et al. DART: A Deployable Architecture for Robot-Mediated Tasks | https://arxiv.org/abs/2609.12349 |
| R7 | (d) sistema + SUS | Srihari R et al. JobSphere: AI-Powered Multilingual Career Copilot | https://arxiv.org/abs/2511.08343 |

## Qué dice cada fuente (según su página abs)
- R1: compara NSGA-II, NNIA y AMOSA; métricas de exactitud, diversidad y novedad, más spacing, distancia ideal media y dispersión del frente. No consta hipervolumen, pruebas estadísticas, ablación ni código.
- R2: bandido combinatorio multiobjetivo con aplicación a bundles. Es teoría de aprendizaje en línea, sirve como cita del problema, no como línea base.
- R3: aprendizaje contrastivo supervisado con negativos duros del bloqueo; "estado del arte" en datasets públicos; limitaciones declaradas (solo títulos cortos, sin aumento de datos, backbone ligero). No constan umbral, IC ni ablación.
- R4: benchmark a gran escala de MLLM solo-imagen contra OCR+MLLM; análisis jerárquico de errores con LLM; el diseño del esquema y los ejemplos mejoran el resultado. Datos/código no constan.
- R5: propone la métrica GLIRM frente a ANLS*, DocILE y GriTS; hay ablación LLM con RASG frente a LMM. No constan IC, pruebas ni código.
- R6: arquitectura que combina robot, app web y nube; SUS 78,89 (n=103 en laboratorio) y 87,5 (n=4 en casa). No constan IC, línea base ni amenazas.
- R7: SUS 78,5, "50 % mejor" que la plataforma base PGRKAM; precisión@10 68 %, exactitud factual 94 %. No constan n, pruebas, IC ni limitaciones.

## Comparación por dimensión (Tukit vs. lo observado)
Evidencia de Tukit en archivo:línea dentro de `sections/`.

| Dimensión | Lo observado en las fuentes | Tukit | Veredicto |
|---|---|---|---|
| Trabajo relacionado comparativo | R1-R7 lo presentan en prosa o no consta en el abs | Tabla comparativa con soluciones existentes: contextoProyecto.tex:158; conceptos de base: contextoProyecto.tex:43 | Por encima de lo visible; pero el trabajo académico (papers de bundles, entity matching, extracción) se cita poco: ver brecha 1 |
| Líneas base | R5 y R7 comparan con base; R1 con otros MOEA | Reglas 0,298 vs. Gemini 0,948 (resultados.tex:26); enumeración exacta como referencia del frente (resultados.tex:163-200); punto de partida del optimizador con Wilcoxon (optimizacion.tex:206-207) | A la altura |
| IC y pruebas estadísticas | Ninguna de las páginas abs las menciona | Bootstrap 95 % (optimizacion.tex:186; resultados.tex:135), kappa con IC (resultados.tex:112), Wilcoxon (optimizacion.tex:207), t para SUS (oe5.tex:73) | Por encima |
| Ablación | R5 tiene ablación; R3 no consta | Estrategias de recuperación por fase (desarrolloSolucion.tex:55); comparación léxico/semántico/híbrido y MTEB (desarrolloSolucion.tex:160); sensibilidad de pesos (optimizacion.tex:219) | A la altura; por debajo solo en percepción (una corrida por motor, resultados.tex:271) |
| Amenazas a la validez | R3 declara limitaciones; el resto no consta | Sección completa con los 4 tipos de Wohlin (resultados.tex:246-278) y amenazas del optimizador (optimizacion.tex:230) | Por encima |
| Reproducibilidad | R4/R5/R6/R7: no consta en abs | Semilla y umbral de enumeración (optimizacion.tex:88), cifras desde archivos de la corrida (optimizacion.tex:10), commit evaluado (conclusiones.tex:51), anexos de reproducción (introduccion.tex:69) | Por encima |
| Arquitectura | R6 solo la describe | ATAM de 3 alternativas, 17 escenarios, 4+1, C4 y 49 ADR (disenoSolucion.tex:60-236; conclusiones.tex:50) | Por encima |
| Evaluación con usuarios | R6 n=103 y n=4; R7 n sin constar | n=6, SUS 90 [82-98], RTLX, NPS, tareas con IC (oe5.tex:41-80) | Por debajo en tamaño de muestra (n=6 contra 103 de R6); a la altura en rigor. No se cierra sin datos nuevos; ya se declara como indicativo (resultados.tex:275-277) |
| Percepción documental | R4 evalúa a gran escala con análisis de errores | F1 micro 0,948 sobre 10 documentos, oro corregido desde uno de los motores (resultados.tex:56, 267-268) | Por debajo: 10 documentos y oro sesgado. Cerrar sin datos nuevos: parcial (análisis de errores por categoría con las salidas ya guardadas; reportar IC bootstrap por renglón sobre los mismos 10 documentos) |
| Frente de Pareto | R1 usa métricas de calidad del frente | Hipervolumen 0,9969 del exacto, 40 listas, 32 con NSGA-II (resumen) | A la altura o por encima; falta spacing/otro indicador (opcional, calculable sin datos nuevos) |

## Brechas concretas y si se cierran sin datos nuevos
1. Estado del arte académico delgado. Las referencias de producto (TeacherLists) y de método (Deb, Lewis) están, pero no hay trabajos comparables de bundles multiobjetivo, entity matching de productos ni extracción con MLLM. Se cierra sin datos nuevos: añadir 3-4 citas (R1, R3, R4/R5 tras leer el PDF) y una frase por trabajo en contextoProyecto.tex junto a la Tabla de la línea 158.
2. Tabla comparativa académica: solo hay una de soluciones comerciales. Se cierra sin datos nuevos con una columna extra o tabla corta "trabajos académicos: qué hacen, qué toma Tukit".
3. Percepción con n=10 y oro sesgado (resultados.tex:267). No se cierra del todo sin datos nuevos; se mitiga con IC bootstrap y análisis de errores sobre salidas existentes.
4. Usabilidad con n=6. No se cierra sin datos nuevos; la memoria ya lo dice con claridad y cierra el caso (OE5 aceptado como ronda única).
5. Un solo anotador. No se cierra sin datos nuevos; declarado en resultados.tex:253-254.
6. Falta una tesis de maestría real como referencia de formato (ver limitaciones arriba).

## Hallazgos de escritura (observación, no se editó nada)
- No se corrió el cazador de marcas de IA sobre el texto; esta tarea fue comparación y rúbrica. Lectura de muestra: introduccion.tex y el resumen cumplen el estilo (contexto primero, conectores). Una frase de cierre del capítulo de resultados ("Con esto el sistema queda evaluado... el capítulo siguiente recoge...", resultados.tex:279-280) habla del documento más que del tema, de bajo impacto.
- El abstract en inglés (covers/abstract_resumen.tex:7) tiene "utilizing", "comprehensive" y "extensive and ambiguous"; el resumen en español usa "Posteriormente" (línea 21). Menores.
