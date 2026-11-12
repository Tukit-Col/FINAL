"""Pruebas del auditor de campos del catalogo."""

from __future__ import annotations

from tukit_catalogo.auditar_campos import CAMPOS_OBLIGATORIOS, Hallazgo, auditar, resumir


def _producto(**cambios: str) -> dict[str, str]:
    base = {c: "x" for c in CAMPOS_OBLIGATORIOS}
    base.update({"id": "p1", "activo": "true"})
    base.update(cambios)
    return base


def test_producto_completo_sin_hallazgos() -> None:
    assert auditar([_producto()], {"p1"}) == []


def test_campo_vacio_se_reporta() -> None:
    assert auditar([_producto(imagen_url="")], {"p1"}) == [Hallazgo("p1", "imagen_url", "vacio")]


def test_nan_y_espacios_cuentan_como_vacio() -> None:
    campos = {h.campo for h in auditar([_producto(marca="nan", descripcion="  ")], {"p1"})}
    assert campos == {"marca", "descripcion"}


def test_sin_precio_se_reporta() -> None:
    hallazgos = auditar([_producto()], set())
    assert [h.campo for h in hallazgos] == ["precio"]


def test_inactivos_se_ignoran() -> None:
    for valor in ("false", "0"):
        assert auditar([_producto(activo=valor, nombre="")], set()) == []
    assert auditar([_producto(activo="false", nombre="")], set(), activos_solo=False) != []


def test_resumir_cuenta_por_campo() -> None:
    hs = [Hallazgo("a", "marca", "vacio"), Hallazgo("b", "marca", "vacio"), Hallazgo("a", "precio", "sin_oferta")]
    assert resumir(hs) == {"marca": 2, "precio": 1}
