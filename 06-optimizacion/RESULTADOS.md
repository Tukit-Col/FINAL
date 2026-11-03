# Comparación de optimizadores: enumeración, programación dinámica, NSGA-II y voraz

Esta es la comparación propia de este repositorio. Las cifras salen de `resultados/resumen.json` y
`resultados/tablas.md`, que generan `scripts/correr.py` y `scripts/analizar.py`.

## Montaje

- **Instancias.** Las 175 listas del benchmark Laya (`datos/instancias.json.gz`, foto del catálogo
  `d60ef70e9428f7e6`). 174 tienen frente: una no tiene líneas decidibles. n medio = 16,9 líneas
  decidibles (máximo 64), k medio = 2,35 candidatos por línea (máximo 3) y |E| hasta 4,4 × 10¹⁷. En 137
  listas |E| > 4.096, así que producción corre NSGA-II. Se suman **24 hogares sintéticos** de 2 a 8
  hijos (listas consecutivas de un mismo colegio), con n de 21 a 313 y |E| hasta 10¹⁰⁷. Es el caso de
  varios hijos que el benchmark Laya no cubría.
- **Algoritmos.** Los cuatro reciben exactamente las mismas líneas y candidatos, y todos se puntúan con
  `_objetivos_de_asignacion` de producción:
  - *Enumeración exacta*: el `_frente_exacto` de producción, corrido hasta |E| ≤ 60.000 (65 listas).
  - *Programación dinámica (DP)*: la recurrencia del Teorema «El frente exacto se calcula en tiempo
    polinomial» de `07-optimizacion.tex`, implementada en `scripts/algoritmos.py`.
  - *NSGA-II (producción)*: el `_frente_nsga` de producción (`FINAL@a8f09c7`, rama `validacion/oe5`)
    importado sin copiarlo, con N = min(100, max(20, 6n)) redondeado a par y
    G = min(60, max(15, 10·log₁₀|E|)) calibrados, semilla por omisión (0), SBX (0,9; η = 15), PM
    (η = 20), redondeo y siembra con la heurística y la escalera, con los pesos de producción y sin
    filtros. Se corre en **todas** las listas, también en las que producción
    enumera, para medirlo contra el exacto.
  - *NSGA-II sin siembra*: el mismo algoritmo, con la población inicial al azar y sin reinyectar las
    semillas.
  - *Voraz*: los tres kits de `elegir_por_perfil` más los peldaños de la escalera de costo marginal,
    filtrados por no dominancia.
- **Medición.** Tiempo de pared con `perf_counter`, en un proceso y un hilo BLAS, en una pasada. El
  pico de memoria se midió con `tracemalloc` en otra pasada (NSGA-II en una de cada 5 listas y uno
  de cada 3 hogares, ordenados por n). La calidad se mide contra el frente exacto de la DP.
  Máquina: Apple M4 (10 núcleos, 24 GiB), macOS 26.7.1, Python 3.12.12, numpy 2.5.3 y pymoo 0.6.2.
  **Había otras cargas en la máquina** (Postgres, Redis y RabbitMQ de Homebrew activos; carga media de
  1,54 / 1,76 / 2,10 al lanzar la corrida del NSGA-II y de 2,10 / 1,91 / 2,09 al terminar la pasada de
  tiempo), así que los tiempos absolutos son indicativos; las razones (de unas 10² veces) no dependen
  de eso.
- **Qué se re-ejecutó.** La enumeración, la DP y el voraz son los de la corrida con `FINAL@30cf1b5`:
  con `FINAL@a8f09c7` el frente exacto, n y |E| son idénticos en las 332 filas, porque la rama no
  cambia los objetivos ni los candidatos admisibles. Las dos variantes del NSGA-II se re-ejecutaron
  con `scripts/actualizar_nsga.py` (tiempo, memoria y hogares) y `correr.py semillas` (las 5 semillas),
  el 2 de noviembre de 2026.
- **Calidad.** HV/HV* es el hipervolumen en los 4 objetivos normalizados por instancia con el ideal y
  el nadir del frente exacto (punto de referencia 1,1), dividido por el del frente exacto. «Frente
  exacto» significa el mismo conjunto de vectores objetivo; «cobertura», la fracción de puntos del
  exacto que se encontraron. Para los escenarios se proyecta el frente con las reglas de producción
  (`_proyectar`; con presupuesto, la mejor marca que cabe) y se compara con el óptimo de
  `escenarios.json`.

## Tabla 1. Resumen en las 174 listas reales

| Algoritmo | Listas | Tiempo mediano | Tiempo p95 | Tiempo máximo | Memoria pico mediana | HV/HV* medio | HV/HV* mínimo | Frente exacto | Cobertura del exacto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Enumeración exacta | 65 | 47,7 ms | 8,85 s | 29,3 s | 1,54 MiB | 1 | 1 | 100 % | 100 % |
| **Programación dinámica** | 174 | **0,64 ms** | 4,1 ms | 8,7 ms | 0,12 MiB | **1** | **1** | **100 %** | **100 %** |
| NSGA-II (producción) | 174 | 243 ms | 323 ms | 782 ms | 0,82 MiB | 0,9981 | 0,9511 | 81,6 % | 94,9 % |
| NSGA-II sin siembra | 174 | 236 ms | 306 ms | 801 ms | 0,81 MiB | 0,8673 | 0,6678 | 6,3 % | 42,5 % |
| Voraz | 174 | 0,57 ms | 2,0 ms | 4,5 ms | 0,04 MiB | 0,4299 | 0,1113 | 1,1 % | 44,0 % |

- La DP da **el mismo frente que la enumeración en las 65 de 65 listas** donde la enumeración corre, y
  también en 1.000 instancias aleatorias de 2 a 8 líneas con y sin personaje pedido (`test_dp.py`). La
  mochila de presupuesto, O(n²k), coincide con la fuerza bruta en 500 instancias.
- NSGA-II tarda, en mediana, **311 veces** lo que tarda la DP en la misma lista (entre 38 y 3.608
  veces). En las 174 listas suman 0,18 s de DP contra 39,3 s de NSGA-II.
- En las 137 listas en que producción usa NSGA-II, su frente es exacto en el 76,6 %, con HV/HV* medio
  de 0,9976 (mínimo 0,9511) y cobertura de 93,5 %.
- El máximo de NSGA-II (782 ms) es la lista 2.2 de Séptimo, con n = 8, |E| = 54, N = 48 y G = 17: en un
  espacio tan pequeño la eliminación de duplicados de pymoo repite el muestreo para llenar la población
  (al re-medirla tarda de 0,85 a 0,97 s). Producción enumera esa lista. En las 137 listas en que
  producción usa NSGA-II la mediana es de 250 ms y el máximo de 393 ms, lejos del límite de 20 s de
  RNF03.
- La enumeración de producción (|E| ≤ 4.096) tarda como máximo 0,34 s, y su tiempo crece como
  |E|^1,5 (ajuste sobre 58 listas con |E| ≥ 100).

## Tabla 2. Iguala el óptimo por escenario (kit proyectado del frente)

| Algoritmo | Ahorrador (174) | Premium (174) | Fan (157) | Presupuesto (174) | Calidad con presupuesto |
|---|---:|---:|---:|---:|---:|
| Programación dinámica | 100 % | 100 % | 100 % | 100 % | 100 % |
| NSGA-II (producción) | 100 % | 100 % | 100 % | 98,9 % | 100 % |
| NSGA-II sin siembra | 94,3 % | 6,3 % | 100 % | 18,4 % | 90,6 % |
| Voraz | 100 % | 100 % | 100 % | 86,8 % | 99,1 % |

Con el optimizador calibrado, el kit recomendado con presupuesto iguala el óptimo en el 98,9 % de las
listas (172 de 174) y logra el 100 % de la calidad alcanzable en todas, y la heurística acierta el
100 % de los Ahorrador. Pero **el NSGA-II sin siembra no llega**: Premium en 6,3 % y Presupuesto en
18,4 %. Los extremos y el compromiso con presupuesto los garantiza la siembra voraz, no la evolución.

## Tabla 3. Tiempo y memoria por tamaño (medianas)

| n | Listas | log₁₀\|E\| mediano | Enumeración | DP | NSGA-II | NSGA-II sin siembra | Voraz | Ternas DP (máximo por etapa) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1–10 | 37 | 2,7 | 12,3 ms / 0,56 MiB | 0,25 ms / 0,04 MiB | 109 ms / 0,40 MiB | 122 ms / 0,41 MiB | 0,24 ms / 0,02 MiB | 21 |
| 11–15 | 43 | 4,9 | 968 ms / 16,7 MiB (21 listas) | 0,57 ms / 0,09 MiB | 166 ms / 0,62 MiB | 163 ms / 0,62 MiB | 0,45 ms / 0,03 MiB | 44 |
| 16–20 | 57 | 6,2 | 7,72 s / 71,3 MiB (6 listas) | 0,75 ms / 0,13 MiB | 252 ms / 0,85 MiB | 244 ms / 0,83 MiB | 0,66 ms / 0,05 MiB | 54 |
| 21–30 | 21 | 7,4 | 3,17 s / 130 MiB (1 lista) | 1,1 ms / 0,16 MiB | 275 ms / 0,87 MiB | 269 ms / 0,85 MiB | 1,0 ms / 0,06 MiB | 62 |
| 31–64 | 16 | 12,8 | — | 4,5 ms / 0,91 MiB | 284 ms / 1,00 MiB | 269 ms / 0,87 MiB | 2,1 ms / 0,14 MiB | 253 |

## Tabla 4. Hogares sintéticos (varios hijos)

| Hogar | Hijos | n | log₁₀\|E\| | Ternas DP | DP: tiempo / memoria | NSGA-II: tiempo / memoria | HV/HV* NSGA-II | HV/HV* sin siembra | HV/HV* voraz |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.4, 3 hijos, desde Quinto | 3 | 21 | 6,7 | 114 | 2,1 ms / 0,3 MiB | 259 ms / 0,9 MiB | 1,000 | 0,792 | 0,473 |
| 2.11, 3 hijos, desde Quinto | 3 | 40 | 15,9 | 366 | 9,2 ms / 1,7 MiB | 282 ms / 1,1 MiB | 0,932 | 0,704 | 0,197 |
| 2.11, 4 hijos, desde Cuarto | 4 | 60 | 23,4 | 546 | 19,1 ms / 3,7 MiB | 351 ms / 1,6 MiB | 0,929 | 0,642 | 0,195 |
| 2.3, 6 hijos, desde Cuarto | 6 | 80 | 27,1 | 1.515 | 45,6 ms / 8,4 MiB | 439 ms / 2,0 MiB | 0,879 | 0,583 | 0,580 |
| 2.14, 7 hijos, desde Cuarto | 7 | 110 | 36,5 | 1.994 | 119 ms / 22,5 MiB | 562 ms / 3,1 MiB | 0,834 | 0,567 | 0,316 |
| 2.9, 8 hijos, desde Cuarto | 8 | 141 | 45,7 | 2.097 | 157 ms / 25,9 MiB | 687 ms / 3,8 MiB | 0,820 | 0,511 | 0,260 |
| 2.13, 5 hijos, desde Once | 5 | 195 | 67,5 | 5.290 | 474 ms / 95,3 MiB | 925 ms / 7,0 MiB | 0,701 | 0,478 | 0,454 |
| 2.13, 6 hijos, desde Cuarto | 6 | 238 | 81,2 | 6.184 | 705 ms / 135 MiB | 1,11 s / 8,8 MiB | 0,592 | 0,460 | 0,405 |
| 2.13, 8 hijos, desde Cuarto | 8 | 313 | 107,0 | 11.900 | 2,56 s / 297 MiB | 1,46 s / 12,6 MiB | 0,648 | 0,429 | 0,444 |

Las 24 filas están en `resultados/tablas.md`. En los 24 hogares, con el tope a la mitad entre
Ahorrador y Premium: NSGA-II (producción) iguala el Ahorrador y el Premium exactos en el 100 % e iguala
la mejor marca que cabe en el 83,3 % (99,79 % de la calidad en promedio, 98,36 % como mínimo), lo mismo
que el voraz, porque con N y G calibrados los kits proyectados en hogares grandes son los de la siembra.
El NSGA-II sin siembra logra 12,5 %, 0 % y 0 % (71,4 % de la calidad).

## Tabla 5. Variabilidad del NSGA-II con 5 semillas (de 0 a 4; 174 listas × 5 semillas)

| Variante | Corridas | HV/HV* medio | HV/HV* mínimo | Corridas con frente exacto | Listas con frente exacto en las 5 semillas |
|---|---:|---:|---:|---:|---:|
| NSGA-II (producción) | 870 | 0,9980 | 0,9511 | 77,5 % | 58,6 % |
| NSGA-II sin siembra | 870 | 0,8612 | 0,6189 | 6,7 % | 3,4 % |

La desviación media del HV/HV* entre semillas de una misma lista es de 0,0007 con siembra y de 0,026
sin ella.

## Tabla 6. Complejidad asintótica y crecimiento medido

M = 4 objetivos; N y G son la población y las generaciones; S_i son las ternas (a, b, p) alcanzables
tras i líneas; U son los vectores objetivo distintos.

| Algoritmo | Tiempo (teórico) | Memoria (teórica) | Medido: tiempo ∝ | Medido: memoria ∝ |
|---|---|---|---|---|
| Enumeración exacta | O(\|E\|·n + \|U\|²·M), con \|U\| ≤ \|E\| ≤ 3ⁿ | O(\|E\|·n) | \|E\|^1,5 | — |
| Programación dinámica (frente) | O(n·S·k) con S ≤ (2n+1)(n+1)², es decir O(n⁴k); filtro final O(S) | O(Σᵢ Sᵢ) = O(n⁴) para recuperar las asignaciones | n^2,55 | n^2,61 |
| Programación dinámica (presupuesto, MCKP) | O(n²k) | O(n²) | — | — |
| NSGA-II, por corrida | O(G·(M·N² + N·n)), con N = min(100, max(20, 6n)) par y G = min(60, max(15, 10·log₁₀\|E\|)) | O(N·n) | n^0,49 | n^0,83 |
| Voraz (heurística + escalera) | O(n²k), con ≤ 2n + 1 peldaños | O(n²) | n^1,78 | n^1,78 |

El peor caso de la DP casi nunca se alcanza: en las listas reales, todas las líneas tienen precio (b
no varía) y pocas tienen personaje (p casi no varía). Así, para n = 17 se alcanzan como mucho unas 54
ternas por etapa frente a las 11.340 del peor caso, y para n = 313 unas 11.900 frente a 6,2 × 10⁷. Por
eso la DP medida crece como n^2,6 y no como n⁴. El NSGA-II tiene topes (N ≤ 100, G ≤ 60), así que con n
grande solo crece la evaluación O(N·n). El exponente de memoria (n^0,83) sale de solo 30 corridas
medidas con tracemalloc.

## Qué puede y qué no puede representar la DP

| Elemento del modelo | ¿La DP lo representa? | Cómo, o por qué no |
|---|---|---|
| Los 4 objetivos (costo, fidelidad, disponibilidad, personaje) | **Sí, de forma exacta** | El costo es el valor de la DP; los otros tres son conteos en el estado (a, b, p) |
| Empaque **por línea**: u = ⌈q/emp⌉ | **Sí** | Está dentro de κᵢ(c), que es separable por línea |
| Personaje pedido por hijo | **Sí** | φᵢ(c) depende solo de la línea y del hijo |
| Presupuesto como restricción dura | **Sí** | Se podan los estados con C > B, o se filtra el frente; con un solo objetivo es la MCKP O(n²k) |
| Proyección y recomendación (A tu Medida y lo demás) | **Sí** | Operan sobre el frente ya calculado |
| **Coherencia de personaje** (todo el kit con el mismo personaje cuando no se pidió uno) | **No, en la formulación vigente** | f₄ cuenta cualquier personaje, y la coherencia no es separable. Se puede agregar con una DP por personaje (O(\|Π\|·n⁴k)); «máximo número de líneas con un mismo personaje» es el máximo de esas \|Π\| DP. Contar personajes distintos exigiría guardar conjuntos en el estado (exponencial) |
| **Empaque entre líneas**: juntar herramientas de un hijo (máx. q por producto) y consolidar entre hermanos (⌈Σq/emp⌉) | **No** | El costo de una línea depende de si otra eligió el mismo producto; no es separable. El estado tendría que llevar la demanda acumulada por producto compartido (exponencial en los productos compartidos). Hoy tampoco está en f₁: producción lo aplica después de elegir |
| Costo fijo por tienda o proveedor usado | Solo con pocas tiendas | El estado lleva el subconjunto de tiendas usadas (2^T); con T = 2 multiplica los estados por 4 |
| Objetivos no aditivos (peor línea, varianza de calidad) | No directamente | Hace falta otro estado, por ejemplo el mínimo nivel visto |

## ¿Por qué NSGA-II y no programación dinámica? (respuesta con la evidencia)

1. **Con la formulación vigente, la evidencia favorece a la DP en todo lo que se midió en listas
   reales.** Es exacta por construcción y verificada (65/65 listas y 1.000 instancias aleatorias),
   unas 310 veces más rápida en mediana (0,64 ms contra 243 ms) y usa menos memoria en 32 de las 35
   listas reales en que se midió (n ≤ 64; en los hogares, solo en el de 21 líneas). El NSGA-II de
   producción da el frente exacto en el 81,6 % de las listas y sus kits proyectados igualan el óptimo
   en Ahorrador, Premium y Fan en todas y con presupuesto en el 98,9 %, pero ese resultado lo explica
   la siembra voraz: sin ella, el mismo NSGA-II acierta el Premium en el 6,3 % y el presupuesto en el
   18,4 %.
2. **Lo único que el NSGA-II gana es un costo acotado.** Su tiempo (n^0,5) y su memoria (≤ 13 MiB con
   n = 313) casi no crecen, porque N y G tienen tope, mientras la DP crece como n^2,6 (297 MiB y 2,6 s
   con n = 313). Con N y G calibrados, el NSGA-II es más rápido que la DP en el hogar de 8 hijos y 313
   líneas (1,46 s contra 2,56 s); en los demás hogares la DP sigue siendo más rápida (de 1,2 a 195
   veces). A cambio, el frente del NSGA-II se degrada más en los hogares grandes (HV/HV* de 0,59 a
   0,94 en hogares de más de 60 líneas), aunque los kits proyectados siguen siendo los de la siembra.
   Un hogar de 4 hijos tiene unas 70 a 140 líneas, lejos del cruce.
3. **La justificación legítima del NSGA-II es la extensibilidad**, no la calidad ni la velocidad con el
   modelo de hoy. Si se incorporan términos acoplados (la consolidación entre hermanos o juntar
   herramientas dentro de f₁, un costo fijo por tienda o la coherencia de personaje), la separabilidad
   se rompe y la DP deja de aplicar o explota en estados. El NSGA-II solo necesita evaluar el kit
   completo como una caja negra. Es la misma conclusión del «Hallazgo» del documento de algoritmos.
4. **Recomendación.** Usar la DP como motor exacto del frente vigente, o al menos como referencia,
   semilla y verificación, y conservar el NSGA-II para cuando el objetivo incluya acoplamientos. Una
   opción intermedia es sembrar el NSGA-II con el frente de la DP y evaluar con el costo consolidado,
   lo que garantiza no quedar por debajo del óptimo separable.

## Figuras

- `figuras/fig_opt_tiempo.pdf|png`: tiempo de pared frente a n y frente a |E| (log-log), en listas
  reales y hogares sintéticos.
- `figuras/fig_opt_memoria.pdf|png`: pico de memoria (tracemalloc) frente a n (log-log).
- `figuras/fig_opt_calidad.pdf|png`: (a) HV/HV* por algoritmo, listas y hogares; (b) porcentaje de
  listas en que el kit proyectado iguala el óptimo, por escenario.
