# Trabajos de grado Javeriana: lecciones de escritura para una memoria de 60 páginas

Fecha de la búsqueda: 2026-11-06.

## Resultado principal: no hay mención verificable

No encontré ningún trabajo de Ingeniería de Sistemas ni de la Maestría en Ingeniería de Sistemas y Computación cuya mención (laureada, meritoria, mención de honor) se pueda comprobar. Por eso los tres trabajos de abajo se analizan solo como ejemplos de estructura y redacción, sin atribuirles ningún reconocimiento.

Cómo se buscó:

- `repository.javeriana.edu.co` es una aplicación Angular y su ruta `/server/api` devuelve HTML. La API REST real está en `https://apidspace.javeriana.edu.co/server/api/discover/search/objects`.
- Se consultó por `laureada`, `meritoria`, `mención de honor` y `mención honorífica`. Las coincidencias son casi todas de Arquitectura, Diseño Industrial y otras facultades. Los dos hits de ingeniería (10554/1385 y 10554/56302) son de Ingeniería Electrónica y no entran en el alcance.
- Se listaron los 498 registros del programa "Ingeniería de Sistemas" y los 131 de la "Maestría en Ingeniería de Sistemas y Computación" (campo `dc.publisher.program`). Ninguno trae la mención en sus metadatos.
- Se descargaron 25 PDF de trabajos sobre recomendación, optimización, documentos y usuarios, y se buscó `laureada|meritoria|mención de honor` en el texto de cada uno. Cero coincidencias.
- No se probó Google Scholar ni las páginas del departamento. WebSearch no está disponible en este entorno. La mención suele constar en el acta de grado o en un listado de la facultad, no en el PDF, así que su ausencia en el repositorio no prueba que estos trabajos no la tengan.
- Para confirmar una mención hay que pedir a la secretaría del departamento el listado de trabajos laureados o meritorios.

## Trabajos analizados

Los PDF están en `/tmp/javeriana/pdf/`. Las páginas citadas son las impresas en el pie de cada documento.

| Trabajo | Autor | Año | URL | Mención verificada |
|---|---|---|---|---|
| RMFAR: modelo analítico de recomendación para la reducción y mitigación de riesgos de hurto | Montaña Granados, Juan Camilo (Maestría en Ing. de Sistemas y Computación) | 2021 (inferido del código 211002 y de las referencias; el metadato de fecha viene vacío) | http://hdl.handle.net/10554/54928 | No |
| RunayaySoft: sistema de recomendación de actividades de enriquecimiento | González Vargas, Juan Camilo (Maestría en Ing. de Sistemas y Computación) | 2016 | http://hdl.handle.net/10554/19633 | No |
| UAQUE: sistema de recomendación a partir del perfil grupal | Angarita Torres, Tibaquira Galindo, Salgado Tello, Ortegon Parra (Ing. de Sistemas) | 2021 | http://hdl.handle.net/10554/58350 | No |

## 1. RMFAR (maestría, la más cercana a una memoria de 60 páginas)

Extensión: 76 páginas del PDF, 65 de cuerpo hasta las conclusiones. Reparto aproximado de las páginas impresas:

| Parte | Páginas | Tamaño |
|---|---|---|
| Introducción | 12 | 1 |
| 1. Descripción general (problemática, oportunidad) | 13 a 15 | 3 |
| 2. Descripción del proyecto (objetivos, fases) | 16 a 18 | 3 |
| 3. Marco teórico y estado del arte | 19 a 37 | 19 |
| 4. Caracterización del caso de estudio | 38 a 40 | 3 |
| 5. Modelo RMFAR (metodología, diseño, experimentos) | 41 a 58 | 18 |
| 6. Evaluación y resultados (prototipo, validación) | 59 a 64 | 6 |
| 7. Conclusiones | 65 a 66 | 2 |
| 8. Anexos (tabla de índice) | 67 | 1 |

Lección de proporción: el marco teórico pesa lo mismo que el diseño del modelo. En 60 páginas convendría recortarlo a unas 8 y dejar el resto al diseño y a los resultados.

**Apertura de capítulos.** La introducción anuncia todos los capítulos en un párrafo: "El presente documento esté compuesto por 8 capítulos, en el primer capítulo se expone la descripción del proyecto…" (p. 12). Cada capítulo empieza con una frase que lo ata a una fase: "Este capítulo implementa la primera fase de desarrollo propuesta en el numeral 2.3.1…" (p. 19) y "En este capítulo se implementa la última fase de desarrollo propuesta, asociada a la evaluación del modelo…" (p. 59). Los conectores son ordinales ("En el segundo capítulo… En el tercero…") y remisiones a números de sección y de anexo.

**Metodología por objetivo.** Hay cuatro objetivos específicos (p. 16) y cuatro fases, una por objetivo: "la metodología, se dividirá en cuatro fases (ver Figura 1), cada una de ellas asociada al cumplimiento de cada uno de los objetivos específicos" (p. 16). Las fases son análisis de la problemática, exploración analítica, modelo de recomendaciones y evaluación (índice, 2.3.1 a 2.3.4). Los capítulos 3, 5 y 6 siguen esa misma secuencia. El detalle pesado va a anexos A a I, enumerados en una tabla de una página (p. 67).

**Resultados.** Se comparan dos modelos en tablas numeradas: "el mejor accuracy (0.5735) para el modelo de 70% de los datos para entrenamiento y 30% para pruebas (ver Tabla 12)" frente a "el mejor accuracy (0.55) para el modelo RMFAR" (sección 5.2.5, hacia p. 56 a 58). Antes se definió el plan de prueba (70/30, 80/20, ajuste de hiperparámetros, matriz de confusión; sección 5.1.4, p. 49 a 50) y se muestran curvas ROC. El prototipo se describe en dos páginas con arquitectura (SPA en S3, API en Flask sobre EC2) y figuras (p. 59 a 60). La validación con usuarios dedica una página al instrumento: 4 expertos y 15 ciudadanos, cuestionario TAM con escala Likert de 1 a 5 (Tabla 13) y un video previo; el detalle queda en el anexo H (p. 62 a 63).

**Conclusiones.** Se organizan por tópico, no por objetivo: "Respecto a la problemática", "Respecto al modelo de recomendaciones", "Respecto a la validación", "Trabajos futuros" (p. 65 a 66). Dice sin rodeos que el resultado es modesto: "A pesar de que el accuracy no es tan alto trae como consecuencia que las reco-mendaciones sean buenas" (p. 65). Cierra con cuatro mejoras concretas y accionables. Falta el cruce explícito objetivo por objetivo.

**Amenazas y limitaciones.** No tiene sección de amenazas a la validez. Las limitaciones están dentro de las conclusiones y ocupan unas 6 a 8 líneas: "de tratarse de un prototipo funcional pudo afectar la actitud hacia el uso" (p. 66) y "Podría realizarse una validación mucho más completa utilizando una metodología más robusta que TAM" (p. 66).

## 2. RunayaySoft (maestría)

Extensión: 95 páginas del PDF, unas 90 de cuerpo. Capítulos: introducción (13), 1. Descripción general (15), 2. Descripción del proyecto (18), 3. Estado del arte (22 a 36), 4. Contribuciones (37 a 85, casi la mitad del documento), 5. Conclusiones y perspectivas (86 a 90). Es un modelo de lo que no conviene copiar con 60 páginas.

**Metodología por objetivo.** Cinco objetivos específicos y cinco fases con el mismo orden (2.3.1 a 2.3.5: identificación de características, modelo de adaptación, métodos de selección, implementación, validación; p. 19 a 22). El capítulo de contribuciones sigue ese orden: diagnóstico (4.1), modelo de adaptación (4.2), sistema (4.3), experimento (4.4) y post-mortem (4.5).

**Resultados.** La sección 4.4 se divide en pruebas de estrés (p. 70), satisfacción de 214 estudiantes (p. 71 a 75), validación del experto (p. 75) y pruebas con y sin adaptación (p. 76 a 83). La comparación con y sin el componente propio ocupa unas 8 páginas y es la parte más útil para copiar como patrón.

**Conclusiones y limitaciones.** Se introducen en una línea: "En esta sección se describen las conclusiones, los trabajos futuros e impactos a nivel tecnológico, social, ético y ambiental" (p. 86). Los impactos se agrupan en "Científicos y tecnológicos", "Social", "Éticos y ambientales" (p. 87). Tiene una sección de post-mortem (4.5, p. 84 a 86) con limitaciones dichas de forma directa: "Por falta de tiempo, no se obtuvo una lista de actividades que desarrollan en las instituciones educativas, por lo que no se alcanzó a validar las recomendaciones" (p. 85). También recoge la crítica de los usuarios: los test eran "tediosos" por la cantidad de preguntas (p. 86). Es una sección de limitaciones honesta de unas 2 páginas, sin llamarse amenazas a la validez.

## 3. UAQUE (pregrado)

Extensión: unas 81 páginas de cuerpo más 7 de referencias. Reparto según el índice: introducción (11), descripción general (12 a 21), Fase I investigación (22 a 35), Fase II analítica CRISP-DM (36 a 59), Fase III implementación (60 a 68), Fase IV validación (69 a 75), conclusiones (76 a 81). Los capítulos se nombran por fase, no por tema.

**Apertura.** Cada capítulo empieza diciendo qué hará: "En este capítulo se realiza la descripción del trabajo de grado UAQUE en cuanto a la problemática, el objetivo general, los objetivos específicos…" (p. 12). La introducción presenta cada fase con una frase y cierra con "Por último, el documento expone las conclusiones del proceso, así como el trabajo futuro…".

**Resultados.** La validación se hace desde tres perspectivas (expertos de Smart-UJ, funcionarios de la biblioteca y estudiantes) con encuesta y sesiones grabadas (6.1). Compara dos algoritmos con figuras y da una cifra: "las recomendaciones generadas a través del sistema de suma ponderada tienen una calidad percibida entre 15% y 20% mayor comparadas con las generadas por el algoritmo SAR" (hacia p. 73 a 74). Los objetivos de negocio se puntúan de 1 a 5 y se comenta cuáles cumplen del todo y cuáles tienen margen (6.1.2, p. 72 a 74).

**Conclusiones.** Hay una sección de impacto por audiencia (7.1) y otra de conclusiones por objetivo. Esta última es la más aprovechable: abre con el objetivo general ("podemos concluir que fue alcanzado con éxito, debido a que…") y sigue con "Con respecto los objetivos específicos… también fueron alcanzados con éxito, debido a que: se logró…; se construyó…; se desarrolló…; y se validó…" (7.2, hacia p. 78 a 81). La prueba de carga reporta hardware y límites: 5000 usuarios concurrentes, 10 nuevos por segundo, equipo con 8 GB de RAM, "probablemente diferentes a las del servidor de producción" (7.3). Esa frase hace de limitación en una línea.

**Amenazas y limitaciones.** Sin sección propia de amenazas a la validez. El texto extraído de las conclusiones tiene párrafos repetidos (7.3 y 7.4 casi idénticos), un defecto de edición que conviene evitar.

## Lecciones para una memoria de 60 páginas

1. Asignar una fase, un capítulo o sección y un resultado a cada objetivo específico, y decirlo en el capítulo 2 con una tabla o figura. Los tres trabajos lo hacen y facilita escribir las conclusiones.
2. Abrir cada capítulo con una frase que diga qué fase u objetivo cubre ("Este capítulo implementa la primera fase…", p. 19 de RMFAR). Cerrar remitiendo al capítulo siguiente o al anexo.
3. Limitar el marco teórico. RMFAR gasta 19 de 66 páginas en él; con 60 páginas, 6 a 8 bastan si lo demás se apoya en referencias y anexos.
4. Resultados con una tabla comparativa contra un baseline (RMFAR contra árbol de decisión, UAQUE contra SAR, RunayaySoft con y sin adaptación), la definición del plan de prueba antes y una cifra citable. Declarar el resultado modesto con franqueza, como hace RMFAR en la p. 65.
5. Evaluación con usuarios en una página: quién (n expertos, n usuarios), qué instrumento (TAM, Likert 1 a 5), qué material vieron (video, prototipo) y un gráfico de promedios. Derivar los datos crudos a un anexo.
6. Conclusiones por objetivo, con el patrón de UAQUE ("fue alcanzado con éxito, debido a que…"), más un bloque corto de trabajo futuro con ideas concretas como las de RMFAR (p. 66).
7. Limitaciones: ninguno de los tres usa el nombre "amenazas a la validez". Todos las dejan en 1 a 2 páginas dentro de conclusiones o post-mortem. Una subsección explícita de media página (tamaño de muestra, prototipo en lugar de producción, sesgo de evaluadores, datos disponibles) sería más clara que lo que hacen estos trabajos.
8. Revisar que no haya párrafos duplicados ni errores de numeración de figuras (RMFAR numera "Figura 20" y "Figura 22" para el mismo diagrama en la p. 59 a 60; UAQUE repite la sección de pruebas).
