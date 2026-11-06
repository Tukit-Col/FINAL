# Diff de redacción: versión del equipo (zip del 3-nov) frente a la memoria actual (6-nov)

## De dónde sale cada versión
- **El zip del equipo** parte de la versión de Dani y Juan del 1-nov (commit `757764f`, "corregida hasta requisitos"). La mayoría de sus archivos son del 3-nov.
- **La memoria actual** (`validacion/oe5`, `fd4f7dd`) también parte de esa base. Después pasó por la integración del 2-nov, las revisiones R1-R4, la reestructura del 5-nov y el council del 6-nov.
- Ambas ramas se separaron el 1-nov y nunca se volvieron a unir. Por eso nada de lo que el equipo escribió después del 1-nov llegó a la versión actual.

## Cuánto cambió el equipo sobre la base del 1-nov
Palabras de párrafos nuevos o editados por el equipo que no están en la versión actual:

| Archivo | Palabras | Qué es |
|---|---|---|
| desarrolloSolucion | ~8.560 | Capítulo reescrito como un recorrido por pantallas: registro, lista, procesamiento, kits, asistente, pago, seguimiento, privacidad, revisión, catálogo, logística, métricas y comparación de alternativas. Tiene 40 figuras, tablas y algoritmos. |
| diseñoSolucion | ~3.790 | Capítulo nuevo: modelo de negocio (Canvas), alternativas, alto nivel, vista lógica, tiempo de ejecución, modelo de datos (ER por servicio) y vista física. |
| analisisProblema | ~1.950 | Mapa de empatía y arquetipos, restricciones en cinco tipos y casos de uso con diagrama. |
| descripcionGeneral | ~990 | Ediciones de redacción: Ley 1269, asistente, exportar y suprimir datos, kits. |
| resultados | ~520 | Validación financiera a tres años. |
| abstract, contexto, introducción, conclusiones | ~840 | Asistente y datos en el resumen, Porter, alcance en la introducción y lanzamiento comercial. |

En total son unas 16.600 palabras, entre 35 y 40 páginas. El cuerpo actual ya está en 60 de 60, así que no cabe todo. Hay que elegir.

## Ya integrado en la versión actual (no se pierde)
- 65 encuestas recibidas y 60 analizables.
- Hasta cuatro kits.
- La puerta de enlace.
- 10 de los párrafos de desarrollo y 1 de análisis aparecen casi iguales (similitud ≥ 0,9).

## Cómo leer el detalle
- **Editado por el equipo:** el párrafo de la base del 1-nov con sus cambios. **Negrita** es lo que agregaron y ~~tachado~~ es lo que quitaron.
- **Nuevo del equipo:** un párrafo que no existía en la base.
- *Lo más parecido en la versión actual:* aparece cuando hay un párrafo actual que cubre lo mismo con otra redacción. Sirve para decidir cuál queda.

## introduccion.tex  (2 párrafos y 0 figuras/tablas del equipo que no están en la versión actual)

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Frente a este panorama, el presente proyecto describe a Tukit como una plataforma que le permite al acudiente conseguir la lista de útiles completa. Funciona como un sistema de recomendación multiobjetivo con un modelo B2B2C, en el que el colegio aporta la lista oficial y la familia hace la compra. El acudiente elige el colegio y el grado de cada hijo, o sube su propia lista en imagen, PDF o texto libre, e indica su presupuesto y sus preferencias. A cambio recibe hasta cuatro kits completos (Ahorrador, Premium, Fan y A tu ~~Medida) y~~ **Medida),** puede cambiar cualquier producto **o pedirle cambios al asistente del kit** antes de pagar en ~~línea.~~ **línea, y después sigue su pedido y gestiona sus datos personales desde la misma aplicación.** Para llegar a esos kits, el sistema recorre tres etapas.

  - *Lo más parecido en la versión actual* (introduccion.tex, similitud 0.81): Frente a este panorama, el proyecto construyó Tukit, un sistema de recomendación multiobjetivo con un modelo B2B2C, en el que el colegio aporta la lista oficial y la familia hace la compra. El acudiente elige el colegio y el grado de cada hijo, o sube su propia lista en imagen, PDF o texto libre, e indica su presupuesto y sus preferencias. A cambio recibe hasta cuatro kits completos (Ahorrador, Pr

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Esta estrategia toma de un esquema RAG la indexación del catálogo y la recuperación de los productos, pero en lugar de que un modelo de lenguaje redacte la respuesta, los kits los construye el optimizador y el equipo de Tukit los revisa antes de publicarlos (human-in-the-loop). Todo corre sobre una arquitectura de ~~seis~~ **cinco** servicios **de dominio y una puerta de enlace,** con cinco bases de datos, elegida entre tres alternativas con el método ATAM [cita].

  - *Lo más parecido en la versión actual* (introduccion.tex, similitud 0.53): Para llegar a los kits, la estrategia toma de la generación aumentada por recuperación (RAG) [cita] la indexación y la recuperación de productos. Los kits los construye el optimizador, no un modelo de lenguaje, y el equipo de Tukit los revisa antes de publicarlos (human-in-the-loop, es decir, con una persona en el circuito).


## covers/abstract_resumen.tex  (2 párrafos y 0 figuras/tablas del equipo que no están en la versión actual)

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Colombian households often receive extensive and ambiguous school supply lists, forcing them to visit multiple stores to fulfill them—frequently without finding a single, comprehensive kit that meets their specific needs. Tukit processes these lists—whether provided as images, PDFs, or free-text—by comparing each item against a canonical catalog, utilizing both lexical and semantic similarity. It then assembles **up to four** optimized kits using a multi-objective approach based on the NSGA-II algorithm, balancing factors such as cost, brand fidelity, product availability, and thematic preferences. **Parents can adjust each kit directly or through a kit assistant that proposes changes requested in natural language, and they can view, export, or delete their personal data from the same application.** The project followed a hybrid, encompassing methodology that integrates SCRUM, Design Thinking, RUP, and CRISP-DM, in alignment with IEEE standards 830, 1016, and 1058. ~~\begin{center} {RESUMEN} \end{center}~~

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Los hogares colombianos reciben listas escolares extensas y ambiguas, y deben recorrer varios comercios para completarlas sin encontrar un kit que se ajuste a sus necesidades. Tukit lee la lista en imagen, PDF o texto libre, compara cada renglón con un catálogo canónico combinando el parecido léxico y el semántico. Posteriormente, arma **hasta cuatro** kits con una optimización multiobjetivo basada en NSGA-II que equilibra costo, fidelidad de marca, disponibilidad y preferencias temáticas. **El acudiente ajusta cada kit de forma directa o con un asistente que propone los cambios que pide en lenguaje natural, y desde la misma aplicación consulta, exporta o suprime sus datos personales.** El trabajo siguió una metodología híbrida contenedora que combina SCRUM, Design Thinking, RUP y CRISP-DM con los estándares IEEE 830, 1016 y 1058.


## descripcionGeneral.tex  (6 párrafos y 0 figuras/tablas del equipo que no están en la versión actual)

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > El comercio electrónico en Colombia ha mantenido un crecimiento sostenido. En 2025, las ventas en línea alcanzaron COP 105 billones, un 5,9% más que el año anterior, y la categoría de libros y papelería representó el 0,81% de las transacciones [cita]. No obstante, ese crecimiento no ha transformado la manera en que se adquieren los útiles escolares, una tarea que se repite cada año y que, solo en Bogotá, involucra a más de 1.171.390 estudiantes matriculados [cita]. De acuerdo con las encuestas de temporada escolar de FENALCO, el 35% de las familias destina entre \$300.000 y \$500.000 por niño [cita], y el 70% no planea la compra con anticipación. Apenas el 6% la realiza con meses de margen, mientras que el resto compra a medida que surgen las necesidades o pocas semanas o días antes del inicio de clases [cita]. A esta presión de tiempo se suma la de los precios, pues el 91% de los padres percibe un alza, y el precio continúa siendo el principal criterio de elección (33%), seguido de la calidad (23%) y, de ~~\subsubsection{Propuesta~~ de ~~Solución}~~ **forma creciente, del gusto de los niños (22%) [cita].**

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > En la plataforma intervienen tres ~~actores, cada uno con un canal propio.~~ **actores.** El ~~colegio, por medio~~ **colegio entrega al equipo** de ~~su administrador, entrega y publica~~ **Tukit** la lista oficial de cada grado. El equipo de Tukit opera desde una aplicación de administración, en la que revisa las listas antes de que lleguen a las familias, atiende la cola de renglones que el sistema no resolvió con certeza y valida o corrige cada uno de ellos. Por su parte, el acudiente accede mediante una aplicación web progresiva, en la que selecciona el colegio y el grado de cada hijo, o carga su propia lista en el formato que prefiera, e indica su presupuesto y sus preferencias. **En la misma aplicación sigue sus pedidos y sus casos, y consulta, exporta o suprime sus datos personales.**

  - *Lo más parecido en la versión actual* (descripcionGeneral.tex, similitud 0.48): De los actores del sistema (Capítulo IV), dos tuvieron un canal propio. El equipo de Tukit operó una aplicación de administración, en la que revisó las listas y atendió la cola de renglones dudosos. El acudiente accedió por una aplicación web progresiva, una página web que se instala y funciona como aplicación, seleccionó el colegio y el grado de cada hijo, o cargó su lista, e indicó presupuesto y

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Como resultado, el acudiente recibe ~~tres~~ **hasta cuatro** propuestas de kit para la lista completa. El kit Ahorrador corresponde a la opción de menor ~~costo;~~ **costo y** el Premium, a la de mejores ~~marcas; y el Fan, a la que incluye los personajes solicitados para cada hijo.~~ **marcas.** Cuando el acudiente **pide un personaje para alguno de sus hijos, recibe además el Fan, que lo incluye, y cuando elige el punto medio de gasto o** fija un ~~tope de gasto, recibe además~~ **tope,** el kit A tu Medida, que ofrece la mejor marca posible dentro de ese monto. Cada propuesta presenta los productos, las cantidades que deben comprarse según el empaque y el valor total. Finalmente, el acudiente puede reemplazar productos de manera individual, **descartar los que ya tiene, pedir cambios en lenguaje natural al asistente del kit,** elegir el kit de su preferencia y realizar el pago en línea.

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Los actores que lideran este segmento en Colombia trasladaron su modelo físico al canal digital sin modificarlo, de modo que publican un catálogo y delegan en el cliente la búsqueda, la comparación y la validación. Panamericana ofrece cotizaciones por categorías genéricas, sin relación con la lista de cada colegio [cita]; Primavera permite armar manualmente un carrito sobre su propio catálogo [cita]; MercadoLibre comercializa kits preconfigurados por terceros [cita], y Éxito ofrece kits por nivel escolar sin distinguir entre colegios ni optimizar varios criterios a la vez [cita]. En el ámbito internacional, Amazon School Lists permite que los docentes publiquen listas que los padres agregan al carrito [cita], pero no interpreta listas impresas o fotografiadas, no reconoce las variaciones del vocabulario local (esferos o lapiceros, marcadores o plumones) ni distingue entre presupuestos familiares. A ello se suma que la ~~Resolución 019805~~ **Ley 1269** de ~~2025 del Ministerio de Educación Nacional prohíbe~~ **2008 obliga** a los colegios **a entregar en la matrícula la lista completa de útiles y les prohíbe** exigir ~~marcas o proveedores específicos~~ **que los padres entreguen esos materiales al colegio** [cita], lo cual favorece que las familias comparen y elijan de manera informada. En consecuencia, se identifica la ausencia de un actor que transforme el modelo reactivo de compra en uno proactivo y asistido, y esta brecha constituye la oportunidad que motiva el presente proyecto.

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Presentar pocas alternativas ya armadas facilita la decisión, puesto que el exceso de opciones dificulta la elección y tiende a postergar la compra [cita], mientras que un sistema que le propone una selección reducida disminuye su esfuerzo y mejora la calidad de su decisión [cita]. Por esta razón, Tukit se concibe como un asistente que entrega kits completos entre los cuales el acudiente solo debe elegir. Esta forma de operar beneficia a cada uno de los actores. El acudiente evita recorrer varios establecimientos y puede ajustar la alternativa elegida antes de pagar; el colegio se asegura de que las familias compren a partir de la versión oficial de su ~~lista y puede orientarlas sin exigir marcas ni proveedores, conforme~~ **lista, la misma que la Ley 1269 de 2008 le obliga** a ~~lo dispuesto por~~ **entregar en** la ~~Resolución 019805 de 2025 del Ministerio de Educación Nacional~~ **matrícula** [cita]; y el equipo de Tukit concentra su revisión en los renglones que el sistema no resolvió con certeza, en lugar de revisar cada lista de forma manual. Esa revisión garantiza, a su vez, que la calidad de los kits no dependa únicamente de la automatización. Cuando el sistema no alcanza la certeza suficiente sobre un renglón, este se remite a una persona antes de que la lista llegue a las familias, siguiendo las pautas que recomiendan indicar con claridad lo que el sistema desconoce y facilitar la corrección de sus errores [cita].

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Las etapas de CRISP-DM se recorrieron en varias iteraciones. En la lectura de las listas, en la búsqueda contra el catálogo y en el optimizador, cada evaluación podía mostrar que un componente no alcanzaba el desempeño esperado. En esos casos el equipo volvía a preparar los datos o a ajustar el modelo, y repetía la evaluación. El Capítulo ~~V~~ describe estas iteraciones junto a cada ~~componente: qué~~ **componente, con lo que** se probó, ~~con qué datos, qué~~ **los datos usados, el** resultado **obtenido y el ajuste que** se ~~obtuvo y qué se cambió.~~ **hizo.** La última etapa de CRISP-DM, el despliegue, corresponde a la integración de estos componentes en el sistema construido. Su puesta en operación con colegios y familias se presenta entre los siguientes pasos, en ~~el Capítulo VII.~~ **la Sección .**


## contextoProyecto.tex  (2 párrafos y 1 figuras/tablas del equipo que no están en la versión actual)

- **Nuevo del equipo:**
  > Para dimensionar la competencia que enfrenta Tukit en el mercado colombiano se aplicó el modelo de las cinco fuerzas de Porter [cita], que evalúa la rivalidad entre los competidores existentes, la amenaza de nuevos competidores y de productos sustitutos, y el poder de negociación de proveedores y clientes. La Figura resume los factores identificados para cada fuerza y su intensidad.

- **Nuevo del equipo:**
  > Las fuerzas de mayor intensidad son el poder de negociación de los clientes y la amenaza de sustitutos, ya que los acudientes cuentan con múltiples alternativas de compra y un bajo costo de cambio. Por ello, la estrategia de Tukit se basa en la diferenciación frente a cadenas que compiten por precio con economías de escala. Su ventaja se apoya en dos activos difíciles de replicar en el corto plazo, las listas oficiales normalizadas por colegio y grado y el canal de confianza que construye con cada institución, respaldado por el 90% de los acudientes que confiaría más en la plataforma si el colegio la recomienda. La dependencia de los proveedores se mitiga con un catálogo que reúne ofertas de diez tiendas y con un modelo multimodal aislado detrás de un adaptador, que conserva las solicitudes para reintentarlas si el servicio falla.

- **Figuras y tablas nuevas:** Cinco fuerzas de Porter aplicadas a Tukit, con la intensidad de cada fuerza. Las cifras so


## analisisProblema.tex  (18 párrafos y 2 figuras/tablas del equipo que no están en la versión actual)

- **Nuevo del equipo:**
  > Del levantamiento surgieron tres arquetipos de comprador que dieron origen a los kits. El Ahorrador prioriza el precio total y el cumplimiento de la lista, el Fan busca que los útiles motiven al hijo sin un sobrecosto desproporcionado y el Premium antepone la calidad y la marca a cambio de no tener que buscar. Para comprender al acudiente, quien arma y paga el kit, los hallazgos se organizaron en el mapa de empatía de la Figura , basado en el modelo de Gray [cita], que reúne lo que piensa, oye, ve, dice y hace, sus esfuerzos y los resultados que espera.

- **Nuevo del equipo:**
  > El principal hallazgo es que el mayor obstáculo de la compra es la disponibilidad de los productos. El 43,3% de los acudientes señala como su mayor dificultad no encontrar un producto o encontrarlo agotado, frente al 16,7% que menciona el precio. Como la lista llega con más de un mes de anticipación, la dificultad se concentra en el esfuerzo de recorrer varios lugares, traducir cada renglón a un producto y confirmar que corresponde a lo que pide el colegio. El mapa muestra también que la confianza del acudiente crece con el respaldo de la institución y con un medio de pago conocido, y que el gusto del hijo ocupa el último lugar entre sus criterios, aunque uno de cada cinco niños quedó insatisfecho con sus útiles el primer día de clases.

- **Nuevo del equipo:**
  > Estos hallazgos orientan el recorrido que propone la plataforma. Frente a una compra fragmentada, en la que el acudiente interpreta la lista, compara precios en varios canales y corre el riesgo de omitir productos, Tukit parte de la lista oficial ya revisada, considera la disponibilidad al armar kits según la prioridad de cada familia y reúne la compra en un solo pedido con entrega a domicilio.

- **Nuevo del equipo:**
  > El desarrollo de Tukit está sujeto a restricciones técnicas, normativas y de negocio que delimitan el alcance del sistema y condicionan su diseño. Estas restricciones provienen de la especificación de requerimientos, del marco legal colombiano y de las condiciones de la relación con los colegios y las familias, y se presentan a continuación agrupadas por categoría.

- **Nuevo del equipo:**
  > \begin{itemize} • Contenedores: todos los servicios se empaquetan en contenedores estándar, reproducibles sin cambios entre desarrollo, pruebas y producción. • Tecnologías base: PostgreSQL 16 con pgvector, Python 3.12 o superior para los servicios, y Node.js 20 o superior con Next.js 16 para las aplicaciones web. • Eventos y caché: RabbitMQ 3.13 o superior y Redis 7 o superior, que mejoran la entrega de eventos y el desempeño.

- **Nuevo del equipo:**
  > • Servicios externos: la lectura de listas y los vectores de texto dependen de Gemini, los pagos de Wompi y la búsqueda de direcciones de OpenStreetMap o, en un despliegue con su llave, de Google Places, con sus condiciones, costos por uso y disponibilidad. • Navegadores: Chrome 90 o superior y los navegadores móviles actuales.

- **Nuevo del equipo:**
  > • Límites de carga: archivos de hasta 10 MB y 40 páginas, y un número limitado de peticiones por usuario. Esto protege al sistema frente a archivos diseñados para agotar sus recursos, como los PDF bomb, frente a cargas repetidas que buscan saturarlo y frente al costo de enviar páginas innecesarias al servicio de lectura. \end{itemize}

- **Nuevo del equipo:**
  > \begin{itemize} • Lista oficial como fuente: los kits se construyen a partir de la lista que publica el colegio para cada grado, y solo llegan a las familias después de la revisión del equipo de Tukit. • Formato de las listas: el sistema acepta listas en PDF, imagen o texto, con una sola lista por grado. • Idioma: español colombiano, con reconocimiento del vocabulario escolar local, como ``esfero'' o ``colbón''. \end{itemize}

- **Nuevo del equipo:**
  > \begin{itemize} • Arquitectura por capas: cada servicio separa la recepción de peticiones, las reglas de negocio y el acceso a datos, de modo que la lógica del negocio no depende de la base de datos ni de los servicios externos. • Patrones de diseño: puertos y adaptadores para los servicios externos, como la pasarela de pagos, de modo que puedan reemplazarse sin cambiar la lógica; repositorios para el acceso a datos; puerta de enlace como punto único de entrada; y disyuntor con reintentos ante fallas de otros servicios. • Eventos confiables: cada evento se registra en la misma transacción que el cambio que lo origina y se procesa una sola vez, aunque llegue repetido. • Frontend por componentes: las aplicaciones web se construyen con componentes reutilizables agrupados por funcionalidad, cada uno con sus propios estilos, y comparten una biblioteca común de tipos y validaciones. • Verificación automática: las pruebas, la revisión de estilo del código, las migraciones de las bases de datos y la verificación de que ningún servicio accede a los datos de otro se ejecutan de forma automática. • Revisión humana: ningún kit se publica sin la revisión del equipo de Tukit. \end{itemize}

- **Nuevo del equipo:**
  > \begin{itemize} • Piloto: esta versión se valida con el Colegio Agustiniano Ciudad Salitre, en Bogotá. • Productos: los textos escolares, las licencias digitales y los uniformes no se venden en la plataforma. Se muestran con la instrucción del colegio y no se cobran. • Pagos: durante el piloto no se hacen cobros reales, que se habilitan con el despliegue en producción. • Canal: el acudiente usa una aplicación web progresiva, sin aplicación móvil nativa. \end{itemize}

- **Nuevo del equipo:**
  > \begin{itemize} • Datos de menores: la Ley 1581 de 2012 y el Decreto 1377 de 2013 exigen un tratamiento especial de los datos de niños y adolescentes [cita]. El sistema debe recoger solo los datos indispensables y depurarlos antes de guardarlos o enviarlos a terceros. • Datos de pago: no se almacenan datos de tarjetas. Solo se guarda el identificador de la transacción y su estado. • Retracto: la Ley 1480 de 2011 obliga a garantizar el retracto en las compras a distancia [cita]. • Lista oficial de útiles: el artículo 1 de la Ley 1269 de 2008, que modifica el parágrafo 1 del artículo 203 de la Ley 115 de 1994, obliga a los colegios a entregar en la matrícula la lista completa de útiles, aprobada por el Consejo Directivo, y les prohíbe exigir que los padres entreguen esos materiales al colegio [cita], por lo que el sistema construye los kits sobre la lista oficial de cada grado. \end{itemize}

- **Nuevo del equipo:**
  > La plataforma está diseñada para asistir a las familias en la compra de los útiles escolares de sus hijos, mediante un flujo digital que combina la lectura automática de la lista del colegio, su correspondencia con un catálogo de productos y la construcción de kits de compra que equilibran el costo, la calidad y las preferencias de cada hogar.

- **Nuevo del equipo:**
  > El sistema contempla funcionalidades para el registro y la autenticación de los acudientes, la carga de listas escolares, la generación y personalización de los kits, la compra y el seguimiento de los pedidos, la atención de solicitudes como el derecho de retracto y los casos, y la consulta, la exportación y la supresión de los datos personales. Del lado de la operación, ofrece una aplicación de administración para revisar y publicar las listas oficiales, gestionar el catálogo, responder los casos y consultar las métricas del negocio, así como funciones para la entrega de los pedidos. Las funcionalidades se organizan en servicios independientes, lo que permite que cada una evolucione y crezca por separado.

- **Nuevo del equipo:**
  > \begin{itemize} • Acudiente: es el comprador final. Se registra, otorga el consentimiento para el tratamiento de los datos de sus hijos, registra a cada hijo con su colegio y su grado, carga la lista o consulta la lista oficial de su colegio, indica su presupuesto y sus preferencias, recibe los kits propuestos, los personaliza, por sí mismo o con el asistente del kit, y paga. También puede consultar el estado y el historial de sus pedidos, ejercer el derecho de retracto, radicar y seguir peticiones, quejas o reclamos, y consultar, descargar o suprimir sus datos. Solo tiene acceso a su propia información. • Administrador de Tukit: opera la plataforma desde la aplicación de administración. Carga las listas oficiales que entregan los colegios, revisa los renglones que el sistema no resolvió con certeza, valida o corrige cada uno y publica la lista una vez revisada. Además, gestiona el catálogo de productos, administra los colegios aliados, atiende y responde los casos de las familias y consulta los pedidos, el mapa de entregas, las familias registradas y las métricas del negocio. • Operador de última milla: se encarga de la entrega de los pedidos. Consulta los pedidos pendientes y el contacto de cada entrega, registra el despacho con el repartidor asignado y reporta la entrega o cualquier incidencia. • Sistema: agrupa los procesos que se ejecutan de forma automática, como la lectura de la lista, su correspondencia con el catálogo, la generación de los kits, la verificación del precio antes del cobro, la confirmación del pago y la propagación de eventos entre servicios. \end{itemize}

- **Nuevo del equipo:**
  > El estudiante no utiliza el sistema, pero influye en la compra, sobre todo en el kit Fan, y sus datos reciben la protección especial que exige la ley. Por su parte, el colegio entrega su lista oficial al equipo de Tukit, y su portal propio para publicarla y consultar el panel institucional se contempla entre los siguientes pasos.

- **Nuevo del equipo:**
  > La Figura presenta el diagrama de casos de uso del sistema, organizado en cuatro grupos según el actor. Los casos del acudiente se identifican con la letra P, los del sistema con la S, los del operador de última milla con la O y los del administrador de Tukit con la T. Las relaciones de inclusión muestran que varias acciones del acudiente activan procesos automáticos. Por ejemplo, cargar la lista incluye extraer su estructura y emparejar sus renglones con el catálogo, y pagar el kit incluye procesar la confirmación del pago. La relación de extensión indica que un renglón de baja confianza se escala a validación humana, donde el administrador lo valida o lo corrige.

- **Nuevo del equipo:**
  > El flujo principal inicia cuando el acudiente carga la lista escolar (P-20), acción que incluye la extracción de su estructura (S-01), el emparejamiento de cada renglón con el catálogo (S-02) y la generación de los kits candidatos (S-03). Cuando un renglón no se resuelve con suficiente certeza, el sistema lo escala a validación humana (S-07), y el Administrador de Tukit lo confirma o lo corrige (T-02 y T-03) antes de publicar la lista validada (T-05), que queda disponible para las demás familias del mismo colegio y grado (P-19). Con los kits propuestos, el acudiente puede personalizar los productos (P-12) y confirmar su elección (P-21), lo que genera la orden y conduce al pago (P-22 y P-23). Antes de cobrar, el sistema verifica de nuevo el precio (S-04) y luego procesa la confirmación del pago (S-05). Por último, el Operador de última milla marca el pedido como despachado y registra la entrega (O-03 y O-04), y cada cambio de estado se notifica al acudiente (S-08).

- **Nuevo del equipo:**
  > Alrededor de ese flujo, el acudiente puede pedir un cambio al asistente del kit (P-25) y descartar un renglón que ya tiene (P-26), seguir sus casos y agregarles mensajes (P-30) y, desde Privacidad y mis datos (P-17), exportar sus datos (P-27), revocar un consentimiento (P-28) y solicitar la supresión de sus datos (P-29), que incluye la propagación del evento a los demás servicios (S-09). Del lado del equipo, el administrador responde un caso o cambia su estado (T-16), lo que incluye el aviso al acudiente (S-08), y consulta el mapa de las entregas pendientes (T-17).

- **Figuras y tablas nuevas:** Mapa de empatía del acudiente, elaborado a partir de la encuesta a 60 acudientes del Coleg; Diagrama de casos de uso de Tukit.


## diseñoSolucion.tex  (39 párrafos y 12 figuras/tablas del equipo que no están en la versión actual)

- **Nuevo del equipo:**
  > \setcounter{subsection}{0} \section{DISEÑO DE LA SOLUCIÓN}

  - *Lo más parecido en la versión actual* (desarrolloSolucion.tex, similitud 0.81): \setcounter{subsection}{0} \section{DESARROLLO DE LA SOLUCIÓN}

- **Nuevo del equipo:**
  > En este capítulo se presenta la arquitectura de Tukit y los principales artefactos de su diseño detallado, así como las herramientas y tecnologías seleccionadas para construirlo. El diseño se elaboró antes de la implementación, a partir de los requerimientos y los atributos de calidad definidos en el análisis del problema, y se documenta siguiendo el estándar IEEE 1016 [cita] y las vistas 4+1 de Kruchten [cita]. En primer lugar se describen la arquitectura general y su justificación, y luego las vistas lógica, de procesos, de datos y física. El capítulo cierra con las herramientas y tecnologías seleccionadas.

- **Nuevo del equipo:**
  > El diseño parte del modelo de negocio de Tukit, que la Figura resume en los nueve bloques del lienzo de Osterwalder y Pigneur [cita].

- **Nuevo del equipo:**
  > Varios bloques del lienzo se traducen directamente en decisiones de arquitectura. Los canales determinan las aplicaciones del sistema, que son la aplicación web progresiva de los acudientes y el panel de administración del equipo de Tukit. Las actividades de percepción, normalización y optimización corresponden a las etapas del pipeline que ejecutan los servicios de inteligencia y catálogo, mientras que la actualización del catálogo, los pagos y las entregas dan origen a los servicios de catálogo, comercio y operación. La revisión humana de cada lista exige, además, una cola de revisión en el panel de administración, y la dependencia de proveedores externos de pagos y de modelos multimodales explica por qué estos se integran detrás de adaptadores intercambiables. Las cifras que sustentan la estructura de costos y el flujo de ingresos se validan en la Sección .

- **Nuevo del equipo:**
  > \subsection{Arquitectura del sistema}

  - *Lo más parecido en la versión actual* (disenoSolucion.tex, similitud 0.54): \subsection{Evaluación de la arquitectura con ATAM}

- **Nuevo del equipo:**
  > Con base en los requerimientos, restricciones y modelo de negocio, se compararon tres alternativas de arquitectura mediante el método ATAM [cita]. La primera es un monolito modular, es decir, una sola aplicación organizada en módulos internos. La segunda es una arquitectura de microservicios de grano fino, con trece servicios de dominio y una puerta de enlace. La tercera es una arquitectura de microservicios de grano grueso, con cinco servicios de dominio y una puerta de enlace. Cada alternativa se calificó de 1 a 5 en diez criterios con pesos definidos según su importancia, como muestra la Tabla .

- **Nuevo del equipo:**
  > Se seleccionó la arquitectura de microservicios de grano grueso, con 3,91 sobre 5,00. El monolito resulta sencillo de operar, pero no permite separar las políticas de respaldo ni aislar los datos de los menores, ya que todos los datos comparten una misma base. La arquitectura de grano fino aísla mejor cada dominio, pero convierte cada compra en una operación repartida entre varios servicios, cuya coordinación supera la capacidad de un equipo de cuatro personas [cita]. La alternativa elegida conserva el aislamiento donde la ley y la recuperación de los datos lo exigen, y mantiene juntas las operaciones que deben ocurrir de forma conjunta, como crear un pedido, reservar el inventario y registrar el pago.

- **Nuevo del equipo:**
  > La Figura presenta el sistema frente a sus usuarios y a los servicios externos con los que interactúa. El acudiente, el administrador de Tukit y el operador de última milla acceden al sistema a través de sus aplicaciones, y todas las peticiones pasan por una puerta de enlace, que es el único punto de entrada. El sistema, a su vez, consulta el servicio de inteligencia artificial para leer las listas y representar los textos como vectores, las tiendas en línea para completar la información de los productos, la pasarela de pagos para procesar las compras, los canales de aviso para notificar a las familias y los servicios de mapas para buscar y ubicar las direcciones de entrega.

- **Nuevo del equipo:**
  > La vista lógica describe los componentes del sistema y la responsabilidad de cada uno. La división en servicios sigue el diseño guiado por el dominio, de modo que cada servicio corresponde a una parte del negocio con su propio vocabulario y sus propios datos [cita]. La Figura muestra los componentes y sus conexiones, y la Tabla resume la responsabilidad de cada uno.

- **Nuevo del equipo:**
  > En la parte superior del diagrama se ubican las dos aplicaciones de usuario, admin, la consola del equipo de Tukit, a la izquierda, y web, la aplicación del acudiente, a la derecha. Entre ellas está tukit-contrato, la biblioteca compartida que ambas importan y que reúne los tipos de datos y el cliente con el que se comunican con el servidor. Sobre tukit-contrato se encuentra OpenStreetMap, que las dos aplicaciones consultan por HTTPS para buscar las direcciones de entrega y mostrarlas en un mapa, y en el extremo derecho, GooglePlaces, que la aplicación web usa para sugerir la dirección cuando el despliegue cuenta con su llave. Las peticiones de las dos aplicaciones llegan por HTTP a MS-APIGateway, la puerta de enlace, que las reparte entre los cinco servicios de dominio y registra en Redis, a su derecha, el conteo con el que limita las peticiones de cada usuario.

- **Nuevo del equipo:**
  > En el centro se encuentran los cinco servicios de dominio, que de izquierda a derecha son MS-Identidad, MS-Operacion, MS-Inteligencia, MS-Comercio y MS-Catalogo. Las flechas entre ellos representan consultas directas por HTTP, como la que hace MS-Inteligencia a MS-Catalogo para emparejar los renglones de una lista o la que hace MS-Comercio a MS-Catalogo para verificar de nuevo el precio antes de cobrar. MS-Identidad, a su vez, consulta a MS-Comercio, MS-Operacion y MS-Inteligencia con la misma sesión del acudiente para reunir en un solo inventario sus pedidos, sus casos y sus solicitudes de kits. Sobre esta fila se ubican los sistemas externos que consultan los servicios. MS-Inteligencia y MS-Catalogo usan Gemini, el primero para leer las listas y el segundo para calcular las representaciones vectoriales, MS-Catalogo obtiene los productos y precios de TiendasEnLinea por las interfaces de VTEX y Shopify, y MS-Operacion genera los enlaces de WhatsApp con los que avisa a las familias y entrega por SMTP a CorreoSMTP los avisos que se envían por correo electrónico. MS-Catalogo y MS-Inteligencia usan también Redis como caché de los vectores y de las lecturas de las listas.

- **Nuevo del equipo:**
  > Debajo de cada servicio aparece su base de datos lógica en PostgreSQL, a la que se conecta por SQL mediante asyncpg, junto con las colas de RabbitMQ de las que consume eventos. MS-Identidad consume ColaIdentidadColegios, MS-Operacion consume ColaOperacionAvisos y MS-Inteligencia consume ColaInteligenciaListas y ColaInteligenciaTrabajos. En la fila siguiente están las colas de la supresión de datos, ColaIdentidadSupresion, ColaOperacionSupresion, ColaInteligenciaSupresion y ColaComercioSupresion, cada una bajo el servicio que la consume, y a su derecha, Wompi, la pasarela con la que MS-Comercio procesa los pagos. ExchangeTukitEventos, debajo de MS-Comercio, recibe por AMQP los eventos que los cinco servicios publican desde sus bandejas de salida. En la franja inferior está tukit\_comun, la biblioteca común que importan la puerta de enlace y los cinco servicios, y que envía por OTLP las trazas a Jaeger, en el extremo izquierdo, para seguir cada petición de un servicio a otro.

- **Nuevo del equipo:**
  > Esta distribución responde a los criterios con que se eligió la arquitectura. Los datos personales de las familias y de los menores se concentran en MS-Identidad, de modo que su protección se aplica en un solo servicio. Las operaciones que deben ocurrir juntas, como crear el pedido, reservar el inventario y registrar el pago, quedan dentro de MS-Comercio y se resuelven en una sola transacción. A su vez, MS-Inteligencia concentra el procesamiento más exigente, lo que permite asignarle más recursos durante la temporada escolar sin aumentar los del resto del sistema.

- **Nuevo del equipo:**
  > Los servicios se comunican de dos maneras. Cuando un servicio necesita una respuesta inmediata, como el catálogo cuando inteligencia le pide emparejar los renglones, la comunicación es directa. Cuando un servicio debe informar un hecho a otros, como un pago confirmado, registra el evento en su propia base, en la misma operación en que ocurre el cambio, y una cola de mensajes lo entrega a los servicios interesados. De esta manera, ningún evento se pierde si un servicio falla, y cada uno se procesa una sola vez aunque llegue repetido. El detalle de las clases de cada servicio, organizadas en entidades, fronteras y controladores, se presenta en el anexo de diagramas de clases de la Tabla .

- **Nuevo del equipo:**
  > El diseño incorpora además dos decisiones de seguridad. La primera es que el acceso se controla por rol y por alcance, de modo que un acudiente solo ve su propia información y un usuario del colegio, únicamente la de su institución. La segunda es que los datos personales se protegen desde el diseño, pues el sistema solicita solo los datos indispensables, exige el consentimiento para tratarlos, guarda cifrados los que identifican a los menores y nunca almacena datos de tarjetas, ya que el pago se captura por completo en la pasarela. Cuando un acudiente pide suprimir sus datos, MS-Identidad anonimiza los suyos y publica el evento, que llega a las colas de supresión de Comercio, Operación e Inteligencia. Cada uno borra o enmascara su parte, conserva lo que la ley obliga a guardar, como los soportes contables de los pedidos, y confirma por ColaIdentidadSupresion, y la solicitud se cierra cuando confirman los tres.

- **Nuevo del equipo:**
  > \subsection{Vista de tiempo de ejecución}

  - *Lo más parecido en la versión actual* (disenoSolucion.tex, similitud 0.54): \subsection{Vistas de contexto, contenedores y despliegue}

- **Nuevo del equipo:**
  > La vista de tiempo de ejecución describe cómo colaboran los componentes para atender las principales interacciones de los usuarios. A continuación se describen los tres procesos centrales del sistema.

- **Nuevo del equipo:**
  > \paragraph{Proceso 1: cargar la lista y generar los kits.} El proceso inicia cuando el acudiente selecciona la lista oficial de su colegio y grado, o carga la suya, e indica sus preferencias. El servicio de inteligencia registra la solicitud como un trabajo y la procesa en segundo plano, de modo que el acudiente puede seguir su avance por etapas. El trabajo lee la lista mediante el modelo de inteligencia artificial, normaliza cada renglón y le pide al catálogo que lo empareje con su concepto. Si la lista ya fue revisada por el equipo, el sistema reutiliza esa revisión y pasa directamente a la optimización, que genera los kits y los publica para el acudiente (Figura ).

- **Nuevo del equipo:**
  > \paragraph{Proceso 2: revisar la lista.} Cuando una lista nueva termina de procesarse, queda en la cola de revisión del administrador de Tukit. El administrador compara la lectura del sistema con el documento original, valida o corrige los renglones dudosos y marca los productos que no están disponibles. Solo después de esta revisión los kits se publican para el acudiente, de modo que ningún producto equivocado llega a la familia, y la lista revisada queda disponible para las demás familias del mismo colegio y grado (Figura ).

- **Nuevo del equipo:**
  > \paragraph{Proceso 3: confirmar y pagar el kit.} Cuando el acudiente confirma el kit, el servicio de comercio crea el pedido, verifica de nuevo con el catálogo el precio de cada producto y reserva el inventario por un tiempo limitado. Luego, el acudiente paga en la pasarela, y el sistema recibe la confirmación por dos vías, el aviso que envía la pasarela y la consulta que hace el propio sistema cuando el acudiente regresa. Ambas vías se procesan de forma que el pago se aplique una sola vez. Una vez confirmado, el pedido queda pagado, el servicio de operación notifica al acudiente y el pedido pasa a la entrega (Figura ).

- **Nuevo del equipo:**
  > El modelo de datos reúne las entidades del sistema y sus relaciones. Un acudiente registra a sus hijos, y cada hijo se asocia con un colegio y un grado mediante su matrícula, que determina qué lista oficial le corresponde. Una lista está formada por renglones, y cada renglón se asocia con un concepto del catálogo, que agrupa los productos equivalentes y sus ofertas en distintas tiendas. A partir de esas asociaciones se generan los kits, y el kit que elige el acudiente se convierte en un pedido con su pago y su entrega.

- **Nuevo del equipo:**
  > Cada servicio de dominio guarda sus datos en su propia base y conoce los de los demás solo a través de sus interfaces o de sus eventos. Por eso las relaciones de cada base quedan dentro de ella, y una entidad que se refiere a otra de un servicio distinto, como el kit a la matrícula, guarda solo su identificador. Las Figuras a presentan el modelo de cada servicio. En todas aparece la bandeja de salida, donde el servicio deja los eventos que comunica a los demás.

- **Nuevo del equipo:**
  > En las figuras, cada línea discontinua une la tabla referida con la que guarda la llave foránea, y su etiqueta indica esa llave y la columna a la que apunta. La barra marca el lado de uno, la pata de gallo el lado de muchos y el círculo indica que la relación es opcional.

- **Nuevo del equipo:**
  > En Identidad (Figura ), el usuario es la entidad central. Se relaciona con sus roles mediante la asignación de rol, que registra además quién la otorgó, y cada rol reúne sus permisos en la tabla que los vincula. Del usuario dependen su libreta de direcciones, su perfil socioeconómico, su decisión sobre cada finalidad del tratamiento de datos y sus solicitudes de supresión. La matrícula une a un estudiante con un colegio y una de sus sedes, y la tabla de acudientes por matrícula la vincula con quienes responden por él. El consentimiento registra la aceptación de cada texto legal por parte del usuario y puede referirse a una matrícula cuando autoriza el tratamiento de los datos de un menor.

- **Nuevo del equipo:**
  > En Catálogo (Figura ), el concepto representa la necesidad que pide el colegio, como un cuaderno o una caja de colores, y agrupa los productos canónicos que la satisfacen. Los productos casi idénticos forman un grupo de variantes con un representante, y cada producto se ofrece en una o varias tiendas, con precios que conservan su vigencia y la corrida de captura de la que salieron. La lista oficial de un colegio se publica en versiones, cada una con sus renglones ya asociados a un concepto, y su importación avanza por tareas que se pueden reanudar. La propuesta de producto deja en espera de revisión el candidato de una tienda para un renglón, la sustituibilidad indica qué concepto ofrecer cuando falta otro y la ruta de categoría ubica cada concepto en la taxonomía de cada tienda. Para los textos escolares, las ediciones de libro registran cuál usa hoy cada colegio y las propuestas de reemplazar una edición por otra.

- **Nuevo del equipo:**
  > En Inteligencia (Figura ), cada solicitud de kits de un hogar es un trabajo, que guarda sus etapas con lo que tardó cada una. Los renglones de la lista entran como ítems crudos, cada uno con los candidatos que ofreció el catálogo y una resolución que fija su estado y su producto, y las transiciones de esa resolución registran quién la cambió, cuándo y por qué. Del trabajo salen los kits, uno por perfil, cuyas líneas apuntan al renglón que cubren, y el kit canónico señala el trabajo cuyos kits se aprobaron para un colegio y un grado, para reutilizarlos. Las importaciones de listas y los eventos de otros servicios ya procesados no dependen de otras tablas.

- **Nuevo del equipo:**
  > En Comercio (Figura ), el pedido es la compra de un hogar, así que dos hermanos caben en un solo pago. El pedido agrupa sus líneas con el precio congelado, sus intentos de pago, sus reservas de inventario, sus devoluciones y retractos, el historial de sus cambios de estado y su envío, y cada envío pertenece a una zona de entrega y a la ruta de reparto del día en esa zona. Del lado del abastecimiento, el proveedor reúne sus condiciones comerciales, sus precios, el inventario que declara y los pedidos mayoristas con sus ítems. El inventario propio y los eventos de la pasarela ya procesados no dependen de otras tablas.

- **Nuevo del equipo:**
  > En Operación (Figura ), el caso representa una petición, queja, reclamo o sugerencia, o una falla del proceso de compra, y reúne su historia en los eventos del caso y sus alarmas de vencimiento. Las notificaciones, las preferencias de canal de cada usuario, las salidas a una tienda desde un kit, las métricas diarias y el registro de auditoría se guardan sin depender de otras tablas.

- **Nuevo del equipo:**
  > La vista física muestra cómo se distribuyen los elementos de Tukit sobre la infraestructura que los ejecuta y por qué protocolos se comunican. El Entorno de ejecución de Tukit agrupa tres nodos de cómputo, el Nodo Web (Next.js), el Nodo Servicios (Python) y el Nodo Datos (Docker), y se conecta con los dispositivos de los usuarios y con los sistemas externos. La Figura presenta el diagrama de despliegue.

- **Nuevo del equipo:**
  > A continuación se describen los nodos de la figura y lo que aloja cada uno.

  - *Lo más parecido en la versión actual* (anexo_antecedentes.tex, similitud 0.48): Esta sección desarrolla los conceptos de la Tabla .

- **Nuevo del equipo:**
  > \begin{itemize} • Dispositivo del acudiente, Equipo del personal Tukit y Dispositivo del operador de última milla. El acudiente usa la aplicación web desde el navegador de su celular o computador, el personal de Tukit usa la consola admin desde el suyo, y el operador de última milla abre la consola desde el navegador de su celular para registrar el avance de las entregas. Los tres llegan al Nodo Web (Next.js) por HTTPS. Los navegadores descargan además de OpenStreetMap las teselas de los mapas en los que el acudiente confirma su dirección y el equipo de Tukit ve las entregas pendientes. Desde el navegador del acudiente se consulta Google Places cuando el despliegue tiene su llave, se abre el widget de pago de Wompi y se siguen los enlaces de WhatsApp (wa.me) que arma MS-Operacion, en todos los casos por HTTPS.

- **Nuevo del equipo:**
  > • Nodo Web (Next.js). Ejecuta las dos aplicaciones Next.js 16, los componentes web y admin, que se sirven con el artefacto next start (Node.js), la web en el puerto 3000 y la consola en el 3001. Sus rutas de servidor llaman al Nodo Puerta de enlace por HTTP en el puerto 8010, de modo que el navegador nunca conoce la dirección de los servicios. Esas mismas rutas consultan por HTTPS el buscador de OpenStreetMap (Nominatim), con una petición por segundo y una caché, para buscar las direcciones del acudiente y ubicar las entregas en el mapa de la consola.

- **Nuevo del equipo:**
  > • Nodo Puerta de enlace. Aloja MS-APIGateway, un proceso Python 3.12 con FastAPI sobre Uvicorn que es la única entrada desde el Nodo Web. Enruta cada solicitud al nodo del servicio que la atiende, por HTTP en el puerto 8011 para Identidad, 8012 para Catálogo, 8013 para Inteligencia, 8014 para Comercio y 8015 para Operación, y aplica el límite de tasa con los contadores que lleva en Redis.

- **Nuevo del equipo:**
  > • Nodos Identidad, Catálogo, Inteligencia, Comercio y Operación. Cada uno aloja un servicio de dominio, MS-Identidad, MS-Catalogo, MS-Inteligencia, MS-Comercio o MS-Operacion, como un proceso Python 3.12 con FastAPI sobre Uvicorn junto con sus trabajadores de fondo, y el artefacto de su base, IdentidadDB, CatalogoDB, InteligenciaDB, ComercioDB u OperacionDB, en PostgreSQL 16 con pgvector. Cada servicio se conecta por SQL (asyncpg, puerto 5432) solo a su base. Desde estos nodos salen por HTTPS las conexiones con los sistemas externos. MS-Inteligencia consulta a Gemini (Google) para leer las listas, MS-Catalogo le pide los vectores de búsqueda y consulta las tiendas en línea, y MS-Comercio intercambia con Wompi las consultas de las transacciones y sus avisos de pago. MS-Operacion envía los correos por SMTP.

- **Nuevo del equipo:**
  > • MOM\_RabbitMQ. Ejecuta el artefacto rabbitmq:3.13-management-alpine con el intercambio tukit.eventos, al que los cinco servicios de dominio se conectan por AMQP en el puerto 5672, y aloja ocho colas durables. ColaIdentidadColegios lleva a MS-Identidad los colegios que verifica MS-Catalogo, y ColaInteligenciaListas lleva a MS-Inteligencia las listas que MS-Catalogo verifica o aprueba. ColaInteligenciaTrabajos reparte los trabajos encolados entre los trabajadores de MS-Inteligencia, y ColaOperacionAvisos recibe los eventos de MS-Inteligencia y MS-Comercio que se convierten en avisos para el acudiente. Las otras cuatro sirven a la supresión de datos. ColaComercioSupresion, ColaOperacionSupresion y ColaInteligenciaSupresion llevan a cada servicio el evento que publica MS-Identidad cuando un acudiente pide suprimir sus datos, y ColaIdentidadSupresion le devuelve las confirmaciones.

- **Nuevo del equipo:**
  > • Redis y Jaeger (all-in-one). Redis ejecuta el artefacto redis:7 y atiende por RESP, en el puerto 6379, los contadores del límite de tasa de MS-APIGateway, la caché de las lecturas de listas de MS-Inteligencia y la de los vectores de MS-Catalogo. Jaeger ejecuta el artefacto jaegertracing/all-in-one:1.60 y recibe por OTLP, en el puerto 4317, las trazas de la puerta de enlace y de los cinco servicios.

- **Nuevo del equipo:**
  > • Sistemas externos. Gemini (Google) interpreta las fotografías de las listas escolares para MS-Inteligencia y calcula los vectores de búsqueda de MS-Catalogo. Las tiendas en línea Éxito, Panamericana y Papelería Grancentral publican los productos y precios que consulta MS-Catalogo. Wompi procesa los pagos que inicia MS-Comercio, Correo SMTP entrega los avisos por correo electrónico que envía MS-Operacion, OpenStreetMap busca las direcciones de entrega y sirve las teselas de los mapas, Google Places sugiere direcciones cuando el despliegue tiene su llave y WhatsApp (wa.me) abre la conversación con el aviso ya redactado.

- **Nuevo del equipo:**
  > \end{itemize} Los servicios se comunican entre sí por HTTP y reciben por variables de entorno las direcciones de sus dependencias, por lo que los nodos pueden ocupar máquinas separadas o compartir una sola sin cambios en el código. El estado de negocio de cada servicio vive en su propia base y los contadores del límite de tasa viven en Redis, así que un servicio puede ejecutarse en varias réplicas sin compartir memoria entre ellas. Los enlaces con los sistemas externos van cifrados con HTTPS y el envío de correo usa STARTTLS.

- **Nuevo del equipo:**
  > El despliegue tolera la caída de sus componentes de soporte. Si MOM\_RabbitMQ no responde, cada evento espera en la bandeja de salida de su productor, donde se escribió en la misma transacción que el cambio, y se publica cuando el intercambio vuelve a estar disponible. Los consumidores se reconectan solos, y las colas, que son durables, conservan los mensajes que ya habían recibido. Sin Redis, las lecturas y los vectores se calculan sin caché y MS-APIGateway cuenta las solicitudes en su propia memoria. Si Jaeger se detiene, los servicios siguen atendiendo y solo se pierden las trazas. Si Gemini (Google) falla, el sistema reintenta la lectura una vez y, si el fallo persiste, informa al acudiente para que vuelva a cargar la lista, sin guardar una lectura incompleta.

- **Figuras y tablas nuevas:** Lienzo del modelo de negocio de Tukit. Adaptado de Osterwalder y Pigneur \citep{osterwalde; Diagrama de contexto de Tukit.; Diagrama de componentes de Tukit.; Diagrama de secuencia del proceso de carga de la lista y generación de los kits.; Diagrama de secuencia del proceso de revisión de la lista.; Diagrama de secuencia del proceso de confirmación y pago del kit.; Modelo entidad-relación del servicio de Identidad.; Modelo entidad-relación del servicio de Catálogo.; Modelo entidad-relación del servicio de Inteligencia.; Modelo entidad-relación del servicio de Comercio.; Modelo entidad-relación del servicio de Operación.; Diagrama de despliegue de Tukit.


## desarrolloSolucion.tex  (81 párrafos y 16 figuras/tablas del equipo que no están en la versión actual)

- **Nuevo del equipo:**
  > Este capítulo describe la construcción de Tukit siguiendo el recorrido de quienes lo usan, el acudiente, que se registra, entrega la lista, recibe y ajusta los kits, paga, sigue su pedido y administra sus datos, y el equipo de Tukit, que revisa las listas, cura el catálogo, despacha y consulta las métricas. Cada funcionalidad se presenta con su pantalla, su objetivo específico, su fase, su marco metodológico y los requerimientos que atiende. Al llegar al procesamiento de la lista, el capítulo se detiene en los algoritmos, y al final compara las alternativas evaluadas.

- **Nuevo del equipo:**
  > La construcción siguió las fases de la Tabla . SCRUM [cita] ordenó la integración en sprints de dos semanas con un tablero Kanban, y CRISP-DM [cita] guió los componentes que dependen de datos. En la Fase 3, ligada al OE3, la percepción y la normalización recorrieron la comprensión y la preparación de los datos, el modelado y la evaluación; en la Fase 4, ligada al OE4, la optimización recorrió el modelado y la evaluación, y la integración en el sistema correspondió al despliegue. El corpus de listas y el catálogo de conceptos del OE1 alimentaron ambas fases (Tabla ).

- **Nuevo del equipo:**
  > \subsection{Registro del acudiente y matrícula de los hijos}

  - *Lo más parecido en la versión actual* (disenoSolucion.tex, similitud 0.46): \subsubsection{Organización del código y funciones de aptitud}

- **Nuevo del equipo:**
  > El acudiente entra por la aplicación web progresiva, que funciona desde el navegador del celular sin instalación, como pide RNF04, y quien llega por primera vez se registra en el mismo formulario en que entrega su lista (Figura ). Esta funcionalidad pertenece al OE4 y se construyó en los sprints de la Fase 4. El registro pide un correo, una clave de al menos ocho caracteres, si se desea un celular para los avisos y la aceptación de la política de tratamiento de datos y de los términos, que el servidor exige antes de crear la cuenta y guarda con su versión y su fecha. La clave se guarda derivada con PBKDF2-HMAC-SHA256, con sal por usuario y 240.000 iteraciones, y la sesión es un token firmado con HMAC con la versión de permisos del usuario, que la puerta de enlace valida con el servicio de identidad, de modo que cerrar la sesión revoca los tokens anteriores.

- **Nuevo del equipo:**
  > La protección de los datos de los menores, que pide RNF02 conforme a la Ley 1581 de 2012 y al Decreto 1377 de 2013 [cita], empieza por la recolección. El formulario nunca pide el nombre legal del estudiante, porque el colegio y el grado bastan para armar su kit, y el apodo opcional con que el acudiente lo reconoce en su panel se guarda mediante un puerto de cifrado cuyo adaptador de producción es Fernet, igual que las direcciones de la libreta de entrega. Agregar un hijo a una cuenta existente exige además autorizar el tratamiento de su dato, que se registra como consentimiento del menor con su propia versión.

- **Nuevo del equipo:**
  > Cada hijo se matricula con su colegio, su sede, su grado y el año lectivo, y esa matrícula determina qué lista oficial le corresponde, como pide RF01. El buscador reúne los colegios aliados y el directorio de colegios de Bogotá, y de un colegio que todavía no es aliado se deriva un identificador estable que la aprobación de su primera lista convierte en su identidad. Los quince grados, de Párvulos a Once, son una constante del sistema educativo, así que un colegio sin lista publicada sigue apareciendo, y un hogar puede tener hijos en colegios distintos.

- **Nuevo del equipo:**
  > \subsection{Carga o selección de la lista}

  - *Lo más parecido en la versión actual* (disenoSolucion.tex, similitud 0.49): \subsection{Evaluación de la arquitectura con ATAM}

- **Nuevo del equipo:**
  > Esta funcionalidad atiende RF01 y une el trabajo de las Fases 3 y 4. El formulario pide, por cada hijo, la lista y, si el niño lo desea, uno o varios personajes; luego, el canal de los avisos, y por último cuánto quiere gastar el hogar. Esta pregunta ofrece tres opciones, lo más económico, un punto medio o puedo estirarme un poco, y solo el punto medio admite un tope de gasto. Cada opción se traduce en pesos para los cuatro criterios del kit y en una disposición a pagar sobreprecio de 0, 5 o 10%, que usa la recomendación.

- **Nuevo del equipo:**
  > Los grados con lista verificada se distinguen en el selector, y si el colegio es aliado y la lista de ese grado ya fue revisada, el acudiente no sube nada, porque el sistema usa la lista oficial. Si además el hogar tiene un solo hijo y no eligió el punto medio, se aplica de inmediato el kit canónico de esa lista, es decir, los kits que una persona ya aprobó para el colegio y el grado, con el perfil elegido y el personaje en los productos ancla, sin volver a optimizar. Para un grado sin lista verificada, el formulario ofrece subirla en PDF, JPG, PNG o WEBP, de hasta 10 MB (Figura ).

- **Nuevo del equipo:**
  > La subida percibe el archivo de cada hijo antes de escribir cualquier dato, con una regla de todo o nada por hogar, de modo que si se rechaza un archivo, por traer varios grados, una página incompleta o un contenido ilegible, la respuesta explica el motivo y no se guarda ninguno. Cada archivo aceptado queda como versión sin revisar de su colegio y grado, con un aviso al acudiente cuando quede verificada. Como exige RNF08, si el catálogo no responde, la petición confirma la recepción y guarda lo percibido para que un proceso de fondo lo importe con espera exponencial, de 5 s hasta 5 minutos, y una clave de idempotencia, sin volver a pagar la lectura; y con el servicio de lectura caído, las listas oficiales y los kits ya generados siguen disponibles. La puerta de enlace limita además la tasa, con 300 peticiones por token y 1.200 por dirección IP cada minuto, y 30 y 60 cada diez minutos en las rutas costosas, como subir una lista, y 5 y 10 cada hora en la supresión de los datos.

- **Nuevo del equipo:**
  > El procesamiento convierte la lista en kits, reúne el trabajo de los OE3 y OE4 y atiende RF01, RF02 y RF03. Cada solicitud es un trabajo por hogar cuyo estado se guarda en la base del servicio de inteligencia, y pasa por encolado, procesando, en espera de revisión y publicado, con fallido, reintentable, y cancelado como salidas. Un proceso trabajador toma los trabajos encolados con una consulta SELECT \ldots{} FOR UPDATE SKIP LOCKED, de modo que dos procesos nunca toman el mismo, y como el procesamiento recalcula desde cero los renglones y los kits de su trabajo, retomarlo después de una caída no duplica nada. Cada etapa, percepción, normalización, resolución y optimización, guarda su estado y su duración, y la pantalla de espera las presenta en lenguaje cotidiano (Figura ).

- **Nuevo del equipo:**
  > En la ruta rápida, cuando todas las listas del hogar ya fueron revisadas, los conceptos y los candidatos curados se leen del catálogo y el trabajo pasa directamente a la optimización; la ruta completa ejecuta las cuatro etapas. En las dos, el trabajo espera la revisión antes de que el acudiente vea los kits, salvo cuando nace de una lista que una persona acaba de aprobar. En la solicitud de la figura, de una lista ya verificada, obtener la lista tomó 0,7 s, la optimización con NSGA-II 2,0 s y el trabajo quedó en revisión unos 4 s después de enviarse.

- **Nuevo del equipo:**
  > La percepción lee el documento y lo convierte en renglones con su descripción y, si existe, su cantidad. Recibe un archivo, PDF o imagen, y devuelve la tupla \(\langle ok, G, X, e\rangle\), con la decisión de aceptación, los grados detectados, los ítems leídos y el código de rechazo. Como la mayoría de las listas son tablas, en las que una fila puede ocupar dos líneas y la cantidad está en otra columna, partir en líneas el texto del PDF separa lo que va junto. Por eso cada página se rasteriza a 150 puntos por pulgada, unos 1.275 por 1.650 píxeles en tamaño carta, y se entrega como imagen a un modelo multimodal que la lee como tabla [cita], que en la versión construida es gemini-3.5-flash-lite.

- **Nuevo del equipo:**
  > La instrucción al modelo fija reglas de segmentación tomadas del corpus, como que una fila es un ítem aunque ocupe dos líneas o que los contenidos de una cartuchera se separan y una serie de durezas no. La respuesta se restringe a un esquema JSON con temperatura 0 y se vuelve a validar localmente, de modo que ningún ítem se produce fuera de la lectura del modelo.

- **Nuevo del equipo:**
  > Sobre esa lectura, la percepción aplica una regla de negocio que no delega. El archivo se acepta solo si todas sus páginas se leyeron completas y si corresponde a un único grado (Algoritmo ). La señal de una lista de varios cursos es el número de grados distintos, porque en el corpus hay listas de un grado que ocupan seis páginas y archivos de tres grados que caben en dos. Cada nombre de grado se canoniza antes de contarlo, para que ``4'', ``4°'' y ``Cuarto'' cuenten como uno, y un nombre desconocido se conserva como grado distinto para no ocultar un archivo de varios cursos. El tope de 40 páginas, justo por encima del PDF más largo del corpus, que tiene 39, protege contra archivos abusivos.

- **Nuevo del equipo:**
  > Cada llamada tiene un tiempo límite de 40 s, y los fallos pasajeros, como la falta de respuesta o un código HTTP 429 o 5xx, se reintentan una vez después de 3 s, con un peor caso de 83 s por página. Con la regla de todo o nada, si cada llamada falla con probabilidad \(p\), el reintento baja la de un documento de \(P\) páginas de \(1-(1-p)^P\) a \(1-(1-p^2)^P\), de 26,5% a 1,5% con \(p = 0{,}05\) y \(P = 6\).

- **Nuevo del equipo:**
  > Como las familias de un colegio suben el mismo archivo, la lectura aceptada se memoriza en Redis durante 30 días (Algoritmo ), como en la memoización de la programación dinámica, con una clave que combina la huella SHA-256 del archivo y una versión del código de lectura y del modelo.

  - *Lo más parecido en la versión actual* (anexo_algoritmos.tex, similitud 0.63): \paragraph{Memoización de la lectura.} Como las familias de un colegio suben el mismo archivo, la lectura aceptada se guarda en Redis durante 30 días, con una clave que combina la huella SHA-256 del archivo y una versión del código de lectura y del modelo. Los rechazos no se guardan, y si el almacén no responde la lectura se hace de nuevo. Una lectura memorizada cuesta solo la huella, $\Theta(\lve

- **Nuevo del equipo:**
  > Sea \(P\) el número de páginas. La rasterización es lineal en los píxeles y el algoritmo hace \(\Theta(P)\) llamadas, como máximo \(2P\), con un tiempo \(T(P) \le P\,(2 \cdot 40 + 3)\) s y \(P \le 40\), de modo que dominan las inferencias; una lectura memorizada cuesta la huella, \(\Theta(\lvert A\rvert)\). En una corrida real con gemini-3.5-flash-lite, la lista de tres páginas del grado Cuarto del Colegio Agustiniano Ciudad Salitre se leyó e importó en 16,7 s de extremo a extremo, y 76 de sus 78 renglones quedaron con concepto automático.

- **Nuevo del equipo:**
  > La normalización responde qué pidió el colegio antes de mirar el catálogo. Recibe un renglón con su texto, la cantidad de la columna, si existía, y el tipo y el modo de adquisición que la lista oficial trae revisados, y devuelve una demanda con el tipo, el modo, la cantidad pedida y el empaque que el texto declara (Algoritmo ). El tipo y el modo salen de una lista de decisión [cita], una secuencia ordenada de condiciones en la que gana la primera que se cumple. Sus once filas reconocen, en orden, lo que ya está en casa, lo que se pedirá después, las licencias, la papelería que dice libro, la venta directa, las ediciones exclusivas, los uniformes, los textos y, por omisión, los útiles, y el orden importa, porque ``Diccionario, el disponible en casa'' debe caer en la primera fila y no en la de textos.

  - *Lo más parecido en la versión actual* (anexo_algoritmos.tex, similitud 0.52): \paragraph{Normalización de un renglón.} La normalización recibe el texto del renglón, la cantidad de la columna si existía y el tipo y el modo curados de la lista oficial, y devuelve una demanda con el tipo, el modo, la cantidad pedida y el empaque que declara el texto. El tipo y el modo salen de una lista de decisión de once filas en la que gana la primera que se cumple, y lo curado prevalece so

- **Nuevo del equipo:**
  > La decisión central es separar la cantidad que pide el colegio de las unidades por empaque del producto, de modo que doce lápices pedidos frente a una caja de doce se traducen en una caja y no en doce. El empaque del texto se lee de expresiones como ``x 12'' o ``caja de 12'', salvo si las sigue una unidad de medida, y lo que se compra se calcula con el empaque del producto elegido, como \(\lceil q/\upsilon\rceil\). Lo curado prevalece, primero el tipo de la lista oficial, luego el del concepto y al final el inferido.

- **Nuevo del equipo:**
  > Con \(\ell\) la longitud del renglón y \(F = 37\) frases clave, la forma plana cuesta \(O(\ell)\) y la clasificación \(O(F\ell)\); como \(F\) es constante, normalizar un renglón es \(\Theta(\ell)\) y una lista, lineal en su longitud total.

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > ~~\subsection{Normalización y resolución}~~ **\subsubsection{Resolución con búsqueda híbrida}**

  - *Lo más parecido en la versión actual* (desarrolloSolucion.tex, similitud 0.6): \subsection{Normalización y resolución}

- **Nuevo del equipo:**
  > La resolución decide, para cada renglón que se busca en el catálogo, a qué concepto corresponde, qué atributos exige y qué productos ofrecer, como pide RF02. Un concepto es una clase de productos intercambiables para el colegio, como cuaderno, con su nombre, sus sinónimos y los atributos que distinguen sus variantes. Del marco de generación aumentada por recuperación [cita] esta etapa toma solo la recuperación, y combina la señal léxica, precisa con marcas y referencias, con la semántica, que compara significados mediante vectores [cita] y reconoce sinónimos que nadie escribió, como estuche por cartuchera.

- **Nuevo del equipo:**
  > Antes, una corrección ortográfica conservadora, con la distancia de alineamiento óptimo de cadenas [cita] calculada por programación dinámica [cita] y cortada en 1, cambia una palabra solo si hay exactamente una del léxico a un cambio, con su misma primera letra y su misma longitud, como ``taolla'' por ``toalla''.

- **Nuevo del equipo:**
  > La señal léxica aprovecha que en español el núcleo del sintagma nominal va primero; en ``pompones de colores'' lo pedido son pompones. Por eso el puntaje premia que la frase del concepto empiece por la cabeza del renglón, su primera palabra útil sin cantidades, empaques ni medidas, y exige como guarda que la frase al menos la nombre. Las palabras se comparan en singular, y el parecido entre frases es el coeficiente de Jaccard [cita] sobre las palabras significativas. La señal semántica usa vectores unitarios de 1.024 dimensiones de gemini-embedding-001 [cita]; el de un concepto es el centroide normalizado de los de sus productos, y el del renglón se calcula una vez por lista, en un lote. Si el servicio de vectores falla, la resolución sigue con la señal léxica y registra la degradación.

- **Nuevo del equipo:**
  > El Algoritmo define el puntaje. Si la frase del concepto empieza por la cabeza, parte de 0,6 y suma 0,4 veces el Jaccard y 0,15 veces el coseno; si la nombra en otra posición, vale el Jaccard más el mismo aporte del coseno; si no la nombra, solo un coseno de 0,86 o más la rescata, con un puntaje entre 0,55 y 0,95. El coseno se recorta en cero y solo suma, de modo que el puntaje híbrido nunca queda por debajo del léxico; la guarda léxica evitó que ``chaquiras de colores'' alcanzara 0,5 contra los lápices de colores.

  - *Lo más parecido en la versión actual* (anexo_algoritmos.tex, similitud 0.61): \paragraph{Puntaje híbrido léxico-semántico.} El procedimiento recibe el renglón ya corregido, los conceptos del catálogo con su nombre, sus sinónimos y su centroide, y el vector del renglón si existe, y devuelve el concepto de mayor puntaje. Si la frase del concepto empieza por la cabeza del renglón, el puntaje parte de 0,6; si la nombra en otra posición, vale el Jaccard más el aporte del coseno,

- **Nuevo del equipo:**
  > Reconocido el concepto, el Algoritmo lee solo los atributos que ese concepto declara como discriminantes, como el tamaño o el rayado, y filtra sus productos; lo que se mide admite al menos lo pedido, como 100 hojas donde se piden 80, y un atributo no declarado no se da por cumplido. Si ningún producto cumple, el sistema se abstiene en lugar de ofrecer otro, y entre los que cumplen ofrece uno por nivel de marca, con máximo tres opciones.

  - *Lo más parecido en la versión actual* (anexo_algoritmos.tex, similitud 0.51): \paragraph{Resolución de un renglón.} Reconocido el concepto, el procedimiento lee solo los atributos que ese concepto declara como discriminantes y filtra sus productos. Si ninguno cumple, se abstiene en lugar de ofrecer otro, y entre los que cumplen ofrece uno por nivel de marca, con máximo tres opciones. El estado depende de dos umbrales: por debajo de 0,5 el renglón queda sin correspondencia, 

- **Nuevo del equipo:**
  > El estado del renglón depende de dos umbrales. Por debajo de 0,5 queda sin correspondencia; entre 0,5 y \(\tau\), ambiguo y en revisión humana, y desde \(\tau\) se resuelve de forma automática. El valor por omisión, \(\tau = 0{,}75\), se ajusta por configuración y hace que una cabeza acertada sin más contexto, que vale 0,6, vaya a revisión, y que para aceptarse sola necesite \(0{,}4J + 0{,}15\kappa \ge 0{,}15\). Si una persona ya asignó el concepto, este se usa con puntaje 1.

- **Nuevo del equipo:**
  > Con \(\lvert\mathcal{C}\rvert\) conceptos, \(\Lambda\) frases candidatas de longitud media \(\bar L\) y vectores de dimensión \(d\), clasificar un renglón cuesta \(O\bigl(\lvert\mathcal{C}\rvert d + \Lambda(\bar L + \lvert \mathrm{sig}(\tilde x)\rvert)\bigr)\), lineal en el catálogo, porque el coseno se calcula una vez por concepto; con unos 150 conceptos y 1.024 dimensiones son unos \(1{,}5 \times 10^5\) productos escalares, y resolver una lista es lineal en sus renglones, más una llamada por lotes al modelo de vectores.

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > ~~\subsection{Optimización del kit}~~ **\subsubsection{Optimización multiobjetivo}**

  - *Lo más parecido en la versión actual* (desarrolloSolucion.tex, similitud 0.82): \subsection{Optimización del kit}

- **Nuevo del equipo:**
  > La optimización elige un candidato por línea y arma los kits, como pide RF03 dentro del OE4. Como el kit más barato difiere del de mejor marca y del que trae el personaje, el sistema construye el frente de Pareto y después lo proyecta en los kits [cita]. Sean \(1,\dots,n\) las líneas decidibles, las no informativas con al menos un candidato, y \(A_i\) los candidatos admisibles de la línea \(i\), los que cumplen los atributos impuestos o, si ninguno cumple, todos, con \(\lvert A_i\rvert \le 3\). Una asignación \(\mathbf{x} = (x_1,\dots,x_n)\) toma un candidato por línea en \(\Omega = A_1 \times \cdots \times A_n\), con \(\lvert\Omega\rvert \le 3^n\). Si la línea pide \(q_i\) unidades y el candidato \(c\) viene en empaques de \(\upsilon(c)\), se compran \(u_i(c) = \lceil q_i/\upsilon(c)\rceil\) empaques, con costo de línea \(\kappa_i(c) = \pi(c)\,u_i(c)\). Los objetivos son \begin{align} f_1(\mathbf{x}) &= \sum_{i\,:\,\pi(x_i) \ne \bot} \kappa_i(x_i), & f_2(\mathbf{x}) &= \frac{1}{n}\sum_{i=1}^{n} \frac{\nu(x_i)}{2}, \nonumber\\ f_3(\mathbf{x}) &= \frac{1}{n}\sum_{i=1}^{n} \mathbf{1}\bigl[\pi(x_i) \ne \bot\bigr], & f_4(\mathbf{x}) &= \frac{1}{n}\sum_{i=1}^{n} \varphi_i(x_i), \end{align} con el costo \(f_1\) a minimizar y la fidelidad de marca \(f_2\), la disponibilidad \(f_3\) y el personaje \(f_4\) a maximizar. Aquí \(\nu(c) \in \{0,1,2\}\) es el nivel de marca, \(\pi(c)\) el menor precio vigente entre las ofertas, o \(\bot\) si no hay, y \(\varphi_i(c)\) vale 1 si el producto trae el personaje pedido para ese hijo o, si no se pidió ninguno, cualquier personaje. Una asignación \(\mathbf{x}\) domina a \(\mathbf{y}\), \(\mathbf{x} \prec \mathbf{y}\), si no es peor en ningún objetivo y es mejor en al menos uno, y el frente reúne los vectores de las asignaciones que ninguna otra domina [cita].

- **Nuevo del equipo:**
  > El Algoritmo construye el frente según el tamaño del espacio. Con \(\lvert\Omega\rvert \le 1\) no hay compromiso, y los kits salen de una heurística por perfil que en ese caso es óptima. Con \(\lvert\Omega\rvert \le 4.096 = 2^{12}\), el sistema enumera todas las asignaciones y filtra las no dominadas, lo que da el frente exacto. El límite queda entre los puntos en que la enumeración deja de ser más rápida que NSGA-II, unas 4.932 asignaciones en la mediana y 2.380 en el percentil 95, y por debajo de él la enumeración ganó en 28 de 30 subproblemas medidos. Por encima de ese límite, que en el corpus de 175 listas corresponde a 137, el frente se aproxima con NSGA-II [cita] en la implementación de pymoo [cita].

- **Nuevo del equipo:**
  > Antes de construir el frente se aplican los filtros duros del acudiente. Una marca excluida sale de los candidatos, salvo en el renglón que la nombra porque el colegio la exige, y la opción de solo productos disponibles quita los que no tienen oferta vigente. Un renglón que se queda sin candidatos pasa a ser un hueco del catálogo con un mensaje que explica por qué, y los mismos filtros rigen en las opciones de cada línea y en el cambio de producto.

- **Nuevo del equipo:**
  > NSGA-II (Algoritmo ) mantiene \(N\) soluciones, produce \(N\) descendientes por selección, cruce binario simulado y mutación polinomial [cita], y elige la generación siguiente por rango de no dominancia y distancia de aglomeración. La variable de cada línea es el índice entero del candidato. La población es \(N = \min(100, \max(20, 6n))\), redondeada a un número par, y las generaciones son \(G = \bigl\lfloor\min\bigl(60, \max(15, 10\log_{10}\lvert\Omega\rvert)\bigr)\bigr\rfloor\), con semilla 0 por omisión, para que una entrada reproduzca su frente. Esos tamaños son la configuración más barata cuyo hipervolumen quedó a menos de 0,1% del mejor en una calibración de cinco pliegues agrupada por colegio. Como el índice es una etiqueta nominal, la población inicial se siembra con la heurística por perfil y con una escalera de costo marginal, que parte del kit más barato y sube en cada paso la línea con menor \(\Delta\kappa/\Delta\nu\), el criterio de eficiencia de la mochila de elección múltiple [cita], en \(O(n^2k)\) con \(k = \max_i \lvert A_i\rvert\); las semillas entran al filtro final, así que el frente nunca queda por debajo de ellas.

  - *Lo más parecido en la versión actual* (anexo_algoritmos.tex, similitud 0.53): \paragraph{NSGA-II sembrado.} NSGA-II mantiene $N$ soluciones, produce $N$ descendientes por selección, cruce binario simulado y mutación polinomial, y elige la generación siguiente por rango de no dominancia y distancia de aglomeración. La variable de cada línea es el índice entero del candidato, y la población inicial se siembra con la heurística por perfil y con la escalera de costo marginal, d

- **Nuevo del equipo:**
  > Del frente salen los kits por selección lexicográfica sobre los puntos de máxima disponibilidad (Algoritmo ). El Ahorrador minimiza el costo, el Premium maximiza la fidelidad, el Fan maximiza el personaje, y A tu Medida es el de mayor fidelidad cuyo costo cabe en el tope, el presupuesto declarado o la mitad del camino entre el Ahorrador y el Premium; el Fan se arma si se pidió un personaje, y A tu Medida si se eligió el punto medio o un tope. Después del frente, el producto del personaje se ubica, por cada hijo y concepto, en el renglón con el que mejor encaja sin contradecir sus atributos, y en los cuatro conceptos ancla, el cuaderno, la cartuchera, la carpeta y la maleta, encabeza el kit. La enumeración cuesta \(O(\lvert\Omega\rvert\,n)\) más el filtro por pares, \(O(\lvert U\rvert^2 M)\) con \(M = 4\), y NSGA-II cuesta \(O\bigl(G(MN^2 + Nn)\bigr)\) por el ordenamiento no dominado y la evaluación.

  - *Lo más parecido en la versión actual* (anexo_algoritmos.tex, similitud 0.58): \paragraph{Selección de los kits.} Del frente salen los kits por selección lexicográfica sobre los puntos de máxima disponibilidad. El Ahorrador minimiza el costo, el Premium maximiza la fidelidad, el Fan maximiza el personaje, y A tu Medida es el de mayor fidelidad cuyo costo cabe en el tope, que es el presupuesto declarado o la mitad del camino entre el Ahorrador y el Premium. Si ningún punto tr

- **Nuevo del equipo:**
  > \subsubsection{NSGA-II frente a la programación dinámica}

- **Nuevo del equipo:**
  > La programación dinámica es la alternativa natural a una metaheurística cuando el problema tiene subestructura óptima [cita]. Con la formulación de la Ecuación \eqref{eq:dev-objetivos}, cada objetivo es una suma de términos de una sola línea, y tres de ellos son contadores enteros pequeños. Si \(a(\mathbf{x}) = \sum_i \nu(x_i) \in [0, 2n]\), \(b(\mathbf{x})\) es el número de líneas con precio y \(p(\mathbf{x})\) el de líneas con el personaje, el menor costo de cada terna \((a, b, p)\) sale de la recurrencia del Algoritmo , y el frente es el conjunto de ternas no dominadas con su costo mínimo. Tras \(i\) líneas hay a lo sumo \((2i+1)(i+1)^2\) estados con \(k\) transiciones cada uno, de modo que el tiempo es \(O(n^4k)\) y la memoria, con el retroceso de todas las etapas, \(O(n^4)\). Para \(n = 17\) y \(k = 3\) el peor caso es de 11.340 ternas por etapa, frente a \(3^{17} \approx 1{,}3 \times 10^8\) asignaciones, aunque en las listas reales se alcanzaron como mucho 253, porque todas las líneas tienen precio y pocas tienen personaje. El compromiso con presupuesto, que maximiza \(f_2\) sujeto a \(f_1 \le B\), es una mochila de elección múltiple [cita], NP-difícil en general [cita], que aquí se resuelve en \(O(n^2k)\) porque los valores son niveles enteros entre 0 y \(2n\).

  - *Lo más parecido en la versión actual* (anexo_algoritmos.tex, similitud 0.49): \paragraph{Frente exacto por programación dinámica.} Como cada objetivo es una suma de términos de una sola línea y tres de ellos son contadores enteros pequeños, el menor costo de cada terna $(a, b, p)$ de nivel de marca acumulado, líneas con precio y líneas con personaje sale de una recurrencia línea por línea, y el frente es el conjunto de ternas no dominadas con su costo mínimo. Tras $i$ línea

- **Nuevo del equipo:**
  > La comparación entre los dos procedimientos usó las 175 listas reales del corpus y 24 hogares sintéticos de 2 a 8 hijos, armados con listas consecutivas de un mismo colegio, con entre 21 y 313 líneas decidibles (Sección ). La programación dinámica reprodujo el frente exacto en las 65 de 65 listas en que corre la enumeración y en 1.000 instancias aleatorias, y en las listas reales tardó 0,64 ms y ocupó 0,12 MiB en la mediana, frente a 243 ms y 0,82 MiB de NSGA-II (Apple M4, un hilo). Su costo, sin embargo, crece con el número de líneas. Su memoria medida crece como \(n^{2{,}61}\), frente a \(n^{0{,}83}\) en NSGA-II, y en el hogar de 8 hijos y 313 líneas llegó a 297 MiB frente a 12,6 MiB, con 2,56 s frente a 1,46 s (Figuras y ).

- **Nuevo del equipo:**
  > La programación dinámica es exacta mientras los objetivos se descompongan por línea y se agreguen en contadores acotados, y hay reglas del kit que no tienen esa forma. La coherencia del personaje entre las líneas de un hijo, el empaque compartido entre líneas, como las herramientas que piden varias materias o la consolidación entre hermanos, y un costo fijo por tienda hacen que el costo de una línea dependa de lo que eligieron las demás. Para representarlas, el estado tendría que llevar el personaje elegido, la demanda acumulada de cada producto compartido o el conjunto de tiendas usadas, y el número de estados crecería de forma exponencial [cita]. En la versión construida, esas reglas se aplican sobre la asignación elegida, y el tope de A tu Medida se verifica sobre el total consolidado.

- **Nuevo del equipo:**
  > Por eso NSGA-II es el motor general del sistema. Esas reglas solo cambiarían su función de evaluación, su memoria queda acotada porque \(N \le 100\), y su tiempo, que crece como \(n^{0{,}49}\), cumple con holgura los 20 s de RNF03, con un máximo de 1,46 s en el hogar más grande. Con la siembra, sus kits proyectados igualaron el óptimo en el 100% de las listas en los escenarios Ahorrador, Premium y Fan, y en el 98,9% con presupuesto, con un hipervolumen relativo medio de 0,9981, un mínimo de 0,9511 y el frente exacto en el 81,6% de las listas. La siembra explica buena parte de ese resultado, porque sin ella el mismo algoritmo igualó el Premium en el 6,3% de las listas y el presupuesto en el 18,4%, con un hipervolumen relativo de 0,87. La programación dinámica y la enumeración cumplen el papel de referencia exacta en la evaluación, y la Tabla reúne las cifras.

- **Nuevo del equipo:**
  > \subsection{Kits, recomendación y personalización}

  - *Lo más parecido en la versión actual* (resultados.tex, similitud 0.54): \subsection{Recuperación y decisión de resolución}

- **Nuevo del equipo:**
  > La pantalla de kits presenta las propuestas del hogar con su total y abre la recomendada, marcada con su razón (Figura ). Completa RF03 y la parte de RF04 que permite ajustar el kit, dentro del OE4. En el hogar de la figura, con un personaje pedido y el punto medio de gasto, los kits costaban \$661.311 el Ahorrador, \$687.320 el Fan, \$941.101 A tu Medida y \$1.273.928 el Premium, y se marcó el Fan con la razón ``Pediste un personaje, así que este es el kit que lo trae''; de los 78 renglones, 64 iban al carrito y ninguno era un hueco del catálogo, y el Fan llevaba el personaje en dos productos, el cuaderno y la carpeta. Cada propuesta muestra los productos, las unidades según el empaque y un total que suma solo lo que Tukit puede entregar, y los renglones se agrupan en diez clases que, siguiendo las pautas de interacción con sistemas de inteligencia artificial [cita], dicen lo que el sistema sabe y lo que desconoce.

- **Nuevo del equipo:**
  > Entre los kits armados se marca uno, sin ocultar los demás, con una regla derivada de la encuesta, que tuvo 65 respuestas y 60 analizables. Se recomienda el Fan si se pidió un personaje, y si no, A tu Medida cuando ese kit existe. Si el acudiente acepta un sobreprecio de al menos el 10%, decide la utilidad multiatributo de sus pesos [cita], aplicada después de construir el frente [cita], \begin{equation} U(\mathbf{x}) = w_{\mathrm{precio}}\,u_{\mathrm{costo}}(\mathbf{x}) + (w_{\mathrm{marca}} + w_{\mathrm{calidad}})\,u_{\mathrm{fidelidad}}(\mathbf{x}) + w_{\mathrm{personaje}}\,u_{\mathrm{personaje}}(\mathbf{x}), \end{equation} con cada \(u\) lineal entre 0 y 1 sobre el rango de los kits, y se marca el Premium cuando esa utilidad lo prefiere; en otro caso se marca el Ahorrador, porque 42 de las 60 familias pagarían como máximo un 5% más. Los pesos por omisión salen de la pregunta de la encuesta que ordena las prioridades, con 0,285 para el precio, 0,273 para la marca, 0,255 para la calidad y 0,187 para el personaje, y al perturbarlos con una desviación de 0,05, 0,10 y 0,20 el kit recomendado se mantuvo en el 96,5, el 98,6 y el 94,6% de los sorteos. Pocas opciones bien diferenciadas, con una marcada, facilitan la decisión sin quitar libertad [cita]. Si el kit marcado no cabe en el tope declarado, la marca pasa al de mejor marca que sí cabe, y si ninguno cabe, al más barato, con una razón que dice cuánto cuesta.

- **Nuevo del equipo:**
  > El kit se presenta con lo que va al carrito primero y completo, y lo que no se cobra en Tukit, como libros, uniformes y licencias, en un bloque compacto agrupado por lo que el acudiente debe hacer con ello. Una línea sin precio dice la instrucción del colegio, por ejemplo que el libro se compra en librería, que el útil se compra en papelería o que la prenda se pregunta en el colegio. Cada línea abre un carrusel con sus opciones revisadas y la diferencia de precio de cada una en el total, como pide RF04 (Figura ), y el acudiente puede también descartarla porque ya la tiene, de modo que deja de sumar al total y se puede volver a poner. En el ejemplo, el acudiente cambió la Biblia Latinoamericana de letra normal, de \$75.223, por la de letra grande, de \$105.000, y el total del kit Fan pasó de \$687.320 a \$717.097, sin tocar los demás kits. El cambio y el descarte se guardan en el trabajo y se aplican cada vez que se leen los kits, con la misma aritmética del armado, y el sugerido queda como alternativa para volver a él.

- **Nuevo del equipo:**
  > En la página de kits, un chat flotante permite pedir cambios en lenguaje natural, como algo más barato en los cuadernos, una mejor marca o variar el personaje, y preguntar qué se puede hacer, como parte de RF03 y RF04. El asistente solo propone. Cada propuesta muestra el producto actual, el propuesto y el ahorro, y el acudiente la acepta o la rechaza, de a una o todas en secuencia, por la misma ruta con que cambia un producto en el carrusel (Figura ). Una llamada del modelo produce como máximo 5 propuestas, y un pedido sobre una categoría, como máximo 12. En el formulario de inicio el asistente va apagado, y allí se usa el formulario guiado.

- **Nuevo del equipo:**
  > El modelo es gemini-3.5-flash-lite con temperatura 0, y su diseño trata como datos no confiables el texto del acudiente y las descripciones de los renglones, que vienen de las listas escolares [cita]. Cada ruta tiene un plan fijo en el código, y el modelo solo elige una función de una lista blanca [cita]. Responde con referencias cortas a los renglones, que el servidor resuelve contra sus propios datos, de modo que los precios, los productos y los textos que ve el acudiente salen del servidor y de plantillas [cita]. Antes de la llamada se redactan el correo, el teléfono, la dirección, los enlaces y el nombre de un hijo, y los renglones se acotan a 80 caracteres y van entre marcas que el modelo trata como datos. La salida se valida con un esquema estricto que rechaza campos de más, el resultado de una función no vuelve al modelo y el asistente no escribe nada por sí mismo, en línea con RNF02. Con casos de ataque cuya condición de éxito se fijó antes de correr el modelo [cita], el asistente fue útil en 58 de 70 casos, no cedió en ninguno de 81 ataques y respondió en 1.000 ms en la mediana.

- **Nuevo del equipo:**
  > Cuando el acudiente confirma un kit, el servicio de comercio crea el pedido, como parte de RF04. Antes de cerrarlo, vuelve a leer el precio de cada línea y, si alguno cambió, no lo cierra; luego reserva el inventario por 24 horas, plazo en que el pedido se paga o se cancela, y cancelar consulta antes a la pasarela si hay un pago en curso. La dirección se busca en OpenStreetMap con el botón Buscar o con la tecla Enter, y el acudiente confirma el punto arrastrando un pin sobre el mapa o moviéndolo con las flechas del teclado (Figura ). La búsqueda pasa por el servidor de la aplicación, con una consulta por segundo y una caché, y el pedido guarda la latitud y la longitud del punto; si el servicio de mapas no responde, el campo sigue como texto libre.

- **Nuevo del equipo:**
  > El pago se abre en el widget de Wompi sobre la página del kit, y con PSE el banco toma la pestaña y lo devuelve a una página de resultado. El servidor firma los datos del widget con el SHA-256 de la referencia, el monto, la moneda y un secreto que nunca llega al navegador, y comercio guarda solo la referencia, el estado, el medio y el monto de la transacción, sin datos de tarjeta, como exige RNF01. La confirmación llega por el aviso firmado de la pasarela y por una consulta de servidor a servidor, y ambas pasan por el mismo procedimiento idempotente, para que un pago se aplique una sola vez.

- **Nuevo del equipo:**
  > \subsection{Seguimiento del pedido, retracto y atención de casos}

  - *Lo más parecido en la versión actual* (analisisProblema.tex, similitud 0.49): \subsubsection{Requerimientos más importantes}

- **Nuevo del equipo:**
  > Una vez pagado, el pedido pasa por en preparación, despachado, en reparto y entregado, con la incidencia como desvío desde el que se vuelve a la preparación, y el acudiente lo sigue en una línea de tiempo en el detalle del pedido, con la hora de cada paso y el repartidor asignado (Figura ), lo que completa el ciclo de compra de RF04. Cada cambio produce un aviso por correo o por un enlace de WhatsApp, con el contacto resuelto contra identidad al enviar y sin guardarlo. El evento se escribe en la bandeja de salida de su servicio en la misma transacción que el cambio, RabbitMQ lo entrega cuando está disponible, y como la notificación se registra antes de marcarlo como publicado, un evento produce un solo aviso aunque llegue repetido, en línea con RNF08.

- **Nuevo del equipo:**
  > El mismo detalle permite ejercer el derecho de retracto del artículo 47 de la Ley 1480 de 2011 [cita] dentro de los cinco días hábiles siguientes a la entrega, y muestra la fecha en que vence (Figura , izquierda). El plazo se cuenta en la hora de Bogotá con un calendario de días hábiles que descuenta los festivos de Colombia, y vencido el plazo, el servidor rechaza la solicitud con un código 409. Antes de la entrega, el retracto cancela el pedido y marca el pago para reembolso; después, registra la solicitud para que el equipo coordine la recogida y el reembolso, y pedirlo dos veces no abre dos solicitudes. El pie del sitio enlaza las páginas legales de términos y condiciones, de la política de tratamiento de datos y de retracto y garantía.

- **Nuevo del equipo:**
  > En su panel, el acudiente abre en Mis casos peticiones, quejas, reclamos y sugerencias, y problemas de pago o de entrega, los sigue y les agrega mensajes (Figura , derecha). Cada caso nace con una prioridad y un vencimiento según su término, de 15 días para las peticiones, quejas y reclamos, conforme a la Ley 1755 de 2015 [cita], de 24 horas para un problema de pago y de 48 para uno de entrega. El equipo los atiende en una bandeja de la consola ordenada por prioridad y vencimiento, y en el detalle de cada caso lee la conversación, lo vincula a un pedido, lo mueve entre los estados abierto, en gestión, esperando a un tercero, resuelto y cerrado, y responde con hasta 2.000 caracteres. La respuesta y su aviso al acudiente se guardan en la misma transacción, y responder un caso recién abierto lo pasa a en gestión.

- **Nuevo del equipo:**
  > \subsection{Privacidad y supresión de los datos}

  - *Lo más parecido en la versión actual* (resultados.tex, similitud 0.54): \subsection{Recuperación y decisión de resolución}

- **Nuevo del equipo:**
  > La página Privacidad y mis datos muestra al acudiente lo que Tukit guarda de él, con su cuenta, en la que el correo y el celular aparecen enmascarados, el apodo y el grado de sus hijos, sus direcciones, sus autorizaciones con su versión y su fecha y el número de sus pedidos, casos y solicitudes de kit (Figura ). Desde allí descarga una copia completa de esos datos, retira su autorización sin cerrar la cuenta y pide la supresión, que exige escribir una frase de confirmación, conforme a la Ley 1581 de 2012 y al Decreto 1377 de 2013 [cita] y como pide RNF02. Identidad arma el inventario consultando por HTTP a comercio, operación e inteligencia con el mismo token del titular, y si uno no responde, su parte aparece como no disponible y el resto se muestra.

- **Nuevo del equipo:**
  > La supresión anonimiza la cuenta en identidad, que borra los datos personales, las direcciones, los apodos de los hijos y el perfil, y publica un evento de titular suprimido que RabbitMQ lleva a los otros tres servicios. Comercio enmascara los datos del envío, operación redacta el texto de los casos e inteligencia borra las preferencias y el documento subido de la lista. Cada servicio anota su confirmación en la bandeja de salida en la misma transacción en que borra, de modo que repetir el evento no cambia nada, y la solicitud se completa cuando confirman los tres. Se conserva, sin los datos de la persona, lo que la ley obliga a guardar, como los pedidos, sus líneas, los pagos y el historial, y el estado, la categoría y las fechas de los casos. Un proceso de fondo reenvía el evento de las solicitudes que siguen sin completarse y avisa cuando una supera los 15 días hábiles del reclamo.

- **Nuevo del equipo:**
  > \subsection{Revisión humana de las listas}

  - *Lo más parecido en la versión actual* (disenoSolucion.tex, similitud 0.46): \subsection{Descomposición en seis desplegables}

- **Nuevo del equipo:**
  > La revisión humana impide que un producto equivocado llegue a una familia, y atiende RF05 y la parte de RF02 que remite a una persona los renglones dudosos [cita]. La unidad de la cola es una versión de lista sin revisar, con lo que espera un acudiente primero, y cada versión se revisa en cuatro paneles, con el documento original, la lectura del modelo por página, los renglones con su concepto, candidatos y confianza, que se pueden editar, y la previsualización de los kits con el botón de aprobar (Figura ). Aprobar la vuelve la lista oficial verificada de su colegio y grado, arma, publica y avisa el kit del acudiente que la subió y genera los kits canónicos del grado para las demás familias.

- **Nuevo del equipo:**
  > En la lectura real de la Sección , 76 de los 78 renglones (97%) quedaron con concepto, como ``archivador de fuelle, oficio, 13 bolsillos'', emparejado con Carpeta y los atributos tipo fuelle y tamaño oficio, y los dos restantes, un texto de editorial y ``un compás'', pasaron a revisión; el revisor asignó el segundo al concepto Compás. Casos como ``bata para artes con mangas'', emparejada con la bata de laboratorio, muestran por qué una persona revisa la lista completa antes de publicarla. Un trabajo en espera de revisión se presenta además como una matriz, con una fila por concepto y una columna por kit, en la que el revisor valida en lote los ambiguos o fija otro producto antes de aprobar.

- **Nuevo del equipo:**
  > El catálogo es propio y curado. El OE1 lo construyó a partir de la demanda real de las listas y las Fases 3 y 4 lo usan; atiende RF02 y RF03 y recorrió la comprensión y la preparación de los datos de CRISP-DM. Sobre el corpus de la caracterización, de 175 listas de 17 colegios y 4.719 renglones, el catálogo de la versión capturada tenía 1.078 productos, todos con foto y revisados, en 132 conceptos, 93 de ellos con los tres niveles de marca, y ofertas de 10 tiendas, entre ellas Éxito, Panamericana y Papelería Grancentral; el precio que se muestra es el menor vigente.

- **Nuevo del equipo:**
  > El equipo lo administra desde la consola, con filtros por concepto, nivel y personaje, edición de cada producto y reclasificación en otro concepto (Figura ). Para un renglón que el catálogo no tiene, el sistema consulta las tiendas, conserva las ofertas disponibles con precio entre \$1.000 y \$400.000 cuyo nombre contenga la cabeza del renglón y propone tres, en las posiciones \(\lfloor N/6\rfloor\), \(\lfloor N/2\rfloor\) y \(\lfloor 5N/6\rfloor\) por precio, que una persona aprueba antes de que entren al catálogo.

- **Nuevo del equipo:**
  > Dos algoritmos garantizan lo que la resolución y la optimización suponen. El empaque se extrae del nombre del producto con la regla de que ``x \(N\)'' cuenta empaques salvo que lo siga una unidad de medida, y la nivelación hace que, en cada escalera de un mismo concepto y personaje, el nivel de marca crezca con el precio, reasignando las mismas etiquetas en orden de precio en \(O(k \log k)\). La curaduría se exporta a archivos CSV versionados, de modo que el catálogo se reconstruye sin red.

- **Nuevo del equipo:**
  > En el tablero de logística, el operador ve los pedidos con indicadores globales, un mapa de las entregas pendientes y, debajo, los filtros y la tabla de pedidos (Figura ), y esta funcionalidad cierra el ciclo de RF04 dentro del OE4. El mapa agrupa las entregas por colegio, con el número de pedidos y de hijos de cada uno, y ubica las direcciones sin definir el orden de reparto. El servidor de la consola las geocodifica con Nominatim, con caché y una consulta por segundo, y si el servicio no responde, la sección queda como una lista sin marcadores. El operador avanza cada pedido un paso a la vez o lo pasa a incidencia con su tipo, siguiendo una tabla única de transiciones legales que comparten el tablero, el pago y el barredor de reservas; con reparto propio, un despacho exige el nombre y el celular del repartidor. Cada paso queda en el historial con el operador que lo dio, y el pedido de la demostración recorrió de pagado a entregado en unos dos minutos.

- **Nuevo del equipo:**
  > Los procesos de fondo sobreviven a las caídas pasajeras de la base o del intermediario, con una espera de 1 s que se duplica hasta 30 s, y las llamadas entre servicios pasan por un disyuntor por destino que se abre tras cinco fallos y prueba de nuevo a los 30 s [cita]; solo las consultas idempotentes se reintentan, porque reintentar una escritura podría cobrar dos veces, como pide RNF08.

- **Nuevo del equipo:**
  > \subsection{Métricas y observabilidad}

- **Nuevo del equipo:**
  > La página de inicio de la consola reúne el pulso de la operación con la cola de revisión, el estado de los trabajos, el catálogo, los pedidos, los casos y los colegios (Figura ), y cada grupo se lee por separado, de modo que si un servicio no responde solo se oculta su sección. Las métricas de un colegio, calculadas en vivo, son los kits publicados, la cobertura de líneas comprables con producto real y el ahorro de la consolidación; en la versión capturada, el Colegio Agustiniano Ciudad Salitre tenía una cobertura del 90% con 202 kits. Cada etapa del procesamiento registra su duración, y los servicios emiten métricas y trazas de OpenTelemetry que se consultan en Jaeger, lo que sostiene la medición de RNF03, RNF05 y RNF07.

- **Nuevo del equipo:**
  > \subsection{Comparación de alternativas}

  - *Lo más parecido en la versión actual* (disenoSolucion.tex, similitud 0.47): \subsubsection{Asignación de lenguajes: una decisión medida}

- **Nuevo del equipo:**
  > Cada componente que depende de datos se eligió comparando alternativas en las etapas de modelado y evaluación de CRISP-DM. Cada comparación responde una pregunta con sus propios datos y su propia métrica, que se describen en su apartado, junto con su conclusión y la forma en que orientó el sistema construido.\footnote{Los programas, los datos y los resultados de estas comparaciones están reunidos en el repositorio Tukit-Benchmarks de la organización, \url{https://github.com/Tukit-Col/Tukit-Benchmarks}.}

- **Nuevo del equipo:**
  > La primera comparación pregunta qué motor lee mejor una lista de útiles. Usó CGS-10, un conjunto de 10 listas reales de colegios de Teusaquillo y Fontibón, de entre 2 y 39 páginas, con 1.293 ítems de referencia, y comparó el reconocimiento de caracteres con Tesseract y reglas [cita], Google Cloud Vision con las mismas reglas, GOT-OCR2.0 [cita], Docling [cita] y el modelo multimodal gemini-3.5-flash-lite con salida JSON. La métrica es la precisión, la exhaustividad y el F1 por ítem (micro) y por documento (macro), con un emparejamiento que acepta una similitud de texto de al menos 0,75, más la latencia mediana y el costo por documento (Tabla ).

- **Nuevo del equipo:**
  > \smallskip {\footnotesize \textsuperscript{a} La mediana está dominada por la espera de la cuota gratuita de la API durante la comparación.

- **Nuevo del equipo:**
  > El modelo multimodal obtuvo el mayor F1 en todas las columnas, con 0,948 por ítem frente a 0,673 del siguiente, y en los documentos de hasta cinco páginas, la comparación más pareja entre motores, llegó a 0,987 frente a valores entre 0,695 y 0,789. Su costo fue de 0,0017 dólares por documento. Por eso el sistema lee las páginas con el modelo multimodal, con la respuesta validada por esquema y la regla de todo o nada, y su latencia se reparte entre las familias de un grado gracias a la memoización.

- **Nuevo del equipo:**
  > La segunda comparación pregunta qué modelo representa mejor un renglón para encontrar su producto. Usó 542 renglones de cinco listas reales, cada uno con cinco candidatos del catálogo anotados a mano, y midió, sobre los 392 renglones que tienen algún candidato correcto, la precisión del primer puesto (P@1) y el rango recíproco medio (MRR) al reordenar los candidatos por coseno, y sobre los 2.710 pares, el área bajo la curva ROC (Tabla ). Las alternativas fueron una señal léxica de n-gramas de caracteres de 3 a 5, jina-embeddings-v2-base-es [cita], all-MiniLM-L6-v2, multilingual-e5-large [cita] y dos modelos multilingües de paráfrasis [cita].

- **Nuevo del equipo:**
  > Con renglones reales, la señal léxica es la más fuerte, y jina-embeddings-v2-base-es es el mejor modelo neuronal, y multilingual-e5-large supera a paraphrase-multilingual-mpnet-base-v2 en el mismo orden que en las tareas generales de MTEB [cita]. El sistema construido responde a esa evidencia dejando que la estructura léxica decida y usando los vectores solo para desempatar o rescatar sinónimos, y con ese papel acotado emplea gemini-embedding-001, del mismo proveedor que la percepción, lo que evita alojar un modelo en una GPU.

- **Nuevo del equipo:**
  > La tercera comparación pregunta si conviene la búsqueda vectorial exacta o un índice aproximado. Usó 6.122 productos reales representados con multilingual-e5-large, de 1.024 dimensiones, y 381 consultas tomadas de renglones reales, y midió el Recall@10 frente a la búsqueda exacta y los milisegundos por consulta, una a la vez y en un hilo, para los índices IVF [cita] y HNSW [cita] de FAISS [cita] (Tabla ).

- **Nuevo del equipo:**
  > Con un catálogo de miles de productos, la búsqueda exacta cuesta menos de un milisegundo y no pierde vecinos, mientras que los índices aproximados ganan tiempo a costa de entre el 5 y el 17% de los vecinos. Por eso el sistema guarda los vectores en la base PostgreSQL del catálogo con pgvector, junto al producto y sin un segundo almacén que sincronizar [cita], y clasifica con un recorrido exacto sobre los centroides de los conceptos; la base conserva un índice HNSW para cuando el catálogo crezca, y la comparación indica usarlo con un ef\_search de al menos 100.

- **Nuevo del equipo:**
  > La cuarta comparación pregunta si la correspondencia debe ser léxica, vectorial o híbrida. Usó 30 casos de listas en lenguaje natural, 20 en prosa y 10 en forma de lista, sobre un catálogo de 29 productos, y midió el F1, la precisión y la exhaustividad promedio por caso de los ítems recuperados (Tabla ). Sobre los 2.710 pares anotados de la comparación anterior, el área bajo la curva ROC de cada señal fue de 0,728 para la léxica, 0,805 para la densa, 0,739 para la fusión recíproca de rangos [cita], 0,843 para el máximo de las dos y 0,880 para un reordenador cruzado [cita].

- **Nuevo del equipo:**
  > La estructura léxica es la señal más confiable y la más barata, y la fusión por rangos mide peor que su propio canal denso, de modo que no sirve como confianza. Esa evidencia orientó la fusión con guardas del sistema, en la que la cabeza anclada decide qué conceptos son admisibles y el coseno solo desempata o rescata un sinónimo con \(\kappa \ge 0{,}86\).

- **Nuevo del equipo:**
  > La quinta comparación pregunta cuándo aceptar de forma automática el primer candidato de un renglón y cuándo remitirlo a una persona. El prototipo comparó un umbral único con reglas que añadían condiciones sobre el segundo candidato y con un verificador basado en un modelo de lenguaje para los renglones dudosos, y el sistema construido adopta la regla más simple de auditar, un solo umbral sobre su puntaje híbrido, \(\tau = 0{,}75\) por omisión, que se ajusta por configuración sin cambiar el código. Los renglones entre 0,5 y \(\tau\) pasan a la revisión humana de la lista (Sección ), de modo que un valor conservador protege lo que llega a las familias a cambio de enviar más renglones al revisor.

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > ~~\subsection{Optimización del kit}~~ **\subsubsection{Optimización}**

  - *Lo más parecido en la versión actual* (desarrolloSolucion.tex, similitud 0.74): \subsection{Optimización del kit}

- **Nuevo del equipo:**
  > La última comparación pregunta qué procedimiento construye mejor el frente de los cuatro objetivos y los kits proyectados. Usó las 175 listas reales del corpus, de las cuales 174 tienen líneas decidibles, con 16,9 líneas en promedio y 64 como máximo, 2,35 candidatos por línea y hasta \(4{,}4 \times 10^{17}\) combinaciones, y los 24 hogares sintéticos de la Sección . Midió el tiempo de pared en un Apple M4 con un hilo, el pico de memoria, el hipervolumen relativo al del frente exacto (HV/HV*) [cita], la fracción de listas con el frente exacto y la de kits proyectados que igualan el óptimo en los escenarios Ahorrador, Premium, Fan y presupuesto (Tabla ).

- **Nuevo del equipo:**
  > \smallskip {\scriptsize\raggedright \textsuperscript{a} En las 65 listas con hasta 60.000 combinaciones; el sistema enumera hasta 4.096, con un máximo de 0,34 s. \textsuperscript{b} Comparación previa con las mismas listas, en su mejor modalidad para cada escenario.

- **Nuevo del equipo:**
  > La programación dinámica es exacta y la más rápida en las listas reales, y NSGA-II con siembra iguala el óptimo en los kits Ahorrador, Premium y Fan y en el 98,9% de los de presupuesto; con cinco semillas por lista, su hipervolumen relativo medio fue de 0,9980 y el frente fue exacto en el 77,5% de las 870 corridas. El voraz es tan rápido como la programación dinámica, pero su frente cubre poco, y Laya [cita], un modelo de decisión de propósito general, igualó el óptimo en como mucho el 6% de los Ahorrador, de modo que una formulación explícita sigue siendo necesaria. Por eso el sistema enumera de forma exacta los espacios pequeños y usa NSGA-II sembrado en los demás, y la programación dinámica sirve de referencia exacta en la evaluación.

- **Figuras y tablas nuevas:** Formulario de inicio en el modo ``Soy nuevo usuario'', con los datos del acudiente y la ca; Hijo de un colegio aliado en un grado sin lista verificada, para el que el formulario ofre; Pantalla de espera de una solicitud, con la lectura de la lista, la normalización y la bús; Tiempo de pared de los procedimientos de optimización frente al número de líneas decidible; Pico de memoria de los procedimientos de optimización frente al número de líneas decidible; Kits del hogar con el total de cada uno, el Fan recomendado con su razón, los productos co; Carrusel de opciones del renglón ``Biblia católica'' en el kit Fan, con la diferencia de c; Asistente del kit con una propuesta que cambia el cuaderno cuadriculado de Stitch por uno ; Dirección de entrega del pedido buscada en OpenStreetMap, con el punto confirmado en el ma; Seguimiento del pedido F8C47935 hasta su entrega, con la hora de cada paso y el repartidor; Plazo del derecho de retracto en el detalle del pedido (izquierda) y un caso de Mis casos ; Privacidad y mis datos, con el inventario de la cuenta, los hijos, las direcciones y las a; Revisión de la lista de Cuarto del Colegio Agustiniano Ciudad Salitre, con el PDF original; Catálogo de productos en la consola, con los filtros por concepto, nivel y personaje y las; Tablero de logística con los pedidos en curso, con incidencia y entregados, los ingresos c; Panel de la operación con la cola de revisión, el estado de los trabajos y el resumen del 


## resultados.tex  (4 párrafos y 0 figuras/tablas del equipo que no están en la versión actual)

- **Editado por el equipo** (cambios en negrita, lo que quitaron tachado):
  > Este capítulo presenta los resultados de las Fases 3, 4 y 5 del proyecto, ligadas a los objetivos tercero, cuarto y quinto. Los de los componentes de datos y de recuperación siguen la fase de evaluación de CRISP-DM, y los del código, el plan del informe de pruebas (Sección ). Cada cifra va con su muestra, su condición y su grado de respaldo: recalculada desde una salida conservada, respaldada por una salida existente o solo reportada. Cuando dos fuentes discrepan o falta el programa que produjo una cifra, el texto lo dice en lugar de dar un valor. **El capítulo cierra con la validación financiera del modelo de negocio, que proyecta sus resultados y su balance general a tres años.**

- **Nuevo del equipo:**
  > La validación financiera comprueba si el modelo de negocio descrito en la Sección es sostenible, mediante una proyección a tres años construida sobre supuestos del equipo. Cada kit tiene un valor promedio de \$180.000, sobre el cual Tukit recibe una comisión del 15%, es decir, \$27.000 por venta. A ese ingreso se le restan los costos variables, que corresponden a la comisión de la pasarela de pagos y al uso de los modelos de inteligencia artificial y suman cerca de \$7.500 por kit, lo que deja una contribución de \$19.500. Con costos fijos de \$15.000.000 en el primer año, el punto de equilibrio se alcanza con cerca de 770 kits, frente a los 1.500 que se proyectan para ese año con un número reducido de colegios aliados. La Tabla presenta la proyección completa, que supone 8.000 kits en el segundo año, con cerca de diez colegios, y 25.000 en el tercero, con cerca de treinta.

- **Nuevo del equipo:**
  > El plan requiere una inversión inicial de \$70.000.000, aportada por los socios, de la cual el 40% se destina a desarrollo, el 15% a infraestructura, el 25% a mercadeo y el 20% a capital de trabajo y trámites legales. Al descontar los resultados operativos de los tres años a una tasa del 20% anual, el valor presente neto es de cerca de \$235 millones. La Tabla proyecta el balance general al cierre de cada año. La inversión se registra como aporte de capital, sin deuda financiera. El desarrollo y la infraestructura, que suman \$38,5 millones, forman la plataforma tecnológica, amortizada en línea recta a cinco años, mientras que el mercadeo es un gasto del primer año y el 20% restante permanece en caja. Los cobros y los pagos a las tiendas y a la pasarela se liquidan dentro del mismo año, y las cifras se presentan antes de impuestos.

- **Nuevo del equipo:**
  > El primer año cierra con una pérdida contable de \$10,95 millones, porque absorbe el mercadeo de lanzamiento y la amortización de la plataforma, aunque la operación ya genera un resultado positivo de \$14,25 millones y la caja se mantiene en \$28,25 millones, de modo que la inversión inicial alcanza para financiar el arranque sin recurrir a deuda. Desde el segundo año, las utilidades superan esa pérdida y el patrimonio crece con los resultados retenidos. Estas cifras dependen, sobre todo, de la velocidad con que se incorporen nuevos colegios, que determina el número de kits vendidos.


## conclusiones.tex  (1 párrafos y 0 figuras/tablas del equipo que no están en la versión actual)

- **Nuevo del equipo:**
  > Con el sistema en producción, el paso siguiente es el lanzamiento comercial en el colegio piloto, con la institución como canal de entrada a sus familias. La estrategia concentra la promoción en la temporada de diciembre a enero, cuando las familias preparan la compra, y se apoya en un programa de referidos entre padres del mismo colegio y en recordatorios por WhatsApp para que carguen su lista antes del inicio de clases. El lanzamiento se seguirá con cuatro indicadores, que son la conversión de lista cargada a kit comprado, el costo de adquisición por cliente, la activación de los colegios y la recompra en la temporada siguiente, para reemplazar los supuestos del modelo financiero por mediciones reales.
