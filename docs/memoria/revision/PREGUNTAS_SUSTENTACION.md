# Preguntas de sustentación (TUKIT)

Une las preguntas de `hallazgos-R4.md` con las de los cinco jurados del council (6 nov 2026). Las páginas son del cuerpo actual (pp. 1-60), verificadas en `e2e-2026-11-06/council/cuerpo.txt`. Donde la respuesta de R4 ya no cuadra con el texto actual, va marcada "(corregida)". Cada respuesta usa solo lo que la memoria permite decir.

## I. Introducción (pp. 1-5)

**1. ¿Con qué revisión sostiene que ninguna solución resuelve la cadena completa? ¿Y un asistente general de IA con una foto de la lista?** (pp. 1, 3, 11-13)
La afirmación lleva la salvedad "hasta donde se revisó". La Tabla 5 (p.13) compara seis plataformas en trece criterios con fuentes públicas consultadas en noviembre de 2026, y deja n/c donde la página no permitió confirmar. No se comparó con un LLM de propósito general leyendo la lista; es una limitación que se reconoce y un camino de trabajo futuro. (Corregida: R4 decía que la tabla estaba en el anexo; ya está en el cuerpo.)

**2. La encuesta es de 60 acudientes de un colegio, con estrato 4 sobrerrepresentado. ¿Cómo justifica llevar el modelo a otros colegios?** (pp. 2, 15, 57-59)
No se generaliza: p.2 dice que la encuesta describe solo a esa población, y las Conclusiones señalan el 68,3 % de estrato 4 y la ausencia de estratos 1 y 6. Agregar un colegio exige cargar y revisar su lista y volver a medir la preferencia de sus familias. (Corregida: R4 señalaba que el sesgo no aparecía; ahora sí.)

**3. ¿Cuál es el sistema real: seis desplegables o catorce servicios?** (pp. 2, 20-22)
Seis desplegables: cinco servicios de dominio y la puerta de enlace, sobre cinco bases. La alternativa B del ATAM tenía 13 servicios más la puerta de enlace (14 en total) y se eligió la de grano grueso B', que es el sistema construido.

**4. ¿Es viable el negocio? ¿Qué pasa si la comisión es del 10 %?** (pp. 5, 57)
Es una estimación con supuestos del equipo: con comisión del 15 %, $29.353 de contribución por kit Ahorrador y 41 kits de punto de equilibrio con la infraestructura del piloto (512 con la escalable). Con 10 % la contribución es negativa. La memoria dice que la operación real debe confirmarlo y que el modelo no se validó con colegios ni tiendas. (Corregida: R4 citaba 770 kits y VPN de $235 millones, cifras que ya no están.)

## II. Descripción general (pp. 6-10)

**5. Con n = 6 y sin grupo de control, ¿qué inferencia permite sobre carga cognitiva y cómo se cumple el objetivo general?** (pp. 7, 54-55, 58-59)
Ninguna causal. El objetivo general dice diseñar el sistema y medir su efecto con padres del sector Salitre; se midió en seis, con protocolo preregistrado. El RTLX fue 9 frente a 63 recordado de la última compra (diferencia 54, IC 23 a 85, dz = 1,83) y se lee como indicio formativo (n < 10), con comparación contra el recuerdo.

**6. ¿Qué objetivo cubre NL2C y por qué la memoria habla de búsqueda híbrida?** (pp. 8-9, 51)
NL2C está en el OE3 (Tablas 2 y 3) y se evalúa en VII.4 con el OE3. La resolución usa un parecido léxico más el coseno (híbrida). (Corregida: R4 describía una contradicción OE3/OE4 que el cuerpo actual ya no tiene.)

## III. Contexto del proyecto (pp. 11-14)

**7. ¿Las tablas de antecedentes son marco teórico o glosario?** (p. 12)
La columna "Lo que toma Tukit" enlaza cada concepto con un reto y una decisión, y la Tabla 5 y 2.3 contrastan con soluciones y trabajo académico. Es un estado del arte breve; no hay tabla comparativa con cifras de otros trabajos.

**8. ¿Con qué evidencia dice que Docling u OCR fallan con fotos de celular?** (pp. 32, 47)
Con medición propia: en la comparación de motores de lectura (VII.1) Gemini obtuvo F1 0,948 frente a 0,673 de Google Vision y 0,298 de reglas, sobre diez documentos y una corrida por motor. Esa distancia con Vision es menos segura por el sesgo del oro.

## IV. Análisis del problema (pp. 15-19)

**9. ¿Cómo se rastrea cada requerimiento hasta su prueba?** (pp. 16-17)
Hay 132 requerimientos (67 funcionales, 49 no funcionales, 16 de aprendizaje automático) y 98 con prioridad MoSCoW; la distribución está en el Anexo X.5. El cuerpo muestra los más importantes con ID (Tabla 8). La matriz completa vive en el SRS, no en el cuerpo.

**10. ¿Cumple el sistema la Ley 1581 con el nombre del menor?** (pp. 17, 32-33, 53)
Cumplimiento parcial, declarado en RNF02: el nombre no se pide (el apodo es opcional y cifrado), pero un nombre que figure en el documento cargado viaja al proveedor (PE-06 pendiente). Varios acudientes subieron listas de sus hijos en el OE5. La depuración es lo primero del trabajo futuro. (Conviene preparar la respuesta sobre qué se hizo con esos datos tras las sesiones.)

## V. Diseño de la solución (pp. 20-30)

**11. El ATAM lo puntuó el equipo. ¿Cómo sabe que los pesos no favorecieron a B'?** (pp. 21-22, 58)
Se perturbaron los diez pesos en ±20 % (20 combinaciones): B' obtuvo 3,88 a 3,94, frente a 3,38 a 3,50 y 2,77 a 2,88; la menor ventaja es 0,40. Es verdad que los puntajes por criterio los asignó el equipo y la sensibilidad no los mueve; la Tabla 24 lo reconoce. (Corregida: R4 decía que el cuerpo no mostraba la sensibilidad; ahora está en p.22.)

**12. ¿Por qué seis desplegables si la escalabilidad no lo exige? ¿No es sobreingeniería?** (pp. 4, 20-22)
Por tres impulsores que no dependen de la carga: recuperabilidad asimétrica (catálogo frente a pedidos), frontera de cumplimiento de los datos de menores y perfil de recurso (inferencia y optimización frente a transacciones). Monolito 2,82, microservicios finos 3,44, B' 3,91. El despliegue evaluado corre en un portátil con un servidor para las cinco bases; el escalado independiente y la restauración por base no se ejercitaron.

**13. ¿Con qué criterios se eligieron RabbitMQ, pgvector, Gemini, Wompi?** (pp. 22, 26-30)
Solo el lenguaje tiene comparación medida (Amdahl, NSGA-II). Las demás se justifican por ADR, por ejemplo Redis como dato recalculable. No hay alternativas medidas para cada una.

**14. ¿Se cumple el OE2 si el diseño evaluado (14 servicios) no es el sistema construido?** (pp. 20-22, 58)
Lo evaluado con ATAM fue B' (cinco servicios de dominio y puerta de enlace), que es lo construido. Las otras dos alternativas eran el contraste. Los 49 ADR y las vistas 4+1 documentan el diseño.

## VI. Desarrollo de la solución (pp. 31-43)

**15. ¿Qué mide la comparación de recuperación y qué sistema produjo las cifras de τ?** (pp. 31, 48, 59)
Parte de las cifras de recuperación y la medición de τ del 4 de octubre pertenecen a un prototipo no integrado (p.31); la p.59 dice que las corridas de τ y las sesiones usaron la misma versión del código. Hay que responder con una sola procedencia (ver COUNCIL.md, A5). Contra el sistema construido no se midió la latencia de la recuperación.

**16. El Algoritmo 2 filtra por máxima disponibilidad f3 antes de aplicar el tope y el sobreprecio. ¿Eso no vuelve f3 lexicográfico?** (pp. 38-40)
Sí: la línea 15 deja solo kits de máxima disponibilidad ("solo lo disponible") y la utilidad MAUT no incluye u3 porque la disponibilidad ya está fijada en su máximo (p.39). El frente sigue siendo de cuatro objetivos, y el kit recomendado se escoge dentro de ese subconjunto.

**17. ¿Qué tan independientes son los conjuntos de oro y qué parte de lo calibrado está validada?** (pp. 31-34, 41-42, 59)
El oro de percepción se construyó corrigiendo la salida de Gemini (coincide en 86,7 % de los ítems literales), 4 anotadores con una pauta común etiquetaron los 405 pares, sin acuerdo entre ellos calculado, (391 de un colegio) y la calibración usa 3 colegios de prueba apartados antes de mirar resultados. Todo se declara en VIII.2.1; lo firme es la ventaja sobre las reglas y sobre el azar.

**18. ¿Contra qué frente exacto se mide el hipervolumen de 0,9969 si hay espacios de hasta 10^17?** (pp. 41-42, 50)
Ocho de las 40 listas de prueba se resolvieron de forma exacta (media 0,9969 en las 40, 0,9962 en las 32 con NSGA-II). Donde el exacto es inviable, la calidad se verificó con instancias de hasta 2^18; más allá no se verificó. No se comparó con otros optimizadores (MOEA/D, SPEA2); se apoya en la referencia [4].

**19. ¿Por qué τ = 0,75 si la validación cruzada sugiere 0,33 a 0,60 y no se calculó el acuerdo entre los 4 anotadores?** (pp. 34, 48-49)
Se mantiene por prudencia: sin acuerdo calculado entre los 4 anotadores y con 391 de 405 pares de un colegio, la medición es débil. En τ = 0,75 la precisión fue 0,968 (IC 0,948 a 0,986) y la cobertura 84,0 % (aceptar todo daría 0,867). El costo de un τ alto es solo más revisión humana, y toda lista nueva se revisa antes de publicarse (PE-04). El 84 % es entre pares con candidato; de punta a punta se resolvió solo el 35,3 %.

## VII. Resultados (pp. 46-56)

**20. ¿Qué cifra describe el sistema entregado y cuál es el F1 independiente de Gemini?** (pp. 46-47, 59)
No hay F1 con oro independiente: el 0,948 está sesgado a favor de Gemini y se declara. Lo firme es la ventaja sobre reglas (0,298); frente a Google Vision (0,673) es menos segura. La medición con el modelo real en el sistema integrado queda pendiente.

**21. ¿Por qué NSGA-II si la programación dinámica da el óptimo en 0,64 ms en listas reales? ¿Qué aporta lo multiobjetivo?** (pp. 40-42, 50)
Lo que aporta es el frente: un solo kit cubre 0,517 (MAUT), 0,362 (Ahorrador) o 0,231 (Premium) del hipervolumen exacto. La programación dinámica sirve para un perfil escalarizado; en un hogar extremo (8 hijos, 313 líneas) tardó 2,56 s y 297 MiB frente a 1,46 s y 12,6 MiB de NSGA-II. Igualar el costo en el Ahorrador no distingue a NSGA-II de una regla simple, que también marca 100 %, y es de una semilla.

**22. Con seis acudientes conocidos del equipo, ¿cómo declara "Cumplido" el OE5 si T1 fue 4/6 y T4 1/5?** (pp. 54-55, 58-59)
El OE5 pedía ejecutar pruebas funcionales, no funcionales, de carga y de usabilidad con usuarios reales; se ejecutaron las cuatro clases. C1 (SUS 90, IC 82 a 98) y C2 se cumplen; C3 solo en el pago (T6). T1 y T4 se leen como hallazgos de diseño con cambios priorizados. Los límites (conveniencia, una moderadora, formularios a los 2-3 días, sin SEQ) están declarados. Si el SUS hubiera salido 60, el criterio C1 no se habría cumplido y el estado tendría que haberse matizado más.

**23. SUS 90 y NPS +83 conviven con T4 1 de 5. ¿No es sesgo de cortesía?** (pp. 54-55)
Puede serlo; la memoria dice que varios participantes conocen al equipo. Por eso la lectura se apoya en las observaciones (navegación a "Ver mis kits", origen del precio, etiqueta "confiable", listas largas) y no solo en el SUS.

**24. ¿Qué parte del OE4 ("integrada con la pasarela de pagos") está demostrada si Wompi nunca se ejecutó?** (pp. 17, 45, 52, 56)
Solo el flujo con la pasarela simulada, con confirmación idempotente por aviso y por consulta, probada con simuladores. Los "6 de 6 pagaron" son pagos simulados que se aprueban solos. El sandbox y el cobro real son trabajo futuro. (Hay una frase en p.17 que dice lo contrario y debe corregirse; ver COUNCIL.md, A3.)

**25. Hay 85 hallazgos vigentes, 16 de severidad alta. ¿Es responsable haber probado con familias?** (pp. 52-53, 60)
Vigentes al 5 de noviembre: 85 (16 altos, 58 medios, 11 bajos) y 10 cerrados. Las sesiones fueron con consentimiento y los hallazgos altos (rutas de administración sin sesión, administrador sin segundo factor, depuración del nombre) encabezan el trabajo futuro antes de operar con datos y pagos reales. Solo una de ocho características ISO se declara "Probada". (Corregida: R4 citaba 78 y 59.)

**26. ¿Qué se puede afirmar de seguridad del asistente NL2C con 0 de 81 ataques?** (pp. 42, 51, 53, 59)
Que no se encontró un ataque exitoso. La cota de 3,7 % por regla de tres supone intentos independientes; son 27 ataques por 3 repeticiones, así que la cota honesta está cerca de 11 %. Los escribió el equipo y el criterio de descarte de la última ronda cambió sin preregistro. Ningún acudiente usó el asistente.

**27. ¿Dónde está el consentimiento informado y quién aprobó el protocolo ético?** (p. 54)
El cuerpo dice que las sesiones se grabaron con consentimiento conforme a la Ley 1581 y se transcribieron en el equipo del proyecto. El formato firmado y la instancia que aprobó el protocolo no están en el cuerpo; hay que llevarlos a la sustentación.

**28. ¿Por qué la prueba de carga usa percepción simulada y una sola máquina? ¿Qué garantiza el RNF05?** (pp. 52, 59)
No lo garantiza para el sistema completo: el catálogo resistió 25.706 peticiones sin error hasta 100 usuarios en un Apple M4; la percepción con el modelo real y los niveles 2 y 3 de degradación quedaron sin ejecutar.

**29. ¿Qué pasa con una lista de un colegio nuevo? ¿Los 149 conceptos la cubren?** (pp. 2, 33, 48-49, 59)
El código no cambia, pero el catálogo necesita curaduría: en el ensayo con 14 PDF (4.414 renglones) el sistema se abstuvo en 926 (20,98 %) y dejó 1.397 productos faltantes. Cada lista nueva se revisa completa antes de publicarse. La cobertura de 25 conceptos para el 80,97 % se calculó con las listas que definieron los conceptos.

## VIII. Conclusiones (pp. 57-60)

**30. ¿Qué parte del objetivo general queda demostrada con pago simulado, oro sesgado y seguridad abierta?** (pp. 58-59)
Que el recorrido de la lista al pedido pagado funciona en el piloto y que la carga percibida fue baja en seis acudientes. No queda demostrado: pago real, generalización a otros colegios, el efecto causal sobre la carga ni la elección autónoma del kit (T4). La Tabla 24 deja el alcance de cada objetivo.

**31. ¿Se hizo una medición de impacto ambiental o social?** (p. 57)
Ambiental: no, solo es una hipótesis. Social: el 65 % reportó cuatro horas o más de compra frente a unos minutos de sesión con Tukit, con la salvedad de que son medidas distintas.

**32. ¿Con cuántos hallazgos abiertos cierra el trabajo y qué se hace con ellos?** (pp. 52, 60)
85 vigentes al 5 de noviembre, con el cierre de los 16 altos como primer punto del trabajo futuro (Sección VII.5). (Corregida: R4 mencionaba 78 frente a 59.)

**33. ¿Por qué las referencias de normas retiradas (IEEE 830, 1058)?** (pp. 6, 14, 16)
El cuerpo cita IEEE 830 "y su sucesor, ISO/IEC/IEEE 29148" [8, 28] (p.16). Se usó la forma de especificación de 830 porque guió el SRS entregado; el sucesor se cita junto a ella. Conviene revisar [15], [32], [58], [60] antes de entregar.
