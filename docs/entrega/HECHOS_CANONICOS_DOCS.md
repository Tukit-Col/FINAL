# Hechos canónicos de los documentos (puerta de consistencia)

Cada fila: término o cifra, valor canónico y fuente. Estado: V = verificado en código o documento fuente; P = pendiente de confirmar (depende de otra sesión o de decisión del equipo). Documentos que ya lo aplican: `VFP_ISIS2610G19_v4.docx` y las cuatro enmiendas de esta carpeta.

## Alcance y producto

| Término | Valor canónico | Fuente | Estado |
|---|---|---|---|
| Cliente | PWA instalable (no app nativa) | rama `validacion/oe5`, `apps/web` | V |
| Capacitor / apps nativas | No existe. Solo trabajo futuro, nunca como hecho | coordinación | V |
| Despliegue | Local: Docker Compose (`infra/docker-compose.yml`) para PostgreSQL, RabbitMQ, Redis y Jaeger, y `make arriba` para las apps y los servicios; sin Kubernetes, autoescalado ni clúster gestionado | `Makefile`, `infra/` | V |
| Desplegables | 6 con código: identidad, catálogo, inteligencia, comercio, operación y puerta de enlace. La ingesta del diseño (ADR 0012, 0014) se reemplazó por el catálogo curado y no tiene servicio (decisión del autor, 5-nov-2026) | `servicios/` (6 carpetas) | V |
| Servicios de dominio con base propia | 5 (el mapa de 6 era el ADR 0001, superado) | SAD líneas 315 a 323 | V |
| Bases de datos | 5 | SAD | V |
| Tablas | 74 (manifiesto: identidad 16, catálogo 19, inteligencia 12, comercio 18, operación 9; igual que los modelos del código). LEEME (70) y README (69) están desactualizados | `arquitectura/manifiesto.toml`, `servicios/*/modelos` | V |
| Consolidación histórica | 14 servicios a 6 (ADR 0001), luego a 5 más gateway e ingesta (ADR 0012) | SAD | V |
| Lenguaje de ingesta | Python (el manifiesto declara `lenguaje = "python"` en los servicios) | manifiesto | V |

## Optimización

| Término | Valor canónico | Fuente | Estado |
|---|---|---|---|
| Objetivos | 4: costo (min), fidelidad, disponibilidad, personaje | `optimizador.py`, ADR 0030 | V |
| Perfiles de kit | 4: Ahorrador, Fan, Premium, A tu Medida | ADR 0030 | V |
| Enumeración exacta | hasta `LIMITE_ENUMERACION = 4096`; por encima NSGA-II | `optimizador.py` línea 102 | V |
| Población | min(100, max(20, 6·n)), par (calibrada) | `optimizador.py`, `calibracion_nsga.json` | V |
| Generaciones | 10·log10(espacio), acotadas a 15 a 60 (calibradas) | `optimizador.py`, `calibracion_nsga.json` | V |
| Semilla | fija | `optimizador.py` | V |
| Biblioteca | pymoo, sin respaldo heurístico (fail-loud) | memoria del proyecto | V |
| Presupuesto | se aplica después del frente | ADR 0029 | V |
| Selección a posteriori | MAUT: U = w_precio·u_costo + (w_marca+w_calidad)·u_fidelidad + w_personaje·u_personaje. En el código: `elegir_recomendado_maut` | `optimizador.py`, spec 2026-09-22 | V |
| Pesos P21 | 0,285 precio / 0,273 marca / 0,255 calidad / 0,187 personaje (reemplazan 0,35/0,30/0,25/0,10). En el código desde a664810 | `modelos/base.py` PESOS_POR_OMISION; `pesos_p21.json` (IC 95 % bootstrap) | V |
| Independencia preferencial | supuesto declarado | spec | V |
| Regla de recomendación | Fan si pidió personaje; si no, A tu Medida cuando ese kit existe, es decir, cuando eligió el punto medio de gasto o declaró un tope (con el tope declarado o, sin tope, a mitad de camino entre Ahorrador y Premium); si no existe, Premium cuando el sobreprecio aceptado es de al menos 10 % y MAUT lo prefiere; en otro caso Ahorrador; al final, si el elegido se pasa del tope, el de mayor fidelidad que cabe | `optimizador.py` `recomendar` | V |

## Resolución de ítems

| Término | Valor canónico | Fuente | Estado |
|---|---|---|---|
| Estados | RESUELTO_AUTO, AMBIGUO, SIN_MATCH, HUECO_CATALOGO (v3: COINCIDENCIA, COINCIDENCIA_PARCIAL, SIN_COINCIDENCIA) | `trabajos.py` | V |
| Método | híbrido léxico más coseno | código | V |
| Embeddings | `gemini-embedding-001`, 1.024 dimensiones, HNSW en pgvector | código, SDD | V |
| τ | 0,75 (`TAU_POR_OMISION`, variable TUKIT_TAU), calibrado sobre 405 pares anotados (18 listas, 3 colegios): precisión 0,968 (IC 0,948–0,986), exhaustividad 0,937, AUC 0,921; límite declarado una vez en VIII: un solo anotador y un colegio con 391 de los 405 pares | `trabajos.py` línea 77; `cifras_calibracion.tex` (\calTau*) | V |
| 0,630 (ADR 0010) y 0,85 como τ | Retirados de todos los documentos | coordinación | V |
| 0,85 / 0,50 del SDD (8.3) | Clasificación del puntaje multiatributo del mejor candidato; es otro parámetro que τ y se nombra así | SDD 8.3 | V |
| Brecha δ = 0,05 del SDD | No aparece en `estado_desde_emparejamiento`; retirar o marcar no implementada | `dominio/pipeline.py` | V |
| Calibración (precisión, cobertura, AUC) | No se citan: no hay una calibración válida | coordinación | V |
| Listas de útiles | 17 colegios con lista, 4.719 ítems en el corpus vigente (`items_lista.csv`, con libros, licencias y uniformes). El OE1 (acta del 21-sep) contó 3.608 ítems y 1.451 formas de nombrar sobre el corpus de entonces (`datos/listas/oe1/Corpus_ItemLista.csv`, copia de `Arquitectura/Corpus_ItemLista.csv`; verificado: 3.610 filas, 1.451 textos distintos); son el mismo corpus de 17 colegios más 1.109 ítems agregados después (verificado: los 3.610 del OE1 están todos en el corpus vigente) | `datos/listas/colegios.csv`, `items_lista.csv` | V |

## NL2C

| Término | Valor canónico | Fuente | Estado |
|---|---|---|---|
| Estado | Fusionado en `validacion/oe5` (bf8b7d5): `/v1/nl2c/interpretar`, asistente "pídeme un cambio" en `/kits` (propuesta de cambio o descarte confirmada por el padre); el panel de `/empezar` existe pero va apagado (`NEXT_PUBLIC_TUKIT_ASISTENTE_EMPEZAR`, decisión del equipo 2026-11-02: en el inicio se usa el formulario guiado) | git | V |
| Arquitectura | plan y luego ejecución; separación de datos y control al estilo CaMeL; Pydantic con `extra="forbid"`; doble feature flag; UI generativa armada por el servidor y revalidada en la web | `nl2c.py` | V |
| Límite de tasa | en la puerta de enlace (ADR 0047) | ADR | V |
| Riesgos OWASP | LLM01, 02, 05, 06, 10 | S4 | V |
| Modelo | gemini-3.5-flash-lite, temperatura 0 | S4 | V |
| Cifras de evaluación | Ronda 3 (cifras de la memoria): utilidad 58/70, F1 1,000 en personajes y marcas, ASR 0/81 (cota superior del 95 % cerca de 3,7 %), p50 1.000 ms y p95 1.177 ms, utilidad bajo ataque 36/60, controles del kit 12/12. Ronda 2 (referencia): 57/70, ASR 0/81. Cambio de criterio `descarte_aplicable` → `descarte_sin_confirmar` declarado como no preregistrado | `docs/informes/nl2c/resultados/ronda3_*.json` | V |
| Salida R | {filtros duros, pesos NSGA, preferencias PRM} | S4 | V |
| Filtros duros en el optimizador | `marcas_excluidas` y `solo_disponibles` llegan al optimizador (commit 0059f6d) y se aplican antes del frente de Pareto, también en el carrusel de opciones y en el cambio de producto (976deb1). La marca que el colegio exige en el renglón no se quita. La ruta rápida `aplicar-canonico` los rechaza con 422 `filtros_requieren_recalculo`. Ya no se documenta como brecha. Límite: `solo_disponibles` usa la oferta activa con precio vigente, no stock por tienda | `optimizador.py`, `test_filtros_duros.py` | V |
| Lectura de un kit | con dueño de cuenta con clave solo lo lee su sesión o el staff (sin sesión 401, otra cuenta 404); trabajos anónimos o de contacto sin clave se leen por identificador (commit 0c9d1e1). Registro y cuenta exigen `acepta_terminos` (422 `consentimiento_requerido`) | `routers/inteligencia.py`, IDOR 2026-11-02 | V |
| Versión de Next.js | 16.4.3 en web y admin; `npm audit --omit=dev` en 0 (commit a201f4c) | `package.json` | V |
| Cobertura de pruebas (2026-11-02) | identidad 77 %, catálogo 54 %, inteligencia 88 %, comercio 83 %, operación 81 %, gateway 98 %, `tukit_comun` 85 %; sin umbral de falla. Suite: 2.542 pruebas Python pasan, 1 saltada; web 86, contrato 67 | `pytest-cov`, `make prueba` | V |
| Carga de lectura | 1 a 20 usuarios, error 0 %, p95 entre 9,6 y 48,7 ms, 962 peticiones/s como máximo; no cubre DP-02 (50 concurrentes, kits y checkout) | `ensayos/carga/` | V |

## Pagos y legal

| Término | Valor canónico | Fuente | Estado |
|---|---|---|---|
| Pasarela | Wompi (widget ADR 0033, webhook ADR 0034, sandbox); ePayco y Stripe descartados (ADR 0011) | ADR | V |
| Modo por defecto | simulado (`WOMPI_MODO`) | código | V |
| Comisiones de referencia | PSE cerca de 1,49 %; tarjetas cerca de 2,99 %; ePayco 2,79 a 3,50 % (verificar vigencia) | documentación de las pasarelas | P |
| Retracto | Ley 1480 de 2011, art. 47: 5 días hábiles para retractarse, 30 días calendario para el reembolso | ley | V |
| Datos personales | Ley 1581 de 2012; Decreto 1377 de 2013 | ley | V |
| Retención | datos de investigación eliminados 12 meses después de la aprobación del trabajo de grado; grabaciones hasta 30 días | consentimiento | V |
| Normativa de listas escolares | Solo la Ley 1269 de 2008, art. 1 (parágrafo 1° del art. 203 de la Ley 115 de 1994), verificada en la Secretaría del Senado. Se retiran la Resolución 17821 de 2023 (no verificable en el portal del MEN; su título trata de tarifas) y la Resolución 019805 y la Circular 002 (la memoria ya las retiró) | coordinación, Senado | V |

## Investigación y validación

| Término | Valor canónico | Fuente | Estado |
|---|---|---|---|
| Encuesta | N = 65 recibidas, n = 60 analizables; un colegio (Agustiniano Ciudad Salitre), sesgo a estrato 4 | SRS, dossier | V |
| Encuesta no es la muestra de usabilidad | confirmado | ENMIENDA_SRS_v7 R2 | V |
| P15 | personaje es el primer criterio para 11,7 % (7 de 60) | dossier | V |
| Sobreprecio | 70 % (42 de 60) pagaría hasta 5 % más | dossier | V |
| OE5 | Una sola ronda, 2 y 3-nov-2026, versión `b6b6fe7`, 6 acudientes del Colegio Agustiniano Ciudad Salitre (5 remotas, 1 presencial; ACU-04 grabada parcial: T1 codificada y pago aprobado visible en su segunda grabación, así que los seis pagos se observaron). Sin ronda 1. Sesión de 15 min con entrevista oral; SUS, RTLX y NPS por formulario el 5-nov (6/6): SUS 90 [82, 98] (C1 cumple), RTLX habitual 63 vs TUKIT 9, diferencia 54 [23, 85], dz 1,83 (C2 cumple), NPS +83 [50, 100]; SEQ no aplicado. Éxito sin ayuda: T1 4/6, T2 3/5, T3 4/5, T4 1/5, T5 3/5, T6 4/5, T7 2/2; T8 nadie la intentó. C3 alcanzado en T6 (no en T1 ni T4). 4 de 6 la llamaron fácil, intuitiva o rápida. Tiempo activo de las sesiones completas 2,4 a 10,3 min. OE5: Cumplido (C1 y C2 cumplen; C3 en T6, formativo en T1 y T4) | `datos_ronda2.csv`, `oe5_cierre/salida_analisis.txt`, `analisis_oe5.py`, `plan_analisis_oe5.md` | V |
| Muestra | mínimo n ≥ 5 por ronda (Nielsen 1994), ideal n ≥ 20; n < 20 exploratorio | VFP v4 | V |
| Carga cognitiva | medida principal: conteo de interacciones discretas; complementaria: RTLX (Hart 2006) | VFP v4, ENMIENDA_SRS_v7 R1 | V |
| Instrumentos | SUS (umbral 68), NPS, pensamiento en voz alta | SPMP, WBS | V |
| Metodología | CRISP-DM extendido con revisión humana | VFP v4 | V |

## Documentos

| Término | Valor canónico | Fuente | Estado |
|---|---|---|---|
| Requisitos del SRS | 132 (RF 67, RNF 49, RML 16); el texto v6 decía 131 | tabla 39 del SRS v6 | V |
| Objetivos específicos | 5; OE3 y OE4 reescritos en la VFP v4 | VFP v4 | V |
| Objetivos del optimizador (documentos) | 4 (SPMP v3 y SDD decían 3) | ver enmiendas | V |
| Control de versiones | VFP v4 fechada 01/11/2026, sin retrodatar; v3 (27/04/2026) sigue siendo la aprobada | VFP v4 | V |
| Referencias nuevas de la VFP v4 | [58] a [72] | VFP v4 | V |
| Miettinen | K. Miettinen, Nonlinear Multiobjective Optimization, Kluwer Academic Publishers, 1999 | coordinación | V |
| Wirth y Hipp | Proc. 4th Int. Conf. on the Practical Applications of Knowledge Discovery and Data Mining, 2000, pp. 29-39 | coordinación | V |

## Alcance reducido y entregables

1. Panel de colegio (Módulo 7 del SRS, CO-01 y CO-02) y ajuste de presupuesto en vivo: estaban en la v3; no existen en el producto. Se registran en la tabla de versiones como alcance reducido, con justificación y trabajo futuro. No se afirma que existan.
2. Panel de privacidad (consulta, exportación y supresión; PV-02, Ley 1581): entregable, en implementación por la coordinación. Se redacta como entregable.
3. Offline-first no verificado.
4. Los conteos del catálogo cambian mientras S1 cura; citar solo cifras del manifiesto final.

## Calibración del optimizador (S2, fusionado en validacion/oe5)
| Hecho | Valor | Fuente | Estado |
|---|---|---|---|
| Población NSGA-II | min(100, max(20, 6n)), par | `optimizador.py`, `calibracion_nsga.json` | V |
| Generaciones NSGA-II | min(60, max(15, 10·log10 S)) | ídem | V |
| Elección de la configuración | CV 5 pliegues agrupada por colegio, elegida en 4/5; prueba (32 listas, uso único): HV 0,9962 contra 0,9996 (Δ −0,0034, IC [−0,0054, −0,0017]); tiempo medio 2,04 s → 0,47 s | `calibracion_nsga.json` | V |
| Umbral 4.096 | el exacto deja de ganar en S≈4.932 (mediana) / 2.380 (p95); exacto más rápido en 28/30 subproblemas bajo 4.096 y en 1/24 por encima | `umbral.json`, `umbral_elegida.json` | V |
| Sensibilidad MAUT | el kit recomendado se mantiene en 0,965 / 0,986 / 0,946 de los sorteos (σ 0,05/0,10/0,20); peor lista 0,54 | `sensibilidad.json` | V |
| HV por perfil (relativo al frente exacto) | MAUT-P21 0,517; Ahorrador 0,362; Premium 0,231; frente NSGA-II 0,9969 del exacto | `hipervolumen_prueba.json` | V |
| Regla `calidad_primero` | Retirada; Premium se decide con MAUT | `optimizador.py` | V |
| Corpus de calibración | 174 listas de 17 colegios; 175 instancias del benchmark (una sin renglones decidibles) | `docs/informes/calibracion/README.md` | V |
| Semilla | 0 por omisión en el código; la calibración usó 20261101 | `optimizador.py`, README de calibración | V |

| Carga L-02 (RNF05, DP-02) | 5-nov-2026, versión `dc8e2e7` (b6b6fe7 + override del modelo simulado), rampa de 5 a 100 usuarios en 15 min con el arnés de Tukit-QA. Windows 11 / WSL2 con 4 CPU: saturación desde 30 usuarios (H-B-08). Apple M4 nativo: 25.706 peticiones, 0 errores, sin saturación hasta 100; p95 del catálogo por ventana de 180 a 420 ms hasta 50 usuarios y 2,5 s con 100; catálogo al 100 % de un núcleo en el pico | `docs/informes/calidad/carga_mac_2026-11-05/`, Tukit-QA `resultados/informe-fases-7-9.md` | V |
| Hallazgos de QA | 85 vigentes (17 H-C, 57 H-A, 11 H-B; 16 alta, 58 media, 11 baja) y 10 cerrados, al 5-nov-2026 | Tukit-QA `trazabilidad/hallazgos.md`, `docs/informes/calidad/hallazgos_qa_oficial.csv` | V |
| Benchmark PD vs NSGA-II | FINAL@a8f09c7 (optimizador igual a b6b6fe7): PD = enumeración en 65/65 listas; medianas PD 0,64 ms / 0,12 MiB vs NSGA-II 243 ms / 0,82 MiB; hogar de 8 hijos y 313 líneas PD 2,56 s / 297 MiB vs 1,46 s / 12,6 MiB; una semilla | Tukit-Benchmarks `06-optimizacion` (8d917ae) | V |

| ADR | 49 decisiones: 0001-0049 en `docs/arquitectura/adr/` (los 0001-0026 se copiaron allí el 5-nov desde la carpeta `Arquitectura/adr/`, hoy archivada; su índice es `INDICE_0001-0026.md`) | `docs/arquitectura/adr/` | V |
| Calibración de τ (re-corrida 5-nov sobre b6b6fe7) | 405 pares, 351 aciertos, AUC 0,921; en τ = 0,75: TP 329, FP 11, FN 22, TN 43, precisión 0,968, recall 0,937, F1 0,952 | `docs/informes/calibracion/tau.json` | V |
