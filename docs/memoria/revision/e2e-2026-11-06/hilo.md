# Auditoría de hilo conductor (2026-11-06)

Rutas relativas a `docs/memoria/sections/`. Líneas aproximadas (inicio del párrafo o fila citada).

## 1. Cadena problema -> conclusiones

Se sigue sin saltos mayores. Cada capítulo abre mirando al anterior y casi todos cierran hacia el siguiente:
II abre (descripcionGeneral:4-8) con el hallazgo de la introducción; III abre (contextoProyecto:4); IV abre (analisisProblema:4); V abre (disenoSolucion:4) y cierra "el siguiente capítulo" (disenoSolucion:236); VI abre (desarrolloSolucion:4) y cierra hacia resultados (desarrolloSolucion:430); VII abre (resultados:4) y cierra hacia VIII (resultados:280); IV cierra hacia V (analisisProblema:276); III cierra hacia IV (contextoProyecto:197).
Fallos: II no cierra hacia III con una frase propia (solo una oración suelta en descripcionGeneral:344, después de la lista de ciclos); VIII no abre con párrafo de capítulo (conclusiones:3-9 salta a una subsubsección).

## 2. Trazabilidad por OE

| OE | Objetivo (literal) | Método nombrado (inicio de bloque) | Dónde se construye | Dónde se mide | Conclusión |
|---|---|---|---|---|---|
| OE1 | descripcionGeneral:125 | Design Thinking + IEEE 830: introduccion:54, descripcionGeneral:173, contextoProyecto:4-7, analisisProblema:4-8 | Cap. III y IV: contextoProyecto:12,71; analisisProblema:14,182,225 | No hay subsección de resultados; el criterio es el SRS y el corpus (analisisProblema:276; tab:metricas lo omite, resultados:21-32) | conclusiones:49 (tabla), :58 |
| OE2 | descripcionGeneral:130 | RUP + IEEE 1016 + ATAM: descripcionGeneral:175-176, disenoSolucion:4-5 (abre con el método) | disenoSolucion:7,48,60,119,160,182,206 | ATAM en disenoSolucion:60; prueba de tiempo ESC-D4 en resultados:166 y calidad.tex:59; tab:metricas lo omite | conclusiones:50, :60 |
| OE3 | descripcionGeneral:135 | SCRUM + CRISP-DM: descripcionGeneral:176, desarrolloSolucion:5-10 | desarrolloSolucion:17 (pipeline), 77, 116, 145; NL2C en desarrolloSolucion:420 y nl2c.tex:1 (anexo) | resultados:35 (percepción), :82 (recuperación), :229 (NL2C) | conclusiones:51, :62 |
| OE4 | descripcionGeneral:142 | SCRUM + CRISP-DM: igual que OE3; optimizacion.tex:4-8 lo repite como "Modeling" | desarrolloSolucion:281, optimizacion.tex:1, desarrolloSolucion:319 (web y pago) | resultados:163 (HV, p95); el pago solo en simulado (desarrolloSolucion:414-417) | conclusiones:52, :64 |
| OE5 | descripcionGeneral:149 | ISO 25010 + protocolo preregistrado: descripcionGeneral:177, resultados:6-9, calidad.tex:3-8, oe5.tex:3-6 | no se construye (evalúa lo de OE3/OE4) | calidad.tex:3 y oe5.tex:1 (vía `\input` en resultados:242-243) | conclusiones:53, :66 |

Ruptura de trazabilidad: OE1 y OE2 no aparecen en `tab:metricas` (resultados:21-32) ni se dice por qué.

## 3. Puentes faltantes y orden (con frase propuesta)

1. **Intro: tres etapas vs cuatro.** introduccion:28 dice "tres etapas" (percepción, normalización, optimización); desarrolloSolucion:19-24 dice "cuatro etapas" (agrega resolución). Además, el asistente en lenguaje natural (NL2C, OE3 en el objetivo) no aparece en la introducción pero sí en el resumen y en VI. Frase tras introduccion:41:
   `A esas tres etapas se suma un asistente que traduce una frase del acudiente, por ejemplo «Minnie para mi hija, máximo 500 mil», en filtros para el optimizador (NL2C, de \emph{natural language to constraints}); el Capítulo~VI lo describe y el anexo lo evalúa.\par`
   Y en desarrolloSolucion:19: aclarar `la normalización, en sentido amplio, incluye la resolución` o igualar en la introducción a cuatro.
2. **Intro: mapa de capítulos incompleto.** introduccion:67 asigna el VII solo a la Fase 5, pero resultados:4-14 evalúa también OE3 y OE4. Reemplazar por:
   `El VII reúne la evaluación: mide las etapas de datos del OE3 y del OE4 con CRISP-DM y después el sistema integrado y el uso por acudientes (OE5) con ISO/IEC~25010 y el protocolo preregistrado.`
3. **II no cierra hacia III** (descripcionGeneral:344). Añadir al final de la última subsubsección:
   `Con los objetivos y los métodos fijados, el Capítulo~III reúne los conceptos y las soluciones existentes sobre los que se construyó el OE1.\par`
4. **VIII sin apertura** (conclusiones:3-9). Antes de `\subsection{Análisis de Impacto}` o al inicio de él:
   `Este capítulo cierra el documento en dos partes. Primero describe el impacto del trabajo en la ingeniería de sistemas y en las familias; después contrasta cada objetivo específico con su evidencia (Tabla~\ref{tab:cumplimiento}) y propone el trabajo futuro.\par`
   conclusiones:9 repite "Este capítulo" dos veces seguidas; fusionar.
5. **OE1 y OE2 fuera de la tabla de resultados** (resultados:21-32). Tras la Tabla~\ref{tab:metricas} (resultados:34):
   `El OE1 y el OE2 no figuran en la tabla porque se evaluaron en su propio capítulo: el OE1 con el SRS y su trazabilidad (Capítulo~IV) y el OE2 con la comparación ATAM (Sección~\ref{sec:alternativas}); del OE2 solo se mide aquí el escenario de tiempo ESC-D4.`
6. **Orden dentro de VI (principal reordenamiento).** `\input{sections/optimizacion}` está en desarrolloSolucion:418, después de "Prototipo funcional: aplicación web y pago" (:319) y antes del asistente (:420). Resultado: la subsección "Optimización y calibración" queda detrás de la interfaz que la consume y la apertura de "Prototipo" (:321 "Con el mecanismo construido") se contradice. Además la apertura del capítulo (desarrolloSolucion:11-13) dice "la Sección optimizacion-dev y la siguiente", que hoy es la web. Orden propuesto: pipeline (17) -> datos (77) -> percepción (116) -> normalización y resolución (145) -> optimización del kit (281) -> **optimización y calibración (mover el `\input` a antes de :319)** -> asistente NL2C (420) -> **prototipo web y pago al final** (cierra el recorrido y justifica "Con ello el desarrollo queda completo", :429). Ajustar el final de NL2C (:429) a: `Con el asistente, el mecanismo queda completo; falta la pieza que el acudiente ve.` y la apertura de web (:321) a `Con el mecanismo y el asistente construidos, queda la pieza que el acudiente ve...`.
7. **Orden dentro de VII.** Percepción -> Recuperación -> Optimización -> Asistente -> Verificación del sistema (calidad) -> Evaluación con usuarios -> Amenazas es lógico (de componente a sistema a usuario a límites). Dos arreglos: (a) `\input{calidad}` y `\input{oe5}` (resultados:242-243) hacen que las dos subsecciones no tengan puente propio con la anterior; añadir antes de :242: `Hasta aquí se midió cada componente por separado; las dos subsecciones siguientes miden el sistema ya integrado (OE5), primero con pruebas y después con usuarios.\par`. (b) El Asistente NL2C (resultados:229) está en OE3 por el objetivo pero aparece después de Optimización (OE4) y no está en `tab:metricas`: agregar una fila `OE3, asistente` o aclarar con `El asistente (NL2C) se evalúa aquí porque su salida alimenta al optimizador.`
8. **Inconsistencia de ubicación de NL2C.** descripcionGeneral:140 lo pone en OE3; la tabla CRISP (descripcionGeneral:322) lo pone en OE4 (Modelado) y conclusiones:51 en OE3. Unificar en OE3 (literal de la VFP v4) y corregir la fila de :322.
9. **Siete / catorce / seis servicios.** disenoSolucion:48 ("catorce a seis"), introduccion:46-47 (séptimo servicio previsto), conclusiones:50 ("siete desplegables; se construyeron seis"). Las cifras no se tocan; añadir en disenoSolucion:50: `Los catorce servicios documentados originalmente se redujeron a siete en el diseño y, al construir, el séptimo (ingesta) se reemplazó por un catálogo curado, de ahí los seis desplegables.` (verificar que esa secuencia es la correcta antes de aplicar).
10. **Términos usados antes de definirse.**
    - ESC-D4: descripcionGeneral:89 -> primera definición en disenoSolucion:105. Frase: `ESC-D4, el escenario de rendimiento del árbol de utilidad ATAM (Sección~\ref{sec:alternativas}),`.
    - CGS-10 y 1.293 ítems: descripcionGeneral:303 -> definido en desarrolloSolucion:86. Añadir `(el conjunto de oro de percepción, definido en la Sección~\ref{sec:datos-sistema})`.
    - Hipervolumen en el resumen y en tab:metricas (resultados:28) sin definición previa; la definición está en resultados:167. Una frase en introduccion:40: `la calidad del frente se mide con el hipervolumen, la fracción del espacio de objetivos que los kits cubren`.
    - SUS, RTLX, NPS: usados en resumen y resultados:29 sin expandir; definidos en oe5.tex:14. Expandir en la primera aparición de resultados (`SUS, escala de usabilidad del sistema`).
    - τ (resultados:26) aparece antes de su definición en desarrolloSolucion:196; la tabla de resultados debe decir `umbral de certeza $\tau$`.
11. **Resumen.** Coherente con conclusiones (cifras iguales). Falta decir en una frase el estado de cumplimiento y el límite principal (un solo colegio, n=6, pago simulado); el último ya aparece parcialmente. Propuesta final del resumen: `Los cinco objetivos específicos se cumplieron con esos límites: un solo colegio, seis participantes y pago simulado.`

## 4. Lo que está bien

El método aparece al inicio de cada bloque de resultados (resultados:37-39, :84, :166, :231; calidad.tex:3-8; oe5.tex:3-6) con el esquema pregunta-método-métrica. La tabla de fases (descripcionGeneral:248) y la de cumplimiento (conclusiones:44-55) cierran el ciclo objetivo -> evidencia -> sección.
