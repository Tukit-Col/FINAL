"""Las perturbaciones son deterministas, conservan la etiqueta en un conjunto fijo y no hay fuga entre particiones."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import aumentacion as a  # noqa: E402
import barrido as b  # noqa: E402
import clasificacion as k  # noqa: E402
from robustez import similitud  # noqa: E402
from particion import SEMILLA_BASE, partir  # noqa: E402

pytestmark = pytest.mark.skipif(not (k.DATOS / "renglones_etiquetados.csv").exists(), reason="faltan los datos exportados")

# Perturbaciones que, por construccion, no cambian la palabra que decide el concepto (la cabeza).
CONSERVADORAS = ["tipeo", "tildes", "mayusculas", "plural", "ocr", "espacios", "sufijo", "marca"]


@pytest.fixture(scope="module")
def cx() -> b.Contexto:
    return b.Contexto(con_vectores=False)


def _conjunto_fijo(cx: b.Contexto, n: int = 40) -> list[int]:
    """Los primeros n renglones con concepto que el sistema lexico clasifica bien y con puntaje >= 0,75 (fijo y reproducible)."""
    p, s = cx.puntuar(a.LEXICO)
    ok = [i for i, f in enumerate(cx.d.filas) if f["etiqueta"] and p[f["u"]] == cx.y[i] and s[f["u"]] >= 0.75]
    vistos, out = set(), []
    for i in ok:
        u = cx.d.filas[i]["u"]
        if u not in vistos:
            vistos.add(u)
            out.append(i)
    return out[:n]


def test_determinista() -> None:
    for tp in a.TIPOS_TODOS:
        for sv in (a.LEVE, a.FUERTE):
            assert a.perturbar("Cuaderno cuadriculado de 100 hojas", tp, sv) == a.perturbar("Cuaderno cuadriculado de 100 hojas", tp, sv)
    assert a.variante_aumentada("lápiz negro", 2) == a.variante_aumentada("lápiz negro", 2)


def test_leves_conservan_legibilidad_y_numeros(cx: b.Contexto) -> None:
    fijo = _conjunto_fijo(cx)
    assert len(fijo) >= 30
    for tp in a.TIPOS:
        for i in fijo:
            o = cx.d.textos[cx.d.filas[i]["u"]]
            p = a.perturbar(o, tp, a.LEVE)
            assert p.strip(), (tp, o)
            if tp not in ("prefijo", "sufijo", "ocr", "marca", "orden"):
                assert sorted(c for c in o if c.isdigit()) == sorted(c for c in p if c.isdigit()), (tp, o, p)
            if tp not in ("prefijo", "sufijo", "marca"):  # estos agregan palabras: la similitud no aplica
                assert similitud(o, p) >= 0.5, (tp, o, p)


def test_etiqueta_se_conserva_en_conjunto_fijo(cx: b.Contexto) -> None:
    """En 40 renglones bien clasificados, cada perturbacion leve conservadora deja el MISMO concepto en >= 85 % de los casos
    (el sistema lexico, con su corrector de tipeos; no hay vectores)."""
    fijo = _conjunto_fijo(cx)
    for tp in CONSERVADORAS:
        textos = [cx.d.textos[cx.d.filas[i]["u"]] for i in fijo]
        nuevos = list(cx.d.textos)
        for i, t in zip(fijo, textos, strict=True):
            nuevos[cx.d.filas[i]["u"]] = a.perturbar(t, tp, a.LEVE)
        c2 = a.contexto_con_textos(cx, nuevos, None)
        p, s = c2.puntuar(a.LEXICO)
        conserva = np.mean([p[cx.d.filas[i]["u"]] == cx.y[i] and s[cx.d.filas[i]["u"]] >= 0.5 for i in fijo])
        assert conserva >= 0.85, (tp, conserva)


def test_sin_fuga_por_lista_ni_por_texto(cx: b.Contexto) -> None:
    estres = a.conjuntos_de_estres(cx.d.textos)
    aum = a.conjuntos_aumentados(cx.d.textos)
    pila = a.Pila(cx, [a.contexto_con_textos(cx, lst, None) for lst in aum])
    listas = sorted(set(cx.lista))
    for i in (0, 7, 19):
        parte = partir(listas, SEMILLA_BASE + i)
        assert not set(parte["entrenamiento"]) & set(parte["prueba"] + parte["validacion"])
        proh = a.cadenas_prohibidas(cx, parte, estres)
        m = a.mascaras(pila, parte, proh)
        c = a.comprobar_fuga(pila, parte, m, proh)
        assert c["listas_compartidas_entre_particiones"] == 0
        assert c["variantes_de_entrenamiento_con_texto_base_de_val_o_prueba"] == 0
        assert c["cadenas_de_variantes_de_entrenamiento_iguales_a_algun_texto_de_val_o_prueba"] == 0
        # validacion y prueba son siempre filas limpias (origen 0)
        assert (pila.origen[m["val"]] == 0).all() and (pila.origen[m["prueba"]] == 0).all()
        assert not (m["train_aum"] & (m["val"] | m["prueba"])).any()
