# Anexo T.3. Plan de análisis de la validación (OE5)

Se fecha y se confirma (commit) antes de recolectar datos. Después de la primera sesión no se cambian umbrales ni pruebas. Todo cambio posterior se anota como desviación, con fecha y motivo.

## 1. Lugar en la metodología
OE5 es la fase F5 de la Metodología Híbrida Contenedora (SCRUM + RUP + CRISP-DM) y corresponde a la fase *Evaluation* de CRISP-DM y a la Transición de RUP. El objetivo general es medir el efecto del recomendador sobre la carga cognitiva, la usabilidad y la satisfacción de acudientes del sector Salitre frente al proceso tradicional (Marco Metodológico v3, F5; ISO/IEC 25010; Ley 1581 de 2012).

## 2. Diseño y muestra
- **Etapa A, formativa:** 3 rondas de 5 acudientes (15) con pensamiento en voz alta; se corrige entre rondas. Sin inferencia estadística; se reportan problemas y severidad. Justificación del 5 por ronda en `\citep{nielsen_estimating_1994}`; el valor p = 0,31 por problema `[VERIF]` contra la fuente primaria.
- **Etapa B, sumativa pareada:** 30 analizables (se reclutan 36, ≈ 15 % de pérdida). Cada participante compara el NASA-TLX retrospectivo de su compra tradicional con el NASA-TLX de Tukit. Muestreo por conveniencia con cuotas (nivel escolar, gasto anual), solo del colegio piloto: no se generaliza más allá. Los 15 de A no cuentan en B.
- Con 30 pares, α = 0,05 bilateral y potencia 0,80, se detecta un efecto pareado de dz ≈ 0,52; un efecto menor no es detectable y se declara.
- Subgrupo de control de 12 para la tarea en línea (Anexo T.2 §8).

## 3. Variables
| Variable | Instrumento | Tipo | Momento |
|---|---|---|---|
| Usabilidad | SUS (0-100) | Continua | Tras las tareas |
| Carga de trabajo | NASA-TLX raw (0-100), tradicional y Tukit | Continua pareada | Previas y tras tareas |
| Satisfacción / recomendación | NPS (0-10) | Ordinal / categórica | Tras las tareas |
| Éxito de tarea | S/A/F por tarea | Binaria (sin ayuda = éxito) | Durante |
| Tiempo en tarea y lista → kit elegido | Cronómetro (T1 inicio a T4 elección) | Continua | Durante |
| Facilidad percibida | SEQ 1-7 por tarea | Ordinal | Tras cada tarea |
| Problemas de usabilidad | Códigos E1-E7, severidad 0-4 | Conteo / ordinal | Durante |
| Pensamiento en voz alta | Transcripción despersonalizada | Cualitativa | Durante |
| Covariables | Nivel escolar, dispositivo, frecuencia de compra en línea | Categóricas | Previas |

## 4. Hipótesis, umbrales y decisión
Las tres primeras son las confirmatorias. Cada una es un criterio que debe cumplirse por separado, así que no se ajusta α entre ellas (se declara que el éxito de OE5 exige las tres).
| ID | Hipótesis (H0 entre paréntesis) | Prueba | Criterio de éxito |
|---|---|---|---|
| C1 | SUS medio mayor que 68 (μ ≤ 68) | t de una muestra; Wilcoxon si Shapiro-Wilk rechaza normalidad | Media ≥ 68 y límite inferior del IC95 % > 68 (regla estricta `[PROP]`) |
| C2 | La carga con Tukit es menor que con la compra tradicional (diferencia media = 0) | t pareada o Wilcoxon de rangos con signo | IC95 % de la diferencia excluye 0, dirección Tukit < tradicional, dz ≥ 0,5 |
| C3 | Éxito sin ayuda ≥ 80 % en las tareas críticas T1, T4, T6 | Proporción con IC de Wilson | Estimación ≥ 80 % por tarea crítica; se reporta el IC aunque sea amplio |
| S1 | NPS positivo | Bootstrap (10.000 remuestreos) | NPS > 0; reportar IC |
| S2 | Mediana lista → kit elegido ≤ 20 min | Descriptivo, mediana e IQR | ≤ 20 min con lista completa `[PROP]` |
| S3 | Diferencias de TLX por escala, y SEQ por tarea | Wilcoxon pareada, Holm | Exploratorio |
| S4 | Con la tarea de control, tiempo Tukit < tiempo de control | Wilcoxon pareada (n = 12) | Exploratorio; potencia baja |
Normalidad: Shapiro-Wilk sobre las diferencias pareadas (C2) y sobre los puntajes SUS (C1). El criterio se decide antes de ver los datos: normal, t; si no, Wilcoxon. Tamaño del efecto: dz con t, Hodges-Lehmann con Wilcoxon. El SUS tiene DE esperada ≈ 12,5 `[VERIF]` (Sauro y Lewis, fuera del .bib); con 30, el IC95 % de la media ronda ±4,7.
Correspondencia con las hipótesis del trabajo (`GUIONES_ENTREVISTA` §0.5) `[VERIF]` ids: C2 aporta a H1 (costo del proceso, no el cambio de canal); S1-S3 al objetivo de satisfacción; H8 (elección Fan) solo se observa en T4 como descripción de elecciones. Las hipótesis sobre pago, descuento y comisión (H2, H3, H5, H6) no se miden en esta versión del instrumental; quedan para la etapa C si se decide mantenerla.

## 5. Análisis cualitativo
Transcripción despersonalizada. Dos codificadores independientes (moderador y observador distintos del que construyó la pantalla) con plantilla de problemas (E1-E7) y de motivos. Acuerdo con κ de Cohen, meta κ ≥ 0,6; desacuerdos por consenso. En la etapa A se revisa saturación temática. La severidad se asigna por consenso; se cuentan problemas por severidad y por pantalla.

## 6. Datos faltantes y exclusiones
Sesión completa es la que llega a T7 y a los cuestionarios. Una tarea con falla del sistema (E6) se repite; si no se puede repetir, es dato faltante de esa tarea y no cuenta como fallida. Sin imputación. Se reporta la tabla de participantes reclutados, completados y excluidos, con el motivo. Si hay menos de 24 pares de TLX completos, C2 se reporta como no concluyente.

## 7. Cómo retroalimenta el desarrollo
| Resultado | Qué pasa |
|---|---|
| Problema severidad 3-4 en la etapa A | Entra al *backlog* con prioridad máxima del siguiente *sprint*; se corrige antes de la siguiente ronda |
| Cada ronda de A | Cuenta como revisión de *sprint*: demo con el hallazgo, lista de cambios y acta corta |
| Problemas de severidad 2 | Al *backlog* ordenado por frecuencia |
| Cero problemas de severidad 4 abiertos | Parte de la definición de "hecho" de la versión que entra a B |
| C1-C3 cumplidos | CRISP-DM *Evaluation*: pasa a *Deployment* (piloto y despliegue) |
| C1 o C3 no cumplidos | Vuelve a *Business Understanding* / *Data Understanding* si el fallo es de contenido (cobertura, ambigüedad de variantes) o a *Modeling* si es de la recomendación; si es de interfaz, a un *sprint* de rediseño |
| C2 no cumplido | Se reporta como hallazgo negativo con el mismo peso; se revisa si el recomendador mejoró la carga o si cambió el canal |
Todo resultado, incluyendo refutaciones, se reporta con el mismo peso. Los cambios a la lista de requisitos pasan por el registro de decisiones de arquitectura (ADR) cuando afecten la arquitectura.

## 8. Cuaderno reproducible
Entrada: tablas con ACU-xx, SUS ítem a ítem, TLX por escala, SEQ, resultados y tiempos por tarea. Pasos: cálculo del SUS, Shapiro-Wilk, prueba elegida, IC95 % y tamaños de efecto, Wilson, bootstrap del NPS, tablas de problemas. Se prueba con datos sintéticos antes de la primera sesión (paquete F5-13.2). Salida: tablas y figuras para el reporte.

---
Notas para revisión (borrar al pegar): (1) **El cuaderno no existe en el repositorio** (busqué `*.ipynb` y las pruebas de normalidad solo aparecen en documentos); el párrafo de `resultados.tex` dice que "está preparado". Hay que construirlo (§8) o cambiar la frase. (2) El plan 03 define umbrales y la regla estricta del IC como `[PROP]`: el equipo debe aceptarlos. (3) La correspondencia con H1-H11 es parcial a propósito: el instrumental revisado no incluye precio ni reserva real.
