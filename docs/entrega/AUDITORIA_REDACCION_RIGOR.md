# Auditoría de redacción y rigor (2026-11-02)

Alcance: memoria-final (main.tex, sections/*.tex, bib/tukit.bib, PDF de 95 páginas), ENMIENDA_*.md, HECHOS_CANONICOS_DOCS.md, VFP v4 (muestreo con pandoc) y QC/control_calidad.tex. Lectura por muestreo con rg y Read con offset. Nada se editó ni se compiló. Las rutas `sections/` son de `memoria-final/`. No verifiqué el código del producto; lo que dicen los cambios de hoy (direccion, fan, planlector) se toma del encargo.

## 1. Veredicto por documento

| Documento | Veredicto | Motivo corto |
|---|---|---|
| Memoria, caps. I a VI | Buena base, con 6 desalineaciones | Estructura de Dani y formato de Leo presentes en resolución, optimización y NL2C. Fallan cifras de arquitectura, una afirmación sin evidencia (pago) y párrafos largos. |
| Memoria, cap. VII y VIII | No está lista para jurado | `oe5.tex` y `calidad.tex` son stubs de una frase; 14 marcas `\pendienteEvidencia` siguen vivas (pendientes_evidencia.txt); la tabla de cumplimiento deja OE4 y OE5 en "Ver Sec."; hay tres versiones de cifras de prueba sin conciliar. |
| Anexos y bib | Aceptable, con huecos de cita | 83 claves citadas, todas existen en el bib. Faltan Hart 2006 y IEEE 29119-3. Nielsen 1994 y Bangor 2008 están en el bib pero no se citan. 3 citas de la introducción usan claves `noauthor_*`. |
| ENMIENDA_SDD/SPMP/SRS_v7/WBS | Coherentes con HECHOS | Patrón texto actual / reemplazo / por qué. Ninguna cubre todavía dirección (ADR 0049), chat flotante ni Fan por post-proceso. |
| HECHOS_CANONICOS_DOCS | Sólido, desactualizado en 4 puntos | Faltan filas de dirección/OSM, Fan sin repetición, libros, y el conteo de pruebas de inteligencia. |
| VFP v4 | Sin hallazgos nuevos en el muestreo | Ya dice Minikube y Capacitor como trabajo futuro; menciona mapa OSM de entregas. |
| QC/control_calidad.tex | Buen informe de hechos, incompleto como IEEE 29119-3 | Dice seguir esa norma pero no tiene plan, riesgos, criterios de finalización ni desviaciones; tiene contradicciones internas (sección 3). |

## 2. Problemas concretos (archivo:línea)

### Críticos (un jurado los ve)

1. `sections/oe5.tex:1-4` y `sections/calidad.tex:1-4`: cada uno es una frase. Son las dos secciones que sostienen "análisis, control de calidad y prototipo". `conclusiones.tex:58` y `:81` remiten a ellas para juzgar OE5.
2. `sections/desarrolloSolucion.tex:372-374`: "El flujo de pago se verificó en el entorno de pruebas (sandbox) ... con tarjeta, Nequi y PSE". QC (`control_calidad.tex`, Entorno) y HECHOS dicen modo simulado y "no hay llaves de sandbox". Es una afirmación no medida. La marca `\pendienteEvidencia` no se imprime, así que el PDF sí la afirma.
3. `sections/nl2c.tex:121-124`: dice que `marcas_excluidas` y `solo_disponibles` "todavía no llegan al optimizador". HECHOS (fila Filtros duros) dice que llegan desde `0059f6d` y que ya no se documenta como brecha. Contradicción directa.
4. Tres cifras de prueba sin conciliar: `resultados.tex:226` (1.647 pruebas, 72,43 % de cobertura, versión del 8-oct), QC primera corrida (2.573) y re-ejecución (2.542, cobertura por servicio, commits a201f4c a 976deb1). El lector no sabe cuál es "la versión final".
5. `sections/desarrolloSolucion.tex:361-362` y `sections/disenoSolucion.tex:271-293`: la dirección sigue descrita como Google Places o texto libre y la copia del envío "en claro". Falta el cambio de hoy: búsqueda explícita en OpenStreetMap (Nominatim) más confirmación en mapa, ADR 0049, migración c7a41e9d02f5, latitud y longitud nulables, supresión del titular y firma de la orden. ADR 0044 no aparece en el texto.

### Altos

6. Desplegables: `introduccion.tex:58` ("seis servicios con cinco bases"), `disenoSolucion.tex:32,302,384`, `desarrolloSolucion.tex:57`, `conclusiones.tex:67` dicen seis. HECHOS fija 7 desplegables (5 de dominio, puerta de enlace, ingesta) y QC dice que ingesta no tiene código. Es conciliable (7 diseñados, 6 con código), pero la introducción debe decirlo igual que HECHOS.
7. `descripcionGeneral.tex:129-132`: "recibe tres propuestas ... Fan ... además A tu Medida". El Fan solo sale si pidió personaje; la introducción dice "hasta cuatro".
8. `optimizacion.tex:66` usa $U$ para la utilidad y `:101` usa $U\leq S$ para vectores distintos. Misma letra, dos cosas, en la sección que debe ser modelo de formato de Leo.
9. `optimizacion.tex:99-112`: el párrafo de complejidad da $N\sqrt{G}\approx 2^{...}$ y $GN^2\approx 2^{...}$ sin mostrar la igualación; es difícil de seguir. Falta la frase de Fan por post-proceso pedida hoy.
10. `resultados.tex:198-203`: tiempo de 5,3 s (29 listas) de un optimizador anterior, solo reportado, y la propia sección dice que no es la prueba ESC-D4. Con Fan sin repetición los costos del Fan pueden bajar; no encontré totales del Fan citados en la memoria, así que basta con no citar esta cifra como actual.
11. `resultados.tex:209-210`: el párrafo sobre umbrales de cobertura abre la sección sin contexto (sobre "microservicios anteriores"). Está fuera de lugar.
12. `conclusiones.tex:13` (1.085 caracteres, una línea) y `resultados.tex:237` (995 caracteres): párrafos de cinco a seis ideas. Chocan con el estilo de Dani (una idea por párrafo, contexto primero).
13. `conclusiones.tex:55`: "38 ADR". Ya existen ADR 0047 y 0049; confirmar el total vigente antes de imprimir.
14. `introduccion.tex:16`: "60 respuestas válidas". HECHOS y `analisisProblema.tex:56` dicen 65 recibidas y 60 analizables (5 sin consentimiento). No son inválidas.
15. Citas: Hart 2006 (RTLX) y IEEE 29119-3 no están en `bib/tukit.bib`. Nielsen 1994 (n mínimo por ronda) y Bangor 2008 (umbral SUS 68) sí, pero no se citan. Las claves `noauthor_resultados_2024/2025`, `noauthor_estadisticas_nodate`, `noauthor_informe_nodate-1` salen sin autor institucional.
16. Resumen/Abstract (`covers/abstract_resumen.tex`): sin palabras clave, sin una sola cifra de resultado y el ABSTRACT en inglés usa rayas largas. No da evidencia de metodología ni de resultados.

### Medios

17. Introducción: no declara pregunta, objetivo general ni mapa del documento (están en el cap. II). Verifique si el reglamento del TG los exige en la Introducción.
18. Subsecciones de Resultados (`resultados.tex:12`, `:58`, `:179`) abren con datos y sin la frase "En esta sección ..." del modelo de Dani; `analisisProblema.tex` sí la usa.
19. "de modo que" aparece 37 veces en las secciones; varíe con "por eso", "así", "en consecuencia".
20. Amenazas a la validez: bien en `resultados.tex:275-313` (Wohlin) y A1-A6 en `optimizacion.tex:170-187`, pero no cubren OE5 (muestreo por conveniencia sí) ni el límite de la dirección (OSM devuelve calle y no portón; sin autocompletado por política de Nominatim).
21. Diagramas: solo hay `c4-contenedores` (TikZ, cap. V) y `c4-contexto` (anexo, JPG). Hacen falta pipeline de tres etapas, flujo del pedido, despliegue (Minikube local; no hay vista física pese a citar 4+1), y trazabilidad OE a requisito a prueba. Ver sección 5.
22. Libros (planlector): no hay cifras de libros en la memoria. Si se agregan, usar las finales: C134 (libro_libre, isbn13) 78 líneas en `listas_revisadas.csv` (1.215 filas): 18 libro_libre con ISBN (17 ediciones, todas con precio y URL de Buscalibre), `otro` de 59 a 57, no_comprar de 1 a 3; 34 productos TK-LIB-* activos; similitud máxima de los 44 títulos faltantes 0,70. El encargo llega cortado en la causa ("cobertura de catálogo, no el emp..."): confirmar la frase completa antes de citarla. 1.215 filas no coincide con los 4.719 ítems de HECHOS; aclarar que son archivos distintos.

## 3. QC (control_calidad.tex)

- Líneas 20 y 32: dice seguir IEEE 29119-3. Faltan de esa estructura: identificador y versión del informe, resumen de la evaluación de la prueba (criterios de finalización cumplidos o no), desviaciones del plan (el texto las promete en la línea 33 y no hay sección), riesgos residuales y lista de verificación contra el plan de pruebas. No hay plan de pruebas citable. Cítese la norma en el bib o no se afirme que se sigue.
- Línea 87: la celda "scripts \ruta{e2e*.sh}" perdió la barra invertida (hay un salto de línea y `uta{...}`); el PDF imprime texto roto. Corregir.
- Líneas 463-473: "Pruebas de carga: no existen" y "cobertura no ejecutada" contradicen la re-ejecución (líneas 517-564), que sí mide ambas. "Usabilidad sumativa programada para el 2 de noviembre" ya está en pasado.
- Líneas 24-26 y 72-90: commit a664810 y 2.573 pruebas frente a 2.542 de la re-ejecución; el encabezado debe decir qué commit es el definitivo. La hora "UTC-8" de la línea 24 no coincide con Bogotá (UTC-5); confirmar.
- Trazabilidad (línea 405): agregar filas para dirección (latitud/longitud, supresión, firma) y Fan sin repetición. Sin cifras de rendimiento ni datos sembrados nuevos.
- El conteo de inteligencia en QC es 535 (`pytest_por_servicio.txt`). El "341 a 350" del encargo no aparece en HECHOS ni en QC, así que no lo copié: confirmar a qué suite se refiere (puede ser un subconjunto de pruebas de optimización).

## 4. Diez párrafos a reescribir (propuestas cortas, sin cifras nuevas)

**P1. `desarrolloSolucion.tex:372-374`** (pago, afirma sandbox)
Actual: "El flujo de pago se verificó en el entorno de pruebas (sandbox) de la pasarela con tarjeta, Nequi y PSE."
Propuesta: "El flujo de pago se probó con la pasarela en modo simulado, que es el modo por omisión del sistema. La prueba con las llaves de sandbox de Wompi queda pendiente, y el cobro con dinero real depende del despliegue productivo (Sección~\ref{sec:trabajo-futuro})." (Quitar la marca `\pendienteEvidencia` solo si se hace la prueba.)

**P2. `desarrolloSolucion.tex:361-362`** (dirección)
Propuesta: "La dirección de entrega se completa de dos maneras. Con una llave de Google, el servicio sugiere direcciones. Sin ella, el acudiente pulsa «Buscar», el sistema consulta OpenStreetMap con Nominatim y el acudiente confirma el punto en un mapa (ADR 0049). Nominatim prohíbe el autocompletado, por eso hay un botón y no sugerencias mientras se escribe. OpenStreetMap tiene menos numeración de predio que Google, y muchas búsquedas devuelven la calle y no el portón; por eso la confirmación en el mapa es parte de la decisión y no un adorno."

**P3. `disenoSolucion.tex:291-293`** (copia del envío)
Propuesta: "La copia del envío conserva el destinatario y la dirección en claro, como prueba ante un reclamo de la Ley 1480 de 2011. Desde el ADR 0049 guarda además la latitud y la longitud del punto confirmado, ambas nulables: los pedidos anteriores y los de Google quedan en NULL. El ADR 0044 había descartado guardar coordenadas por los términos de Google; la licencia ODbL de OpenStreetMap sí lo permite. La supresión del titular borra las dos columnas y la firma de la orden las incluye. La minimización por columna sigue sin cubrir el dato congelado."

**P4. `nl2c.tex:121-124`** (brecha ya cerrada)
Propuesta: "Los filtros `marcas_excluidas` y `solo_disponibles` se interpretan, se muestran al acudiente y llegan al optimizador (commit 0059f6d), que los aplica antes de calcular el frente. La marca que el colegio exige en el renglón no se quita. La ruta rápida de cambio canónico los rechaza con el error 422 `filtros_requieren_recalculo`." (Citar el commit como fuente y quitar "brecha de integración".)

**P5. `introduccion.tex:58-60`** (seis servicios)
Propuesta: "Todo corre sobre una arquitectura de cinco servicios de dominio con base propia y una puerta de enlace, es decir, seis desplegables con código. El diseño previó un séptimo, la ingesta, que el sistema construido reemplazó por un catálogo curado. La arquitectura se eligió entre tres alternativas con el método ATAM \citep{bass_software_2021}."

**P6. `descripcionGeneral.tex:129-132`** (tres propuestas)
Propuesta: "Como resultado, el acudiente recibe hasta cuatro propuestas de kit. El Ahorrador es el de menor costo y el Premium el de mejores marcas. El Fan aparece si pidió un personaje, y A tu Medida aparece si eligió el punto medio de gasto o declaró un tope, con la mejor marca que cabe en él."

**P7. `resultados.tex:198-203`** (29 listas)
Propuesta: "Una medición anterior reportó 5,3 s de media y 9,0 s de máximo para producir todos los kits de 29 listas. Se hizo con el optimizador previo a las correcciones del 4 y el 7 de octubre y no equivale a la prueba ESC-D4 del ATAM, que pide al menos 30 ejecuciones y el percentil 95. Por eso no se usa como resultado del sistema construido. El tiempo de generación por lista queda pendiente de medir sobre esta versión." (Eliminar la comparación con DP-03 hasta tener la medición.)

**P8. `conclusiones.tex:13`** (párrafo de 1.085 caracteres; dividir en tres)
Propuesta: "Segundo, el sistema se auditó más allá de sus requisitos funcionales. La auditoría de autorización encontró 22 de 152 puntos de entrada sin una comparación completa de ámbito, y la de datos personales, catorce hallazgos.

El sistema construido corrigió una parte y reemplazó las políticas de fila del ADR 0015 por un control de ámbito en la aplicación. La Sección~\ref{sec:defectos} reúne los que siguen abiertos.

Tercero, las fronteras entre servicios pasaron de convención a funciones de aptitud ejecutables \citep{ford_building_2017}: doce pruebas contrastan el código con el manifiesto y otras veintiocho comprueban que detectan infracciones plantadas. Las tres prácticas sirven si el seguimiento de los hallazgos forma parte del método."

**P9. `optimizacion.tex:100-102`** (notación)
Propuesta: "... y luego filtra los $V\leq S$ vectores distintos comparándolos por pares, con un costo de $O(V^2M)$ en el peor caso ..." (reservar $U$ para la utilidad de la línea 66; ajustar la misma letra en el Algoritmo~\ref{alg:frente-maut}).

**P10. `desarrolloSolucion.tex:288-289`** (Fan; también `optimizacion.tex`, después del Algoritmo)
Propuesta: "El Fan sale solo si el acudiente pidió un personaje. El personaje se reparte después de calcular el frente, por post-proceso: una vez por hijo y concepto, sin contradecir los atributos exigidos del renglón, y repetido solo si el renglón pide surtido. Es una regla de presentación y ensamblado posterior al frente, no un quinto objetivo: NSGA-II, los cuatro objetivos, la proyección de perfiles y la recomendación no cambian." (Revisar cualquier total del Fan que se cite; hoy no hay ninguno.)

## 5. Diagramas faltantes

1. Pipeline de tres etapas (percepción, normalización, optimización) con las revisiones humanas. Cap. IV o VI (`desarrolloSolucion.tex:14`).
2. Flujo del pedido (kit, cambio o descarte, dirección con mapa, pago, retracto). Cap. VI.
3. Vista de despliegue (Minikube local, 5 bases, puerta de enlace, RabbitMQ, Redis). Cap. V; hoy se cita el modelo 4+1 sin vista física.
4. Trazabilidad OE a requisito a prueba a evidencia. Cap. VII o anexo.
5. Secuencia de la dirección (Buscar, Nominatim, confirmar en mapa, guardar con coordenadas, supresión). Cap. V o VI.
6. Arquitectura de los datos personales (qué columna va cifrada). Opcional, anexo.

## 6. Tareas repartibles (por prioridad)

Responsable propuesto entre paréntesis; el equipo lo confirma.

| # | Prio | Doc / sección | Qué hacer | Criterio de terminado |
|---|---|---|---|---|
| 1 | P0 | Memoria VII.7-8, `oe5.tex`, `calidad.tex` | Escribir OE5 con el formato de Dani: diseño de la evaluación, participantes, instrumentos (SUS, NPS, RTLX, interacciones), resultados de las rondas 1 y 2, amenazas, estado frente a C1-C3. Escribir el resumen de QC con los cuatro niveles y la re-ejecución. (Dani) | Cada cifra con fuente y igual a HECHOS; sin `\pendienteEvidencia` en esas dos secciones; n<20 declarado exploratorio. |
| 2 | P0 | Memoria VI.9 `desarrolloSolucion.tex:372` | Reescribir pago (P1) sin decir sandbox. (Dani) | Texto coincide con modo simulado de HECHOS y QC. |
| 3 | P0 | Memoria `nl2c.tex:121` | Quitar la brecha de filtros duros (P4) y citar 0059f6d; añadir en la sección "Dónde quedó" el chat flotante en /kits y el inicio con formulario. (Dani) | Ninguna contradicción con HECHOS fila Filtros duros y NL2C. |
| 4 | P0 | Memoria V y VI, dirección | Aplicar P2 y P3; agregar el límite de OSM en amenazas (calle y no portón; sin autocompletado). (Dani + Juan) | ADR 0049 y c7a41e9d02f5 citados; ADR 0044 explicado como superado; sin cifras de rendimiento nuevas. |
| 5 | P0 | HECHOS_CANONICOS_DOCS | Añadir filas: dirección (OSM, lat/lon nulables, NULL en pedidos viejos y de Google, supresión y firma), Fan sin repetición (renglones_con_personaje, 50a0f4d), TUKIT_NOMINATIM_CONTACTO; actualizar conteo de pruebas de inteligencia tras confirmar la suite (350). Libros: cifras de planlector con la frase final completa. (Juan) | Cada fila con fuente y estado V/P; ningún número sin archivo o commit. |
| 6 | P0 | Memoria cap. VII, cifras de prueba | Fijar una sola versión (commit) y una tabla: pruebas, cobertura, hallazgos. Dejar las anteriores solo como histórico. (Juan) | `resultados.tex:226` y QC re-ejecución dicen lo mismo; el commit está nombrado. |
| 7 | P1 | QC/control_calidad.tex | Añadir plan y alcance, criterios de finalización, desviaciones, riesgos residuales; corregir línea 87, líneas 463-473 y la zona horaria; filas de trazabilidad para dirección y Fan; sección de dirección (lat/lon, supresión, firma). (Juan) | Compila; cada sección de 29119-3 usada está presente o declarada "no aplica"; sin contradicciones con la re-ejecución. |
| 8 | P1 | Memoria Cap. I, `introduccion.tex:16,58` | P5; cambiar "60 respuestas válidas" por "65 recibidas, 60 analizables"; agregar objetivo general y mapa del documento si el reglamento lo pide. (Dani) | Cifras = HECHOS; seis/siete desplegables explicados igual en I, V, VI y VIII. |
| 9 | P1 | Memoria II `descripcionGeneral.tex:129` | P6 (hasta cuatro kits). (Dani) | Coincide con intro y `analisisProblema.tex:365`. |
| 10 | P1 | Memoria VI.8 `optimizacion.tex` | P9 ($V$ en vez de $U$), P10 (Fan por post-proceso), y reescribir el párrafo de complejidad con la igualación paso a paso. Revisar totales del Fan citados (hoy ninguno). (Dani) | Notación sin repetir símbolos; ninguna cifra del frente cambia; el Fan se declara regla posterior al frente. |
| 11 | P1 | Memoria VII `resultados.tex:198-211,237`, VIII `conclusiones.tex:13` | P7 y P8; mover el párrafo de cobertura (`:209`) a su contexto; partir párrafos de más de 900 caracteres; verificar "38 ADR". (Dani) | Ningún párrafo con más de 5 ideas; conteo de ADR verificado contra la carpeta de ADR. |
| 12 | P1 | `bib/tukit.bib` y citas | Agregar Hart 2006 (RTLX) y IEEE 29119-3 sólo con datos verificados; citar Nielsen 1994 y Bangor 2008 donde se usan n y umbral 68; reemplazar claves `noauthor_*` por el autor institucional. (Gabriel) | `bibtex` sin avisos; cada cita sale de un documento real; no se inventa ningún dato. |
| 13 | P1 | Memoria, tabla de cumplimiento `conclusiones.tex:56-58` | Resolver "Ver Sec." de OE4 y OE5 con un estado y el criterio. (Dani) | Cada OE con estado y evidencia; coincide con OE5 (tarea 1). |
| 14 | P2 | Resumen/Abstract | Añadir palabras clave y 2-3 cifras de resultados; quitar rayas largas del abstract en inglés. (Dani) | Resumen y abstract dicen lo mismo; cifras = HECHOS. |
| 15 | P2 | Memoria V, VI, VII, diagramas | Dibujar los diagramas de la sección 5 (TikZ como `c4-contenedores.tex`). (Gabriel + María Paula) | Cada figura con leyenda, etiqueta, referencia en el texto y fuente (código o ADR); caben en el presupuesto de páginas o van al anexo. |
| 16 | P2 | Memoria completa | Pasada de estilo: "En esta sección ..." en las subsecciones de Resultados, bajar el uso de "de modo que" (37), humanizer al final. Revisar el presupuesto de 60 páginas de cuerpo tras todo lo anterior (hoy conclusiones llegan a la p. 56-57). (Dani) | Cuerpo <=60 páginas; `main.log` sin referencias indefinidas; 0 marcas `\pendienteEvidencia` sin justificar. |
