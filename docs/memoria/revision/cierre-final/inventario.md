# Inventario de cierre final de la memoria

Rutas de `.tex` relativas a `tukit/docs/memoria/sections/`. Todo viene de los cuatro insumos (conteos, jurado, alineación, páginas). Donde un insumo es vago o falta, se dice.

## 1) Resumen

- Autocontenido: hay 30 líneas con ADR, 15 con rutas/comandos/repositorio y 15 con "anexo". Solo dos referencias a anexo parecen necesarias para entender (`disenoSolucion.tex:209`, `desarrolloSolucion.tex:324`); ambas son juicio del insumo sobre un fragmento, sin contexto completo.
- Tono pendiente: 44 líneas J5 en total, que incluyen las 5 líneas con `\pendienteEvidencia`. Varias son falsos positivos del patrón y están marcadas abajo.
- Jurado: J1/J2, J3, J6, J7, J9, J10, J16, J17 y J18 están pendientes. J4 y J12 están parciales. J11 y J13 ya están resueltas en lo esencial. J14 no se encontró. J5 la cuenta otra agente. J8 y J15 son listados.
- J1/J2 es el más delicado: el texto dice que τ "no se recalibró" y "no se usa como calibración", y la nota pide lo contrario (se calibró con 405 pares).
- J4: faltan en `optimizacion.tex:100-106` la codificación, SBX/PM con reparación, N y G reales y el paso del frente a 2-4 kits.
- Alineación con el equipo: faltan en la memoria actual privacidad, catálogo, métricas y la validación financiera (`tab:proyeccion`, inversión, VPN). Hay 12 cifras en conflicto o sin equivalente; ninguna está resuelta.
- Páginas: cuerpo de 60 páginas, viable pero ajustado. Se necesitan unas 3,9 páginas nuevas y el recorte identificado libera 2,5 a 3,5, más 0,5 a 0,8 de flotantes en las páginas 45-46. El riesgo mayor es el capítulo VI, que absorbe fórmulas sin recorte propio.
- Límites de los insumos: los conteos son de líneas, no de ocurrencias; no se calculó la página de cada línea; la lista J8 está incompleta (15 de 25 sin cerrar); no se comprobó que `\calTauPares` valga 405.

## 2) Autocontenido y tono pendiente

### Conteos por archivo (líneas con coincidencia, `rg -c`)

| Archivo | ADR | Rutas/cmds/repo | anexo | `\pendienteEvidencia` | J5 |
|---|---|---|---|---|---|
| introduccion | 0 | 0 | 1 | 0 | 0 |
| descripcionGeneral | 0 | 1 | 2 | 0 | 3 |
| contextoProyecto | 0 | 0 | 0 | 0 | 1 |
| analisisProblema | 3 | 2 | 3 | 0 | 2 |
| disenoSolucion | 9 | 4 | 2 | 0 | 5 |
| desarrolloSolucion | 15 | 3 | 4 | 1 | 11 |
| optimizacion | 0 | 0 | 1 | 0 | 4 |
| nl2c | 0 | 1 | 1 | 0 | 3 |
| resultados | 0 | 0 | 1 | 3 | 7 |
| calidad | 1 | 1 | 0 | 1 | 5 |
| oe5 | 0 | 2 | 0 | 0 | 2 |
| conclusiones | 2 | 1 | 0 | 0 | 1 |
| **Total** | 30 | 15 | 15 | 5 | 44 |

Notas: líneas, no ocurrencias. Rutas/cmds/repo usa el patrón `\path{|docs/|.md|.py|make |hash|repositorio|monorrepositorio`. J5 incluye las líneas con `\pendienteEvidencia`. Las líneas con ADR se listan por conteo; el insumo no da archivo:línea de cada una salvo `disenoSolucion.tex:218, :231, :246` y `desarrolloSolucion.tex:43`.

### Rutas, comandos, hashes y repositorio a corregir

- descripcionGeneral.tex:104: `docs/negocio/punto\_equilibrio.py`
- analisisProblema.tex:232: "monorrepositorio"
- analisisProblema.tex:234: `make arriba`
- disenoSolucion.tex:168: `make arriba`
- disenoSolucion.tex:218: monorrepositorio y "un solo repositorio" (ADR 0014)
- disenoSolucion.tex:220: "el repositorio único facilita la erosión de fronteras"
- disenoSolucion.tex:246: fila ADR 0014 "Monorrepositorio con despliegue independiente"
- desarrolloSolucion.tex:43: monorrepositorio (ADR 0014)
- desarrolloSolucion.tex:49: versión `b6b6fe7`
- desarrolloSolucion.tex:337: `docs/memoria/img/desarrollo/`
- nl2c.tex:25: `nl2c.py`
- calidad.tex:81: `make arriba`
- oe5.tex:8: `docs/validacion/plan_analisis_oe5.md`
- oe5.tex:32: `analisis_oe5.py` y `docs/validacion/oe5/oe5_ronda2/datos_ronda2.csv`
- conclusiones.tex:62: `b6b6fe7`

### Anexo: clasificación

| Archivo:línea | Clase |
|---|---|
| introduccion.tex:59 | consulta |
| descripcionGeneral.tex:207 | consulta |
| descripcionGeneral.tex:322 | consulta (constantes) |
| analisisProblema.tex:14 | consulta |
| analisisProblema.tex:158 | consulta (MoSCoW) |
| analisisProblema.tex:161 | consulta (comentario) |
| disenoSolucion.tex:209 | necesaria para entender (reparto de las cinco bases) |
| disenoSolucion.tex:231 | consulta (lista de ADR) |
| desarrolloSolucion.tex:178 | consulta (constantes) |
| desarrolloSolucion.tex:306 | consulta (constantes) |
| desarrolloSolucion.tex:317 | consulta |
| desarrolloSolucion.tex:324 | necesaria para entender (repeticiones y límite del OE5) |
| optimizacion.tex:10 | consulta (calibración) |
| nl2c.tex:5 | consulta |
| resultados.tex:152 | consulta (calibración) |

### `\pendienteEvidencia` (5)

- desarrolloSolucion.tex:416: pago de extremo a extremo en el sandbox de Wompi
- resultados.tex:73: latencia de la percepción con el modelo real
- resultados.tex:112: latencia de la recuperación de candidatos
- resultados.tex:119: kappa entre dos anotadores humanos ciegos, n>=30
- calidad.tex:91: niveles 2 y 3 de degradación, carga y telemetría

### Otras frases de tono pendiente (J5)

Falsos positivos probables del patrón `faltan?\b` (el insumo no verificó qué palabra disparó cada uno): disenoSolucion.tex:129, 218, 246; desarrolloSolucion.tex:43; optimizacion.tex:103, 169; nl2c.tex:130; resultados.tex:256.

- descripcionGeneral: :16, :27, :92
- contextoProyecto: :8
- analisisProblema: :188 (falta depurar el nombre), :221 (PE-06 pendiente)
- disenoSolucion: :133 (300,8 s, no se midió), :231
- desarrolloSolucion: :34, :138 (Redis pendiente), :158, :221, :278, :322, :324, :331, :398, :416
- optimizacion: :5, :70
- nl2c: :82, :124
- resultados: :73, :112, :119, :150, :205, :239
- calidad: :55, :56, :62, :91, :93
- oe5: :98, :109
- conclusiones: :23

Algunas de estas son honestas (declaran un límite real) y no necesariamente hay que quitarlas; el insumo no distingue cuáles.

## 3) Notas del jurado J1-J18

| Nota | Dónde | Estado | Qué falta |
|---|---|---|---|
| J1 umbral τ | desarrolloSolucion.tex:185-190; resultados.tex:145-151; optimizacion.tex:213; resultados.tex:30,98,137; analisisProblema.tex:265; descripcionGeneral.tex:252,296 | Pendiente (el texto dice lo contrario) | Decir que τ sí se calibró con 405 pares y reportar `\calTauP{}` (IC `\calTauPBajo`-`\calTauPAlto`) como resultado. Reescribir desarrolloSolucion.tex:189-190 y resultados.tex:149-151. No se comprobó que `\calTauPares` = 405. |
| J2 "sin calibrar" | las mismas tres frases de J1 | Pendiente | Se resuelve con J1. conclusiones.tex:80 ("Calibración con más anotadores") es trabajo futuro y es aceptable. |
| J3 defectos heredados vs sistema final | desarrolloSolucion.tex:45-49; calidad.tex:39-53; conclusiones.tex:13 | Pendiente | Etiquetar en defectos abiertos cuáles son del sistema final (152 puntos de entrada y 14 hallazgos no distinguen). |
| J4 diseño NSGA-II | optimizacion.tex:100-106 (p. 40); desarrolloSolucion.tex:342 | Parcial | Codificación (un índice de candidato por renglón), operadores SBX y PM con reparación por redondeo, N y G reales, paso del frente a 2-4 kits. |
| J5 tono | ver sección 2 | Pendiente, lo cuenta otra agente | Sin resumen en el insumo. |
| J6 datos a Google/Gemini | analisisProblema.tex:220-221; calidad.tex:50-53; desarrolloSolucion.tex:128, 369, 105, 159; nl2c.tex:103, 123 | Pendiente (disperso) | Un párrafo único: qué se envía (página, texto de renglones, dirección, embeddings) y qué no. |
| J7 conclusiones repiten caracterización | conclusiones.tex:13-19, 47, 57 | Pendiente | Quitar cifras de auditoría y corpus repetidas. No se ubicó línea por línea "17 colegios" y "25 conceptos" en conclusiones (en el cuerpo salen en analisisProblema.tex:267). |
| J8 marcas temporales | 25 ocurrencias en 9 archivos: resultados 5, contextoProyecto 4, optimizacion 4, conclusiones 4, descripcionGeneral 3, calidad 2, analisisProblema 1, nl2c 1, desarrolloSolucion 1 | Pendiente | Lista incompleta. Vistas: descripcionGeneral.tex:47, :75; optimizacion.tex:55, :73; conclusiones.tex:68; resultados.tex:141; contextoProyecto.tex:235. Correr el `rg` de la tarea con `-n` para completar. |
| J9 historia v0 14→7→6 | disenoSolucion.tex:73, :96, :218 | Pendiente (pocas líneas, 3-5 dispersas) | No hay narración 14→7→6 explícita. El insumo de páginas dice no haber hallado historia v0 ni "14 servicios" con `rg`, solo la justificación de los seis desplegables (:73, :79); los dos insumos no coinciden del todo. |
| J10 objetivo general | conclusiones.tex:57 (p. 59) | Pendiente (débil) | Una sola oración. Falta argumento en VII.6 y una medida contra el objetivo general. |
| J11 fórmulas con símbolos | optimizacion.tex:61-70, 108-110 | Resuelta en el texto | Alinear la descripción con el código (ver abajo). El texto no menciona los desempates por perfil. |
| J12 componentes vs despliegue | disenoSolucion.tex:152, 163, 178, 191, 200 | Parcial | No hay figura de componentes (C4 nivel 3); la de contenedores cumple parcialmente. |
| J13 kappa 0,7331 | resultados.tex:114-118 (p. 49); conclusiones.tex:64 | Resuelta en lo esencial | Ya aclara que compara heurística contra modelo de lenguaje y que SPMP exige κ >= 0,7 con segundo anotador humano (pendiente). |
| J14 "11 de 12" | cuerpo | No se encontró | Sin coincidencias de `11 de 12` ni `once de doce`. El texto usa "200 pares de 12 documentos" (resultados.tex:97). |
| J15 párrafos largos | ver lista abajo | Listado | Decidir cuáles partir. |
| J16 cap. IV cifras sueltas | analisisProblema.tex (:267) | Pendiente | Unas 150 cifras sueltas; falta tabla de referencia del corpus. |
| J17 embudo del corpus | analisisProblema.tex:267; desarrolloSolucion.tex:107, 180; conclusiones.tex:47 | Pendiente | Las cifras están, falta figura o tabla de embudo (3.610 renglones, 17 colegios, 3.608 analizables, 1.451 formas, 1.109 libros/licencias/uniformes, 4.719 ítems; 99 conceptos; 2.588 de 4.719 y 98 conceptos). |
| J18 ejemplo trabajado | desarrolloSolucion.tex:203 (p. 35); disenoSolucion.tex:185-191 | Pendiente | Solo hay un renglón ("pompones de colores x 20"). Falta una lista real recorrida por todas las etapas. |

### J15: los 10 párrafos más largos (palabras)

1. resultados.tex:180, 308
2. desarrolloSolucion.tex:164, 265
3. optimizacion.tex:195, 240
4. optimizacion.tex:21, 222
5. desarrolloSolucion.tex:78, 221
6. nl2c.tex:7, 220
7. desarrolloSolucion.tex:230, 218
8. optimizacion.tex:168, 210
9. descripcionGeneral.tex:96, 208
10. desarrolloSolucion.tex:314, 206

### Parámetros reales de NSGA-II (`servicios/inteligencia/tukit_inteligencia/optimizador.py`)

- `:854-860`: `NSGA2(pop_size=_poblacion(n), sampling=_poblacion_inicial(...), crossover=SBX(prob=0.9, eta=15, repair=RoundingRepair()), mutation=PM(prob=1.0, eta=20, repair=RoundingRepair()), eliminate_duplicates=True)`.
- `:117-122`: `_POBLACION_POR_LINEA=6`, `_POBLACION_MIN=20`, `_POBLACION_MAX=100`, `_GENERACIONES_POR_DECADA=10`, `_GENERACIONES_MIN=15`, `_GENERACIONES_MAX=60`.
- `:125-132`: N = 6·n, limitado a [20, 100] y redondeado a par.
- `:135-143`: G = 10·log10(espacio), limitado a [15, 60].
- `:864`: `("n_gen", _generaciones(espacio))`; parada solo por número de generaciones, semilla fija.

### Fórmula de personaje según el código

- `:272`: `s.personaje` es una fracción en [0,1]. En el texto es f4 = (1/n)ΣΣ x·κ_p.
- `:1005-1006`: pesos normalizados, w = peso/total.
- `:1007`: w_fidelidad = w["marca_exigida"] + w["calidad"].
- `:1009-1016`: rangos min-max de costo, fidelidad y personaje.
- Texto (`optimizacion.tex:108-110`): U = ŵ_precio·u1 + (ŵ_marca + ŵ_calidad)·u2 + ŵ_personaje·u4, sin u3.
- Desempate por perfil: Fan `max(frente, key=(s.personaje, -s.costo, s.fidelidad))` (`:947`); Premium `max(key=(fidelidad, -costo, disponibilidad))` (`:943`). El texto no las menciona.

## 4) Alineación con el equipo

Palabras aproximadas (`wc`/`awk`). Equipo = `/tmp/rey_zip.4smu/sections/`. Actual = `docs/memoria/sections/`. No se leyó `revision/diff-equipo-2026-11-06.md` más allá de su índice.

Hallazgos que cambian la lectura:
- En `resultados.tex` actual no existen las subsecciones "Verificación de la versión evaluada", auditoría de seguridad ni validación financiera (solo percepción, recuperación, optimización y asistente). Su equivalente está repartido en `calidad.tex`, `nl2c.tex`, `oe5.tex` y `descripcionGeneral.tex:96-106`.
- No se halló "340 %" ni "0,961" en equipo ni actual. "Diez tiendas" sí está en el equipo.
- El actual ya no usa algunas cifras de la lista del usuario: `calidad.tex:23` dice 2.542 pruebas Python (más 86 web y 67 de contrato); `calidad.tex:47` dice 85 hallazgos (16/58/11). No se verificó cuál es la vigente.

### Tabla de acciones

| Tema | Equipo (palabras) | Actual (palabras) | Acción |
|---|---|---|---|
| Modelo de negocio | diseñoSolucion:14 (185) | disenoSolucion.tex:7 (132) | traer redacción; canvas a 0,85 del ancho (actual 0,56) |
| Alternativas evaluadas | :48 (452) | :82 ATAM (655) | excluido |
| Arquitectura alto nivel | :99 (133) | :141 (501) | ya está |
| Vista lógica | :117 (1.191) | :29 y :70 (624) | traer redacción; componentes por servicio con `diagrama-componentes.jpg` |
| Vista de tiempo de ejecución | :234 (399) | :182 (310) | traer estructura; tres secuencias (carga l.252, revisión l.268, pago l.284) |
| Modelo de datos | :291 (862) | :204 (333) | traer redacción; cinco ER (l.314, 330, 348, 364, 379), los `er-*.jpg` existen en `img/arquitectura/` |
| Vista física | :391 (1.014) | :141 (501) | traer redacción; nodos y sistemas externos (l.408-411) con `diagrama-despliegue.jpg` |
| Registro y matrícula de hijos | desarrolloSolucion:57 (409) | :328 (816, parcial) | traer estructura |
| Carga o selección de lista | :95 (422) | :328 y :115 (parcial) | traer estructura |
| Procesamiento (percepción, normalización, resolución) | :133 (801+459+997) | :115, :144, :185, :196 | ya está |
| Optimización y NSGA-II frente a PD | :444 y :593 (1.240+862) | :275 y optimizacion.tex (444+2.740) | ya está |
| Kits, recomendación, personalización | :686 (674) | :275 y :328 (parcial) | traer redacción (Ahorrador, Premium, Fan, A tu Medida) |
| Asistente del kit | :750 (348) | :311 y nl2c.tex (213+1.645) | ya está |
| Pago | :785 (278) | :328 (parcial) | traer redacción; faltan capturas de checkout y pasarela |
| Seguimiento, retracto y casos | :812 (482) | :328 (parcial) | traer estructura; retracto y PQRS no están |
| Privacidad y supresión | :867 (348) | sin equivalente | traer redacción |
| Revisión humana | :907 (299) | :328 (parcial) | traer redacción |
| Catálogo | :939 (311) | sin equivalente | traer redacción (cifra "10 tiendas") |
| Logística y entrega | :971 (280) | :328 (parcial) | traer redacción |
| Métricas y observabilidad | :1001 (160) | sin equivalente | traer redacción |
| Percepción documental | resultados:13 (372) | :42 (355) | ya está |
| Recuperación y normalización | :60 (1.000) | :78 (1.028) | ya está |
| Optimización | :195 (308) | :166 (887) | ya está |
| Verificación de la versión evaluada | :220 (932) | calidad.tex:2 (1.183) | ya está (cifras en conflicto) |
| Auditoría de seguridad y privacidad | :287, :297, :310 (90+161+575) | calidad.tex (parcial) | traer redacción; los 14 defectos de los microservicios anteriores (l.295) no están |
| Validación con usuarios OE5 | :356 (369) | oe5.tex (1.398) | ya está |
| Validación financiera `tab:proyeccion` | :388 (674) | descripcionGeneral.tex:96-106 (~170) | traer redacción; faltan tabla de proyección, inversión y VPN |

Prioridades: (1) validación financiera en subsección nueva con cifras reconciliadas; (2) privacidad, catálogo y métricas; (3) reutilizar las capturas de `img/desarrollo/` (el actual usa solo 3 de 35: `10-cola-revision-listas`, `11a-revision-pdf-y-lectura`, `13a-logistica-pedidos`), sujeto al límite de 60 páginas.

### Figuras a copiar

- arquitectura: ya están `er-*` x5, `secuencia-carga-lista`, `secuencia-pago`, `secuencia-revision`. No están `diagrama-casos-uso.pdf`, `diagrama-componentes.jpg`, `diagrama-contexto.pdf`, `diagrama-despliegue.jpg`, `diagrama-entidad-relacion.jpg`; hay TikZ equivalentes (`c4-*.tex`, `despliegue.tex`). `c4-contenedores.tex` está en ambos.
- desarrollo: las 35 capturas existen en `img/desarrollo/`; el actual usa 3.
- graficas: `fig_opt_calidad.pdf`, `fig_opt_memoria.pdf`, `fig_opt_tiempo.pdf` ya están; uso solo en optimizacion.tex (no verificado).
- modelo: `contexto.jpg` ya está.

### Cifras en conflicto

| Cifra | Equipo | Actual |
|---|---|---|
| 1.647 pruebas, 72,43 % de 12.039 sentencias | resultados.tex:243 | calidad.tex:23: 2.542 pruebas Python; 54 % y 98 % por servicio |
| 78 hallazgos abiertos (14/56/8) | resultados.tex:251 | calidad.tex:47: 85 (16/58/11) |
| 3.911 pruebas y 94,32 % de cobertura | resultados.tex:244 | sin equivalente |
| ~770 kits de punto de equilibrio | resultados.tex:398, descripcionGeneral.tex:202 | descripcionGeneral.tex:102-104: 41 (piloto) y 512 (escalable) |
| Comisión \$27.000, costos \$7.500 | resultados.tex:392-396 | descripcionGeneral.tex:98-101: Ahorrador \$609.343, comisión \$91.401, contribución \$29.353 |
| "cerca de diez colegios" | resultados.tex:400 | 17 colegios (resultados.tex:177) |
| "10 tiendas" | desarrolloSolucion.tex:946 | sin equivalente |
| VPN ≈ \$235 millones | resultados.tex:429 | sin equivalente |
| 1.500 / 8.000 / 25.000 kits | resultados.tex:399, descripcionGeneral.tex:203-205 | sin equivalente |
| Hipervolumen 0,9981 y frente exacto 81,6 % | desarrolloSolucion.tex:671-672 | resultados.tex:31: 0,9969; 0,31 s |
| 11.340 ternas por etapa | desarrolloSolucion.tex:605 | no encontrado |
| AUC 0,880 | resultados.tex:112 | cifras_calibracion.tex:69: 0,921 |
| "340 %" y "0,961" | no encontrados | no encontrados |

## 5) Presupuesto de páginas (cuerpo <= 60; el PDF tiene 97)

Se midieron las páginas 1-60 del cuerpo (PDF 13 a 72). Solo las cuerpo 45 (23 líneas) y 46 (26 líneas) bajan de 30 líneas; contienen la Figura 11 y la Tabla 18 (espacio de flotantes, recuperable 0,5 a 0,8 página). No se pudo medir el relleno al final de cada capítulo. Palabras aproximadas (`rg`/`sed`, puede incluir texto de tablas; `detex` devolvió 0).

| Capítulo | Palabras | Fig. | Tablas | Actual (base) | Propuesto | Se agrega | Se quita | Páginas netas |
|---|---|---|---|---|---|---|---|---|
| I introduccion | ~960 | 0 | 0 | 2 | 2 | nada | nada | 0 |
| II descripcionGeneral | ~3.080 | 0 | 3 | 6 | 5,5 | nada indicado en el insumo (la validación financiera de la sección 4 no está presupuestada aquí) | tabla de trazabilidad por objetivo (:300-307, 0,3); aclaraciones entre paréntesis (:307, 0,3) | -0,5 |
| III contextoProyecto | ~1.980 | 1 | 2 | 5 | 4,5 | nada | el insumo no detalla de dónde | -0,5 |
| IV analisisProblema | ~3.100 | 1 | 3 | 6 | 6 | tabla de cifras del corpus (J16), embudo (J17) | compensado dentro del capítulo | 0 |
| V disenoSolucion | ~3.100 | 6 | 5 | 10 | 10 | diagrama de componentes (J12) | ADR (:218, :246), repetición erosión de fronteras (:135, :220) | 0 |
| VI desarrollo+optimizacion+nl2c | ~8.500 | 4 | 6 | 16 | 16 | fórmulas (+0,7), absorbidas; ejemplo trabajado (J18) | sin recorte propio; ADR en desarrolloSolucion.tex:43, pendientes :138, :416 | 0 |
| VII resultados+calidad+oe5 | ~5.270 | 3 | 5 | 11 | 12,5 | +1,5 (contenido de la sección 4) | auditorías duplicadas (resultados.tex:210, :238, 217-223) | +1,5 |
| VIII conclusiones | ~2.060 | 0 | 1 | 4 | 3,5 | nada | resumen que repite el cap. VII (:13-15, 0,3); cifras repetidas | -0,5 |
| Total | | | | 60 | 60 | ~3,9 | ~2,5 a 3,5 | 0 |

Las columnas "se agrega" y "se quita" por capítulo son una asignación mía a partir de las listas del insumo; el insumo solo da totales por concepto (+1,5 en VII, +0,7 en VI, +1 diagrama y embudo, +0,7 ejemplo) y los cambios netos de la última columna. Viabilidad: ajustada pero viable; el diagrama y el ejemplo deben ir donde ya hay flotantes.

### Lista de recortes (archivo:línea, estimación en páginas)

| Recorte | Dónde | Páginas |
|---|---|---|
| Cifras repetidas (405 pares τ, 391/405, 152 puntos de entrada, 100 usuarios, seis acudientes) | conclusiones.tex:13, :68; calidad.tex:41; resultados.tex; oe5.tex | 0,4 a 0,6 |
| Resumen de resultados en conclusiones | conclusiones.tex:13-15 | 0,3 |
| Párrafo de auditorías de kits (29,6 % a 85,6 %), aparece dos veces | resultados.tex:210, :238 | 0,2 |
| Tabla de auditorías que duplica el texto | resultados.tex:217-223 | 0,3 |
| Oraciones y tabla de ADR | disenoSolucion.tex:218, :246; desarrolloSolucion.tex:43 | 0,3 a 0,5 |
| Frases "pendiente" y `\pendienteEvidencia` | resultados.tex:73, :112, :119; desarrolloSolucion.tex:138, :416; calidad.tex:91-92; oe5.tex:98 | 0,3 |
| Tabla de trazabilidad por objetivo | descripcionGeneral.tex:300-307 | 0,3 |
| Repetición del argumento de erosión de fronteras | disenoSolucion.tex:135, :220 | 0,2 |
| Aclaraciones entre paréntesis para el lector | descripcionGeneral.tex:307; optimizacion.tex:222 | 0,3 |

Total realista: 2,5 a 3,5 páginas, sin contar los flotantes del capítulo VI ni las páginas 45-46. Contradicción a notar: la sección 4 pide traer varias subsecciones nuevas (financiera, privacidad, catálogo, métricas) y el presupuesto de páginas solo reserva 3,9 páginas de contenido nuevo; el insumo no las suma explícitamente.
