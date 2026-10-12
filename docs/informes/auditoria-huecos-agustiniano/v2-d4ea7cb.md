# Auditoría de huecos del catálogo: Colegio Agustiniano Ciudad Salitre (2026)

- **Tipo:** auditoría de datos, renglón por renglón, de las listas oficiales 2026 de Jardín a Once y de los kits canónicos Ahorrador y Premium que arma el sistema con ellas.
- **Fecha:** 2026-10-11.
- **Rama:** `feature/integracion-total`.
- **Commit:** `d4ea7cbd545db4991b040d5338825ebc548dee11` ("Guia de curaduria: conceptos, productos y atributos").
- **Árbol de trabajo:** sin cambios en archivos con seguimiento. Sin seguimiento: `.sf/` y `docs/informes/nuevo-reporte-huecos-agustiniano.md` (la versión anterior de este informe, que esta reemplaza).
- **Versión anterior:** esta auditoría reemplaza la hecha sobre `a565aeb`, 24 commits atrás. La rama local se avanzó a la punta de la rama (fast-forward, sin merge), se recrearon las bases aisladas y se rearmaron los kits con el código nuevo. La sección 8 compara las dos.
- **Base de datos consultada:** bases aisladas creadas para esta auditoría en el Postgres local (`tukit_identidad_auditoria`, `tukit_catalogo_auditoria`, `tukit_inteligencia_auditoria`), migradas al head de la rama y cargadas con `datos/` de la rama.

| Servicio | Base consultada | Revisión alembic (`current`) | Head de la rama (`heads`) | ¿Coincide? |
| --- | --- | --- | --- | --- |
| identidad | `tukit_identidad_auditoria` | `6e2f9a4c1d83` | `6e2f9a4c1d83` | sí |
| catalogo | `tukit_catalogo_auditoria` | `9f3c8d5b1a24` | `9f3c8d5b1a24` | sí |
| inteligencia | `tukit_inteligencia_auditoria` | `9e3a5f7b2c41` | `9e3a5f7b2c41` | sí |

> Las bases compartidas `tukit_*` no se usaron ni se modificaron. No tenían cargadas las listas de esta rama, y `tukit_comercio` está en `b619c58fc0c3`, una revisión que no es de esta rama (su head es `a58b45f8b14c`). No se restampó ni se migró ninguna base compartida. La auditoría no necesita Comercio: en las bases aisladas, Comercio y Operación apuntaban a nombres inexistentes para que nada pudiera escribir fuera. No se usó Gemini.

---

## 1. Alcance y método

1. **Datos.** Se cargaron el catálogo (`tukit_catalogo.cargador --datos datos/catalogo`) y la curaduría (`tukit_identidad.curaduria importar` y `tukit_catalogo.curaduria importar`). Quedaron 684 productos canónicos activos, todos con precio vigente, 146 conceptos activos y 13 listas oficiales del colegio (`bccf0294-f6b2-5203-84dd-e7fc643ae17f`), con **1092 renglones** (528 textos distintos una vez normalizados).
2. **Kits.** Se levantó la API del catálogo de la rama y se corrió una pasada de `python -m tukit_inteligencia.poller` sin claves de Gemini. El poller drena los eventos `lista_aprobada` (`poller.py:153`, `_procesar_canonico`), crea un trabajo de origen `canonico_lista` por grado y lo procesa por la **ruta rápida** (`trabajos.py:481`, `_procesar_verificado`). La ruta rápida lee `/v1/admin/listas/{version}/resueltos` (`routers/admin.py:418`, `resueltos_de_version`) y no llama a Gemini ni a `emparejar`. Resultado: 13 trabajos del colegio, todos `publicado`, y por cada grado un kit **Ahorrador (A)** y uno **Premium (P)**, fijados como canónicos.
3. **Revisión.** Cada renglón se comparó con el producto que cobra cada perfil. Cuando no cumplía o el sistema dijo HUECO_CATALOGO, se buscó un sustituto en los 684 productos activos por palabras clave, marca, medida, ISBN y URL de origen (`datos/catalogo/productos_procedencia.csv`). Los sustitutos citados existen en el catálogo con el SKU y el precio indicados.
4. **Frente a la auditoría anterior.** Los kits nuevos se cruzaron renglón por renglón con los de `a565aeb`. **575 renglones** cambiaron de estado, producto, unidades, subtotal o línea informativa, o de texto, cantidad, concepto o tipo en la curaduría, y se revisaron de nuevo desde cero. Los **517** restantes salen igual y conservan su categoría, con las notas revisadas contra el código nuevo. Hay una excepción: `6#27` y `10#32` se reclasificaron por un error de la auditoría anterior (sección 8).
5. **Clasificación.**
   - **A. Hueco real:** el catálogo no tiene un producto que cumpla. 🔴 si, aun así, el sistema cobra un producto que no es lo pedido (falso positivo).
   - **B. Falso hueco:** el sistema dice HUECO_CATALOGO, pero el catálogo sí tiene un producto que cumple.
   - **C. Mal elegido:** el sistema cobra un producto que no cumple lo pedido (color, tamaño, tipo, cantidad, empaque). C(A) o C(P) cuando falla un solo perfil.
   - **D. No es hueco:** no se compra en Tukit por diseño, o no hay nada que comprar. Entran aquí los uniformes, las licencias, lo que se trae de casa, lo que Tukit decidió no vender (tipo `otro`, ADR 0027) y los textos con título que el catálogo no tiene. 🔴 si el sistema lo cobra.
   - **OK. Cumple:** los dos perfiles cobran un producto que cumple, o la línea llega como debe (informativa, en $0 porque otra línea ya la cubre). Con la bandera **K** se marcan los renglones donde el único producto que cumple es de personaje y el sistema lo cobra como último recurso. Es la regla de diseño (`routers/admin.py:339`), así que cuentan como OK.

**Notación.** "Grado y Renglón" es `grado#orden` del renglón en la lista oficial: `J` es Jardín, `T` Transición y `1`–`11` Primero a Once. Así, `7#45` es el renglón 45 de Séptimo. En las tablas, **A** es el Ahorrador y **P** el Premium. Los precios son los de la base consultada; "× n" indica las unidades que compra el kit. Los renglones iguales (mismo texto normalizado, mismos productos y unidades) se agrupan en una sola fila.

## 2. Resumen cuantitativo

### 2.1 Lo que resolvió el sistema

| Estado de la resolución | Ahorrador | Premium |
| --- | ---: | ---: |
| RESUELTO_AUTO | 707 | 707 |
| HUECO_CATALOGO | 385 | 385 |
| SIN_MATCH | 0 | 0 |
| &nbsp;&nbsp;· de ellas, líneas informativas (no se cobran) | 3 | 3 |
| **Total de renglones** | **1092** | **1092** |
| Suma de subtotales del kit (13 grados) | $9.857.452 | $17.602.526 |

Los dos perfiles comparten la resolución: los mismos renglones salen resueltos o como hueco en ambos. Solo 3 líneas salen informativas: `7#9`, `7#27` y `7#69`. Son los únicos renglones a los que la curaduría les puso tipo en el propio renglón (3.1).

### 2.2 Clasificación de la auditoría

| Cat. | Significado | Renglones | % | Textos distintos | Cobrado A | Cobrado P |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| **A🔴** | Hueco real, con falso positivo cobrado | 67 | 6,1 % | 38 | $991.120 | $2.547.890 |
| **A** | Hueco real (sin producto, no se cobra) | 148 | 13,6 % | 76 | $0 | $0 |
| **B** | Falso hueco (el producto sí existe) | 57 | 5,2 % | 33 | $0 | $0 |
| **C** | Mal elegido en los dos perfiles | 97 | 8,9 % | 69 | $2.777.650 | $4.650.760 |
| **C(A)** | Mal elegido solo en el Ahorrador | 23 | 2,1 % | 13 | $352.450 | $678.463 |
| **C(P)** | Mal elegido solo en el Premium | 31 | 2,8 % | 13 | $316.600 | $1.037.500 |
| **D🔴** | No es hueco, pero se cobra | 24 | 2,2 % | 12 | $633.650 | $1.022.650 |
| **D** | No es hueco | 180 | 16,5 % | 94 | $0 | $0 |
| **OK** | Cumple en los dos perfiles | 465 | 42,6 % | 185 | $4.785.982 | $7.665.263 |
|  | **Total** | **1092** | 100 % |  | $9.857.452 | $17.602.526 |

En familias: **A** 215 · **B** 57 · **C** 151 · **D** 204 · cumplen 465 (de ellos, 33 con la bandera K, 3.3). Sin contar los D, que no se compran en Tukit, de 888 renglones comprables **465 (52,4 %) salen bien en los dos perfiles**.

### 2.3 Los huecos que reporta el sistema frente a los reales

| De los HUECO_CATALOGO del sistema | Renglones |
| --- | ---: |
| **A.** Huecos reales (un `util` que el catálogo no tiene) | 148 |
| **B.** Falsos huecos (el producto sí existe) | 57 |
| **D.** No son huecos | 180 |
| &nbsp;&nbsp;· concepto de tipo `texto` | 66 |
| &nbsp;&nbsp;· concepto de tipo `uniforme` | 52 |
| &nbsp;&nbsp;· concepto de tipo `otro` | 30 |
| &nbsp;&nbsp;· concepto de tipo `licencia_digital` | 16 |
| &nbsp;&nbsp;· concepto de tipo `no_comprar` | 16 |
| **Total** | **385** |

Solo **148 de 385** huecos que muestra el sistema (38,4 %) son algo que falta surtir. Otros 180 son renglones que por diseño no se venden y debían llegar como línea informativa o "por su cuenta" (3.1); el ADR 0027 de la rama separa precisamente ese grupo de los huecos reales. De los 57 falsos huecos, 49 son nuevos y los produce el filtro por atributos (3.2 a); los otros 8 ya lo eran: renglones curados en un concepto sin productos.

| De los RESUELTO_AUTO del sistema | Renglones |
| --- | ---: |
| Cumplen en los dos perfiles (incluye las líneas informativas y las de $0) | 465 |
| **C.** Mal elegidos (C, C(A), C(P)) | 151 |
| **A🔴.** Se cobra algo y no existe producto que cumpla | 67 |
| **D🔴.** Se cobra algo que no había que comprar en Tukit | 24 |
| **Total** | **707** |

### 2.4 Dinero en juego

| Concepto | Ahorrador | Premium |
| --- | ---: | ---: |
| Suma de subtotales de los 13 kits | $9.857.452 (100,0 %) | $17.602.526 (100,0 %) |
| Cobrado en renglones A🔴 (no existe producto que cumpla) | $991.120 (10,1 %) | $2.547.890 (14,5 %) |
| Cobrado en renglones D🔴 (no había que comprarlo en Tukit) | $633.650 (6,4 %) | $1.022.650 (5,8 %) |
| Cobrado por un producto mal elegido (C y el C del perfil) | $3.130.100 (31,8 %) | $5.688.260 (32,3 %) |
| Cobrado por productos que cumplen | $5.102.582 (51,8 %) | $8.343.726 (47,4 %) |

"Mal elegido" no quiere decir que todo ese dinero sobre: muchas veces el producto correcto cuesta parecido. Indica cuánto del kit corresponde a renglones donde el acudiente recibiría algo distinto de lo que pide el colegio. En el Ahorrador, "productos que cumplen" incluye los renglones C(P), donde A sí cumple; en el Premium, los C(A). El exceso por empaque y cantidad se detalla en el Anexo 1.

### 2.5 Por grado

| Grado | Renglones | RESUELTO | HUECO | A🔴 | A | B | C | D🔴 | D | Cumplen | Kit A | Kit P |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Jardín (`J`) | 94 | 68 | 26 | 9 | 7 | 10 | 30 | 2 | 9 | 27 | $887.020 | $1.599.490 |
| Transición (`T`) | 90 | 71 | 19 | 8 | 7 | 2 | 31 | 1 | 10 | 31 | $970.405 | $1.444.229 |
| Primero (`1`) | 72 | 53 | 19 | 6 | 7 | 5 | 14 | 1 | 7 | 32 | $593.169 | $1.070.974 |
| Segundo (`2`) | 86 | 60 | 26 | 7 | 10 | 5 | 13 | 2 | 11 | 38 | $599.950 | $1.075.925 |
| Tercero (`3`) | 85 | 56 | 29 | 6 | 8 | 5 | 7 | 2 | 16 | 41 | $509.729 | $1.126.291 |
| Cuarto (`4`) | 76 | 48 | 28 | 5 | 10 | 5 | 6 | 2 | 13 | 35 | $801.545 | $1.371.136 |
| Quinto (`5`) | 84 | 54 | 30 | 6 | 11 | 3 | 4 | 2 | 16 | 42 | $547.234 | $1.137.975 |
| Sexto (`6`) | 71 | 44 | 27 | 2 | 8 | 2 | 2 | 3 | 17 | 37 | $531.848 | $886.769 |
| Séptimo (`7`) | 95 | 60 | 35 | 3 | 18 | 1 | 10 | 0 | 16 | 47 | $1.022.326 | $1.584.597 |
| Octavo (`8`) | 85 | 46 | 39 | 4 | 17 | 5 | 10 | 2 | 17 | 30 | $936.397 | $1.830.618 |
| Noveno (`9`) | 92 | 50 | 42 | 3 | 20 | 4 | 8 | 3 | 18 | 36 | $963.937 | $2.022.948 |
| Décimo (`10`) | 81 | 48 | 33 | 4 | 13 | 5 | 6 | 3 | 15 | 35 | $710.796 | $1.123.467 |
| Once (`11`) | 81 | 49 | 32 | 4 | 12 | 5 | 10 | 1 | 15 | 34 | $783.096 | $1.328.107 |
| **Total** | 1092 | 707 | 385 | 67 | 148 | 57 | 151 | 24 | 180 | 465 | $9.857.452 | $17.602.526 |

## 3. Hallazgos sistémicos: por qué pasa

Las causas están en el código y los datos de la rama. Las referencias son a `servicios/inteligencia/tukit_inteligencia/` (`trabajos.py`, `optimizador.py`, `parseo.py`, `poller.py`) y a `servicios/catalogo/tukit_catalogo/` (`routers/`, `repositorios/`, `consulta.py`, `enriquecer.py`).

### 3.1 La ruta rápida pierde el tipo del concepto: todo sale como `util`

- Solo 3 de los 1092 renglones declaran tipo en la curaduría: `7#9` (`otro`), `7#27` (`no_comprar`), `7#69` (`no_comprar`). En los demás, el tipo lo trae el concepto curado.
- La ruta rápida lee `tipo = item.get("tipo_item") or "util"` (`trabajos.py:513`). El endpoint que la alimenta devuelve el tipo del renglón sin caer al del concepto (`routers/admin.py:396`, `"tipo_item": f.tipo_item`). El tipo del concepto sí se calcula más abajo, como `tipo_concepto` (`:407`), pero `resueltos_de_version` lo quita de la respuesta antes de enviarla (`:449`). Dentro del catálogo, `_avisos_de` sí lo usa (`i.get("tipo_item") or i.get("tipo_concepto") or "util"`, `:1318`); la ruta rápida nunca lo recibe.
- El otro endpoint de listas sí aplica la regla, `f.tipo_item or f.concepto_tipo_item` (`routers/catalogo.py:557`), con el comentario "Nulo en el renglón significa 'lo que diga el concepto', NO `util`". La ruta lenta la aplica con `_tipo_del_concepto_manda` (`trabajos.py:416`, llamada en `:833`). Su docstring dice que deja la línea informativa "igual que en la ruta rápida", pero en esta rama la ruta rápida solo lo hace cuando el tipo viene en el renglón: por eso `7#9`, `7#27` y `7#69` sí salen informativas.
- Efecto: los 185 renglones de conceptos que no se buscan en el catálogo (`BUSCA_EN_CATALOGO = {"util", "libro_libre"}`, `parseo.py:22`; `TIPOS_NO_COMPRABLES`, `optimizador.py:83`) entran como `util` surtible. Sin productos, caen en HUECO_CATALOGO (`trabajos.py:525-530`) y el acudiente ve "No lo tenemos":

| Tipo del concepto | Renglones | Estado en la ruta rápida | Clase que debía ver el acudiente (`libs/ts/tukit-contrato/src/linea.ts`) |
| --- | ---: | --- | --- |
| `texto` | 70 | HUECO_CATALOGO | `por_su_cuenta`, "Lo consigues por tu cuenta" (SIN_MATCH en `trabajos.py:531-532`; `linea.ts:41`) |
| `uniforme` | 52 | HUECO_CATALOGO | `fuera_de_alcance`, "Uniformes: fuera de Tukit por ahora" (`linea.ts:33`) |
| `otro` | 31 | HUECO_CATALOGO | `por_su_cuenta`, "Lo consigues por tu cuenta" (`linea.ts:36`) |
| `licencia_digital` | 16 | HUECO_CATALOGO | `licencia_digital`, "Se paga por fuera" (`linea.ts:30`) |
| `no_comprar` | 16 | HUECO_CATALOGO | `no_comprar`, "No hay que comprarlo" (`linea.ts:31`) |

- **Corrección sugerida** (no aplicada): en `routers/admin.py:396`, `"tipo_item": f.tipo_item or reglas.get(f.concepto_codigo, _SIN_REGLAS)[2]`. Es la misma regla de `routers/catalogo.py:557`, con el valor que ya se calcula en `:407`. La otra opción es conservar `tipo_concepto` en la respuesta y leerlo en `trabajos.py:513` como hace `_avisos_de`.
- Con eso, los 185 renglones dejan de mostrarse como "No lo tenemos" sin tocar la curaduría. 180 son D y quedan bien clasificados. Los otros 5 (`8#7`, `8#8`, `9#72`, `11#6` y `11#7`) son falsos huecos: pasarían a "por su cuenta" aunque el producto existe, y se corrigen en la curaduría (3.7).

### 3.2 El filtro por atributos de cada renglón: qué arregla y cómo falla

Desde `2be642d` ("La ruta rapida elige por renglon entre todo el catalogo y deja hueco si nada cumple"), `_renglon_resuelto` (`routers/admin.py:299-367`) arma los candidatos de cada renglón así:

1. Toma los atributos que `extraer_atributos` lee del texto del renglón, menos `tipo=escolar` (`_NO_SE_EXIGEN`, `consulta.py:112`), y les pone encima los atributos que curó la lista.
2. Se queda con los productos del concepto que los declaran **con el mismo valor**. `_cumple` (`consulta.py:115-117`) compara texto en minúsculas y da por incumplido el atributo que el producto no declara.
3. Si queda alguno sin personaje, el de personaje sale de la lista (`:339`). El Ahorrador lleva el más barato; el Premium, el de mejor nivel y, dentro de él, el más barato.
4. Si no queda ninguno, el renglón va sin candidatos y la ruta rápida lo marca HUECO_CATALOGO (`trabajos.py:525-530`).

Entre las dos auditorías (sección 8), **96** renglones que cobraban un sustituto equivocado pasaron a ser huecos reales. Es obra del filtro y es lo correcto: el catálogo no tiene lo pedido y ya no se cobra otra cosa. Además, **217** renglones que se cobraban mal ahora cumplen: todos por cambios de código, salvo `4#53` y `7#27`, que corrigió la curaduría. Pero el filtro falla de cuatro maneras. La primera produce **49** falsos huecos nuevos: 46 renglones que antes cobraban un producto que no cumplía y 3 que cumplían (`3#12`, `3#52` y `4#32`).

#### (a) Falsos huecos: lo que sí cumple no pasa el filtro

El filtro deja fuera el producto que cumple cuando este no declara el atributo, cuando declara un valor cercano o cuando el extractor leyó mal el renglón. Los demás falsos huecos son de curaduría: el renglón está en un concepto sin productos, o en el equivocado. La tabla recoge los 57.

| Causa | Renglones (todos B) | Concepto | El filtro exige | Qué hay en el catálogo |
| --- | --- | --- | --- | --- |
| El producto no declara el atributo | `J#14`, `J#96` y `T#53` | `C006` | `punta=punta gruesa` / `tipo=borrable`, `punta=punta gruesa` / `tipo=permanente`, `color=negro`, `punta=punta gruesa` | 7 de 14 productos de `C006` no declaran `punta`. Ningún marcador declara `punta=punta gruesa`. Cumplen Faber Fiesta x12 (`TK-REV-632443`, $16.700), Faber-Castell borrable (`TK-REV-133274`, $5.390) y Faber-Castell permanente negro (`TK-REV-694313`, $4.400). |
| El producto no declara el atributo | `1#47`, `2#24`, `3#14`, `4#14` y `5#15` | `C011` | `tipo=fuelle`, `tamano=oficio` | 12 de 12 productos de `C011` no declaran `tamano`. La única carpeta de fuelle es Starglow Scribe (`TK-C011-CON`, $16.750), sin `tamano`. |
| El producto no declara el atributo | `1#54` y `2#32` | `C020` | `presentacion=frasco` | 10 de 12 productos de `C020` no declaran `presentacion`. Los dos que la declaran dicen `tarro`. Sirve vinilo escolar primarios x6 (`TK-REV-124368970`, $27.900). |
| El producto no declara el atributo | `2#11` y `3#12` | `dic-ingles` | `monolingue=false` | 3 de 3 productos de `dic-ingles` no declaran `monolingue`. Los tres son bilingües: Larousse School español-inglés (`TK-LIB-9789706073990`, $27.000), Oxford Pocket (`TK-LIB-9780194337311`, $136.000)… |
| El producto no declara el atributo | `1#1`, `2#1`, `3#1`, `4#1`, `5#1`, `6#1`, `7#1`, `8#1`, `9#1`, `10#1` y `11#1` | `C048` | `edicion=completa` | 7 de 8 productos de `C048` no declaran `edicion`. La única que lo declara es la infantil (`TK-C048-ECO`, `edicion=infantil`). Sirve Biblia Latinoamericana rústica (`TK-LIB-9788471512635`, $75.223). |
| El producto no declara el atributo | `4#55` | `C030` | `tamano=oficio` | 1 de 3 productos de `C030` no declara `tamano`. Acetato calibre 10 x5 hojas (`TK-C030-CON`, $17.300) no declara tamaño. |
| Valor cercano que la igualdad rechaza | `8#17`, `9#16`, `10#10`, `10#17`, `10#24`, `10#27`, `11#10` y `11#17` | `C001` | `rayado=cuadriculado`, `materias=5` / `materias=5` / `rayado=cuadriculado`, `materias=3` | Argollado Multimaterias (`TK-C001-CON-SPIDERMAN`, $25.900) declara `materias=multiple` (`enriquecer.py:969-970`) y no es igual a 3 ni a 5. Es de personaje: por la regla de último recurso, sería el elegido. |
| Valor cercano que la igualdad rechaza | `1#15` | `C001` | `hojas=80`, `rayado=ferrocarril`, `materias=1`, `encuadernacion=cosido` | El único ferrocarril cosido es de 100 h: Primavera Rengloncitos (`TK-REV-47518218715307`, $8.150). |
| Valor cercano que la igualdad rechaza | `4#32` | `C019` | `longitud=20 cm` | La escuadra de 45° es de 26 cm: Faber-Castell 45° (`TK-C019-ECO`, $6.400). Antes se aceptaba. |
| Valor cercano que la igualdad rechaza | `3#44`, `4#42`, `5#50` y `6#30` | `C003` | `tipo=dibujo`, `tamano=carta` | El block de bocetos es A4: Mont Marte A4 60 h (`TK-C003-PRE`, $49.900). |
| Valor cercano que la igualdad rechaza | `3#52` | `C049` | `material=plastico` | El único delantal sin personaje declara `material=tela`: delantal antifluido (`TK-REV-44922807910571`, $15.600). |
| El extractor leyó mal el renglón | `J#17`, `J#18`, `J#19`, `J#20` y `J#21` | `C027` | `color=surtido` | "Colores variados" se lee como `color=surtido`, pero cada renglón pide un color (entre paréntesis). Además C027 solo tiene óleos: la pintura escolar está en C020 y C051. |
| El extractor leyó mal el renglón | `J#22` | `C027` | `color=surtido` | "Fluorescentes" se lee como `color=surtido`. Sirve, en C051, témpera fluorescente x6 (`TK-REV-3006214`, $12.990). |
| El extractor leyó mal el renglón | `T#69`, `1#26` y `2#53` | `C001` | `hojas=15`, `rayado=blanco`, `materias=1` | `hojas=15` y `rayado=blanco` salen de la receta para armar la bitácora ("15 hojas de cartulina blanca…"). Sirve, en C003, Norma cuaderno de dibujo 80 h (`TK-REV-794726`, $15.850). |
| El producto está en otro concepto | `J#71` | `C129` | — | C129 no tiene productos; el bond está en C031: resma HP carta x500 (`TK-C031-ECO`, $16.500). |
| El producto está en otro concepto | `8#7`, `8#8`, `11#6` y `11#7` | `C134` | — | C134 no tiene productos; los cuatro libros están en C044 (3.7). |
| El producto está en otro concepto | `8#62` y `9#65` | `C121` | — | C121 no tiene productos; los jumpers vienen en C071, en kit protoboard + 40 jumpers (`TK-REV-102561087`, $26.000). |
| El producto está en otro concepto | `9#72` | `C142` | — | C142 no tiene productos; el módulo está en C071: módulo L298N (`TK-REV-102416735`, $17.800). |
| Error de curaduría | `J#5` | `C011` | `tamano=oficio` | Una maleta asignada a C011 Carpeta; correspondía a C086 Maleta o morral, que tiene productos. |

Los 57 falsos huecos por causa: el producto no declara el atributo: **24** · valor cercano que la igualdad rechaza: **15** · el extractor leyó mal el renglón: **9** · el producto está en otro concepto: **8** · error de curaduría: **1**.

Corrección sugerida: completar los atributos en `datos/catalogo` (las Biblias, las carpetas de fuelle, la punta de los marcadores) y, en `_cumple`, decidir qué hacer con el atributo ausente. Hoy cuenta como incumplido; tratarlo como "por confirmar" devolvería estos productos al Premium sin volver a cobrar lo que el filtro sí descarta bien.

Esta causa explica también una diferencia con la auditoría de Séptimo del repositorio (`docs/informes/auditoria-kits-agustiniano-septimo.md`). Esa auditoría, hecha en la rama `feature/atributos-catalogo` y sobre otra base, da la "Biblia completa en los dos kits" por arreglada. Con los `datos/` de esta rama, `7#1` es hueco: ninguna Biblia Latinoamericana declara `edicion`.

#### (b) El extractor lee mal el renglón y se cobra otra cosa

- `11#21` y `11#24` piden "cuaderno **tres** materias". El extractor solo cuenta materias escritas en cifras (`enriquecer.py:972-979`) y, si no las encuentra, pone 1 por omisión. Se exige `materias=1` y se cobra un cuaderno de una materia ($14.300 A / $14.300 P en los dos renglones).
- `7#39`, `8#40`, `9#48`, `10#52` y `11#48` piden un "kit de 12 pinceles sintéticos. delgados, planos redondos y abanico". "Delgados" se lee como `grosor=delgado`, la forma queda por revisar porque el renglón nombra varias, y el más barato que cumple es **un solo** pincel de agua Pentel Aquash ($29.800 por renglón). Sustituto: Mont Marte x15 mixto (`TK-C021-CON`, $26.900).
- Las lecturas equivocadas que dejan hueco están en la tabla de (a): `J#17`–`J#22` y `T#69`, `1#26`, `2#53`.

#### (c) Lo que el colegio pide no se exige: el texto no se extrae o el concepto no lo distingue

Si el atributo que hace la diferencia no se extrae, o el concepto no lo tiene entre sus discriminantes, el filtro deja pasar todo el concepto y gana el más barato.

| Renglones | Cat. | Concepto (atributos que filtra) | Lo que pide y no se exige | Lo que se cobra (primer renglón) |
| --- | --- | --- | --- | --- |
| `T#64`, `2#41`, `5#33`, `3#26` y `4#24` | `C(A)` | `C007` (deposito, orificios) | "portabasura" (debía leerse como `deposito`) | A: Sacapuntas Y Borrador Redondo TW EVANS<br>P: Sacapuntas Faber Castell Con Deposito Set X 3 Unidades |
| `J#62` | `C(A)` | `C013` (punta) | "puntaroma", junto (debía leerse como `punta=punta roma`) | A: Tijeras Multiusos 6,5 pulgadas Eterna<br>P: Tijera punta roma NESSAN |
| `2#10` | `A🔴` | `C003` (tipo, tamano) | "a rayas" (`tipo`) | A: Block Cuadriculado Tamaño Carta JEAN BOOK<br>P: Block Cuadriculado Tamaño Carta JEAN BOOK |
| `3#16` | `A🔴` | `C003` (tipo, tamano) | "hojas blancas" (`tipo`) | A: Block Cuadriculado Tamaño Carta JEAN BOOK<br>P: Block Cuadriculado Tamaño Carta JEAN BOOK |
| `J#38` y `T#34` | `A🔴` | `C010` (color, tamano, acabado) | "fluorescente" | A: Cartulina escolar de 1/8 135 g x 10 unidades (surtido)<br>P: Cartulina escolar de 1/8 135 g x 10 unidades (surtido) |
| `T#40` | `A🔴` | `C021` (grosor, forma) | "# 10" (la talla no es atributo) | A: Pincel Plano Eterna #5<br>P: Pincel Plano Eterna #5 |
| `J#59` | `C` | `C002` (dureza, forma, color) | "gruesos" | A: Lápiz Negro HB Eterna<br>P: Lapiz primavera negro x 12 PRIMAVERA |
| `J#61` | `C` | `C004` (unidades, forma) | "triangulares gruesos" | A: Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta<br>P: Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta |
| `J#11` y `T#12` | `C` | `C022` (unidades, presentacion) | "gigante" | A: Plastilina Larga Caja X12 Colores PELIKAN<br>P: Plastilina en barra Norma x 12 uds. |
| `T#27` y `J#30` | `C` | `C029` (color, tamano) | "escarchado" | A: Foamy en octavo x 10 unidades, 25 cm x 35 cm<br>P: Foamy en octavo x 10 unidades, 25 cm x 35 cm |
| `T#7` | `C` | `C086` (tipo) | "de rodachines" (`tipo`) | A: Maleta Morral Bolso Pequeño Infantil De Animales Para Niños Mariquita<br>P: Maleta Morral Bolso Pequeño Infantil De Animales Para Niños Mariquita |
| `8#25` | `C(A)` | `C025` (tamano) | la marca Walter | A: Tabla periódica tamaño carta<br>P: Tabla Periodica Walter Grande (26x20cm) |
| `T#17`, `T#18`, `T#19`, `T#20`, `T#21`, `J#80`, `J#81`, `J#82`, `T#79`, `T#80`, `T#81`, `1#33`, `1#34`, `1#35`, `2#61`, `2#62` y `2#63` | `C` | `C027` (tipo, color) | pintura escolar o académica: `tipo=escolar` se lee y no se exige (`consulta.py:112`), y en C027 solo hay óleos | A: Óleo franco amarillo ocre de 50 ml<br>P: Óleo franco amarillo ocre de 50 ml |
| `T#67`, `1#67`, `2#44`, `3#31`, `4#29` y `5#38` | `A🔴` | `C016` (sin discriminantes) | "125 gr" | A: Pegante en barra de 15 g, surtido<br>P: Pegante en barra de 40 g PegaStic |
| `J#53`, `T#35` y `3#37` | `C` | `C113` (sin discriminantes) | "plegado 15×15" / "20×20" | A: Block Iris Carta Colores Surtidos X 12H FINLANDEK<br>P: Block Iris Carta Colores Surtidos X 12H FINLANDEK |
| `1#11`, `1#57`, `2#36`, `3#20`, `4#19` y `5#27` | `A🔴` | `C106` (sin discriminantes) | "grueso", "oficio" | A: Paquete Bolsillo Acetato x100 Unds Delgado Carta<br>P: Acetato Bolsillo Delgado * 100 Unidades Tamaño Carta |

Tres de estos conceptos (`C016`, `C106` y `C113`) no tienen ningún atributo discriminante. En ellos, cualquier renglón recibe el producto más barato del concepto.

#### (d) Sin el tamaño del paquete como atributo, gana la unidad suelta

- Cuando el renglón pide "caja de marcadores", "marcadores x10" o "x12", el Ahorrador cobra un Sharpie suelto ($4.400): `J#13`, `T#14`, `J#79`, `T#76`, `1#32` y `2#60` (C) y `3#62`, `7#87`, `8#77`, `9#81`, `10#70` y `11#67` (C(A)). En C006, `unidades` no es discriminante (punta, tipo, color), así que el filtro no distingue una caja de un marcador.
- `4#48` pide "pinceles planos y redondos" y recibe un solo pincel en cada perfil.
- Es la otra cara del empaque (3.4): el catálogo no sabe cuántas unidades trae cada producto, ni para elegir ni para calcular cuántos comprar.

### 3.3 Personaje como último recurso, y personajes sin la marca

- `_renglon_resuelto` usa un producto de personaje solo si ninguno sin personaje cumple (`routers/admin.py:339`). La auditoría de Séptimo lo llama "el último recurso acordado". Aquí pasa en **33 renglones** (bandera K), casi todos cuadernos:

| Producto | Personaje | Precio | Renglones en A | Renglones en P | Grado y Renglón |
| --- | --- | ---: | ---: | ---: | --- |
| Cuaderno Stitch 100 Hojas (`TK-C001-CON-STITCH`) | `stitch` | $18.299 | 21 | 21 | `5#46`, `6#24`, `6#26`, `7#14`, `7#23`, `7#25`, `7#28`, `8#21`, `8#24`, `8#29`, `9#21`, `9#25`, `9#28`, `10#31`, `10#33`, `10#34`, `10#35`, `11#28`, `11#29`, `11#30` y `11#31` |
| Cuaderno Cosido 50 Hojas Primavera Cuadros Disney Clasicos - Se envia un Motivo Aleatorio (`TK-REV-47580578087083`) | `disney` | $6.500 | 11 | 11 | `1#19`, `2#45`, `3#43`, `4#41`, `5#49`, `6#29`, `7#29`, `8#30`, `9#29`, `10#36` y `11#32` |
| Cuaderno Frozen Mediano Rayado 100 hojas Cosido FROZEN (`TK-C001-ECO-FROZEN`) | `frozen` | $15.900 | 1 | 0 | `J#2` |
| Cuaderno Bluey Mediano Rayado 100 hojas Cosido NORMA (`TK-C001-CON-BLUEY`) | `bluey` | $17.200 | 0 | 1 | `J#2` |

- Son OK porque es la regla, pero son una decisión de producto que conviene mirar. Un acudiente que pide un "cuaderno argollado cuadriculado de 100 hojas" recibe uno de Stitch en los dos perfiles, porque sin personaje solo hay de 80 hojas, como Primavera argollado cuadriculado 80 h (`TK-REV-45616431038635`, $13.750). También cobran personaje 4 renglones que no había que comprar (`2#77`, `3#70`, `4#65` y `5#69`, D🔴).
- La regla solo reconoce como de personaje los productos que tienen el campo `personaje` lleno. Estos no lo tienen, así que compiten como cualquier otro y se cobran sin que nadie los haya pedido:

| Producto | Concepto · nivel | Renglones cobrados en A | en P |
| --- | --- | ---: | ---: |
| Cartuchera Tigger Plegable (`TK-REV-124388164`) | `C009` · economico | 11 | 0 |
| Paquete Vaso Plastico X12 Unds Among Us (`TK-REV-45126704693419`) | `C057` · economico | 6 | 0 |
| Carpeta Moana Motunui (`TK-C011-ECO`) | `C011` · economico | 1 | 0 |
| Carpeta Plastica Princesas SCRIBE (`TK-C011-PRE`) | `C011` · premium | 0 | 1 |
| Cuaderno Cosido Toy Story Playtime Optimize (`TK-REV-124354701`) | `C001` · confiable | 0 | 0 |
| Cuaderno Cosido Toy Story Playtime (`TK-REV-124354708`) | `C001` · confiable | 0 | 0 |
| Cuaderno Cosido 100 Hojas Primavera Marvel Comics Cuadros - Se envia un motivo aleatorio (`TK-REV-47580579758251`) | `C001` · confiable | 0 | 0 |
| Rompecabezas 100 Piezas Mickey RONDA (`TK-REV-3644613`) | `C056` · confiable | 0 | 0 |

### 3.4 Empaque y cantidad: el catálogo no sabe cuántas unidades trae un paquete

- Los 684 productos activos tienen `unidades_por_empaque = 1` (todos). Unos 245 nombres anuncian un paquete ("x 12", "X10 Unds"…), y 68 de ellos están en los kits del colegio.
- El optimizador compra `ceil(cantidad / unidades_por_empaque)` empaques (`unidades_a_comprar`, `optimizador.py:262-271`). Con empaque 1, si el colegio pide 4 octavos de cartulina negra (`6#40`), el kit compra 4 paquetes de 10 ($34.000). Lo mismo pasa con 10 hojas de durex: el kit compra 10 paquetes de 20 en `7#57`, `8#56` y `9#58` ($135.000 por renglón). Y con 10 hojas de papel pergamino (`8#57`): $155.000 en A y $306.000 en P.
- A eso se suman cantidades mal curadas. En `4#65` (el cuaderno del año anterior, que además no se compra) la cantidad quedó en 50 y el kit compra 50 cuadernos Disney ($325.000 en A y P). En `1#65` ("colores delgados X12") quedó en 12: el Premium compra 12 cajas ($73.200), y en el Ahorrador la línea se junta con `1#20` y las 12 cajas pasan a esa línea ($73.200; 3.5).
- Hay un riesgo latente que hoy no se ve porque son huecos. La curaduría de Séptimo bajó a 1 la cantidad de los paquetes de jumpers, LEDs y resistencias (`7#75`–`7#77`, commit `c9b9ddb`). Pero 18 renglones de otros grados piden unidades sueltas ("30 jumpers", "10 LEDs") con cantidad 2–30: cuando el catálogo tenga esos productos en paquete, el kit comprará un paquete por unidad.
- 44 renglones tienen sobrecobro por empaque o cantidad (Anexo 1).

### 3.5 La herramienta pedida en varias materias se compra una vez, si es el mismo producto

- Desde `642a53d`, `juntar_herramientas` (`optimizador.py:820-869`) junta las líneas de un mismo hijo que eligieron el **mismo SKU** en un concepto `uno_por_estudiante`. Compra la cantidad mayor en la primera y deja las demás en $0 con "Ya va en la línea N: sirve para todas las materias." Aquí pasa en 32 líneas del Ahorrador y 31 del Premium:

| Concepto | Líneas en $0 en A | en P |
| --- | ---: | ---: |
| `C013` Tijeras | 10 | 10 |
| `C004` Colores | 11 | 6 |
| `C008` Regla | 6 | 6 |
| `C026` Calculadora | 5 | 5 |
| `C018` Compás | 0 | 4 |

- Junta por producto, no por necesidad. En 4 grados la lista pide "compás" en una materia y "compás de precisión" en otra. El Premium elige el de precisión para las dos y las junta; el Ahorrador elige el escolar para la primera y el de precisión para la segunda, y **compra dos compases**: `3#35` Compas escolar keyroad (surtido) $14.900 + `3#47` Compas Precision Faber Castell $22.990 (igual en `6#19`, `7#19` y `10#18`). Cada línea, sola, cumple, así que no cambia la clasificación; son $59.600 de más en los Ahorradores.
- La cantidad que se junta es la mayor, y una cantidad mal curada se contagia: `1#65` (12, mal) se junta con `1#20` (1) y el Ahorrador cobra 12 cajas en la línea 20.
- No junta lo que no es `uno_por_estudiante`. C024 Bata de laboratorio no lo es, así que en Octavo se cobran dos batas (`8#22` y `8#26`, $41.600 A / $100.000 P). El renglón 26 llega con el aviso "posible repetido de la línea 22" en el motivo, pero el aviso no cambia lo que se compra.

### 3.6 Curaduría: lo corregido solo en Séptimo, conceptos equivocados y renglones compuestos

Los commits `c9b9ddb` y `00875ff` corrigieron en `datos/curaduria/listas_revisadas.csv` renglones de Séptimo (y `4#53`, una caja de colores que estaba en C007 Tajalápiz), a partir de la auditoría de Séptimo. Los mismos textos en otros grados siguen sin corregir:

| Séptimo | Corrección | Cómo llega en Séptimo | Mismo caso en otros grados (D🔴) | Se cobra en ellos (A / P) |
| --- | --- | --- | --- | ---: |
| `7#69` | Cuaderno del año anterior: `no_comprar` | No hay que comprarlo. Ya se tiene en casa. | `2#77`, `3#70`, `4#65`, `5#69`, `6#54`, `8#58` y `9#61` | $365.950 / $365.950 |
| `7#9` | Lectura libre guiada: `otro` | No lo vendemos en Tukit: consíguelo por tu cuenta. | `8#10`, `9#9`, `10#9` y `11#9` | $58.000 / $131.600 |
| `7#27` | "La misma bata" de laboratorio: `no_comprar` | No hay que comprarlo. Ya se tiene en casa. | `6#27` y `10#32` | $41.600 / $100.000 |

- El mismo diccionario inglés-español está curado en C034 en `2#15`, `4#10`, `5#11` y `6#12` (sale bien, Libsa $34.000) y en `dic-ingles` en `2#11` y `3#12`, donde queda como hueco por el atributo `monolingue` (3.2 a).
- 8 renglones tienen el concepto equivocado: la serie de lápices 2H-6B en C002 Lápiz (`3#45`, `4#43`), la maleta (`J#5`) y el portabasura (`1#64`) en C011 Carpeta, la cinta métrica en C015 Cinta adhesiva (`2#19`) y los textos Gateway en C044 Libro (`6#72`, `9#91`, `10#81`).
- 2 renglones compuestos tienen un solo concepto asignado, y la segunda cosa ni se cobra ni se avisa: `8#19` "Transportador, compás de precisión" (solo C023 Transportador) y `J#90` "Gorro en Lycra o Silicona y Gafas" (solo C111 Gorro de natación).

### 3.7 Productos en el concepto equivocado y libros sin título

- **C071 Kit de tecnología** reúne 14 productos de naturaleza distinta: protoboards de 270 a 2.200 puntos, el módulo L298N, un kit protoboard + 40 jumpers, un kit Arduino, un sensor MQ135 y kits de herramientas para celulares. Las listas piden esas cosas por su propio concepto (C102 Protoboard, C121 Cables jumper, C142 Componente electrónico especializado), donde no están esos productos. Resultado: falsos huecos (`8#62`, `9#65`, `9#72`) y protoboards de 400 puntos resueltas con una de 840 (`6#47`, `7#73`, `8#60`), aunque la de 400 puntos AVC 400 puntos (`TK-REV-101119299`, $8.900) está en C071.
- El ADR 0027 (`docs/arquitectura/adr/0027-lo-que-tukit-no-vende-se-clasifica.md`) pone el puente H como ejemplo de lo que Tukit decide no vender, y por eso C142 es de tipo `otro`. Pero el módulo L298N `TK-REV-102416735` está aprobado y a la venta en C071. Hay que decidir cuál de las dos curadurías manda.
- **Los libros con título viven en C044 Libro, pero las listas los piden por C134 Libro o texto con título**, que no tiene productos. Por eso `8#7`, `8#8`, `11#6` y `11#7` salen como hueco aunque el libro esté en el catálogo. Al revés, lo que cae en C044 sin título (el "libro de recortes", la lectura libre, los textos Gateway, el libro para colorear) cobra el más barato del concepto: "Nacho. Libro inicial de lectura" (`TK-C044-ECO`, $14.500) en A y "Don Quijote De La Mancha Parte 1 (Novela gráfica) - Enlace Editorial, Tapa Blanda (72 pags)" (`TK-REV-9789585594678`, $32.900) en P. Son 10 renglones.
- **14 libros de C044 perdieron el título en `nombre`.** Solo queda la editorial y el formato; el título sobrevive en la URL de origen. Una búsqueda por título no los encuentra: `11#7` pide *Aquiles en TikTok*, que está en el catálogo como "Ariel (Grupo Planeta), Tapa Blanda, 2023".

| SKU | `nombre` en el catálogo | Título (según la URL de origen) | Precio | URL de origen |
| --- | --- | --- | ---: | --- |
| `TK-REV-9786287593480` | Enlace Editorial, rústica, 176 páginas | Leyendas y mitos de mi patria | $38.900 | <https://www.panamericana.com.co/leyendas-y-mitos-de-mi-patria-696920/p> |
| `TK-REV-9786287624429` | Austral, tapa dura, 2026, 176 páginas (el colegio pide Editorial Norma; no se halló edición Norma en las tiendas permitidas, se ofrece la edición Austral verificada) | Veinte poemas de amor y una canción desesperada | $45.000 | <https://www.panamericana.com.co/veinte-poemas-de-amor-y-una-cancion-desesperada-725645/p> |
| `TK-REV-9786287788466` | Enlace Editorial (Kit con cartilla), tapa blanda, 125 páginas | Maju, cambia esa cara larga (kit) | $39.500 | <https://www.librerianacional.com/maju-cambia-esa-cara-larga-kit/p> |
| `TK-REV-9788434436169` | Ariel (Grupo Planeta), Tapa Blanda, 2023 | Aquiles en TikTok | $95.544 | <https://www.buscalibre.com.co/libro-aquiles-en-tiktok/9788434436169/p/54505464> |
| `TK-REV-9789583061738` | Editorial Panamericana, Tapa Dura, 266 págs, 1a edición | La rebelión de las ratas | $42.000 | <https://www.librerianacional.com/la-rebelion-de-las-ratas-382360/p> |
| `TK-REV-9789584231161` | Planeta Lector (edición Colombia), tapa blanda, 2013 | Once relatos mitológicos y uno más de propina | $23.786 | <https://www.buscalibre.com.co/libro-once-relatos-mitologicos-y-uno-mas-de-propina/9789584231161/p/32380147> |
| `TK-REV-9789584281876` | Planeta Comic, tapa blanda, 79 páginas, adaptación gráfica de Óscar Adán (2020) | María (novela gráfica) | $28.369 | <https://www.buscalibre.com.co/libro-maria/9789584281876/p/53094971> |
| `TK-REV-9789585497634` | Enlace Editorial SAS, Tapa Blanda, 1 edición | Atchú y otros cuentos (kit) | $81.565 | <https://www.buscalibre.com.co/libro-atchu-y-otros-cuentos-kit/9789585497634/p/53343569> |
| `TK-REV-9789585594098` | Enlace Editorial, rústica, 167 páginas, incluye cartilla de actividades | Vuelven las leyendas | $40.500 | <https://www.panamericana.com.co/vuelven-las-leyendas-594850/p> |
| `TK-REV-9789585862753` | Enlace Editorial S.A.S., Tapa Blanda, 143 págs (kit importado, última unidad) | La tortuga, el muchacho y el escritor (kit) | $105.820 | <https://www.buscalibre.com.co/libro-la-tortuga-el-muchacho-y-el-escritor-kit/9789585862753/p/53343513> |
| `TK-REV-9789588886176` | Debolsillo, Rústica, 136 págs. | Crónica de una muerte anunciada | $42.000 | <https://www.panamericana.com.co/cronica-de-una-muerte-anunciada-3/p> |
| `TK-REV-9789589019368` | Atenea, 1a edición, tapa blanda, 94 páginas | Voces desde el desvelo | $34.291 | <https://www.buscalibre.com.co/libro-voces-desde-el-desvelo/9789589019368/p/53035372> |
| `TK-REV-9789589019573` | Atenea, tapa blanda, 284 páginas, 1a edición | Los hijos del viento | $34.686 | <https://www.buscalibre.com.co/libro-los-hijos-del-viento/9789589019573/p/53035353> |
| `TK-REV-9789589019719` | Editorial Atenea, Tapa Blanda, 159 págs, edición colombiana | La metamorfosis y otros cuentos | $34.900 | <https://www.buscalibre.com.co/libro-la-metamorfosis-y-otros-cuentos/9789589019719/p/53035332> |

## 4. A. Huecos reales

Lo que la lista pide, Tukit vende (concepto `util` o `libro_libre`) y el catálogo no tiene.

### 4.1 🔴 Con falso positivo cobrado (67 renglones)

El sistema cobra un producto que no es lo pedido. Son los más graves: el acudiente paga por algo que no le sirve. Muchos son de la familia (c) de 3.2: lo que hace la diferencia no se exige.

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| J#3 | cuaderno Cuadriculado cuadros de 1cm x 1 cm de 100 hojas, cosido Duralink | `C001` Cuaderno<br>**A y P:** Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) $7.150 | Pide cuadros de 1×1 cm (cuadrícula grande de preescolar); no existe en el catálogo y se cobra un cuadriculado normal (Norma X-Presarte Cuadros 100 h). |
| 2#10 | Block tamaño carta a rayas | `C003` Block<br>**A y P:** Block Cuadriculado Tamaño Carta JEAN BOOK (`TK-REV-1659569`) $4.990 | Pide block rayado carta; no hay block rayado en el catálogo. El extractor no lee 'a rayas' como `tipo` y se cobra el cuadriculado Jean Book ($4.990). |
| 3#16 | blocks de hojas blancas tamano carta · **cant. 2** | `C003` Block<br>**A y P:** Block Cuadriculado Tamaño Carta JEAN BOOK (`TK-REV-1659569`) $4.990 × 2 = $9.980 | Pide block de hojas blancas carta; no hay block blanco escolar en el catálogo. El extractor no lee 'blancas' como `tipo` y se cobran 2 cuadriculados Jean Book. |
| J#40 | pliegos de papel Cartulina blanca · **cant. 2** | `C010` Cartulina<br>**A:** Cartulina escolar de 1/8 135 g x 10 unidades blanca (`TK-REV-633655`) $4.600 × 2 = $9.200<br>**P:** Paquete Carton Cartulina Octavo x25 Unds (`TK-C010-PRE`) $18.600 × 2 = $37.200 | Pide pliegos de cartulina blanca; el catálogo solo tiene octavos y se cobra un paquete de octavos. |
| 1#39, 2#67 | cuartos de cartulina blanca · **cant. 2** | `C010` Cartulina<br>**A:** Cartulina escolar de 1/8 135 g x 10 unidades blanca (`TK-REV-633655`) $4.600 × 2 = $9.200<br>**P:** Paquete Carton Cartulina Octavo x25 Unds (`TK-C010-PRE`) $18.600 × 2 = $37.200 | Pide cartulina en cuartos; el catálogo solo tiene octavos y se cobra un paquete de octavos. |
| J#38 | paquetes de octavos de cartulina fluorescente colores surtidos · **cant. 3** | `C010` Cartulina<br>**A y P:** Cartulina escolar de 1/8 135 g x 10 unidades (surtido) (`TK-REV-633667`) $4.800 × 3 = $14.400 | Pide cartulina fluorescente; no existe en el catálogo y se cobra cartulina surtida normal (TK-REV-633667, $4.800 por paquete). |
| T#34 | paquetes de octavos de cartulina fluorescente colores surtidos · **cant. 2** | `C010` Cartulina<br>**A y P:** Cartulina escolar de 1/8 135 g x 10 unidades (surtido) (`TK-REV-633667`) $4.800 × 2 = $9.600 | Pide cartulina fluorescente; no existe en el catálogo y se cobra cartulina surtida normal (TK-REV-633667, $4.800 por paquete). |
| 1#64 | portabasura | `C011` Carpeta<br>**A:** Carpeta Moana Motunui (`TK-C011-ECO`) $12.900<br>**P:** Carpeta Plastica Princesas SCRIBE (`TK-C011-PRE`) $16.790 | Error de curaduría: 'portabasura' asignado a C011 Carpeta. No hay portabasuras en el catálogo y se cobra una carpeta. |
| 10#59, 11#56 | Tijeras 8,5 pulgadas | `C013` Tijeras<br>**A:** Tijeras Multiusos 6,5 pulgadas Eterna (`TK-C013-ECO`) $5.800<br>**P:** Tijera punta roma NESSAN (`TK-C013-PRE`) $10.490 | Pide tijeras de 8,5"; no hay de esa medida y se cobra la escolar (sustituto cercano). |
| T#77 | Pliegos de papel celofán de cualquier color. · **cant. 2** | `C014` Papel<br>**A y P:** Paquete Papel Kraft Adhesivo Grafitos x20 Unds A4 Resistente al Agua (`TK-REV-46311604420779`) $11.000 × 2 = $22.000 | Pide papel celofán; no existe en el catálogo y se cobra papel kraft adhesivo (C014). |
| 2#90 | papel lija | `C014` Papel<br>**A y P:** Paquete Papel Kraft Adhesivo Grafitos x20 Unds A4 Resistente al Agua (`TK-REV-46311604420779`) $11.000 | Pide lija; no existe en el catálogo y se cobra papel kraft adhesivo (C014). |
| 2#19 | cinta métrica de 1 metro | `C015` Cinta adhesiva<br>**A:** Cinta de enmascarar Startape de 18 mm x 40 metros (`TK-REV-634115`) $8.200<br>**P:** Cinta de enmascarar multiusos Pegafan beige (`TK-REV-142931`) $11.500 | Error de curaduría: 'cinta métrica' asignada a C015 Cinta adhesiva, y se cobra cinta de enmascarar. C145 Cinta métrica no tiene productos. |
| T#67, 1#67, 2#44, 3#31, 4#29, 5#38 | pegante en barra 125 gr | `C016` Pegante en barra<br>**A:** Pegante en barra de 15 g, surtido (`TK-REV-656600`) $4.900<br>**P:** Pegante en barra de 40 g PegaStic (`TK-C016-PRE`) $11.500 | Pide pegante en barra de 125 g; la barra más grande del catálogo es de 40 g. C016 no tiene atributos discriminantes, así que '125 gr' no se exige y se cobra la de 15 g (A) o 40 g (P); sustituto cercano: 3 barras de 40 g. |
| T#40 | pincel plano # 10 | `C021` Pincel<br>**A y P:** Pincel Plano Eterna #5 (`TK-REV-124275612`) $1.200 | Pide pincel plano #10; no hay #10 en el catálogo (solo Eterna #5 y #6) y se cobra un plano #5. El set de planos x4 Kangrui (TK-C021-ECO) no dice sus tallas. |
| J#42 | pinceles planos pelo de Camello · **cant. 2** | `C021` Pincel<br>**A y P:** Pincel Plano Eterna #5 (`TK-REV-124275612`) $1.200 × 2 = $2.400 | Pide pincel de pelo de camello; no existe en el catálogo y se cobra un plano de nylon Eterna #5. |
| J#43 | Plano pelo de Camello | `C021` Pincel<br>**A y P:** Pincel Plano Eterna #5 (`TK-REV-124275612`) $1.200 | Pide pincel de pelo de camello; no existe en el catálogo y se cobra un plano de nylon Eterna #5. |
| 3#41, 5#47, 8#22, 8#26, 9#22 | Bata de laboratorio de material antifluido | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Pide bata antifluido de laboratorio; no existe en el catálogo y se cobra una bata de tela. |
| 4#38 | Bata de laboratorio de material antifluido, debidamente marcada y uso | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Pide bata antifluido de laboratorio; no existe en el catálogo y se cobra una bata de tela. |
| 6#25 | Bata de laboratorio de material antifluido debidamente marcada y uso obligatorio para ingreso a laboratorios de biología y procesos fisicoquímicos | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Pide bata antifluido de laboratorio; no existe en el catálogo y se cobra una bata de tela. |
| 7#24 | Bata de laboratorio de material antifluido, debidamente marcada y uso obligatorio para ingreso a laboratorios de ciencias naturales, procesos fisicoquímicos. | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Pide bata antifluido de laboratorio; no existe en el catálogo y se cobra una bata de tela. |
| 10#29 | bata de laboratorio de material antifluido, debidamente marcada y uso obligatorio para ingreso a laboratorios de física y química | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Pide bata antifluido de laboratorio; no existe en el catálogo y se cobra una bata de tela. |
| 11#26 | Bata de laboratorio con material antifluido | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Pide bata antifluido de laboratorio; no existe en el catálogo y se cobra una bata de tela. |
| J#49 | paquete de figuras en foami | `C029` Foamy<br>**A y P:** Paquete Plasti Fomi X8 Unidades Surtidas - Fomi Moldeable (`TK-C029-CON`) $7.800 | Pide figuras de foamy; no existen en el catálogo y se cobra foamy moldeable. |
| J#45 | palos de pincho largos · **cant. 5** | `C033` Palitos<br>**A:** Palo De Balso Cuadrado 5 X 5 Mm X 90 Cm 10 Unidades (`TK-C033-ECO`) $11.400 × 5 = $57.000<br>**P:** Palos De Madera Para Paleta Color Natural X 500 Unidades (`TK-REV-105198377`) $23.900 × 5 = $119.500 | Pide palos de pincho; no existen en el catálogo. A cobra palos de balso de 90 cm (5 en J#45) y P palitos de paleta x500. |
| T#43 | palos de pincho largos · **cant. 2** | `C033` Palitos<br>**A:** Palo De Balso Cuadrado 5 X 5 Mm X 90 Cm 10 Unidades (`TK-C033-ECO`) $11.400 × 2 = $22.800<br>**P:** Palos De Madera Para Paleta Color Natural X 500 Unidades (`TK-REV-105198377`) $23.900 × 2 = $47.800 | Pide palos de pincho; no existen en el catálogo. A cobra palos de balso de 90 cm (5 en J#45) y P palitos de paleta x500. |
| J#47, T#45 | paquete de palos de paleta de colores | `C033` Palitos<br>**A y P:** Palos De Madera Para Paleta Color Natural X 500 Unidades (`TK-REV-105198377`) $23.900 | Pide palos de paleta de colores; no hay de colores en el catálogo y se cobran los naturales x500 ($23.900), que sirven solo como sustituto cercano. |
| J#67 | Kit de aseo personal: caja de pañuelos faciales | `C040` Toallas y pañitos<br>**A:** Paquete Pañitos Humedos Grandulones Panda X100 Unds (`TK-REV-45616427991211`) $8.250<br>**P:** Pequeñin Toallitas Húmedas Original (`TK-C040-PRE`) $14.850 | Pide pañuelos faciales; no hay en el catálogo y se cobran pañitos húmedos. |
| T#57 | caja de pañuelos faciales | `C040` Toallas y pañitos<br>**A:** Paquete Pañitos Humedos Grandulones Panda X100 Unds (`TK-REV-45616427991211`) $8.250<br>**P:** Pequeñin Toallitas Húmedas Original (`TK-C040-PRE`) $14.850 | Pide pañuelos faciales; no hay en el catálogo y se cobran pañitos húmedos. |
| T#55 | libro didáctico para colorear - Dibujos pequeños para niños etc. | `C044` Libro<br>**A:** Nacho. Libro inicial de lectura (`TK-C044-ECO`) $14.500<br>**P:** Don Quijote De La Mancha Parte 1 (Novela gráfica) - Enlace Editorial, Tapa Blanda (72 pags) (`TK-REV-9789585594678`) $32.900 | Pide libro para colorear; no hay en el catálogo y se cobra 'Nacho' (A) o 'Don Quijote' novela gráfica (P). |
| 1#25, 2#73 | Lienzo de 25x25cms | `C050` Lienzo<br>**A:** Lienzo con bastidor con grapa posterior 20 x 30 cm (`TK-C050-ECO`) $16.900<br>**P:** Lienzo con bastidor tipo exposición de 50 x 70 cm (`TK-C050-PRE`) $61.600 | Pide lienzo de 25×25; no hay esa medida. A (20×30) es sustituto cercano; P (50×70) es desproporcionado. |
| 3#60 | lienzos de 25x25cms · **cant. 2** | `C050` Lienzo<br>**A:** Lienzo con bastidor con grapa posterior 20 x 30 cm (`TK-C050-ECO`) $16.900 × 2 = $33.800<br>**P:** Lienzo con bastidor tipo exposición de 50 x 70 cm (`TK-C050-PRE`) $61.600 × 2 = $123.200 | Pide lienzo de 25×25; no hay esa medida. A (20×30) es sustituto cercano; P (50×70) es desproporcionado. |
| 4#45, 6#33 | 2 lienzos de 25x25 cms. · **cant. 2** | `C050` Lienzo<br>**A:** Lienzo con bastidor con grapa posterior 20 x 30 cm (`TK-C050-ECO`) $16.900 × 2 = $33.800<br>**P:** Lienzo con bastidor tipo exposición de 50 x 70 cm (`TK-C050-PRE`) $61.600 × 2 = $123.200 | Pide lienzo de 25×25; no hay esa medida. A (20×30) es sustituto cercano; P (50×70) es desproporcionado. |
| 5#53 | lienzos de 25x25 cms · **cant. 2** | `C050` Lienzo<br>**A:** Lienzo con bastidor con grapa posterior 20 x 30 cm (`TK-C050-ECO`) $16.900 × 2 = $33.800<br>**P:** Lienzo con bastidor tipo exposición de 50 x 70 cm (`TK-C050-PRE`) $61.600 × 2 = $123.200 | Pide lienzo de 25×25; no hay esa medida. A (20×30) es sustituto cercano; P (50×70) es desproporcionado. |
| 7#36, 9#36, 10#43, 11#39 | lienzo blanco de 30x40 cms aproximadamente | `C050` Lienzo<br>**A:** Lienzo con bastidor con grapa posterior 20 x 30 cm (`TK-C050-ECO`) $16.900<br>**P:** Lienzo con bastidor tipo exposición de 50 x 70 cm (`TK-C050-PRE`) $61.600 | Pide lienzo de 30×40; no hay esa medida y se cobra 20×30 o 50×70. |
| 8#34 | 1 lienzo blanco de 30x40 cms aproximadamente | `C050` Lienzo<br>**A:** Lienzo con bastidor con grapa posterior 20 x 30 cm (`TK-C050-ECO`) $16.900<br>**P:** Lienzo con bastidor tipo exposición de 50 x 70 cm (`TK-C050-PRE`) $61.600 | Pide lienzo de 30×40; no hay esa medida y se cobra 20×30 o 50×70. |
| 7#37, 9#37, 10#44, 11#40 | lienzo de pintura por números (libre elección) | `C050` Lienzo<br>**A:** Lienzo con bastidor con grapa posterior 20 x 30 cm (`TK-C050-ECO`) $16.900<br>**P:** Lienzo con bastidor tipo exposición de 50 x 70 cm (`TK-C050-PRE`) $61.600 | Pide lienzo de pintura por números; no hay en el catálogo y se cobra un lienzo en blanco. |
| 8#35 | 1 lienzo de pintura por números (libre elección) | `C050` Lienzo<br>**A:** Lienzo con bastidor con grapa posterior 20 x 30 cm (`TK-C050-ECO`) $16.900<br>**P:** Lienzo con bastidor tipo exposición de 50 x 70 cm (`TK-C050-PRE`) $61.600 | Pide lienzo de pintura por números; no hay en el catálogo y se cobra un lienzo en blanco. |
| 5#10 | juego didáctico de mesa acorde a su edad | `C054` Juego didáctico<br>**A:** Rompecabezas En Madera Animales 4 Piezas Grande (`TK-REV-45308083667115`) $13.600<br>**P:** Computador Didactico 6683 Niños Aprender Ordenador Educativo Ingles (`TK-REV-101941514`) $48.900 | Pide juego de mesa para Quinto; el catálogo no tiene juegos para esa edad y se cobra un rompecabezas de 4 piezas o un computador didáctico. |
| 3#56, 4#50, 5#55 | Plato y vaso de plástico | `C057` Vaso o plato<br>**A:** Paquete Vaso Plastico X12 Unds Among Us (`TK-REV-45126704693419`) $5.900<br>**P:** Vaso plástico de 700 ml con pitillo, multicolor (`TK-REV-712640`) $19.900 | Pide plato y vaso; no hay platos en el catálogo y solo se cobra el vaso (A paquete de 12 vasos desechables Among Us, P vaso de 700 ml con pitillo). |
| 1#11, 1#57, 2#36, 3#20, 4#19, 5#27 | Sobre de acetato grueso tamaño oficio | `C106` Sobre de acetato<br>**A:** Paquete Bolsillo Acetato x100 Unds Delgado Carta (`TK-REV-47124878786731`) $12.300<br>**P:** Acetato Bolsillo Delgado * 100 Unidades Tamaño Carta (`TK-REV-104236138`) $18.000 | Pide un sobre de acetato grueso oficio; solo hay paquetes de 100 bolsillos delgados y ninguno declara atributos, así que se cobra el más barato: carta ($12.300 en A, $18.000 en P), aunque existen los de oficio (TK-REV-44702946197675, $13.800). |

### 4.2 Sin producto (148 renglones)

El sistema dice HUECO_CATALOGO y es cierto. 96 son huecos nuevos del filtro por atributos (3.2): antes se cobraba un sustituto que no servía.

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| J#60 | lápices rojos gruesos · **cant. 2** | HUECO_CATALOGO (A y P) · `C002` Lápiz | Pide lápiz rojo; no hay lápiz rojo en el catálogo y el filtro (`color=rojo`) ya no cobra lápiz negro. |
| T#62, 1#61, 2#39, 3#24, 4#22, 5#31 | lápiz rojo delgado | HUECO_CATALOGO (A y P) · `C002` Lápiz | Pide lápiz rojo; no hay lápiz rojo en el catálogo y el filtro (`color=rojo`) ya no cobra lápiz negro. |
| 2#26, 4#17, 5#18 | block de hojas blancas tamaño oficio | HUECO_CATALOGO (A y P) · `C003` Block | Pide block de hojas blancas oficio; no hay block blanco escolar en el catálogo y el filtro (`tamano=oficio`) ya no cobra uno de otro tipo. |
| 1#48, 4#15, 5#16 | block rayado tamaño oficio | HUECO_CATALOGO (A y P) · `C003` Block | Pide block rayado oficio; no hay block rayado en el catálogo y el filtro (`tamano=oficio`) ya no cobra uno de otro tipo. |
| 10#21 | block de papel milimetrado tamaño carta | HUECO_CATALOGO (A y P) · `C003` Block | Pide block milimetrado; no existe en el catálogo y el filtro (`tipo=milimetrado`) ya no cobra uno de otro tipo. |
| 4#54 | Caja de plumones (acrílicos) doble punta de 12 o 18 unidades. | HUECO_CATALOGO (A y P) · `C006` Marcador | Pide marcadores acrílicos; no existen en el catálogo y el filtro (`tipo=acrilico`) ya no cobra marcadores escolares. |
| 6#34, 11#54 | estuche de marcadores acrílicos de 12 o 18 unidades doble punta (Marcados) | HUECO_CATALOGO (A y P) · `C006` Marcador | Pide marcadores acrílicos; no existen en el catálogo y el filtro (`tipo=acrilico`) ya no cobra marcadores escolares. |
| 7#41, 9#54, 10#56 | estuche de marcadores acrílicos | HUECO_CATALOGO (A y P) · `C006` Marcador | Pide marcadores acrílicos; no existen en el catálogo y el filtro (`tipo=acrilico`) ya no cobra marcadores escolares. |
| 7#55, 8#54, 9#50 | Micropunta negro | HUECO_CATALOGO (A y P) · `C006` Marcador | Pide micropunta; no existen en el catálogo y el filtro (`punta=micropunta`) ya no cobra marcadores escolares. |
| 10#57 | micropunta | HUECO_CATALOGO (A y P) · `C006` Marcador | Pide micropunta; no existen en el catálogo y el filtro (`punta=micropunta`) ya no cobra marcadores escolares. |
| 7#31, 9#33, 10#40, 11#36 | regla de acero inoxidable de 30 cm | HUECO_CATALOGO (A y P) · `C008` Regla | Pide regla de acero inoxidable; no existe en el catálogo y el filtro (`material=acero`) ya no cobra regla plástica. |
| 8#37 | 1 regla de acero inoxidable de 30 cm. | HUECO_CATALOGO (A y P) · `C008` Regla | Pide regla de acero inoxidable; no existe en el catálogo y el filtro (`material=acero`) ya no cobra regla plástica. |
| 5#66 | Block cartulina iris tamaño carta | HUECO_CATALOGO (A y P) · `C010` Cartulina | Pide block de cartulina iris tamaño carta; solo hay iris en octavo (TK-REV-705165 x20 $12.900, TK-REV-135131 $8.390). |
| 1#17, 2#47, 3#67 | Carpeta tipo legajador | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta con gancho legajador; no existe en el catálogo (solo se venden los ganchos sueltos, C082) y el filtro (`tipo=legajador`) ya no cobra la carpeta de personaje. |
| 6#15, 11#14 | carpeta tamaño oficio con gancho legajador | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta con gancho legajador; no existe en el catálogo (solo se venden los ganchos sueltos, C082) y el filtro (`tipo=legajador`) ya no cobra la carpeta de personaje. |
| J#7 | carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Colores: Amarillo | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta legajadora plástica translúcida oficio de un color; no existe en el catálogo y el filtro ya no cobra la carpeta Moana/Princesas. |
| J#8 | carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Colores: Azul | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta legajadora plástica translúcida oficio de un color; no existe en el catálogo y el filtro ya no cobra la carpeta Moana/Princesas. |
| J#9 | carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Colores: Rojo | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta legajadora plástica translúcida oficio de un color; no existe en el catálogo y el filtro ya no cobra la carpeta Moana/Princesas. |
| J#10 | carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Colores: Verde | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta legajadora plástica translúcida oficio de un color; no existe en el catálogo y el filtro ya no cobra la carpeta Moana/Princesas. |
| T#8 | carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Color: Amarillo | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta legajadora plástica translúcida oficio de un color; no existe en el catálogo y el filtro ya no cobra la carpeta Moana/Princesas. |
| T#9 | carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Color: Azul | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta legajadora plástica translúcida oficio de un color; no existe en el catálogo y el filtro ya no cobra la carpeta Moana/Princesas. |
| T#10 | carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Color: Rojo | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta legajadora plástica translúcida oficio de un color; no existe en el catálogo y el filtro ya no cobra la carpeta Moana/Princesas. |
| T#11 | carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Color: Verde | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide carpeta legajadora plástica translúcida oficio de un color; no existe en el catálogo y el filtro ya no cobra la carpeta Moana/Princesas. |
| 7#43, 8#42, 9#39, 10#45, 11#41 | Pinturas acrílicas tubo de 45 cc: cian | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide acrílico en tubo de 45 cc; C027 solo tiene óleos y el filtro (`tipo=acrilico`) ya no cobra uno. No hay acrílicos en tubo en el catálogo. |
| 7#44, 8#43, 9#40, 10#46, 11#42 | Pinturas acrílicas tubo de 45 cc: magenta | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide acrílico en tubo de 45 cc; C027 solo tiene óleos y el filtro (`tipo=acrilico`) ya no cobra uno. No hay acrílicos en tubo en el catálogo. |
| 7#45, 8#44, 9#41, 10#47, 11#43 | Pinturas acrílicas tubo de 45 cc: amarillo 900 | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide acrílico en tubo de 45 cc; C027 solo tiene óleos y el filtro (`tipo=acrilico`) ya no cobra uno. No hay acrílicos en tubo en el catálogo. |
| 7#46 | Pinturas acrílicas tubo de 45 cc: blanco | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide acrílico en tubo de 45 cc; C027 solo tiene óleos y el filtro (`tipo=acrilico`) ya no cobra uno. No hay acrílicos en tubo en el catálogo. |
| 7#47 | Pinturas acrílicas tubo de 45 cc: negro | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide acrílico en tubo de 45 cc; C027 solo tiene óleos y el filtro (`tipo=acrilico`) ya no cobra uno. No hay acrílicos en tubo en el catálogo. |
| 7#48, 8#46, 9#43, 10#49, 11#45 | Pinturas acrílicas tubo de 45 cc: azul primario | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide acrílico en tubo de 45 cc; C027 solo tiene óleos y el filtro (`tipo=acrilico`) ya no cobra uno. No hay acrílicos en tubo en el catálogo. |
| 7#49, 8#47, 9#44, 10#50, 11#46 | Pinturas acrílicas tubo de 45 cc: rojo primario | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide acrílico en tubo de 45 cc; C027 solo tiene óleos y el filtro (`tipo=acrilico`) ya no cobra uno. No hay acrílicos en tubo en el catálogo. |
| 8#45, 9#42, 10#48, 11#44 | Pinturas acrílicas tubo de 45 cc: blanco negro | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide acrílico en tubo de 45 cc, blanco y negro en un mismo renglón; no hay acrílicos en tubo. El color queda en `atributos_por_revisar` porque el renglón nombra dos. |
| 5#61 | Estuche de pinturas acrílicas | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide estuche de pinturas acrílicas; no hay estuche acrílico. Lo más cercano es el set de arte Langer con acrílicos x 20 piezas (TK-REV-513810, C070, $64.900). |
| 3#57, 4#51, 5#56, 7#52, 8#49, 9#53, 10#53, 11#51 | Toalla pequeña | HUECO_CATALOGO (A y P) · `C040` Toallas y pañitos | Pide toalla pequeña; no hay toallas en el catálogo (exige tipo=tela). Ya no se cobran pañitos húmedos. |
| J#41 | octavos de cartón paja blanco · **cant. 10** | HUECO_CATALOGO (A y P) · `C041` Cartón | Pide octavos de cartón paja blanco; solo hay crema o de colores (TK-C041-CON crema x10, $10.200). Con q=10 / q=3 octavos, basta 1 paquete. |
| T#39 | octavos de cartón paja blanco · **cant. 3** | HUECO_CATALOGO (A y P) · `C041` Cartón | Pide octavos de cartón paja blanco; solo hay crema o de colores (TK-C041-CON crema x10, $10.200). Con q=10 / q=3 octavos, basta 1 paquete. |
| 8#39 | Acuarelas en tubo | HUECO_CATALOGO (A y P) · `C065` Acuarela | Pide acuarelas en tubo; solo hay pastillas y el filtro (presentacion=tubo) ya no las cobra. |
| 1#44 | caimanes eléctricos cortos (15 cm) de longitud · **cant. 4** | HUECO_CATALOGO (A y P) · `C108` Cables caimanes | No hay cables caimanes en el catálogo. |
| 2#82, 5#73 | caimanes eléctricos · **cant. 4** | HUECO_CATALOGO (A y P) · `C108` Cables caimanes | No hay cables caimanes en el catálogo. |
| 3#77 | cables caimanes · **cant. 2** | HUECO_CATALOGO (A y P) · `C108` Cables caimanes | No hay cables caimanes en el catálogo. |
| 4#71 | 4 caimanes eléctricos · **cant. 4** | HUECO_CATALOGO (A y P) · `C108` Cables caimanes | No hay cables caimanes en el catálogo. |
| 7#33, 8#31, 9#30, 10#37, 11#33 | Sketchbook de papel durex 50 hojas tamaño carta | HUECO_CATALOGO (A y P) · `C112` Papel durex | Pide sketchbook de papel durex de 50 h carta; solo hay un paquete de 20 octavos y el filtro (tamano=carta) ya no lo cobra. Sustituto cercano: TK-REV-794726 cuaderno de dibujo 80 h. |
| 6#48 | Paquete de Jumpers x 10 unidades de 10cm de largo (macho - macho) | HUECO_CATALOGO (A y P) · `C121` Cables jumper | No hay jumpers sueltos de 10 cm ni hembra-macho/hembra-hembra; el único kit trae macho-macho. |
| 6#49 | Paquete de Jumpers x 10 unidades de 10cm de largo (hembra - macho) | HUECO_CATALOGO (A y P) · `C121` Cables jumper | No hay jumpers sueltos de 10 cm ni hembra-macho/hembra-hembra; el único kit trae macho-macho. |
| 7#74 | Paquete de Jumpers x 10 unidades de 10cm de largo | HUECO_CATALOGO (A y P) · `C121` Cables jumper | No hay jumpers sueltos de 10 cm ni hembra-macho/hembra-hembra; el único kit trae macho-macho. |
| 8#63 | 10 jumpers macho-hembra 20cm de largo · **cant. 10** | HUECO_CATALOGO (A y P) · `C121` Cables jumper | No hay jumpers sueltos de 10 cm ni hembra-macho/hembra-hembra; el único kit trae macho-macho. |
| 8#64 | 10 jumpers hembra-hembra 20cm de largo · **cant. 10** | HUECO_CATALOGO (A y P) · `C121` Cables jumper | No hay jumpers sueltos de 10 cm ni hembra-macho/hembra-hembra; el único kit trae macho-macho. |
| 9#66 | jumpers macho-hembra · **cant. 10** | HUECO_CATALOGO (A y P) · `C121` Cables jumper | No hay jumpers sueltos de 10 cm ni hembra-macho/hembra-hembra; el único kit trae macho-macho. |
| 7#75 | Paquete de Jumpers x 10 unidades de 10cm de largo (hembra - macho) | HUECO_CATALOGO (A y P) · `C121` Cables jumper | Pide jumpers x10 de 10 cm hembra-macho; el concepto no tiene productos; los únicos jumpers son los 40 de 20 cm del kit protoboard TK-REV-102561087 (C071). La ruta lo señala como posible repetido de 7#74. |
| 1#45 | leds · **cant. 4** | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 2#83 | leds · **cant. 3** | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 3#74 | leds · **cant. 2** | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 4#72 | 3 leds · **cant. 3** | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 5#74 | leds · **cant. 6** | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 6#50 | Paquete de leds x 10 unidades (diferentes colores) | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 8#65 | 10 LEDs de diferentes colores · **cant. 10** | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 9#67 | leds diferentes colores · **cant. 10** | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 7#76 | Paquete de leds x 10 unidades (diferentes colores) | HUECO_CATALOGO (A y P) · `C122` LED | No hay LEDs en el catálogo. |
| 8#61, 9#64 | Arduino Uno | HUECO_CATALOGO (A y P) · `C123` Arduino | No hay Arduino Uno suelto. Sustituto cercano y caro: TK-REV-104886579 kit de aprendizaje Arduino Uno R3 de 220 piezas ($386.980, C071). |
| 1#41, 5#70 | switch o interruptor tipo balancín | HUECO_CATALOGO (A y P) · `C124` Switch (interruptor) | No hay interruptores en el catálogo. |
| 2#78, 3#71 | switch o interruptor | HUECO_CATALOGO (A y P) · `C124` Switch (interruptor) | No hay interruptores en el catálogo. |
| 4#67 | 1 switch o interruptor | HUECO_CATALOGO (A y P) · `C124` Switch (interruptor) | No hay interruptores en el catálogo. |
| 6#52 | 2 switch de dos posiciones (2 pines) · **cant. 2** | HUECO_CATALOGO (A y P) · `C124` Switch (interruptor) | No hay interruptores en el catálogo. |
| 1#46 | resistencias de 330 ohm · **cant. 2** | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| 2#84 | resistências de 330 ohm o 1k Ohm · **cant. 3** | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| 3#75 | resistências de 330 ohm o 1k Ohm · **cant. 2** | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| 4#73 | 3 resistências de 330 ohm o 1k 0hm · **cant. 3** | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| 5#75 | resistências de 330 ohm · **cant. 3** | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| 6#51 | Paquete de resistencias x 20 unidades 1/4W de diferentes valores | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| 8#66 | paquete de 20 resistencias surtidas a 1/4 W | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| 9#68 | resistencias diferente amperaje · **cant. 20** | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| 7#77 | Paquete de resistencias x 20 unidades 1/4W de diferentes valores | HUECO_CATALOGO (A y P) · `C125` Resistencia | No hay resistencias en el catálogo. |
| J#56, T#54 | antifaz de dormir. Para ejercicios sensoriales | HUECO_CATALOGO (A y P) · `C135` Antifaz | No hay antifaces en el catálogo. |
| 5#76 | metro de cable estañado calibre 22 | HUECO_CATALOGO (A y P) · `C138` Cable eléctrico | No hay cable estañado calibre 22 en el catálogo. |
| 9#69 | servo Motor · **cant. 2** | HUECO_CATALOGO (A y P) · `C140` Servomotor | No hay servomotores en el catálogo. |
| 2#79 | motor generador proyecto escolar | HUECO_CATALOGO (A y P) · `C141` Motor DC | No hay motores DC ni motorreductores en el catálogo. |
| 4#68 | 1 motor generador proyecto escolar | HUECO_CATALOGO (A y P) · `C141` Motor DC | No hay motores DC ni motorreductores en el catálogo. |
| 6#53 | motoreductor | HUECO_CATALOGO (A y P) · `C141` Motor DC | No hay motores DC ni motorreductores en el catálogo. |
| 7#79 | motorreductor | HUECO_CATALOGO (A y P) · `C141` Motor DC | No hay motores DC ni motorreductores en el catálogo. |
| 9#70 | motor DC rectangular | HUECO_CATALOGO (A y P) · `C141` Motor DC | No hay motores DC ni motorreductores en el catálogo. |
| 9#46 | Ecolines de colores primarios: blanco | HUECO_CATALOGO (A y P) · `C143` Ecoline (acuarela líquida) | No hay ecolines en el catálogo. |
| 9#47 | Ecolines de colores primarios: negro | HUECO_CATALOGO (A y P) · `C143` Ecoline (acuarela líquida) | No hay ecolines en el catálogo. |
| 2#71 | Materiales para generar textura como: piedras de bisutería -pequeñas | HUECO_CATALOGO (A y P) · `C144` Piedras decorativas | No hay piedras decorativas (bisutería o jardinería) en el catálogo. |
| 2#91 | piedras de colores de jardinería | HUECO_CATALOGO (A y P) · `C144` Piedras decorativas | No hay piedras decorativas (bisutería o jardinería) en el catálogo. |
| 3#38 | cinta metrica | HUECO_CATALOGO (A y P) · `C145` Cinta métrica | No hay cintas métricas en el catálogo (C145 vacío). |
| 7#12, 8#13, 9#12, 10#12, 11#11 | Diccionario Inglés – Inglés | HUECO_CATALOGO (A y P) · `dic-ingles` Diccionario de inglés | Pide diccionario inglés-inglés (monolingüe); no hay en el catálogo (los tres son bilingües) y el filtro ya no cobra uno bilingüe. |

## 5. B. Falsos huecos

### 5.1 El sistema dice HUECO_CATALOGO y el producto existe (57 renglones)

La causa principal es el filtro por atributos (3.2 a): el producto no declara el atributo: 24 · valor cercano que la igualdad rechaza: 15 · el extractor leyó mal el renglón: 9 · el producto está en otro concepto: 8 · error de curaduría: 1.

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| 8#17, 9#16, 11#17 | cuaderno 5 materias cuadriculado grande | HUECO_CATALOGO (A y P) · `C001` Cuaderno | Existe TK-C001-CON-SPIDERMAN Argollado Multimaterias cuadriculado ($25.900, personaje), pero su `materias` es `multiple` y el filtro exige 3 o 5 exactas (`consulta.py:115-117`). Hay que confirmar cuántas materias trae. |
| 10#10 | Cuaderno 5 materias | HUECO_CATALOGO (A y P) · `C001` Cuaderno | Existe TK-C001-CON-SPIDERMAN Argollado Multimaterias cuadriculado ($25.900, personaje), pero su `materias` es `multiple` y el filtro exige 3 o 5 exactas (`consulta.py:115-117`). Hay que confirmar cuántas materias trae. |
| 10#17, 10#24, 10#27 | cuaderno 3 materias cuadriculado grande | HUECO_CATALOGO (A y P) · `C001` Cuaderno | Existe TK-C001-CON-SPIDERMAN Argollado Multimaterias cuadriculado ($25.900, personaje), pero su `materias` es `multiple` y el filtro exige 3 o 5 exactas (`consulta.py:115-117`). Hay que confirmar cuántas materias trae. |
| 11#10 | Cuaderno 5 materias preferiblemente empastado | HUECO_CATALOGO (A y P) · `C001` Cuaderno | Existe TK-C001-CON-SPIDERMAN Argollado Multimaterias cuadriculado ($25.900, personaje), pero su `materias` es `multiple` y el filtro exige 3 o 5 exactas (`consulta.py:115-117`). Hay que confirmar cuántas materias trae. |
| T#69, 1#26, 2#53 | bitácora o Sketchbook para arte tamaño octavo, argollada. (Verificar que las hojas tengan calibre grueso, tipo cartulina, tapa dura para facilitar su trabajo y manipulación, ninguna marca específica. La bitácora puede ser armada de la siguiente manera: 15 hojas de cartulina blanca tamaño octavo 10 hojas papel bond tamaño octavo 10 hojas papel acuarela tamaño octavo) | HUECO_CATALOGO (A y P) · `C001` Cuaderno | Pide bitácora o sketchbook en octavo. El filtro exige `hojas=15` y `rayado=blanco`, leídos de la receta para armarla ('15 hojas de cartulina blanca…'), y nada cumple. Sustituto: TK-C001-CON ICOPEL cuaderno de arte bond tapa dura ($16.990) o TK-REV-794726 Norma cuaderno de dibujo sin línea 80 h (C003, $15.850). |
| 1#15 | Cuaderno ferrocarril grande cosido 80 hojas | HUECO_CATALOGO (A y P) · `C001` Cuaderno | Pide ferrocarril cosido de 80 h; el único ferrocarril es de 100 h (TK-REV-47518218715307, $8.150) y el filtro exige `hojas=80` exactas. |
| 3#44, 4#42, 5#50, 6#30 | Sketch book tamaño carta | HUECO_CATALOGO (A y P) · `C003` Block | Pide sketch book carta; el filtro exige `tamano=carta` y el block de bocetos es A4 (TK-C003-PRE Mont Marte A4 60 h, $49.900), casi el mismo tamaño. También TK-REV-794726 Norma cuaderno de dibujo 80 h ($15.850). |
| J#14 | caja de marcadores gruesos x 12 | HUECO_CATALOGO (A y P) · `C006` Marcador | Pide marcadores gruesos x12; ningún producto declara `punta=punta gruesa` y el filtro deja fuera a los que no la declaran. Sustituto: TK-REV-632443 Faber Fiesta x12 ($16.700) o TK-C006-ECO Luxor lavables x20 ($20.900). |
| T#53 | marcador negro grueso permanente | HUECO_CATALOGO (A y P) · `C006` Marcador | Pide marcador permanente negro grueso; ninguno declara `punta`, salvo los Sharpie de punta fina. Sustituto: TK-REV-694313 Faber-Castell permanente negro ($4.400) o TK-REV-11453 Pelikan ($4.800). |
| J#96 | marcadores borrables para tablero 1 grueso · **cant. 2** | HUECO_CATALOGO (A y P) · `C006` Marcador | Pide 1 marcador borrable grueso (la curaduría dejó q=2); ningún borrable declara `punta=punta gruesa`. Sustituto: TK-REV-133274 Faber-Castell borrable negro ($5.390) o TK-REV-71996 Pelikan ($7.100), 1 unidad. |
| 1#47, 2#24, 3#14, 4#14, 5#15 | Archivador de fuelle, oficio, 13 bolsillos, tipo maleta | HUECO_CATALOGO (A y P) · `C011` Carpeta | Pide archivador de fuelle oficio; la única carpeta de fuelle (TK-C011-CON Starglow Scribe, $16.750) no declara `tamano` y el filtro la deja fuera. Hay que confirmar tamaño y bolsillos. |
| J#5 | maleta con capacidad para llevar una carpeta tamaño oficio. Para uso diario. | HUECO_CATALOGO (A y P) · `C011` Carpeta | Error de curaduría: 'maleta' asignada a C011 Carpeta; el filtro exige `tamano=oficio` y queda como hueco. Correspondía a C086 Maleta o morral, que tiene productos. |
| 4#32 | escuadra de 20 cm.- 45 grados | HUECO_CATALOGO (A y P) · `C019` Escuadra | Pide escuadra de 45° de 20 cm; el filtro exige longitud=20 cm exacta y descarta TK-C019-ECO Faber 45° de 26 cm ($6.400), que es la escuadra de 45° del catálogo y antes se aceptaba. |
| 1#54, 2#32 | frascos de vinilos colores primarios 120 ml · **cant. 3** | HUECO_CATALOGO (A y P) · `C020` Vinilo | Pide 3 frascos de vinilo primarios de 120 ml; el filtro exige presentacion=frasco y ningún vinilo la declara. Sustituto: TK-REV-124368970 vinilo escolar primarios 130 g x6 ($27.900), una caja en vez de 3 unidades. |
| J#17 | frascos de pintura escolares de 100 ml de colores variados con tapa dosificadora. (amarillo | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide pintura escolar en frasco de 100 ml de un color (entre paréntesis); el filtro lee 'colores variados' como `color=surtido` y ningún óleo cumple. Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| J#18 | frascos de pintura escolares de 100 ml de colores variados con tapa dosificadora. (azul | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide pintura escolar en frasco de 100 ml de un color (entre paréntesis); el filtro lee 'colores variados' como `color=surtido` y ningún óleo cumple. Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| J#19 | frascos de pintura escolares de 100 ml de colores variados con tapa dosificadora. (rojo | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide pintura escolar en frasco de 100 ml de un color (entre paréntesis); el filtro lee 'colores variados' como `color=surtido` y ningún óleo cumple. Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| J#20 | frascos de pintura escolares de 100 ml de colores variados con tapa dosificadora. (blanco | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide pintura escolar en frasco de 100 ml de un color (entre paréntesis); el filtro lee 'colores variados' como `color=surtido` y ningún óleo cumple. Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| J#21 | frascos de pintura escolares de 100 ml de colores variados con tapa dosificadora. (negro | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide pintura escolar en frasco de 100 ml de un color (entre paréntesis); el filtro lee 'colores variados' como `color=surtido` y ningún óleo cumple. Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| J#22 | frascos de pintura escolares de 100 ml de colores fluorescentes tapa dosificadora. (colores fluorescentes) · **cant. 2** | HUECO_CATALOGO (A y P) · `C027` Pintura | Pide pinturas escolares fluorescentes; el filtro exige `color=surtido` y ningún óleo cumple. Sustituto: TK-REV-104775445 vinilo fluorescente x3 Payasito ($23.000) o TK-REV-3006214 témpera fluorescente x6 ($12.990), ambos en C051. |
| 4#55 | 2 hojas de acetato tamaño oficio · **cant. 2** | HUECO_CATALOGO (A y P) · `C030` Acetato | Pide 2 hojas de acetato oficio; el filtro exige `tamano=oficio` y TK-C030-CON (acetato calibre 10 x5 hojas, $17.300) no declara tamaño. Basta 1 paquete. |
| 1#1, 2#1, 3#1, 4#1, 5#1, 6#1, 7#1, 8#1, 9#1, 10#1, 11#1 | Biblia católica | HUECO_CATALOGO (A y P) · `C048` Biblia | Pide Biblia católica; el filtro exige edicion=completa y solo TK-C048-ECO declara `edicion` (infantil). Las Biblias Latinoamericanas no declaran el atributo. Sustituto: TK-LIB-9788471512635 Biblia Latinoamericana rústica ($75.223). |
| 3#52 | Protector para ropa (delantal plástico) | HUECO_CATALOGO (A y P) · `C049` Delantal | Pide delantal plástico; el filtro exige material=plastico y el único delantal sin personaje, TK-REV-44922807910571 antifluido ($15.600), declara tela. Sirve como protector de ropa y antes se aceptaba. |
| 8#62 | 30 jumpers macho-macho 20cm de largo · **cant. 30** | HUECO_CATALOGO (A y P) · `C121` Cables jumper | Jumpers macho-macho de 20 cm: existe TK-REV-102561087 kit protoboard 840 + 40 jumpers de 20 cm ($26.000) en C071 Kit de tecnología; en Octavo cubre también la protoboard de 8#60. |
| 9#65 | jumpers macho-macho · **cant. 30** | HUECO_CATALOGO (A y P) · `C121` Cables jumper | Jumpers macho-macho de 20 cm: existe TK-REV-102561087 kit protoboard 840 + 40 jumpers de 20 cm ($26.000) en C071 Kit de tecnología; en Octavo cubre también la protoboard de 8#60. |
| J#71 | 10 hojas papel bond tamaño octavo | HUECO_CATALOGO (A y P) · `C129` Papel bond | Papel bond: C129 no tiene productos, pero el papel bond existe como resma en C031 (TK-C031-ECO HP 75 g carta x500, $16.500). La presentación es desproporcionada para 10 octavos. |
| 8#7 | Puñales en la niebla. Danilo E. Ramírez G. Editorial Enlace | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | Existe en el catálogo: TK-REV-9786287761919 'Puñales en la niebla' (Enlace, Danilo Ramírez G.), $39.500, en C044. C134 no tiene productos y la ruta rápida solo trae los productos del concepto asignado (routers/admin.py:384-389): no busca por título. |
| 8#8 | El mensajero de Agartha 6: Metempsicosis.Mario Mendoza. Editorial Planeta | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | Existe en el catálogo: TK-REV-9786287579903 'El mensajero de Agartha 6. Metempsicosis' (Planeta/Destino), $42.300, en C044. |
| 11#6 | Orgullo y Prejuicio. Autor: Jane Austen. Editorial: Enlace. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | Existe en el catálogo: TK-REV-9789585990937 'Los Bennet. Orgullo y prejuicio' kit (Enlace), $41.500, en C044. Hay que confirmar que sea la edición que pide el colegio. |
| 11#7 | Aquiles en TikTok: El camino a la virtud. Autor: Eduardo Infante. Editorial: Planeta. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | Existe en el catálogo: TK-REV-9788434436169 (Ariel, Grupo Planeta, $95.544); la URL de origen es 'aquiles-en-tiktok'. El nombre del producto perdió el título ('Ariel (Grupo Planeta), Tapa Blanda, 2023'). |
| 9#72 | módulo Puente H (L298N recomendado) | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Existe en el catálogo: TK-REV-102416735 módulo L298N puente H ($17.800), mal clasificado en C071 Kit de tecnología. C142 no tiene productos y es tipo `otro` (el ADR 0027 cita el puente H entre lo que no se vende), pero el catálogo sí vende este módulo: hay que decidir cuál de las dos curadurías manda. |
| 2#11 | Diccionario Larousse Básico Inglés - español | HUECO_CATALOGO (A y P) · `dic-ingles` Diccionario de inglés | Pide diccionario inglés-español; el concepto filtra por `monolingue` y ningún producto declara ese atributo, así que nada cumple. Sustituto: TK-LIB-9789706073990 Larousse School español-inglés ($27.000) o TK-LIB-9780194337311 Oxford Pocket ($136.000). |
| 3#12 | Diccionario: espanol - ingles | HUECO_CATALOGO (A y P) · `dic-ingles` Diccionario de inglés | Pide diccionario inglés-español; el concepto filtra por `monolingue` y ningún producto declara ese atributo, así que nada cumple. Sustituto: TK-LIB-9789706073990 Larousse School español-inglés ($27.000) o TK-LIB-9780194337311 Oxford Pocket ($136.000). |

## 6. C. Mal elegidos

### 6.1 En los dos perfiles (97 renglones)

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| 11#21 | cuaderno tres materias cuadriculado grande | `C001` Cuaderno<br>**A y P:** Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) $7.150 | Pide tres materias; el extractor solo lee el número en cifras (`enriquecer.py:972-979`) y exige `materias=1`, así que se cobra uno de una materia. El único multimaterias es TK-C001-CON-SPIDERMAN ($25.900, personaje). |
| 11#24 | cuaderno tres materias cuadriculado grande | `C001` Cuaderno<br>**A:** Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) $7.150<br>**P:** Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Hombre (`TK-REV-2512282`) $7.150 | Pide tres materias; el extractor solo lee el número en cifras (`enriquecer.py:972-979`) y exige `materias=1`, así que se cobra uno de una materia. El único multimaterias es TK-C001-CON-SPIDERMAN ($25.900, personaje). |
| J#69 | bitácora o Sketchbook para arte tamaño octavo, argollada | `C001` Cuaderno<br>**A:** Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) $7.150<br>**P:** Cuaderno argollado rayado de 100 hojas (`TK-C001-PRE`) $39.900 | Pide bitácora o sketchbook en octavo; A cobra un cuaderno cosido cuadriculado y P un argollado rayado Mr Wonderful ($39.900). Sustituto: TK-REV-794726 Norma cuaderno de dibujo sin línea 80 h argollado ($15.850, en C003) o TK-C001-CON ICOPEL cuaderno de arte bond tapa dura ($16.990). |
| J#59 | lápices negros gruesos · **cant. 2** | `C002` Lápiz<br>**A:** Lápiz Negro HB Eterna (`TK-C002-CON`) $6.500 × 2 = $13.000<br>**P:** Lapiz primavera negro x 12 PRIMAVERA (`TK-REV-3331469`) $6.900 × 2 = $13.800 | Pide lápices negros gruesos (q=2); A cobra 2 Eterna HB y P 2 cajas Primavera x12, todos delgados: el grosor no es atributo del concepto. Sustituto: TK-C002-PRE Kores Jumbo x12 ($15.400), 1 caja. |
| 3#45, 4#43 | Lápiz 2H-6B | `C002` Lápiz<br>**A:** Lápiz Negro HB Eterna (`TK-C002-CON`) $6.500<br>**P:** Lapiz primavera negro x 12 PRIMAVERA (`TK-REV-3331469`) $6.900 | Error de curaduría: pide la serie 2H-6B (kit de dibujo), asignado a C002 Lápiz; se cobra un lápiz HB. Sustituto: TK-REV-124280762 caja de lápices de dibujo Eterna ($13.000, C114). |
| 1#65 | colores delgados X12 · **cant. 12** | `C004` Colores<br>**A:** Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) $6.100 × 0 = $0<br>**P:** Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) $6.100 × 12 = $73.200 | Cantidad mal curada: el 'X12' (colores por caja) se leyó como cantidad 12. P compra 12 cajas Norma x12 ($73.200); en A el renglón se fusiona con 1#20 y las 12 cajas pasan a esa línea. Debe ser 1 caja de 12. |
| J#61 | cajas de colores x 12 triangulares gruesos · **cant. 2** | `C004` Colores<br>**A y P:** Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) $6.100 × 2 = $12.200 | Pide colores triangulares gruesos x12; el filtro solo lee `unidades=12` y se cobran los Norma Imágenes delgados de 3 mm. Sustituto: TK-REV-100717597 Prismacolor triangulares gruesos x12 ($24.890). |
| J#13, T#14 | caja de marcadores delgados x 12 | `C006` Marcador<br>**A y P:** Marcador Sharpie Punta Fina Rojo (`TK-REV-44702916182187`) $4.400 | Pide caja de 12 marcadores delgados; el filtro solo exige `punta=punta fina` y el más barato que cumple es un Sharpie rojo suelto ($4.400). Sustituto: TK-REV-639636 Keyroad delgados x12 ($10.900) o TK-C006-CON neón delgados x12 ($20.900). |
| J#79, T#76, 1#32, 2#60 | caja de marcadores gráficos x 10 | `C006` Marcador<br>**A:** Marcador Sharpie Punta Fina Rojo (`TK-REV-44702916182187`) $4.400<br>**P:** Plumones SuperTips lavables colores pastel x 12 unidades (`TK-REV-667410`) $23.450 | Pide caja de marcadores gráficos x10; A cobra un Sharpie rojo suelto y P Crayola pastel x12. Sustituto: TK-REV-44702870110379 Norma doble punta x10 ($23.800). |
| J#95 | marcadores borrables para tablero 1 delgado · **cant. 2** | `C006` Marcador<br>**A y P:** Paquete Marcador Kores Borrable X4 Unds Punta Delgada Surtido (`TK-REV-47122444714155`) $9.350 × 2 = $18.700 | Pide 1 marcador borrable delgado; la curaduría dejó q=2 y el único borrable de punta fina es el paquete Kores x4, así que se compran 8 marcadores ($18.700). Basta 1 paquete. |
| J#36 | paquetes de octavos de cartulina pasteles · **cant. 3** | `C010` Cartulina<br>**A:** Cartulina escolar de 1/8 135 g x 10 unidades blanca (`TK-REV-633655`) $4.600 × 3 = $13.800<br>**P:** Paquete Carton Cartulina Octavo x25 Unds (`TK-C010-PRE`) $18.600 × 3 = $55.800 | Pide cartulina de colores (pastel, vivos o Bristol); se cobra blanca o cartón. Sustituto: TK-REV-633667 cartulina surtida x10 ($4.800). |
| T#32 | paquetes de octavos de cartulina pastel · **cant. 2** | `C010` Cartulina<br>**A:** Cartulina escolar de 1/8 135 g x 10 unidades blanca (`TK-REV-633655`) $4.600 × 2 = $9.200<br>**P:** Paquete Carton Cartulina Octavo x25 Unds (`TK-C010-PRE`) $18.600 × 2 = $37.200 | Pide cartulina de colores (pastel, vivos o Bristol); se cobra blanca o cartón. Sustituto: TK-REV-633667 cartulina surtida x10 ($4.800). |
| 5#22 | paquete de (1/8 cartulina) color agua marina o similares | `C010` Cartulina<br>**A:** Cartulina escolar de 1/8 135 g x 10 unidades blanca (`TK-REV-633655`) $4.600<br>**P:** Paquete Carton Cartulina Octavo x25 Unds (`TK-C010-PRE`) $18.600 | Pide un color específico (amarillo, azul, verde, agua marina); se cobra blanca. Sustitutos: TK-REV-633665 / TK-REV-633659 / TK-REV-633661 (agua marina → azul o verde). |
| 6#40 | 4 octavos de cartulina negra · **cant. 4** | `C010` Cartulina<br>**A y P:** Cartulina Negra 1/8 Manualidades Escolar X10 Negro (`TK-REV-104886189`) $8.500 × 4 = $34.000 | Pide 4 octavos de cartulina negra; el producto es el correcto (TK-REV-104886189 negra 1/8 x10, $8.500) pero q=4 compra 4 paquetes (40 octavos, $34.000). Basta 1 paquete. |
| 7#39, 8#40, 9#48 | Kit de 12 pinceles sintéticos. delgados, planos redondos y abanico | `C021` Pincel<br>**A y P:** Pincel Pentel Aquash punta fina para acuarela (`TK-REV-517439`) $29.800 | Pide kit de 12 pinceles sintéticos variados; el filtro lee 'delgados' como `grosor=delgado` y se cobra un solo pincel de agua Pentel Aquash ($29.800). Sustituto: TK-C021-CON Mont Marte x15 mixto ($26.900). |
| 10#52, 11#48 | Kit de 12 pinceles sintéticos. (delgados,planos redondos y abanico etc.) | `C021` Pincel<br>**A y P:** Pincel Pentel Aquash punta fina para acuarela (`TK-REV-517439`) $29.800 | Pide kit de 12 pinceles sintéticos variados; el filtro lee 'delgados' como `grosor=delgado` y se cobra un solo pincel de agua Pentel Aquash ($29.800). Sustituto: TK-C021-CON Mont Marte x15 mixto ($26.900). |
| 4#48 | Pinceles de punta plana y redonda | `C021` Pincel<br>**A:** Pincel Plano Eterna #5 (`TK-REV-124275612`) $1.200<br>**P:** Pincel Pentel Aquash punta fina para acuarela (`TK-REV-517439`) $29.800 | Pide pinceles planos y redondos; A cobra un solo plano Eterna #5 y P un Pentel Aquash. Sustituto: TK-C021-CON Mont Marte x15 mixto ($26.900), o un plano y un redondo Eterna #5 ($1.200 cada uno). |
| J#11 | caja de plastilina gigante larga x12 colores · **cant. 3** | `C022` Plastilina<br>**A:** Plastilina Larga Caja X12 Colores PELIKAN (`TK-REV-3007961`) $5.950 × 3 = $17.850<br>**P:** Plastilina en barra Norma x 12 uds. (`TK-C022-PRE`) $11.200 × 3 = $33.600 | Pide plastilina gigante larga x12 (q=3 / q=2 cajas); A cobra Pelikan larga x12 y P Norma x12 normal: 'gigante' no es atributo del concepto. Sustituto: TK-REV-538665 Norma gigante x12 ($12.900). |
| T#12 | cajas de plastilina gigante larga x12 colores · **cant. 2** | `C022` Plastilina<br>**A:** Plastilina Larga Caja X12 Colores PELIKAN (`TK-REV-3007961`) $5.950 × 2 = $11.900<br>**P:** Plastilina en barra Norma x 12 uds. (`TK-C022-PRE`) $11.200 × 2 = $22.400 | Pide plastilina gigante larga x12 (q=3 / q=2 cajas); A cobra Pelikan larga x12 y P Norma x12 normal: 'gigante' no es atributo del concepto. Sustituto: TK-REV-538665 Norma gigante x12 ($12.900). |
| 8#19 | Transportador, compás de precisión | `C023` Transportador<br>**A:** Transportador escolar de 360° Faber Castell (`TK-C023-CON`) $3.600<br>**P:** Transportador 360 Grados FABER CASTELL (`TK-REV-4673`) $10.260 | Renglón compuesto 'Transportador, compás de precisión': solo se cobra el transportador y el compás se omite. Existe TK-C018-PRE compás Faber Precision. |
| T#17 | frascos de pintura escolares de 100 ml de color amarillo con tapa dosificadora | `C027` Pintura<br>**A y P:** Óleo franco amarillo ocre de 50 ml (`TK-REV-684702`) $14.700 | Pide pintura escolar en frasco de 100 ml por color; el filtro solo exige el color y se cobra un óleo de ese color (Franco 50 ml $14.700; blanco y negro Mont Marte 75 ml $29.900). Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| T#18 | frascos de pintura escolares de 100 ml de color azul con tapa dosificadora | `C027` Pintura<br>**A y P:** Óleo franco azul ultramar de 50 ml (`TK-REV-684710`) $14.700 | Pide pintura escolar en frasco de 100 ml por color; el filtro solo exige el color y se cobra un óleo de ese color (Franco 50 ml $14.700; blanco y negro Mont Marte 75 ml $29.900). Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| T#19 | frascos de pintura escolares de 100 ml de color rojo con tapa dosificadora | `C027` Pintura<br>**A y P:** Óleo franco tono rojo cadmio de 50 ml (`TK-REV-684716`) $14.700 | Pide pintura escolar en frasco de 100 ml por color; el filtro solo exige el color y se cobra un óleo de ese color (Franco 50 ml $14.700; blanco y negro Mont Marte 75 ml $29.900). Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| T#20 | frascos de pintura escolares de 100 ml de color blanco con tapa dosificadora | `C027` Pintura<br>**A y P:** Pintura al óleo de 75 ml, blanco titanio (`TK-REV-635462`) $29.900 | Pide pintura escolar en frasco de 100 ml por color; el filtro solo exige el color y se cobra un óleo de ese color (Franco 50 ml $14.700; blanco y negro Mont Marte 75 ml $29.900). Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| T#21 | frascos de pintura escolares de 100 ml de color negro con tapa dosificadora | `C027` Pintura<br>**A y P:** Pintura al óleo de 75 ml, negro Marte (`TK-REV-635505`) $29.900 | Pide pintura escolar en frasco de 100 ml por color; el filtro solo exige el color y se cobra un óleo de ese color (Franco 50 ml $14.700; blanco y negro Mont Marte 75 ml $29.900). Sustituto: vinilo Botero por color (TK-REV-170423 amarillo, TK-REV-170424 azul, TK-REV-159044 rojo, TK-REV-159041 blanco, TK-REV-159040 negro; C020) o TK-REV-124368970 vinilo escolar x6. |
| T#22 | frasco de pintura escolar de 100 ml de color fluorescente con tapa dosificadora | `C027` Pintura<br>**A:** Óleo franco magenta 50 ml (`TK-C027-ECO`) $13.400<br>**P:** Óleo franco sombra tostada de 50 ml (`TK-REV-684705`) $14.700 | Pide pintura escolar fluorescente; se cobra óleo (A magenta, P sombra tostada). Sustituto: TK-REV-104775445 vinilo fluorescente x3 Payasito ($23.000) o TK-REV-3006214 témpera fluorescente x6 ($12.990). |
| J#80, T#79 | pintura académica amarillo | `C027` Pintura<br>**A y P:** Óleo franco amarillo ocre de 50 ml (`TK-REV-684702`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| J#81, T#80 | pintura académica azul | `C027` Pintura<br>**A y P:** Óleo franco azul ultramar de 50 ml (`TK-REV-684710`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| J#82, T#81 | pintura académica rojo | `C027` Pintura<br>**A y P:** Óleo franco tono rojo cadmio de 50 ml (`TK-REV-684716`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| 1#33 | pintura académica color amarillo | `C027` Pintura<br>**A y P:** Óleo franco amarillo ocre de 50 ml (`TK-REV-684702`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| 1#34 | pintura académica color azul | `C027` Pintura<br>**A y P:** Óleo franco azul ultramar de 50 ml (`TK-REV-684710`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| 1#35 | pintura académica color rojo | `C027` Pintura<br>**A y P:** Óleo franco tono rojo cadmio de 50 ml (`TK-REV-684716`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| 2#61 | pintura académica color 120g, amarillo | `C027` Pintura<br>**A y P:** Óleo franco amarillo ocre de 50 ml (`TK-REV-684702`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| 2#62 | pintura académica color 120g, azul | `C027` Pintura<br>**A y P:** Óleo franco azul ultramar de 50 ml (`TK-REV-684710`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| 2#63 | pintura académica color 120g, rojo | `C027` Pintura<br>**A y P:** Óleo franco tono rojo cadmio de 50 ml (`TK-REV-684716`) $14.700 | Pide pintura académica (témpera escolar) por color; se cobra un óleo Franco de 50 ml del color ($14.700). Sustituto: TK-REV-606459 témpera académica x6 Bozetto ($20.500) o TK-REV-47123276529835 Payasito x6 primarios ($4.350). |
| J#93 | barras largas de silicona · **cant. 2** | `C028` Silicona<br>**A:** Barra Silicona Transparente Delgada X 10 Unidades (`TK-C028-ECO`) $10.400 × 2 = $20.800<br>**P:** Docena Barra Silicona Gruesa (`TK-C028-PRE`) $16.250 × 2 = $32.500 | Pide barras de silicona (q=2); el sistema compra 2 paquetes de 10-12 barras. |
| J#94 | barras delgadas de silicona · **cant. 2** | `C028` Silicona<br>**A y P:** Barra Silicona Transparente Delgada X 10 Unidades (`TK-C028-ECO`) $10.400 × 2 = $20.800 | Pide 2 barras delgadas de silicona; el producto es un paquete de 10 y q=2 compra 2 paquetes (20 barras). Basta 1 paquete. |
| J#30 | paquetes de foamy escarchado tamaño octavo colores surtidos · **cant. 2** | `C029` Foamy<br>**A y P:** Foamy en octavo x 10 unidades, 25 cm x 35 cm (`TK-REV-612632`) $13.900 × 2 = $27.800 | Pide foamy escarchado; 'escarchado' no es atributo de C029 (solo filtra color y tamaño) y se cobra foamy liso. Sustituto: TK-REV-612633 foamy escarchado 1/8 x10 ($23.700). |
| T#27 | paquetes de foami escarchado tamaño octavo colores surtidos · **cant. 2** | `C029` Foamy<br>**A y P:** Foamy en octavo x 10 unidades, 25 cm x 35 cm (`TK-REV-612632`) $13.900 × 2 = $27.800 | Pide foamy escarchado; 'escarchado' no es atributo de C029 (solo filtra color y tamaño) y se cobra foamy liso. Sustituto: TK-REV-612633 foamy escarchado 1/8 x10 ($23.700). |
| T#78 | Acetatos tamaño carta. · **cant. 2** | `C030` Acetato<br>**A y P:** Acetato De Laminacion Carta Calibre 10 X 10 Unidades (`TK-REV-104236147`) $25.000 × 2 = $50.000 | Pide acetatos carta (q=2 hojas); el producto es un paquete de 10 y q=2 compra 2 paquetes (20 hojas, $50.000). Basta 1 paquete. |
| 7#63 | octavos de cartón paja · **cant. 4** | `C041` Cartón<br>**A:** Cartón paja color crema por 10 uds. (`TK-C041-CON`) $10.200 × 4 = $40.800<br>**P:** Paquete Carton Paja Octavos x10 Unds Colores (`TK-C041-PRE`) $11.750 × 4 = $47.000 | Pide 4 octavos de cartón paja; el producto es un paquete de 10 octavos y q=4 compra 4 paquetes (40 octavos). Basta 1 paquete (TK-C041-CON crema $10.200 / TK-C041-PRE colores $11.750). |
| 7#68 | octavos de cartón paja de colores · **cant. 4** | `C041` Cartón<br>**A y P:** Paquete Carton Paja Octavos x10 Unds Colores (`TK-C041-PRE`) $11.750 × 4 = $47.000 | Pide 4 octavos de cartón paja; el producto es un paquete de 10 octavos y q=4 compra 4 paquetes (40 octavos). Basta 1 paquete (TK-C041-CON crema $10.200 / TK-C041-PRE colores $11.750). |
| T#49 | tubos de escarcha (colores variados) · **cant. 3** | `C052` Escarcha<br>**A:** Escarcha Brillantina En Tubo X 12 Unidades Para Manualidades (`TK-C052-ECO`) $8.000 × 3 = $24.000<br>**P:** Paquete Escarcha En Libra Azul (`TK-C052-CON`) $14.150 × 3 = $42.450 | Pide 3 tubos de escarcha; A compra 3 paquetes de 12 tubos (36 tubos) y P 3 libras de escarcha azul. |
| 1#5 | Juego didáctico de mesa acorde a la edad | `C054` Juego didáctico<br>**A:** Rompecabezas En Madera Animales 4 Piezas Grande (`TK-REV-45308083667115`) $13.600<br>**P:** Computador Didactico 6683 Niños Aprender Ordenador Educativo Ingles (`TK-REV-101941514`) $48.900 | Pide juego de mesa para Primero; A es un rompecabezas de 4 piezas para bebé y P un computador didáctico. Sustituto: TK-REV-104913796 juego de madera con tableros de letras y números ($83.381). |
| 2#52 | fichas bibliográficas (blancas) · **cant. 10** | `C078` Fichas bibliográficas<br>**A:** Paquete Ficha Bibliografica X50 Unds Azul (`TK-C078-ECO`) $2.950 × 10 = $29.500<br>**P:** Fichas Bibliográficas Cartulina X 100 Unidades Colores: Blanco, Amarillo, Azul, Rosado (Según Disponibilidad) (`TK-REV-104986188`) $8.000 × 10 = $80.000 | Fichas bibliográficas: q=10 se leyó como 10 paquetes (500 fichas azules). |
| T#7 | maleta de rodachines | `C086` Maleta<br>**A y P:** Maleta Morral Bolso Pequeño Infantil De Animales Para Niños Mariquita (`TK-REV-103740754`) $40.000 | Pide maleta de rodachines; "rodachines" no se extrae como tipo=con ruedas y se cobra un morral pequeño sin ruedas (TK-REV-103740754, $40.000). El único con ruedas es TK-C086-CON-BLUEY Totto ($269.900), con personaje. |
| 6#47, 7#73 | Protoboard de 400 puntos mediana | `C102` Protoboard<br>**A y P:** Protoboard Gl12 Con 840 Puntos (`TK-REV-104905872`) $24.000 | Pide protoboard de 400 puntos; se cobra la de 840 ($24.000), el único producto de C102. Existe TK-REV-101119299 AVC 400 puntos ($8.900), mal clasificada en C071 Kit de tecnología. |
| 8#60 | 1 Protoboard Genérica MB-102 400 puntos | `C102` Protoboard<br>**A y P:** Protoboard Gl12 Con 840 Puntos (`TK-REV-104905872`) $24.000 | Pide protoboard de 400 puntos; se cobra la de 840 ($24.000), el único producto de C102. Existe TK-REV-101119299 AVC 400 puntos ($8.900), mal clasificada en C071 Kit de tecnología. |
| J#90 | Gorro en Lycra o Silicona y Gafas | `C111` Gorro de natación<br>**A:** Gorro De Natación En Silicona E Sport Azul (`TK-REV-104996053`) $12.000<br>**P:** Gorro de Natación Classic Silicone (`TK-REV-123728132`) $67.900 | Renglón compuesto 'Gorro … y Gafas': la curaduría solo asignó C111 Gorro y las gafas no se cobran. Existe C136 TK-REV-104926378 ($19.900). |
| 7#57 | hojas papel durex tamaño 1/8 · **cant. 10** | `C112` Papel durex<br>**A y P:** Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 | Pide 10 hojas de durex; q=10 compra 10 paquetes de 20 hojas ($135.000). Basta 1 paquete ($13.500). |
| 8#56 | 10 hojas de papel durex tamaño octavo · **cant. 10** | `C112` Papel durex<br>**A y P:** Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 | Pide 10 hojas de durex; q=10 compra 10 paquetes de 20 hojas ($135.000). Basta 1 paquete ($13.500). |
| 9#58 | hojas Durex tamaño octavo · **cant. 10** | `C112` Papel durex<br>**A y P:** Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 | Pide 10 hojas de durex; q=10 compra 10 paquetes de 20 hojas ($135.000). Basta 1 paquete ($13.500). |
| 10#62, 11#59 | hojas de papel dure 180 grms · **cant. 10** | `C112` Papel durex<br>**A y P:** Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 | Pide 10 hojas de durex; q=10 compra 10 paquetes de 20 hojas ($135.000). Basta 1 paquete ($13.500). |
| J#53, T#35 | block de papel para plegado de 15 X15 cm | `C113` Papel iris<br>**A y P:** Block Iris Carta Colores Surtidos X 12H FINLANDEK (`TK-REV-3630108`) $2.290 | Pide block de plegado 15×15; el concepto no exige tamaño y se cobra el block iris carta. Sustituto: TK-REV-729206 block iris plegado 15×15 x20 ($2.600), del mismo concepto. |
| 3#37 | block de papel para plegados de 20 x 20 o 15 x 15 | `C113` Papel iris<br>**A y P:** Block Iris Carta Colores Surtidos X 12H FINLANDEK (`TK-REV-3630108`) $2.290 | Pide block de plegado de 20×20 o 15×15; se cobra el block iris carta. Sustituto: TK-REV-44702917623979 plegado 20×20 x20 ($4.000) o TK-REV-729206 (15×15). |
| 10#61, 11#58 | Papel iris octavos. | `C113` Papel iris<br>**A y P:** Block Iris Carta Colores Surtidos X 12H FINLANDEK (`TK-REV-3630108`) $2.290 | Pide papel iris en octavos; se cobra block carta. Sustituto cercano: TK-REV-705165 cartulina iris 1/8 x20 ($12.900, C010). |
| 11#18 | Instrumentos de trazo | `C114` Kit de lápices de dibujo<br>**A:** Caja de Lápices Para Dibujo Eterna (`TK-REV-124280762`) $13.000<br>**P:** Set de 12 lápices de dibujo con accesorios (`TK-REV-554182`) $35.900 | 'Instrumentos de trazo' en el bloque de matemáticas y física de Once: probablemente juego de geometría (C036), no lápices de dibujo. Sustituto: TK-C036-ECO juego geométrico Eterna ($9.000). |
| J#23, T#23 | paleta de acuarelas x 12 | `C117` Paleta de pintura<br>**A:** Paleta de fórmica tradicional (`TK-REV-87487`) $14.900<br>**P:** Set de herramientas de arte x 5 piezas, blanco (`TK-REV-627492`) $34.900 | Pide paleta (set) de acuarelas x12; A cobra una paleta de fórmica y P un set de herramientas de arte. Sustituto: TK-C065-PRE acuarela x12 con pincel y paleta ($39.900) o TK-C065-CON Pelikan x12 ($30.000). |
| 2#54 | paleta de acuarelas | `C117` Paleta de pintura<br>**A:** Paleta de fórmica tradicional (`TK-REV-87487`) $14.900<br>**P:** Set de herramientas de arte x 5 piezas, blanco (`TK-REV-627492`) $34.900 | Pide paleta (set) de acuarelas x12; A cobra una paleta de fórmica y P un set de herramientas de arte. Sustituto: TK-C065-PRE acuarela x12 con pincel y paleta ($39.900) o TK-C065-CON Pelikan x12 ($30.000). |
| 8#55 | 6 hojas Papel acuarela tamaño octavo · **cant. 6** | `C119` Papel acuarela<br>**A:** Papel acuarela blanco de 1/8 x 5 unidades, 300 g (`TK-REV-581780`) $10.000 × 6 = $60.000<br>**P:** Bloc argollado de papel acuarela de 20 hojas (`TK-REV-638487`) $59.900 × 6 = $359.400 | Papel acuarela: q=6 o q=10 compra paquetes o blocs ($60.000 / $100.000 A; $359.400 / $599.000 P). Bastan 2 paquetes de 5 hojas. |
| 9#59 | hojas de papel acuarela · **cant. 10** | `C119` Papel acuarela<br>**A:** Papel acuarela blanco de 1/8 x 5 unidades, 300 g (`TK-REV-581780`) $10.000 × 10 = $100.000<br>**P:** Bloc argollado de papel acuarela de 20 hojas (`TK-REV-638487`) $59.900 × 10 = $599.000 | Papel acuarela: q=6 o q=10 compra paquetes o blocs ($60.000 / $100.000 A; $359.400 / $599.000 P). Bastan 2 paquetes de 5 hojas. |
| 4#56 | 2 hojas de papel pergamino · **cant. 2** | `C120` Papel pergamino<br>**A:** Bloc de papel pergamino, 25 hojas de 1/8 (`TK-REV-97606`) $15.500 × 2 = $31.000<br>**P:** Bloc de papel pergamino para dibujo de 1/8, 50 hojas (`TK-REV-116389`) $30.600 × 2 = $61.200 | Papel pergamino: q en hojas compra blocs de 25 ($155.000 A / $306.000 P con q=10). Basta 1 bloc. |
| 7#56, 9#60 | octavos de papel pergamino · **cant. 10** | `C120` Papel pergamino<br>**A:** Bloc de papel pergamino, 25 hojas de 1/8 (`TK-REV-97606`) $15.500 × 10 = $155.000<br>**P:** Bloc de papel pergamino para dibujo de 1/8, 50 hojas (`TK-REV-116389`) $30.600 × 10 = $306.000 | Papel pergamino: q en hojas compra blocs de 25 ($155.000 A / $306.000 P con q=10). Basta 1 bloc. |
| 8#57 | 10 hojas de papel pergamino · **cant. 10** | `C120` Papel pergamino<br>**A:** Bloc de papel pergamino, 25 hojas de 1/8 (`TK-REV-97606`) $15.500 × 10 = $155.000<br>**P:** Bloc de papel pergamino para dibujo de 1/8, 50 hojas (`TK-REV-116389`) $30.600 × 10 = $306.000 | Papel pergamino: q en hojas compra blocs de 25 ($155.000 A / $306.000 P con q=10). Basta 1 bloc. |
| J#39, J#83, T#82, 1#36, 2#64 | pliegos de papel Kraft café · **cant. 2** | `C126` Papel kraft<br>**A y P:** Papel Kraft Mano Pliego X 25 Unidades (`TK-REV-105198360`) $11.900 × 2 = $23.800 | Pide 2-3 pliegos de kraft; el sistema compra 2-3 paquetes de 25 pliegos (único producto). Basta 1 paquete. |
| T#38 | pliegos de papel Kraft café · **cant. 3** | `C126` Papel kraft<br>**A y P:** Papel Kraft Mano Pliego X 25 Unidades (`TK-REV-105198360`) $11.900 × 3 = $35.700 | Pide 2-3 pliegos de kraft; el sistema compra 2-3 paquetes de 25 pliegos (único producto). Basta 1 paquete. |
| J#32 | pliegos de papel crepe colores surtidos · **cant. 2** | `C127` Papel crepé<br>**A y P:** Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 | Pide pliegos de crepé (surtidos); se cobran 2 paquetes x10 lila. Sustituto: TK-REV-46473281929387 crepé x10 surtido ($7.850), 1 paquete. |
| J#84, T#83, 1#37, 1#53, 2#31, 2#65 | pliegos de papel crepe · **cant. 2** | `C127` Papel crepé<br>**A y P:** Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 | Pide pliegos de crepé (surtidos); se cobran 2 paquetes x10 lila. Sustituto: TK-REV-46473281929387 crepé x10 surtido ($7.850), 1 paquete. |
| T#29 | pliegos de papel crepe colores surti · **cant. 2** | `C127` Papel crepé<br>**A y P:** Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 | Pide pliegos de crepé (surtidos); se cobran 2 paquetes x10 lila. Sustituto: TK-REV-46473281929387 crepé x10 surtido ($7.850), 1 paquete. |
| J#31 | pliegos de papel seda colores surtidos · **cant. 2** | `C128` Papel seda<br>**A y P:** Rollo Papel Seda Naranja X25 Medios De Pliego (`TK-REV-44702889902251`) $5.500 × 2 = $11.000 | Pide pliegos de seda surtidos; se cobran 2-3 rollos x25 naranja. No hay surtido: lo correcto es 1 rollo de 2 o 3 colores distintos. |
| T#28 | pliegos de papel seda colores surtido · **cant. 3** | `C128` Papel seda<br>**A y P:** Rollo Papel Seda Naranja X25 Medios De Pliego (`TK-REV-44702889902251`) $5.500 × 3 = $16.500 | Pide pliegos de seda surtidos; se cobran 2-3 rollos x25 naranja. No hay surtido: lo correcto es 1 rollo de 2 o 3 colores distintos. |

### 6.2 Solo en el Ahorrador (23 renglones)

El Premium cumple.

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| 1#20 | Caja de colores | `C004` Colores<br>**A:** Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) $6.100 × 12 = $73.200<br>**P:** COLORES TRIANGULAR X 24 ECO FABER CASTELL (`TK-C004-PRE`) $32.200 | Pide una caja de colores. En A se fusiona con 1#65, cuya cantidad mal curada (12) sube esta línea a 12 cajas Norma x12 ($73.200). P (Faber-Castell x24) cumple. |
| 3#62 | caja de plumones | `C006` Marcador<br>**A:** Marcador Sharpie Punta Fina Rojo (`TK-REV-44702916182187`) $4.400<br>**P:** Plumones SuperTips lavables colores pastel x 12 unidades (`TK-REV-667410`) $23.450 | Pide marcadores (una caja); sin atributo que filtrar, el Ahorrador cobra un Sharpie permanente suelto ($4.400). P (Crayola x12) cumple. Sustituto A: TK-REV-639636 Keyroad x12 ($10.900) o TK-C006-ECO Luxor lavables x20 ($20.900). |
| 7#87, 9#81, 10#70, 11#67 | marcadores | `C006` Marcador<br>**A:** Marcador Sharpie Punta Fina Rojo (`TK-REV-44702916182187`) $4.400<br>**P:** Plumones SuperTips lavables colores pastel x 12 unidades (`TK-REV-667410`) $23.450 | Pide marcadores (una caja); sin atributo que filtrar, el Ahorrador cobra un Sharpie permanente suelto ($4.400). P (Crayola x12) cumple. Sustituto A: TK-REV-639636 Keyroad x12 ($10.900) o TK-C006-ECO Luxor lavables x20 ($20.900). |
| 8#77 | marcadores | `C006` Marcador<br>**A:** Marcador Sharpie Punta Fina Negro (`TK-REV-44702916313259`) $4.400<br>**P:** Plumones SuperTips lavables colores pastel x 12 unidades (`TK-REV-667410`) $23.450 | Pide marcadores (una caja); sin atributo que filtrar, el Ahorrador cobra un Sharpie permanente suelto ($4.400). P (Crayola x12) cumple. Sustituto A: TK-REV-639636 Keyroad x12 ($10.900) o TK-C006-ECO Luxor lavables x20 ($20.900). |
| T#64, 2#41, 3#26, 4#24, 5#33 | tajalápiz con portabasura | `C007` Tajalápiz<br>**A:** Sacapuntas Y Borrador Redondo TW EVANS (`TK-C007-ECO`) $5.990<br>**P:** Sacapuntas Faber Castell Con Deposito Set X 3 Unidades (`TK-C007-PRE`) $9.405 | Pide tajalápiz con portabasura (depósito); «portabasura» no se extrae como deposito y A cobra TK-C007-ECO sacapuntas y borrador TW Evans, sin depósito. Sustituto: TK-C007-PRE Faber con depósito x3 ($9.405); P cumple. |
| J#70 | 15 hojas de cartulina blanca tamaño octavo | `C010` Cartulina<br>**A:** Cartulina escolar de 1/8 135 g x 10 unidades blanca (`TK-REV-633655`) $4.600<br>**P:** Paquete Carton Cartulina Octavo x25 Unds (`TK-C010-PRE`) $18.600 | Pide 15 hojas; A trae 10. Sustituto: TK-REV-633654 cartulina blanca x25 ($11.200). |
| J#62 | tijeras puntaroma | `C013` Tijeras<br>**A:** Tijeras Multiusos 6,5 pulgadas Eterna (`TK-C013-ECO`) $5.800<br>**P:** Tijera punta roma NESSAN (`TK-C013-PRE`) $10.490 | Pide tijeras 'puntaroma' (junto); no se extrae punta=punta roma y A cobra TK-C013-ECO Eterna multiusos, de punta. Sustituto: TK-C013-CON Milan punta roma ($10.490); P cumple. |
| J#16 | pegantes en barra grandes · **cant. 5** | `C016` Pegante en barra<br>**A:** Pegante en barra de 15 g, surtido (`TK-REV-656600`) $4.900 × 5 = $24.500<br>**P:** Pegante en barra de 40 g PegaStic (`TK-C016-PRE`) $11.500 × 5 = $57.500 | Pide 5 pegantes en barra grandes; A cobra la barra de 15 g. P (PegaStic 40 g) cumple. Sustituto A: TK-REV-46388329283755 Offiesco 40 g ($5.050). |
| 8#25 | Tabla periódica Walter | `C025` Tabla periódica<br>**A:** Tabla periódica tamaño carta (`TK-REV-12881`) $1.800<br>**P:** Tabla Periodica Walter Grande (26x20cm) (`TK-C025-PRE`) $2.750 | Pide tabla periódica Walter (sin 'grande'); no hay atributo que filtrar y A cobra TK-REV-12881, genérica tamaño carta ($1.800). Sustituto: TK-C025-PRE Walter grande ($2.750); P cumple. |
| T#25 | Juego didáctico de lectura y escritura. Opciones: Rompecabezas, loterías, juegos ABC | `C054` Juego didáctico<br>**A:** Rompecabezas En Madera Animales 4 Piezas Grande (`TK-REV-45308083667115`) $13.600<br>**P:** Computador Didactico 6683 Niños Aprender Ordenador Educativo Ingles (`TK-REV-101941514`) $48.900 | Pide juego didáctico de lectura y escritura; A (rompecabezas de animales de 4 piezas) no es de lectoescritura. Sustituto: TK-REV-104951114 rompecabezas abecedario ($33.210). |
| 5#57 | espumas para lavar loza · **cant. 2** | `C097` Esponja<br>**A:** Paquete Esponja x2 Unds Arte (`TK-C097-ECO`) $7.700 × 2 = $15.400<br>**P:** Esponja Doble Uso Tip Top Vileda 3 Unidades (`TK-REV-105034099`) $8.000 × 2 = $16.000 | Pide esponja de loza; el Ahorrador no lo es. Sustituto: TK-REV-105034099 Vileda doble uso x3 ($8.000). |
| T#3, 1#16 | Xilófono de 8 placas con baquetas debidamente marcado | `C107` Xilófono<br>**A:** Xilófono Marimba Juguete Infantil Niños Bebe Musical Emoji (`TK-REV-103222545`) $23.800<br>**P:** Xilofono Infantil Marimba Alta Calidad Musical 8 Tonos Piano Gato (`TK-REV-104059521`) $41.999 | Pide xilófono de 8 placas; A es un juguete de bebé (Emoji). Sustituto: TK-REV-104872762 xilófono didáctico de 8 notas ($30.000); P cumple. |
| 7#40, 11#49 | Pluma para caligrafía con puntas intercambiables | `C116` Pluma<br>**A:** Pluma caligráfica Pilot de 6.0 mm, parallel pen (`TK-REV-613711`) $49.800<br>**P:** Set de pluma speedball para caligrafía (`TK-REV-683664`) $80.200 | Pide pluma con puntas intercambiables; A (Pilot Parallel 6,0 mm) es de una punta. P (Speedball TK-REV-683664) cumple. |
| J#72 | 10 hojas papel acuarela tamaño octavo | `C119` Papel acuarela<br>**A:** Papel acuarela blanco de 1/8 x 5 unidades, 300 g (`TK-REV-581780`) $10.000<br>**P:** Bloc argollado de papel acuarela de 20 hojas (`TK-REV-638487`) $59.900 | Pide 10 hojas de acuarela en octavo; A trae 5 (hacían falta 2 paquetes). |

### 6.3 Solo en el Premium (31 renglones)

El Ahorrador cumple.

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| J#73, T#70, 1#27, 2#55 | pincel de cerdas suaves redondo, Pelo Nylon Mango de Madera # 5 o # 6 | `C021` Pincel<br>**A:** Pincel Redondo Eterna #5 (`TK-REV-124275634`) $1.200<br>**P:** Pincel Pentel Aquash punta fina para acuarela (`TK-REV-517439`) $29.800 | Pide pincel redondo (de nylon y mango de madera en J#73); A cumple con el Eterna redondo #5, pero P cobra el pincel de agua Pentel Aquash ($29.800). Sustituto P: TK-REV-124275568 Eterna redondo #6 ($1.400). |
| T#41 | pincel Redondo | `C021` Pincel<br>**A:** Pincel Redondo Eterna #5 (`TK-REV-124275634`) $1.200<br>**P:** Pincel Pentel Aquash punta fina para acuarela (`TK-REV-517439`) $29.800 | Pide pincel redondo (de nylon y mango de madera en J#73); A cumple con el Eterna redondo #5, pero P cobra el pincel de agua Pentel Aquash ($29.800). Sustituto P: TK-REV-124275568 Eterna redondo #6 ($1.400). |
| 3#88 | Pinceles de punta redonda | `C021` Pincel<br>**A:** Pincel Redondo Eterna #5 (`TK-REV-124275634`) $1.200<br>**P:** Pincel Pentel Aquash punta fina para acuarela (`TK-REV-517439`) $29.800 | Pide pincel redondo (de nylon y mango de madera en J#73); A cumple con el Eterna redondo #5, pero P cobra el pincel de agua Pentel Aquash ($29.800). Sustituto P: TK-REV-124275568 Eterna redondo #6 ($1.400). |
| J#77, T#74 | Barra de plastilina grande de cualquier color | `C022` Plastilina<br>**A:** Paquete Plastilina Mi Trensito En Barra Largas X10 Colores Surtidos (`TK-REV-44702903402667`) $4.500<br>**P:** Plastilina en barra Norma x 12 uds. (`TK-C022-PRE`) $11.200 | Pide una barra grande de un color; A cobra el paquete Mi Trensito x10 ($4.500, más barato que una barra suelta) y P la caja Norma x12 ($11.200). Sustituto P: TK-C022-ECO Mi Trensito 250 g ($4.700). |
| 1#40, 2#74, 3#64, 4#62 | Bata para artes con mangas | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Pide bata de artes con mangas; P es de manga corta. A (bata blanca en tela) cumple. |
| 8#6, 10#5, 11#5 | Diccionario físico | `C034` Diccionario<br>**A:** Diccionario espanol ilustrado (`TK-LIB-9789589714188`) $16.000<br>**P:** Mini diccionario alemán - español (`TK-C034-PRE`) $49.000 | Pide diccionario físico (de español); A cumple (Nika ilustrado, $16.000), pero P cobra el 'Mini diccionario alemán-español' ($49.000). Sustituto P: TK-LIB-9786070400049 Larousse escolar plus ($49.000). |
| 9#4 | Diccionario físico cualquier edición | `C034` Diccionario<br>**A:** Diccionario espanol ilustrado (`TK-LIB-9789589714188`) $16.000<br>**P:** Mini diccionario alemán - español (`TK-C034-PRE`) $49.000 | Pide diccionario físico (de español); A cumple (Nika ilustrado, $16.000), pero P cobra el 'Mini diccionario alemán-español' ($49.000). Sustituto P: TK-LIB-9786070400049 Larousse escolar plus ($49.000). |
| T#37, 1#56, 2#34, 3#19, 4#18, 5#26 | paquete 100 notas adhesivas de 7,6 cm x 7,6 cm | `C045` Notas adhesivas<br>**A:** Notas adhesivas amarilla (`TK-C045-ECO`) $6.900<br>**P:** Notas adhesivas transparentes Post-it x 36 hojas (`TK-C045-PRE`) $21.200 | Pide 100 notas adhesivas de 7,6 cm; P son transparentes x36 hojas. |
| J#26 | juego Didáctico de mesa, se sugiere rompecabezas, lotería, parques, etc | `C054` Juego didáctico<br>**A:** Rompecabezas En Madera Animales 4 Piezas Grande (`TK-REV-45308083667115`) $13.600<br>**P:** Computador Didactico 6683 Niños Aprender Ordenador Educativo Ingles (`TK-REV-101941514`) $48.900 | Pide juego didáctico de mesa (rompecabezas, lotería, parqués); A (rompecabezas de madera) cumple, P cobra un computador didáctico. |
| 7#53, 9#51 | vaso pequeño de plástico | `C057` Vaso o plato<br>**A:** Paquete Vaso Plastico X12 Unds Among Us (`TK-REV-45126704693419`) $5.900<br>**P:** Vaso plástico de 700 ml con pitillo, multicolor (`TK-REV-712640`) $19.900 | Pide vaso pequeño de plástico; P cobra uno de 700 ml con pitillo ($19.900). A (paquete x12 Among Us, $5.900) sirve; sin personaje no hay vaso pequeño. El 'Among Us' tampoco tiene `personaje` etiquetado. |
| J#48 | paquete de pompones | `C089` Pompones<br>**A:** Mini Pompones De 4 Cm Colores Surtidos X 50 Unidades (`TK-C089-ECO`) $11.900<br>**P:** Set para pompones x 3 piezas We R Memory Keepers (`TK-C089-PRE`) $49.900 | Pide pompones; P cobra una herramienta para hacer pompones. Sustituto: TK-REV-105137073. |
| 7#42, 9#38, 10#58, 11#55 | Paleta mezcladora | `C117` Paleta de pintura<br>**A:** Paleta de fórmica tradicional (`TK-REV-87487`) $14.900<br>**P:** Set de herramientas de arte x 5 piezas, blanco (`TK-REV-627492`) $34.900 | Pide paleta mezcladora; A cumple (TK-REV-87487 fórmica Stylo, $14.900), pero P cobra un set de herramientas de arte x5 ($34.900). Sustituto P: TK-REV-712806 paleta para óleo con fórmica ($24.900). |
| 8#41 | Paleta mezcladora blanca | `C117` Paleta de pintura<br>**A:** Paleta de fórmica tradicional (`TK-REV-87487`) $14.900<br>**P:** Set de herramientas de arte x 5 piezas, blanco (`TK-REV-627492`) $34.900 | Pide paleta mezcladora; A cumple (TK-REV-87487 fórmica Stylo, $14.900), pero P cobra un set de herramientas de arte x5 ($34.900). Sustituto P: TK-REV-712806 paleta para óleo con fórmica ($24.900). |

## 7. D. No son huecos

### 7.1 🔴 Se cobran y no había que comprarlos en Tukit (24 renglones)

Lo que se trae o se arma en casa (el diccionario "disponible en casa", el libro de recortes), el cuaderno del año anterior, la misma bata de otro renglón, el delantal "según modelo", la lectura que elige el estudiante y los textos Gateway curados como C044. En Séptimo, tres de estos casos ya se corrigieron en la curaduría (3.6).

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| 2#77, 3#70, 5#69 | Cuaderno pequeño cosido cuadriculado de 50 hojas del año anterior. | `C001` Cuaderno<br>**A y P:** Cuaderno Cosido 50 Hojas Primavera Cuadros Disney Clasicos - Se envia un Motivo Aleatorio (`TK-REV-47580578087083`) $6.500 | El colegio pide reutilizar el cuaderno del año anterior: no hay que comprar. El sistema lo cobra. En 7#69 el mismo texto sí quedó `no_comprar` en la curaduría. |
| 6#54 | Cuaderno cuadriculado del año anterior | `C001` Cuaderno<br>**A:** Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Hombre (`TK-REV-2512282`) $7.150<br>**P:** Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) $7.150 | El colegio pide reutilizar el cuaderno del año anterior: no hay que comprar. El sistema lo cobra. En 7#69 el mismo texto sí quedó `no_comprar` en la curaduría. |
| 8#58, 9#61 | Cuaderno cuadriculado del año anterior | `C001` Cuaderno<br>**A y P:** Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) $7.150 | El colegio pide reutilizar el cuaderno del año anterior: no hay que comprar. El sistema lo cobra. En 7#69 el mismo texto sí quedó `no_comprar` en la curaduría. |
| 4#65 | Cuaderno pequeño cosido cuadriculado de 50 hojas del año anterior. · **cant. 50** | `C001` Cuaderno<br>**A y P:** Cuaderno Cosido 50 Hojas Primavera Cuadros Disney Clasicos - Se envia un Motivo Aleatorio (`TK-REV-47580578087083`) $6.500 × 50 = $325.000 | El colegio pide reutilizar el cuaderno del año anterior: no hay que comprar. Además la cantidad curada es 50 (las hojas), y el sistema cobra 50 cuadernos. |
| 6#27 | Bata de laboratorio de material antifluido (misma bata de biología) | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Es la misma bata del renglón anterior ('misma bata de biología' en 6#27, de 6#25; 'la misma de Química' en 10#32, de 10#29): no hay que comprar otra, y el kit cobra una segunda bata de tela ($20.800 A / $50.000 P). En Séptimo, el mismo texto (7#27) ya quedó `no_comprar` en la curaduría (commit c9b9ddb). |
| 10#32 | Bata de laboratorio de material antifluido, debidamente marcada (la misma de Química) | `C024` Bata de laboratorio<br>**A:** Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) $20.800<br>**P:** Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) $50.000 | Es la misma bata del renglón anterior ('misma bata de biología' en 6#27, de 6#25; 'la misma de Química' en 10#32, de 10#29): no hay que comprar otra, y el kit cobra una segunda bata de tela ($20.800 A / $50.000 P). En Séptimo, el mismo texto (7#27) ya quedó `no_comprar` en la curaduría (commit c9b9ddb). |
| 1#3, 2#8, 3#8, 4#8, 5#8 | Diccionario: El disponible en casa | `C034` Diccionario<br>**A:** Diccionario espanol ilustrado (`TK-LIB-9789589714188`) $16.000<br>**P:** Mini diccionario alemán - español (`TK-C034-PRE`) $49.000 | 'El disponible en casa': el colegio no pide comprar. El sistema cobra un diccionario (A Nika $16.000, P alemán-español $49.000). |
| 6#72 | Libro de inglés Gateway to the world a2 student's book | `C044` Libro<br>**A:** Nacho. Libro inicial de lectura (`TK-C044-ECO`) $14.500<br>**P:** Don Quijote De La Mancha Parte 1 (Novela gráfica) - Enlace Editorial, Tapa Blanda (72 pags) (`TK-REV-9789585594678`) $32.900 | Error de curaduría: texto Gateway (Macmillan) asignado a C044 Libro en vez de C134. No hay Gateway en el catálogo; como texto debía quedar 'Lo consigues por tu cuenta' (ADR 0027) y en cambio se cobra 'Nacho' (A) o 'Don Quijote' novela gráfica (P). |
| 9#91 | El libro de ingles Gateway to the world b2 student's book. Editorial Macmillan Education | `C044` Libro<br>**A:** Nacho. Libro inicial de lectura (`TK-C044-ECO`) $14.500<br>**P:** Don Quijote De La Mancha Parte 1 (Novela gráfica) - Enlace Editorial, Tapa Blanda (72 pags) (`TK-REV-9789585594678`) $32.900 | Error de curaduría: texto Gateway (Macmillan) asignado a C044 Libro en vez de C134. No hay Gateway en el catálogo; como texto debía quedar 'Lo consigues por tu cuenta' (ADR 0027) y en cambio se cobra 'Nacho' (A) o 'Don Quijote' novela gráfica (P). |
| 10#81 | Libro de inglés Gateway to the world b2+. Work book Editorial Macmillan Education | `C044` Libro<br>**A:** Nacho. Libro inicial de lectura (`TK-C044-ECO`) $14.500<br>**P:** Don Quijote De La Mancha Parte 1 (Novela gráfica) - Enlace Editorial, Tapa Blanda (72 pags) (`TK-REV-9789585594678`) $32.900 | Error de curaduría: texto Gateway (Macmillan) asignado a C044 Libro en vez de C134. No hay Gateway en el catálogo; como texto debía quedar 'Lo consigues por tu cuenta' (ADR 0027) y en cambio se cobra 'Nacho' (A) o 'Don Quijote' novela gráfica (P). |
| 8#10, 9#9, 11#9 | Libro de Lectura Libre Guiada | `C044` Libro<br>**A:** Nacho. Libro inicial de lectura (`TK-C044-ECO`) $14.500<br>**P:** Don Quijote De La Mancha Parte 1 (Novela gráfica) - Enlace Editorial, Tapa Blanda (72 pags) (`TK-REV-9789585594678`) $32.900 | Lectura libre guiada: el estudiante elige el libro con el docente; no hay título que comprar. El sistema cobra 'Nacho' (A) o 'Don Quijote' novela gráfica (P). En 7#9 la curaduría lo marcó `otro` y llega como 'Lo consigues por tu cuenta'. |
| 10#9 | Libro de Lectura Libre Guiada: El estudiante debe elegir un libro, teniendo en cuenta las pautas del docente (literatura y autores sugeridos) | `C044` Libro<br>**A:** Nacho. Libro inicial de lectura (`TK-C044-ECO`) $14.500<br>**P:** Don Quijote De La Mancha Parte 1 (Novela gráfica) - Enlace Editorial, Tapa Blanda (72 pags) (`TK-REV-9789585594678`) $32.900 | Lectura libre guiada: el estudiante elige el libro con el docente; no hay título que comprar. El sistema cobra 'Nacho' (A) o 'Don Quijote' novela gráfica (P). En 7#9 la curaduría lo marcó `otro` y llega como 'Lo consigues por tu cuenta'. |
| J#25, T#24 | libro de recortes | `C044` Libro<br>**A:** Nacho. Libro inicial de lectura (`TK-C044-ECO`) $14.500<br>**P:** Don Quijote De La Mancha Parte 1 (Novela gráfica) - Enlace Editorial, Tapa Blanda (72 pags) (`TK-REV-9789585594678`) $32.900 | 'Libro de recortes' (material que arma la familia en casa); el sistema cobra 'Nacho' (A) o 'Don Quijote' novela gráfica (P). |
| J#87 | Delantal de tela según modelo | `C049` Delantal<br>**A y P:** Delantal de Pintura Escolar Antifluido Niña Talla de 6 a 12 - Se envia un Motivo Aleatorio (`TK-REV-44922807910571`) $15.600 | Prenda 'según modelo' del colegio; el sistema cobra un delantal genérico. |

### 7.2 No se venden por diseño, pero el sistema los muestra como hueco (116 renglones)

Uniformes, licencias, lo que se trae de casa, lo que Tukit decidió no vender (tipo `otro`, ADR 0027) y renglones sin nada que comprar. Con el tipo del concepto (3.1) serían líneas informativas o "por su cuenta".

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| J#68 | Kit de aseo personal: muda de ropa para cambio | HUECO_CATALOGO (A y P) · `C067` Muda de ropa | Muda de ropa (C067, tipo `no_comprar`): la familia la envía de casa. Debía llegar como 'No hay que comprarlo' (linea.ts:31); la ruta rápida lo marca HUECO_CATALOGO. |
| J#92 | muda de ropa de cambio | HUECO_CATALOGO (A y P) · `C067` Muda de ropa | Muda de ropa (C067, tipo `no_comprar`): la familia la envía de casa. Debía llegar como 'No hay que comprarlo' (linea.ts:31); la ruta rápida lo marca HUECO_CATALOGO. |
| T#58 | muda completa de ropa: pantalón en material ligero, camisa manga larga, ropa interior y medias | HUECO_CATALOGO (A y P) · `C067` Muda de ropa | Muda de ropa (C067, tipo `no_comprar`): la familia la envía de casa. Debía llegar como 'No hay que comprarlo' (linea.ts:31); la ruta rápida lo marca HUECO_CATALOGO. |
| T#89 | Muda de ropa de cambio en caso de necesidad. | HUECO_CATALOGO (A y P) · `C067` Muda de ropa | Muda de ropa (C067, tipo `no_comprar`): la familia la envía de casa. Debía llegar como 'No hay que comprarlo' (linea.ts:31); la ruta rápida lo marca HUECO_CATALOGO. |
| 1#72 | Una muda de ropa de cambio en caso de necesidad | HUECO_CATALOGO (A y P) · `C067` Muda de ropa | Muda de ropa (C067, tipo `no_comprar`): la familia la envía de casa. Debía llegar como 'No hay que comprarlo' (linea.ts:31); la ruta rápida lo marca HUECO_CATALOGO. |
| 1#7, 2#14, 4#13, 5#14, 6#16, 7#15, 8#14, 9#15, 10#15 | Audífonos estilo diadema (headphones, no earbuds) con conector tipo auxiliar o usb | HUECO_CATALOGO (A y P) · `C110` Audífonos de diadema | Audífonos (C110, tipo `otro`): por diseño Tukit no los vende y la familia los consigue por su cuenta (ADR 0027; optimizador.py:79-83 los cita como ejemplo). Debía llegar como 'Lo consigues por tu cuenta' y la ruta rápida lo marca HUECO_CATALOGO. Si se decide venderlos, pasa a hueco real: no hay audífonos en el catálogo. |
| 3#13, 11#16 | Audifonos estilo diadema | HUECO_CATALOGO (A y P) · `C110` Audífonos de diadema | Audífonos (C110, tipo `otro`): por diseño Tukit no los vende y la familia los consigue por su cuenta (ADR 0027; optimizador.py:79-83 los cita como ejemplo). Debía llegar como 'Lo consigues por tu cuenta' y la ruta rápida lo marca HUECO_CATALOGO. Si se decide venderlos, pasa a hueco real: no hay audífonos en el catálogo. |
| 8#59 | Audífonos Convencionales de casco alámbricos jack 3.5 mm, recomendable cable largo y no de celular | HUECO_CATALOGO (A y P) · `C110` Audífonos de diadema | Audífonos (C110, tipo `otro`): por diseño Tukit no los vende y la familia los consigue por su cuenta (ADR 0027; optimizador.py:79-83 los cita como ejemplo). Debía llegar como 'Lo consigues por tu cuenta' y la ruta rápida lo marca HUECO_CATALOGO. Si se decide venderlos, pasa a hueco real: no hay audífonos en el catálogo. |
| 9#62 | Audífonos Convencionales de casco alámbricos jack 3.5mm, recomendable cable largo y no de celular. | HUECO_CATALOGO (A y P) · `C110` Audífonos de diadema | Audífonos (C110, tipo `otro`): por diseño Tukit no los vende y la familia los consigue por su cuenta (ADR 0027; optimizador.py:79-83 los cita como ejemplo). Debía llegar como 'Lo consigues por tu cuenta' y la ruta rápida lo marca HUECO_CATALOGO. Si se decide venderlos, pasa a hueco real: no hay audífonos en el catálogo. |
| J#65 | Baletas para Danzas o Gimnasia negras | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| J#86, T#85, 1#69, 2#87, 3#80, 4#76, 5#77, 5#78, 6#67, 7#93, 8#84, 9#87, 10#76, 11#73 | Uniforme de diario | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| J#88, T#86, 1#70, 2#88, 4#77, 5#79, 6#68, 7#94, 8#85, 9#88, 10#77, 11#74 | Uniforme para Educación Física | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| J#89, T#87, 4#78 | traje de baño | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| J#91, T#88, 1#71, 2#89, 3#87, 4#81, 5#84, 6#69, 7#95, 8#86, 9#89, 10#78, 11#80 | Uniforme de Gala | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| T#68 | Baletas para Danzas o Gimnasia negras (Que no sean de disfraz) marcadas. | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| 1#18 | Uniforme para las niñas: una falda rotonda y larga. Para los niños: un sombrero y una pañoleta para ensayo. | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| 3#81 | Uniforme para educación física · **cant. 2** | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| 3#82 | Traje de baño de una sola pieza | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| 3#85 | Pantaloneta de baño | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| 5#80, 11#75 | Traje de baño femenino | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| 5#83, 11#77 | Pantaloneta de baño masculino | HUECO_CATALOGO (A y P) · `C131` Uniforme | Uniforme o prenda (C131, tipo `uniforme`): no se vende en el catálogo. Debía llegar como 'Uniformes: fuera de Tukit por ahora' (linea.ts:33) y la ruta rápida lo marca HUECO_CATALOGO. |
| J#57, T#59 | títere correspondiente algún personaje (Persona), (animal) o rol. Ejemplo: Mujer, hombre, niño, niña bombero(a), enfermera(o), cocodrilo, tigre etc. | HUECO_CATALOGO (A y P) · `C132` Títere | Títere (C132, tipo `otro`): por diseño no se vende (ADR 0027; optimizador.py:79-83 lo cita como ejemplo). Debía llegar como 'Lo consigues por tu cuenta'. Tampoco hay títeres en el catálogo. |
| J#1, T#2 | Plan lector virtual RAZ- PLUS inglés y lengua castellana, administrada en Colombia por QUOVIX | HUECO_CATALOGO (A y P) · `C133` Plan lector virtual | Licencia digital RAZ-PLUS (C133, tipo `licencia_digital`): se paga a QUOVIX. Debía llegar como 'Se paga por fuera' (linea.ts:30) y se marca HUECO_CATALOGO. |
| 2#4, 3#4, 4#4, 5#4 | Comprensión lectora y Plan lector virtual Lengua Castellana RAZ- PLUS | HUECO_CATALOGO (A y P) · `C133` Plan lector virtual | Licencia digital RAZ-PLUS (C133, tipo `licencia_digital`): se paga a QUOVIX. Debía llegar como 'Se paga por fuera' (linea.ts:30) y se marca HUECO_CATALOGO. |
| 2#12, 4#11, 5#12, 7#13, 10#13 | Plan lector virtual Inglés RAZ- PLUS, administrada en Colombia por QUOVIX | HUECO_CATALOGO (A y P) · `C133` Plan lector virtual | Licencia digital RAZ-PLUS (C133, tipo `licencia_digital`): se paga a QUOVIX. Debía llegar como 'Se paga por fuera' (linea.ts:30) y se marca HUECO_CATALOGO. |
| 3#10, 8#15, 9#13, 11#12 | Plan lector virtual Ingles RAZ- PLUS | HUECO_CATALOGO (A y P) · `C133` Plan lector virtual | Licencia digital RAZ-PLUS (C133, tipo `licencia_digital`): se paga a QUOVIX. Debía llegar como 'Se paga por fuera' (linea.ts:30) y se marca HUECO_CATALOGO. |
| 6#13 | Plan lector virtual Inglés RAZ- PLUS, administrada en Colombia por QUOVIX. Link de pago: https://pagoslearning.com/ | HUECO_CATALOGO (A y P) · `C133` Plan lector virtual | Licencia digital RAZ-PLUS (C133, tipo `licencia_digital`): se paga a QUOVIX. Debía llegar como 'Se paga por fuera' (linea.ts:30) y se marca HUECO_CATALOGO. |
| 6#9 | PLAN LECTOR: Libro de Lectura Libre Guiada: El estudiante debe elegir un libro, teniendo en cuenta las pautas del docente (literatura y autores sugeridos) | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | Lectura libre guiada: el estudiante elige el libro; no hay título que comprar. |
| 6#70 | Libro de matemáticas | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | 'Libro de matemáticas' sin título ni editorial: no se puede surtir sin aclaración del colegio. |
| 1#2 | Cartilla Agustiniana (medio digital en la página del colegio, no se debe comprar) | HUECO_CATALOGO (A y P) · `C137` Lo entrega el colegio | Cartilla Agustiniana: material digital del colegio, que dice 'no se debe comprar'. C137 es tipo `no_comprar` y debía llegar como 'No hay que comprarlo' (linea.ts:31), como 7#27 y 7#69, que traen el tipo en el renglón; la ruta rápida lo marca HUECO_CATALOGO. |
| 2#2 | Cartilla Augustiniana | HUECO_CATALOGO (A y P) · `C137` Lo entrega el colegio | Cartilla Agustiniana: material digital del colegio, que dice 'no se debe comprar'. C137 es tipo `no_comprar` y debía llegar como 'No hay que comprarlo' (linea.ts:31), como 7#27 y 7#69, que traen el tipo en el renglón; la ruta rápida lo marca HUECO_CATALOGO. |
| 3#3, 5#3, 7#2, 8#3, 11#3 | Cartilla Agustiniana | HUECO_CATALOGO (A y P) · `C137` Lo entrega el colegio | Cartilla Agustiniana: material digital del colegio, que dice 'no se debe comprar'. C137 es tipo `no_comprar` y debía llegar como 'No hay que comprarlo' (linea.ts:31), como 7#27 y 7#69, que traen el tipo en el renglón; la ruta rápida lo marca HUECO_CATALOGO. |
| 4#3 | Cartilla Augustiniana (medio virtual en la pagina del colegio, no se debe comprar) | HUECO_CATALOGO (A y P) · `C137` Lo entrega el colegio | Cartilla Agustiniana: material digital del colegio, que dice 'no se debe comprar'. C137 es tipo `no_comprar` y debía llegar como 'No hay que comprarlo' (linea.ts:31), como 7#27 y 7#69, que traen el tipo en el renglón; la ruta rápida lo marca HUECO_CATALOGO. |
| 6#2, 10#3 | Cartilla Agustiniana (medio virtual en la página del colegio, no se debe comprar) | HUECO_CATALOGO (A y P) · `C137` Lo entrega el colegio | Cartilla Agustiniana: material digital del colegio, que dice 'no se debe comprar'. C137 es tipo `no_comprar` y debía llegar como 'No hay que comprarlo' (linea.ts:31), como 7#27 y 7#69, que traen el tipo en el renglón; la ruta rápida lo marca HUECO_CATALOGO. |
| 11#15 | Cartilla de Pruebas Saber | HUECO_CATALOGO (A y P) · `C137` Lo entrega el colegio | Cartilla de Pruebas Saber asignada a 'Lo entrega el colegio'. Hay que confirmar con el colegio; si se compra, es un hueco de texto. |
| 2#76, 4#64 | Para las niñas: una falda rotonda y larga. Para los niños: un sombrero y una pañoleta para ensayo. Los mismos del año anterior. | HUECO_CATALOGO (A y P) · `C139` Vestuario para presentaciones | Vestuario de presentación (falda rotonda, sombrero, pañoleta; en 2#76 y 4#64 'los mismos del año anterior'): prenda fuera del catálogo, igual que el uniforme. C139 es tipo `otro`. |
| 3#68 | falda de rotonda y larga | HUECO_CATALOGO (A y P) · `C139` Vestuario para presentaciones | Vestuario de presentación (falda rotonda, sombrero, pañoleta; en 2#76 y 4#64 'los mismos del año anterior'): prenda fuera del catálogo, igual que el uniforme. C139 es tipo `otro`. |
| 3#69, 5#68 | sombrero y pañoleta para ensayo | HUECO_CATALOGO (A y P) · `C139` Vestuario para presentaciones | Vestuario de presentación (falda rotonda, sombrero, pañoleta; en 2#76 y 4#64 'los mismos del año anterior'): prenda fuera del catálogo, igual que el uniforme. C139 es tipo `otro`. |
| 5#67 | falda rotonda y larga | HUECO_CATALOGO (A y P) · `C139` Vestuario para presentaciones | Vestuario de presentación (falda rotonda, sombrero, pañoleta; en 2#76 y 4#64 'los mismos del año anterior'): prenda fuera del catálogo, igual que el uniforme. C139 es tipo `otro`. |
| 3#72 | buzzer | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Componente electrónico especializado (C142, tipo `otro`: por diseño no se vende, ADR 0027). Debía llegar como 'Lo consigues por tu cuenta'. Ninguno de estos (buzzer, broche de 9 V, pulsadores, sensores PIR/HC-SR04/IR, relé, joystick) está en el catálogo, aunque C071 sí vende otros componentes (L298N, sensor MQ135): conviene decidir si C142 se vende. |
| 6#45, 7#71 | Broche de batería de 9V | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Componente electrónico especializado (C142, tipo `otro`: por diseño no se vende, ADR 0027). Debía llegar como 'Lo consigues por tu cuenta'. Ninguno de estos (buzzer, broche de 9 V, pulsadores, sensores PIR/HC-SR04/IR, relé, joystick) está en el catálogo, aunque C071 sí vende otros componentes (L298N, sensor MQ135): conviene decidir si C142 se vende. |
| 7#78 | pulsadores de 4 pines · **cant. 4** | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Componente electrónico especializado (C142, tipo `otro`: por diseño no se vende, ADR 0027). Debía llegar como 'Lo consigues por tu cuenta'. Ninguno de estos (buzzer, broche de 9 V, pulsadores, sensores PIR/HC-SR04/IR, relé, joystick) está en el catálogo, aunque C071 sí vende otros componentes (L298N, sensor MQ135): conviene decidir si C142 se vende. |
| 8#67 | Sensor de movimiento PIR HCSR501 | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Componente electrónico especializado (C142, tipo `otro`: por diseño no se vende, ADR 0027). Debía llegar como 'Lo consigues por tu cuenta'. Ninguno de estos (buzzer, broche de 9 V, pulsadores, sensores PIR/HC-SR04/IR, relé, joystick) está en el catálogo, aunque C071 sí vende otros componentes (L298N, sensor MQ135): conviene decidir si C142 se vende. |
| 8#68 | 1 sensor de proximidad HCSR04 | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Componente electrónico especializado (C142, tipo `otro`: por diseño no se vende, ADR 0027). Debía llegar como 'Lo consigues por tu cuenta'. Ninguno de estos (buzzer, broche de 9 V, pulsadores, sensores PIR/HC-SR04/IR, relé, joystick) está en el catálogo, aunque C071 sí vende otros componentes (L298N, sensor MQ135): conviene decidir si C142 se vende. |
| 8#69 | 1 sensor de proximidad IR | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Componente electrónico especializado (C142, tipo `otro`: por diseño no se vende, ADR 0027). Debía llegar como 'Lo consigues por tu cuenta'. Ninguno de estos (buzzer, broche de 9 V, pulsadores, sensores PIR/HC-SR04/IR, relé, joystick) está en el catálogo, aunque C071 sí vende otros componentes (L298N, sensor MQ135): conviene decidir si C142 se vende. |
| 9#71 | módulo RELAY de 1 canal 5V | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Componente electrónico especializado (C142, tipo `otro`: por diseño no se vende, ADR 0027). Debía llegar como 'Lo consigues por tu cuenta'. Ninguno de estos (buzzer, broche de 9 V, pulsadores, sensores PIR/HC-SR04/IR, relé, joystick) está en el catálogo, aunque C071 sí vende otros componentes (L298N, sensor MQ135): conviene decidir si C142 se vende. |
| 9#73 | joystick Analógico para Arduino (KY-023) · **cant. 2** | HUECO_CATALOGO (A y P) · `C142` Componente electrónico especializado | Componente electrónico especializado (C142, tipo `otro`: por diseño no se vende, ADR 0027). Debía llegar como 'Lo consigues por tu cuenta'. Ninguno de estos (buzzer, broche de 9 V, pulsadores, sensores PIR/HC-SR04/IR, relé, joystick) está en el catálogo, aunque C071 sí vende otros componentes (L298N, sensor MQ135): conviene decidir si C142 se vende. |

### 7.3 Textos con título que el catálogo no tiene (64 renglones)

Por diseño, un texto con título sin producto resuelto es "Lo consigues por tu cuenta" (ADR 0027; `libs/ts/tukit-contrato/src/linea.ts:41`): la edición la vende una librería. No son huecos del catálogo de útiles, aunque sí de la lista de compra si Tukit decide surtir textos. La ruta rápida los marca HUECO_CATALOGO porque pierde el tipo `texto` (3.1). Todos son del concepto C134, que no tiene productos. Se buscaron uno por uno por título, autor e ISBN en los nombres y en las URLs de origen, también en C044, y ninguno está.

| Grado y Renglón | Pide el colegio | Propuesta del sistema | Análisis/Sustituto en catálogo |
| --- | --- | --- | --- |
| T#1 | Entre amigos C Lenguaje (Cuaderno letra Script, editorial Norma) | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 2#5 | Yo soy yo. (Incluye cuaderno de actividades).Gabriela Peyron. Editorial Norma | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 2#6 | Bobot (incluye cartilla de actividades). Cecilia Eudave. Editorial Castillo | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 2#7 | Antología de cuentos para leer. Jorge A. Jiménez R. Editorial Palbooks | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 3#5 | Libro de plan lector: La familia mas rica del mundo, Editorial Enlace | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 3#6 | Libro de plan lector: El pais mas hermoso del mundo. Editorial Norma | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 3#7 | Libro de plan lector: Detective Equis. Antonia Sanin. Ediciones Castillo | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 3#32 | Alpha Mathematics On-Level Practice Book. 3 | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 4#5 | Un regalo inesperado, Maria Garcia Esperon. Editorial Enlace. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 4#6 | De donde vienen los perros?, Francisco Leal Quevedo. Editorial Panamericana. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 4#7 | De Taquito antologia de cuentos futboleros, Diego F. Barros. Editorial Planeta. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 4#30 | Competencias y habilidades del siglo XXI.4. Editorial Libros y Libros | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 5#5 | La llave de las estrellas, Malena Salazar Murcia. Editorial Enlace | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 5#6 | La teoría de los colibríes, Michelle Kadarusman. Editorial Norma | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 5#7 | La palabra más hermosa, Jordi Sierra i Fabra. Editorial Algar | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 5#39 | Competencias y habilidades del siglo XXI.5. Editorial Libros y Libros | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 6#4, 7#4, 9#3, 10#4, 11#4 | Lectura Multidimensional Método 84H | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 6#6 | PLAN LECTOR: Danny, el campeón del mundo. Roald Dahl. Editorial Loqueleo | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 6#7 | PLAN LECTOR: El pan de la guerra. Editorial. Deborah Ellis. Ediciones Castillo | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 6#8 | PLAN LECTOR: Mi hermano el genio. Rodrigo Muñoz Avia. Editorial Edebé | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 6#11 | GATEWAY TO THE WORLD A2 STUDENT'S BOOK. Editorial Macmillan Education | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 6#17 | Competencias y habilidades del siglo XXI.6. Editorial Libros y Libros | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 6#23, 7#22 | Mader.Sylvia S. Windelspecht Michael. Biology. fourteenth edition. Ed. Mc Graw Hill Education | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 6#71, 9#90 | Texto Mader.Sylvia S. Windelspecht Michael. Biology. Thirteenth edition. Ed. Mc Graw Hill Education | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 7#6 | Los secretos de Hafiz Mustafá - Francisco Leal Quevedo. Editorial Norma. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 7#7 | Sherlock, Lupin y yo. Último acto en el teatro de la Ópera. Irene Adler. Editorial Planeta. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 7#8 | Valeria. En el reino de Malagana. Albeiro Echeverria. Editorial Panamericana. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 7#11, 8#11 | GATEWAY TO THE WORLD B1 STUDENT'S BOOK. Editorial Macmillan Education. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 7#16 | Competencias y habilidades del siglo XXI.7. Editorial Libros y Libros. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 7#96 | El libro de inglés Gateway to the world b1 student's book student's book Editorial Macmillan Education | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 8#5 | Lectura Multidimensional Método 84H - Grado Octavo | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 8#9 | Te amo, peladita. Albeiro Echavarría. Editorial Norma | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 8#16 | Matemáticas Jenga 8. Ediciones Milenio S.A.S. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 8#20, 9#20 | Mader.Sylvia S. Windelspecht Michael. Biology. Thirteenth edition. Ed. Mc Graw Hill Education | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 8#23, 9#23, 10#26, 11#23 | Química general, orgánica y biológica. Estructuras de la vida. Karen C. Timberlake. Cuarta edición. Editorial Pearson | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 8#27, 9#24, 10#23, 11#20 | Física. Wilson, Buffa, Lou. Sexta edición. Editorial Pearson | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 9#5 | Las claves de la Argumentación. Anthony Weston. Ed. Planeta Lector | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 9#6 | La noche en que Frankenstein leyó el Quijote. Santiago Posteguillo. Editorial Planeta | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 9#7 | Montes de María. Daniel Ángel. Editorial Algar | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 9#8 | Cien años de soledad. Autor Gabriel García Márquez, Cualquier edición | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 9#11 | GATEWAY TO THE WORLD B2 STUDENT'S BOOK. Editorial Macmillan Education | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 10#6 | Meditaciones Gato Aurelio- Editorial planeta | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 10#7 | Humanos Púrpura - Fredy Pedraza Cuevas - Novela Autopublicada | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 10#8 | En los pliegues del aire - Daniel Hernández Chambers - Editorial Algar | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 10#11 | GATEWAY TO THE WORLD B2+. WORKBOOK. Editorial Macmillan Education | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 10#79, 11#81 | Texto Fundamentos de Física Ruelas Arturo. Velásquez Juan Carlos. Segunda edición. Editorial Mc Graw Hill | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 10#80, 11#82 | Texto Fundamentos de Quimica Hein Morris. Arena Susan. Willard Cary. Decimoquinta edición. Editorial Cengage | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |
| 11#8 | Gabriel García Márquez, un genio de muchos rostros. Orlando Oliveros. Editorial Algar. | HUECO_CATALOGO (A y P) · `C134` Libro o texto con título | No está en el catálogo (buscado por título, autor e ISBN en nombres y URLs de origen). Oportunidad de surtido. |

## 8. Qué cambió frente a la auditoría sobre `a565aeb`

Entre `a565aeb` y `d4ea7cb` hay 24 commits. Los que tocan la resolución, el armado, el catálogo o la curaduría son:

- `e3c13e5` y `a50c334`: atributos del catálogo y del extractor.
- `d868d8f`: datos del catálogo (la caja matemática y los embeddings).
- `2be642d`: el filtro por renglón (3.2).
- `c9b9ddb` y `00875ff`: la curaduría de Séptimo y `4#53` (3.6).
- `642a53d`: juntar herramientas (3.5).
- `57dccb1`, `75856b9`, `9414819` y `3fa7173`: precios nulos, repetidos, avisos y regeneración de canónicos.

|  | a565aeb | d4ea7cb | Diferencia |
| --- | ---: | ---: | ---: |
| RESUELTO_AUTO (A y P) | 852 | 707 | -145 |
| HUECO_CATALOGO (A y P) | 240 | 385 | +145 |
| SIN_MATCH (A y P) | 0 | 0 | +0 |
| Líneas informativas | 0 | 3 | +3 |
| Suma de los 13 kits Ahorrador | $13.864.663 | $9.857.452 | −$4.007.211 |
| Suma de los 13 kits Premium | $32.031.940 | $17.602.526 | −$14.429.414 |

| Categoría | a565aeb | d4ea7cb | Diferencia |
| --- | ---: | ---: | ---: |
| **A🔴** | 160 | 67 | -93 |
| **A** | 52 | 148 | +96 |
| **B** | 8 | 57 | +49 |
| **C** | 279 | 97 | -182 |
| **C(A)** | 67 | 23 | -44 |
| **C(P)** | 59 | 31 | -28 |
| **D🔴** | 24 | 24 | +0 |
| **D** | 180 | 180 | +0 |
| **OK** | 263 | 465 | +202 |
| **Total** | 1092 | 1092 |  |

**De dónde viene cada renglón.** Filas: categoría en la auditoría anterior. Columnas: categoría ahora.

| antes \ ahora | A🔴 | A | B | C | C(A) | C(P) | D🔴 | D | OK | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **A🔴** | 64 | 93 | · | · | · | · | 2 | · | 1 | 160 |
| **A** | · | 52 | · | · | · | · | · | · | · | 52 |
| **B** | · | · | 8 | · | · | · | · | · | · | 8 |
| **C** | 2 | 3 | 29 | 94 | · | 11 | · | · | 140 | 279 |
| **C(A)** | · | · | 16 | 1 | 15 | · | · | · | 35 | 67 |
| **C(P)** | 1 | · | 1 | · | · | 16 | · | · | 41 | 59 |
| **D🔴** | · | · | · | · | · | · | 22 | · | 2 | 24 |
| **D** | · | · | · | · | · | · | · | 180 | · | 180 |
| **OK** | · | · | 3 | 2 | 8 | 4 | · | · | 246 | 263 |
| **Total** | 67 | 148 | 57 | 97 | 23 | 31 | 24 | 180 | 465 | 1092 |

- 575 renglones salen distinto; 393 de ellos cambiaron de categoría. **219** pasaron a cumplir. **17** que cumplían dejaron de cumplir:
  - 3 (`3#12`, `3#52` y `4#32`): falsos huecos nuevos del filtro (3.2 a).
  - 8 (`J#13`, `T#14`, `3#62`, `7#87`, `8#77`, `9#81`, `10#70` y `11#67`): cajas de marcadores que ahora se cobran como un marcador suelto (3.2 d).
  - 1 (`1#20`): la cantidad mal curada de `1#65` se junta en esta línea (3.5).
  - 5: un perfil pasó a un producto que no cumple: pegante de 15 g (`J#16`), plastilina en paquete (`J#77`, `T#74`) y vaso de 700 ml (`7#53`, `9#51`).
- Los cobros por productos que no cumplen bajaron: A🔴 + C + D🔴 pasan de 589 a 242 renglones.
- **Corrección de la auditoría anterior, sin cambio del sistema:** `6#27` y `10#32` estaban en A🔴 ("no hay bata antifluido"). En realidad piden "la misma bata" del renglón anterior (`6#25`, `10#29`): no hay que comprar otra y el kit cobra una segunda ($41.600 A / $100.000 P). Ahora son D🔴, como el mismo texto de Séptimo (`7#27`), que la curaduría ya marcó `no_comprar`.
- **Frente a la auditoría de Séptimo del repositorio** ("Después del arreglo": 59 líneas con producto, 2 informativas, 34 huecos). Aquí Séptimo tiene 57 con producto, 3 informativas y 35 huecos. Las diferencias son `7#9`, que `00875ff` volvió informativa después de esa auditoría, y `7#1`, la Biblia, que aquí es hueco (3.2 a). Los totales de esa auditoría ($796.889 A / $1.368.377 P) no se pueden reconciliar con estos ($1.022.326 / $1.584.597): se calcularon en otra rama y sobre otra base.

## Anexo 1. Sobrecobros por empaque y cantidad

Renglones con la bandera de empaque o cantidad. También aparecen, con su análisis, en la tabla de su categoría.

| Grado y Renglón | Cat. | Pide el colegio | Ahorrador compra | Premium compra |
| --- | --- | --- | --- | --- |
| 4#65 | `D🔴` | Cuaderno pequeño cosido cuadriculado de 50 hojas del año anterior. · **cant. 50** | Cuaderno Cosido 50 Hojas Primavera Cuadros Disney Clasicos - Se envia un Motivo Aleatorio (`TK-REV-47580578087083`) $6.500 × 50 = $325.000 | Cuaderno Cosido 50 Hojas Primavera Cuadros Disney Clasicos - Se envia un Motivo Aleatorio (`TK-REV-47580578087083`) $6.500 × 50 = $325.000 |
| J#59 | `C` | lápices negros gruesos · **cant. 2** | Lápiz Negro HB Eterna (`TK-C002-CON`) $6.500 × 2 = $13.000 | Lapiz primavera negro x 12 PRIMAVERA (`TK-REV-3331469`) $6.900 × 2 = $13.800 |
| 1#20 | `C(A)` | Caja de colores | Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) $6.100 × 12 = $73.200 | COLORES TRIANGULAR X 24 ECO FABER CASTELL (`TK-C004-PRE`) $32.200 |
| 1#65 | `C` | colores delgados X12 · **cant. 12** | Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) $6.100 × 0 = $0 | Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) $6.100 × 12 = $73.200 |
| J#95 | `C` | marcadores borrables para tablero 1 delgado · **cant. 2** | Paquete Marcador Kores Borrable X4 Unds Punta Delgada Surtido (`TK-REV-47122444714155`) $9.350 × 2 = $18.700 | Paquete Marcador Kores Borrable X4 Unds Punta Delgada Surtido (`TK-REV-47122444714155`) $9.350 × 2 = $18.700 |
| 6#40 | `C` | 4 octavos de cartulina negra · **cant. 4** | Cartulina Negra 1/8 Manualidades Escolar X10 Negro (`TK-REV-104886189`) $8.500 × 4 = $34.000 | Cartulina Negra 1/8 Manualidades Escolar X10 Negro (`TK-REV-104886189`) $8.500 × 4 = $34.000 |
| 1#54, 2#32 | `B` | frascos de vinilos colores primarios 120 ml · **cant. 3** | HUECO | HUECO |
| J#93 | `C` | barras largas de silicona · **cant. 2** | Barra Silicona Transparente Delgada X 10 Unidades (`TK-C028-ECO`) $10.400 × 2 = $20.800 | Docena Barra Silicona Gruesa (`TK-C028-PRE`) $16.250 × 2 = $32.500 |
| J#94 | `C` | barras delgadas de silicona · **cant. 2** | Barra Silicona Transparente Delgada X 10 Unidades (`TK-C028-ECO`) $10.400 × 2 = $20.800 | Barra Silicona Transparente Delgada X 10 Unidades (`TK-C028-ECO`) $10.400 × 2 = $20.800 |
| T#78 | `C` | Acetatos tamaño carta. · **cant. 2** | Acetato De Laminacion Carta Calibre 10 X 10 Unidades (`TK-REV-104236147`) $25.000 × 2 = $50.000 | Acetato De Laminacion Carta Calibre 10 X 10 Unidades (`TK-REV-104236147`) $25.000 × 2 = $50.000 |
| J#45 | `A🔴` | palos de pincho largos · **cant. 5** | Palo De Balso Cuadrado 5 X 5 Mm X 90 Cm 10 Unidades (`TK-C033-ECO`) $11.400 × 5 = $57.000 | Palos De Madera Para Paleta Color Natural X 500 Unidades (`TK-REV-105198377`) $23.900 × 5 = $119.500 |
| T#43 | `A🔴` | palos de pincho largos · **cant. 2** | Palo De Balso Cuadrado 5 X 5 Mm X 90 Cm 10 Unidades (`TK-C033-ECO`) $11.400 × 2 = $22.800 | Palos De Madera Para Paleta Color Natural X 500 Unidades (`TK-REV-105198377`) $23.900 × 2 = $47.800 |
| 7#63 | `C` | octavos de cartón paja · **cant. 4** | Cartón paja color crema por 10 uds. (`TK-C041-CON`) $10.200 × 4 = $40.800 | Paquete Carton Paja Octavos x10 Unds Colores (`TK-C041-PRE`) $11.750 × 4 = $47.000 |
| 7#68 | `C` | octavos de cartón paja de colores · **cant. 4** | Paquete Carton Paja Octavos x10 Unds Colores (`TK-C041-PRE`) $11.750 × 4 = $47.000 | Paquete Carton Paja Octavos x10 Unds Colores (`TK-C041-PRE`) $11.750 × 4 = $47.000 |
| T#49 | `C` | tubos de escarcha (colores variados) · **cant. 3** | Escarcha Brillantina En Tubo X 12 Unidades Para Manualidades (`TK-C052-ECO`) $8.000 × 3 = $24.000 | Paquete Escarcha En Libra Azul (`TK-C052-CON`) $14.150 × 3 = $42.450 |
| 2#52 | `C` | fichas bibliográficas (blancas) · **cant. 10** | Paquete Ficha Bibliografica X50 Unds Azul (`TK-C078-ECO`) $2.950 × 10 = $29.500 | Fichas Bibliográficas Cartulina X 100 Unidades Colores: Blanco, Amarillo, Azul, Rosado (Según Disponibilidad) (`TK-REV-104986188`) $8.000 × 10 = $80.000 |
| 7#57 | `C` | hojas papel durex tamaño 1/8 · **cant. 10** | Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 | Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 |
| 8#56 | `C` | 10 hojas de papel durex tamaño octavo · **cant. 10** | Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 | Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 |
| 9#58 | `C` | hojas Durex tamaño octavo · **cant. 10** | Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 | Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 |
| 10#62, 11#59 | `C` | hojas de papel dure 180 grms · **cant. 10** | Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 | Paquete Papel Durex En Octavos De 180 Gramos X20 Hojas (`TK-REV-44702903468203`) $13.500 × 10 = $135.000 |
| 8#55 | `C` | 6 hojas Papel acuarela tamaño octavo · **cant. 6** | Papel acuarela blanco de 1/8 x 5 unidades, 300 g (`TK-REV-581780`) $10.000 × 6 = $60.000 | Bloc argollado de papel acuarela de 20 hojas (`TK-REV-638487`) $59.900 × 6 = $359.400 |
| 9#59 | `C` | hojas de papel acuarela · **cant. 10** | Papel acuarela blanco de 1/8 x 5 unidades, 300 g (`TK-REV-581780`) $10.000 × 10 = $100.000 | Bloc argollado de papel acuarela de 20 hojas (`TK-REV-638487`) $59.900 × 10 = $599.000 |
| 4#56 | `C` | 2 hojas de papel pergamino · **cant. 2** | Bloc de papel pergamino, 25 hojas de 1/8 (`TK-REV-97606`) $15.500 × 2 = $31.000 | Bloc de papel pergamino para dibujo de 1/8, 50 hojas (`TK-REV-116389`) $30.600 × 2 = $61.200 |
| 7#56, 9#60 | `C` | octavos de papel pergamino · **cant. 10** | Bloc de papel pergamino, 25 hojas de 1/8 (`TK-REV-97606`) $15.500 × 10 = $155.000 | Bloc de papel pergamino para dibujo de 1/8, 50 hojas (`TK-REV-116389`) $30.600 × 10 = $306.000 |
| 8#57 | `C` | 10 hojas de papel pergamino · **cant. 10** | Bloc de papel pergamino, 25 hojas de 1/8 (`TK-REV-97606`) $15.500 × 10 = $155.000 | Bloc de papel pergamino para dibujo de 1/8, 50 hojas (`TK-REV-116389`) $30.600 × 10 = $306.000 |
| J#39, J#83, T#82, 1#36, 2#64 | `C` | pliegos de papel Kraft café · **cant. 2** | Papel Kraft Mano Pliego X 25 Unidades (`TK-REV-105198360`) $11.900 × 2 = $23.800 | Papel Kraft Mano Pliego X 25 Unidades (`TK-REV-105198360`) $11.900 × 2 = $23.800 |
| T#38 | `C` | pliegos de papel Kraft café · **cant. 3** | Papel Kraft Mano Pliego X 25 Unidades (`TK-REV-105198360`) $11.900 × 3 = $35.700 | Papel Kraft Mano Pliego X 25 Unidades (`TK-REV-105198360`) $11.900 × 3 = $35.700 |
| J#32 | `C` | pliegos de papel crepe colores surtidos · **cant. 2** | Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 | Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 |
| J#84, T#83, 1#37, 1#53, 2#31, 2#65 | `C` | pliegos de papel crepe · **cant. 2** | Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 | Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 |
| T#29 | `C` | pliegos de papel crepe colores surti · **cant. 2** | Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 | Paquete Papel Crepe X10 Pliegos Lila (`TK-C127-PRE`) $7.850 × 2 = $15.700 |
| J#31 | `C` | pliegos de papel seda colores surtidos · **cant. 2** | Rollo Papel Seda Naranja X25 Medios De Pliego (`TK-REV-44702889902251`) $5.500 × 2 = $11.000 | Rollo Papel Seda Naranja X25 Medios De Pliego (`TK-REV-44702889902251`) $5.500 × 2 = $11.000 |
| T#28 | `C` | pliegos de papel seda colores surtido · **cant. 3** | Rollo Papel Seda Naranja X25 Medios De Pliego (`TK-REV-44702889902251`) $5.500 × 3 = $16.500 | Rollo Papel Seda Naranja X25 Medios De Pliego (`TK-REV-44702889902251`) $5.500 × 3 = $16.500 |

Cobrado en estos 44 renglones: $2.415.400 en el Ahorrador y $3.904.350 en el Premium.

## Anexo 2. Renglones que cumplen

Los 465 renglones donde los dos perfiles cobran un producto que cumple, o la línea llega como debe, agrupados por concepto. **K**: producto de personaje como último recurso (3.3).

| Concepto | Grado y Renglón | Ahorrador | Premium |  |
| --- | --- | --- | --- | --- |
| `C001` Cuaderno | J#2 | Cuaderno Frozen Mediano Rayado 100 hojas Cosido FROZEN (`TK-C001-ECO-FROZEN`) | Cuaderno Bluey Mediano Rayado 100 hojas Cosido NORMA (`TK-C001-CON-BLUEY`) | K |
| `C001` Cuaderno | J#4, T#4, 1#4, 1#6, 1#13, 2#3, 2#9, 3#11 | Cuaderno Cosido Primavera 100 Hojas Mi Primer Cuaderno C Motivo Niña Rengloncitos (Ferrocarril) (`TK-REV-47518218715307`) | Cuaderno Cosido Primavera 100 Hojas Mi Primer Cuaderno C Motivo Niña Rengloncitos (Ferrocarril) (`TK-REV-47518218715307`) |  |
| `C001` Cuaderno | T#5, T#6, 1#8, 1#12, 2#13, 2#17, 3#2, 3#9, 3#33, 3#40, 3#42, 4#2, 4#9, 4#12, 4#31, 4#40, 5#2, 5#9, 5#13, 5#40, 5#48, 6#3, 6#18, 6#28, 7#3, 7#10, 7#17, 8#2, 8#4, 8#12, 9#2, 9#14, 10#2, 10#14, 11#2, 11#13 | Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) | Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) |  |
| `C001` Cuaderno | 1#19, 2#45, 3#43, 4#41, 5#49, 6#29, 7#29, 8#30, 9#29, 10#36, 11#32 | Cuaderno Cosido 50 Hojas Primavera Cuadros Disney Clasicos - Se envia un Motivo Aleatorio (`TK-REV-47580578087083`) | Cuaderno Cosido 50 Hojas Primavera Cuadros Disney Clasicos - Se envia un Motivo Aleatorio (`TK-REV-47580578087083`) | K |
| `C001` Cuaderno | 2#22, 2#23 | Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) | Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Hombre (`TK-REV-2512282`) |  |
| `C001` Cuaderno | 4#37, 6#10, 9#10 | Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Hombre (`TK-REV-2512282`) | Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) |  |
| `C001` Cuaderno | 5#46, 6#24, 6#26, 7#14, 7#23, 7#25, 7#28, 8#21, 8#24, 8#29, 9#21, 9#25, 9#28, 10#31, 10#33, 10#34, 10#35, 11#28, 11#29, 11#30, 11#31 | Cuaderno Stitch 100 Hojas (`TK-C001-CON-STITCH`) | Cuaderno Stitch 100 Hojas (`TK-C001-CON-STITCH`) | K |
| `C001` Cuaderno | 6#14 | Cuaderno Cosido 100 Hojas Scribe Master Cuadros Hombre (`TK-REV-2512284`) | Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Mujer (`TK-REV-2512281`) |  |
| `C001` Cuaderno | 7#69 | Informativa (`no_comprar`) | Informativa (`no_comprar`) |  |
| `C002` Lápiz | T#61, 1#60, 2#38, 3#23, 4#21, 5#30, 6#58, 7#83, 8#73, 9#77, 10#66, 11#63 | Lápiz Negro HB Eterna (`TK-C002-CON`) | Lapiz primavera negro x 12 PRIMAVERA (`TK-REV-3331469`) |  |
| `C003` Block | 1#10, 2#21, 2#25, 3#15, 3#39, 4#16, 4#36, 5#17, 5#44, 6#22, 7#18, 8#18, 9#18 | Block Cuadriculado Tamaño Carta JEAN BOOK (`TK-REV-1659569`) | Block Cuadriculado Tamaño Carta JEAN BOOK (`TK-REV-1659569`) |  |
| `C004` Colores | T#65, 2#42, 3#27, 4#25, 5#34 | Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) | Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) |  |
| `C004` Colores | 2#48, 3#48, 4#53, 5#60, 6#39, 6#61, 7#58, 7#86, 8#51, 8#76, 9#49, 9#80, 10#54, 10#69, 11#52, 11#66 | Caja Lapices De Colores Norma Imagenes 3mm X12 Unds Unipunta (`TK-REV-47726016594091`) | COLORES TRIANGULAR X 24 ECO FABER CASTELL (`TK-C004-PRE`) |  |
| `C005` Borrador | J#63, 6#59, 7#84, 8#74, 9#78, 10#67, 11#64 | Set Borrador X3 Negro Eterna (`TK-C005-ECO`) | Borradores de nata Silver X 2 MILAN (`TK-C005-PRE`) |  |
| `C005` Borrador | T#63, 1#62, 2#40, 3#25, 4#23, 5#32 | Borradores de nata Silver X 2 MILAN (`TK-C005-PRE`) | Borradores de nata Silver X 2 MILAN (`TK-C005-PRE`) |  |
| `C006` Marcador | T#15, 1#58, 2#20, 2#37, 3#21, 4#20, 5#28 | MARCADOR BORRABLE NEGRO FABER CASTELL (`TK-REV-133274`) | MARCADOR BORRABLE NEGRO FABER CASTELL (`TK-REV-133274`) |  |
| `C006` Marcador | 4#57, 5#63, 10#55, 11#53 | Marcador Sharpie Punta Fina Negro (`TK-REV-44702916313259`) | Marcador Sharpie Punta Fina Negro (`TK-REV-44702916313259`) |  |
| `C007` Tajalápiz | J#64 | Tajalapiz Sleeve Colores Surti FABER CASTELL (`TK-REV-953885`) | Tajalapiz Sleeve Colores Surti FABER CASTELL (`TK-REV-953885`) |  |
| `C007` Tajalápiz | 1#63, 6#60, 7#85, 8#75, 9#79, 10#68, 11#65 | Sacapuntas Y Borrador Redondo TW EVANS (`TK-C007-ECO`) | Sacapuntas Faber Castell Con Deposito Set X 3 Unidades (`TK-C007-PRE`) |  |
| `C008` Regla | 1#9, 2#18, 2#49, 3#34, 3#63, 4#33, 5#41, 6#62, 6#74, 7#21, 7#88, 8#78, 9#82, 9#93, 10#22, 10#71, 11#68 | Regla De 30Cm FINLANDEK (`TK-REV-3318633`) | Regla Kores Elastick 30 Cm Color Verde (`TK-C008-PRE`) |  |
| `C009` Cartuchera | J#58, T#60, 1#59, 3#22, 5#29, 6#55, 7#80, 8#70, 9#74, 10#63, 11#60 | Cartuchera Tigger Plegable (`TK-REV-124388164`) | Cartuchera Multiuso Marañón Negra (`TK-C009-PRE`) |  |
| `C010` Cartulina | J#33, T#30, 5#64 | Cartulina Negra 1/8 Manualidades Escolar X10 Negro (`TK-REV-104886189`) | Cartulina Negra 1/8 Manualidades Escolar X10 Negro (`TK-REV-104886189`) |  |
| `C010` Cartulina | J#34, J#76, T#31, T#73, 1#29, 1#50, 2#28, 2#57, 3#58 | Cartulina escolar de 1/8 135 g x 10 unidades blanca (`TK-REV-633655`) | Paquete Carton Cartulina Octavo x25 Unds (`TK-C010-PRE`) |  |
| `C010` Cartulina | J#37, 3#18 | PTE CARTULINA IRIS MULTICOLOR EVERY DAYS (`TK-REV-135131`) | Cartulina Iris En 1/8 Paquete X 20 Unidades (`TK-REV-104885383`) |  |
| `C010` Cartulina | J#75, T#72, 1#14, 1#28, 1#49, 2#27, 2#56 | Cartulina escolar de 1/8 135 g x 10 unidades (surtido) (`TK-REV-633667`) | Cartulina escolar de 1/8 135 g x 10 unidades (surtido) (`TK-REV-633667`) |  |
| `C010` Cartulina | T#33 | PTE CARTULINA IRIS MULTICOLOR EVERY DAYS (`TK-REV-135131`) | PTE CARTULINA IRIS MULTICOLOR EVERY DAYS (`TK-REV-135131`) |  |
| `C010` Cartulina | 5#19 | Cartulina escolar de 1/8 135 g x 10 unidades amarilla (`TK-REV-633665`) | Cartulina escolar de 1/8 135 g x 10 unidades amarilla (`TK-REV-633665`) |  |
| `C010` Cartulina | 5#20 | Cartulina escolar de 1/8 135 g x 10 unidades azul (`TK-REV-633659`) | Cartulina escolar de 1/8 135 g x 10 unidades azul (`TK-REV-633659`) |  |
| `C010` Cartulina | 5#21 | Cartulina escolar de 1/8 de 135 g x 10 unidades verde (`TK-REV-633661`) | Cartulina escolar de 1/8 de 135 g x 10 unidades verde (`TK-REV-633661`) |  |
| `C012` Esfero | 3#28, 4#26, 5#35 | Caja Esfero BIC Cristal 1.0mm x12 Unds Tapa Negro (`TK-REV-47620768792747`) | Caja Esfero BIC Cristal 1.0mm x12 Unds Tapa Negro (`TK-REV-47620768792747`) |  |
| `C012` Esfero | 6#56, 7#81, 8#71, 9#75, 10#64, 11#61 | Caja Esfero Norma 0.7mm Gel x12 Unds Tapa Azul Rey (`TK-REV-47235739549867`) | Bolígrafo Faber Castell 062M pague 5 lleve 6 (`TK-C012-PRE`) |  |
| `C013` Tijeras | T#66, 1#21, 1#66, 2#43 | Tijera punta roma NESSAN (`TK-C013-PRE`) | Tijera punta roma NESSAN (`TK-C013-PRE`) |  |
| `C013` Tijeras | 3#30, 3#49, 4#28, 4#58, 5#37, 5#62, 6#42, 6#65, 7#59, 7#64, 7#91, 8#81, 9#52, 9#85, 10#74, 11#71 | Tijeras Multiusos 6,5 pulgadas Eterna (`TK-C013-ECO`) | Tijera punta roma NESSAN (`TK-C013-PRE`) |  |
| `C015` Cinta adhesiva | J#27, T#50, 4#60, 5#24 | Cinta Adhesiva Transparente X 255 Metros N°01 01 (`TK-C015-ECO`) | Cinta Adhesiva Transparente X 255 Metros N°01 01 (`TK-C015-ECO`) |  |
| `C015` Cinta adhesiva | J#50, J#78, T#47, T#75, 1#31, 1#55, 2#33, 2#59, 3#61, 4#61, 6#41, 7#61, 7#66, 9#56 | Cinta de enmascarar Startape de 18 mm x 40 metros (`TK-REV-634115`) | Cinta de enmascarar multiusos Pegafan beige (`TK-REV-142931`) |  |
| `C016` Pegante en barra | 6#43, 6#63, 7#65, 7#89, 8#79, 9#83, 10#72, 11#69 | Pegante en barra de 15 g, surtido (`TK-REV-656600`) | Pegante en barra de 40 g PegaStic (`TK-C016-PRE`) |  |
| `C017` Pegante líquido | J#15, T#16, 1#23, 3#50, 4#59, 5#65 | Pegante Liquido Invisible 147ml (`TK-C017-ECO`) | PEGANTE MADERA COLBON (`TK-C017-PRE`) |  |
| `C017` Pegante líquido | 2#51 | Pegante Liquido Invisible 147ml (`TK-C017-ECO`) | Pegamento líquido Glukids x 250 g (`TK-C017-CON`) |  |
| `C018` Compás | 3#35, 4#34, 5#42, 6#19, 7#19, 10#18 | Compas escolar keyroad (surtido) (`TK-C018-ECO`) | Compas Precision Faber Castell (`TK-C018-PRE`) |  |
| `C018` Compás | 3#47, 6#38, 7#32, 8#38, 9#34, 10#41, 11#37 | Compas Precision Faber Castell (`TK-C018-PRE`) | Compas Precision Faber Castell (`TK-C018-PRE`) |  |
| `C019` Escuadra | 5#45, 6#73 | Escuadra Faber-Castell de 45° y 26 cm (`TK-C019-ECO`) | Set Escuadra Semiprofesional Eterna 32x23 Cm X 2 Pcs Eterna (`TK-C019-CON`) |  |
| `C021` Pincel | J#74, T#71, 3#89 | Pincel Plano Eterna #5 (`TK-REV-124275612`) | Pincel Plano Eterna #5 (`TK-REV-124275612`) |  |
| `C022` Plastilina | 1#30, 1#52, 2#30, 2#50, 2#58, 5#23 | Paquete Plastilina Mi Trensito En Barra Largas X10 Colores Surtidos (`TK-REV-44702903402667`) | Plastilina en barra Norma x 12 uds. (`TK-C022-PRE`) |  |
| `C023` Transportador | 3#36, 4#35, 5#43, 6#20, 7#20, 10#19 | Transportador escolar de 360° Faber Castell (`TK-C023-CON`) | Transportador 360 Grados FABER CASTELL (`TK-REV-4673`) |  |
| `C024` Bata de laboratorio | 7#27 | Informativa (`no_comprar`) | Informativa (`no_comprar`) |  |
| `C024` Bata de laboratorio | 7#54, 8#53 | Bata Laboratorio Escolar Blanca en Tela (`TK-C024-ECO`) | Bata De Laboratorio Unisex Manga Corta Talla Xl (`TK-REV-104159467`) |  |
| `C025` Tabla periódica | 7#26, 9#26, 10#30, 11#27 | Tabla Periodica Walter Grande (26x20cm) (`TK-C025-PRE`) | Tabla Periodica Walter Grande (26x20cm) (`TK-C025-PRE`) |  |
| `C026` Calculadora | 8#28, 9#19, 9#27, 10#16, 10#25, 10#28, 11#19, 11#22, 11#25 | Calculadora Científica Casio Fx 82La Plus (`TK-REV-102106286`) | Calculadora Científica Casio Fx 82La Plus (`TK-REV-102106286`) |  |
| `C028` Silicona | T#90, 1#43, 2#81, 3#76, 4#70, 5#72 | Barra Silicona Transparente Delgada X 10 Unidades (`TK-C028-ECO`) | Docena Barra Silicona Gruesa (`TK-C028-PRE`) |  |
| `C028` Silicona | T#91 | Barra Silicona Transparente Delgada X 10 Unidades (`TK-C028-ECO`) | Barra Silicona Transparente Delgada X 10 Unidades (`TK-C028-ECO`) |  |
| `C028` Silicona | 7#60, 8#52, 9#55, 10#60, 11#57 | Silicona Liquida 100Ml TESA (`TK-C028-CON`) | Silicona Liquida 100Ml TESA (`TK-C028-CON`) |  |
| `C029` Foamy | J#29, T#26, 2#35 | Foamy en octavo x 10 unidades, 25 cm x 35 cm (`TK-REV-612632`) | Foamy en octavo x 10 unidades, 25 cm x 35 cm (`TK-REV-612632`) |  |
| `C032` Hojas | 6#66, 7#92, 8#82, 9#86, 10#75, 11#72 | Paquete De Hojas Examen X100 Unds Cuadros (`TK-C032-ECO`) | Paquete De Hojas Examen X100 Unds Cuadros (`TK-C032-ECO`) |  |
| `C033` Palitos | 7#51 | Palos De Madera Para Paleta Color Natural X 500 Unidades (`TK-REV-105198377`) | Palos De Madera Para Paleta Color Natural X 500 Unidades (`TK-REV-105198377`) |  |
| `C034` Diccionario | 2#15, 4#10, 5#11, 6#12 | Diccionario básico de español – inglés e inglés – español (`TK-C034-CON`) | Diccionario básico de español – inglés e inglés – español (`TK-C034-CON`) |  |
| `C034` Diccionario | 6#5, 7#5 | Diccionario Español Bristol Nuevo (`TK-C034-ECO`) | Diccionario Español Bristol Nuevo (`TK-C034-ECO`) |  |
| `C036` Juego de geometría | 5#58, 6#35, 7#30, 8#36, 9#32, 10#39, 11#35 | Set Juego Geométrico Flexible Eterna (`TK-C036-ECO`) | Juego geométrico Faber-Castell x 4 piezas (`TK-C036-PRE`) |  |
| `C038` Lana | J#44, J#85, T#42, T#84, 1#38, 2#66 | Rollo de lana x 100 metros 50g con Lurex, rojo (`TK-C038-CON`) | Lana Escolar 5 Colores X15G FINLANDEK (`TK-REV-3332191`) |  |
| `C039` Resaltador | 3#29, 4#27, 5#36, 6#57, 7#82, 8#72, 9#76, 10#65, 11#62 | Resaltador Boss Pastel STABILO (`TK-REV-1630647`) | Caja Resaltador Doricolor x10 Unds Azul (`TK-C039-PRE`) |  |
| `C040` Toallas y pañitos | J#66, T#56 | Paquete Pañitos Humedos Grandulones Panda X100 Unds (`TK-REV-45616427991211`) | Pequeñin Toallitas Húmedas Original (`TK-C040-PRE`) |  |
| `C041` Cartón | 3#59 | Pliego De Carton Paja 100x70 Centimetros (`TK-C041-ECO`) | Paquete Carton Paja Octavos x10 Unds Colores (`TK-C041-PRE`) |  |
| `C043` Lentejuelas | J#52, T#48, 2#70 | Paquete Lentejuelas x9 Colores (Metro por Color) Surtido (`TK-C043-ECO`) | Paquete Lentejuelas x9 Colores (Metro por Color) Surtido (`TK-C043-ECO`) |  |
| `C044` Libro | 7#9 | Informativa (`otro`) | Informativa (`otro`) |  |
| `C045` Notas adhesivas | 6#64, 7#90, 8#80, 9#84, 10#73, 11#70 | Notas adhesivas amarilla (`TK-C045-ECO`) | Notas adhesivas transparentes Post-it x 36 hojas (`TK-C045-PRE`) |  |
| `C046` Tabla de picar | J#12, T#13 | Tabla Picado Con Tablero Acrilico Octavo Motivo Para Niña + Punzon Plastico (`TK-C046-ECO`) | TABLA DE PICADO Y PUNZADO MALUMA (`TK-REV-450006`) |  |
| `C047` Algodón | 2#68 | Paquete Algodón Blanco X50 Gramos (`TK-C047-ECO`) | Algodón HIGIETEX pads y copitos (1 und) (`TK-REV-3711895`) |  |
| `C049` Delantal | J#28, T#51, 4#46 | Delantal de Pintura Escolar Antifluido Niña Talla de 6 a 12 - Se envia un Motivo Aleatorio (`TK-REV-44922807910571`) | Delantal de Pintura Escolar Antifluido Niña Talla de 6 a 12 - Se envia un Motivo Aleatorio (`TK-REV-44922807910571`) |  |
| `C051` Témpera | 3#53, 4#47 | Caja Tempera Payasito Escolar X6 Colores Primarios + Pincel + Paleta No Toxico (`TK-REV-47123276529835`) | Témpera gouache de colores de 12 ml x 12 unidades (`TK-C051-PRE`) |  |
| `C053` Crayones | J#24 | Crayón Eterna X 12 Jumbo Largo Redondo Eterna (`TK-C053-ECO`) | Crayón Jumbo, Estuche X 12 Col STABILO (`TK-C053-PRE`) |  |
| `C053` Crayones | 1#22 | Crayola Crayones Mi Trensito * 12 Colores X 1 Cajas (`TK-REV-104946593`) | Crayón Jumbo, Estuche X 12 Col STABILO (`TK-C053-PRE`) |  |
| `C057` Vaso o plato | 8#50 | Paquete Vaso Plastico X12 Unds Among Us (`TK-REV-45126704693419`) | Vaso plástico de 700 ml con pitillo, multicolor (`TK-REV-712640`) |  |
| `C058` Agenda | 1#68, 3#78 | Agenda Chica Kawai 2026 2027 (`TK-C058-ECO`) | Agenda Design Argollada Grande 105 5 Materias Cuadros Hombre - Se Envia Un Motivo Aleatorio (`TK-C058-PRE`) |  |
| `C060` Curvígrafo | 4#52, 9#92, 10#20 | Curvigrafo Grande (`TK-C060-ECO`) | Curvígrafo Faber-Castell x 3 piezas (`TK-C060-PRE`) |  |
| `C061` Aserrín | 2#69 | Paquete De Aserrin En Colores Escolar X12 Unds Surtidas (`TK-C061-CON`) | Aserrin Escolar De Colores Bolsa X 12 Unidades (`TK-C061-PRE`) |  |
| `C066` Flauta | 2#46, 3#66 | FLAUTA DULCE SOPRANO HAMMELIN NORMARH (`TK-REV-407601`) | Flauta dulce soprano Excel (`TK-REV-19670`) |  |
| `C068` Ojos móviles | J#46, T#44 | Ojos Móviles Redondos 12 Mm Para Manualidades X 100 Unidades (`TK-C068-ECO`) | Ojos Móviles Redondos 15 Mm Para Manualidades X 100 Unidades (`TK-REV-105171848`) |  |
| `C075` Bolsa de basura | 3#55, 4#49, 5#54 | Bolsa para basura TASK minipapelera 55x38 cm (`TK-REV-3569349`) | Bolsa para basura TASK provechable 50x70 cm (`TK-REV-3405243`) |  |
| `C076` Carboncillo | 6#36 | Lapiz Carboncillo Prang Medio Unidad (`TK-C076-ECO`) | Lápiz carboncillo de pita x 3 piezas (`TK-C076-PRE`) |  |
| `C085` Limpiapipas | J#51, T#46 | Paquete Chelines - Limpia Pipas X10 Unds Azul (`TK-C085-ECO`) | Paquete Chelines - Limpia Pipas X100 Unds Azul (`TK-C085-PRE`) |  |
| `C093` Tinta china | 7#38, 11#50 | Tinta Winsor & Newton negro indio 030 de 14 ml (`TK-REV-552579`) | Tinta Winsor & Newton negro indio 030 de 14 ml (`TK-REV-552579`) |  |
| `C094` Tiza | 5#59 | Tiza pastel suave seca x 12 unidades surtidas (`TK-C094-ECO`) | Caja de tiza colores metalizados x 10 unidades (`TK-C094-PRE`) |  |
| `C102` Protoboard | 9#63 | Protoboard Gl12 Con 840 Puntos (`TK-REV-104905872`) | Protoboard Gl12 Con 840 Puntos (`TK-REV-104905872`) |  |
| `C103` Batería 9V | 1#42, 2#80, 3#73, 4#69, 5#71, 6#46, 7#72 | Pila Bateria 9V Alcalina (`TK-REV-101124304`) | Cargador + Bateria 9V 250Mah Beston Compatible Aa/Aaa/9V (`TK-REV-102549385`) |  |
| `C111` Gorro de natación | 3#86, 4#79, 5#81, 11#78 | Gorro De Natación En Silicona E Sport Azul (`TK-REV-104996053`) | Gorro de Natación Classic Silicone (`TK-REV-123728132`) |  |
| `C113` Papel iris | J#6, T#36, 1#24, 1#51, 2#29, 3#17, 3#51, 5#25, 7#62, 7#67, 9#57 | Block Iris Carta Colores Surtidos X 12H FINLANDEK (`TK-REV-3630108`) | Block Iris Carta Colores Surtidos X 12H FINLANDEK (`TK-REV-3630108`) |  |
| `C114` Kit de lápices de dibujo | 5#51, 6#31, 7#34, 8#32, 9#31, 10#38, 11#34 | Caja de Lápices Para Dibujo Eterna (`TK-REV-124280762`) | Set de 12 lápices de dibujo con accesorios (`TK-REV-554182`) |  |
| `C115` Limpiatipos | 3#46, 4#44, 5#52, 6#32, 7#35, 8#33, 9#35, 10#42, 11#38 | Paquete Limpiatipos Pelikan X4 Unds (`TK-REV-47664059121835`) | Pasta Limpiatipos Multiusos X 4 Uds Pelikan (`TK-REV-100826115`) |  |
| `C118` Frascos para almacenar pintura | 7#50, 8#48, 9#45, 10#51, 11#47 | Set de 8 frascos de vidrio, 4 cm, con corcho (`TK-REV-603894`) | Set de 8 frascos de vidrio, 4 cm, con corcho (`TK-REV-603894`) |  |
| `C130` Papel silueta | J#35 | Papel Silueta Octavos Paq X 10 Und (`TK-REV-124001135`) | Paquete Papel Silueta Octavos X10 Unds Surtido (`TK-REV-47408270901419`) |  |
| `C136` Gafas de natación | 3#84, 4#80, 5#82, 11#79 | Gafas De Natacion Deportivas Swimming (`TK-REV-104926378`) | Gafas de Natación Tracks Junior (`TK-REV-123572356`) |  |

## Anexo 3. Cómo se reprodujo

1. `git merge --ff-only origin/feature/integracion-total`, que llevó la rama local de `a565aeb` a `d4ea7cb`. Nada local se perdió: el árbol no tenía cambios con seguimiento.
2. Bases nuevas `tukit_{identidad,catalogo,inteligencia}_auditoria` (con `vector` y `pg_trgm`), migradas al head de cada servicio con las migraciones de la rama y con los índices de `infra/postgres/indices/`.
3. Variables `TUKIT_*_DB_URL` apuntando a esas bases, las de Comercio y Operación a nombres inexistentes, y sin `GEMINI_API_KEY` ni `GOOGLE_API_KEY`.
4. `python -m tukit_catalogo.cargador --datos datos/catalogo`, `python -m tukit_identidad.curaduria importar` y `python -m tukit_catalogo.curaduria importar`.
5. `python -m tukit_catalogo.api --puerto 8112` y una pasada de `python -m tukit_inteligencia.poller`.
6. Extracción de `item_lista_oficial` (con su concepto y tipo), `linea_kit` de los kits Ahorrador y Premium, los candidatos y atributos exigidos de `/resueltos`, y `producto_canonico` activo con precio vigente. Cruce renglón por renglón, y con la extracción de la auditoría sobre `a565aeb`.

Las bases aisladas se eliminaron al terminar. Para repetir la auditoría basta con recrearlas con estos pasos sobre el mismo commit.
