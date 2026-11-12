"""Pruebas del auditor de campos del catalogo."""

from __future__ import annotations

from tukit_catalogo.auditar_campos import (
    CAMPOS_OBLIGATORIOS,
    CAMPOS_RECOMENDADOS,
    Hallazgo,
    auditar,
    main,
    resumir,
)


def _producto(**cambios: str) -> dict[str, str]:
    base = {c: "x" for c in (*CAMPOS_OBLIGATORIOS, *CAMPOS_RECOMENDADOS)}
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


def _csv(datos, nombre, filas):
    import csv

    with (datos / f"{nombre}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def _datos(tmp_path, **cambios):
    _csv(tmp_path, "productos_canonicos", [_producto(**cambios)])
    _csv(tmp_path, "ofertas_tienda", [{"id": "o1", "producto_canonico_id": "p1"}])
    _csv(tmp_path, "precios_oferta", [{"oferta_id": "o1", "valor_centavos": "100"}])
    return ["--datos", str(tmp_path), "--informe", str(tmp_path / "i.md"), "--estricto"]


def test_estricto_falla_con_campo_obligatorio_vacio(tmp_path) -> None:
    assert main(_datos(tmp_path, marca="")) == 1


def test_estricto_tolera_recomendados_vacios(tmp_path, capsys) -> None:
    assert main(_datos(tmp_path, descripcion="", texto_embedding="")) == 0
    assert "ADVERTENCIA" in capsys.readouterr().out
