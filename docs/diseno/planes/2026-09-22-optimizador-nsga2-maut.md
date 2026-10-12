# Optimizador NSGA-II + MAUT — Plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para
> ejecutar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Spec:** `tukit/docs/specs/2026-09-22-optimizador-nsga2-maut-design.md`

**Goal:** Reemplazar la heurística por hogar del optimizador por un NSGA-II real cuyo frente de
Pareto sea genuino, porque el empaque compartido entre hermanos y el costo fijo por tienda
entran como parte de la decisión y no como post-proceso.

**Architecture:** La demanda de todos los hijos se agrega en **grupos** `(concepto, atributos)`
antes de optimizar. Un vector entero con un gen por grupo indexa una **oferta**
`(producto × tienda)`; las unidades salen de `⌈demanda/empaque⌉`. Tres objetivos (costo con
costo fijo por tienda, fidelidad, disponibilidad), presupuesto como restricción dura y
diversidad de marca como restricción blanda. MAUT escalariza el frente dos veces: una para
definir los tres kits, otra para recomendar uno.

**Tech Stack:** Python 3.12, pymoo 0.6.2 (NSGA2, SBX, PM, RoundingRepair,
IntegerRandomSampling), numpy, `scipy.optimize.milp` (HiGHS) para el frente exacto, pytest.

## Global Constraints

- **TDD obligatorio.** Ninguna línea de producción sin una prueba que haya fallado antes. Si
  escribiste código antes de la prueba, bórralo y empieza de nuevo.
- **`ruff` limpio** con `line-length = 110`, reglas `E,F,I,UP,B,SIM`.
- Los cinco invariantes de `tukit/arquitectura/test_fronteras.py` tienen que seguir verdes.
- **Toda referencia cruzada se declara en `arquitectura/manifiesto.toml` ANTES de escribirse en
  código**, o el invariante 4 tumba la construcción.
- `inteligencia` **no puede** importar código de `catalogo` ni conectarse a su base. Todo lo que
  necesite del catálogo viaja por HTTP.
- Vocabulario que no se puede mezclar: **nivel** de producto es `economico|confiable|premium`;
  **perfil** de kit es `Ahorrador|Fan|Premium`. Comparten la palabra "premium" y son ejes
  distintos.
- Semilla por omisión **42**, y todo resultado debe ser reproducible con ella.
- Suite completa antes de cada commit: `cd tukit && uv run pytest`.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `servicios/inteligencia/tukit_inteligencia/optimizacion/grupos.py` | Agregar renglones a grupos de demanda del hogar |
| `servicios/inteligencia/tukit_inteligencia/optimizacion/problema.py` | El `Problem` de pymoo: objetivos y restricciones |
| `servicios/inteligencia/tukit_inteligencia/optimizacion/frente.py` | Correr NSGA-II y devolver el frente |
| `servicios/inteligencia/tukit_inteligencia/optimizacion/maut.py` | Utilidades, escalarización, los 3 kits y la recomendación |
| `servicios/inteligencia/tukit_inteligencia/optimizacion/exacto.py` | Frente exacto por ε-restricción (línea base) |
| `servicios/inteligencia/tukit_inteligencia/optimizador.py` | Se conserva; pasa a orquestar y a exponer la misma API pública |

Se crea el paquete `optimizacion/` en vez de engordar `optimizador.py` (ya 483 líneas) porque
cada pieza tiene una responsabilidad y una prueba propias.

---

### Task 1: Dependencias y paquete

**Files:**
- Modify: `servicios/inteligencia/pyproject.toml`
- Create: `servicios/inteligencia/tukit_inteligencia/optimizacion/__init__.py`
- Test: `servicios/inteligencia/tests/test_dependencias_optimizacion.py`

**Interfaces:**
- Produces: el paquete `tukit_inteligencia.optimizacion` importable.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# servicios/inteligencia/tests/test_dependencias_optimizacion.py
"""Las dependencias numericas tienen que estar y con la version que el plan fija.

Se prueba el import y no la version en el pyproject porque lo que rompe la
construccion es que el modulo no este, no que el texto del archivo diga otra cosa.
"""


def test_pymoo_disponible_con_nsga2():
    from pymoo.algorithms.moo.nsga2 import NSGA2

    assert NSGA2 is not None


def test_scipy_trae_milp_para_el_frente_exacto():
    from scipy.optimize import milp

    assert milp is not None


def test_el_paquete_de_optimizacion_existe():
    import tukit_inteligencia.optimizacion as paquete

    assert paquete is not None
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_dependencias_optimizacion.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'pymoo'`

- [ ] **Step 3: Agregar las dependencias**

En `servicios/inteligencia/pyproject.toml`, dentro de `[project] dependencies`, agregar:

```toml
    "pymoo>=0.6.2,<0.7",
    "numpy>=1.26",
    "scipy>=1.12",
```

Crear `servicios/inteligencia/tukit_inteligencia/optimizacion/__init__.py`:

```python
"""El optimizador multiobjetivo: grupos de demanda, frente de Pareto y MAUT.

Vive en un paquete propio y no dentro de `optimizador.py` porque son cinco
responsabilidades con pruebas separadas, y porque el modulo viejo ya pasaba de
las 480 lineas antes de agregarles nada.
"""
```

- [ ] **Step 4: Instalar y verificar que pasa**

Run: `cd tukit && uv sync && uv run pytest servicios/inteligencia/tests/test_dependencias_optimizacion.py -v`
Expected: PASS, 3 pruebas.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/pyproject.toml servicios/inteligencia/tukit_inteligencia/optimizacion/__init__.py servicios/inteligencia/tests/test_dependencias_optimizacion.py uv.lock
git commit -m "feat(inteligencia): dependencias numericas y paquete de optimizacion"
```

---

### Task 2: Grupos de demanda del hogar

Esta es la tarea que mueve el acoplamiento adentro. Hoy `consolidar()` junta hermanos después
de elegir; aquí se agrega **antes**.

**Files:**
- Create: `servicios/inteligencia/tukit_inteligencia/optimizacion/grupos.py`
- Test: `servicios/inteligencia/tests/test_grupos_demanda.py`

**Interfaces:**
- Consumes: `Renglon` y `Candidato` de `tukit_inteligencia.optimizador`.
- Produces:
  - `@dataclass(frozen=True) Oferta` con `sku: str`, `producto_id: str | None`,
    `oferta_id: str | None`, `tienda_id: str | None`, `tienda_slug: str | None`,
    `nombre: str`, `nivel: str`, `marca: str | None`, `personaje: str | None`,
    `precio_cop: int | None`, `unidades_por_empaque: int`, `disponible: bool`.
  - `@dataclass(frozen=True) GrupoDemanda` con `clave: tuple[str, tuple[tuple[str, str], ...]]`,
    `concepto_codigo: str | None`, `descripcion: str`, `hijos: tuple[str, ...]`,
    `ordenes: tuple[tuple[str, int], ...]`, `demanda: int`, `unidad_base: str`,
    `ofertas: tuple[Oferta, ...]`.
  - `agrupar(renglones: list[Renglon]) -> tuple[list[GrupoDemanda], list[Renglon]]`, que
    devuelve los grupos comprables y los renglones informativos aparte.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/inteligencia/tests/test_grupos_demanda.py
"""La agregacion ocurre ANTES de elegir, y esa es toda la diferencia.

Si la consolidacion se hace despues de elegir el producto, las lineas son
independientes y un greedy es optimo. Estas pruebas fijan lo contrario.
"""

from tukit_inteligencia.optimizacion.grupos import agrupar
from tukit_inteligencia.optimizador import Candidato, Renglon


def _candidato(sku: str, precio: int, empaque: int = 1, nivel: str = "economico") -> Candidato:
    return Candidato(
        sku=sku,
        nombre=f"producto {sku}",
        nivel=nivel,
        precio_cop=precio,
        unidades_por_empaque=empaque,
    )


def _renglon(hijo: str, orden: int, texto: str, concepto: str, cantidad: int, **extra) -> Renglon:
    base = {
        "hijo": hijo,
        "orden": orden,
        "texto": texto,
        "tipo_item": "papeleria",
        "modo_adquisicion": "mercado_abierto",
        "cantidad": cantidad,
        "estado_resolucion": "RESUELTO_AUTO",
        "concepto_codigo": concepto,
        "candidatos": (_candidato("TK-BORR-ECO", 500, empaque=10),),
    }
    base.update(extra)
    return Renglon(**base)


def test_dos_hermanos_con_el_mismo_concepto_forman_un_solo_grupo():
    renglones = [
        _renglon("Ana", 1, "borrador", "C005", 1),
        _renglon("Luis", 1, "borrador", "C005", 1),
    ]

    grupos, informativos = agrupar(renglones)

    assert informativos == []
    assert len(grupos) == 1
    assert grupos[0].demanda == 2
    assert grupos[0].hijos == ("Ana", "Luis")


def test_atributos_distintos_no_se_mezclan_aunque_compartan_concepto():
    """Un block carta y un block oficio son el mismo concepto y NO la misma compra."""
    renglones = [
        _renglon("Ana", 1, "block carta", "C003", 1, atributos_impuestos={"tamano": "carta"}),
        _renglon("Luis", 1, "block oficio", "C003", 1, atributos_impuestos={"tamano": "oficio"}),
    ]

    grupos, _ = agrupar(renglones)

    assert len(grupos) == 2


def test_los_textos_nunca_se_agregan_entre_hermanos():
    """Dos ediciones del mismo titulo no son sustituibles. Es la regla inversa."""
    renglones = [
        _renglon("Ana", 1, "biblia", "C040", 1, tipo_item="texto"),
        _renglon("Luis", 1, "biblia", "C040", 1, tipo_item="texto"),
    ]

    grupos, _ = agrupar(renglones)

    assert len(grupos) == 2
    assert all(len(g.hijos) == 1 for g in grupos)


def test_lo_informativo_sale_aparte_y_no_forma_grupo():
    renglones = [
        _renglon("Ana", 1, "plan lector RAZ-PLUS", "C090", 1, tipo_item="licencia_digital"),
        _renglon("Ana", 2, "borrador", "C005", 1),
    ]

    grupos, informativos = agrupar(renglones)

    assert len(grupos) == 1
    assert len(informativos) == 1
    assert informativos[0].tipo_item == "licencia_digital"


def test_un_producto_con_tres_ofertas_produce_tres_ofertas_en_el_grupo():
    """El optimizador decide tienda, asi que nunca se colapsa a min(precio)."""
    candidatos = (
        Candidato(sku="TK-A", nombre="a", nivel="economico", precio_cop=1000, oferta_id="o1", tienda_id="t1"),
        Candidato(sku="TK-A", nombre="a", nivel="economico", precio_cop=1200, oferta_id="o2", tienda_id="t2"),
        Candidato(sku="TK-A", nombre="a", nivel="economico", precio_cop=900, oferta_id="o3", tienda_id="t3"),
    )
    renglones = [_renglon("Ana", 1, "cosa", "C001", 1, candidatos=candidatos)]

    grupos, _ = agrupar(renglones)

    assert len(grupos[0].ofertas) == 3
    assert {o.tienda_id for o in grupos[0].ofertas} == {"t1", "t2", "t3"}
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_grupos_demanda.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tukit_inteligencia.optimizacion.grupos'`

Nota: las pruebas usan `Candidato(..., oferta_id=..., tienda_id=...)` y `Renglon(..., atributos_impuestos=...)`,
campos que todavía no existen. Se agregan en el Step 3.

- [ ] **Step 3: Implementar lo mínimo**

Primero, en `servicios/inteligencia/tukit_inteligencia/optimizador.py`, agregar los campos
nuevos a los dos dataclasses existentes (sin tocar nada más):

```python
# dentro de @dataclass(frozen=True) class Candidato, despues de `producto_id`:
    oferta_id: str | None = None
    tienda_id: str | None = None
    tienda_slug: str | None = None
    disponible: bool = True

# dentro de @dataclass(frozen=True) class Renglon, despues de `concepto_nombre`:
    atributos_impuestos: dict[str, Any] = field(default_factory=dict)
```

Luego crear `servicios/inteligencia/tukit_inteligencia/optimizacion/grupos.py`:

```python
"""Agrega la demanda del hogar ANTES de que el optimizador elija.

El orden importa y es la diferencia entre un frente de Pareto y un adorno. Si
cada renglon se resuelve por separado y despues se junta lo repetido, las
decisiones son independientes: el optimo del conjunto es la suma de los optimos
por renglon y cualquier busqueda global sobra. Agregando primero, el empaque
compartido entra en la decision.

La regla inversa vive aqui tambien: la papeleria se agrega entre hermanos y los
textos NO, porque dos ediciones del mismo titulo no son sustituibles aunque el
titulo coincida.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..optimizador import Candidato, Renglon

# Un texto escolar nunca comparte compra entre hermanos.
TIPOS_NO_AGREGABLES = frozenset({"texto"})


@dataclass(frozen=True)
class Oferta:
    """Un producto EN UNA TIENDA a un precio. No es lo mismo que un producto.

    La distincion es la que el optimizador necesita: un mismo producto en tres
    tiendas son tres decisiones distintas, porque cada tienda que se toca suma
    su costo fijo. Colapsarlas a `min(precio)` es lo que hacia separable el
    problema.
    """

    sku: str
    nombre: str
    nivel: str
    precio_cop: int | None
    unidades_por_empaque: int = 1
    producto_id: str | None = None
    oferta_id: str | None = None
    tienda_id: str | None = None
    tienda_slug: str | None = None
    marca: str | None = None
    personaje: str | None = None
    disponible: bool = True


@dataclass(frozen=True)
class GrupoDemanda:
    """La demanda del hogar entero para una misma cosa."""

    clave: tuple[str, tuple[tuple[str, str], ...]]
    concepto_codigo: str | None
    descripcion: str
    hijos: tuple[str, ...]
    ordenes: tuple[tuple[str, int], ...]
    demanda: int
    unidad_base: str
    ofertas: tuple[Oferta, ...]


def _oferta_de(candidato: Candidato) -> Oferta:
    return Oferta(
        sku=candidato.sku,
        nombre=candidato.nombre,
        nivel=candidato.nivel,
        precio_cop=candidato.precio_cop,
        unidades_por_empaque=candidato.unidades_por_empaque,
        producto_id=candidato.producto_id,
        oferta_id=candidato.oferta_id,
        tienda_id=candidato.tienda_id,
        tienda_slug=candidato.tienda_slug,
        marca=candidato.marca,
        personaje=candidato.personaje,
        disponible=candidato.disponible,
    )


def _clave(renglon: Renglon) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Que cuenta como "la misma cosa".

    El concepto solo no alcanza: un block carta y uno oficio comparten concepto
    y son compras distintas. Los atributos impuestos entran a la clave ordenados
    para que dos renglones que pidan lo mismo en distinto orden caigan juntos.
    """
    base = renglon.concepto_codigo or f"__texto__:{renglon.texto}"
    if renglon.tipo_item in TIPOS_NO_AGREGABLES:
        # Un grupo por hijo: no se comparte ni con un hermano que pida igual.
        base = f"{base}#{renglon.hijo}"
    atributos = tuple(sorted((str(k), str(v)) for k, v in (renglon.atributos_impuestos or {}).items()))
    return (base, atributos)


def agrupar(renglones: list[Renglon]) -> tuple[list[GrupoDemanda], list[Renglon]]:
    """Separa lo informativo y agrega el resto por (concepto, atributos)."""
    informativos = [r for r in renglones if r.informativa]
    comprables = [r for r in renglones if not r.informativa]

    acumulado: dict[tuple, list[Renglon]] = {}
    for renglon in comprables:
        acumulado.setdefault(_clave(renglon), []).append(renglon)

    grupos: list[GrupoDemanda] = []
    for clave, miembros in acumulado.items():
        primero = miembros[0]
        # Las ofertas se toman del primer miembro: todos comparten concepto y
        # atributos impuestos, asi que el catalogo les dio el mismo conjunto.
        ofertas = tuple(_oferta_de(c) for c in primero.candidatos)
        grupos.append(
            GrupoDemanda(
                clave=clave,
                concepto_codigo=primero.concepto_codigo,
                descripcion=primero.texto,
                hijos=tuple(sorted({m.hijo for m in miembros})),
                ordenes=tuple((m.hijo, m.orden) for m in miembros),
                demanda=sum(m.cantidad for m in miembros),
                unidad_base=primero.unidad_base,
                ofertas=ofertas,
            )
        )
    return grupos, informativos
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_grupos_demanda.py -v`
Expected: PASS, 5 pruebas.

Run: `cd tukit && uv run pytest servicios/inteligencia -q`
Expected: la suite del servicio sigue verde (los campos nuevos tienen valor por omisión).

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/tukit_inteligencia/optimizacion/grupos.py servicios/inteligencia/tukit_inteligencia/optimizador.py servicios/inteligencia/tests/test_grupos_demanda.py
git commit -m "feat(inteligencia): grupos de demanda del hogar, agregados antes de elegir

La agregacion pasa de post-proceso a paso previo. Es lo que permite que el
empaque compartido entre hermanos influya en la decision en vez de corregirla
despues. Los textos quedan excluidos de la agregacion a proposito."
```

---

### Task 3: El problema de pymoo

**Files:**
- Create: `servicios/inteligencia/tukit_inteligencia/optimizacion/problema.py`
- Test: `servicios/inteligencia/tests/test_problema_optimizacion.py`

**Interfaces:**
- Consumes: `GrupoDemanda`, `Oferta` de `optimizacion.grupos`.
- Produces:
  - `COSTO_FIJO_TIENDA_COP: int = 8000` (parámetro de modelo, no dato medido).
  - `UTILIDAD_NIVEL: dict[str, float]`, `UTILIDAD_PERSONAJE: float`.
  - **No** define su propio cálculo de unidades: reusa `unidades_a_comprar` de
    `..optimizador`, que ya está probado. Dos definiciones del techo de la división serían dos
    sitios donde volver a equivocarse con las doce cajas.
  - `class ProblemaKit(pymoo.core.problem.Problem)` con
    `__init__(grupos, *, costo_fijo_tienda=COSTO_FIJO_TIENDA_COP, presupuesto=None, max_frac_misma_marca=0.8, personajes=())`
    y atributos `n_grupos`, `evaluar_una(x) -> dict`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/inteligencia/tests/test_problema_optimizacion.py
"""Los objetivos, y sobre todo el termino que acopla."""

import numpy as np

from tukit_inteligencia.optimizacion.grupos import GrupoDemanda, Oferta
from tukit_inteligencia.optimizacion.problema import ProblemaKit
from tukit_inteligencia.optimizador import unidades_a_comprar


def _grupo(clave: str, demanda: int, ofertas: tuple[Oferta, ...]) -> GrupoDemanda:
    return GrupoDemanda(
        clave=(clave, ()),
        concepto_codigo=clave,
        descripcion=clave,
        hijos=("Ana",),
        ordenes=(("Ana", 1),),
        demanda=demanda,
        unidad_base="unidad",
        ofertas=ofertas,
    )


def _oferta(sku, precio, tienda, empaque=1, nivel="economico", marca=None, personaje=None):
    return Oferta(
        sku=sku,
        nombre=sku,
        nivel=nivel,
        precio_cop=precio,
        unidades_por_empaque=empaque,
        oferta_id=f"of-{sku}-{tienda}",
        tienda_id=tienda,
        tienda_slug=tienda,
        marca=marca,
        personaje=personaje,
    )


def test_las_unidades_son_el_techo_de_la_division():
    """Se reusa la funcion que ya existe y ya estaba probada; no se redefine."""
    assert unidades_a_comprar(12, 12) == 1
    assert unidades_a_comprar(12, 1) == 12
    assert unidades_a_comprar(2, 10) == 1
    assert unidades_a_comprar(0, 10) == 0


def test_el_costo_fijo_por_tienda_se_cobra_una_vez_por_tienda_usada():
    grupos = [
        _grupo("A", 1, (_oferta("a1", 1000, "t1"), _oferta("a2", 1100, "t2"))),
        _grupo("B", 1, (_oferta("b1", 1000, "t1"), _oferta("b2", 1100, "t2"))),
    ]
    problema = ProblemaKit(grupos, costo_fijo_tienda=5000)

    una_tienda = problema.evaluar_una(np.array([0, 0]))  # t1 y t1
    dos_tiendas = problema.evaluar_una(np.array([0, 1]))  # t1 y t2

    assert una_tienda["costo"] == 1000 + 1000 + 5000
    assert dos_tiendas["costo"] == 1000 + 1100 + 5000 * 2


def test_dos_tiendas_pueden_perder_contra_una_aunque_cada_item_sea_mas_barato():
    """La prueba que justifica todo el spec.

    Comprar cada cosa donde es mas barata da 900+900=1800 pero toca dos tiendas
    (2 x 5000). Comprar las dos en t1 da 1000+1000=2000 con una sola (5000).
    El kit "caro por item" gana por 1200.
    """
    grupos = [
        _grupo("A", 1, (_oferta("a1", 1000, "t1"), _oferta("a2", 900, "t2"))),
        _grupo("B", 1, (_oferta("b1", 1000, "t1"), _oferta("b2", 900, "t3"))),
    ]
    problema = ProblemaKit(grupos, costo_fijo_tienda=5000)

    cada_uno_donde_es_barato = problema.evaluar_una(np.array([1, 1]))
    ambos_en_la_misma = problema.evaluar_una(np.array([0, 0]))

    assert ambos_en_la_misma["costo"] < cada_uno_donde_es_barato["costo"]


def test_el_empaque_hace_que_la_caja_compita_contra_los_sueltos():
    """Dos hermanos, un borrador cada uno: demanda 2."""
    grupos = [
        _grupo("BORR", 2, (_oferta("suelto", 500, "t1", empaque=1), _oferta("caja", 800, "t1", empaque=10))),
    ]
    problema = ProblemaKit(grupos, costo_fijo_tienda=0)

    sueltos = problema.evaluar_una(np.array([0]))
    caja = problema.evaluar_una(np.array([1]))

    assert sueltos["costo"] == 500 * 2
    assert caja["costo"] == 800 * 1
    assert caja["costo"] < sueltos["costo"]


def test_la_fidelidad_puntua_nivel_y_personaje_a_la_vez():
    """El defecto que se corrige: un producto de personaje tenia utilidad None."""
    grupos = [
        _grupo(
            "A",
            1,
            (
                _oferta("pelado", 1000, "t1", nivel="premium"),
                _oferta("spiderman", 1000, "t1", nivel="premium", personaje="spiderman"),
            ),
        ),
    ]
    problema = ProblemaKit(grupos, personajes=("spiderman",))

    sin_personaje = problema.evaluar_una(np.array([0]))
    con_personaje = problema.evaluar_una(np.array([1]))

    assert con_personaje["fidelidad"] > sin_personaje["fidelidad"]
    assert sin_personaje["fidelidad"] > 0


def test_el_presupuesto_es_una_restriccion_no_un_objetivo():
    grupos = [_grupo("A", 1, (_oferta("caro", 50000, "t1"), _oferta("barato", 1000, "t1")))]
    problema = ProblemaKit(grupos, costo_fijo_tienda=0, presupuesto=10000)

    assert problema.evaluar_una(np.array([0]))["viola_presupuesto"] > 0
    assert problema.evaluar_una(np.array([1]))["viola_presupuesto"] <= 0


def test_la_diversidad_de_marca_es_blanda_y_ordena_por_menor_violacion():
    grupos = [
        _grupo("A", 1, (_oferta("a1", 1000, "t1", marca="Norma"), _oferta("a2", 1000, "t1", marca="Scribe"))),
        _grupo("B", 1, (_oferta("b1", 1000, "t1", marca="Norma"),)),
        _grupo("C", 1, (_oferta("c1", 1000, "t1", marca="Norma"),)),
    ]
    problema = ProblemaKit(grupos, max_frac_misma_marca=0.8)

    todo_norma = problema.evaluar_una(np.array([0, 0, 0]))  # 3/3 = 1.0
    mezclado = problema.evaluar_una(np.array([1, 0, 0]))  # 2/3 = 0.67

    assert todo_norma["viola_marca"] > 0
    assert mezclado["viola_marca"] <= 0


def test_pymoo_puede_evaluar_una_poblacion_entera():
    grupos = [_grupo("A", 1, (_oferta("a1", 1000, "t1"), _oferta("a2", 900, "t2")))]
    problema = ProblemaKit(grupos)

    salida: dict = {}
    problema._evaluate(np.array([[0.0], [1.0]]), salida)

    assert salida["F"].shape == (2, 3)
    assert salida["G"].shape[0] == 2
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_problema_optimizacion.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tukit_inteligencia.optimizacion.problema'`

- [ ] **Step 3: Implementar lo mínimo**

```python
# servicios/inteligencia/tukit_inteligencia/optimizacion/problema.py
"""Los tres objetivos y las dos restricciones, en la forma que pymoo espera.

El termino que importa es el costo fijo por tienda. Sin el, cada grupo se
decide solo y el optimo del conjunto es la suma de los optimos por grupo: un
bucle lo resuelve exacto y NSGA-II sobra. Con el, la eleccion de un grupo
cambia lo que cuesta el siguiente, y ahi si hay algo que buscar.
"""

from __future__ import annotations

import numpy as np
from pymoo.core.problem import Problem

from ..optimizador import unidades_a_comprar
from .grupos import GrupoDemanda

# PARAMETRO DE MODELO, NO DATO MEDIDO. No tenemos costos de envio reales; este
# valor representa la friccion de sumar una tienda (desplazamiento, otro
# despacho, otro tiempo de espera). La evaluacion lo barre para reportar
# sensibilidad, y presentarlo como medido seria falso.
COSTO_FIJO_TIENDA_COP = 8000

# El nivel de marca describe el producto. `licencia` NO aparece aqui: el
# personaje es un eje aparte, y meterlo en esta escala fue el defecto que
# dejaba a los productos de personaje sin poder puntuar en fidelidad.
UTILIDAD_NIVEL = {"economico": 0.4, "confiable": 0.7, "premium": 1.0}
UTILIDAD_NIVEL_DESCONOCIDO = 0.15

# Ortogonal al nivel: un cuaderno de Spiderman tiene calidad Y personaje.
UTILIDAD_PERSONAJE = 1.0

# Sub-pesos dentro de fidelidad, de la P21 renormalizada sobre los tres
# criterios que describen al producto (marca 2,73 / calidad 2,55 / personaje 1,87).
PESO_CALIDAD = 0.357
PESO_PERSONAJE = 0.262
PESO_MARCA = 0.382


class ProblemaKit(Problem):
    """Un gen entero por grupo; el valor indexa una oferta (producto x tienda)."""

    def __init__(
        self,
        grupos: list[GrupoDemanda],
        *,
        costo_fijo_tienda: int = COSTO_FIJO_TIENDA_COP,
        presupuesto: int | None = None,
        max_frac_misma_marca: float = 0.8,
        personajes: tuple[str, ...] = (),
    ) -> None:
        self.grupos = [g for g in grupos if g.ofertas]
        self.costo_fijo_tienda = costo_fijo_tienda
        self.presupuesto = presupuesto
        self.max_frac_misma_marca = max_frac_misma_marca
        self.personajes = {p.lower() for p in personajes}

        self.n_grupos = len(self.grupos)
        n_slots = max((len(g.ofertas) for g in self.grupos), default=1)
        self.n_slots = n_slots

        # Tablas rectangulares (grupo x slot) para poder evaluar la poblacion
        # entera con indexado avanzado en vez de un bucle por individuo.
        self.costo_linea = np.zeros((self.n_grupos, n_slots))
        self.utilidad = np.zeros((self.n_grupos, n_slots))
        self.disponible = np.zeros((self.n_grupos, n_slots))
        self.tienda = np.full((self.n_grupos, n_slots), -1, dtype=int)
        self.marca = np.full((self.n_grupos, n_slots), -1, dtype=int)
        self.peso = np.array([max(1, g.demanda) for g in self.grupos], dtype=float)

        tiendas: dict[str, int] = {}
        marcas: dict[str, int] = {}
        xu = np.zeros(self.n_grupos)

        for i, grupo in enumerate(self.grupos):
            xu[i] = len(grupo.ofertas) - 1
            for j, oferta in enumerate(grupo.ofertas):
                unidades = unidades_a_comprar(grupo.demanda, oferta.unidades_por_empaque)
                # Una oferta sin precio no se descarta: puede ser la unica que
                # cumple el atributo que el colegio exigio. Lo que no puede es
                # ganar una comparacion de precio, y por eso entra cara.
                precio = oferta.precio_cop if oferta.precio_cop is not None else 10**9
                self.costo_linea[i, j] = precio * unidades
                self.utilidad[i, j] = self._utilidad_de(oferta)
                self.disponible[i, j] = 1.0 if (oferta.disponible and oferta.precio_cop is not None) else 0.0
                if oferta.tienda_id:
                    self.tienda[i, j] = tiendas.setdefault(oferta.tienda_id, len(tiendas))
                if oferta.marca:
                    self.marca[i, j] = marcas.setdefault(oferta.marca, len(marcas))

            # Los slots sobrantes repiten la ultima oferta real, para que un
            # indice fuera de rango nunca invente un producto que no existe.
            for j in range(len(grupo.ofertas), n_slots):
                self.costo_linea[i, j] = self.costo_linea[i, len(grupo.ofertas) - 1]
                self.utilidad[i, j] = self.utilidad[i, len(grupo.ofertas) - 1]
                self.disponible[i, j] = self.disponible[i, len(grupo.ofertas) - 1]
                self.tienda[i, j] = self.tienda[i, len(grupo.ofertas) - 1]
                self.marca[i, j] = self.marca[i, len(grupo.ofertas) - 1]

        self.n_tiendas = max(1, len(tiendas))
        self.n_marcas = max(1, len(marcas))

        super().__init__(
            n_var=self.n_grupos,
            n_obj=3,
            n_ieq_constr=2,
            xl=np.zeros(self.n_grupos),
            xu=xu,
            vtype=float,  # se redondea con RoundingRepair en los operadores
        )

    def _utilidad_de(self, oferta) -> float:
        nivel = UTILIDAD_NIVEL.get(oferta.nivel, UTILIDAD_NIVEL_DESCONOCIDO)
        pedido = oferta.personaje and oferta.personaje.lower() in self.personajes
        personaje = UTILIDAD_PERSONAJE if pedido else 0.0
        # La marca exigida por el colegio todavia no viaja en la oferta; se usa
        # el nivel como aproximacion declarada y se corrige cuando el dato exista.
        return PESO_MARCA * nivel + PESO_CALIDAD * nivel + PESO_PERSONAJE * personaje

    def _indices(self, X: np.ndarray) -> np.ndarray:
        return np.clip(np.round(X).astype(int), 0, self.n_slots - 1)

    def _metricas(self, idx: np.ndarray) -> tuple[np.ndarray, ...]:
        fila = np.arange(self.n_grupos)
        costo_items = self.costo_linea[fila, idx].sum(axis=1)

        # Cuantas tiendas distintas toca cada solucion.
        tiendas = self.tienda[fila, idx]
        usadas = np.zeros((idx.shape[0], self.n_tiendas + 1), dtype=bool)
        for t in range(self.n_tiendas):
            usadas[:, t] = (tiendas == t).any(axis=1)
        n_tiendas = usadas.sum(axis=1)

        costo = costo_items + n_tiendas * self.costo_fijo_tienda

        peso_total = self.peso.sum()
        fidelidad = (self.utilidad[fila, idx] * self.peso).sum(axis=1) / peso_total
        disponibilidad = self.disponible[fila, idx].mean(axis=1)

        # Concentracion de marca: la fraccion que tiene la marca dominante.
        marcas = self.marca[fila, idx]
        conteos = np.zeros((idx.shape[0], self.n_marcas))
        for m in range(self.n_marcas):
            conteos[:, m] = (marcas == m).sum(axis=1)
        con_marca = conteos.sum(axis=1)
        frac_dominante = np.where(con_marca > 0, conteos.max(axis=1) / np.maximum(con_marca, 1), 0.0)

        return costo, fidelidad, disponibilidad, frac_dominante

    def _evaluate(self, X, out, *args, **kwargs):
        idx = self._indices(np.atleast_2d(X))
        costo, fidelidad, disponibilidad, frac_dominante = self._metricas(idx)

        out["F"] = np.column_stack([costo, -fidelidad, -disponibilidad])

        # Restricciones en la convencion de pymoo: g(x) <= 0 es factible.
        # Declararlas asi es lo que las vuelve BLANDAS sin escribir penalizacion:
        # NSGA-II ordena las factibles primero y, si ninguna lo es, por menor
        # violacion. Un catalogo que no da para diversificar entrega el kit menos
        # concentrado posible en vez de no entregar nada.
        techo = np.inf if self.presupuesto is None else float(self.presupuesto)
        viola_presupuesto = costo - techo if np.isfinite(techo) else np.full_like(costo, -1.0)
        viola_marca = frac_dominante - self.max_frac_misma_marca
        out["G"] = np.column_stack([viola_presupuesto, viola_marca])

    def evaluar_una(self, x: np.ndarray) -> dict:
        """Una sola solucion, con los numeros legibles. Para pruebas y para explicar."""
        idx = self._indices(np.atleast_2d(x))
        costo, fidelidad, disponibilidad, frac_dominante = self._metricas(idx)
        techo = np.inf if self.presupuesto is None else float(self.presupuesto)
        return {
            "costo": int(costo[0]),
            "fidelidad": float(fidelidad[0]),
            "disponibilidad": float(disponibilidad[0]),
            "frac_marca_dominante": float(frac_dominante[0]),
            "viola_presupuesto": float(costo[0] - techo) if np.isfinite(techo) else -1.0,
            "viola_marca": float(frac_dominante[0] - self.max_frac_misma_marca),
        }
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_problema_optimizacion.py -v`
Expected: PASS, 8 pruebas.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/tukit_inteligencia/optimizacion/problema.py servicios/inteligencia/tests/test_problema_optimizacion.py
git commit -m "feat(inteligencia): problema multiobjetivo con costo fijo por tienda

Tres objetivos y dos restricciones. El costo fijo por tienda es el termino que
acopla los grupos entre si; sin el el problema se descompone. El personaje pasa
a eje propio con utilidad no nula, que corrige utilidad_por_tier['licencia']=None.
La diversidad de marca entra como restriccion de pymoo, que es blanda por como
NSGA-II ordena la violacion."
```

---

### Task 4: Correr NSGA-II y devolver el frente

**Files:**
- Create: `servicios/inteligencia/tukit_inteligencia/optimizacion/frente.py`
- Test: `servicios/inteligencia/tests/test_frente.py`

**Interfaces:**
- Consumes: `ProblemaKit`.
- Produces:
  - `PARAMETROS_NSGA: dict` con `pop_size`, `n_gen`, `prob_cruce`, `eta_mutacion`.
  - `@dataclass(frozen=True) PuntoFrente` con `x: tuple[int, ...]`, `costo: int`,
    `fidelidad: float`, `disponibilidad: float`, `factible: bool`.
  - `calcular_frente(problema: ProblemaKit, *, semilla: int = 42) -> list[PuntoFrente]`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/inteligencia/tests/test_frente.py
"""El frente tiene que ser un frente: nadie domina a nadie."""

from tukit_inteligencia.optimizacion.frente import calcular_frente
from tukit_inteligencia.optimizacion.grupos import GrupoDemanda, Oferta
from tukit_inteligencia.optimizacion.problema import ProblemaKit


def _grupo(clave, demanda, ofertas):
    return GrupoDemanda(
        clave=(clave, ()),
        concepto_codigo=clave,
        descripcion=clave,
        hijos=("Ana",),
        ordenes=(("Ana", 1),),
        demanda=demanda,
        unidad_base="unidad",
        ofertas=ofertas,
    )


def _oferta(sku, precio, tienda, nivel="economico"):
    return Oferta(
        sku=sku,
        nombre=sku,
        nivel=nivel,
        precio_cop=precio,
        oferta_id=f"of-{sku}",
        tienda_id=tienda,
        tienda_slug=tienda,
    )


def _problema_variado() -> ProblemaKit:
    grupos = [
        _grupo("A", 1, (_oferta("a-eco", 1000, "t1"), _oferta("a-pre", 5000, "t2", nivel="premium"))),
        _grupo("B", 1, (_oferta("b-eco", 1200, "t1"), _oferta("b-pre", 6000, "t2", nivel="premium"))),
        _grupo("C", 2, (_oferta("c-eco", 800, "t1"), _oferta("c-pre", 4000, "t3", nivel="premium"))),
    ]
    return ProblemaKit(grupos, costo_fijo_tienda=3000)


def test_ninguna_solucion_del_frente_domina_a_otra():
    frente = calcular_frente(_problema_variado(), semilla=42)

    def domina(p, q):
        mejor_o_igual = (
            p.costo <= q.costo and p.fidelidad >= q.fidelidad and p.disponibilidad >= q.disponibilidad
        )
        estrictamente = p.costo < q.costo or p.fidelidad > q.fidelidad or p.disponibilidad > q.disponibilidad
        return mejor_o_igual and estrictamente

    for p in frente:
        for q in frente:
            if p is not q:
                assert not domina(p, q), f"{p} domina a {q}"


def test_el_frente_tiene_mas_de_un_punto_en_un_problema_no_trivial():
    frente = calcular_frente(_problema_variado(), semilla=42)

    assert len(frente) > 1


def test_es_reproducible_con_la_misma_semilla():
    uno = calcular_frente(_problema_variado(), semilla=7)
    otro = calcular_frente(_problema_variado(), semilla=7)

    assert [p.x for p in uno] == [p.x for p in otro]


def test_un_problema_sin_grupos_da_un_frente_vacio():
    assert calcular_frente(ProblemaKit([]), semilla=42) == []


def test_un_grupo_con_una_sola_oferta_se_asigna_sin_buscar():
    problema = ProblemaKit([_grupo("A", 1, (_oferta("unico", 1000, "t1"),))], costo_fijo_tienda=0)

    frente = calcular_frente(problema, semilla=42)

    assert len(frente) == 1
    assert frente[0].costo == 1000
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_frente.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tukit_inteligencia.optimizacion.frente'`

- [ ] **Step 3: Implementar lo mínimo**

```python
# servicios/inteligencia/tukit_inteligencia/optimizacion/frente.py
"""Corre NSGA-II y devuelve el frente no dominado.

El cableado (codificacion entera con redondeo, SBX, PM, semilla) se toma de
`Isis2610-G19-Tukit-Poc/services/optimizer/nsga.py`, que ya lo tenia funcionando.
Lo que NO se toma de ahi es la formulacion: la de ese modulo tiene una variable
por item y objetivos aditivos, asi que es separable, y sus propias pruebas lo
demuestran al afirmar que empata con fuerza bruta.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.optimize import minimize

from .problema import ProblemaKit

PARAMETROS_NSGA = {"pop_size": 100, "n_gen": 200, "prob_cruce": 0.9, "eta_mutacion": 20}

# Por debajo de este numero de grupos, 200 generaciones solo agregan latencia a
# una pantalla que el acudiente esta esperando.
MIN_GEN_PROBLEMA_PEQUENO = 40


@dataclass(frozen=True)
class PuntoFrente:
    x: tuple[int, ...]
    costo: int
    fidelidad: float
    disponibilidad: float
    factible: bool


def calcular_frente(problema: ProblemaKit, *, semilla: int = 42) -> list[PuntoFrente]:
    if problema.n_grupos == 0:
        return []

    n_gen = PARAMETROS_NSGA["n_gen"]
    if problema.n_grupos < 10:
        n_gen = min(n_gen, MIN_GEN_PROBLEMA_PEQUENO)

    algoritmo = NSGA2(
        pop_size=PARAMETROS_NSGA["pop_size"],
        sampling=IntegerRandomSampling(),
        crossover=SBX(prob=PARAMETROS_NSGA["prob_cruce"], eta=15, vtype=float, repair=RoundingRepair()),
        mutation=PM(eta=PARAMETROS_NSGA["eta_mutacion"], vtype=float, repair=RoundingRepair()),
        eliminate_duplicates=True,
    )

    resultado = minimize(problema, algoritmo, ("n_gen", n_gen), seed=semilla, verbose=False)

    X = np.atleast_2d(resultado.X)
    puntos: list[PuntoFrente] = []
    vistos: set[tuple[int, ...]] = set()
    for fila in X:
        x = tuple(int(v) for v in np.clip(np.round(fila).astype(int), 0, problema.n_slots - 1))
        if x in vistos:
            continue
        vistos.add(x)
        m = problema.evaluar_una(np.array(x))
        puntos.append(
            PuntoFrente(
                x=x,
                costo=m["costo"],
                fidelidad=round(m["fidelidad"], 6),
                disponibilidad=round(m["disponibilidad"], 6),
                factible=m["viola_presupuesto"] <= 0 and m["viola_marca"] <= 0,
            )
        )
    # Orden estable por costo para que la salida no dependa del azar interno.
    return sorted(puntos, key=lambda p: (p.costo, -p.fidelidad, p.x))
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_frente.py -v`
Expected: PASS, 5 pruebas.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/tukit_inteligencia/optimizacion/frente.py servicios/inteligencia/tests/test_frente.py
git commit -m "feat(inteligencia): frente de Pareto con NSGA-II reproducible"
```

---

### Task 5: Frente exacto por ε-restricción (línea base)

**Files:**
- Create: `servicios/inteligencia/tukit_inteligencia/optimizacion/exacto.py`
- Test: `servicios/inteligencia/tests/test_exacto.py`

**Interfaces:**
- Consumes: `ProblemaKit`, `PuntoFrente`.
- Produces: `frente_exacto(problema: ProblemaKit, *, max_grupos: int = 8) -> list[PuntoFrente]`,
  que enumera exhaustivamente y devuelve solo los no dominados. Lanza `ValueError` si el
  problema excede `max_grupos`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/inteligencia/tests/test_exacto.py
"""La verdad de campo contra la que se compara NSGA-II."""

import pytest

from tukit_inteligencia.optimizacion.exacto import frente_exacto
from tukit_inteligencia.optimizacion.frente import calcular_frente
from tukit_inteligencia.optimizacion.grupos import GrupoDemanda, Oferta
from tukit_inteligencia.optimizacion.problema import ProblemaKit


def _grupo(clave, demanda, ofertas):
    return GrupoDemanda(
        clave=(clave, ()),
        concepto_codigo=clave,
        descripcion=clave,
        hijos=("Ana",),
        ordenes=(("Ana", 1),),
        demanda=demanda,
        unidad_base="unidad",
        ofertas=ofertas,
    )


def _oferta(sku, precio, tienda, nivel="economico"):
    return Oferta(
        sku=sku,
        nombre=sku,
        nivel=nivel,
        precio_cop=precio,
        oferta_id=f"of-{sku}",
        tienda_id=tienda,
        tienda_slug=tienda,
    )


def _problema_pequeno() -> ProblemaKit:
    grupos = [
        _grupo("A", 1, (_oferta("a1", 1000, "t1"), _oferta("a2", 3000, "t2", nivel="premium"))),
        _grupo("B", 1, (_oferta("b1", 1200, "t1"), _oferta("b2", 3500, "t2", nivel="premium"))),
        _grupo("C", 1, (_oferta("c1", 900, "t1"), _oferta("c2", 2800, "t3", nivel="premium"))),
    ]
    return ProblemaKit(grupos, costo_fijo_tienda=3000)


def test_el_frente_exacto_no_tiene_soluciones_dominadas():
    frente = frente_exacto(_problema_pequeno())

    for p in frente:
        for q in frente:
            if p is q:
                continue
            assert not (
                p.costo <= q.costo
                and p.fidelidad >= q.fidelidad
                and p.disponibilidad >= q.disponibilidad
                and (p.costo < q.costo or p.fidelidad > q.fidelidad or p.disponibilidad > q.disponibilidad)
            )


def test_nsga_alcanza_el_frente_exacto_en_instancias_pequenas():
    problema = _problema_pequeno()
    exacto = {(p.costo, p.fidelidad, p.disponibilidad) for p in frente_exacto(problema)}
    aproximado = {(p.costo, p.fidelidad, p.disponibilidad) for p in calcular_frente(problema, semilla=42)}

    assert aproximado <= exacto, "NSGA-II devolvio puntos que no estan en el frente real"
    assert len(aproximado) == len(exacto), "NSGA-II no encontro todo el frente real"


def test_se_niega_a_enumerar_instancias_grandes():
    grupos = [
        _grupo(f"G{i}", 1, (_oferta(f"x{i}", 100, "t1"), _oferta(f"y{i}", 200, "t2"))) for i in range(12)
    ]

    with pytest.raises(ValueError, match="grupos"):
        frente_exacto(ProblemaKit(grupos), max_grupos=8)
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_exacto.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tukit_inteligencia.optimizacion.exacto'`

- [ ] **Step 3: Implementar lo mínimo**

```python
# servicios/inteligencia/tukit_inteligencia/optimizacion/exacto.py
"""El frente verdadero, por enumeracion, para instancias chicas.

Existe para poder decir cuanto se acerca NSGA-II al frente REAL y no solo que
le gana al greedy. Una metaheuristica sin verdad de campo solo se puede comparar
contra otra metaheuristica, y eso no responde la pregunta.

Se enumera en vez de resolver un MILP por epsilon-restriccion porque con tres
objetivos y <= 8 grupos el espacio cabe (a lo sumo unos pocos miles de puntos) y
la enumeracion no puede equivocarse. El MILP volveria a hacer falta el dia que
las instancias de referencia crezcan.
"""

from __future__ import annotations

import itertools

import numpy as np

from .frente import PuntoFrente
from .problema import ProblemaKit


def _domina(p: PuntoFrente, q: PuntoFrente) -> bool:
    mejor_o_igual = p.costo <= q.costo and p.fidelidad >= q.fidelidad and p.disponibilidad >= q.disponibilidad
    estricto = p.costo < q.costo or p.fidelidad > q.fidelidad or p.disponibilidad > q.disponibilidad
    return mejor_o_igual and estricto


def frente_exacto(problema: ProblemaKit, *, max_grupos: int = 8) -> list[PuntoFrente]:
    if problema.n_grupos > max_grupos:
        raise ValueError(
            f"El frente exacto solo se enumera hasta {max_grupos} grupos; "
            f"este problema tiene {problema.n_grupos}."
        )
    if problema.n_grupos == 0:
        return []

    rangos = [range(len(g.ofertas)) for g in problema.grupos]
    candidatos: list[PuntoFrente] = []
    for combinacion in itertools.product(*rangos):
        m = problema.evaluar_una(np.array(combinacion))
        candidatos.append(
            PuntoFrente(
                x=tuple(combinacion),
                costo=m["costo"],
                fidelidad=round(m["fidelidad"], 6),
                disponibilidad=round(m["disponibilidad"], 6),
                factible=m["viola_presupuesto"] <= 0 and m["viola_marca"] <= 0,
            )
        )

    no_dominados = [p for p in candidatos if not any(_domina(q, p) for q in candidatos)]

    # Se deduplica por vector de objetivos: dos combinaciones distintas con los
    # mismos tres valores son el mismo punto del frente.
    unicos: dict[tuple, PuntoFrente] = {}
    for p in no_dominados:
        unicos.setdefault((p.costo, p.fidelidad, p.disponibilidad), p)
    return sorted(unicos.values(), key=lambda p: (p.costo, -p.fidelidad, p.x))
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_exacto.py -v`
Expected: PASS, 3 pruebas.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/tukit_inteligencia/optimizacion/exacto.py servicios/inteligencia/tests/test_exacto.py
git commit -m "feat(inteligencia): frente exacto por enumeracion como verdad de campo"
```

---

### Task 6: MAUT — los tres kits y la recomendación

**Files:**
- Create: `servicios/inteligencia/tukit_inteligencia/optimizacion/maut.py`
- Modify: `servicios/inteligencia/tukit_inteligencia/modelos/base.py` (pesos)
- Test: `servicios/inteligencia/tests/test_maut.py`

**Interfaces:**
- Consumes: `PuntoFrente`.
- Produces:
  - `PESOS_PERFIL: dict[str, dict[str, float]]` para `Ahorrador|Fan|Premium`.
  - `normalizar(frente) -> np.ndarray` (n × 3 en [0,1], ya en sentido "más es mejor").
  - `utilidad(frente, pesos) -> np.ndarray`.
  - `seleccionar_tres(frente) -> list[tuple[str, PuntoFrente, bool]]` donde el `bool` dice si
    ese perfil tuvo que desplazarse por coincidir con otro.
  - `recomendar_perfil(kits_utilidad: dict[str, float], preferencias: dict) -> tuple[str, str]`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/inteligencia/tests/test_maut.py
"""MAUT en dos momentos: define los tres kits y despues recomienda uno."""

from tukit_inteligencia.modelos import PESOS_POR_OMISION
from tukit_inteligencia.optimizacion.frente import PuntoFrente
from tukit_inteligencia.optimizacion.maut import PESOS_PERFIL, seleccionar_tres, utilidad, normalizar


def _punto(costo, fid, disp):
    return PuntoFrente(x=(0,), costo=costo, fidelidad=fid, disponibilidad=disp, factible=True)


def test_los_pesos_por_omision_son_los_de_la_p21_normalizada():
    """La P21 suma 10,00 exactos: precio 2,85 / marca 2,73 / calidad 2,55 / personaje 1,87."""
    assert PESOS_POR_OMISION == {
        "precio": 0.285,
        "marca_exigida": 0.273,
        "calidad": 0.255,
        "personaje": 0.187,
    }
    assert abs(sum(PESOS_POR_OMISION.values()) - 1.0) < 1e-9


def test_la_normalizacion_deja_todo_entre_cero_y_uno_y_mas_es_mejor():
    frente = [_punto(1000, 0.2, 0.5), _punto(5000, 0.9, 1.0)]

    U = normalizar(frente)

    assert U.min() >= 0.0 and U.max() <= 1.0
    # El mas barato tiene la mejor utilidad de costo.
    assert U[0][0] > U[1][0]
    # El de mejor fidelidad tiene la mejor utilidad de fidelidad.
    assert U[1][1] > U[0][1]


def test_un_frente_de_un_solo_punto_no_divide_por_cero():
    U = normalizar([_punto(1000, 0.5, 1.0)])

    assert U.shape == (1, 3)
    assert not (U != U).any()  # sin NaN


def test_ahorrador_toma_el_mas_barato_y_premium_el_de_mas_fidelidad():
    frente = [_punto(1000, 0.2, 1.0), _punto(3000, 0.6, 1.0), _punto(9000, 0.95, 1.0)]

    elegidos = {perfil: punto for perfil, punto, _ in seleccionar_tres(frente)}

    assert elegidos["Ahorrador"].costo == 1000
    assert elegidos["Premium"].fidelidad == 0.95


def test_si_dos_perfiles_coinciden_el_segundo_se_desplaza_y_queda_dicho():
    """Un frente de dos puntos con tres perfiles: alguien tiene que moverse."""
    frente = [_punto(1000, 0.2, 1.0), _punto(9000, 0.95, 1.0)]

    seleccion = seleccionar_tres(frente)

    assert len(seleccion) == 3
    assert any(desplazado for _, _, desplazado in seleccion)


def test_los_tres_perfiles_cargan_criterios_distintos():
    assert PESOS_PERFIL["Ahorrador"]["costo"] > PESOS_PERFIL["Premium"]["costo"]
    assert PESOS_PERFIL["Premium"]["fidelidad"] > PESOS_PERFIL["Ahorrador"]["fidelidad"]
    for pesos in PESOS_PERFIL.values():
        assert abs(sum(pesos.values()) - 1.0) < 1e-9
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_maut.py -v`
Expected: FAIL. Dos fallas distintas y las dos esperadas: `ModuleNotFoundError` para `maut`, y
`test_los_pesos_por_omision_son_los_de_la_p21_normalizada` falla contra los valores actuales
`{"precio": 0.35, "marca_exigida": 0.30, "calidad": 0.25, "personaje": 0.10}`.

- [ ] **Step 3: Corregir los pesos e implementar MAUT**

En `servicios/inteligencia/tukit_inteligencia/modelos/base.py`, reemplazar el diccionario de
pesos por omisión y su comentario:

```python
# Los pesos de la P21, puntuada por posicion sobre 60 respuestas: precio 2,85 /
# marca exigida 2,73 / calidad 2,55 / personaje 1,87. Suman 10,00 exactos, asi
# que normalizarlos es dividir por diez.
#
# Los valores anteriores (0,35 / 0,30 / 0,25 / 0,10) NO salian de la encuesta:
# exageraban la separacion y le quitaban a `personaje` casi la mitad de su peso
# real. Importa porque el argumento que sostiene el kit Fan es justamente cuanto
# pesa el personaje, y la encuesta lo pone en 0,187 y no en 0,10.
PESOS_POR_OMISION: dict[str, float] = {
    "precio": 0.285,
    "marca_exigida": 0.273,
    "calidad": 0.255,
    "personaje": 0.187,
}
```

Crear `servicios/inteligencia/tukit_inteligencia/optimizacion/maut.py`:

```python
"""Teoria de utilidad multiatributo sobre el frente.

Se usa dos veces y son dos preguntas distintas:

1. Que tres puntos del frente son los kits. Tres vectores de peso escalarizan el
   frente y su argmax es un punto. Asi los tres kits son puntos del frente POR
   CONSTRUCCION y no por etiqueta, que es lo que pide OP-01.
2. Cual de los tres se recomienda. Los pesos declarados por ESE acudiente
   escalarizan otra vez.

La agregacion es aditiva, lo que supone independencia preferencial entre los
tres atributos. El supuesto se enuncia aqui en vez de esconderse; la forma
multiplicativa se considero y no se adopto.
"""

from __future__ import annotations

import numpy as np

from ..modelos import PESOS_POR_OMISION, PerfilKit
from .frente import PuntoFrente

# Los tres vectores que DEFINEN los kits, sobre (costo, fidelidad, disponibilidad).
# No son los pesos de la encuesta: son la definicion de cada gama. La encuesta
# entra en los sub-pesos de fidelidad (ver problema.py) y en la recomendacion.
PESOS_PERFIL: dict[str, dict[str, float]] = {
    PerfilKit.AHORRADOR.value: {"costo": 0.70, "fidelidad": 0.15, "disponibilidad": 0.15},
    PerfilKit.FAN.value: {"costo": 0.20, "fidelidad": 0.65, "disponibilidad": 0.15},
    PerfilKit.PREMIUM.value: {"costo": 0.15, "fidelidad": 0.70, "disponibilidad": 0.15},
}


def normalizar(frente: list[PuntoFrente]) -> np.ndarray:
    """Utilidad por atributo en [0,1], normalizada SOBRE EL FRENTE.

    Se normaliza contra el rango observado y no contra un maximo teorico porque
    un techo inalcanzable aplasta las diferencias que si existen entre las
    opciones reales que el acudiente va a ver.
    """
    if not frente:
        return np.zeros((0, 3))

    bruto = np.array([[p.costo, p.fidelidad, p.disponibilidad] for p in frente], dtype=float)
    minimos, maximos = bruto.min(axis=0), bruto.max(axis=0)
    rango = np.where(maximos - minimos < 1e-9, 1.0, maximos - minimos)
    normalizado = (bruto - minimos) / rango
    # El costo se invierte: menos es mejor, y aqui todo queda "mas es mejor".
    normalizado[:, 0] = 1.0 - normalizado[:, 0]
    return normalizado


def utilidad(frente: list[PuntoFrente], pesos: dict[str, float]) -> np.ndarray:
    U = normalizar(frente)
    w = np.array([pesos["costo"], pesos["fidelidad"], pesos["disponibilidad"]])
    return U @ w


def seleccionar_tres(frente: list[PuntoFrente]) -> list[tuple[str, PuntoFrente, bool]]:
    """Un punto del frente por perfil. Devuelve (perfil, punto, se_desplazo).

    Si dos perfiles apuntan al mismo punto, el segundo toma el siguiente mejor
    por SU vector y se marca como desplazado. Eso no se oculta: que el kit
    Ahorrador y el Premium sean casi el mismo es informacion util para el papa.
    """
    if not frente:
        return []

    seleccion: list[tuple[str, PuntoFrente, bool]] = []
    usados: set[int] = set()
    for perfil in (PerfilKit.AHORRADOR.value, PerfilKit.PREMIUM.value, PerfilKit.FAN.value):
        puntajes = utilidad(frente, PESOS_PERFIL[perfil])
        orden = np.argsort(-puntajes)
        desplazado = False
        elegido = int(orden[0])
        for indice in orden:
            if int(indice) not in usados:
                elegido = int(indice)
                break
            desplazado = True
        else:
            desplazado = True
        usados.add(elegido)
        seleccion.append((perfil, frente[elegido], desplazado))

    orden_canonico = {p.value: i for i, p in enumerate(PerfilKit)}
    return sorted(seleccion, key=lambda t: orden_canonico[t[0]])


def recomendar_perfil(preferencias: dict) -> tuple[str, str]:
    """Cual de los tres se marca, con su razon en lenguaje llano.

    Las reglas salen de la encuesta y se aplican como priors sobre los pesos, no
    como parches sobre el resultado.
    """
    pesos = {**PESOS_POR_OMISION, **(preferencias.get("pesos") or {})}
    personajes = preferencias.get("personaje_por_hijo") or {}
    sobreprecio = float(preferencias.get("disposicion_sobreprecio") or 0.0)

    calidad_primero = pesos.get("calidad", 0) >= max(
        pesos.get("precio", 0), pesos.get("marca_exigida", 0), pesos.get("personaje", 0)
    )

    if personajes and pesos.get("personaje", 0) > 0:
        return (
            PerfilKit.FAN.value,
            "Pediste personajes para tus hijos, asi que este es el kit que los incluye.",
        )
    if calidad_primero and sobreprecio >= 0.10:
        return PerfilKit.PREMIUM.value, "Pusiste la calidad primero y aceptas pagar hasta un 10 % mas."
    return PerfilKit.AHORRADOR.value, "Elegiste precio como lo mas importante y este es el kit mas barato."
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_maut.py -v`
Expected: PASS, 6 pruebas.

Run: `cd tukit && uv run pytest servicios/inteligencia -q`
Expected: verde. Si `test_optimizador.py::TestLaRecomendacion` falla por el cambio de pesos,
**la prueba estaba fijando los valores viejos**: actualiza sus valores esperados a los de la
P21 y deja la razón escrita en el commit.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/tukit_inteligencia/optimizacion/maut.py servicios/inteligencia/tukit_inteligencia/modelos/base.py servicios/inteligencia/tests/test_maut.py
git commit -m "feat(inteligencia): MAUT define los tres kits y recomienda uno

Corrige PESOS_POR_OMISION a la P21 normalizada. Los valores que habia
(0,35/0,30/0,25/0,10) no salian de la encuesta y le quitaban a personaje casi
la mitad de su peso real (0,187)."
```

---

### Task 7: Conectar el optimizador y conservar la API pública

**Files:**
- Modify: `servicios/inteligencia/tukit_inteligencia/optimizador.py`
- Test: `servicios/inteligencia/tests/test_optimizador_nsga.py`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: `armar_los_tres(renglones, preferencias=None) -> list[KitArmado]` con la **misma
  firma y el mismo tipo de retorno de hoy**, para que `trabajos.py` y la API no cambien.
  `KitArmado.objetivos` gana `n_tiendas`, `semilla` y `tamano_frente`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/inteligencia/tests/test_optimizador_nsga.py
"""El optimizador nuevo, por la puerta publica de siempre."""

from tukit_inteligencia.optimizador import Candidato, Renglon, armar_los_tres


def _renglon(hijo, orden, texto, concepto, cantidad, candidatos):
    return Renglon(
        hijo=hijo,
        orden=orden,
        texto=texto,
        tipo_item="papeleria",
        modo_adquisicion="mercado_abierto",
        cantidad=cantidad,
        estado_resolucion="RESUELTO_AUTO",
        concepto_codigo=concepto,
        candidatos=candidatos,
    )


def _cand(sku, precio, tienda, empaque=1, nivel="economico"):
    return Candidato(
        sku=sku,
        nombre=sku,
        nivel=nivel,
        precio_cop=precio,
        unidades_por_empaque=empaque,
        oferta_id=f"of-{sku}",
        tienda_id=tienda,
        tienda_slug=tienda,
    )


def test_siempre_salen_tres_kits_con_uno_recomendado():
    renglones = [
        _renglon(
            "Ana",
            1,
            "cuaderno",
            "C001",
            2,
            (_cand("c-eco", 3000, "t1"), _cand("c-pre", 9000, "t1", nivel="premium")),
        ),
    ]

    kits = armar_los_tres(renglones, {})

    assert len(kits) == 3
    assert sum(1 for k in kits if k.recomendado) == 1
    assert {k.perfil for k in kits} == {"Ahorrador", "Fan", "Premium"}


def test_el_kit_reporta_cuantas_tiendas_toca():
    renglones = [
        _renglon("Ana", 1, "a", "C001", 1, (_cand("a1", 1000, "t1"),)),
        _renglon("Ana", 2, "b", "C002", 1, (_cand("b1", 1000, "t2"),)),
    ]

    kits = armar_los_tres(renglones, {})

    assert kits[0].objetivos["n_tiendas"] == 2


def test_las_lineas_llevan_la_tienda_de_la_que_sale_el_precio():
    renglones = [_renglon("Ana", 1, "a", "C001", 1, (_cand("a1", 1000, "t1"),))]

    kit = armar_los_tres(renglones, {})[0]
    linea = next(line for line in kit.lineas if not line.informativa)

    assert linea.elegido is not None
    assert linea.elegido.tienda_id == "t1"
    assert linea.elegido.oferta_id == "of-a1"


def test_dos_hermanos_comparten_el_empaque_y_el_total_lo_refleja():
    """Demanda 2 sobre una caja de 10: se compra UNA caja, no dos."""
    caja = _cand("caja10", 800, "t1", empaque=10)
    renglones = [
        _renglon("Ana", 1, "borrador", "C005", 1, (caja,)),
        _renglon("Luis", 1, "borrador", "C005", 1, (caja,)),
    ]

    kit = armar_los_tres(renglones, {})[0]
    comprables = [line for line in kit.lineas if not line.informativa]

    assert sum(line.unidades_a_comprar for line in comprables) == 1
    assert kit.total_cop == 800


def test_lo_informativo_se_muestra_y_no_se_cobra():
    renglones = [
        Renglon(
            hijo="Ana",
            orden=1,
            texto="RAZ-PLUS",
            tipo_item="licencia_digital",
            modo_adquisicion="plataforma",
            cantidad=1,
            estado_resolucion="RESUELTO_AUTO",
            url_externa="https://pagoslearning.com/",
        ),
        _renglon("Ana", 2, "cuaderno", "C001", 1, (_cand("c1", 3000, "t1"),)),
    ]

    kit = armar_los_tres(renglones, {})[0]

    informativa = next(line for line in kit.lineas if line.informativa)
    assert informativa.subtotal_cop is None
    assert kit.total_cop == 3000


def test_el_presupuesto_que_no_alcanza_lo_dice_en_vez_de_fallar():
    renglones = [_renglon("Ana", 1, "cuaderno", "C001", 1, (_cand("caro", 90000, "t1"),))]

    kits = armar_los_tres(renglones, {"presupuesto_por_hijo": 1000})
    recomendado = next(k for k in kits if k.recomendado)

    assert recomendado.dentro_de_presupuesto is False
    assert "presupuesto" in (recomendado.razon or "").lower()


def test_es_reproducible():
    renglones = [
        _renglon("Ana", 1, "a", "C001", 1, (_cand("a1", 1000, "t1"), _cand("a2", 2000, "t2"))),
        _renglon("Ana", 2, "b", "C002", 1, (_cand("b1", 1500, "t1"), _cand("b2", 2500, "t3"))),
    ]

    primero = armar_los_tres(renglones, {})
    segundo = armar_los_tres(renglones, {})

    assert [k.total_cop for k in primero] == [k.total_cop for k in segundo]
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_optimizador_nsga.py -v`
Expected: FAIL. `test_el_kit_reporta_cuantas_tiendas_toca` falla con `KeyError: 'n_tiendas'` y
`test_dos_hermanos_comparten_el_empaque...` puede pasar por la vía vieja; eso está bien, lo que
importa es que al menos una falle por la razón esperada antes de tocar `optimizador.py`.

- [ ] **Step 3: Reescribir `armar_los_tres` sobre las piezas nuevas**

En `servicios/inteligencia/tukit_inteligencia/optimizador.py`, reemplazar el cuerpo de
`armar_los_tres` y agregar el armado desde el frente. Conservar sin tocar:
`unidades_a_comprar`, `LineaKit`, `KitArmado`, `Renglon`, `Candidato` y la propiedad
`informativa`. **Borrar** `elegir_por_perfil` y `consolidar`, cuya responsabilidad pasa a
`grupos.py` y `problema.py`; conservar `_linea` solo para las informativas.

```python
def _linea_de_grupo(grupo, oferta, hijo: str, orden: int, cantidad: int, cobra: bool) -> LineaKit:
    """Una linea del kit. Solo la PRIMERA del grupo cobra el empaque.

    Las demas quedan en cero unidades con su explicacion en vez de borrarse: el
    acudiente pidio ese item para ese hijo y tiene que seguir viendolo.
    """
    unidades = unidades_a_comprar(grupo.demanda, oferta.unidades_por_empaque) if cobra else 0
    subtotal = None if oferta.precio_cop is None else oferta.precio_cop * unidades
    return LineaKit(
        hijo=hijo,
        orden=orden,
        descripcion=grupo.descripcion,
        tipo="papeleria",
        estado_resolucion=EstadoResolucion.RESUELTO_AUTO.value,
        cantidad_pedida=cantidad,
        unidad_base=grupo.unidad_base,
        unidades_por_empaque=oferta.unidades_por_empaque,
        unidades_a_comprar=unidades,
        informativa=False,
        elegido=Candidato(
            sku=oferta.sku,
            nombre=oferta.nombre,
            nivel=oferta.nivel,
            precio_cop=oferta.precio_cop,
            producto_id=oferta.producto_id,
            marca=oferta.marca,
            personaje=oferta.personaje,
            unidades_por_empaque=oferta.unidades_por_empaque,
            oferta_id=oferta.oferta_id,
            tienda_id=oferta.tienda_id,
            tienda_slug=oferta.tienda_slug,
            disponible=oferta.disponible,
        ),
        precio_unitario_cop=oferta.precio_cop,
        subtotal_cop=subtotal,
        mensaje=None if cobra else "Se compra junto con el de su hermano: un empaque alcanza para los dos.",
    )


def armar_los_tres(renglones: list[Renglon], preferencias: dict[str, Any] | None = None) -> list[KitArmado]:
    """Los tres kits, ahora como tres puntos de un frente de Pareto real."""
    from .optimizacion.frente import PARAMETROS_NSGA, calcular_frente
    from .optimizacion.grupos import agrupar
    from .optimizacion.maut import recomendar_perfil, seleccionar_tres
    from .optimizacion.problema import ProblemaKit

    preferencias = preferencias or {}
    semilla = int(preferencias.get("semilla") or 42)
    grupos, informativos = agrupar(renglones)

    personajes: list[str] = []
    for valores in (preferencias.get("personaje_por_hijo") or {}).values():
        personajes.extend(str(v) for v in valores)

    presupuesto = preferencias.get("presupuesto_por_hijo")
    tope = None
    if isinstance(presupuesto, int) and presupuesto > 0:
        n_hijos = len({r.hijo for r in renglones}) or 1
        sobreprecio = float(preferencias.get("disposicion_sobreprecio") or 0.0)
        tope = int(presupuesto * n_hijos * max(1.0, 1.0 + sobreprecio))

    problema = ProblemaKit(grupos, presupuesto=tope, personajes=tuple(personajes))
    frente = calcular_frente(problema, semilla=semilla)

    lineas_informativas = tuple(_linea(r, PerfilKit.AHORRADOR.value, ()) for r in informativos)

    kits: list[KitArmado] = []
    for perfil, punto, desplazado in seleccionar_tres(frente):
        lineas: list[LineaKit] = []
        for i, grupo in enumerate(problema.grupos):
            oferta = grupo.ofertas[min(punto.x[i], len(grupo.ofertas) - 1)]
            for k, (hijo, orden) in enumerate(grupo.ordenes):
                cantidad = next((r.cantidad for r in renglones if r.hijo == hijo and r.orden == orden), 1)
                lineas.append(_linea_de_grupo(grupo, oferta, hijo, orden, cantidad, cobra=(k == 0)))
        todas = tuple(lineas) + lineas_informativas
        total = sum(line.subtotal_cop or 0 for line in todas if not line.informativa)
        kits.append(
            KitArmado(
                perfil=perfil,
                total_cop=total,
                objetivos={
                    "costo": punto.costo,
                    "fidelidad": round(punto.fidelidad, 3),
                    "disponibilidad": round(punto.disponibilidad, 3),
                    "n_tiendas": len({line.elegido.tienda_id for line in lineas if line.elegido}),
                    "semilla": semilla,
                    "tamano_frente": len(frente),
                    "generaciones": PARAMETROS_NSGA["n_gen"],
                    "perfil_desplazado": desplazado,
                },
                lineas=todas,
            )
        )

    if not kits:
        return []

    elegido, razon = recomendar_perfil(preferencias)
    por_perfil = {k.perfil: k for k in kits}
    cabe = None
    if tope is not None:
        cabe = por_perfil[elegido].total_cop <= tope
        if not cabe:
            mas_barato = min(kits, key=lambda k: k.total_cop)
            if mas_barato.total_cop <= tope:
                elegido, cabe = mas_barato.perfil, True
                razon = (
                    f"El kit que pediste se pasa de tu presupuesto de ${presupuesto:,}, "
                    f"asi que te recomiendo este, que si cabe."
                )
            else:
                elegido = mas_barato.perfil
                razon = (
                    f"Ningun kit cabe en tu presupuesto de ${presupuesto:,}. "
                    f"Este es el mas barato que puedo armar."
                )

    return [
        replace(
            kit,
            recomendado=kit.perfil == elegido,
            razon=razon if kit.perfil == elegido else None,
            dentro_de_presupuesto=cabe if kit.perfil == elegido else None,
        )
        for kit in kits
    ]
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_optimizador_nsga.py -v`
Expected: PASS, 7 pruebas.

Run: `cd tukit && uv run pytest servicios/inteligencia -q`
Expected: verde. `test_optimizador.py` va a tener fallas en las clases
`TestCadaPerfilEligeLoQueDice` y `TestLaConsolidacionEntreHermanos`, que probaban
`elegir_por_perfil` y `consolidar` — funciones que ya no existen. **Bórralas y deja constancia
en el commit**; su comportamiento está cubierto por `test_grupos_demanda.py` y
`test_problema_optimizacion.py`. Las clases `TestLaCuentaDeUnidadesNoVuelveASumarCajas`,
`TestLoInformativoSeMuestraYNoSeCobra` y `TestLaRecomendacion` **tienen que seguir pasando**.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/tukit_inteligencia/optimizador.py servicios/inteligencia/tests/
git commit -m "feat(inteligencia): los tres kits salen de un frente de Pareto real

armar_los_tres conserva firma y tipo de retorno para no tocar trabajos.py ni la
API. elegir_por_perfil y consolidar desaparecen: la agregacion ocurre antes de
elegir y la eleccion la hace NSGA-II. Se borran sus pruebas, cubiertas ahora por
test_grupos_demanda y test_problema_optimizacion."
```

---

### Task 8: La prueba de falsación

La tarea que puede demostrar que el diseño estaba mal, y por eso existe.

**Files:**
- Create: `servicios/inteligencia/tests/test_falsacion_acoplamiento.py`

- [ ] **Step 1: Escribir la prueba**

```python
# servicios/inteligencia/tests/test_falsacion_acoplamiento.py
"""La prueba contra nosotros mismos.

Afirmacion a sostener: NSGA-II le gana al greedy PORQUE el problema esta
acoplado. Si con el acoplamiento apagado el greedy NO empata, entonces la
ventaja venia de otro lado y la formulacion esta mal. Un experimento que no
puede salir mal no demuestra nada.
"""

import numpy as np

from tukit_inteligencia.optimizacion.frente import calcular_frente
from tukit_inteligencia.optimizacion.grupos import GrupoDemanda, Oferta
from tukit_inteligencia.optimizacion.maut import PESOS_PERFIL, utilidad
from tukit_inteligencia.optimizacion.problema import ProblemaKit


def _grupo(clave, demanda, ofertas):
    return GrupoDemanda(
        clave=(clave, ()),
        concepto_codigo=clave,
        descripcion=clave,
        hijos=("Ana",),
        ordenes=(("Ana", 1),),
        demanda=demanda,
        unidad_base="unidad",
        ofertas=ofertas,
    )


def _oferta(sku, precio, tienda, nivel="economico"):
    return Oferta(
        sku=sku,
        nombre=sku,
        nivel=nivel,
        precio_cop=precio,
        oferta_id=f"of-{sku}",
        tienda_id=tienda,
        tienda_slug=tienda,
    )


def _grupos_de_prueba():
    return [
        _grupo("A", 1, (_oferta("a1", 1000, "t1"), _oferta("a2", 900, "t2", nivel="premium"))),
        _grupo("B", 1, (_oferta("b1", 1200, "t1"), _oferta("b2", 1100, "t3", nivel="premium"))),
        _grupo("C", 1, (_oferta("c1", 800, "t1"), _oferta("c2", 700, "t2", nivel="premium"))),
    ]


def _greedy(problema: ProblemaKit, pesos: dict[str, float]) -> float:
    """Elige la mejor oferta de cada grupo por separado. El sistema de antes."""
    x = []
    for i, grupo in enumerate(problema.grupos):
        mejor, mejor_puntaje = 0, -np.inf
        for j in range(len(grupo.ofertas)):
            prueba = [0] * problema.n_grupos
            prueba[i] = j
            m = problema.evaluar_una(np.array(prueba))
            puntaje = -pesos["costo"] * m["costo"] + pesos["fidelidad"] * m["fidelidad"] * 1e4
            if puntaje > mejor_puntaje:
                mejor, mejor_puntaje = j, puntaje
        x.append(mejor)
    m = problema.evaluar_una(np.array(x))
    return m["costo"]


def test_sin_acoplamiento_el_greedy_empata_con_nsga():
    """costo_fijo=0: el problema se descompone y el greedy es optimo."""
    problema = ProblemaKit(_grupos_de_prueba(), costo_fijo_tienda=0)
    pesos = PESOS_PERFIL["Ahorrador"]

    frente = calcular_frente(problema, semilla=42)
    mejor_nsga = min(p.costo for p in frente)
    mejor_greedy = _greedy(problema, pesos)

    assert mejor_nsga == mejor_greedy, (
        "Sin acoplamiento el greedy deberia igualar a NSGA-II. Si no lo hace, "
        "la ventaja no viene del acoplamiento y la formulacion esta mal."
    )


def test_con_acoplamiento_nsga_encuentra_algo_que_el_greedy_no():
    """costo_fijo alto: elegir por separado manda al papa a tres tiendas."""
    problema = ProblemaKit(_grupos_de_prueba(), costo_fijo_tienda=5000)
    pesos = PESOS_PERFIL["Ahorrador"]

    frente = calcular_frente(problema, semilla=42)
    mejor_nsga = min(p.costo for p in frente)
    mejor_greedy = _greedy(problema, pesos)

    assert mejor_nsga < mejor_greedy, (
        "Con costo fijo por tienda, NSGA-II deberia encontrar una combinacion "
        "mas barata que la de elegir cada grupo por separado."
    )
```

- [ ] **Step 2: Correr**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_falsacion_acoplamiento.py -v`
Expected: PASS las dos.

**Si `test_con_acoplamiento...` falla**, el acoplamiento no está teniendo efecto: revisa que
`costo_fijo_tienda` esté llegando al cálculo y que las ofertas de prueba tengan tiendas
distintas. **Si `test_sin_acoplamiento...` falla**, es el hallazgo importante: para, no lo
"arregles" subiendo generaciones, y reporta que la formulación tiene una ventaja que no viene
del acoplamiento.

- [ ] **Step 3: Commit**

```bash
cd tukit
git add servicios/inteligencia/tests/test_falsacion_acoplamiento.py
git commit -m "test(inteligencia): falsacion del argumento de acoplamiento

Con costo_fijo=0 el greedy debe empatar con NSGA-II; con costo fijo alto, no.
Si la primera falla, la contribucion no es el acoplamiento."
```

---

### Task 9: Esquema, manifiesto y migración

**Files:**
- Modify: `arquitectura/manifiesto.toml`
- Modify: `servicios/inteligencia/tukit_inteligencia/modelos/kit.py`
- Create: `servicios/inteligencia/migraciones/versions/<hash>_tienda_en_la_linea_de_kit.py`
- Test: `servicios/inteligencia/tests/test_linea_kit_tienda.py`

**El orden importa:** el manifiesto **primero**, o `test_fronteras.py` falla.

- [ ] **Step 1: Declarar las referencias cruzadas en el manifiesto**

En `arquitectura/manifiesto.toml`, junto a las demás de `inteligencia`:

```toml
[[referencias_cruzadas]]
desde = "inteligencia.linea_kit.oferta_id"
hacia = "catalogo.oferta_tienda"
nota = """
De que oferta concreta sale el precio. Sin ella el kit no puede decir en que
tienda se compra cada cosa, y el costo fijo por tienda que el optimizador cobra
no seria auditable contra el catalogo.
"""

[[referencias_cruzadas]]
desde = "inteligencia.linea_kit.tienda_id"
hacia = "catalogo.tienda"
nota = "Denormalizada desde la oferta para poder agrupar por tienda sin salir del servicio."
```

- [ ] **Step 2: Escribir la prueba que falla**

```python
# servicios/inteligencia/tests/test_linea_kit_tienda.py
"""El kit tiene que poder decir en que tienda se compra cada linea."""

from tukit_inteligencia.modelos import LineaKit


def test_la_linea_declara_oferta_y_tienda():
    columnas = {c.name for c in LineaKit.__table__.columns}

    assert "oferta_id" in columnas
    assert "tienda_id" in columnas
```

- [ ] **Step 3: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_linea_kit_tienda.py -v`
Expected: FAIL con `AssertionError` sobre `oferta_id`.

- [ ] **Step 4: Agregar las columnas y la migración**

En `servicios/inteligencia/tukit_inteligencia/modelos/kit.py`, dentro de `class LineaKit`,
después de `producto_canonico_id`:

```python
    # Referencias logicas a catalogo, declaradas en el manifiesto. Van como UUID
    # sin llave foranea porque el catalogo vive en otra base.
    oferta_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    tienda_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
```

Generar la migración:

```bash
cd tukit
uv run alembic -c servicios/inteligencia/alembic.ini revision --autogenerate -m "tienda en la linea de kit"
```

Revisar el archivo generado: debe traer dos `op.add_column` sobre `linea_kit` y nada más.

- [ ] **Step 5: Correr y verificar que pasa**

```bash
cd tukit
uv run pytest servicios/inteligencia/tests/test_linea_kit_tienda.py -v
make bd-migrar
make bd-deriva
uv run pytest arquitectura -q
```
Expected: prueba en verde, migración aplicada, **sin deriva**, y los cinco invariantes verdes.

- [ ] **Step 6: Commit**

```bash
cd tukit
git add arquitectura/manifiesto.toml servicios/inteligencia/tukit_inteligencia/modelos/kit.py servicios/inteligencia/migraciones/versions/ servicios/inteligencia/tests/test_linea_kit_tienda.py
git commit -m "feat(inteligencia): oferta_id y tienda_id en linea_kit

Referencias cruzadas declaradas en el manifiesto antes del codigo, como exige
el invariante 4."
```

---

### Task 10: ADR 0020 y cierre

**Files:**
- Create: `Arquitectura/adr/0020-formulacion-del-optimizador-multiobjetivo.md` (fuera del submódulo)
- Modify: `Arquitectura/ARQUITECTURA.md` (tabla §4)

- [ ] **Step 1: Escribir el ADR**

Formato Nygard, siguiendo la forma de `Arquitectura/adr/0005-*.md`. Contenido obligatorio:

- **Contexto:** el optimizador anterior elegía por línea y consolidaba después, lo que hace el
  problema separable; evidencia de `Isis2610-G19-Tukit-Poc` cuyas propias pruebas afirman que
  NSGA-II empata con fuerza bruta.
- **Decisión:** grupos de demanda del hogar, gen entero por grupo indexando una oferta
  (producto × tienda), costo fijo por tienda dentro del objetivo de costo, tres objetivos,
  presupuesto duro y diversidad de marca blanda.
- **Alternativa rechazada:** MOKP binario `x_ij ∈ {0,1}` por línea × candidato — más fiel a la
  literatura que cita el VFP, pero espacio mucho mayor y necesita operadores de reparación.
- **Alternativa rechazada:** número de tiendas como cuarto objetivo en vez de costo fijo.
- **Consecuencias:** dos referencias cruzadas nuevas; `costo_fijo_tienda` es parámetro de
  modelo y no dato medido, con barrido de sensibilidad obligatorio en la evaluación.

- [ ] **Step 2: Actualizar la tabla del §4 de `ARQUITECTURA.md`**

Agregar la fila del ADR 0020 con estado `aceptada`.

- [ ] **Step 3: Verificación final**

```bash
cd tukit
uv run pytest
uv run ruff check .
make bd-deriva
```
Expected: suite completa verde, ruff limpio, sin deriva en las tres bases.

- [ ] **Step 4: Commit**

```bash
cd /Users/mariapaula.rodriguez/Documents/university/TUKIT
git add Arquitectura/adr/0020-formulacion-del-optimizador-multiobjetivo.md Arquitectura/ARQUITECTURA.md
git commit -m "docs(adr): 0020 formulacion del optimizador multiobjetivo"
```

---

## Qué queda fuera de este plan

- La medición completa sobre las 175 listas y los hogares sintéticos (hipervolumen,
  sensibilidad a `costo_fijo_tienda`, tiempos). Es un trabajo de evaluación con su propio
  guion y va después de que el algoritmo esté verde.
- Que `catalogo` devuelva ofertas en vez de `min(precio)`: lo entrega el plan del OE3. Mientras
  tanto, este plan funciona porque `Candidato` ya acepta `oferta_id` y `tienda_id`, y las
  pruebas los pasan a mano.
- El MOKP binario, que se documenta en el ADR y no se implementa.
