# Mapa de la memoria contra la rúbrica (2026-11-06)

Evidencia en `sections/` (archivo:línea). Estado: Cubierto / Parcial / Brecha.

## 1. Expresión escrita
- Evidencia: apertura con orden de capítulos y fases (introduccion.tex:61-69); conectores y definición en contexto en toda la introducción (introduccion.tex:4-59); resumen y abstract (covers/abstract_resumen.tex:7, 18-30); amenazas con definiciones inline (resultados.tex:251-277).
- Brechas: (a) abstract en inglés con vocabulario inflado ("utilizing", "comprehensive", línea 7); (b) cierres de capítulo que hablan del documento (resultados.tex:279-280; introduccion.tex:69 "Los anexos solo guardan material..." es neutro). (c) Párrafos de conclusiones con listas largas de cifras en una sola frase (conclusiones.tex:29). Estado: Cubierto, con ajustes menores.

## 2. Análisis de entorno y herramientas (referencias, trabajos encontrados, fortalezas vs. debilidades)
- Evidencia: conceptos de base con lo que Tukit toma de cada uno (contextoProyecto.tex:43); plataformas internacionales (contextoProyecto.tex:74); soluciones en Colombia (contextoProyecto.tex:111); alternativas consideradas (contextoProyecto.tex:121); tabla comparativa (contextoProyecto.tex:158); antecedentes ampliados (anexo_antecedentes.tex, 16 citas).
- Brechas: (a) casi no hay trabajos académicos comparables (bundles multiobjetivo, product matching, extracción con MLLM), ver benchmark-maestria.md R1-R5; (b) fortalezas frente a debilidades del estado del arte no aparecen como dos columnas explícitas; la tabla compara Tukit, no resume qué falla en cada trabajo. Cerrable sin datos nuevos (añadir columna "limitación" y 3-4 citas). Estado: Parcial.

## 3. Diseño con restricciones y requerimientos
- Evidencia: requerimientos derivados de la encuesta (analisisProblema.tex:75), priorizados (analisisProblema.tex:121-159); restricciones (analisisProblema.tex:182); especificación funcional (analisisProblema.tex:225); interesados y preocupaciones (disenoSolucion.tex:14); impulsores (disenoSolucion.tex:31); ATAM con tres alternativas (disenoSolucion.tex:60-93); escenarios con decisión, compromiso y prueba (disenoSolucion.tex:97-111); vistas C4/despliegue/proceso (disenoSolucion.tex:119-180); 49 ADR (disenoSolucion.tex:206-233).
- Brechas: ninguna relevante. Riesgo menor: trazabilidad restricción a decisión repartida entre analisisProblema.tex:182 y disenoSolucion.tex:97. Estado: Cubierto.

## 4. Prototipo funcional con pantallas y funcionalidades
- Evidencia: recorrido del acudiente (desarrolloSolucion.tex:331-353); tabla recorrido, pantalla, requisito, prueba y resultado (desarrolloSolucion.tex:377); pantallas del equipo (desarrolloSolucion.tex:408); asistente en lenguaje natural (desarrolloSolucion.tex:420); pipeline y optimizador (desarrolloSolucion.tex:17-318).
- Brechas: pago simulado declarado (introduccion.tex:27); cambios de la prueba con usuarios no implementados (conclusiones.tex:72, T4 y panel de colegio). Estado: Cubierto, con límites declarados.

## 5. Control de calidad: protocolo y escenarios de prueba
- Evidencia: plan de diez fases y cinco familias de escenarios, ordenado por ISO/IEC 25010 (calidad.tex:2-12); tabla de evidencia por característica (calidad.tex:52-61); 2.542 pruebas (resultados.tex:29); escenarios ATAM medidos, p. ej. ESC-D4 p95 0,31 s frente a 8 s (conclusiones.tex:53); protocolo de usuarios preregistrado con criterios C1-C3 (oe5.tex:14); 85 hallazgos vigentes del control de calidad (conclusiones.tex:72).
- Brechas: usabilidad marcada "Parcial" en la propia tabla (calidad.tex:61); T8 exploratoria posterior al preregistro (resultados.tex:257). Estado: Cubierto, con parciales honestos.

## 6. Análisis y conclusiones (impacto disciplina/social/tecnológico/económico, cumplimiento, resultados)
- Evidencia: impacto en ingeniería de sistemas (conclusiones.tex:7); contextos global, económico, ambiental y social (conclusiones.tex:15-34); tabla de cumplimiento por OE con "Cumplido" (conclusiones.tex:43-53); párrafo por objetivo (conclusiones.tex:58-66); trabajo futuro (conclusiones.tex:70-79); resumen de resultados por objetivo (resultados.tex:19-29); amenazas (resultados.tex:246).
- Brechas: (a) impacto ambiental y tecnológico se mencionan poco frente al social/económico; verificar que el párrafo de 15-34 diga algo concreto sobre ambiental (si no, una frase o declarar que no aplica y por qué); (b) el efecto económico se declara como hipótesis (comisión supuesta del 15 %, conclusiones.tex:30-34). Cerrable sin datos nuevos por redacción. Estado: Cubierto, con ajustes de redacción.

## Resumen
| Criterio | Estado |
|---|---|
| 1 Expresión escrita | Cubierto (ajustes menores) |
| 2 Entorno y herramientas | Parcial |
| 3 Diseño | Cubierto |
| 4 Prototipo | Cubierto |
| 5 Control de calidad | Cubierto |
| 6 Análisis y conclusiones | Cubierto (ajustes) |

Nota: algunas líneas citadas (p. ej. conclusiones.tex:30-34, 72; resultados.tex:253, 257, 267, 271, 275-280) son aproximadas por el recorte de columnas al leer; confirmar antes de editar.
