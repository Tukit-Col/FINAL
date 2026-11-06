# Segunda pasada R2 (2026-11-05)

PDF revisado: `docs/memoria/main.pdf` de las 16:11 del 5-nov, 92 páginas, commit 4f5e6d3. Página física = impresa + 10. Mi rango son los capítulos III a V, de la p. 9 a la 26.

**Resumen.**
- De los 34 hallazgos ALTO y MEDIO de la primera pasada: **27 resueltos, 4 parciales y 3 no resueltos**.
- De los 11 ALTOS quedan 10 resueltos y 1 parcial (#10: el texto ya concilia el número de desplegables, pero el canónico sigue diciendo 7).
- Aparecen **8 problemas nuevos**. Tres son altos:
  - La Figura 5 dibuja mal quién crea la orden.
  - La Figura 4 no cuadra con el código en cuatro puntos.
  - El cap. III repite su contenido en dos subsecciones seguidas.
- El texto ahora dice "Minikube" y el repositorio no tiene nada de Kubernetes.
- Los ADR 0001 a 0026 sí existen, en `../Arquitectura/adr/`.

---

## 1. Estado de los hallazgos ALTO y MEDIO

| # | Sev. | Estado | Pág. nueva | Evidencia |
|---|---|---|---|---|
| 1 | ALTO | Resuelto | 11–12 | La Tabla 4 vuelve al cuerpo con lectura ("conviene mirar las dos primeras filas y la última") y el capítulo cierra con la brecha: "convertir cualquier lista escolar en kits completos y auditables. De ella parte… el Capítulo IV". |
| 2 | ALTO | Parcial | 19–25 | Hay criterios para la arquitectura (Tabla 10 ATAM, Tabla 11), para Python (V.6.2) y para Wompi (una línea, ADR 0033). Siguen sin criterio Next.js, PostgreSQL con pgvector, RabbitMQ (solo el ADR 0046 en la Tabla 12), Redis y Gemini. Ver también N6. |
| 3 | ALTO | Resuelto | 18, 25 | "con la norma IEEE 1016 como estructura del Documento de Diseño de Software (SDD)" (p. 18) y "El SDD detalla las políticas y la minimización por columna" (p. 25). |
| 4 | ALTO | Resuelto | 15, 18 | RNF05 dice ahora "en el día pico de diseño", y V.2 aclara "decenas de pedidos diarios en temporada (el pico de diseño de RNF05 es de unos 1.000)". |
| 5 | ALTO | Resuelto | 18, 21 | La Tabla 8 liga cada preocupación a sus RNF y la Tabla 11, cada decisión a un escenario (L-02 a RNF05). Detalle menor: la Tabla 8 asocia "pagar sin exponer datos de tarjeta" a RNF03/RNF04, pero ese requisito es RNF01. |
| 6 | ALTO | Resuelto | 17 | "El OE5 evaluó con seis acudientes el recorrido completo, que incluye este flujo (Sección VII.5)". |
| 7 | ALTO | Resuelto | 13, 15, 16 | La Tabla 5 dice "Emite la lista oficial"; RF05 dice "El equipo de Tukit revisa y publica… (el panel de colegio quedó fuera del alcance)"; IV.3 separa "cuatro roles de uso, distintos de los interesados de la Tabla 5". |
| 8 | ALTO | Resuelto | 17, 19 | "con 4.719 ítems. Un análisis inicial de 3.608… reducía a 99 conceptos; el catálogo actual tiene 149." Se quitó la frase "sin explicación registrada". |
| 9 | ALTO | Resuelto, con un caso nuevo | 16, 21 | El texto y la figura dicen ahora "Minikube, sin autoescalado", que coincide con HECHOS. Pero el repositorio no lo respalda (ver **N1**). |
| 10 | ALTO | Parcial | 19 | "seis desplegables (siete en el manifiesto, que cuenta la ingesta)" concilia el texto. Falta actualizar `HECHOS_CANONICOS`, que sigue diciendo 7. |
| 11 | ALTO | Resuelto | 13, 13 | Design Thinking queda explícito (empatía en III, definición en IV), aparece el método ("encuesta y entrevistas") y "Los guiones de entrevista y los mapas de empatía están en los anexos (Tabla 25)". La promesa de la Descripción general ya no existe. Las entrevistas siguen sin número ni perfiles; es un detalle menor. |
| 12 | MEDIO | Resuelto | 9 | La apertura nueva ya no promete arquitectura ni caracterización. |
| 13 | MEDIO | Resuelto | 9 | Ya no está "a continuación"; ahora remite a la Tabla 3. |
| 14 | MEDIO | Resuelto | 9 | Queda un solo párrafo de apertura. |
| 15 | MEDIO | Resuelto | 9 | "La apuesta del proyecto es combinarlos en una cadena de lectura, normalización, optimización y revisión humana." |
| 16 | MEDIO | Resuelto | 11 | "Tres abordan el problema completo… Las otras tres resuelven solo la lectura." |
| 19 | MEDIO | Resuelto | 14 | "Como proviene de un solo colegio y se inclina al estrato 4, describe a esa población y no se generaliza." |
| 20 | MEDIO | No resuelto | 13 / 18 (Tabla 2) | El texto sigue diciendo "dieciocho preguntas" y la Tabla 2 sigue diciendo "pregunta P21". No se explica la numeración. |
| 23 | MEDIO | Resuelto | 15 | MoSCoW queda citado [57]; "los 34 restantes no tienen prioridad"; "81 de los 98 priorizados (82,7 %)". |
| 24 | MEDIO | Resuelto | 15 | RNF06 queda como "Eficiencia de desempeño". |
| 25 | MEDIO | Resuelto | 15 | En RNF02: "parcial, la depuración del documento (PE-06) está pendiente". |
| 26 | MEDIO | Resuelto | 16 | "Las restricciones técnicas se derivan del ADR 0014". |
| 27 | MEDIO | Resuelto | 16 | "Sus códigos (CO, PV, PE, PS, AD, NR, UM) identifican los requisitos por módulo, mientras que las tablas del cuerpo usan RF y RNF." |
| 28 | MEDIO | Resuelto | 17 | El capítulo cierra con "el Capítulo V elige y diseña la arquitectura que los sostiene mediante ATAM". |
| 29 | MEDIO | Parcial | 9, 13 | Se quitó "Venimos… descubrimos" del cap. V, pero la primera persona plural apareció en III ("Encontramos que ninguna solución revisada…", p. 9) y en IV ("Encontramos que la dificultad está en el esfuerzo…", p. 13). |
| 30 | MEDIO | Resuelto | 18–21 | ATAM y los escenarios se presentan ahora en el propio cap. V (V.3, Tabla 11). |
| 31 | MEDIO | Resuelto | 10 | Se quitó la cita a Sun et al. del texto; `rg sun_product sections/contextoProyecto.tex` = 0. |
| 32 | MEDIO | Resuelto | 19 | La Tabla 9 de impulsores está en el cuerpo. |
| 33 | MEDIO | Parcial | 18–19 | Ya no está la frase "aproximadamente adecuado", pero la fecha sigue siendo incoherente: "fusionó los servicios el 10 de septiembre, sobre lo desarrollado en los sprints SCRUM del 2 al 18 de septiembre de 2026" (fusión en medio del periodo que se fusiona). |
| 34 | MEDIO | Resuelto | 19–20 | A, B y B′ se definen antes de descartarse y la Tabla 10 está en el cuerpo. Los puntajes 3,91/3,44/2,82 y la sensibilidad de ±20 % no tienen fuente canónica (no es un error). |
| 35 | MEDIO | No resuelto (empeoró) | 22 | El C4 ahora va a `\resizebox*{!}{0.5\textheight}` (antes 0,80). Las cajas miden unos **2,9 pt** y las etiquetas de flecha unos **2,1 pt**. A 100 ppp la figura no se lee (pasos A/B/C y leyenda incluidos). La Figura 1, el contexto UML en JPG al 62 % del ancho, tampoco se lee en papel. |
| 37 | MEDIO | Resuelto | 25 | "doce pruebas… (nueve sobre código y manifiesto, tres sobre las colas y Redis)", con un total coherente. |
| 38 | MEDIO | No resuelto (ahora velado) | 25 | Se quitó la cifra 3.187, pero el perfilado sigue sin decir con qué catálogo se hizo, y el catálogo actual es de 1.050 productos. |
| 39 | MEDIO | Resuelto | 25 + anexo | Los ADR 0001 a 0026 existen en `../Arquitectura/adr/` y la Tabla 25 lo dice ("0001 a 0026 en Arquitectura/adr/ y 0027 a 0049 en docs/arquitectura/adr/"). |

Bajos de la primera pasada (sin pedido de estado): el #17 (Docling) se resolvió con una remisión a VII.1, el #21 (JTBD) quedó nombrado y el #40 (C4, RBAC) quedó citado (`brown_c4_2018`, `sandhu_role-based_1996`). Las 49 claves citadas en III a V existen en `tukit.bib`.

---

## 2. Problemas nuevos

| # | Pág. | Sección / archivo | Lente | Severidad | Hallazgo | Evidencia | Sugerencia |
|---|---|---|---|---|---|---|---|
| N1 | 16, 21–22 | IV.2 / analisisProblema.tex:216; V.4 / disenoSolucion.tex:146; Fig. 3 | cifra | ALTO | El texto dice "Se despliegan en local con Minikube", pero el repositorio no tiene manifiestos de Kubernetes. `Makefile:30` usa `COMPOSE := docker compose -f infra/docker-compose.yml`, `bd-arriba` hace `$(COMPOSE) up -d`, y la Fig. 3 describe `make arriba` (procesos locales). El hecho canónico está probablemente desactualizado y el texto lo copió. | `rg -i 'minikube\|kubectl'` fuera de `docs/` = 0 | Corregir HECHOS y el texto a lo que hay (Postgres, RabbitMQ y Redis en Docker Compose, servicios como procesos con `make arriba`). |
| N2 | 24 | V.5 Fig. 5 / img/arquitectura/secuencia-pago.tex | visual | ALTO | La Figura 5 dibuja "puerta de enlace → comercio: crea la orden", pero en el código la orden la crea **inteligencia**. Además la Figura 5 contradice el C4 (B1: "inteligencia crea la orden en comercio"). | `inteligencia/trabajos.py:1442 comercio.crear_orden(` y `:1455 comercio.iniciar_pago(`; la puerta solo expone `/v1/ordenes/{id}/avanzar` (`gateway/api.py:180-181`) | Añadir la línea de vida de inteligencia entre la puerta y comercio. |
| N3 | 24 | V.5 Fig. 4 / img/arquitectura/secuencia-pipeline.tex; disenoSolucion.tex:163 | visual | ALTO | La Figura 4 no cuadra con el código en cuatro puntos. (a) Pinta una cadena síncrona con retorno de kits al acudiente: `POST /v1/trabajos` responde 202, encola y el trabajador durable lo toma de RabbitMQ o de la tabla. (b) La lectura con Gemini ocurre en la subida (`routers/inteligencia.py:978, :1142`), no en el trabajo. `trabajos.py` no llama a Gemini, y esto contradice también A2 del C4 ("el trabajador… lee las páginas con Gemini"). (c) τ solo separa RESUELTO_AUTO de AMBIGUO; hueco y sin match los decide el estado que devuelve el catálogo (`dominio/pipeline.py:75-83`). (d) "optimiza todos los renglones": el optimizador es un módulo dentro de inteligencia, no una línea de vida aparte, y optimiza solo los decidibles con candidatos (`optimizador.py:894`). Los AMBIGUO entran con una elección provisional. | Ver el anexo de verificación abajo | Redibujar con trabajador y cola, la lectura en la subida y una nota de que τ solo separa resuelto de ambiguo. Corregir A2 del C4. |
| N4 | 10–11 | III.2.1 y III.2.2 / contextoProyecto.tex:74-131 | claridad | ALTO | Hay contenido duplicado. "Plataformas internacionales" (2.1) ya trae TeacherLists, 1st Day, Panamericana, Éxito, Primavera, MercadoLibre y el párrafo académico. "Soluciones en Colombia" (2.2) repite los tres párrafos casi literalmente, y empieza con "A nivel internacional, TeacherLists…". Un jurado lo nota de inmediato. | p. 10: "2.2 Soluciones en Colombia — A nivel internacional, TeacherLists reúne…" | Dejar una sola versión, partida en "internacional" y "Colombia" (y "académico"). |
| N5 | 18 / 21 | V Tabla 8 / disenoSolucion.tex:15-25 | hilo | MEDIO | La Tabla 8 liga "pagar sin exponer datos de tarjeta" a RNF03/RNF04, que son tiempo y PWA; el requisito que corresponde es RNF01. "Colegio y equipo de Tukit" aparece como un solo interesado, aunque el colegio ya no opera el sistema (RF05). | "(RNF03, RNF04)" | Poner RNF01 y separar al colegio. |
| N6 | 25 | V.7 / disenoSolucion.tex:232 | claridad | MEDIO | La línea "Wompi, con su widget, deja los datos de tarjeta fuera del sistema (ADR 0033)." queda suelta entre la Tabla 12 y la Síntesis, como resto de una edición. Es la única justificación de herramienta fuera de Python. | Párrafo de una sola línea | Integrarla en una tabla corta de herramienta, criterio y ADR (ver #2). |
| N7 | 22 | V.4 / disenoSolucion.tex:137 | visual | MEDIO | Además del tamaño (#35), el C4 ocupa media página de altura con una franja vacía a los lados, y la Figura 1 (contexto) es una captura JPG de baja resolución con etiquetas ilegibles. | Fig. 1, p. 21; Fig. 2, p. 22 | Llevar el C4 a una página completa, o apaisada; volver a exportar la Fig. 1 en vectorial. |
| N8 | 23–24 | V.6 / disenoSolucion.tex:184-191 | claridad | BAJO | La sección 6 tiene un único párrafo largo que cubre dominio, matrícula, asimetría y autorización sin subsecciones. Antes eran 4.1 y 4.2, y la lectura en papel se volvió densa. | "La descomposición sigue el diseño guiado por el dominio… matrícula… asimétricas" en un solo bloque | Separar en dos párrafos: matrícula y asimetría, y autorización. |

---

## 3. ¿Hay algo que obligue a ir al anexo para entender?

No en lo esencial. Las tablas y figuras que el argumento necesita están en el cuerpo: Tablas 3 a 12 y Figuras 1 a 5. Las remisiones que quedan son de detalle y no cortan la lectura:

- **IV.1.3:** la Tabla 29 (MoSCoW por componente). Basta con la cifra 81/98 que da el texto.
- **IV intro:** la Tabla 25 (índice de anexos), que remite a los guiones de entrevista y los mapas de empatía.
- **V.6:** la Tabla 27 (reparto de tablas), que solo apoya el conteo de 74 tablas.
- **V.6.2:** la Tabla 28 (desglose de latencia); la conclusión está en el texto.
- **V.7:** la Tabla 25, solo para ubicar los 49 ADR.

**Excepción práctica.** Las Figuras 1 y 2 están en el cuerpo, pero no se pueden leer impresas (#35, N7). En papel, el lector tiene que fiarse del texto o de una versión ampliada.

---

## 4. Hilo y metodología visible

| Método | Dónde se ve | Estado |
|---|---|---|
| Design Thinking | III intro (p. 9: "etapa de empatía de Design Thinking [13]"); IV intro y IV.1.2 (p. 13: "etapas de definición"; "El método de levantamiento fue el de Design Thinking: empatía… y definición") | Visible. Faltan el número y el perfil de las entrevistas. |
| IEEE 830 | IV intro (p. 13: "escribió los requerimientos con la forma de especificación de IEEE 830 [17]"); IV.1.2 (p. 14: "IEEE 830 y su sucesor, ISO/IEC/IEEE 29148") | Visible. |
| RUP | V intro (p. 18: "sigue la ruta de diseño de las disciplinas de RUP") | Se nombra, pero sin cita (existe `kruchten_rup_2003` en el `.bib`) y sin decir qué disciplina o artefacto de RUP produjo cada sección. |
| IEEE 1016 | V intro (p. 18: "la norma IEEE 1016 como estructura del Documento de Diseño de Software (SDD)") | Se nombra sin cita (existe `ieee_1016_2009`). El capítulo no muestra qué puntos de vista de 1016 cubre (contexto, composición, interacción…), cuando podría mapearlos a la Tabla 8. |
| ATAM | V.3 (p. 19–21: método, alternativas, matriz ponderada, sensibilidad de ±20 %, Tabla 11 de escenarios con riesgo y compromiso) | Bien visible. Detalle: se habla de "diez criterios" con pesos, pero ni los criterios ni los pesos aparecen en el cuerpo, y la Tabla 10 solo muestra cinco filas cualitativas y el puntaje. |
| SCRUM | V.2 (p. 19: "sprints SCRUM del 2 al 18 de septiembre") | Se menciona de pasada, y la fecha es incoherente (#33). |

**El hilo entre capítulos funciona.** Cada capítulo abre con su fase y su OE y cierra con el paso al siguiente:
- El III cierra con la brecha y pasa al IV.
- El IV cierra con los requerimientos y pasa al V con ATAM.
- El V cierra con "el siguiente capítulo describe cómo se construyó en la Fase 3".

Los defectos que quedan son N4 (la duplicación en III) y N8 (la densidad de V.6).

---

## 5. Las Figuras 4 y 5 contra el código (`servicios/`)

Verificación paso a paso con dos agentes por figura: uno verifica y otro intenta refutar abriendo los archivos. Además confirmé a mano las líneas clave.

### Figura 4: lectura de la lista y kits
| Paso | Veredicto | Evidencia |
|---|---|---|
| 1 sube la lista | Parcial | Hay dos rutas. `POST /v1/listas/subir` lee el PDF con Gemini e importa una versión PENDIENTE; `POST /v1/trabajos` (202) crea el trabajo y arma el kit (`routers/inteligencia.py:304, :844`). |
| 2 reenvía con límite 429 | Cuadra | `gateway/api.py:383 limite.revisar`; `limite.py:55-60` rutas estrictas `listas-subir` y `trabajos`; 429 en `:268`. |
| 3 lectura con Gemini | Parcial | Ocurre en la petición de subida (`routers/inteligencia.py:978, :1142 api._percibir_onboarding`), no en el trabajo; `trabajos.py` no llama a Gemini. |
| 4 normaliza | Cuadra | `dominio/pipeline.py:34 _normalizar`, en el trabajador. |
| 5–6 emparejar, candidatos y parecido | Cuadra | `remoto.py:129-137 POST /v1/catalogo/emparejar`; respuesta con estado, opciones y parecido. Solo se emparejan los renglones con `busca_en_catalogo`. |
| 7 τ = 0,75 | Parcial | `trabajos.py:81 TAU_POR_OMISION = 0.75` (variable `TUKIT_TAU`). `estado_desde_emparejamiento` (`dominio/pipeline.py:64-83`) usa τ solo cuando el catálogo responde `reconocido` con opciones; hueco y sin match vienen del catálogo. |
| 8 optimiza todos | Parcial | El optimizador es `optimizador.py`, dentro de inteligencia. Recibe todos los renglones y optimiza solo los decidibles (`:894`); con un solo decidible usa la heurística. |
| retorno y 9 revisión humana | Parcial | No hay retorno síncrono: el cliente recibe 202 y consulta después. El trabajo termina en `ESPERA_REVISION` (`trabajos.py:503-523`), salvo la lista verificada, que se publica directo. |

**Omisiones:**
- No aparecen el trabajador durable, la cola `inteligencia.trabajos`, la bandeja (`trabajo_encolado`) ni el sondeador de listas.
- Falta la ruta rápida de lista verificada, que va sin Gemini, sin emparejar y sin τ.
- Los cuatro kits de salida no se muestran.

### Figura 5: pago
| Paso | Veredicto | Evidencia |
|---|---|---|
| 1 confirma el kit | Parcial | La web llama a `/api/trabajos/{id}/ordenar` (`apps/web/src/lib/api-navegador.ts:203`) y la puerta lo rutea a **inteligencia** (`gateway/api.py:127`). |
| 2 crea la orden (puerta → comercio) | **No cuadra** | La orden la crea inteligencia (`trabajos.py:1442 comercio.crear_orden`); la puerta no expone `POST /v1/ordenes` (`api.py:180-181`). |
| 3 orden idempotente, rechazo por precio | Parcial | Que se relea el precio y se rechace con `422 precio_cambiado` cuadra (`comercio.py:392-399`). No hay clave de idempotencia en la orden: se reutiliza el pedido pendiente; la idempotencia está en el webhook. La reserva de inventario se crea aquí y la figura no la muestra. |
| 4 referencia del pago | Parcial | Es una segunda llamada (`iniciar_pago`, `trabajos.py:1455`) en la que comercio crea la transacción en Wompi (`comercio.py:540`); vuelve por inteligencia. |
| 5 widget y pago | Cuadra en lo general | La web paga en Wompi; no verifiqué cómo el front integra el widget. |
| webhook sin límite de tasa | Cuadra | `gateway/api.py:152 '/v1/webhooks/wompi': 'comercio'`; `limite.py:208-211 exenta()` exime `/v1/webhooks/`. |
| 6–7 firma, aplicación única, bandeja | Cuadra | El candado `evento_pasarela_procesado` (`comercio.py:15, :581, :605`) devuelve el estado `repetido`. |
| 8–9 RabbitMQ → operación | Cuadra | Hay un publicador aparte y el repartidor de avisos en operación. Sin RabbitMQ, el repartidor sondea la bandeja. |

**Omisiones:**
- Falta inteligencia como línea de vida.
- Faltan la relectura de precio en catálogo y la creación de la transacción en Wompi por comercio.
- Falta la sincronización al regreso (`/v1/pagos`, `comercio.py:632`), que usa el mismo aplicador idempotente. El texto dice con razón que "el pago no depende del regreso", pero no dibuja ese camino.

**Conclusión.**
- La Figura 5 tiene un error estructural (N2): falta inteligencia. El resto del flujo del webhook cuadra.
- La Figura 4 tiene el flujo de datos correcto, pero no muestra la asincronía, ubica mal la lectura con Gemini y le atribuye a τ más de lo que decide (N3).
- La frase A2 del C4 (Figura 2) también ubica a Gemini en el trabajador, y en el código está en la subida.
