# Auditoría de repetición entre capítulos (memoria Tukit)

Base: `docs/memoria/sections/*.tex` (introduccion, descripcionGeneral, contextoProyecto, analisisProblema, disenoSolucion, desarrolloSolucion, optimizacion, resultados, calidad, oe5, conclusiones, covers/abstract_resumen). Líneas de la versión del 6-nov-2026. Leyenda: E = se explica (método, definición o tabla), N = solo se nombra.
Nota: las cifras con macros (`\calTauPares`, `\calPruebaElegidaHV`) se cuentan por el macro, no por el valor.

## 1. Matriz

| Cifra / afirmación | Apariciones (archivo:línea) | Dónde se explica | Veredicto |
|---|---|---|---|
| 3.608 ítems / 1.451 formas / 17 colegios | analisisProblema:269 (E, origen) ; conclusiones:20-21 (E repetido, en impacto social), :49 (tabla, N), :58 (E repetido) ; descripcionGeneral:300 (N) ; desarrolloSolucion:63, 87, 109 (N, "17 colegios") ; resultados:172 (N) | analisisProblema:269 | Conclusiones lo explica 3 veces. Dejar 1 mención en la tabla y 1 en el párrafo OE1. |
| N=65 / n=60 encuesta | analisisProblema:76 (E) ; descripcionGeneral:299 (N) ; conclusiones:18 (E repetido), :49, :58 (N) | analisisProblema:76 | Quitar de conclusiones:18 el desglose N/n y los porcentajes ya dados en el capítulo IV (65 %, 68,3 %), o dejarlos solo allí. |
| SUS 90 [82-98] | oe5:60, 80 (E, tabla con IC) ; resultados:29 (N) ; calidad:61 (N) ; conclusiones:29 y :66 (N, duplicado en 2 sitios) ; abstract:7 (N) | oe5:60-83 | Conclusiones lo cita dos veces (:29 y :66). Dejar una. |
| RTLX 63 -> 9 | oe5:62, 81-83 (E, con d_z 1,83 y IC 23-85) ; conclusiones:29 (N) ; abstract:7 (N) | oe5 | Aceptable. En conclusiones:29 quitar "(n = 6)" y el IC. |
| 6 de 6 pagaron / seis sesiones | oe5 ; resultados:29 ; conclusiones:28-29 (E: "cuatro de seis...fácil, intuitiva", "solo uno de cinco") y :66 ; abstract:7 | oe5 | Conclusiones:28-29 reescribe los resultados cualitativos de oe5; condensar a una frase. |
| 0,9969 hipervolumen / 40 listas / 32 NSGA-II | resultados:28, 175 (E) ; desarrolloSolucion:89, 110 (E, partición) ; conclusiones:52 (tabla), :64 (párrafo) ; abstract:25-26 | resultados:175 (resultado), desarrolloSolucion:89 (método) | Conclusiones lo da en tabla y en párrafo (2x). Dejar solo el párrafo. |
| F1 0,948 vs 0,298 | resultados:26, 50, 63, 67, 74 (E) ; conclusiones:51 (tabla), :62 (párrafo) ; abstract:25 (solo 0,948) | resultados:50-74 | Conclusiones repite 0,948 en tabla y párrafo; el 0,298 solo en el párrafo. Dejar el párrafo. |
| tau = 0,75 | descripcionGeneral:312 (N) ; resultados:27, 119-122 (E) ; optimizacion:212-218, 237-239 (E, no recalibrado) | resultados:119 (def.) y optimizacion:212 (decisión) | Dos explicaciones: resultados define y optimizacion argumenta; correcto, pero optimizacion:212 y :237-239 dicen dos veces "no se recalibró". |
| 405 pares / 391 de 405 | resultados:97, 140, 268 ; conclusiones:66 ; optimizacion:237 (macro) | resultados:97 | "391 de los 405" aparece en resultados:268 y conclusiones:66 sin cambio. Una vez en resultados (límites) y en conclusiones solo "un solo colegio". |
| 41 / 512 kits, $29.353 | descripcionGeneral:102-104 (E, con desglose de costos) ; conclusiones:30 (E repetido, mismo desglose) | descripcionGeneral:98-106 | Duplicado casi literal. Conclusiones: una frase. |
| 85 hallazgos | calidad:34 (E) ; conclusiones:75 (N) | calidad:34 | OK. |
| 49 ADR | conclusiones:50 (N, tabla) ; (definidos en disenoSolucion) | disenoSolucion | OK. |
| Seis desplegables (vs. siete previstos) | introduccion:46 (E) ; analisisProblema:213 (E) ; disenoSolucion:48 (E, sección entera) ; desarrolloSolucion:45 (E) ; calidad:15 (N) ; conclusiones:60 (E) | disenoSolucion:48-60 | Se explica 4 veces (intro, analisis, diseno, desarrollo). Dejar diseno (porqué) y desarrollo (cómo); en intro y análisis, una frase. |
| ATAM 3,91 (vs 3,44 y 2,82) | disenoSolucion:84 (tabla) ; conclusiones:9 | disenoSolucion | OK (conclusiones:9 nombra). |
| 81 ataques / 58 de 70 | desarrolloSolucion:427 (E) ; calidad:63 (N) ; conclusiones:51 (N) ; abstract:25 (N) | desarrolloSolucion:427 | OK. |

## 2. Repeticiones y reducciones propuestas

**R1. Contribución por kit y punto de equilibrio (conclusiones:30 repite descripcionGeneral:98-106).** Conservar en descripcionGeneral. Reducir en conclusiones:

```latex
Con una comisión supuesta del 15\,\%, cada kit deja una contribución de \$29.353 y el punto de equilibrio es de 41 kits con la infraestructura del piloto y de 512 con la escalable (Sección~\ref{sec:negocio}).
```
Ganancia: ~5 líneas. (Verificar la etiqueta de la sección antes de usar.)

**R2. Seis desplegables / siete previstos (intro:46, analisisProblema:213, disenoSolucion:48, desarrolloSolucion:45, conclusiones:60).** Conservar disenoSolucion:48-60 (justificación) y desarrolloSolucion:45 (ADR 0013). En intro y análisis:

```latex
El sistema construido tiene seis desplegables (Sección~\ref{sec:desplegables}).
```
Ganancia: ~6-8 líneas entre intro y analisisProblema.

**R3. Corpus 3.608 / 1.451 / 17 colegios en conclusiones (:20-21 y :58).** Conservar en analisisProblema:269. En :20-21:

```latex
Las listas, además, nombran de formas muy distintas los mismos artículos (Capítulo~\ref{cap:problema}), y cada hogar las interpreta por su cuenta.
```
En :58 quitar el paréntesis "(3.608 ítems y 1.451 formas de nombrar, de 17 colegios)" y la frase "El corpus final tiene 4.719 ítems, que son esos 3.608 más 1.109 libros...". Ganancia: ~4 líneas.

**R4. Encuesta N=65, n=60 y porcentajes (conclusiones:18-20 repite analisisProblema:76).** Conservar el cap. IV. En conclusiones:

```latex
La encuesta del primer objetivo específico (n=60) describe una compra costosa para los acudientes, con los resultados del Capítulo~\ref{cap:problema}.
```
Ganancia: ~3 líneas.

**R5. Resultados de las sesiones con acudientes en conclusiones:28-29 y :66 (repite oe5).** Conservar oe5:56-83. En :28-29 dejar:

```latex
En seis sesiones, los seis acudientes pagaron su kit, solo uno de cinco lo eligió sin ayuda, y la carga percibida bajó de 63 a 9 (Sección~\ref{sec:oe5}).
```
En :66 quitar el SUS (queda en el párrafo anterior). Ganancia: ~6 líneas.

**R6. Tabla de cumplimiento (conclusiones:49-52) y párrafos OE1-OE5 (:58-66) repiten las mismas cifras.** Las cifras de OE3 y OE4 (0,948; 0,9969; 40 listas; 32 NSGA-II) están dos veces cada una. Conservar la tabla con cifras y reducir los párrafos al porqué del "Cumplido":

```latex
En percepción, el modelo multimodal superó al reconocimiento con reglas (Tabla~\ref{tab:cumplimiento}), con la salvedad de que el oro se construyó desde su salida.
```
```latex
Su frente de Pareto quedó cerca del exacto (Tabla~\ref{tab:cumplimiento}).
```
Ganancia: ~4 líneas.

**R7. Abstract/resumen (:25-26) cita 0,948, 0,9969, 40, 32, 81, 90, 63->9.** Aceptable para un resumen, pero "(32 resueltas con NSGA-II)" y "pago simulado" son detalles de método; quitarlos. Ganancia: ~1 línea por idioma.

**R8. "No se recalibró τ" (optimizacion:212, :218 y :237-239).** Conservar :212-218 y reducir la viñeta :237-239:

```latex
\item \emph{$\tau$ evaluado con un solo revisor.} Los \calTauPares{} pares los marcó una persona, así que $\tau$ no se recalibró (Sección~\ref{sec:tau}).
```
Ganancia: ~2 líneas.

**R9. SUS en conclusiones (:29 y :66).** Dejar solo :66 como evidencia del OE5. Ganancia: 1 línea.

## 3. Párrafos casi duplicados entre capítulos
1. descripcionGeneral:98-106 y conclusiones:30: desglose de la contribución por kit (comisión, pasarela, IA, entrega, adquisición) casi literal.
2. analisisProblema:76 y conclusiones:18-20: resultados de la encuesta (65 %, 68,3 %, estrato 4).
3. conclusiones:28-29 y oe5: lectura de las sesiones.
4. conclusiones:62-64 y el cuerpo de resultados: cifras de F1 y hipervolumen.
5. disenoSolucion:48 y desarrolloSolucion:45: la razón de los seis desplegables (parcial, con ADR 0013).

## 4. Estimación total de líneas ganadas
R1 5 + R2 7 + R3 4 + R4 3 + R5 6 + R6 4 + R7 2 + R8 2 + R9 1 = ~34 líneas fuente (~1 página). Casi todo se concentra en conclusiones.tex, el capítulo más repetitivo.

Pendiente: mapear las etiquetas `\ref` reales antes de aplicar; no se verificó la compilación porque este informe no edita archivos.
