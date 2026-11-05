# Plan de análisis de OE5 (preregistro)

**Fijado el 28 de octubre de 2026, antes de la primera sesión** (29 y 30 de octubre). La fecha del commit en GitHub hace de preregistro. Después de la primera sesión no cambian los umbrales ni las pruebas. Cualquier cambio se anota abajo, en *Desviaciones posteriores*, con fecha y motivo.

Cuaderno: `analisis_oe5.py`, en esta carpeta. `--sintetico` lo prueba con datos inventados y no produce resultados.

## Qué se evalúa
OE5 es la fase F5 de la metodología híbrida y corresponde a *Evaluation* en CRISP-DM. Sigue el paso 2 de VFP v3 §3.5 y MP5 del SPMP v3: sesiones observadas en las que el acudiente hace tareas representativas, piensa en voz alta y al final responde SUS y NPS. Se agrega el NASA-TLX (raw, RTLX) porque es el instrumento que nombran el SRS (UI-07), QA (QA-U2) y ATAM. También se cuentan las interacciones, que es la métrica con la que la memoria juzga OE5.

Versión evaluada: rama `validacion/oe5` (desde `feature/colas-rabbitmq`), con Redis y RabbitMQ activos y `WOMPI_MODO=falso` (pasarela simulada, sin cobro).

## Diseño y muestra
- Prueba de usabilidad moderada, individual, con pensamiento en voz alta y medidas sumativas al final. Medida intra-sujeto de la carga: RTLX retrospectivo de la última compra de útiles contra RTLX de la tarea con Tukit.
- Modalidad mixta, según prefiera cada acudiente: remota (videollamada de 30 min con pantalla compartida desde su celular) o presencial (40 min). La modalidad se registra como covariable.
- Muestra: mínimo 5 (VFP y SPMP), meta de 8 a 12, y se reporta la n efectiva. Muestreo por conveniencia (bola de nieve y grupo de padres conocidos), no probabilístico: no se generaliza. Se excluyen familiares directos del equipo. Inclusión: adulto acudiente que compró útiles escolares en 2025 o 2026, o que los comprará para 2027.
- Una sola moderadora. Para compensar el efecto del evaluador, el guion se lee textual, no se nombran botones y se graba la pantalla para codificar después.

## Variables
| Variable | Instrumento | Momento |
|---|---|---|
| Usabilidad | SUS (0-100) | Al cierre |
| Carga de trabajo | RTLX (0-100), tradicional y Tukit | Antes de las tareas y después |
| Recomendación | NPS (0-10) | Al cierre |
| Éxito por tarea | S (sin ayuda) / A (asistida) / F (fallida) / N (falla del sistema) | Durante |
| Interacciones discretas por tarea | Conteo en la grabación: cada toque o clic, campo diligenciado, búsqueda y vuelta atrás | Después de la sesión |
| Tiempo por tarea | Grabación (la espera del sistema en T3 no cuenta) | Después de la sesión |
| Facilidad por tarea | SEQ 1-7 | Tras cada tarea |
| Problemas | Códigos E1-E7, severidad 0-4 (Anexo T.2 §7) | Durante y en la grabación |

## Hipótesis y criterios
Las confirmatorias son C1, C2 y C3. OE5 se da por cumplido solo si se cumplen las tres; por eso no se ajusta α entre ellas.

| ID | Hipótesis | Prueba | Criterio |
|---|---|---|---|
| C1 | SUS medio > 68 | t de una muestra; Wilcoxon si Shapiro-Wilk rechaza (p ≤ 0,05) | Media ≥ 68 y límite inferior del IC95 % > 68 |
| C2 | Carga con Tukit < carga tradicional | t pareada sobre la diferencia; Wilcoxon si Shapiro-Wilk rechaza | IC95 % de la diferencia excluye 0, en esa dirección, y dz ≥ 0,5 |
| C3 | Éxito sin ayuda ≥ 80 % en T1, T4 y T6 | Proporción con IC de Wilson | Estimación ≥ 80 % en cada tarea crítica; se reporta el IC aunque sea amplio |
| S1 | NPS > 0 | Bootstrap, 10.000 remuestreos | Se reporta con su IC |
| S2 | Interacciones y tiempo por tarea | Mediana e IQR | Descriptivo |
| S3 | SEQ por tarea y RTLX por escala | Wilcoxon pareada con Holm | Exploratorio |

Con n < 10, C1 y C2 se reportan como **indicativos**, no concluyentes: la potencia no alcanza para detectar dz = 0,5. Se dice así en la memoria, sin redondear a "cumplido".

## Análisis cualitativo
Se transcriben y despersonalizan los fragmentos de pensamiento en voz alta y se codifican con la plantilla de problemas (E1-E7) y de motivos de elección de kit. Con una sola moderadora no hay κ entre dos codificadores. Un segundo miembro del equipo recodifica a ciegas el 30 % de las sesiones, sorteadas, y se reporta κ de Cohen sobre esa muestra (meta ≥ 0,6).

## Datos faltantes y exclusiones
- Una tarea con falla del sistema (E6) se repite. Si no se puede repetir, se anota N: cuenta como dato faltante, no como fallida.
- No se imputa nada. Se reporta cuántos se reclutaron, cuántos completaron y cuántos se excluyeron, con el motivo.

## Desviaciones frente a lo planeado (declaradas antes de recolectar)
| Planeado | Lo que se hace | Por qué |
|---|---|---|
| Reclutamiento vía el colegio piloto con aval de rectoría (SPMP, plan del 17-oct) | Bola de nieve y grupo de padres conocidos | Faltan dos días y no hay aval escrito. Afecta H7 (el aval del colegio no se puede observar) |
| SUS y NPS en papel (SPMP MP5, P-36) | Papel en presencial; formulario en línea en remota | La modalidad remota |
| Etapas A, B y C, A/B de presentación, tarea de control (plan del 17-oct) | Una sola ronda sumativa con pensamiento en voz alta, sin A/B ni reserva real | Tiempo; la etapa C queda como trabajo futuro |
| Moderadora distinta de quien construyó la pantalla | Una sola moderadora del equipo | Disponibilidad. Se mitiga con guion textual y codificación en la grabación |
| T7 del guion anterior: panel de privacidad | Se quita | La pantalla no existe (SRS 3.14, PEN-08) |
| Kit «A tu Medida» sin espera | Si el acudiente elige "Un punto medio", la moderadora aprueba su kit en la cola mientras espera (T3) | Así funciona el sistema: el kit personalizado pasa por revisión humana |

## Desviaciones posteriores
(Vacío al fijar el plan.)

### Registradas el 4 de noviembre de 2026, antes de redactar los resultados
| Planeado | Lo que se hizo | Por qué | Efecto en el análisis |
|---|---|---|---|
| Ronda 1 formativa y ronda 2 sumativa | Una sola ronda (2 y 3-nov), seis sesiones, versión `b6b6fe7` | Calendario; la ronda 1 no se completó | Se reporta una sola ronda, sin mezclar |
| Sesión de 30/40 min con SUS, NPS, SEQ y RTLX por formulario | Sesión de 15 min con entrevista oral breve al final; SUS, RTLX (habitual y Tukit) y NPS por formulario en línea el 5 de noviembre, 6 de 6 respuestas (`oe5/oe5_cierre/`) | El formulario largo no cabía en la sesión | C1, C2 y S1 se evalúan con el formulario, con el sesgo de recuerdo declarado; SEQ no aplicado (S3 de SEQ sin datos) |
| T1-T7 | T1-T8 (T8 chat del kit, exploratoria) | El asistente se integró después del preregistro | T8 fuera de C3; ningún acudiente la intentó |
| Solo ayuda mínima tras 90 s | En dos sesiones la moderadora explicó funciones antes de que el acudiente las resolviera | Desviación de la moderación | Esas tareas se codificaron A (criterio estricto), así que las tasas son conservadoras |
| Sesiones completas grabadas | ACU-04 grabada solo al inicio y al final | Corte de la grabación | ACU-04 aporta T1 y su opinión; el resto queda "no observado" |
| Recodificación de un 30 % por un segundo miembro, kappa | Revisión del 100 % de las hojas por un segundo codificador contra transcripción y cuadros | Disponibilidad | 78 correcciones incorporadas; no se calcula kappa (no fue independiente) |

Datos: `oe5/oe5_ronda2/datos_ronda2.csv`. El cuaderno `analisis_oe5.py` acepta ahora SUS, NPS y RTLX vacíos y T8, sin cambiar umbrales ni pruebas.
