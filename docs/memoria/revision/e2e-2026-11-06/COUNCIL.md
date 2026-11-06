# Council final: memoria TUKIT (6 de noviembre de 2026)

Cinco jurados (académico, software, editor, lego, escéptico) leyeron el cuerpo completo (pp. 1-60) y se criticaron entre sí de forma anónima. Un hallazgo "sobrevive" si al menos dos jurados lo dieron por válido en la cruzada y la mayoría no lo calificó de falso. Verifiqué las citas contra `council/cuerpo.txt`. No se editó ningún archivo de la memoria.

## 1. Nota consolidada por criterio (escala 0 a 5)

| Criterio | Media | Rango | Razón |
|---|---|---|---|
| Expresión escrita | 4,1 | 3,8 a 4,3 | Capítulos con puente y cierre, términos definidos en línea. Restan las referencias que quedaron rotas al recortar contenido (amenazas, "Sección VII.1", ADR, RNF de la Tabla 9), la densidad de siglas internas (ESC-D4, DP-03, CGS-10, Faro) y párrafos con demasiadas cifras. El escéptico es el más severo. |
| Entorno y herramientas | 3,9 | 3,6 a 4,2 | La Tabla 5 (6 plataformas por 13 criterios, con n/c y criterios donde Tukit pierde) es honesta. Falta densidad académica comparada con cifras y la línea base de un LLM de propósito general leída con la lista. "Única de las siete" descansa en sitios públicos consultados en noviembre. |
| Diseño | 4,3 | 4,0 a 4,5 | Lo más fuerte: ATAM de tres alternativas, sensibilidad de pesos (20 combinaciones, B' siempre gana), impulsores explícitos, 49 ADR, funciones de aptitud. Reservas: los puntajes los asignó el equipo y la sensibilidad no los perturba; la cita legal del impulsor de cumplimiento es más fuerte de lo que la norma dice. |
| Prototipo funcional | 4,1 | 3,8 a 4,4 | Recorrido lista a pedido pagado con dos aplicaciones y seis servicios. Resta que el pago es simulado y se aprueba solo, Wompi nunca se ejecutó (y p.17 dice lo contrario), el asistente no lo usó ningún acudiente y hay 16 hallazgos altos abiertos. |
| Control de calidad | 4,1 | 3,8 a 4,5 | 2.542 pruebas, cuatro niveles, preregistro, xfail estricto, auditoría de 152 puntos, estado ISO por característica. Restan 1 de 8 características "Probada", niveles 2 y 3 sin ejecutar, carga con percepción simulada en una máquina y τ con un solo revisor. El lego premia la franqueza. |
| Análisis y conclusiones | 4,0 | 3,6 a 4,2 | Tabla 24 con columna "Alcance" y limitaciones por tipo de validez (Wohlin) son ejemplares. Restan los verbos causales con n = 6 en 1.2, el 84 % presentado como ahorro de revisión y el análisis de impacto más inventario de límites que análisis. |

Media global de los seis criterios: 4,08.

## 2. Nivel de maestría

Los cinco jurados dicen que sí está a la altura en rigor de método y en candor sobre los límites: preregistro, partición por colegio apartada antes de mirar, intervalos, sensibilidad, ablaciones, comparación contra el óptimo exacto, registro abierto de 85 hallazgos. Lo que le falta para sostener el nivel en una defensa exigente:

1. Una línea base realista. Hoy se compara con reglas (F1 0,298), azar, una regla simple y Google Vision, GOT-OCR y Docling. No hay LLM de propósito general ni otro optimizador multiobjetivo (MOEA/D, SPEA2). La memoria ya lo admite como trabajo futuro; conviene decirlo también como limitación.
2. Validez independiente de la medición clave: un anotador, oro de percepción derivado de Gemini (coincide en 86,7 %), 405 pares de τ con 391 de un colegio, 3 colegios de prueba.
3. Un OE5 que prueba funcionamiento y SUS alto pero deja la tarea crítica T4 en 1 de 5; la reducción de carga queda como indicio (n = 6, recuerdo de la compra frente a tarea guiada).
4. Coherencia interna tras los recortes de espacio: referencias cruzadas, ADR, RNF, una frase sobre Wompi, una sobre τ.

## 3. Hallazgos ALTO que sobreviven (7)

### A1. "Iguala el óptimo" sigue en el cuerpo (pp. 50 y Figura 12)
- Cita: "En el perfil Ahorrador, NSGA-II iguala ese óptimo en el 100 % de las listas." (p.50). Pie de Figura 12: "...una elección al azar igualan el óptimo de la programación dinámica" y eje "% de listas que igualan el óptimo".
- Fuente: `sections/resultados.tex` líneas 185, 197 y 202. (B escribió que no estaba literal; es falso, la cruzada lo corrigió.) La mención de p.40 ("se igualan los dos costos") es otra cosa y no se toca.
- Problema: es la frase que la autora pidió retirar. Además el Ahorrador es casi separable, la regla simple también marca 100 % y NSGA-II parte sembrado con esa regla, así que "igualar" no mide a NSGA-II; son una semilla.
- Reescritura: en p.50, "En el perfil Ahorrador, NSGA-II coincide con el costo de la programación dinámica en las 174 listas, igual que la regla simple (una semilla); lo que lo distingue es el frente, no ese kit." En la Figura 12 eje: "% de listas con el costo del exacto"; pie: "...alcanzan el costo mínimo de la programación dinámica". En la línea 197 de resultados.tex: "cuántas listas alcanzan el costo exacto". Revisar que la Tabla 24 y el resumen no lo repitan (no aparece en el cuerpo actual).

### A2. Se anuncian "amenazas a la validez" que ya no existen (pp. 46 y 36)
- Citas: p.46 "y al final las amenazas a la validez, donde se reúnen los límites de la evidencia."; p.36 (VI.6) "lo formaliza, lo resuelve, lo calibra y declara las amenazas a la validez."
- Problema: el capítulo VII termina en VII.6; los límites están en VIII.2.1. El lector busca una sección que no está. Es consecuencia directa de la decisión de convertirlas en párrafo de Conclusiones.
- Reescritura: p.46 "y, en el Capítulo VIII, los límites de la evidencia (Sección VIII.2.1)." p.36 "lo formaliza, lo resuelve, lo calibra y remite sus límites a la Sección VIII.2.1." Dentro de VIII.2.1, abrir cada uno de los cuatro límites con la cifra que afecta (el 0,948, τ, el 0,9969, SUS y RTLX) para no perder trazabilidad.

### A3. p.17 dice que se usó el entorno de pruebas de Wompi; el resto del cuerpo dice que fue simulado
- Cita p.17: "En la evaluación se usó su entorno de pruebas, conectado mediante una capa intermedia...". Contra p.45 ("la prueba en el sandbox de Wompi queda pendiente"), p.52 ("No se ejecutó el pago con las llaves de sandbox") y p.59 ("el pago se probó en modo simulado y no en el entorno de pruebas de Wompi").
- Problema: contradicción literal sobre el OE4 ("integradas con la pasarela de pagos"). Además la Tabla 19 dice "6 de 6 pagaron" sin rotular que el pago simulado aprueba solo.
- Reescritura: p.17 "En la evaluación se usó una versión simulada de la pasarela, conectada mediante la misma capa intermedia que permitirá cambiar a su entorno de pruebas (ADR 0033, ...)". Tabla 19: "6 de 6 llegaron a pedido pagado (pago simulado)". Sin cambiar el estado del OE4.

### A4. "El sistema se ahorró la revisión de cuatro de cada cinco" (p.48)
- Cita: "de cada 100 renglones aceptados sin revisión, 97 eran correctos, y el sistema se ahorró la revisión de cuatro de cada cinco."
- Problema: el 84,0 % es cobertura sobre 405 pares que ya tenían candidato. En el recorrido completo solo el 35,3 % se resuelve solo (p.49) y el administrador revisa toda lista nueva antes de publicarla (PE-04), así que τ ordena la revisión, no la elimina. Un jurado lo cita contra la propia memoria.
- Reescritura: "...97 eran correctos. Esa cobertura (84,0 %) se mide entre los pares con candidato; en el recorrido completo el 35,3 % se resolvió solo, y τ sirve para priorizar la revisión, que se hace de todas formas."

### A5. Procedencia de las cifras de τ (pp. 31, 48 y 59)
- Citas: p.31 "la medición del umbral hecha el 4 de octubre pertenece a un prototipo que no se integró y sus cifras se citan tal como se reportaron allí"; p.59 "Las corridas de τ y la evaluación con usuarios usaron la misma versión del código, b6b6fe7".
- Problema: leídas juntas no se sabe qué algoritmo produjo la precisión 0,968, la cobertura 84,0 % y el AUC 0,921 que aparecen como evidencia "Cumplido" del OE3 (Tablas 19 y 24). La cruzada quedó dividida (2 a 2) sobre la gravedad; sostengo ALTO porque es la métrica central del OE3 y se arregla con una frase.
- Reescritura: dejar una sola procedencia. Si los 405 pares se corrieron con la resolución del commit b6b6fe7, quitar la frase del prototipo en p.31; si no, rotular en Tablas 19 y 24 "τ medido en el prototipo de la resolución (4 de octubre)". Añadir si los 405 pares son disjuntos de los casos de error usados para ajustar γ, θ y ϕ (p.33).

### A6. Referencia errónea a la encuesta en Conclusiones (p.57)
- Cita: "Según la encuesta del OE1 (Sección VII.1), comprar los útiles de un colegio cuesta a las familias mucho tiempo."
- Problema: la Sección VII.1 es percepción documental; la encuesta está en el Capítulo IV. La frase además es vaga y la cifra ya existe (65 % dedica cuatro horas o más, p.1 y p.15). Gravedad real baja, corrección de una palabra, pero está en el cierre. No tocar las otras citas a VII.1 (pp. 8, 9, 58), que sí son correctas.
- Reescritura: "Según la encuesta del OE1 (Capítulo IV), el 65 % de las familias dedica cuatro horas o más a comprar los útiles de un colegio."

### A7. "Esa insatisfacción" sin antecedente (inicio de p.58)
- Cita: "...Por eso, esa insatisfacción no se generaliza a la población escolar colombiana."
- Problema: el párrafo anterior habla del sesgo de estrato (estrato 4 sobrerrepresentado, sin estratos 1 y 6), no de insatisfacción. Residuo de edición.
- Reescritura: "Por eso, los resultados de la encuesta no se generalizan a la población escolar colombiana."

## 4. Hallazgos MEDIO que sobreviven (12)

1. **Tabla 9, RNF mal citados (p.20).** Dice "(RNF03, RNF04)" para tarjeta, "(RNF06)" para operar con cuatro personas y "(RNF08)" para cambios sin romper otro servicio. En la Tabla 8 (p.17) la tarjeta es RNF01, RNF03 es tiempo de respuesta, RNF06 es crecer a 1.000 usuarios. Alinear los códigos con la Tabla 8.
2. **ADR 0013 en el cierre (p.58).** "seis desplegables sobre cinco bases de datos (ADR 0013)": el ADR 0013 es la matrícula (p.27); la división en servicios es el ADR 0001 (p.21) y el monorrepositorio el 0014 (pp.17, 28). Corregir a ADR 0001. Las demás menciones están bien.
3. **Cota del 3,7 % en los ataques (pp.42, 51).** La regla de tres supone intentos independientes; son 27 ataques por 3 repeticiones y la p.59 admite que el criterio de descarte de la última ronda cambió sin preregistro. Reportar la cota sobre 27 ataques distintos (cerca de 11 %) o dejar "no se encontró un ataque exitoso".
4. **Ley 1581 y Decreto 1377 "piden aislar los datos de menores, con base y llaves propias" (p.21, Tabla 10).** Esas normas exigen consentimiento y el interés superior del menor; el aislamiento es una decisión de diseño. Escribir "motivan reducir lo que debe auditarse; el aislamiento con base y llaves propias es una decisión de diseño". En p.17, "queda fuera del alcance de cumplimiento de los datos de tarjeta" debe ir como expectativa mientras Wompi no se pruebe.
5. **Datos de menores en las sesiones (pp.17, 33, 52-53).** La minimización se plantea como regla, pero el nombre en el documento cargado viaja al proveedor y varios acudientes subieron listas de sus hijos (PE-06 abierto). Añadir una frase con lo que se hizo con esos datos tras las sesiones (borrado, fecha). La Tabla 8 ya dice "Cumplimiento parcial". Severidad baja de ALTO a MEDIO por consenso (A y C lo calificaron de declarado).
6. **"Cumplido" del OE5 junto a 1 de 8 características ISO "Probada" y 16 hallazgos altos (pp.52-53, 58).** Sin cambiar estado, añadir en el párrafo del OE5: "Cumplido significa que las cuatro clases de prueba se ejecutaron y se midió la experiencia, no que el sistema esté listo para operar; por eso el trabajo futuro empieza por producción." No hace falta tabla nueva (no cabe).
7. **Verbos causales con n = 6 en 1.2 (p.57).** "los seis acudientes pagaron su kit, la carga percibida bajó de 63 a 9" sin el matiz de la p.55. Escribir "la carga percibida fue de 9, frente a 63 recordados para la última compra (indicio con n = 6)". Los jurados lo calificaron ALTO (A) pero cuatro lo vieron ya matizado en pp.54-55, 59.
8. **Estado del arte y línea base de LLM directo (pp.11-13, 2-3).** Añadir en 2.3 una frase que admita que no se comparó con un LLM de propósito general que lea la lista y arme el pedido, y que la afirmación "ninguna" y "única de las siete" depende de lo revisado en noviembre de 2026. Evita que el flanco "¿y ChatGPT con una foto?" sea una sorpresa.
9. **Sesgo del 0,948 (p.59, Tabla 19).** Ya está declarado, pero la tabla lo presenta sin matiz. Anotar en la Tabla 19: "oro corregido sobre Gemini; la ventaja sobre las reglas es firme, sobre Vision menos".
10. **Escalar a otro colegio "sin cambiar el sistema" (p.2).** El ensayo con 14 PDF dejó 1.397 productos faltantes y 20,98 % de abstención (p.49). Escribir "sin cambiar el código, pero con curaduría del catálogo".
11. **Conteos de conceptos (pp.31, 33, 35, 58).** 99 (corpus OE1, p.58), 98 (oro, Tabla 15), 149 definidos y 145 activos (catálogo). Añadir una nota de reconciliación; no hay error aritmético (175 instancias salen de 174 listas, p.50). La cuenta "13 servicios más puerta de enlace" es coherente, solo conviene decir "14 desplegables" una vez.
12. **Siglas internas sin definir en el primer uso (Faro p.54; ESC-D4 p.4; DP-03; CGS-10).** Glosa breve ("el Faro, el comercio de referencia") o quitar la sigla en el cuerpo.

Además, uno solo (C) y sin refutación: las oraciones de cierre de cada objetivo en pp.58-59 mezclan metodología y cinco cifras; separar "qué se hizo" y "por qué se da por cumplido" mejora la lectura si el límite de páginas lo permite.

## 5. Descartados o rebajados en la cruzada

- **RTLX con n = 6 como ALTO (A).** Cuatro jurados: ya matizado en pp.54-55 y 59. Queda como MEDIO 7 y como pregunta de defensa.
- **ISO 25010 "protocolo de pruebas visible" como ALTO y tabla nueva (B).** Cuatro jurados: la Tabla 21 ya es el protocolo por característica y el cuerpo está al tope. Pasa al MEDIO 6.
- **Dos corridas con resultados distintos el 1 y el 2 de noviembre (B).** Detalle ya declarado; BAJO.
- **"2.1 Limitaciones se lee como lista corrida" (C).** Cuatro jurados: es la recomendación de la autora cumplida, con frase-eje por párrafo. Estilo.
- **137 + 37 = 174, no 175 y 12 + 28 vs 75 (E).** La p.50 dice que son 175 instancias de 174 listas; se arregla con la nota del MEDIO 11.
- **0,47 s frente al máximo de 0,45 s (E).** Dos experimentos distintos (calibración frente a ESC-D4 en un M4). Rotular, no corregir.
- **p-valores unilaterales frente a intervalos bilaterales y reetiquetar C3 (E).** Recálculo no verificado y C3 ya aparece por tarea. Queda como pregunta de defensa.
- **"13 contra 14 servicios" y "ADR 0013 contra 0014" en p.30 (A, B).** Falso: 13 más puerta de enlace es 14, y el monorrepositorio figura como ADR 0014 en pp.17 y 28.
- **Latencia y recuperación del sistema construido sin medir (B).** Admitido en el cuerpo; es limitación, no defecto.
- **Comisión del 15 %, Tabla 5 "entrega ✗" frente a repartidores propios, MAUT con marca y calidad sobre un mismo eje y Fan fuera del frente (E).** Nadie los refutó pero tampoco los confirmó; no los verifiqué contra el .tex. Son buen material de defensa (ver PREGUNTAS_SUSTENTACION.md).
- **Estilo menor (C):** tríada "Primero, Segundo, Tercero", "es decir" 21 veces, cierre de una línea "Estos límites definen buena parte del trabajo futuro". Baratos si hay espacio; no bajan nota.

## 6. Orden sugerido de correcciones

1. A1, A2, A3, A4, A6, A7 (frases, sin efecto en paginación).
2. A5 y MEDIO 1, 2, 4 (una frase cada una).
3. MEDIO 5 a 10 solo si el cuerpo sigue en 60 páginas tras recompilar. Revisar índice y referencias `\ref` tras tocar VII y VIII.
