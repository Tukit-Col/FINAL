"""La carga del catalogo curado de `tukit/datos/catalogo/` en el esquema real.

`test_catalogo.py` prueba que el esquema sepa negarse a lo imposible. Los
`test_catalogo_curado_*` prueban lo otro, que es lo que el esquema no puede saber: que los 242 productos
que se construyeron de verdad quepan dentro de el y digan lo que prometen.

La forma de la prueba es deliberada. En vez de releer los CSV con un validador
escrito a medida, se cargan en las tablas reales con las llaves foraneas y las
restricciones CHECK activas. Asi una columna de mas, un nivel inventado o un
`curado_por` vacio no fallan por una regla que alguien escribio aqui, sino por
la misma restriccion que correra en produccion. Un validador paralelo se
desincroniza del esquema; esta carga no puede.

Los CSV los produce `Arquitectura/scripts/construir_catalogo_curado.py`, que es
reproducible byte a byte. Si estas pruebas fallan tras tocar el script, la
pregunta no es cual umbral aflojar sino que se rompio.
"""

from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
)

DATOS = Path(__file__).resolve().parents[3] / "datos" / "catalogo"

# Los cuatro entregables mas las dos tablas de apoyo que les dan sentido:
# `tiendas` para que la oferta tenga a quien apuntar y `procedencia` para que
# cada producto pueda decir de que fichero y de que posicion salio.
FICHEROS = (
    "conceptos.csv",
    "productos_canonicos.csv",
    "ofertas_tienda.csv",
    "precios_oferta.csv",
    "tiendas.csv",
    "productos_procedencia.csv",
    "revision_manual.csv",
)


def del_corpus(codigo: str) -> bool:
    """Si el concepto es uno de los 99 que midio el corpus (C001-C099).

    La curaduria de listas agrega conceptos (C100 en adelante) y los exporta a
    `conceptos.csv`. Las cifras de este archivo son mediciones de la tesis sobre
    el corpus, asi que se comprueban sobre ESOS conceptos y los curados se
    admiten aparte, en vez de romper la suite cada vez que se cura una lista.
    """
    return len(codigo) == 4 and codigo.startswith("C0") and codigo[1:].isdigit()


# El catalogo dejo de ser la salida byte-a-byte del constructor y paso a ser el
# ESPEJO de la base curada: la curadora aprobo desde el dashboard cientos de
# candidatos que la cola de revision trajo del mercado en vivo (`TK-REV-*`). Eso
# cambio la unidad sobre la que se miden los invariantes de celda.
#
# Una celda (concepto, nivel, personaje) ya no tiene UN producto sino uno
# CANONICO -el que el optimizador de kit muestra, marcado
# `es_representante_canonico`- mas, opcionalmente, PROFUNDIDAD: otras referencias
# aprobadas para esa misma celda que dan alternativas de compra pero no compiten
# por el puesto del kit. Un cuaderno confiable puede tener 20 referencias
# aprobadas detras; el kit sigue proponiendo una, la representante.
#
# Por eso las reglas de "una respuesta por celda", "los tres niveles" y "el
# precio ordena los niveles" se miden sobre los REPRESENTANTES y no sobre el
# conteo crudo de filas: es lo que el optimizador ve y lo que el papa recibe. La
# profundidad detras no puede romper una promesa que se hace sobre el
# representante. Antes de este cambio el corpus tenia un representante por celda
# por construccion y la distincion no hacia falta; ahora si.
#
# Los `TK-REV-*` que quedan como profundidad, no como representantes, se validan
# aparte: existen, cuelgan de un concepto, tienen oferta y precio en rango. Lo
# que no se les exige es acuñar el SKU por concepto/nivel (su SKU nombra la
# referencia de tienda) ni ser unicos en su celda (son, justamente, las
# alternativas).


def _representantes(cargado: Session, **filtro: Any) -> list[ProductoCanonico]:
    """Los productos que el optimizador muestra: uno por celda (concepto, nivel,
    personaje). El resto de una celda es profundidad de compra, no candidato de
    kit, y no entra en los invariantes de celda."""
    consulta = cargado.query(ProductoCanonico).filter_by(es_representante_canonico=True, **filtro)
    return consulta.all()


def _precio_minimo_por_producto(cargado: Session) -> dict[uuid.UUID, int]:
    """producto_id -> el precio mas bajo que se le vio en cualquier tienda.

    Es el que el papa pagaria: si la misma referencia esta en dos tiendas,
    compra en la barata. Es la misma regla que usa `nivelar.py` para ordenar."""
    barato: dict[uuid.UUID, int] = {}
    for oferta in cargado.query(OfertaTienda):
        for precio in cargado.query(PrecioOferta).filter_by(oferta_id=oferta.id):
            visto = barato.get(oferta.producto_canonico_id)
            if visto is None or precio.valor_centavos < visto:
                barato[oferta.producto_canonico_id] = precio.valor_centavos
    return barato


# Umbral de aceptacion medido en `construir_catalogo_curado.py` contra la
# muestra anotada a mano. Por debajo de el no se crea oferta; entre el y
# `UMBRAL_REVISION_MANUAL` la oferta se crea pero va a la cola.
UMBRAL_ACEPTACION = 0.740


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def _leer(nombre: str) -> list[dict[str, str]]:
    with (DATOS / nombre).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _nulo(valor: str) -> str | None:
    """La cadena vacia del CSV es ausencia, no es un valor.

    Importa mas de lo que parece en `ean`, que es UNIQUE y admite nulo: si las
    vacias entraran como cadena, el segundo producto sin EAN chocaria contra el
    primero y la carga fallaria por una razon falsa.
    """
    return valor if valor else None


def _bool(valor: str) -> bool | None:
    """Tres valores y no dos. `disponible` vacio es "no se", no "no hay"."""
    if valor == "":
        return None
    return valor == "true"


def _es_true(valor: str) -> bool:
    """`activo`/`es_representante_canonico` como booleano de dos valores: para
    filtrar filas del CSV crudo donde vacio o cualquier otra cosa es False."""
    return valor.strip().lower() in {"true", "1", "t"}


def _lista(valor: str) -> list[str]:
    return [p for p in valor.split("|") if p]


def _fecha(valor: str) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None


def _uuid(valor: str) -> uuid.UUID | None:
    return uuid.UUID(valor) if valor else None


# ---------------------------------------------------------------------------
# Carga en el esquema real
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def catalogo() -> dict[str, Any]:
    """Los CSV crudos, sin pasar por el ORM. Para lo que se prueba sobre texto."""
    datos = {nombre.removesuffix(".csv"): _leer(nombre) for nombre in FICHEROS}
    datos["metricas"] = json.loads((DATOS / "metricas_catalogo.json").read_text(encoding="utf-8"))
    return datos


@pytest.fixture(scope="module")
def cargado(catalogo) -> Session:
    """Los CSV dentro de las tablas reales, con FK y CHECK activas.

    Que esta fixture no reviente ya es la mitad de la prueba: significa que
    cada columna del CSV existe en el modelo con su tipo, que cada llave
    foranea resuelve y que ninguna fila viola una restriccion del esquema.
    """
    motor = create_engine("sqlite://")

    @event.listens_for(motor, "connect")
    def _activar_fk(conexion, _registro):  # noqa: ANN001
        conexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(motor)
    sesion = Session(motor)

    sesion.add_all(
        Tienda(
            id=_uuid(f["id"]),
            slug=f["slug"],
            nombre=f["nombre"],
            tipo=f["tipo"],
            url_base=_nulo(f["url_base"]),
            activa=_bool(f["activa"]),
        )
        for f in catalogo["tiendas"]
    )
    sesion.add_all(
        Concepto(
            id=_uuid(f["id"]),
            codigo=f["codigo"],
            nombre_canonico=f["nombre_canonico"],
            sinonimos=_lista(f["sinonimos"]),
            categoria=f["categoria"],
            atributos_discriminantes=_lista(f["atributos_discriminantes"]),
            atributos_descriptivos=_lista(f["atributos_descriptivos"]),
            admite_personaje=_bool(f["admite_personaje"]),
            frecuencia_demanda=int(f["frecuencia_demanda"]),
            activo=_bool(f["activo"]),
        )
        for f in catalogo["conceptos"]
    )
    sesion.flush()

    sesion.add_all(
        ProductoCanonico(
            id=_uuid(f["id"]),
            concepto_id=_uuid(f["concepto_id"]),
            ean=_nulo(f["ean"]),
            sku_interno=f["sku_interno"],
            nombre=f["nombre"],
            descripcion=_nulo(f["descripcion"]),
            marca=_nulo(f["marca"]),
            nivel=f["nivel"],
            personaje=_nulo(f["personaje"]),
            imagen_url=_nulo(f["imagen_url"]),
            atributos=json.loads(f["atributos"]),
            ruta_categoria=_nulo(f["ruta_categoria"]),
            es_propio=_bool(f["es_propio"]),
            grupo_variante_id=_uuid(f["grupo_variante_id"]),
            es_representante_canonico=_bool(f["es_representante_canonico"]),
            texto_embedding=_nulo(f["texto_embedding"]),
            quality_score=float(f["quality_score"]),
            activo=_bool(f["activo"]),
            curado_por=_uuid(f["curado_por"]),
            curado_en=_fecha(f["curado_en"]),
        )
        for f in catalogo["productos_canonicos"]
    )
    sesion.flush()

    sesion.add_all(
        OfertaTienda(
            id=_uuid(f["id"]),
            producto_canonico_id=_uuid(f["producto_canonico_id"]),
            tienda_id=_uuid(f["tienda_id"]),
            referencia_externa=f["referencia_externa"],
            url=_nulo(f["url"]),
            metodo_vinculacion=f["metodo_vinculacion"],
            confianza_vinculacion=float(f["confianza_vinculacion"]),
            disponible=_bool(f["disponible"]),
            activo=_bool(f["activo"]),
            visto_en=_fecha(f["visto_en"]),
        )
        for f in catalogo["ofertas_tienda"]
    )
    sesion.flush()

    sesion.add_all(
        PrecioOferta(
            id=_uuid(f["id"]),
            oferta_id=_uuid(f["oferta_id"]),
            valor_centavos=int(f["valor_centavos"]),
            moneda=f["moneda"],
            fuente=f["fuente"],
            vigente_desde=_fecha(f["vigente_desde"]),
            vigente_hasta=_fecha(f["vigente_hasta"]),
            corrida_id=_uuid(f["corrida_id"]),
        )
        for f in catalogo["precios_oferta"]
    )
    sesion.commit()

    yield sesion
    sesion.close()
