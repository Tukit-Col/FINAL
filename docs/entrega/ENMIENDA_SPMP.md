# Enmienda al SPMP v3 (alineación con el producto final y con la VFP v4)

Documento de trabajo, no es una versión aprobada del SPMP. Fuente: `SPMP/SPMP_ISIS2610G19_v3.docx` (fecha de la fila de versión: 23 de agosto de 2026, v3.0). No se modificó el original. Cada ítem sigue el patrón Texto actual (cita textual) / Texto de reemplazo / Por qué. Los números de línea son los del texto convertido del docx (`pandoc -t plain`) y sirven solo para ubicar. Producto de referencia: rama `validacion/oe5`. Fechas reales de OE5, confirmadas por la coordinación: ronda 1 (formativa) el 31-oct-2026 y ronda 2 (sumativa) el 2-nov-2026. El plan del 29 y 30 de octubre se registra como cambio de cronograma en la fila de versión v4.0.

## S1. Aplicación móvil nativa (React Native) pasa a PWA, con empaquetado híbrido Capacitor como trabajo futuro

**S1.a Objetivo específico 4 (línea 272)**

Texto actual: "...integradas en el sistema, con interfaz web progresiva y aplicación móvil nativa para iOS y Android."

Texto de reemplazo: "...integradas en el sistema mediante una interfaz web progresiva (PWA) e integradas con la pasarela de pagos para el cierre transaccional de la compra."

Por qué: el código entregado es una PWA. No existe app nativa ni empaquetado Capacitor en el repositorio. Es la misma redacción de OE4 de la VFP v4.

**S1.b Tabla de tecnologías, fila "Aplicación móvil React Native" (línea 527)**

Texto actual: "Aplicación móvil React Native Aplicación nativa para iOS y Android sobre las mismas APIs del backend que consume la PWA. 4 [43]"

Texto de reemplazo: "PWA instalable (Next.js) Aplicación web progresiva que se instala en el teléfono y consume las mismas APIs del backend. El empaquetado híbrido con Capacitor para las tiendas de aplicaciones queda como trabajo futuro. 4 [43]"

Por qué: la fila describe un componente que no se construyó. La referencia [43] debe revisarse: si es documentación de React Native, se sustituye por la de PWA o Capacitor.

**S1.c Paquete S6 del cronograma (línea 961)**

Texto actual: "S6. Aplicación móvil nativa Aplicación iOS y Android sobre las mismas APIs del backend, con captura nativa de cámara, consulta sin conexión de kits y pedidos, y verificación del modelo de checkout contra las políticas de App Store y Google Play antes de publicar. Cierra AM-01 a AM-04."

Texto de reemplazo: "S6. Aplicación web progresiva Captura de la lista con la cámara del navegador, instalación en el teléfono y verificación de la interfaz en dispositivos móviles. Los requisitos AM-01 a AM-04 que exigen aplicación nativa o consulta sin conexión quedan como trabajo futuro."

Por qué: el paquete fue acotado a lo que sí existe. Confirmar con el SRS qué AM quedan cubiertos por la PWA.

**S1.d Fase 4 (línea 404, última frase), riesgo R-06 (línea 1207) y fila de cronograma OE4 (línea 1009)**

Texto actual (R-06, línea 1207): "...la aplicación móvil nativa, la operación de última milla y el despliegue productivo con endurecimiento no tienen paquete de trabajo en la WBS vigente."
Texto actual (línea 1009): "Aplicación móvil nativa, última milla y despliegue productivo quedan fuera de la WBS vigente (riesgo R-06)."

Texto de reemplazo: "La aplicación móvil nativa (empaquetado híbrido), la operación de última milla y el despliegue productivo gestionado quedan como trabajo futuro (riesgo R-06). El sistema se entrega como PWA con despliegue local reproducible."

Por qué: el texto vigente ya excluía estas piezas; solo se ajusta el nombre del empaquetado y se enlaza con la sección de trabajo futuro de la VFP v4.

**S1.e Fila de versión (línea 146)**

Texto actual: "se consolida el alcance en una sola versión del sistema (incluida la app móvil nativa, la última milla, los pagos productivos y la logística inversa)"

Texto de reemplazo: añadir una fila v4.0 (fecha de la edición real, no retroactiva): "Alineación con el producto final: PWA en lugar de app nativa, Wompi en lugar de PSE/ePayco, despliegue local con Minikube, cuatro funciones objetivo, muestra de validación y trabajo futuro. Cambio de cronograma: las sesiones de validación previstas el 29 y 30 de octubre se realizaron el 31 de octubre (ronda 1) y el 2 de noviembre de 2026 (ronda 2). Alcance reducido respecto de v3: panel propio del colegio y ajuste de presupuesto en vivo, que pasan a trabajo futuro."

Por qué: la fila v3.0 no se reescribe; la historia queda visible.

## S2. Pasarela de pagos: PSE / ePayco pasa a Wompi (sandbox)

**S2.a Tabla de tecnologías (línea 535)**

Texto actual: "Pasarela de pagos PSE / ePayco Procesamiento productivo del pago del kit y reversión en casos de retracto. 4 [13]"

Texto de reemplazo: "Pasarela de pagos Wompi (sandbox, widget y webhook de eventos) Procesamiento del pago del kit con tarjeta, PSE y otros medios. El modo por defecto es simulado (WOMPI_MODO) y el modo sandbox usa llaves de prueba. El retracto (Ley 1480 de 2011, art. 47) se gestiona como caso de la orden. 4 [13]"

Por qué: el código integra Wompi (ADR 0033 widget, ADR 0034 webhook). ePayco y Stripe se evaluaron y descartaron (ADR 0011). Comisiones de referencia: PSE cerca de 1,49 % y tarjetas cerca de 2,99 % (Wompi); ePayco entre 2,79 y 3,50 %. Verificar vigencia antes de citar en el documento.

**S2.b Paquete S4 (línea 957)**

Texto actual: "S4. Fulfillment y pagos Integración productiva con PSE y ePayco, re-verificación de precio y disponibilidad de los SKUs antes de cobrar, registro y ciclo de vida de la orden, y derecho de retracto con reversión del pago."

Texto de reemplazo: "S4. Fulfillment y pagos Integración con Wompi en sandbox (widget y webhook), re-verificación de precio y disponibilidad de los SKUs antes de cobrar, registro y ciclo de vida de la orden, y derecho de retracto con reversión del pago (5 días hábiles para retractarse y 30 días calendario para el reembolso)."

Por qué: alinea con el producto y con las páginas legales (Ley 1480, Ley 1581).

**S2.c Riesgo R-09 (línea 1213)**

Texto actual: "R-09 PSE/ePayco exige registro empresarial y certificación de Tukit como comercio: es una dependencia bloqueante del flujo de pago."

Texto de reemplazo: "R-09 Wompi exige registro empresarial y aprobación de Tukit como comercio para operar en producción: la validación se hace en sandbox y el paso a producción queda como trabajo futuro."

Por qué: el riesgo se mantiene pero cambia de pasarela y de alcance.

**S2.d Línea 1009 y 404 ("checkout mock")**

Texto actual: "Sprint 2 checkout mock, seguimiento..." y "con pago real y entrega trazable".

Texto de reemplazo: "Sprint 2 checkout con Wompi en sandbox, seguimiento..." y "con pago en sandbox y entrega trazable".

Por qué: el texto actual se contradice solo ("mock" y "pago real"). El producto usa sandbox.

## S3. Kubernetes con autoescalado pasa a Minikube local

**S3.a Infraestructura (línea 299)**

Texto actual: "Equipos personales, GitHub, Docker, Kubernetes, Python y herramientas de código abierto. Con el despliegue productivo se añade el costo del clúster gestionado. $0 COP"

Texto de reemplazo: "Equipos personales, GitHub, Docker, Minikube (Kubernetes local), Python y herramientas de código abierto. El despliegue en un clúster gestionado queda como trabajo futuro. $0 COP"

Por qué: el despliegue verificado es local (Minikube). Se mantiene el costo de $0.

**S3.b Tabla de tecnologías (línea 529)**

Texto actual: "Orquestación Kubernetes + NGINX Ingress Despliegue de microservicios con réplicas independientes por servicio, escalado horizontal y punto único de entrada. 4, 5 [44]"

Texto de reemplazo: "Orquestación Minikube + manifiestos Kubernetes Despliegue local de los siete desplegables (identidad, catálogo, inteligencia, comercio, operación, puerta de enlace e ingesta) sobre cinco bases de datos, con punto único de entrada en la puerta de enlace. El escalado horizontal queda como trabajo futuro. 4, 5 [44]"

Por qué: sin autoescalado probado, no se puede afirmarlo. Conteo de desplegables según SAD (ADR 0012, 0014).

**S3.c Paquete S7 (línea 963) y prueba de carga (línea 987)**

Texto actual: "Migración a microservicios sobre Kubernetes con réplicas independientes y autoescalado, NGINX como ingress..." y "verificación del autoescalado de réplicas".

Texto de reemplazo: "Despliegue de los siete desplegables en Minikube, con observabilidad básica (logs estructurados) y endurecimiento de la puerta de enlace (límite de tasa, ADR 0047). Autoescalado, ingress productivo y trazas distribuidas quedan como trabajo futuro." y, en la prueba de carga, retirar la verificación del autoescalado; la meta de 1.000 usuarios concurrentes se declara como no verificada hasta que exista evidencia (pendiente de confirmar con el equipo de pruebas).

Por qué: lo que existe en el repositorio es el despliegue local.

## S4. Objetivos: de tres a cuatro funciones objetivo del optimizador

**S4.a Tecnologías, NSGA-II (línea 497)**

Texto actual: "Motor que genera los tres perfiles de kit (Ahorrador, Fan, Premium) como frente de Pareto. Formulación MOKP [27] con tres funciones objetivo."

Texto de reemplazo: "Motor que genera los cuatro perfiles de kit (Ahorrador, Fan, Premium y A tu Medida) a partir del frente de Pareto. Formulación MOKP [27] con cuatro funciones objetivo: costo, fidelidad de marca, disponibilidad y afinidad de personaje. La enumeración exacta se usa hasta 4.096 combinaciones y NSGA-II por encima de ese límite. Sobre el frente se aplica una selección a posteriori con MAUT; el método usa los pesos de la encuesta (P21: 0,285 precio, 0,273 marca, 0,255 calidad, 0,187 personaje) como pesos de la utilidad."

Por qué: el código (pymoo, fail-loud) usa cuatro objetivos y cuatro perfiles (ADR 0030); el presupuesto se aplica después del frente (ADR 0029). Los pesos reemplazan a 0,35/0,30/0,25/0,10, que eran supuestos sin respaldo. Los pesos P21 ya están en el código (a664810).

**S4.b Justificación de NSGA-II (línea 560)**

Texto actual: "...lo que excede la formulación de tres objetivos del sistema."

Texto de reemplazo: "...lo que excede la formulación de cuatro objetivos del sistema."

Por qué: cuatro es menor que cinco, así que NSGA-II sigue siendo la elección justificada por [27].

**S4.c Línea 585 (criterio de aceptación de OE4)**

Texto actual: "los tres perfiles de kit se generan correctamente, el pago se procesa contra la pasarela"

Texto de reemplazo: "los cuatro perfiles de kit se generan correctamente, el pago se procesa contra la pasarela en sandbox"

Por qué: consistencia con S2 y S4.a.

**S4.d Línea 1009**

Texto actual: "pantallas núcleo (resolución, 3 kits, swap, panel admin)"

Texto de reemplazo: "pantallas núcleo (resolución, 4 kits, swap, panel admin)"

Por qué: consistencia con los cuatro perfiles.

## S5. Muestra de validación e instrumentos

**S5.a Fase 5 (línea 406), instrumentos (línea 521), reporte (línea 589)**

Texto actual: "Prueba con usuarios siguiendo el protocolo de Lazar et al. [17], instrumentos SUS [25] y NPS [24] sobre muestra n ≥ 20 participantes." y "Muestra n ≥ 20. ... n ≥ 20."

Texto de reemplazo: "...instrumentos SUS [25] y NPS [24], pensamiento en voz alta y conteo de interacciones discretas como medida principal de carga cognitiva, con el RTLX [Hart 2006] como medida complementaria. Muestra mínima n ≥ 5 por ronda (Nielsen, 1994) y muestra ideal n ≥ 20. Dos rondas: formativa (31-oct) y sumativa (2-nov)."

Por qué: un n ≥ 20 fijo no es defendible para una prueba de usabilidad cualitativa con la ventana de tiempo que quedó. Se declara el mínimo y el ideal, y que los intervalos de confianza se interpretan según el n real. Si no se alcanza n = 20, las pruebas t o Wilcoxon de la línea 589 se reportan como exploratorias.

**S5.b TAM como alternativa (línea 564)**

Texto actual: "TAM (Technology Acceptance Model) se considera como alternativa si el perfil de los participantes reclutados es más cercano a usuarios técnicos..."

Texto de reemplazo: "SUS y NPS son los instrumentos de la validación. TAM no se aplicó."

Por qué: la decisión ya se tomó; la alternativa condicional se retira para no dejar una puerta abierta que el reporte no usa.

**S5.c Datos de la investigación (nuevo)**

Texto de reemplazo (añadir a ética): "Los datos de la investigación se tratan conforme a la Ley 1581 de 2012 y al Decreto 1377 de 2013. Las grabaciones se conservan hasta 30 días y los datos de investigación se eliminan 12 meses después de la aprobación del trabajo de grado."

Por qué: el consentimiento informado y las páginas legales del producto ya asumen estos plazos.

## S6. Objetivos específicos 3 y 5

**S6.a Objetivo 3 (línea 270)**

Texto actual: "...incluyendo la traducción de preferencias en lenguaje natural a restricciones estructuradas (NL2C)"

Texto de reemplazo: "...incluyendo la traducción de preferencias en lenguaje natural a restricciones estructuradas (NL2C) mediante invocación de funciones de un modelo de lenguaje, con interfaz generativa, confirmación humana y barreras contra la inyección de instrucciones."

Por qué: misma redacción que OE3 en la VFP v4 (objetivo y entregable, sin cifras). El texto no lleva cifras finales de utilidad ni de tasa de éxito de ataque: la ronda 3 de evaluación sigue en curso con un criterio modificado. NL2C está fusionado en `validacion/oe5` (S4: /v1/nl2c/interpretar, panel de interfaz generativa en /empezar, descarte confirmado por el padre en /kits).

## S7. Normativa de listas escolares: se retira la Resolución 17821 de 2023

Texto actual (línea 236): "La Resolución 17821 de 2023 del Ministerio de Educación Nacional [14] prohíbe que los colegios exijan marcas o proveedores específicos en sus listas..."
Texto actual (línea 881): "análisis de la Resolución 17821 de 2023".
Texto actual (referencia [14], línea 1396): "Resolución 17821 de 2023: Por la cual se establecen los parámetros para la fijación de las tarifas de matrícula, pensiones y cobros periódicos..."

Texto de reemplazo: "El parágrafo 1° del artículo 203 de la Ley 115 de 1994, modificado por el artículo 1 de la Ley 1269 de 2008 [14], obliga a los establecimientos a entregar la lista completa de útiles en la matrícula y les prohíbe exigir que los padres entreguen esos materiales al colegio." Referencia [14]: "Congreso de Colombia, Ley 1269 de 2008, Diario Oficial No. 47.219, 31 de diciembre de 2008."

Por qué: no pude verificar la Resolución 17821 en el portal del Ministerio (el listado de resoluciones consultado no la mostró) y el título citado en el SPMP corresponde a tarifas de matrícula y pensiones, no a listas de útiles. La Ley 1269 de 2008 sí se verificó en la base de la Secretaría del Senado. La afirmación "prohíbe exigir marcas" no está en ese texto; si el equipo quiere sostenerla, necesita una fuente verificada. La memoria ya retiró la Resolución 019805.

## Preguntas abiertas

1. Cifras finales de NL2C (ronda 3 en curso).
2. Capacitor no existe en el código: solo trabajo futuro, nunca como hecho.
3. Si el autoescalado y la prueba de 1.000 usuarios concurrentes tienen evidencia.
4. Referencias [13], [43], [44]: cambiar por documentación de Wompi, PWA y Minikube.
