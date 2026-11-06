# Estado del arte academico (2026-11-06)

Fuente: PDF completo de cada trabajo, bajado con curl y convertido con pdftotext; leido por partes (resumen, metodo, experimentos, discusion, limitaciones y conclusiones). Metadatos verificados contra export.arxiv.org. Entradas en `bib_nuevas.bib`; tabla en `tabla-academica.tex`.

Lectura completa (7): R1 HiMARS, R3 Block-SCL, R4 OCR or Not, R5 RASG, R6 DART, mas la tesis de maestria de Abbas (arXiv 2504.13909, Kangwon) y la tesis de pregrado de Dinesh (arXiv 1802.06892, BITS Pilani, supervisada por Beel; se leyeron indice, metodologia de baselines, resultados, resumen). R7 JobSphere tambien se leyo completo y se descarta como cita: no declara n del SUS de la linea base, la tabla 3 dice N=30 en el estudio de usuarios pero el abstract y la conclusion mezclan cifras (SUS 78,5 vs 52,3; "50 % mejor"), hay cifras inconsistentes (NDCG@3 0,78 en la conclusion, 85 % de extraccion contra F1 0,89) y no tiene seccion de limitaciones. R2 (COMO-MAB) no se abrio y no se cita.

## Por trabajo

### R1. Lotfian y Kabgani, HiMARS (arXiv 2604.07572, abr 2026)
- Problema: listas top-s que equilibren exactitud y diversidad (objetivos en conflicto) en recomendadores.
- Metodo: tres etapas (candidatos top-k=100 con filtrado colaborativo por items; optimizacion biobjetivo a top-s=10 con cuatro hibridos HAN/HANI de NSGA-II, AMOSA y NNIA; seleccion del punto del frente mas cercano al ideal por distancia euclidiana).
- Datos: MovieLens (6.040 usuarios, 3.706 peliculas) y ModCloth (44.784 usuarios, 1.020 items); 10 usuarios por conjunto (3411-3420 siguiendo estudios previos; 620-629 al azar); 80/20 entrenamiento/prueba.
- Metricas: exactitud, diversidad y novedad; calidad del frente con espaciamiento (SM), distancia media al ideal (MID), diversificacion (DM) y dispersion (SNS); ranking de algoritmos con TOPSIS con pesos AHP.
- Lineas base: ICF, NNIA, AMOSA, NSGA-II. 20 corridas; parametros por ensayo y error; Python 3.11, laptop i7.
- Estadistica: solo medias, min y max por usuario; sin pruebas ni IC.
- Limitaciones declaradas: un usuario por corrida, escalabilidad, objetivos adicionales, ajuste adaptativo de parametros. El propio paper advierte que DM y MID se pueden "ganar" con frentes de dos puntos o agrupados en el centro, y por eso pondera varios indicadores.
- Que aprende Tukit: (1) agregar a hipervolumen un indicador de forma del frente (espaciamiento) y mostrar por que uno solo engana; se calcula sin datos nuevos desde las salidas del optimizador; (2) la regla de seleccion "punto mas cercano al ideal" es un respaldo defendible para presentar UNA opcion por defecto; (3) declarar el numero de usuarios/listas evaluados y como se escogieron (Tukit: 40 listas, 32 con NSGA-II); (4) Tukit supera su rigor en lo que ellos no tienen: frente exacto por enumeracion, hipervolumen relativo y Wilcoxon. No hay precio ni cobertura en sus objetivos, por eso no es comparable de forma directa.

### R3. Almagro et al., Block-SCL (arXiv 2207.02008, jul 2022)
- Problema: decidir si dos ofertas de distintos comercios son el mismo producto.
- Metodo: preentrenamiento con aprendizaje contrastivo supervisado donde los negativos duros salen del bloqueo (candidatos del mismo bloque), luego clasificador lineal sobre el encoder congelado; solo titulos como entrada, BERT mediano (35,3 M parametros).
- Datos: seis conjuntos publicos (Abt-Buy, Amazon-Google, WDC Computers en cuatro tamanos); estadisticas de bloqueo en tabla (tamano medio del bloque, positivos y negativos por bloque).
- Metricas: F1; tiempo de entrenamiento (4x y 2x mas rapido).
- Lineas base: Ditto, DeepMatcher, JointBERT, Vanilla-SCL con y sin trucos (reproducido por ellos con el mismo backbone para comparar justo), "Fine-tuned LM".
- Estadistica: ablacion en WDC-medium con promedio y desviacion de 3 semillas (p. ej. sin bloqueo 93,15 +- 0,52; con 2 positivos y 16 negativos 96,53 +- 0,15).
- Limitaciones: no pudieron correr RoBERTa-base por computo; no analizaron a fondo el efecto del numero de bloques ni positivos/negativos; no hay umbral de decision explicito ni IC.
- Que aprende Tukit: (1) reproducir la linea base propia con las mismas condiciones y decirlo ("w/o tricks"), no solo citar cifras de otros; (2) tabla de estadisticas del bloqueo/candidatos por dataset; Tukit puede dar candidatos medios por renglon del OE1; (3) ablacion que varia UN parametro (negativos 1 a 16) con desviacion entre semillas; Tukit ya tiene la comparacion lexico/semantico/hibrido, falta mostrar variacion entre corridas del umbral si aplica; (4) declarar con franqueza lo que quedo sin probar.

### R4. Shen et al., OCR or Not? (arXiv 2603.02789, mar 2026; ya en tukit.bib como shen_ocr_2026)
- Problema: si un modelo multimodal puede extraer campos y renglones de documentos de negocio sin OCR previo.
- Metodo: tres entradas (solo imagen, solo OCR, imagen mas OCR); salida JSON con esquema de cabecera y lista de renglones; F1 sobre pares clave-valor; marco de analisis jerarquico de errores con LLM (manejador, razonamiento, atribucion con agrupamiento por embeddings BERT).
- Datos: unos 1.000 documentos de dos conjuntos privados (C1 cadena de suministro, C2 finanzas), multilingues.
- Lineas base: 11 modelos (Llama 4, Pixtral, Nova Pro, GPT-4o, Claude, Gemini). Gemini 1.5 Pro imagen sola 76,8 F1 medio contra 74,1 solo OCR; con prompt optimizado 78,9.
- Estadistica: medias de F1; ninguna prueba ni IC; costo y latencia por pagina estimados (Tabla 2).
- Limitaciones declaradas: no validaron few-shot sistematicamente; sin razonamiento en cadena; el analizador de errores podria mejorar con un modelo de razonamiento.
- Que aprende Tukit: (1) categorizar los errores de percepcion en 3 o 4 clases (mala lectura, ambiguedad del esquema, formato) con las salidas ya guardadas, y mostrarlo en una figura de barras; (2) reportar costo y latencia por pagina de la extraccion; (3) la ablacion imagen/OCR/ambos justifica la decision de leer imagen directa; (4) Tukit debe decir que su oro viene de un motor y que ellos tienen anotacion manual: su limitacion es mas fuerte y se declara una vez en Amenazas.

### R5. Cesista et al., RASG (arXiv 2405.20245, may 2024; IEEE MIPR 2024)
- Problema: extraccion de informacion clave y de renglones (line items) de facturas.
- Metodo: LLM con recuperacion de un ejemplo (1-shot por hash de ondas de la pagina), ajuste fino, generacion estructurada con esquema y prompt que conserva el diseno de la pagina; metrica GLIRM (F1 por celda sobre subsecuencias de renglones, no pide el mismo orden de columnas, penaliza celdas inventadas y faltantes, con parametro beta para pesar recall).
- Datos: DocILE. Linea base: LayoutLMv3 y RoBERTa con y sin datos sinteticos, DETR.
- Resultados: GPT-3.5 + RASG 75,40 % KIE y 79,81 % LIR contra 26,80 % y 23,03 % sin RASG; ablacion de 2^4 = 16 combinaciones con modelo lineal para la contribucion de cada componente.
- Estadistica: sin IC ni pruebas. Limitaciones: recuperacion de un solo ejemplo por la ventana de contexto; una sola epoca de ajuste.
- Que aprende Tukit: (1) definir la metrica de percepcion por renglon con atributos explicitos (cada renglon cuenta una vez, inventados = falsos positivos, faltantes = falsos negativos); (2) justificar un F-beta con mas peso al recall porque la revision humana prefiere revisar sobrantes que buscar faltantes, argumento que encaja con la cola de revision de Tukit; (3) tabla de ablacion por componente.

### R6. Kian et al., DART (arXiv 2609.12349, sep 2026)
- Problema: extender un robot social de bajo costo con aplicacion web y nube; evaluar la arquitectura.
- Metodo: arquitectura con tres componentes (robot, aplicacion web, servicios en nube con MQTT), cinco metas de diseno explicitas, modelo de desarrollo de actividades como modulos, seguridad y privacidad; evaluacion en 3 estudios (diseno participativo, laboratorio con 103, casa con 4 durante 6 semanas).
- Metricas: SUS (media 78,89, DE 13,40, IC 95 % [76,22; 81,56], n=99 completos; benchmark de adjetivos de Bangor); estres, ansiedad y afecto con ANOVA de medidas repetidas, Greenhouse-Geisser, t pareadas con Holm y d de Cohen. Casa: SUS 85,0, 87,5, 90,0 (n=3 de 4), solo descriptivo.
- Estadistica: la mas completa de las leidas. Sin grupo de control.
- Limitaciones declaradas en parrafo propio: sin control en laboratorio, muestra pequena y homogenea en casa; pide estudios controlados futuros; dicen que no buscan demostrar eficacia clinica sino usabilidad y factibilidad.
- Que aprende Tukit: (1) el SUS con n pequeno se reporta descriptivo y con IC, y se interpreta con el benchmark de Bangor; Tukit ya lo hace con n=6 (90 [82-98]); (2) las cinco metas de diseno ligadas a la evaluacion es un buen patron para el capitulo de diseno (meta, requisito, evidencia); (3) frase de alcance: "no busca demostrar X sino usabilidad y factibilidad", pero en estilo llano y una sola vez; (4) la separacion "se declara una limitacion y se dice que estudio futuro la cerraria".

### Tesis de maestria. Abbas et al., Mobile-Driven Incentive Based Exercise (arXiv 2504.13909; tesis de Master of Engineering, Kangwon National University, 2025)
Se leyeron indice, pregunta de investigacion, alcance, estructura, evaluacion del algoritmo, evaluacion de usabilidad y limitaciones.
- Problema: app movil con recomendacion de ejercicio por incentivos para diabetes tipo 2.
- Estructura: introduccion con pregunta, alcance, significancia y estructura de la tesis; trabajo relacionado; metodologia (entradas, flujo, algoritmo, escenarios de uso); resultados por tres fases (analisis, diseno e implementacion, evaluacion); conclusion con una subseccion "Limitacion y trabajo futuro" de dos parrafos.
- Evaluacion: algoritmo contra guias clinicas por un solo experto, con formulas de proficiencia (90 %) y eficiencia (92 %) y puntaje +1/0/-1; heuristica de Bertini con 3 expertos; UEQ con 35 personas (25 expertos que la usaron una semana y 10 pacientes por 21 dias), comparado con un benchmark de 452 productos.
- Limitaciones declaradas: n=10 pacientes, 21 dias, dificultad de monitoreo; ademas atribuyen el puntaje bajo de seguridad al prototipo.
- Que aprende Tukit: es un precedente de que una tesis de maestria con n=10 y un solo evaluador experto se acepta si lo declara; la memoria de Tukit ya supera: IC, kappa, Wilcoxon, frente exacto. Copiar de ellos: (1) un parrafo de "estructura del documento" ya existe en Tukit; (2) usar un instrumento con benchmark publicado (SUS/Bangor, UEQ) y decir en que rango cae; (3) formula explicita de la metrica de acuerdo con el experto, como su proficiencia/eficiencia; Tukit ya reporta kappa.
- Advertencia: es tesis de ingenieria, no de sistemas de recomendacion; su rigor estadistico es menor que el de Tukit. Sirve como referencia de formato y de franqueza en limitaciones, no como linea base.

### Tesis de pregrado. Dinesh, Real World Evaluation of Approaches to Research Paper Recommendation (arXiv 1802.06892, BITS Pilani/Trinity College Dublin, 2017)
No es de maestria; se lee y se cita solo si se aclara. Indice completo, capitulo 3 (que es una buena linea base) y 5 (resultados) y resumen.
- Contribucion: criterios para una linea base (facil de reproducir, relevante a la tarea, independiente del sistema) y cinco baselines (aleatorio, Lucene MoreLikeThis, estereotipo, mas popular, frases clave) en la plataforma Mr. DLib; 3,6 millones de peticiones, 7.700 clics, CTR 0,21 %.
- Estadistica: CTR por enfoque y por idioma; admite que solo en algunos cortes se puede decir "con significancia estadistica", y que el resultado depende del tipo de usuario.
- Que aprende Tukit: definir criterios para escoger las lineas base (Tukit usa reglas, Gemini sin reglas, enumeracion exacta) y listarlos; un aleatorio y un "mas barato" como piso.

## Lecciones para la memoria

| # | Cambio concreto | Fuente | La memoria ya cumple? |
|---|---|---|---|
| 1 | Trabajo relacionado con tabla de trabajos academicos (problema, metodo y evaluacion, limitacion, que toma Tukit), junto a la tabla de productos | todos | Parcial: hay Tabla 5 de soluciones comerciales y la tabla de conceptos (antecedentes); falta la academica. Entrega: tabla-academica.tex |
| 2 | Reportar el frente de Pareto con mas de un indicador: hipervolumen mas espaciamiento (y distancia al ideal) y explicar por que uno solo engana | R1 | Parcial: hay hipervolumen 0,9969 y enumeracion exacta; falta espaciamiento. Se calcula con las salidas guardadas |
| 3 | Elegir y justificar una opcion por defecto del frente (punto mas cercano al ideal) | R1 | Revisar: depende de como el sistema presenta las alternativas; si ya hay regla, citarla |
| 4 | Metrica de percepcion por renglon con definicion explicita (falsos positivos = renglones inventados, falsos negativos = faltantes) y F-beta con recall mayor por la revision humana | R5 | Parcial: hay F1 micro; agregar el argumento de recall y la definicion |
| 5 | Analisis de errores de percepcion por categoria (lectura, esquema, formato) con las salidas existentes, mas costo y latencia por pagina | R4 | No |
| 6 | Reproducir la linea base propia en las mismas condiciones y decirlo; ablacion que varia un parametro, con desviacion entre semillas | R3 | Parcial: hay ablaciones; revisar si todas dan variacion entre corridas |
| 7 | SUS con IC, descriptivo con n pequeno, interpretado con el benchmark de adjetivos de Bangor | R6, Abbas | Si (n=6, 90 [82-98]); agregar la lectura con Bangor si falta y citar |
| 8 | Declarar limitaciones en un solo lugar, sin tono de faltante, y senalar que estudio las cerraria | R6, Abbas | Si segun la decision de la autora: Amenazas a la validez y columna Alcance |

## Notas de verificacion
- Todo numero de esta nota esta en el PDF leido. Lo que dice "no consta" no aparece en el texto.
- Hallazgo menor sobre el benchmark previo: R7 aparece ahi como "SUS 78,5, 50 % mejor"; el PDF sustenta SUS 78,5 contra 52,3 de la plataforma base (N=30 en el estudio de usuarios), pero con inconsistencias internas; no se recomienda citarlo.
- Una tesis de maestria sobre un recomendador con arquitectura y SUS no se hallo en arXiv; la mas cercana es la de Abbas (ingenieria, UEQ). Repositorios universitarios no se consultaron.
