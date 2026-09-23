# `OP-03` frente a `NR-07`: en qué consiste el choque y tres redacciones que lo cierran

- **Tipo:** preparación de decisión. **No decide nada.** Formula el problema y pone las opciones con
  su consecuencia, para que la decisión se tome con el material delante.
- **Fecha:** 2026-09-22.
- **Línea base:** `Arquitectura/SRS_ISIS2610G19_v6.docx`.

> # ✅ DECIDIDO — se aplicó la alternativa B
>
> La usuaria eligió la **alternativa B** y está incorporada al v6: la descripción de `OP-03` pasó a
> acotar el flujo **de extremo a extremo** y remite a `DP-03`, `DP-04` y `DP-06` para los topes por
> etapa; y nació **`DP-06`** en §3.9 con un tope de **30 s** para el camino corto sobre lista
> validada, **declarándose provisional** en su propia descripción y en su criterio, porque el valor es
> derivado y no medido. Este documento queda como el registro del razonamiento y de las dos
> alternativas descartadas. Ver `tukit/docs/CIERRE_V6.md` §1.
- **Insumo:** los textos literales de `OP-03`, `DP-03`, `DP-04` y `NR-07` tal como están en el v5.

---

## 0. La respuesta corta a la lectura preliminar

**Tu lectura es correcta en lo esencial y hay que precisarla en dos puntos, uno de los cuales
corrige lo que yo mismo reporté antes.**

Correcta: `OP-03` y `NR-07` **no miden el mismo flujo**, y la salida natural es que cada camino
declare el suyo. Eso se sostiene al leer los textos.

Primera precisión, y es una corrección a mi informe anterior: dije que los dos requisitos *"se
contradicen"*. **No se contradicen, porque `NR-07` no fija ningún número.** Su criterio dice *"El
segundo trabajo se completa en un orden de magnitud menos de tiempo que el primero"*, que es una
medida **relativa**. Dos requisitos no pueden contradecirse en una cifra cuando solo uno tiene
cifra. Lo que ocurre es más sutil y sigue siendo un problema: `NR-07` vuelve **inútil** el número
de `OP-03` como promesa al acudiente, porque el mismo requisito cubre dos caminos que difieren en
un factor de diez, y el contrato anuncia un solo `estimado_segundos`.

Segunda precisión, y es el hallazgo que importa: **el choque más grave no es entre `OP-03` y
`NR-07`, es dentro de `OP-03`.** Su descripción y su criterio de aceptación tienen alcances
distintos, y la diferencia entre los dos alcances es de un factor de casi cuarenta. Eso no lo
introdujo `NR-07`: viene del v3 y nadie lo había mirado.

---

## 1. El choque, con los textos delante

Estos son los cuatro requisitos que hoy hablan del tiempo, citados del v5:

| REQ | Alcance que declara | Cifra |
|---|---|---|
| **`OP-03`** *descripción* | *"El **motor** debe generar los 3 kits en un tiempo razonable que no afecte negativamente la experiencia del padre."* | ninguna |
| **`OP-03`** *criterio* | *"Tope máximo de 5 minutos **de extremo a extremo** (peor caso), con progreso visible por etapa…"* | **300 s** |
| **`DP-03`** | *"El **motor de optimización** multiobjetivo debe completar la generación de los tres kits… medido desde que la lista está normalizada hasta que los tres kits están disponibles."* | **p95 ≤ 8 s** |
| **`DP-04`** | *"El **módulo de percepción** debe completar la extracción de una lista de un grado…"* | **p95 ≤ 12 s/página, ≤ 45 s/lista** |
| **`NR-07`** *criterio* | *"El segundo trabajo se completa en **un orden de magnitud menos de tiempo que el primero**."* | relativa |

De esa tabla salen tres defectos, en orden de gravedad.

**Primero: `OP-03` se contradice consigo mismo.** Su descripción acota **el motor**; su criterio
acota **el flujo de extremo a extremo**. No son lo mismo: el motor son 8 segundos y el flujo son
300. Un requisito cuyo enunciado normativo y cuyo criterio de aceptación miden objetos distintos
no es verificable, porque no se sabe qué hay que medir para aprobarlo. Y su columna `Módulo` dice
`Optimización`, que es coherente con la descripción y no con el criterio.

**Segundo: la descripción de `OP-03` duplica `DP-03`.** Los dos dicen, en distintas palabras, que
el motor debe generar los tres kits en un tiempo acotado. `DP-03` lo dice con una cifra medible y
`OP-03` sin cifra. Es un solapamiento que la consolidación creó sin querer: el cambio E-18 dio a
`DP-03` el número del optimizador, tomándolo de §2.4.3, y nadie volvió a leer `OP-03` para
re-encuadrarlo. De los ocho duplicados que E-23 identificó, este no estaba.

**Tercero, y es el que tu lectura nombra: nadie declara el presupuesto del camino corto.** `NR-07`
crea un camino que se salta percepción, normalización y resolución, y lo acota solo por comparación
con el camino largo. Como consecuencia práctica, el contrato tiene un solo `estimado_segundos` para
los dos, y la pantalla de espera miente en el caso bueno, que es justo el que el proyecto quiere
demostrar.

### 1.1 Cuánto vale realmente cada camino

Con `DP-03` y `DP-04` ya medidos, el presupuesto se puede repartir en vez de suponerlo:

| Etapa | Camino largo | Camino corto (`NR-07`) |
|---|---:|---|
| Percepción (`DP-04`) | ≤ 45 s | **no se ejecuta** |
| Normalización y resolución | el resto | **no se ejecuta**, se lee del artefacto |
| Optimización (`DP-03`) | ≤ 8 s | ≤ 8 s |
| Lectura del artefacto validado | — | una consulta a base de datos |
| **Total** | **≤ 300 s** (`OP-03`) | **≈ 10 s, sin requisito que lo diga** |

Y aquí hay una coincidencia que conviene aprovechar en la redacción, porque hace que las dos
formas de acotar el camino corto digan lo mismo: **30 segundos es exactamente un orden de magnitud
por debajo de los 300 de `OP-03`.** Si el camino corto se acota en 30 s, el criterio relativo de
`NR-07` —*"un orden de magnitud menos"*— queda satisfecho por construcción y deja de depender de
lo que tardó el primer trabajo, que es una base de comparación que varía con el documento.

---

## 2. Tres redacciones que lo cierran

Las tres arreglan el defecto interno de `OP-03`, porque ninguna decisión sensata lo deja como está.
Se diferencian en dónde ponen los números.

### Alternativa A — `OP-03` se re-encuadra como el requisito del flujo y declara los dos caminos

`OP-03` deja de hablar del motor y pasa a hablar del flujo, alineando su descripción con el
criterio que ya tiene. Los dos caminos entran en el mismo requisito.

> **`OP-03` — Tiempo del flujo hasta los tres kits.** *Tipo:* RNF.
>
> **Descripción:** El sistema debe entregar los tres kits en un tiempo acotado y con progreso
> visible por etapa, con dos presupuestos según el camino que el trabajo tome. El **camino
> completo**, que ejecuta las cuatro etapas del pipeline sobre un documento nuevo, tiene un tope de
> **5 minutos de extremo a extremo** en el peor caso. El **camino corto**, que reutiliza la
> resolución validada de `NR-07` y arranca en la optimización, tiene un tope de **30 segundos**. El
> sistema debe anunciarle al acudiente el presupuesto del camino que su trabajo va a tomar, y no
> uno único para los dos.
>
> **Criterio de aceptación:** Sobre el corpus de listas anotadas, el camino completo cumple el tope
> de 300 s de extremo a extremo y el camino corto el de 30 s, los dos medidos como p95 y con el
> progreso por etapa verificable en la respuesta. Los hiperparámetros del motor se versionan como
> configuración y no requieren desplegar código.

**Consecuencia.** El contrato puede anunciar `estimado_segundos` por camino sin inventar nada.
`NR-07` conserva su criterio relativo y gana un techo absoluto coherente con él. Desaparece el
solapamiento con `DP-03`, porque `OP-03` ya no habla del motor.
**Costo.** La columna `Módulo` de `OP-03` deja de ser `Optimización` y pasa a ser transversal, lo
que mueve su fila del Anexo C. Y el número del camino corto, 30 s, **no está medido**: habría que
medirlo o declararlo provisional como se hizo con `DP-04`.
**Riesgo.** Concentra dos promesas en un requisito; si un camino falla y el otro no, el requisito
queda a medias y hay que decir cuál mitad falló.

### Alternativa B — `OP-03` se corrige mínimamente y nace `DP-06` para el camino corto

`OP-03` se toca solo para que su descripción diga lo que su criterio ya dice. El camino corto se
va a §3.9, que es donde ya viven `DP-02` a `DP-05`.

> **`OP-03`** — se sustituye únicamente la descripción: *"El sistema debe entregar los tres kits en
> un tiempo que no afecte negativamente la experiencia del padre, medido de extremo a extremo y con
> progreso visible por etapa."* El criterio no cambia.
>
> **`DP-06` — Tiempo del camino corto sobre lista validada.** *Tipo:* RNF.
> **Descripción:** Un trabajo que reutiliza la resolución validada de `NR-07` y arranca en la etapa
> de optimización debe completarse con un p95 ≤ 30 s, medido desde la creación del trabajo hasta
> que los tres kits están disponibles.
> **Razón:** El camino corto no ejecuta percepción, normalización ni resolución: su costo es una
> lectura del artefacto más la optimización, que `DP-03` acota en 8 s. Un tope de 30 s es holgado
> sobre ese presupuesto y es exactamente un orden de magnitud por debajo del tope del camino
> completo, de modo que satisface el criterio relativo de `NR-07` por construcción y no por
> coincidencia.
> **Criterio de aceptación:** Ejecutado el mismo grado dos veces con dos hogares distintos, el
> segundo trabajo cumple p95 ≤ 30 s sobre al menos diez repeticiones. **MoSCoW:** Should. **Ver.:** v1.

**Consecuencia.** Cada camino tiene su requisito, su número y su fila. §3.9 queda como el único
sitio con umbrales de tiempo, que es coherente con lo que ya hace. `OP-03` conserva su tope de 5
minutos, que es la cifra que el contrato cita y que el equipo ya tiene interiorizada. `NR-07` no se
toca.
**Costo.** Un requisito más: el documento pasa de 131 a 132, con su fila en el Anexo C. `DP-06`
entra como `Should` porque hereda la prioridad de `NR-07`, que es `Should`: no se puede exigir el
tiempo de un camino que puede no construirse.
**Ventaja.** Es el cambio más pequeño que arregla los tres defectos, y el que menos reescribe.

### Alternativa C — `OP-03` se vuelve cualitativo y todas las cifras se van a §3.9

`OP-03` conserva solo la promesa de experiencia y cede el número.

> **`OP-03`** — *"El sistema debe entregar los tres kits en un tiempo que no afecte negativamente la
> experiencia del padre, con progreso visible por etapa mientras dura el procesamiento."* Criterio:
> *"El acudiente ve el avance por etapa en todo momento y ninguna etapa queda sin reportar. Los
> topes de tiempo se especifican en §3.9."*
>
> Y §3.9 recibe **`DP-06`** (camino corto, ≤ 30 s) y **`DP-07`** (camino completo, ≤ 300 s).

**Consecuencia.** Un solo lugar con todos los umbrales de tiempo: `DP-03` el motor, `DP-04` la
percepción, `DP-06` el camino corto, `DP-07` el completo, `DP-05` la escalabilidad. Es la
organización más limpia de las tres y la que un evaluador recorre más rápido.
**Costo.** El más alto. `OP-03` pierde el tope de 5 minutos, y ese número está citado en
`CONTRATO_API.md` §0 como fundamento de que la API sea asíncrona; habría que reapuntar esa cita a
`DP-07`, y el contrato lo posee otro agente. Además `DP-04` cita hoy a `OP-03` como su cota
superior y habría que reapuntarlo también.
**Riesgo.** Es un cambio de estructura en el documento a cambio de una mejora de orden. Vale si se
va a reorganizar §3.9 de todas formas; no vale por sí solo.

---

## 3. Lo que recomendaría, y por qué

**La alternativa B**, por tres razones y con una reserva.

Arregla los tres defectos —la inconsistencia interna de `OP-03`, el solapamiento con `DP-03` y la
ausencia de presupuesto del camino corto— tocando una sola oración de un requisito existente y
añadiendo uno nuevo. Respeta la estructura que el documento ya tiene, donde §3.9 concentra los
umbrales de desempeño y los módulos enuncian capacidades. Y no toca ninguna cifra que esté citada
fuera del SRS, de modo que no crea trabajo en `CONTRATO_API.md`, que es el archivo que no podemos
editar y que otro agente está moviendo.

**La reserva, y conviene tenerla presente al decidir:** los 30 segundos de `DP-06` son un número
**derivado, no medido**. Se sostiene sobre los 8 s medidos de `DP-03` más una lectura de base de
datos, con holgura. Es la misma clase de cifra que `DP-04` tenía antes de medirla, y por eso
`DP-06` debería nacer con la misma honestidad: declarando que el valor se re-mide en cuanto el
camino corto exista, y que hasta entonces es provisional. La diferencia con `DP-04` es que aquí no
hay corpus que medir, porque `NR-07` todavía no está construido.

Si la decisión fuera **A**, la única objeción sería de forma y no de fondo: concentrar dos promesas
con dos números en un requisito hace más difícil decir cuál falló. Si fuera **C**, conviene
agruparla con la reorganización de §3.9 y no hacerla sola.

---

## 4. Lo que hay que decidir, en una línea

¿El presupuesto de tiempo del camino corto vive **dentro de `OP-03`** (A), en un **`DP-06` propio**
(B), o se **reorganiza §3.9 completa** moviendo también el tope de 5 minutos (C)? En los tres casos
hay que corregir la descripción de `OP-03`, que hoy acota el motor y cuyo criterio acota el flujo.
Eso no es opcional en ninguna de las tres.
