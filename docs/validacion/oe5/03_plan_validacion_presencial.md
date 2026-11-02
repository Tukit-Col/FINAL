# Plan de validación presencial con padres (OE5) — TUKIT

Piloto: Colegio Agustiniano Ciudad Salitre, Bogotá. Versión 0.1, 2026-10-17. Borrador para revisión del equipo.

**Convención de marcas.** `[DOC]` = ya lo afirman los documentos (con fuente). `[PROP]` = propuesta de este plan, sin decisión previa.
`[VERIF]` = dato externo o del colegio que hay que confirmar antes de usarlo. Nada de `[PROP]` debe citarse en la memoria como decidido.

## 1. Lugar en la metodología declarada
- `[DOC]` La metodología es híbrida contenedora SCRUM + RUP + CRISP-DM; las cinco fases mapean 1:1 con OE1–OE5 (Marco_Metodologico_Tukit_v3.md).
- `[DOC]` F5/OE5 = protocolo IHC (Lazar), SUS, NPS, NASA-TLX, think-aloud y estadística inferencial, con ISO/IEC 25010 y Ley 1581/2012. El objetivo general es medir el efecto del recomendador sobre carga cognitiva, usabilidad y satisfacción con padres del sector Salitre.
- `[DOC]` HECHOS_CANONICOS: OE5 está "sin ejecutar"; el instrumental (SUS, NPS, NASA-TLX, think-aloud, batería de tareas, baseline tradicional, notebook Shapiro-Wilk + t-Student/Wilcoxon) es construible; el protocolo ético cita Ley 1581 arts. 7/9/12 y Decreto 1377 art. 12.
- `[DOC]` Criterios de éxito del dossier (tab:criterios): SUS ≥ 68, reducción de NASA-TLX frente a la compra tradicional, NPS positivo, 100 % de los ítems de la lista cubiertos por el kit.
- `[DOC]` La ENMIENDA_VFP deja a la evaluación de F5 la tarea de verificar si la conectividad es una barrera real (justifica la salida de la app nativa y del modo sin conexión).
- Lectura CRISP-DM: este plan es la fase *Evaluation* del ciclo y alimenta la iteración siguiente; la parte de pedido real es el experimento de validación (Lean) que el dossier ya reserva para el piloto del 20 dic al 31 ene `[DOC]`.
- Alcance: este protocolo evalúa **al padre/acudiente con el producto**. No sustituye los guiones B, C, D de colegio y proveedores ni el guion F del niño.

## 2. Objetivo y preguntas
**Objetivo `[PROP]`.** Medir, con acudientes reales del Agustiniano Salitre, (a) usabilidad y carga cognitiva de armar el kit con Tukit frente a su
proceso tradicional, y (b) comportamiento real de compra y disposición a pagar, para cerrar lo que la encuesta (n=60) no puede cerrar: conversión,
disposición revelada y causas de compra tardía `[DOC: dossier, veredicto de continuidad]`.

- P1. ¿Un padre completa sin ayuda el camino lista → kit → pago de prueba, y con qué esfuerzo percibido?
- P2. ¿Hay menos carga y menos tiempo que en su compra tradicional?
- P3. ¿Cómo elige entre Ahorrador, Fan y Premium, y cambia la presentación esa elección?
- P4. ¿Cuánto paga de más, de verdad, por el servicio, y con qué medio?

## 3. Hipótesis que se prueban (IDs de GUIONES_ENTREVISTA §0.5)
| ID | Estado `[DOC]` | Qué mide este plan `[PROP]` | Regla de decisión `[PROP]` salvo que se cite |
|---|---|---|---|
| H1 | Parcial: costo medido, no el cambio de canal | NASA-TLX pareado (tradicional recordado vs Tukit), tiempo hasta kit, reserva real | IC95 % inferior de la diferencia TLX > 0 y dz ≥ 0,5 |
| H2 | No validada; entrevistas apuntan a PSE | Medio de pago elegido de entre PSE, tarjeta, contraentrega, transferencia, y motivo | Dossier: válida si > 50 % elige contraentrega `[DOC]`; refutada si PSE+tarjeta > 50 % |
| H3 | No validada; "solo conversión real" | Tarea de intercambio carga automática sin descuento vs carga manual con 5 % de descuento; tiempos pareados | Se desvía del criterio del dossier (+30 % conversión): no hay potencia (ver §5) |
| H5 | No validada, supuesto en duda (76,7 % recibe la lista con > 1 mes) | Fecha en que planea comprar y por qué; reservas antes del 31 dic en el piloto | Dossier: 25 % de listas captadas antes del 31 dic `[DOC]` |
| H6 | En tensión (70 % no pagaría > 5 %) | Gabor-Granger (0, 5, 10, 15 % sobre la canasta de referencia) y aceptación del precio real al reservar | Si < 50 % de quienes reservan acepta ≥ 10 % de sobreprecio, la comisión pasa al proveedor y se rehace §8 del dossier |
| H7 | No validada (21/35 vs 14/25) | Solo exploratoria: todos llegan por invitación del colegio, así que el aval no varía | No se concluye causalidad; se declara límite |
| H8 | Refutada del lado del acudiente; abierta del lado del niño | Elección de kit, razón declarada, reacción del hijo contada por el padre (proxy) | Fan < 15 % de elecciones y < 20 % que cite al hijo: redimensionar Fan (reserva 2 del dossier `[DOC]`) |
| H9 | Verificada en dato abierto (43,3 %) | Visibilidad del estado de disponibilidad en el kit; faltantes en el piloto concierge | Tasa de ítems entregados completos |
| H10 | Dolor verificado, fuera de alcance v1 | Pregunta de cierre: ¿esperaba libros en el kit? | Solo descriptivo; alimenta decisión de alcance |
| H11 | Declaración vs prohibición de exigir marca | Qué hace ante el popup de variantes, y qué dice que significa "la marca del colegio" | Codificación cualitativa |

Fuera de este plan: H4 (archivada), HC-01..05, HP, HL (se resuelven con guiones B, C, D y operación); HN-01..03 (los menores no participan:
solo se recoge lo que el padre cuenta, y se rotula como evidencia indirecta). Si la memoria necesita cerrar HC-01 con datos de padres, lo único
que aporta aquí es un indicador lateral: cuántos reportan haber reclamado al colegio por la lista (pregunta previa, §7).

## 4. Diseño (mixto, tres etapas)
- **Etapa A. Formativa, iterativa `[PROP]`.** Prueba moderada con think-aloud sobre el prototipo vigente (PWA), 3 rondas de 5 padres con corrección entre rondas. Salida: lista de problemas con severidad, no inferencia estadística.
- **Etapa B. Sumativa pareada `[PROP]`.** 30 padres (reclutar 36), sesión individual, medidas intra-sujeto: NASA-TLX recordado de la compra tradicional del año anterior vs NASA-TLX de la tarea con Tukit; SUS; NPS; tareas con tasa de éxito y tiempo. Es el análisis confirmatorio de OE5, con hipótesis y umbrales fijados antes de ver datos.
- **Etapa C. Pedido real concierge / Wizard-of-Oz `[PROP]`.** Al final de B, el padre puede reservar el kit real. El equipo cumple a mano (compra al proveedor, arma y entrega en el colegio o a domicilio), sin Wompi productivo (no es bloqueante de tesis `[DOC]`). Mide conversión real, medio de pago, sobreprecio aceptado y faltantes. Cumple la reserva real el equipo, no el sistema; así debe declararse en la memoria.
- **Experimento A/B de presentación `[PROP]`.** Factor intra-sujeto con orden contrabalanceado (cuadrado latino 2×2):
  - Formato X: tres alternativas lado a lado (Ahorrador, Fan, Premium), como en el SRS. Formato Y: un kit recomendado por defecto con botón "ver otras dos opciones".
  - Cada padre ve X con una lista de referencia y Y con otra, balanceando listas y orden. Variables: kit elegido, tiempo de decisión, confianza (1–7), arrepentimiento anticipado. Fundamento: sobrecarga de elección e inercia al valor por defecto (`iyengar_when_2000`, `schwartz_paradox_2003`, `thaler_nudge_2008`, `payne_adaptive_1993`).
  - Orden: grupo 1 = X→Y, grupo 2 = Y→X, con la lista 1 o 2 alternada dentro del grupo; asignación por sorteo de sobres.
- **Línea base tradicional `[PROP]`.** (i) NASA-TLX retrospectivo sobre la última compra; (ii) tiempo medido de una tarea de control: ubicar 8 ítems de la lista de referencia en una tienda en línea de papelería ya existente (subgrupo de 12 de la etapa B). Límite declarado: sesgo de recuerdo y de novedad.
- **Cobertura del kit.** `[DOC]` El dossier exige 100 % de ítems cubiertos; `[DOC]` OE3 midió 83 % de cobertura extremo a extremo (60 sublistas, 2.176 ítems). `[PROP]` Reportar ambas cifras: cobertura automática y cobertura final tras la cola del admin; no declarar cumplido el 100 % con la primera.

## 5. Muestra y justificación
- **Etapa A: 3 rondas × 5 = 15.** Nielsen (1994) `nielsen_estimating_1994` sostiene que unos 5 sujetos en una prueba con pensamiento en voz alta detectan la mayor parte de los problemas; con p ≈ 0,31 por problema, 1−(1−p)^5 ≈ 84 % (5 usuarios) y ≈ 67 % (3). Como p varía por producto, se itera: el supuesto se controla corrigiendo y volviendo a probar, no con una sola ronda grande. `[VERIF]` el valor p = 0,31 contra la fuente primaria antes de citarlo.
- **Etapa B: n = 30 analizables, reclutar 36 (≈ 15 % de pérdida).**
  - Diferencia pareada de TLX, t pareada, α = 0,05 bilateral, potencia 0,80: n ≈ 15 para dz = 0,8; 24 para 0,6; 34 para 0,5 (aprox. normal, n ≈ ((1,96+0,84)/dz)² + 1,9); Wilcoxon exige ≈ 5 % más. Con 30 se detecta dz ≈ 0,52 y con 36, dz = 0,47. Se declara que dz < 0,5 no es detectable.
  - SUS: con DE ≈ 12,5 `[VERIF: Sauro y Lewis]`, IC95 % de media ±4,7 con n = 30 (±5,9 con n = 20). Potencia ≈ 0,8 para detectar una media real de 74 frente a 68 (una cola).
  - Éxito de tareas con n = 30: Wilson, por ejemplo 24/30 = 80 %, IC 63–90 %. Amplio; se reporta así, sin redondear a "cumplido".
- **Etapa C: no se calcula potencia; es descriptiva.** Con 36 reservas posibles, 11/36 (31 %) tendría IC95 % de 18–47 %. Probar el +30 % de conversión del criterio H3 (p. ej. 20 % → 26 %) pediría ≈ 770 por brazo: inviable en un colegio. Se decide no hacer A/B de conversión y se documenta como desviación del dossier.
- **Marco muestral.** Familias del Agustiniano Salitre. Cuotas mínimas `[PROP]` alineadas con el guion A `[DOC]`: preescolar/primaria/bachillerato, gasto anual por hijo < $700.000 y > $1.000.000, y hijos insatisfechos el primer día (20 % de la encuesta). Meta: no repetir el sesgo de estrato 4 (68,3 %) de la encuesta. Muestreo por conveniencia con cuotas, no probabilístico: no se generaliza más allá del colegio. Registrar si el padre respondió la encuesta.
- No se mezclan las muestras: los 15 de la etapa A no cuentan en B (el prototipo cambió). Excluir familiares del equipo `[DOC]`.

## 6. Reclutamiento, consentimiento y ética
- **Vía del colegio `[PROP]`.** Carta a rectoría pidiendo permiso para invitar; el colegio envía la invitación por su canal. Tukit no recibe bases de familias: los padres se inscriben ellos mismos con un formulario (autorización de datos separada). Falta el aval escrito `[VERIF]`. Un evento donde los padres ya van (entrega de boletines, escuela de padres) reduce costo; fecha por confirmar con coordinación.
- **Marco legal `[DOC]`.** Ley 1581/2012 (arts. 7, 9, 12), Decreto 1377/2013 (arts. 12–13), finalidad exclusivamente académica; autorización previa, escrita e informada; derecho a no responder y a terminar; correo para consulta, rectificación y supresión; sin incentivo económico (evita complacencia).
- **Menores `[PROP + DOC]`.** No participan en ninguna sesión. Sin nombre, documento, fecha de nacimiento ni foto del hijo. De la lista solo se usa el grado. Las sesiones corren en un entorno de pruebas con datos sintéticos; el padre no crea cuenta real. Se reserva el consentimiento más estricto de la Ley 1581 art. 7 si un padre menciona datos del hijo: se omiten de la transcripción.
- **Coherencia del consentimiento `[DOC]`.** No escribir "no guardamos el nombre de su hijo" mientras el hallazgo del ANEXO_M §5 siga abierto; decir solo que la investigación no lo recoge.
- **Grabación.** `[DOC]` solo audio, nunca video; se destruye al verificar la transcripción; códigos `ACU-xx`. `[PROP]` añadir captura de pantalla del entorno de prueba (sin datos reales) con una línea de consentimiento propia.
- **Etapa C es otra finalidad.** `[PROP]` La reserva real es transacción comercial de Tukit: autorización distinta (tratamiento comercial), política de privacidad y términos, retracto de Ley 1480/2011 en ventas a distancia, factura y reembolso manual. No se mezcla con el consentimiento académico. `[VERIF]` con asesor jurídico.
- `[VERIF]` Si la facultad exige aval del comité de ética o carta del director del trabajo de grado; los documentos no lo dicen.
- Pago de prueba: solo flujo mock. Ninguna tarjeta real en sesiones A y B.

## 7. Sesión (55 min, uno a uno, en el colegio) `[PROP]`
| Min | Bloque | Contenido |
|---|---|---|
| 0–5 | Bienvenida y consentimiento | Lectura, firma, pregunta por audio y pantalla. Sin autorización no hay sesión ni notas |
| 5–10 | Previo | Perfil, grado del hijo, dispositivo y conexión, última compra de útiles, TLX recordado, ¿reclamó al colegio por la lista? |
| 10–14 | Entrenamiento think-aloud | Tarea neutra (p. ej. pedir un domicilio en una app ajena) para que aprenda a hablar en voz alta |
| 14–40 | Tareas con Tukit (A/B dentro) | T1 a T7 abajo, 3–4 min cada una; el moderador no ayuda salvo bloqueo de 90 s (cuenta como asistida) |
| 40–44 | Tras tareas | NASA-TLX de la tarea con Tukit; SEQ por tarea (1–7) |
| 44–48 | Cierre cuantitativo | SUS (10 ítems), NPS (0–10), confianza en la presentación X y Y |
| 48–55 | Precio y pedido | Gabor-Granger, elección de medio de pago, oferta de reserva (etapa C), 2 preguntas abiertas, libros y conectividad |

Tareas (la dificultad real viene del producto, no de instrucciones):
- T1 Ingresar con el código/matrícula del colegio de prueba. T2 Cargar la lista (foto con la cámara o archivo del colegio) y revisar el resultado.
- T3 Resolver un renglón ambiguo mediante el popup de variantes (p. ej. "cuaderno"). T4 Comparar los tres kits en el formato X o Y y elegir uno, pensando en voz alta.
- T5 Ajustar el presupuesto y personalizar un ítem. T6 Pagar con el flujo mock (PSE primero) y ubicar cuándo y dónde recibe. T7 Encontrar el panel de privacidad y pedir la supresión de sus datos.
- Redacción de consignas: escenario, no instrucción ("Quiere dejar esto resuelto antes de las vacaciones…"). No nombrar botones. Reglas de neutralidad del guion A (§0.4) `[DOC]`.

## 8. Materiales
Consentimiento (académico), autorización comercial separada, hoja de código `ACU-xx`, entorno de pruebas con semillas y datos sintéticos, listas de referencia 1 y 2,
dos teléfonos de respaldo, hoja de observación (éxito, asistencia, errores, tiempo, citas), formularios SUS/NASA-TLX/NPS/SEQ impresos y en línea, tarjetas de precio (Gabor-Granger),
tabla de sorteo de orden, guía del moderador, cronómetro, grabadora de audio, bitácora de bugs, carta a rectoría. Sin dinero ni incentivos.

## 9. Métricas y umbrales
| Métrica | Umbral | Origen |
|---|---|---|
| SUS media | ≥ 68 y límite inferior del IC95 % > 68 (regla estricta) | `[DOC]` 68; regla del IC `[PROP]` |
| SUS meta de diseño | ≥ 72 (≈ "bueno", Bangor 2008) | `[PROP]`, `[VERIF]` el valor |
| NASA-TLX | Tukit < tradicional, IC95 % de la diferencia pareada excluye 0, dz ≥ 0,5 | `[DOC]` dirección; umbral `[PROP]` |
| NPS | > 0, reportado con IC bootstrap (será ancho) | `[DOC]` positivo; IC `[PROP]` |
| Éxito de tareas sin ayuda | ≥ 80 % por tarea crítica (T2, T4, T6) | `[PROP]`; `[VERIF]` benchmark (≈ 78 % medio, Sauro) |
| Tiempo lista → kit elegido | Mediana ≤ 20 min con lista completa | `[PROP]`; no comparable uno a uno con "4 h" de la encuesta |
| Cobertura del kit | Reportar automática y final | `[DOC]` 100 %; `[PROP]` doble reporte |
| Reserva real | Tasa con IC Wilson; contrastar con intención alta declarada (≈ 58 %, 35/60) | `[PROP]` |
| Severidad de problemas | Escala 0–4, frecuencia × impacto × persistencia; cero problemas de severidad 4 abiertos | `[PROP]` |

## 10. Análisis `[PROP]`
- **Plan de análisis fechado antes de recolectar** (commit en el repositorio, sin cambiar umbrales después).
- Cuantitativo: Shapiro-Wilk sobre diferencias; t pareada si cumple, Wilcoxon si no (`[DOC]` en el notebook de OE5); tamaño del efecto (dz, Hodges-Lehmann); SUS contra 68 con t de una muestra o Wilcoxon; Wilson para proporciones; bootstrap para NPS; modelo mixto o prueba pareada para el A/B con efecto de orden y lista. Holm para las pruebas secundarias; las confirmatorias son solo SUS, TLX y éxito de tareas.
- Cualitativo: transcripción despersonalizada; codificación de pensamiento en voz alta por dos codificadores (plantilla de problemas y de motivos), acuerdo con κ de Cohen (el proyecto ya lo usa, κ = 0,705 en OE3 `[DOC]`); meta κ ≥ 0,6; desacuerdos por consenso. Saturación temática en la etapa A.
- Triangulación: lo declarado (SUS, intención) contra lo hecho (tareas, reserva, pago). La brecha intención-conducta es un resultado, no un error.
- Se reportan las hipótesis refutadas con el mismo peso que las confirmadas, como ya hace el dossier con H8 `[DOC]`.

## 11. Calendario (hoy sáb. 2026-10-17)
| Semana | Fechas | Actividad |
|---|---|---|
| S1 | 19–25 oct | Congelar plan y análisis; carta a rectoría; consentimientos; entorno de pruebas; 2 ensayos internos |
| S2 | 26 oct–1 nov | Aval del colegio; invitación; piloto del instrumento con 2 personas ajenas; ajustes |
| S3 | 2–8 nov | Ronda 1 (5). Lun 2 nov festivo `[VERIF]` |
| S4 | 9–15 nov | Corrección + Ronda 2 (5) |
| S5 | 16–22 nov | Corrección + Ronda 3 (5). Lun 16 nov festivo `[VERIF]` |
| S6–S7 | 23 nov–6 dic | Etapa B: 30–36 sesiones (≈ 3 por día, 2 semanas), según cierre del año escolar `[VERIF]` |
| S8 | 7–13 dic | Análisis de B; decisión go/no-go del concierge (mar 8 dic festivo) |
| S9 | 14–20 dic | Operación: compromiso de proveedores, logística, textos legales; apertura de reservas |
| S10–S15 | 21 dic–31 ene | Etapa C (ventana del dossier `[DOC]`: 20 dic–31 ene); corte semanal de métricas |
| S16–S17 | 1–14 feb | Análisis de C, actualización del dossier y de la matriz OE↔evidencia |

El calendario del colegio (cierre del año, boletines) no está en los documentos; si el año termina antes de S6, B se adelanta una semana y A se comprime a dos rondas.
Si la memoria vence antes del 31 ene, la etapa B es la evidencia mínima de OE5 y C queda como estudio adicional con corte parcial.

## 12. Roles (equipo de 4) `[PROP]`
| Rol | Tareas |
|---|---|
| R1 Líder del estudio / moderador | Protocolo, plan de análisis, moderar; dueño del marco metodológico |
| R2 Observador y segundo codificador | Hoja de observación, tiempos, codificación independiente, κ |
| R3 Técnico del entorno | Datos sintéticos, dispositivos, bugs, métricas del sistema, exportes; corrige entre rondas |
| R4 Colegio, ética y operación | Carta, invitaciones, consentimientos, jurídico, logística del concierge |

Quien construyó la pantalla evaluada no modera esa pantalla (efecto del evaluador). Los roles rotan entre sesiones para que ningún sesgo de moderador pese sobre todo el estudio.

## 13. Riesgos
| Riesgo | Mitigación |
|---|---|
| Sin aval del colegio o sin fecha de evento | Plan B: reclutar por bola de nieve y grupos de WhatsApp de padres, declarando pérdida del canal institucional (afecta H7) |
| Sesgo de complacencia y de selección (padres comprometidos) | Sin incentivo, escenario neutro, moderador ≠ desarrollador, registrar quién respondió la encuesta; límite declarado en la memoria |
| Prototipo inestable (mock de pago, cobertura 83 %) | Ensayos internos, congelar versión por ronda, sesión de respaldo con guion |
| Muestra pequeña y de un solo colegio | Se declara no generalizable; no hay inferencia sobre estratos 1 y 6 |
| Temporada (dic–ene) satura al equipo y a las familias | Etapa B antes del 6 dic; C con tope de pedidos que el equipo pueda cumplir |
| Pedido real sin respaldo legal ni de proveedor | Etapa C solo con autorización comercial, términos y compromiso previo del proveedor; reembolso manual |
| Cifras fuera de la lista canónica entrando a la memoria | Citar solo HECHOS_CANONICOS y claves del .bib; pendientes con `CITA-FALTANTE` |
| Citas fuera del .bib (Hart 1988, Virzi, Sauro y Lewis) | Dejar `\cite{PENDIENTE}` hasta agregarlas |

## 14. Pendientes
Decisiones del equipo: mantener la etapa C o dejarla como trabajo futuro; aceptar la desviación del criterio H3; formato exacto de las tareas T2 y T3 (qué ofrece hoy la PWA).
Datos por obtener: aval y fechas del colegio, calendario escolar, estado del modo de carga manual, existencia de un comité de ética, verificación de los `[VERIF]`.
