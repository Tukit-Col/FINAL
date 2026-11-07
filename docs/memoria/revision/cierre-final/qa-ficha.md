# Ficha de pruebas (QA) para la subsección de verificación

Fuentes: T = `informe/INFORME_QA.tex`; M = `resultados/informe-fases-7-9.md` (2026-11-05); MN = `trazabilidad/matriz-nfr.md`; H = `trazabilidad/hallazgos.md`; ADV = `trazabilidad/adversariales.md`; MC = `skill/references/matriz-chaos.md`; GO = `skill/references/golden-ocr-rag.md`. Repo: Tukit-QA-main (sin git; se citan los sha de los documentos).

Versiones: base de A `d4ea7cb` (2026-10-08, T:189); punta de A `ae584ad` (T:192); nivel 1 de B `qa`@`70b9108` sobre `main`@`dfc4fd3`, corrida 2026-10-19 (T:195); verificación H-B-01 a H-B-03 `9da9dae`, 2026-10-20 (T:1408-1411); campaña de noviembre `dc8e2e7` (= `b6b6fe7` más 2 archivos de override, M:24), 2026-11-05, corridas R1 `20261105-0410` y R2 `20261105-0652`.

Aviso: el `.tex` es anterior a la campaña del 05-nov. Cubre fases 0 a 6 y el nivel 1 de las fases 7 a 9. Los niveles 2 y 3 y las cifras de `dc8e2e7` solo están en M.

## 1. Plan de fases 0-9 (T:316-352, `tab:fases`)

La tabla solo da «Contenido» (no hay objetivo textual por fase). El `.tex` dice «diez fases» pero numera 0 a 10.

| Fase | Contenido | Resp. |
|---|---|---|
| 0 | Línea base: lint, suite, cobertura y CI | A+B |
| 1 | Escenarios NFR: matriz meta-ensayo | A+B |
| 2 | Unitarias, cobertura y gate de CI | A |
| 3 | Integración contra el stack vivo | A |
| 4 | Funcionales de API y de interfaz; dorados OCR y RAG | A |
| 5 | Adversariales de los llamados a IA | A |
| 6 | Patrones de resiliencia | A |
| 7 | Batería de caos | B |
| 8 | Prueba de carga | B |
| 9 | Telemetría: expedientes por `correlacion_id` | B |
| (10) | Informe (fuera del rango 0-9; cierra cuando B entregue los niveles 2 y 3, T:174) | A+B |

Las fases 7 a 9 se dividen en niveles 1, 2 y 3. T:169 y T:349 marcan los niveles 2 y 3 como pendientes, pero M ya los reporta ejecutados.

## 2. Niveles de prueba

| Nivel | Qué verifica | Datos | N.º | Resultado | Fuente |
|---|---|---|---|---|---|
| Unitarias (f2) | `libs/` y `servicios/`; hallazgos documentados con `xfail` | Código en `ae584ad` | 3911 passed y 129 xfailed; más 58 de fronteras con 1 omitida. Base `d4ea7cb`: 1647 passed de 1706 recolectadas | Gate de cobertura >= 50 % cumplido | T:799-812, 791-795, 909-919 |
| Integración (f3) | Contra el stack vivo, bases `tukit_qa4_*` | Corrida `eec6bea3` | 103 verdes y 37 xfail (confirmados con `--runxfail`) | SEG-01 cumple (0 PAN). Una primera corrida `bdfb9d23` dio un falso positivo de PAN; se corrigió el barrido y se repitió | T:923-943 |
| Funcionales API (f4) | E2E de API | Oro G01-G10 | 71 verdes y 17 xfail | Ver sección 3 | T:951, 833 |
| Funcionales interfaz (f4) | E2E con Playwright | Oro | 16 verdes y 1 `test.fail` | Mixto | T:835, 981-988 |
| Adversariales (f5) | OWASP LLM 2025 | ADV-01 a ADV-11 | Ver sección 4 | Ver sección 4 | T:1093-1135; ADV |
| Resiliencia (f6) | Patrones: disyuntor, reintento, idempotencia, degradación, 413, 429, aislamiento | Corrida `7786e7ae` | 14 verdes y 27 xfail en la tabla de patrones (T:1233); 29 pruebas propias (T:1209) | Disyuntor, reintento, idempotencia, degradación, 413 y 429 no cumplen; aislamiento cumple en lo que existe | T:1209-1268 |
| Caos (f7) | Caídas inyectadas CH-xx, aserciones A1-A7 | Stack Docker + Toxiproxy | N1: 10 escenarios; nov: 25 ensayos en total de la campaña | N1: 7 de 10 cumplen. Nov: ver sección 6 | T:1361-1401; M:16, 36-52 |
| Carga (f8) | Perfiles L-01 a L-07 | Generador de `carga/` | Ver sección 7 | Ver sección 7 | T:1489-1499; M |
| Telemetría (f9) | Expedientes por `correlacion_id` | Trazas | TRAZA-EJEMPLO: 0 trazas por `correlacion.id`; EXPEDIENTES (R2, nivel 3): 32 spans en 2 de 2 expedientes | Ambos no cumplen. p50 de recuperación 1060,8 ms frente a umbral de 100 ms (R2 `resumen.md`:352); la unidad del umbral está por definir (H-B-11) | T:1556-1573; M:35 |
| Degradación | No tiene nivel propio | Fase 6 y caos | «Degradación honesta»: 2 verdes y 4 xfail | No cumple (H-A-58); en caos aparece «cumple con aviso» | T:1229; M:98 |
| Seguridad | Por meta | Fases 3, 5 | SEG-01 a SEG-09 | Solo SEG-01 cumple; SEG-02 a SEG-09 no cumplen. SEG-03 (tasa) incluye L-07 (cumple) | T:669-677; M:46 |
| Usabilidad | Protocolo propuesto | Sin sesiones | 0 | USU-02 «No ejecutado: no hay sesiones»; no hay datos | T:699, 2729-2814 |

Matriz NFR (MN:353-366, corte nivel 1 de oct ampliado con la corrida oe5 de A): 52 ids y 99 filas, no 60. Estados de fila: 54 ejecutadas, 25 por medir, 9 omitidas, 8 no medibles, más 1 pendiente, 1 hallazgo y 1 protocolo. T:722-741 (corte anterior): 49 ids con 3 cumple, 7 parcial, 19 no cumple y 20 no ejecutado.

Cobertura de líneas (T:856-889): 72,43 % en `d4ea7cb` (12 039 sentencias) y 94,32 % en la punta `6393e6d` (12 112 sentencias); con `greenlet` 96,99 %. MN:141 NFR-MAN-01: línea base 52,98 %, re-base 94,32 % (2026-10-11).

## 3. Conjuntos de oro

Fuente GO:20-30. El oro mide el sistema dado un resultado fijo del modelo, no al modelo (GO:6-8). No hay archivo que describa uno por uno qué mide cada conjunto; los datos de `datos/golden/` están en FINAL. Lista base de 18 renglones (T:995-1025).

| Conjunto | Qué es |
|---|---|
| G01 | tabla limpia (PDF) |
| G02 | multipágina, 7 páginas |
| G03 | foto borrosa |
| G04 | Word (.docx) |
| G05 | manuscrito |
| G06 | sin columna de cantidad |
| G07 | fila partida |
| G08 | página cortada |
| G09 | acentos y mayúsculas |
| G10 | grados variados (Cuarto, 4°, Pre-Jardín, "3 A") |

Resultados de fase 4 (corrida `cabb81daff314f5884ef868f81758f01`, 2026-10-09, FINAL `a/fases-2-4`@`359eeae`; MN:204-211) y re-base sobre `d4ea7cb` (2026-10-11, corrida `9711f678dc11465b8390a339fc438aa4`, FINAL `ae584ad`):

| Meta | Resultado | Cifras originales | Re-base `d4ea7cb` |
|---|---|---|---|
| PRE-01 percepción | no cumple | 51 verdes y 3 xfail; G02 da `pdf_ilegible` (H-A-36); G06 llega con 6 de 18 cantidades en 1 (H-A-38); en E2E G04, G08 y G10 dan 422 | 51 verdes y 3 xfail |
| PRE-02 emparejamiento | no cumple (regla de xfail) | Top-1 difíciles 31/32 = 0,9688; ruta rápida 12/12; ruta lenta 7/12; 175 verdes y 3 xfail | 182 verdes y 2 xfail; 33/34 = 0,9706 |
| PRE-03 anti-alucinación | cumple | 0 productos fuera del catálogo; 17 verdes | 18 verdes |
| PRE-04 abstención | no cumple (H-A-39) | 24 verdes y 11 xfail | 22 verdes y 11 xfail |
| PRE-05 baja confianza | no cumple (H-A-40) | Marca renglones 13, 16 y 17; 1 verde y 1 xfail | igual |
| DORADOS | cumple | 2 pruebas en verde (`TestElOroEsCoherente`) | - |

Conflicto de tope de páginas: skill 5, SDD 25, código 40 (`TOPE_PAGINAS = 40`, MN:337).

## 4. Adversariales de IA

Corrida real `43c0659305e64703bac9b01cdd5173cf`, 2026-10-09, FINAL `a/fases-5-6`@`2022574` (ADV:3-6): 143 pruebas, 120 verdes y 23 xfail, 0 llamadas reales a Gemini. Marco: OWASP LLM 2025 y NIST AI RMF. (T:1093-1098, sobre `ae584ad`, corrida `a22dec22`, da 118 verdes y 25 xfail: ver sección 9.)

| ID | Ataque | Resultado | Hallazgo |
|---|---|---|---|
| ADV-01 | Inyección en el texto | cumple (2 verdes) | - |
| ADV-02 | Inyección en la imagen | cumple (8 verdes); riesgo residual N-61 | - |
| ADV-03 | Esquema roto | no cumple (7 verdes, 8 xfail); cuatro formas dan 500 en vez de 422 | H-A-48 |
| ADV-04 | Fuga del prompt de sistema | no cumple (12 verdes, 2 xfail); el 422 repite 17 fragmentos | H-A-49 |
| ADV-05 | Datos personales (Ley 1581) | no cumple (4 verdes, 3 xfail) | H-C-15, H-C-06 p4 |
| ADV-06 | Agencia excesiva | no cumple (5 verdes, 1 xfail) | H-A-52 |
| ADV-07 | Debilidad de embeddings | no cumple (2 verdes, 2 xfail); un vector rival cambia 6 de 12 pares | H-A-50 |
| ADV-08 | Producto inexistente | cumple (22 verdes) | - |
| ADV-09 | Consumo sin tope | no cumple (11 verdes, 1 xfail); tope de 40 páginas sin 429; COS-01 cumple (0,00 USD) | H-C-07 |
| ADV-10 | Ids de correlación hostiles | no cumple (10 verdes, 6 xfail); 0 ids cruzados | H-C-09 p4, H-A-51 |
| ADV-11 | Cadena de suministro | revisión de lectura, no ensayo: brechas documentadas | H-A-53 |

ADV-12 a ADV-19 (NL2C sobre oe5, `b6b6fe7`; FINAL commits `0489b4b` y `bbd9f60`): no corridos, resultado «por medir». 50 nodos de `--collect-only` (49 esperados en verde y 1 rojo esperado en ADV-15). El modelo es un doble (`nl2c._LLAMAR`). No son cifras de corrida.

Doble de proveedor `fake-gemini` (`fake-gemini/servidor.py:1-30`): imita `generateContent`, responde por hash de la entrada, registra en `presupuesto.log` y anota como `intento_real` cualquier conexión al puerto 443; sostiene la guardia de 0 USD.

## 5. Matriz de RNF

Resumen por atributo (MN:353-366; estados de fila, no cumple/no cumple: la matriz no da ese desglose por atributo):

| Atributo | ids | Filas | ejecutado | por medir | omitida | no medible | otros |
|---|---|---|---|---|---|---|---|
| Escalabilidad | 7 | 8 | 1 | 2 | 3 | 2 | |
| Disponibilidad | 6 | 23 | 6 | 15 | 0 | 0 | 1 pendiente, 1 hallazgo |
| Seguridad y privacidad | 10 | 27 | 21 | 1 | 5 | 0 | |
| Mantenibilidad | 4 | 8 | 8 | 0 | 0 | 0 | |
| Rendimiento | 11 | 12 | 4 | 4 | 0 | 4 | |
| Usabilidad | 2 | 2 | 0 | 0 | 0 | 1 | 1 protocolo |
| Latencia | 3 | 3 | 2 | 1 | 0 | 0 | |
| Costo | 3 | 6 | 5 | 0 | 0 | 1 | |
| Precisión y control humano | 6 | 10 | 7 | 2 | 1 | 0 | |
| Total | 52 | 99 | 54 | 25 | 9 | 8 | |

Desgloses parciales de cumple/no cumple: nivel 1 de B (corrida `20261019-0505-70b9108-f7-9`, 2026-10-19, MN:15): 18 ensayos, 14 cumplen y 4 no. Corrida oe5 de A (base `b6b6fe7`, FINAL `a/fases-2-6-oe5`@`47d9a50`; MN:391, 446-451): 12 cumplen, 4 no cumplen y 2 se caracterizan. No hay total global. MN:379 dice «43 por medir» y MN:390 «25»; vigente 25.

Filas representativas:

| Fila | Meta | Estado | Fuente |
|---|---|---|---|
| NFR-SEG-01 | Pago sin PAN | cumple (0 PAN en 248 columnas), fase 3, corrida `76504bb0` | MN:107 |
| NFR-SEG-03 | Tope de páginas y presupuesto | no cumple (FINAL `a/fases-5-6`@`2022574`) | MN:109 |
| NFR-DIS-01 | Aislamiento por caída (A1-A7 al 100 %) | no cumple; 7 de 10 CH cumplen, fallan CH-04 y otros (H-B-01 a H-B-03) | MN:76 |
| NFR-REN-02 | P95 catálogo <= 300 ms | cumple en lo medido (22 ms en L-01, 160 ms en L-02, oct) | MN:158 |
| NFR-REN-04 | Traza completa subida a kit | no cumple (H-C-09 punto 3) | MN:160 |
| NFR-LAT-01 | P95 catálogo | se reporta: 22 ms (L-01), 160 ms (L-02) | MN:185 |
| NFR-COS-01 | 0 USD | cumple (0 llamadas reales) | MN:193 |
| NFR-MAN-01 | Cobertura >= 50 % | cumple: 52,98 % base; 94,32 % re-base | MN:141 |
| NFR-PRE-03 | Anti-alucinación | cumple (0 fuera del catálogo) | MN:208 |
| NFR-USU-01 | Usabilidad | no medible (no hay pantalla de encuesta) | MN:176 |
| NFR-ESC-01 | Escalabilidad | omitida (Q-141) | MN:58-59 |
| NFR-ESC-06 | Escalabilidad | por medir | MN |

## 6. Caos y degradación

Modos (MC:9-16): K matar, P pausar, R cortar red, L latencia (Toxiproxy), E 5xx, D dependencia caída. Aserciones A1 a A7 (MC:24-32).

Disyuntor (umbral: abrir en <= 30 s desde la primera falla, T:1244, 666):
- Reloj simulado, fase 6, `ae584ad`: 300,8 s (inteligencia GET), 300,0 s (POST), 150,8 s (comercio). No cumple (T:1266-1268; H-A-55).
- Docker, catálogo colgado con Toxiproxy, `70b9108`, 2026-10-19: abre a los 26,3 s en inteligencia y comercio; cierra 32,0 s después (T:1300-1310). Cada intento falla en unos 5 s, no en los 60 s o 30 s configurados. H-A-55 «acotado, no cerrado».
- Campaña nov `dc8e2e7` (2026-11-05, M:42, 133): abre en 26,4 s y 26,3 s, cumple; cierra unos 32 s después. H-A-55 sigue acotado y no corregido (el «corrige H-A-55» del CSV es de la herramienta).
- Inconsistencia: DIS-05 queda `no_cumple` (T:666) por el reloj simulado y el TTL (A7 no cumplida, T:1321), mientras el ensayo Docker cumple.

Campaña nov, R1 (M:16, 30-56): 25 ensayos, 14 cumple, 10 no cumple, 1 no concluyente, 0 no ejecutado. Cumplen CH-01 (5,2 s), CH-06, CH-12 (7,8 s), CH-15 (10,5 s), CH-17 (7,3 s) y el disyuntor. Sin ejecutar: 24 filas no medibles o fuera de alcance y 14 ensayos omitidos por decisión de Juan (Q-141), entre ellos CH-29 (M:177-181). Extendidos (CH-02, 03, 05, 07, 08, 10, 11, 13, 14, 16, 18, 19, 22, 27, 33) construidos pero fuera de la campaña; omitidos CH-20, 21, 23, 26, 28, 29, 31, 32, 34, 35.

Caídas fallidas y su arreglo:

| Corrida | Escenario (hallazgo) | Qué falló | Arreglo |
|---|---|---|---|
| Nivel 1 `70b9108` (2026-10-19) | CH-04 (H-B-01) | Con el catálogo caído, `POST /v1/listas/subir` da 500 y la lista no se guarda | Rama `arreglos/h-b-01-03`@`a706edb`. Verificación `9da9dae` (2026-10-20): 202 en 33 ms, recuperación 2,7 s |
| Nivel 1 | CH-12 y CH-15 (H-B-02) | Con Postgres o RabbitMQ caído mueren y no vuelven barredor, pollers, trabajador de inteligencia y repartidor (sin política de reinicio a propósito, Q-36) | Verificación: CH-12 recupera en 7,1 s, CH-15 en 6,9 s |
| Nivel 1 | CH-15 (H-B-03) | Un pago avisa dos veces | Verificación: 1 aviso |
| Nov `dc8e2e7` | CH-04 (H-B-04, baja) | Falla solo `trabajo_reintentable`: vuelve a `fallido` unos 5 s después de retirar la falla, con circuito abierto (cierra en unos 32 s). Recuperación 4,7 s | Sin arreglo; decisión pendiente (M:203-207) |
| Nov | CH-09 (H-B-05 media, H-A-33) | No se libera la reserva vencida; la puerta tardó 300 027 ms en dar el 503. Causa probable: el barredor toma 200 reservas sin `ORDER BY` y había 461 pagadas | Sin arreglo |
| Nov | CH-24 (H-B-06 media) | Supresión queda en `propagando`; Operación escribe la confirmación y publica 0 (sin publicador entre los 14 procesos) | Sin arreglo |
| Nov | CH-30 (H-B-10 media) | Un `down` y `up` pierde un aviso de pago (0 avisos; recuperación 31,5 s). El nodo de RabbitMQ cambia de nombre con el contenedor y arranca vacío. Medido en el stack de QA, no en el compose del producto | Sin arreglo |

Las correcciones de octubre no están integradas a `main` (T:1439-1443). La verificación no repitió los otros siete CH ni midió la importación de la lista guardada. En nov esos síntomas no se repiten (M:136) pero no se sabe si `b6b6fe7` contiene los arreglos (M:115). Las severidades H-B fueron propuestas por la sesión que abrió los hallazgos, para revisión del dueño.

Degradación: la prueba honesta está en la fase 6 (2 verdes, 4 xfail, no cumple, H-A-58, T:1229) y en caos como «cumple con aviso» (M:98).

## 7. Carga

Nivel 1, `70b9108`, 2026-10-19, VM Colima de B, 4 CPU y 8 GiB (T:1489-1499, 1527):

| Perfil | Carga | Peticiones y errores | P95 catálogo |
|---|---|---|---|
| L-01 | 1 usuario, 5 min | 175, 0 errores | 22 ms |
| L-02 | rampa 5 a 100, 15 min | 27 894, 0 errores | 160 ms |

Sin saturación ni 429 en L-02.

Nov, `dc8e2e7`, 2026-11-05, Windows 11 con WSL2 y Docker Desktop, 4 CPU y 7,8 GiB (R1 `resumen.md`:362-369; M:44-51, 87-89). L-02, L-03, L-05 y L-06 no son comparables con una Mac (D-B-11). La máquina anfitriona quedó registrada como «None CPU, None GiB» (M:163).

| Perfil | Veredicto | Cifras |
|---|---|---|
| L-01 | cumple | P95 catálogo 77 ms (umbral 300 ms); 141 de 141 iteraciones |
| L-02 | no cumple | P95 1200 ms antes de saturar; satura desde 30 usuarios (ventana 5, 225 s); error 0,116 % (2 de 1727) |
| L-03 | no cumple | P95 30 000 ms; disponibilidad 49,867 % en la peor ventana (250 usuarios, ventana 18); orden P95 19 000 ms frente a 1500 ms |
| L-05 | no cumple | P95 subida a kit 95,0 s sobre 273 subidas (umbral 90 s); 0 SKU inexistentes en 7644 líneas |
| L-06 | no cumple | Caída del catálogo (CH-25) bajo carga; identidad en 0 % en su peor ventana; catálogo volvió a los 603,3 s |
| L-07 | cumple | 429 en la petición 301 (general) y en la 31 (estricto) |

Notas: L-02 y L-03 (H-B-08): `catalogo` queda en un núcleo, 4685 `ReadTimeout`; muestras de recursos una por minuto, incluyen el generador, pico 377 % (M:171). L-06 (H-B-07): con 100 usuarios identidad e inteligencia en 0 % unos 4 minutos, causa no determinada. L-02 de oct hizo 27 894 peticiones frente a 10 667 en nov: cambian versión y equipo a la vez, no atribuible (M:165). L-04 omitida por Q-141. Logs del gateway de L-03 y L-06 no conservados (M:167).

## 8. Hallazgos

Cabecera de H:38-41 (fecha base 2026-10-08, `58b9e47`; cita `d4ea7cb` 2026-10-11, oe5 `b6b6fe7` y la verificación del 2026-10-20 sobre `a706edb`): 85 vigentes = 17 H-C, 57 H-A y 11 H-B, más 10 H-A cerrados.

Severidad (T:1593-1612, cifras de octubre, desactualizadas): 78 vigentes, 14 altos, 56 medios, 8 bajos (H-C 17: 5/11/1; H-A 58: 9/42/7; H-B 3 medios). M:192 indica que el índice quedó sin actualizar y la tabla ya tiene 11 H-B.

H-B de la campaña de nov (M:93-125): altas H-B-07 y H-B-08; medias H-B-05, H-B-06, H-B-10, y H-B-01 a H-B-03 (corregidos en rama sin integrar); bajas H-B-04, H-B-09 y H-B-11.

Por conteo propio desde la tabla del índice de H (poco fiable, revisar a mano): 82 vigentes (17 H-C, 54 H-A, 11 H-B), 10 H-A cerrados, 92 filas del índice y 95 encabezados `### H-`.

## 9. Conflictos con las cifras vigentes

Cifras vigentes dadas: 2.542 pruebas Python + web 86 + contrato 67; cobertura identidad 77 %, catálogo 54 %, inteligencia 88 %, comercio 83 %, operación 81 %, gateway 98 %; 85 hallazgos vigentes (16 altos); carga M4 25.706 peticiones, 0 errores hasta 100 usuarios.

| Tema | Cifra vigente | Cifra de la fuente QA | Estado |
|---|---|---|---|
| Pruebas Python | 2.542 | 3911 passed y 129 xfailed en `ae584ad` (T:799-812); 1647 passed en `d4ea7cb` | Conflicto. Probablemente otro alcance o corte (QA incluye xfail y suites de QA); sin fuente para reconciliar. Citar con su commit y fecha |
| Web 86 y contrato 67 | 86 y 67 | E2E de interfaz Playwright: 16 verdes y 1 `test.fail`; E2E API 71 verdes y 17 xfail | No comparable; la ficha no trae esas dos cifras |
| Cobertura por servicio | identidad 77, catálogo 54, inteligencia 88, comercio 83, operación 81, gateway 98 | Solo global: 72,43 % (`d4ea7cb`), 94,32 % (`6393e6d`), 96,99 % con `greenlet`; gate >= 50 % | La ficha no contiene cobertura por servicio; no se puede verificar |
| Hallazgos vigentes | 85 (16 altos) | Cabecera de H: 85 (17 H-C, 57 H-A, 11 H-B), coincide. Tabla del índice: 82 vigentes. T:1593-1612: 78 vigentes, 14 altos | 85 coincide con H:38-41; el `.tex` está desactualizado (78/14). Severidad 16 altos coincide con el recuento propio (16 alta, 58 media, 11 baja) pero el desglose por tipo no cuadra con 57 H-A |
| Carga M4 | 25.706 peticiones, 0 errores hasta 100 usuarios | Oct (Colima): 27 894 peticiones, 0 errores (L-02, rampa 5 a 100). Nov (Windows/WSL2): 10 667 peticiones, satura desde 30 usuarios, error 0,116 % | Conflicto. 25.706 no aparece en las fuentes QA; M4 es otro equipo/corrida no presente en el repo QA. Citar aparte con su equipo y fecha |
| Adversariales | - | T:1093-1098: 143 pruebas, 118 verdes y 25 xfail (`a22dec22`, sobre `ae584ad`); ADV:5-6: 120 verdes y 23 xfail (`43c0659305e64703bac9b01cdd5173cf`, 2026-10-09) | Conflicto interno entre dos corridas; usar la que se cite con su id |
| Resiliencia | - | 14 verdes y 27 xfail (T:1233) frente a 29 pruebas propias (T:1209) | Distinto universo (tabla de patrones frente a pruebas propias) |
| Matriz NFR | 60 metas (supuesto) | 52 ids y 99 filas | No son 60 |
| Por medir | - | MN:379 dice 43; MN:390 dice 25 | Vigente 25 |
| Fases | - | Tabla dice «diez fases» pero tiene 11 filas (0 a 10) | Inconsistencia del `.tex` |
| Niveles 2 y 3 | - | `.tex` y entrega dicen pendientes (T:169-174); M los reporta ejecutados | El `.tex` de entrega no incluye los 25 ensayos de nov |
| Disyuntor | - | DIS-05 `no_cumple` (T:666) frente a 26,3 s que cumple en Docker | Reloj simulado y TTL |
| Tope de páginas | - | skill 5, SDD 25, código 40 | Usar 40 (código) |
| L-05 | - | 273 subidas con kit frente a 285 «con 202» (M:187) | Sin reconciliar |

Datos que no existen en las fuentes: objetivo textual por fase; resultados de usabilidad; sesiones; verificación del respaldo local (M:225); sha de la raíz del repo QA (no es git); `evidencias/fase5` y `evidencias/fase7` no revisadas.
