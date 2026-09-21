"""Funciones de aptitud: verifican que el codigo respete las fronteras declaradas.

En el sentido de Ford, Parsons y Kua, una funcion de aptitud es una prueba
automatica y continua sobre una caracteristica arquitectonica. Estas cuatro son
la diferencia entre *afirmar* que Tukit tiene contextos delimitados y
*demostrarlo* en cada integracion.

Existen porque el defecto mas grave del sistema anterior, dos servicios
declarando el maestro del mismo catalogo, no se produjo por falta de criterio
sino porque nada verificaba el criterio. La disciplina humana ya fallo una vez
en este proyecto; esta es la defensa que no depende de ella.

Van ANTES de mover la primera tabla, para que el movimiento trace las fronteras
en vez de borrarlas. Ver ADR 0014.

Ejecutar:  pytest arquitectura/ -v
"""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
MANIFIESTO = RAIZ / "arquitectura" / "manifiesto.toml"


# --------------------------------------------------------------------------
# Carga del manifiesto
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Servicio:
    nombre: str
    lenguaje: str
    ruta: Path
    paquete: str
    base_datos: str
    tablas: frozenset[str]


def _cargar():
    datos = tomllib.loads(MANIFIESTO.read_text(encoding="utf-8"))
    servicios = {
        nombre: Servicio(
            nombre=nombre,
            lenguaje=cfg["lenguaje"],
            ruta=RAIZ / cfg["ruta"],
            paquete=cfg["paquete"],
            base_datos=cfg["base_datos"],
            tablas=frozenset(cfg["tablas"]),
        )
        for nombre, cfg in datos["servicios"].items()
    }
    return datos, servicios


DATOS, SERVICIOS = _cargar()
REPLICADAS = frozenset(DATOS["meta"]["tablas_replicadas"])
REFERENCIAS_DECLARADAS = frozenset(ref["desde"] for ref in DATOS.get("referencias_cruzadas", []))

# Tabla -> servicio duenno. Las replicadas no entran: son de todos por diseno.
DUENO_DE_TABLA: dict[str, str] = {
    tabla: servicio.nombre
    for servicio in SERVICIOS.values()
    for tabla in servicio.tablas
    if tabla not in REPLICADAS
}


def _archivos_python(servicio: Servicio) -> list[Path]:
    if not servicio.ruta.exists():
        return []
    return [
        ruta
        for ruta in servicio.ruta.rglob("*.py")
        if ".venv" not in ruta.parts and "__pycache__" not in ruta.parts
    ]


def _arbol(ruta: Path) -> ast.Module | None:
    try:
        return ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    except SyntaxError:
        pytest.fail(f"{ruta.relative_to(RAIZ)} no es Python valido y no se pudo analizar.")
        return None


def _relativa(ruta: Path) -> str:
    return str(ruta.relative_to(RAIZ))


# --------------------------------------------------------------------------
# Coherencia del propio manifiesto
# --------------------------------------------------------------------------


def test_el_manifiesto_cuadra_con_el_esquema_objetivo():
    """Si el manifiesto se desincroniza del diseno, las demas pruebas validan
    contra una frontera equivocada y dan una falsa sensacion de seguridad."""
    total = sum(len(s.tablas) for s in SERVICIOS.values())
    esperado = DATOS["meta"]["total_tablas_esperado"]
    assert total == esperado, (
        f"El manifiesto declara {total} tablas y el esquema objetivo define {esperado}.\n"
        f"Si agregaste o quitaste una tabla a proposito, actualiza tambien "
        f"`total_tablas_esperado` y Arquitectura/ESQUEMA_OBJETIVO.md."
    )


def test_ninguna_tabla_tiene_dos_duenos():
    """Es exactamente el defecto que origino todo el rediseno: `productos_catalogo`
    declarada como maestro en MS-Comercio y en MS-Busqueda a la vez."""
    apariciones: dict[str, list[str]] = {}
    for servicio in SERVICIOS.values():
        for tabla in servicio.tablas:
            apariciones.setdefault(tabla, []).append(servicio.nombre)

    duplicadas = {
        tabla: duenos for tabla, duenos in apariciones.items() if len(duenos) > 1 and tabla not in REPLICADAS
    }
    assert not duplicadas, (
        "Hay tablas declaradas por mas de un servicio sin estar en "
        "`tablas_replicadas`:\n"
        + "\n".join(f"  {t}: {', '.join(d)}" for t, d in sorted(duplicadas.items()))
        + "\n\nDos duenos de la misma tabla significa que no hay dueno. Elige uno, "
        "o declarala replicada y justifica por que cada copia es necesaria."
    )


# --------------------------------------------------------------------------
# Regla 1: ningun servicio importa codigo de otro servicio
# --------------------------------------------------------------------------


def _modulos_importados(arbol: ast.Module) -> set[str]:
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            modulos.add(nodo.module)
    return modulos


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_ningun_servicio_importa_otro_servicio(nombre: str):
    """Un servicio solo puede importar de `libs/`. Importar el codigo de otro
    servicio convierte dos desplegables en uno acoplado a nivel de compilacion,
    y la separacion pasa a ser decorativa."""
    servicio = SERVICIOS[nombre]
    ajenos = {s.paquete: s.nombre for s in SERVICIOS.values() if s.nombre != nombre}

    infracciones: list[str] = []
    for ruta in _archivos_python(servicio):
        arbol = _arbol(ruta)
        if arbol is None:
            continue
        for modulo in _modulos_importados(arbol):
            raiz = modulo.split(".")[0]
            if raiz in ajenos:
                infracciones.append(f"  {_relativa(ruta)} importa `{modulo}` (de {ajenos[raiz]})")

    assert not infracciones, (
        f"El servicio `{nombre}` importa codigo de otro servicio:\n"
        + "\n".join(sorted(infracciones))
        + "\n\nLo compartido va en `libs/`. Lo que necesitas del otro dominio se "
        "pide por HTTP o llega por evento."
    )


# --------------------------------------------------------------------------
# Regla 2: ningun servicio declara una tabla de un dominio ajeno
# --------------------------------------------------------------------------


def _tablas_declaradas(arbol: ast.Module) -> list[tuple[str, int]]:
    """Busca `__tablename__ = "x"` en cualquier clase del modulo."""
    encontradas: list[tuple[str, int]] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        for destino in nodo.targets:
            if (
                isinstance(destino, ast.Name)
                and destino.id == "__tablename__"
                and isinstance(nodo.value, ast.Constant)
                and isinstance(nodo.value.value, str)
            ):
                encontradas.append((nodo.value.value, nodo.lineno))
    return encontradas


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_ningun_servicio_declara_tabla_ajena(nombre: str):
    """La regla que habria impedido el defecto original.

    Declarar el modelo de una tabla ajena es como nace un segundo maestro: al
    principio es "solo para leer", y termina escribiendo.
    """
    servicio = SERVICIOS[nombre]
    infracciones: list[str] = []

    for ruta in _archivos_python(servicio):
        arbol = _arbol(ruta)
        if arbol is None:
            continue
        for tabla, linea in _tablas_declaradas(arbol):
            if tabla in servicio.tablas:
                continue
            dueno = DUENO_DE_TABLA.get(tabla)
            if dueno:
                infracciones.append(f"  {_relativa(ruta)}:{linea} declara `{tabla}`, que pertenece a {dueno}")
            else:
                infracciones.append(
                    f"  {_relativa(ruta)}:{linea} declara `{tabla}`, que no esta en el manifiesto"
                )

    assert not infracciones, (
        f"El servicio `{nombre}` declara tablas que no le pertenecen:\n"
        + "\n".join(sorted(infracciones))
        + "\n\nSi de verdad necesitas ese dato, pidelo por HTTP o suscribete al "
        "evento. Si la tabla es nueva y es tuya, agregala al manifiesto."
    )


# --------------------------------------------------------------------------
# Regla 3: ningun servicio se conecta a la base de otro
# --------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_ningun_servicio_nombra_la_base_de_otro(nombre: str):
    """Una base por servicio. Conectarse a la base ajena salta la frontera
    entera sin pasar por ninguna interfaz, y ninguna de las otras reglas lo ve."""
    servicio = SERVICIOS[nombre]
    ajenas = {s.base_datos: s.nombre for s in SERVICIOS.values() if s.nombre != nombre and s.base_datos}
    if not ajenas:
        pytest.skip("No hay otras bases declaradas.")

    infracciones: list[str] = []
    for ruta in _archivos_python(servicio):
        for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            for base, dueno in ajenas.items():
                if base in linea:
                    infracciones.append(
                        f"  {_relativa(ruta)}:{numero} menciona la base `{base}` (de {dueno})"
                    )

    assert not infracciones, f"El servicio `{nombre}` nombra la base de datos de otro:\n" + "\n".join(
        sorted(infracciones)
    )


# --------------------------------------------------------------------------
# Regla 4: toda referencia a otro dominio esta declarada
# --------------------------------------------------------------------------


def _columnas_declaradas(arbol: ast.Module) -> list[tuple[str, str, int]]:
    """Devuelve (tabla, columna, linea) de cada `x: Mapped[...] = mapped_column(...)`
    dentro de una clase que declare `__tablename__`."""
    resultado: list[tuple[str, str, int]] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ClassDef):
            continue
        tabla = None
        for cuerpo in nodo.body:
            if isinstance(cuerpo, ast.Assign):
                for destino in cuerpo.targets:
                    if (
                        isinstance(destino, ast.Name)
                        and destino.id == "__tablename__"
                        and isinstance(cuerpo.value, ast.Constant)
                    ):
                        tabla = cuerpo.value.value
        if not tabla:
            continue
        for cuerpo in nodo.body:
            if isinstance(cuerpo, ast.AnnAssign) and isinstance(cuerpo.target, ast.Name):
                resultado.append((tabla, cuerpo.target.id, cuerpo.lineno))
    return resultado


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_toda_referencia_a_otro_dominio_esta_declarada(nombre: str):
    """Una columna `x_id` que apunta a una tabla de otro servicio es una llave
    foranea que Postgres no puede imponer. Si ademas no esta escrita en ningun
    lado, es invisible: nadie sabe que existe hasta que rompe.

    Es exactamente lo que pasaba con `kits_optimizados.items`, un JSON con
    `producto_id` adentro que para Postgres era texto.
    """
    servicio = SERVICIOS[nombre]
    sin_declarar: list[str] = []

    for ruta in _archivos_python(servicio):
        arbol = _arbol(ruta)
        if arbol is None:
            continue
        for tabla, columna, linea in _columnas_declaradas(arbol):
            if not columna.endswith("_id"):
                continue
            apuntada = columna[:-3]
            dueno = DUENO_DE_TABLA.get(apuntada)
            if dueno is None or dueno == nombre:
                continue
            clave = f"{nombre}.{tabla}.{columna}"
            if clave not in REFERENCIAS_DECLARADAS:
                sin_declarar.append(
                    f"  {_relativa(ruta)}:{linea} -> `{clave}` apunta a `{apuntada}` de {dueno}"
                )

    assert not sin_declarar, (
        f"El servicio `{nombre}` referencia otro dominio sin declararlo:\n"
        + "\n".join(sorted(sin_declarar))
        + "\n\nAgregalas a `[[referencias_cruzadas]]` en el manifiesto, con la nota "
        "de como se valida la integridad que Postgres ya no puede imponer."
    )


# --------------------------------------------------------------------------
# Regla 5: el lenguaje declarado es el que hay
# --------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_el_lenguaje_declarado_coincide_con_el_codigo(nombre: str):
    """El reparto de lenguajes salio de una medicion (ver
    Arquitectura/PERFILADO_PIPELINE.md). Si alguien mete Go donde el manifiesto
    dice Python, o al reves, la decision cambio sin que nadie la revisara."""
    servicio = SERVICIOS[nombre]
    if not servicio.ruta.exists():
        pytest.skip(f"`{nombre}` todavia no tiene codigo.")

    hay_python = bool(_archivos_python(servicio))
    hay_go = any(ruta for ruta in servicio.ruta.rglob("*.go") if "vendor" not in ruta.parts)

    if servicio.lenguaje == "python":
        assert not hay_go, (
            f"`{nombre}` esta declarado en Python y tiene archivos .go.\n"
            f"Si el cambio es deliberado, actualiza el manifiesto y escribe el ADR "
            f"que lo justifique con mediciones."
        )
    elif servicio.lenguaje == "go":
        assert not hay_python, f"`{nombre}` esta declarado en Go y tiene archivos .py."
