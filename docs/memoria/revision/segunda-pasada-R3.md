# Segunda pasada R3 (2026-11-05)

PDF revisado: `main.pdf` del commit `5c1f72b` (92 páginas; página impresa = PDF − 10). Rango: capítulos VI a VIII, pp. 28–55. A mitad de la revisión entró `650154a`/`5c1f72b`; todo lo de abajo ya es contra esa versión.

**Resumen.** De los 40 hallazgos ALTO y MEDIO de la primera pasada, 27 quedaron resueltos, 7 parciales y 6 sin resolver. Aparecen 11 hallazgos nuevos (2 altos). Lo más grave: las conclusiones dicen que «ninguna medición de resolución describe el sistema construido», pero Resultados ahora evalúa τ sobre `b6b6fe7`. El Desarrollo y la sección de calibración siguen diciendo que τ «no se pudo calibrar» porque «no hay decisiones humanas». La regla preregistrada del OE5 («cumplido solo si C1, C2 y C3») sigue sin declararse.

**Cifras nuevas contrastadas.** Todas cuadran con su fuente, salvo los matices de N8 a N10.
- **τ** (`tau.json`): TP/FP/FN/TN 329/11/22/43; P 0,968 [0,948–0,986]; R 0,937 [0,912–0,960]; F1 0,952 [0,935–0,968]; AUC 0,921 [0,866–0,968]; cobertura 84,0 % (340/405); aceptar todo da 0,867 (351/405).
- **Punto de equilibrio** (`PUNTO_EQUILIBRIO.md`, escenario base): ticket $609.343, contribución $29.353, 41 kits (≈ 3 % de 1.340 familias) y 512 kits; con comisión del 10 % la contribución es negativa (−$1.114).
- **L-02** (`carga_mac_2026-11-05/`): 25.706 peticiones sin error; p95 del catálogo de 49 a 420 ms hasta 50 usuarios y de 2.500 ms con 100; supera 300 ms desde 25 usuarios; catálogo al 100 % de un núcleo.
- **HV:** 0,9969 en 40 listas y 0,9962 en las 32 con NSGA-II (recalculado desde `hipervolumen_prueba.json`: 0,99616).
- **QA:** 85 vigentes (16 altos, 58 medios, 11 bajos) y 10 cerrados. Cuadra con `hallazgos_qa_oficial.csv` y con la regla de `hallazgos_a_tex.py` («vigente = no empieza por cerrado»).

## (1) Estado de los hallazgos ALTO y MEDIO de la primera pasada

| # | Sev. | Hallazgo (resumen) | Estado | Pág. nueva | Evidencia |
|---|---|---|---|---|---|
| 1 | ALTO | OE5 «Cumplido» contra la regla preregistrada C1+C2+C3 | **Parcial** | 50, 53 | La Lectura reconoce que C3 falla en T1 y T4 y funda el «Cumplido» en las cuatro clases de prueba, el pago y C1+C2. El Límite enumera desviaciones, pero no dice que el plan exigía las tres ni que este «Cumplido» se aparta de esa regla. Tab. 25 y Tab. resumen (p. 43) siguen en «Cumplido» sin matiz. |
| 2 | ALTO | Conteo de interacciones no medido ni declarado | Resuelto | 50 | «No se midió el conteo de interacciones (lo sustituyó el RTLX)». |
| 3 | ALTO | Satisfacción atribuida a la entrevista | Resuelto | 49–50 | SUS y NPS por formulario; la entrevista queda como complemento. |
| 4 | ALTO | 99 frente a 149 conceptos | Resuelto | 53–54 | «99 conceptos canónicos del corpus (el catálogo actual tiene 149)». |
| 5 | ALTO | HV en 40 listas frente a prueba de 32 | Resuelto | 29, 42, 46, 53 | «40 listas (32 por encima del umbral)»; 0,9962 en las 32. |
| 6 | ALTO | OE4 apoyado en la igualdad no reproducida | Resuelto | 53 | El HV va primero y la igualdad lleva «(una semilla, sin reproducir)». |
| 7 | ALTO | OE3 sin medición del sistema construido | **Parcial** | 45, 53–54 | Ahora sí hay medición sobre `b6b6fe7` (τ, p. 45), pero las conclusiones dicen lo contrario (ver N1) y Tab. 25 OE3 sigue con «τ declarado sin calibrar», sin la precisión de 0,968. |
| 8 | ALTO | «Versión evaluada» con dos sentidos | **Parcial** | 47 | Calidad ya dice «las cifras del 8 de octubre». Pero la leyenda de Tab. 21 dice «las dos últimas, posteriores a la versión evaluada», cuando las auditorías del 11 y el 12 de octubre son anteriores a `b6b6fe7` (2-nov). |
| 9 | ALTO | Nombre real en la captura de logística | Resuelto | 37 | La captura dice «Acudiente de prueba · dirección de prueba» (`13a-logistica-pedidos.png`). |
| 10 | ALTO | Apodo de un menor en `solicitud.jpg` | Resuelto (verificar) | 35 | Ahora es «Sofi». Que sea ficticio no se puede comprobar desde el repo. |
| 11 | MEDIO | Optimización partida en §5 y §7, con la web en medio | No resuelto | 33–42 | Sigue igual: §5 «Optimización del kit», §6 «Aplicación web», §7 «Optimización y calibración». Los pesos P21 se repiten en p. 34 y p. 41. |
| 12 | MEDIO | Percepción y recuperación sin el patrón algorítmico | No resuelto | 29–31 | No hay E/S, seudocódigo ni remisión al anexo de algoritmos (`anexo_algoritmos.tex` no tiene etiqueta que citar). |
| 13 | MEDIO | $c_{\min}$, $\sigma$, filtro por $f_3$ y $u_3$ | Resuelto | 38–39 | R3 los define y aclara «No entra $u_3$…». |
| 14 | MEDIO | $f_4$ premia «cualquier personaje» | No resuelto | 39 | Texto idéntico. |
| 15 | MEDIO | $n$ y $N$ con dos sentidos | No resuelto | 32–33, 38–40 | El Alg. 1 sigue con «$n\leftarrow$ núcleo$(r)$» y «$N=1.030$» productos; el optimizador usa $n$ para las líneas y $N$ para la población. |
| 16 | MEDIO | Corte de 0,5 frente a τ | Resuelto | 32 | «piso de 0,5 … sin correspondencia (el corte de revisión, distinto de τ)». Llamar «corte de revisión» a un piso de sin correspondencia todavía confunde un poco. |
| 17 | MEDIO | Seis frente a siete desplegables | Resuelto | 28 | HECHOS ya dice «6 con código». |
| 18 | MEDIO | Hoja de ruta del capítulo desactualizada | Resuelto | 28 | La intro describe el orden real. |
| 19 | MEDIO | «Estudiantes ficticios» frente a listas reales del OE5 | Resuelto | 29 | «en el OE5 varios acudientes subieron listas de sus hijos, y esa depuración sigue pendiente». |
| 20 | MEDIO | 65,3/86,7 % duplicados | Resuelto | 31 | Solo queda el uso del grafo, marcado «(cifras de prototipo)». |
| 21 | MEDIO | 2.202 no cuadra con sus clases | Resuelto | 45 | Ya no se desglosan las clases. |
| 22 | MEDIO | Reparto incompleto de los 14 defectos | Resuelto | 47 | El reparto salió del cuerpo. |
| 23 | MEDIO | ADR 0015 frente a 0016 | Resuelto | 47, 52 | Las dos dicen ADR 0016 (en p. 26, ADR 0015 es el de dirección, otro tema). |
| 24 | MEDIO | Faltaba el nivel «funcional» de la rúbrica | **Parcial** | 47, 54 | El Método enumera unitarias, de integración, de sistema, adversariales, de degradación y de carga, pero no las funcionales como nivel. La conclusión dice «cuatro niveles» sin nombrarlos. |
| 25 | MEDIO | Tab. de métricas sin las del OE5 | Resuelto | 43 | La nueva Tab. resumen por objetivo incluye el SUS y el éxito. |
| 26 | MEDIO | «Privacidad» como característica ISO | Resuelto | 47 | El desglose por característica salió del texto. |
| 27 | MEDIO | Usabilidad «Cumplido» en Tab. ISO | Resuelto | 48 | Ahora dice «Parcial; C3 solo en T6», con párrafo de lectura después. |
| 28 | MEDIO | Docker Compose frente a Minikube | Resuelto | 48 | «levantados en local con Minikube». |
| 29 | MEDIO | Pago de ACU-04 no observado | Resuelto | 48 | «los seis pagos se observaron porque su segunda grabación muestra el pago aprobado». |
| 30 | MEDIO | Token en el historial sin decir si se revocó | No resuelto | 48 | La Tab. 22 sigue con «un token en el historial». |
| 31 | MEDIO | RTLX como «ahorro medido» | Resuelto | 50 | La frase salió. |
| 32 | MEDIO | «Ninguno la calificó de difícil» | Resuelto | 50 | La frase salió; la escala invertida queda en el Límite. |
| 33 | MEDIO | Recodificación ciega del 30 % no declarada | Resuelto | 50 | «ni se hizo la recodificación ciega del 30 % con kappa». |
| 34 | MEDIO | Pantalla (d) «verificada» con la igualdad | Resuelto | 36 | «Hipervolumen de prueba; T4 → T4 1/5». |
| 35 | MEDIO | Capturas ilegibles y página casi vacía | **Parcial** | 35, 37 | La Fig. 7 creció (2 + 1). La Fig. 6 sigue con seis capturas al 0,32 del ancho, ilegibles en papel, y la p. 37 tiene ~45 % en blanco bajo la figura. |
| 36 | MEDIO | Faltaba el impacto global | Resuelto | 53 | «En el plano global, el resultado se acota a Colombia…». |
| 37 | MEDIO | Alcance reducido no registrado | **Parcial** | 54 | El panel de colegio y el presupuesto en vivo ya están, pero se atribuyen a «la evaluación ordenó»: son alcance reducido desde la v3 y no salieron del OE5. |
| 38 | MEDIO | Orden del trabajo futuro | Resuelto | 54 | El endurecimiento va primero, con los 85 hallazgos. |
| 39 | MEDIO | 3.608 renglones y 68,3 % repetido | **Parcial** | 52–54 | 3.608 queda explicado (4.719 = 3.608 + 1.109). El 68,3 % sigue para dos hechos distintos: «compra en tres o más lugares» (p. 52) y «estrato 4» (p. 53). |
| 40 | MEDIO | «49 ADR» frente a 23 archivos | No resuelto (verificar) | 53 | Tab. 25 sigue con «49 ADR»; `docs/arquitectura/adr/` tiene 23 numerados (el último es el 0049). |

## Hallazgos nuevos

| # | Pág. | Sección / archivo:línea | Lente | Severidad | Hallazgo | Evidencia | Sugerencia (≤1 frase) |
|---|---|---|---|---|---|---|---|
| N1 | 54, 45 | conclusiones.tex:66 (párrafo OE5) frente a resultados.tex:99 y 147 | hilo | ALTO | Las conclusiones dicen que en el OE3 «ninguna medición de resolución describe el sistema construido», cuando Resultados presenta la decisión con τ «sobre la versión evaluada `b6b6fe7`». | «en el OE3, que ninguna medición de resolución describe el sistema construido» | Cambiar el límite por el real: un solo revisor, 3 colegios, 20 valores del puntaje. |
| N2 | 32, 41–42 | desarrolloSolucion.tex:193; optimizacion.tex:212-216 y 235 (A3) | hilo | ALTO | El Desarrollo y la calibración dicen que τ «no se pudo calibrar, porque no hay decisiones humanas registradas», mientras Resultados lo evalúa con 405 pares «que un revisor marcó», con IC y validación cruzada. El lector ve dos verdades. | p. 32 «no hay decisiones humanas registradas sobre ese puntaje»; p. 45 «que un revisor marcó como correctos o incorrectos» | Distinguir «evaluado con la curaduría de un revisor» de «no recalibrado» en los tres lugares. |
| N3 | 45–46 | resultados.tex:97-99 y Límite | cifra | MEDIO | La muestra de τ está concentrada: 391 de los 405 pares (97 %) son de un solo colegio, y el Límite solo dice «Son tres colegios». | `tau.json` colegios: 391, 10 y 4 | Decir el 97 % en el Límite. |
| N4 | 43, 53 | Tab. resumen (resultados.tex:24-29); Tab. 25 | rúbrica | MEDIO | La columna «Estado = Cumplido» de OE3 (lectura y decisión) no tiene criterio: ningún umbral de F1 o de precisión se fijó de antemano, a diferencia del OE4 (8 s) y del OE5 (C1–C3). | «OE3, decisión … 0,968 … Cumplido» | Decir el criterio de cada fila o cambiar la columna a «Lectura». |
| N5 | 43, 53 | Tab. resumen; Tab. 25 OE3 | hilo | MEDIO | NL2C cuenta como evidencia del OE3 en Tab. 25 (58/70 y 0/81), pero Resultados no le da un bloque ni una fila en la Tab. resumen; solo está en p. 42 (Desarrollo) y en el anexo. | Tab. 25: «NL2C con 58 de 70…», Sec. `sec:nl2c` (anexo) | Una fila en la Tab. resumen que remita a p. 42. |
| N6 | 47 | calidad.tex (Resultado, «Cada defecto se fijó como una prueba…») | cifra | MEDIO (verificar) | Se afirma que cada uno de los 85 hallazgos quedó fijado como prueba `xfail`, pero el registro oficial incluye hallazgos de proceso y documentales (p. ej., H-C-01 «CI de `main` en rojo»), y la pasada anterior tenía 108 pruebas para 59. | `hallazgos_qa_oficial.csv`: tipo «proceso», «documental» | Decir cuántos tienen prueba `xfail`. |
| N7 | 47 | calidad.tex; `hallazgos_a_tex.py` | cifra | MEDIO | Tres hallazgos marcados «corregido y verificado» (H-B-01 a H-B-03) cuentan como vigentes, porque la regla solo excluye «cerrado». Serían 82 vigentes y 13 cerrados. | estado «corregido y verificado en la r…» | Moverlos a cerrados o decir por qué siguen vigentes. |
| N8 | 46 | resultados.tex:141-145 | cifra | BAJO | «Bastaría un τ entre 0,33 y 0,60 para llegar a 95 % de precisión», pero en un pliegue la precisión con τ = 0,33 fue de 0,945. | `tau.json` validacion_cruzada_agrupada[1].precision = 0,945 | «cerca de 95 %» o dar el rango por pliegue. |
| N9 | 47 | calidad.tex (L-02) | cifra | BAJO | La saturación «desde 30 usuarios» en la máquina virtual con Windows no tiene archivo en `carga_mac_2026-11-05/` (sin fuente canónica). Locust da 25.773 peticiones agregadas y el resumen, 25.706 (la diferencia parece la preparación). | `locust_stats.csv` Aggregated 25.773 | Citar la carpeta de la corrida en Windows y aclarar qué cuenta el 25.706. |
| N10 | 42, 46 | optimizacion.tex; resultados.tex:175-177 | cifra | BAJO | El 0,9962 de las 32 listas sale de `\calPruebaElegidaHV` (calibración, 5 semillas) y no de `hipervolumen_prueba.json` (30 semillas, 0,99616). Coinciden al redondear, pero son dos mediciones. | `calibracion_nsga.json` 0,99619; `hipervolumen_prueba.json` 0,99616 | Tomar la macro de la misma fuente que el 0,9969. |
| N11 | 50, 53 | oe5.tex (Lectura); conclusiones.tex:66 | hilo | BAJO | «el pago de los seis» sostiene el «Cumplido», pero la Tab. 23 da T6 «4 de 5». La razón (ACU-04 no se codificó en T6) está en Datos, lejos. | p. 50 «en el pago de los seis» | Remitir a la nota de ACU-04 junto a la frase. |

## (2) ¿Algo obliga a ir al anexo para entender el texto?

Ya no para lo esencial: la Tab. 14 de estrategias, la Tab. 15 de datos, la Tab. 21 de auditorías y la Fig. 8 de τ están en el cuerpo. Quedan:
- **Códigos del SRS y del ATAM sin definir en el cuerpo (MEDIO):** PE-04, PE-06, ML-09, NR-02, NR-07, PS-01/02/04, OP-04, DP-03, RNF05, ESC-D1, ESC-D4 y ESC-E4 (pp. 29–48). El lector necesita la tabla de requerimientos del anexo para saber qué es cada uno. Sugerencia: definir cada código en su primera aparición, en la misma frase.
- **Siglas de instrumentos (BAJO):** el SUS, el RTLX y el NPS solo se expanden en el glosario del anexo; en p. 49 aparecen como «el SUS (C1, umbral 68), la carga percibida RTLX». El SEQ (p. 50) no se define.
- **«Heurística por perfil» (BAJO, primera pasada #45):** sigue sin definirse (p. 39).
- **Remisiones que sí son solo de detalle y están bien:** constantes (pp. 31 y 34), pantallas adicionales (p. 34), tablero de calibración (p. 38) y el NL2C completo (p. 42, con su resumen en el cuerpo).

## (3) ¿Cada bloque de objetivo declara su metodología?

| Bloque | Pág. | Metodología declarada | Esquema pregunta → límite |
|---|---|---|---|
| Percepción (OE3) | 43–44 | CRISP-DM, evaluación | Completo |
| Recuperación y decisión (OE3) | 44–46 | CRISP-DM, evaluación | Completo (con N2 y N3) |
| Optimización (OE4) | 46–47 | CRISP-DM, evaluación, más ESC-D4 del ATAM | Completo. La subparte de auditorías de kits no tiene métrica ni método propios, solo «un renglón cumple si…» (BAJO) |
| Verificación integrada (OE5) | 47–48 | ISO/IEC 25010, plan de diez fases | Completo |
| Evaluación con usuarios (OE5) | 48–50 | Protocolo preregistrado del 28-oct | Completo; falta la regla de decisión del protocolo (#1) |
| NL2C (OE3) | — | Sin bloque en Resultados | Ver N5 |
| Conclusiones por OE | 53–54 | Cada OE nombra su fase y su método (Design Thinking, IEEE 830/1016, ATAM, CRISP-DM, protocolo + ISO 25010) | Bien |

La introducción de Resultados (p. 43) declara el esquema y lo cumplen los cinco bloques. La única ausencia es el NL2C.
