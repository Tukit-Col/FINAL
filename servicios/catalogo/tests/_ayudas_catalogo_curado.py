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
    return len(codigo) == 4 and codigo.startswith("C0") and codigo[1:].isdigit()


def _representantes(cargado: Session, **filtro: Any) -> list[ProductoCanonico]:
    consulta = cargado.query(ProductoCanonico).filter_by(es_representante_canonico=True, **filtro)
    return consulta.all()


def _precio_minimo_por_producto(cargado: Session) -> dict[uuid.UUID, int]:
    barato: dict[uuid.UUID, int] = {}
    for oferta in cargado.query(OfertaTienda):
        for precio in cargado.query(PrecioOferta).filter_by(oferta_id=oferta.id):
            visto = barato.get(oferta.producto_canonico_id)
            if visto is None or precio.valor_centavos < visto:
                barato[oferta.producto_canonico_id] = precio.valor_centavos
    return barato


UMBRAL_ACEPTACION = 0.740


def _leer(nombre: str) -> list[dict[str, str]]:
    with (DATOS / nombre).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _nulo(valor: str) -> str | None:
    return valor if valor else None


def _bool(valor: str) -> bool | None:
    if valor == "":
        return None
    return valor == "true"


def _es_true(valor: str) -> bool:
    return valor.strip().lower() in {"true", "1", "t"}


def _lista(valor: str) -> list[str]:
    return [p for p in valor.split("|") if p]


def _fecha(valor: str) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None


def _uuid(valor: str) -> uuid.UUID | None:
    return uuid.UUID(valor) if valor else None


@pytest.fixture(scope="module")
def catalogo() -> dict[str, Any]:
    datos = {nombre.removesuffix(".csv"): _leer(nombre) for nombre in FICHEROS}
    datos["metricas"] = json.loads((DATOS / "metricas_catalogo.json").read_text(encoding="utf-8"))
    return datos


@pytest.fixture(scope="module")
def cargado(catalogo) -> Session:
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
