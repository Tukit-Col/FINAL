# OE4 — Frente de Pareto con NSGA-II y selección con MAUT

- **Fecha:** 2026-09-22
- **Objetivo específico:** OE4 (generación de recomendaciones multiobjetivo)
- **Servicio tocado:** `inteligencia`
- **Documento que manda por encima de este:** `Arquitectura/ARQUITECTURA.md`
- **Spec hermano:** `2026-09-22-resolucion-hibrida-grafo-design.md` (OE3), que produce los candidatos

---

## 1. El problema, medido

### 1.1 Lo que hay hoy

`inteligencia/tukit_inteligencia/optimizador.py` es una heurística y su propio docstring lo
declara. Pero afirma algo que no se sostiene:

> «Cambiar la heurística por el algoritmo es reemplazar `elegir_por_perfil` y nada más.»

**No es cierto, y este es el punto central del spec.** `elegir_por_perfil` elige línea por
línea, y `consolidar()` junta la demanda de hermanos **después**, sobre las líneas ya elegidas.
Mientras la consolidación sea post-proceso, las líneas son independientes, el problema se
descompone por línea y un greedy es **óptimo**. Un NSGA-II encima de eso no encontraría nada
que el greedy no encuentre: sería decorativo.

El propio plan del proyecto ya lo había dicho: *«si los ítems fueran independientes el problema
se descompone y es trivial […] ese acoplamiento es la contribución»*.

### 1.2 El defecto que hace separable el problema

`catalogo/tukit_catalogo/consulta.py::cargar_indice` calcula
`func.min(precio.c.valor_centavos)` agrupando por producto, y `Opcion` lleva un único
`precio_cop` **sin tienda**. Es decir: el optimizador no puede razonar sobre tiendas, y asume
implícitamente que cada ítem se compra en su tienda más barata sin fricción — una lista de 20
ítems podría implicar hasta 20 tiendas.

Eso reproduce en el algoritmo exactamente el dolor que la encuesta midió: **41 de 60 familias
compran en 3 o 4+ lugares** contra 3 que compran en uno, y *«no encontrar todo en un solo
lugar»* es el 22 % del dolor declarado (P18).

### 1.3 Por qué la tienda sí acopla, aunque el dato parezca decir lo contrario

Un dato parece matar la idea:

| Hecho | Valor |
|---|---|
| Productos con oferta en **más de una** tienda | **5 de 241** |

Pero el acoplamiento **no necesita** que un producto esté en varias tiendas. Necesita que la
*elección* cambie qué tiendas se usan. Y eso ocurre:

| Conceptos cuyos productos están en… | Cantidad |
|---|---|
| 1 sola tienda | 43 |
| 2 tiendas | 25 |
| 3 tiendas | 14 |
| **≥ 2 tiendas** | **39 de 82** |

Elegir el económico del concepto A (Panamericana) y el premium del B (Éxito) paga dos costos
fijos donde uno habría bastado. Ese término acopla **todos** los grupos entre sí, no solo a los
hermanos. Con él, el problema deja de descomponerse y NSGA-II tiene algo que hacer.

Tiendas activas: Éxito (111 ofertas), Papelería Grancentral (70, mayorista), Panamericana (66).

### 1.4 Supuesto de alcance declarado

Los **102 huecos de catálogo** quedan fuera (igual que en el spec hermano). El optimizador
trabaja con los candidatos que el OE3 le entregue, y un grupo sin candidatos es una línea
informativa con su razón, no un error.

---

## 2. Formulación

### 2.1 Grupos de demanda

Un **grupo** `g = (concepto, atributos_impuestos)`, agregando renglones de **todos los hijos
del hogar**. `demanda_g` = suma de cantidades en unidad base.

Dos reglas opuestas sobre la misma estructura, y las dos son de negocio:

- **Papelería se agrega.** Dos hermanos con un borrador cada uno forman un grupo de demanda 2,
  y la caja de 10 compite por costo contra 2 sueltos.
- **Los textos nunca se agregan.** `tipo_item == "texto"` produce un grupo por
  `(hijo, edición)`. Dos ediciones del mismo título no son sustituibles aunque compartan ISBN
  de obra, y `version_vigente` guarda histórico precisamente para poder explicarle a un
  acudiente por qué el libro del hijo mayor no le sirve al menor.

**La diferencia con hoy es de orden, y es todo el asunto:** hoy se elige y después se
consolida; aquí se agrega **antes** de que el algoritmo elija, así que el empaque compartido
influye en la decisión en vez de parchearla.

### 2.2 Variables

Vector entero `x` de longitud `G` (número de grupos). `x_g ∈ {0, …, n_g − 1}` indexa una
**oferta** candidata del grupo `g`, donde una oferta es una tupla `(producto, tienda, precio)`.

Derivado, no decidido:

```
unidades_g = ceil(demanda_g / unidades_por_empaque(x_g))
```

Esa línea es la corrección del defecto que sumaba doce cajas cuando la lista pedía doce
lápices. Ya está implementada y probada en `unidades_a_comprar`, y **se conserva intacta**.

Codificación siempre factible: cualquier vector dentro de rango es un kit válido. No hacen
falta operadores de reparación, que es la razón principal para preferir esta formulación al
MOKP binario `x_ij ∈ {0,1}` por línea × candidato. El MOKP binario se formula en el documento
como modelo de referencia frente a la literatura que cita el VFP, y **no se implementa**.

### 2.3 Objetivos

Tres, todos a minimizar (convención de pymoo):

```
f₁(x) = Σ_g  precio(x_g) · unidades_g  +  Σ_{t ∈ tiendas(x)}  costo_fijo_t
f₂(x) = − fidelidad(x)
f₃(x) = − disponibilidad(x)
```

**`f₁` — costo.** El segundo término es el que acopla. `tiendas(x)` es el conjunto de tiendas
distintas usadas por la solución completa.

> **`costo_fijo_t` es un parámetro de modelo, no un dato medido.** No tenemos costos de envío
> reales. Se declara como parámetro configurable con un valor por omisión explícito, y la
> evaluación incluye **análisis de sensibilidad** barriéndolo. Presentarlo como dato sería
> falso; presentarlo como parámetro con su barrido es un resultado.

**`f₂` — fidelidad.** Media ponderada por demanda de la utilidad de cada elección:

```
fidelidad(x) = Σ_g demanda_g · u_fid(x_g) / Σ_g demanda_g

u_fid = w_marca · u_marca_exigida + w_calidad · u_nivel + w_pers · u_personaje
```

Aquí se corrige el defecto estructural registrado en el plan: `utilidad_por_tier['licencia']`
vale `None`, así que hoy el optimizador **no puede puntuar un producto de personaje** en el eje
de fidelidad. `licencia` sale del eje de nivel y **el personaje pasa a eje propio, ortogonal al
nivel**, con utilidad no nula. Un cuaderno de Spiderman tiene calidad *y* personaje. De paso se
corrigen `algodon mk` y `diseplast`, hoy mal clasificadas como `licencia`.

**`f₃` — disponibilidad.** Fracción de grupos resueltos con oferta vigente y disponible. Este
objetivo no sale de la P21 sino de la P18: **37 % del dolor declarado es disponibilidad y
agotados**, el primero de la lista. Es lo que justifica que sea un objetivo y no un filtro.

**El número de tiendas NO es un cuarto objetivo.** Entra como costo fijo dentro de `f₁`. Se
probó como objetivo separado y se documenta la comparación; con tres objetivos NSGA-II está
holgadamente dentro del régimen donde su desempeño está validado empíricamente, que es el
argumento que el VFP ya cita.

### 2.4 Restricciones duras

- **Presupuesto del hogar**: `f₁(x) ≤ Σ_hijos presupuesto_hijo · (1 + disposición_sobreprecio)`.
  Es una **cota**, no una preferencia. Es el uso más valioso de la encuesta: convierte una
  opinión declarada en una restricción imponible.
- **Atributos impuestos**: ya filtrados aguas arriba por el OE3; un candidato con
  `cumple = false` no entra al conjunto del grupo.

Si ninguna solución satisface el presupuesto, no se falla: se devuelve el frente sin la
restricción y se dice explícitamente que ningún kit cabe y cuál es el más barato posible. El
comportamiento ya existe en `recomendar` y se conserva.

### 2.5 Lo que se conserva sin tocar

Está probado y no depende del algoritmo:

- `unidades_a_comprar` — el techo de la división.
- **Lo informativo se muestra y no se cobra** (FU-06). El total suma solo lo que Tukit puede
  entregar, y la base lo impone con un `CHECK`.
- Las líneas informativas **no entran** al cálculo de `f₂` ni `f₃`. Medirlas inflaría ambos
  números con ítems que nunca se iban a surtir, y el kit se vería mejor cuanto menos pudiera
  vender.
- La explicación de consolidación por línea, que el acudiente necesita ver.

---

## 3. Lo que hay que pedirle al catálogo

El OE3 debe entregar **ofertas, no precios mínimos**. Concretamente, cada candidato viaja con
`producto_id`, `oferta_id`, `tienda_id`, `tienda_slug`, `precio_cop`, `unidad_base` y
`unidades_por_empaque`. Quitar el `min(precio)` de `cargar_indice` es requisito de este spec.

Un producto con 3 ofertas produce 3 candidatos, no 1. El tamaño del espacio crece y eso es
deseado: es el espacio donde vive la decisión de consolidar tiendas.

---

## 4. MAUT, en dos momentos

### 4.1 Funciones de utilidad

Utilidad por atributo normalizada a [0,1] **sobre el rango observado en el frente**, no sobre
un máximo teórico: `u(costo)` decreciente, `u(fidelidad)` y `u(disponibilidad)` crecientes.
Normalizar sobre el frente evita que un rango teórico inalcanzable aplaste las diferencias
reales.

Agregación **aditiva**: `U(k) = Σ wᵢ · uᵢ(k)`, **declarando explícitamente el supuesto de
independencia preferencial** que la forma aditiva exige. La forma multiplicativa se consideró y
se documenta como alternativa no adoptada; el supuesto se enuncia en la memoria en vez de
esconderse.

### 4.2 Un defecto en los pesos actuales, que hay que corregir

La P21 puntuada por posición sobre 60 respuestas da: **precio 2,85 · marca exigida 2,73 ·
calidad 2,55 · personaje 1,87**, que suman exactamente 10,00. Normalizados:

| Criterio | P21 normalizada | `PESOS_POR_OMISION` en el código |
|---|---|---|
| precio | **0,285** | 0,35 |
| marca_exigida | **0,273** | 0,30 |
| calidad | **0,255** | 0,25 |
| personaje | **0,187** | 0,10 |

**Los pesos del código no son los de la encuesta.** Exageran la separación, y a `personaje` le
quitan casi la mitad de su peso real. El hallazgo importa porque el argumento de negocio que
sostiene el kit Fan es justamente que el personaje quedó último y descolgado — pero la P21 dice
que los tres primeros caben en 0,03 y el personaje queda a 0,187, no a 0,10.

Se corrigen a los valores normalizados de la P21 y se deja el cambio registrado con su
justificación. Es exactamente el tipo de hallazgo que el capítulo de defectos de la memoria
pide.

### 4.3 Estructura de dos niveles

Dos instrumentos distintos responden dos preguntas distintas y no se deben mezclar:

- **P21** (¿qué mira al elegir *entre productos*?) → sub-pesos **dentro** de `f₂ fidelidad`:
  marca 0,382 · calidad 0,357 · personaje 0,262 (renormalizados dentro del grupo).
- **P18** (¿qué le arruina el día?) → justifica que `disponibilidad` exista como objetivo.
- **Pesos de kit** `(w_costo, w_fidelidad, w_disponibilidad)` → definen el perfil. Son el
  parámetro de OP-04.

### 4.4 Momento 1 — MAUT define los tres kits

Tres vectores de peso escalarizan el frente; el argmax de cada uno es un punto del frente:

| Perfil | Carga | Vector `(w_costo, w_fid, w_disp)` |
|---|---|---|
| `Ahorrador` | precio | dominado por `w_costo` |
| `Premium` | calidad y nivel | dominado por `w_fid`, con sub-pesos cargados a calidad |
| `Fan` | personaje | dominado por `w_fid`, con sub-pesos cargados a personaje |

Así **los tres kits son puntos del frente por construcción y no por etiqueta**, que es lo que
`OP-01` y `UI-02` piden y lo que hoy no ocurre.

**Caso que hay que manejar explícitamente:** si dos perfiles caen en el mismo punto del frente,
se toma el siguiente mejor por ese vector **y se dice**. Que el kit Ahorrador y el Premium sean
casi el mismo es información real y útil para el acudiente, no un empate que haya que ocultar.

Recordatorio de vocabulario, ya documentado en el docstring de `PerfilKit` y que este spec no
puede romper: el **nivel** de un producto (`economico|confiable|premium`) y el **perfil** de un
kit (`Ahorrador|Fan|Premium`) son ejes distintos que comparten la palabra "premium". Un kit
`Ahorrador` puede llevar un producto `premium` si resultó más barato por empaque.

### 4.5 Momento 2 — MAUT recomienda uno

Los pesos declarados por **ese** acudiente escalarizan de nuevo y marcan uno de los tres. Las
reglas derivadas de la encuesta se conservan, pero **como priors sobre los pesos, no como
`if/else` sobre el resultado**:

- Por omisión `Ahorrador`: 42 de 60 (70 %) pagan como máximo 5 % más y 15 exigen precio igual
  o menor.
- `Premium` solo si pone calidad primero **y** declara disposición ≥ 10 %.
- `Fan` solo con `personaje_por_hijo` explícito. El que paga es el papá y el que quiere el
  personaje es el hijo.
- Si el recomendado excede el presupuesto, se cae al siguiente punto del frente que sí quepa y
  la razón lo dice en lenguaje llano.
- **Siempre se muestran los tres** (`OP-01`). Nunca se ocultan los otros dos.

### 4.6 Privacidad

El **estrato no entra al modelo**: 41 de 60 respuestas son estrato 4, casi no hay varianza, y
la correlación intuitiva no existe (el segmento de 400–700 mil es el *más* dispuesto a pagar
sobreprecio). Como no predice y sí es dato sensible de un hogar con menores, no guardarlo es a
la vez lo correcto y lo privado.

`kit.pesos_usados_cifrados` ya existe como columna cifrada y las preferencias pasan por el
puerto `Cifrador`. Este spec las mantiene ahí y dentro del alcance del derecho al olvido.

---

## 5. La prueba contra nosotros mismos

Es la parte del spec que más sostiene la tesis, y es autocrítica por diseño.

**Afirmación a demostrar:** NSGA-II supera al greedy *porque* el problema está acoplado.

**Falsación:** se corre la evaluación completa otra vez con `costo_fijo_t = 0` y sin agregación
entre hermanos. Ahí el problema **debe** descomponerse y el greedy **debe** empatar con
NSGA-II en hipervolumen.

- Si empata → queda demostrado que el acoplamiento es la contribución.
- Si NSGA-II gana igual → hay algo mal en la formulación o en la implementación del greedy, y
  es mejor descubrirlo aquí que en la sustentación.

Un experimento que no puede salir mal no demuestra nada. Este puede.

---

## 6. Líneas base y medición

| Línea base | Para qué | Alcance |
|---|---|---|
| **Frente exacto por ε-restricción** | Verdad de campo: cuánto se acerca NSGA-II al frente *real*, no solo si le gana al greedy | Instancias ≤ 8 grupos |
| **Greedy actual** (`elegir_por_perfil` + `consolidar`) | Línea base honesta: es literalmente el sistema de hoy | Todas |
| **Búsqueda aleatoria** | Piso; detecta si el algoritmo genético aporta algo sobre muestrear | Todas |

Métricas:

- **Hipervolumen** con punto de referencia declarado y justificado (el peor valor alcanzable
  por objetivo dentro de la instancia).
- **Cobertura** y **distancia generacional** contra el frente exacto, donde exista.
- **Tiempo de ejecución** y número de evaluaciones hasta convergencia.
- **Sensibilidad a `costo_fijo_t`**, barriéndolo, porque es parámetro y no dato (§2.3).

Instancias de evaluación:

- Las **175 listas oficiales** reales, hogar de un hijo.
- Hogares sintéticos de 2, 3 y 4 hijos combinando listas de grados distintos del mismo colegio,
  que es donde la agregación entre hermanos tiene efecto.

Semilla fija y registrada; el resultado tiene que ser reproducible.

---

## 7. Cambios de esquema, de manifiesto y de ADR

0. **ADR 0020 (bloqueante, va primero).** El `ARQUITECTURA.md` §11 exige que toda modificación
   de arquitectura entre al lock con su ADR antes de bajar a código, y este spec cambia dos
   cosas que califican: la tienda pasa a ser dimensión de decisión (lo que obliga a `catalogo`
   a exponer ofertas en vez de precios mínimos) y aparecen dos referencias cruzadas nuevas.
   El ADR debe registrar, en formato Nygard, la alternativa rechazada —**MOKP binario
   `x_ij ∈ {0,1}`**, más fiel a la literatura que cita el VFP pero con espacio mucho mayor y
   necesidad de operadores de reparación— y el argumento de no separabilidad de §1.3. Es
   material que la sustentación va a pedir de todos modos.
1. **`inteligencia.linea_kit`** += `oferta_id` y `tienda_id`. Hoy guarda `sku`,
   `precio_unitario_cop` y `subtotal_cop`, pero no de dónde sale el precio, así que el kit no
   puede decir en qué tienda se compra cada cosa.
2. **`inteligencia.kit`** += métricas del frente (hipervolumen, tamaño del frente, semilla,
   parámetros) en el JSON de `objetivos` o en columna propia, para que un kit publicado sea
   reproducible.

   Ninguno de los dos cambios agrega tablas: son columnas, y el contador
   `meta.total_tablas_esperado = 70` no se mueve.
3. **Referencias cruzadas nuevas, declaradas en `manifiesto.toml` ANTES de escribir código**,
   o el invariante 4 tumba la construcción:

   ```toml
   [[referencias_cruzadas]]
   desde = "inteligencia.linea_kit.oferta_id"
   hacia = "catalogo.oferta_tienda"
   nota  = "De qué oferta concreta sale el precio. Sin ella el kit no puede decir en qué tienda se compra, y el costo fijo por tienda no sería auditable."

   [[referencias_cruzadas]]
   desde = "inteligencia.linea_kit.tienda_id"
   hacia = "catalogo.tienda"
   nota  = "Denormalizada desde la oferta para poder agrupar por tienda sin salir del servicio."
   ```

4. **Dependencias nuevas en `servicios/inteligencia/pyproject.toml`**: `pymoo` y `numpy`. Para
   el frente exacto, `scipy.optimize.milp` (HiGHS), que evita meter un solver aparte. El
   `pyproject` raíz tiene `dependencies = []` y cada servicio declara las suyas; esto no cambia.

---

## 8. Pruebas, primero

Las de `test_optimizador.py` que **siguen valiendo y no se tocan** (son sobre aritmética y
reglas de negocio, no sobre el algoritmo): la cuenta de unidades, lo informativo que no se
cobra, y la forma de la recomendación.

Nuevas, en `servicios/inteligencia/tests/`:

- `test_grupos_demanda.py` — dos hermanos con un borrador cada uno forman **un** grupo de
  demanda 2; dos hermanos con biblia en grados distintos forman **dos** grupos y la razón queda
  escrita.
- `test_acoplamiento_empaque.py` — con empaque de 10 y demanda 2, la caja compite por costo
  contra 2 sueltos, y gana la que de verdad sea más barata.
- `test_acoplamiento_tienda.py` — **la prueba que justifica el spec.** Construida para que un
  kit de 2 tiendas le gane a uno de 4 aunque cada ítem suelto sea más caro. Si esta prueba pasa
  con el greedy, el diseño falló.
- `test_frente_es_frente.py` — ninguna solución del frente domina a otra; el frente tiene más
  de un punto en instancias no triviales.
- `test_tres_kits_del_frente.py` — los tres perfiles son puntos del frente; si dos coinciden,
  se toma el siguiente y se informa.
- `test_presupuesto_es_cota.py` — el presupuesto es dura; si nada cabe, se dice y se ofrece el
  más barato.
- `test_personaje_ortogonal.py` — un producto puede tener nivel **y** personaje a la vez, y la
  utilidad de personaje no es `None`.
- `test_reproducible.py` — misma semilla y misma entrada dan el mismo frente.
- `test_exacto_vs_nsga.py` — en instancias ≤ 8 grupos, NSGA-II alcanza el frente exacto dentro
  de una tolerancia declarada.
- `test_falsacion_acoplamiento.py` — con `costo_fijo = 0` y sin agregación, greedy y NSGA-II
  empatan en hipervolumen (§5).

---

## 9. Trabajo previo reusable, y la evidencia que dejó

`Isis2610-G19-Tukit-Poc/services/optimizer/nsga.py` **ya implementa un NSGA-II con pymoo**
(0.6.2) y funciona. Se reusa su cableado:

| Qué se reusa | Por qué sirve |
|---|---|
| Codificación **entera** con `IntegerRandomSampling` + `SBX` + `PM` + `RoundingRepair` | Es la misma forma que §2.2 necesita |
| **Normalización del frente antes de escalarizar** (`_normalizar_frente`) | Sin ella el costo en pesos aplasta a los demás objetivos |
| Reproducibilidad por semilla | Requisito de §6 |
| El auxiliar de **fuerza bruta** de sus pruebas | Se convierte en la línea base exacta de §6 |
| `verificar_diversidad_marca` (anti-dominancia de una sola marca) | Existe y no está conectada al optimizador; se evalúa conectarla |

### 9.1 Lo que NO se reusa: la formulación, y por qué

Sus cuatro objetivos (`costo_total`, `−fan_prom`, `−quality_prom`, `−frac_propio`) son
**sumas o promedios sobre ítems independientes**, con una variable por **ítem** y
`costo = precio × cantidad`. Eso hace el problema **completamente separable**: el óptimo del
conjunto es la suma de los óptimos por ítem, y por lo tanto la escalarización por pesos se
resuelve exactamente con un bucle, sin búsqueda.

**Sus propias pruebas lo confirman.** `test_ahorrador_coincide_con_optimo_por_fuerza_bruta`,
`test_fan_prioriza_mayor_afinidad_de_marca` y `test_premium_prioriza_mayor_calidad` afirman
que NSGA-II devuelve **exactamente** lo mismo que la fuerza bruta. Un algoritmo genético de
100 individuos por 200 generaciones que empata con fuerza bruta no está buscando nada: está
confirmando que no hacía falta buscar.

Esa es la evidencia empírica de §1.1, y llega de la suite de pruebas del propio equipo. Va al
capítulo de defectos de la memoria con ruta y nombre de prueba.

Tres defectos adicionales de ese módulo, que este spec no hereda:

- **No hay empaque.** `precio × cantidad` es el error de las doce cajas cuando la lista pedía
  doce lápices.
- **No hay tienda**, así que no hay el acoplamiento de §1.3.
- **El presupuesto se maneja duplicando el kit más barato** hasta completar tres
  (`while len(kits) < 3: kits.append(kit_mas_barato)`), de modo que el acudiente puede recibir
  tres kits idénticos presentados como tres opciones.
- `cobertura` es siempre 1,0 y su propio docstring lo admite: es un objetivo que no mide nada.

## 10. Lo que este spec NO hace

- No llena los 102 huecos de catálogo (§1.4).
- No implementa el MOKP binario; lo formula como referencia (§2.2).
- No mide costos de envío reales: `costo_fijo_t` es parámetro con barrido de sensibilidad.
- No toca la cola de revisión humana ni la máquina de estados HITL, que ya existen.
- No cambia el contrato de `GET /v1/trabajos/{id}`: los tres kits siguen saliendo con la misma
  forma, con uno marcado. Solo se agregan campos de tienda por línea.
- No introduce LangGraph. El ADR 0018 lo evaluó y lo difirió, y este spec no lo reabre.
