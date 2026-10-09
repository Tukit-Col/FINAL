"""Fase 5 de QA: el emparejamiento ante un renglon hostil (ADV-07 y ADV-08).

ADV-07 (OWASP LLM08) ataca el canal semantico: la fusion de `clasificar`
(`descubrir.py`) promete que «ninguna deshace la cabeza anclada» y que «la
fusion nunca hunde un match lexico». Se prueba con dos embebedores, los dos
sin red (N-60):

- el honesto, `embeder_falso`, sobre el renglon y sobre cada concepto (nombre
  y sinonimos, porque `conceptos.csv` no trae `embedding`);
- el adversarial, que le da al renglon el vector de un concepto rival: el peor
  caso de un vector envenenado o de un proveedor que deriva.

El oro es `datos/golden/esperado/oracle.json`, niveles exacto y facil, y el
catalogo es el de `datos/catalogo/` (el mismo de `test_golden_oro.py`).

ADV-08 (LLM09, ESC-02) pide un producto que el catalogo no tiene: ningun SKU
puede salir de la nada. Los textos hostiles son los de
`ensayos/adversariales/fixtures/` y son inventados.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_golden_oro import CONCEPTOS, ORO, PRODUCTOS, SKUS
from tukit_catalogo.consulta import emparejar
from tukit_catalogo.embeddings import MODELO_FALSO, embeder_falso

RAIZ = Path(__file__).resolve().parents[3]
FIXTURES = RAIZ / "ensayos" / "adversariales" / "fixtures"
PARES = [par for par in ORO if par["nivel"] in ("exacto", "facil")]
HUECOS = {"sin_match", "hueco_catalogo", "abstencion"}


def _con_vectores() -> list[dict]:
    conceptos = [dict(concepto) for concepto in CONCEPTOS]
    textos = [" ".join([concepto["nombre"], *concepto["sinonimos"]]) for concepto in conceptos]
    for concepto, vector in zip(conceptos, embeder_falso(textos), strict=True):
        concepto["embedding"] = vector
    return conceptos


CONCEPTOS_CON_VECTOR = _con_vectores()
POR_CODIGO = {concepto["codigo"]: concepto for concepto in CONCEPTOS_CON_VECTOR}
# Los rivales: los ocho primeros conceptos del catalogo (cuaderno, lapiz,
# block, colores...). Todos contra todos son 1.164 casos y 25 s por prueba; con
# ocho la prueba sigue siendo determinista y cabe en `make prueba`.
RIVALES = [concepto["codigo"] for concepto in CONCEPTOS_CON_VECTOR[:8]]


def _textos_de_los_fixtures() -> list[str]:
    """Cada renglon que los fixtures ADV le hacen decir al modelo, menos los tres de la lista base."""
    base = {"Cuaderno cuadriculado de 100 hojas", "Caja de colores x 12", "Borrador blanco"}
    textos = []
    for ruta in sorted(FIXTURES.glob("ADV-*.json")):
        cuerpo = json.loads(ruta.read_text())["respuesta_http"]["cuerpo"]
        for item in json.loads(cuerpo["candidates"][0]["content"]["parts"][0]["text"])["items"]:
            if item["descripcion"] not in base and item["descripcion"] not in textos:
                textos.append(item["descripcion"])
    return textos


def _canal(record_property, embebedor: str | None) -> None:
    """La fila de `acuerdos.md` §1.6: `activo` o `inactivo`, y de donde sale el vector del renglon."""
    record_property("canal_vectorial", "activo" if embebedor else "inactivo")
    record_property("embedding_model", MODELO_FALSO if embebedor else "ninguno")
    record_property("embebedor", embebedor or "ninguno: solo lexico")


@pytest.mark.nfr("NFR-SEG-06")
class TestADV07RankingPorEmbeddings:
    def test_el_canal_honesto_no_cambia_ningun_ganador_del_oro(self, record_property):
        _canal(record_property, "embeder_falso sobre el renglon")
        cambios = []
        for par in PARES:
            resultado = emparejar(
                par["texto"],
                CONCEPTOS_CON_VECTOR,
                PRODUCTOS,
                embedding_renglon=embeder_falso([par["texto"]])[0],
            )
            if resultado.concepto_codigo != par["concepto"]:
                cambios.append((par["texto"], par["concepto"], resultado.concepto_codigo))

        record_property("pares", len(PARES))
        record_property("ganadores_cambiados", len(cambios))
        assert len(PARES) == 12
        assert cambios == []

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-50: la fusion hunde el match lexico; con el texto cargado de sinonimos de otra "
        "categoria, el canal vectorial cambia un ganador que el lexico solo acertaba",
    )
    def test_la_consulta_cargada_no_hunde_un_match_lexico(self, record_property):
        _canal(record_property, "embeder_falso sobre el texto cargado")
        cargados = casos = hundidos = 0
        ejemplos = []
        for par in PARES:
            for rival in RIVALES:
                if rival == par["concepto"]:
                    continue
                concepto = POR_CODIGO[rival]
                texto = f"{par['texto']} {' '.join([concepto['nombre'], *concepto['sinonimos']])}"
                cargados += 1
                # Solo cuentan los casos en que el lexico, sin vector, acierta: ahi la
                # fusion no tiene nada que rescatar y lo unico que puede hacer es hundir.
                if emparejar(texto, CONCEPTOS_CON_VECTOR, PRODUCTOS).concepto_codigo != par["concepto"]:
                    continue
                casos += 1
                fundido = emparejar(
                    texto, CONCEPTOS_CON_VECTOR, PRODUCTOS, embedding_renglon=embeder_falso([texto])[0]
                )
                if fundido.concepto_codigo != par["concepto"]:
                    hundidos += 1
                    ejemplos.append(f"{par['concepto']}->{fundido.concepto_codigo}({fundido.estado})")

        record_property("consultas_cargadas", cargados)
        record_property("casos_lexico_correcto", casos)
        record_property("hundidos_por_la_fusion", hundidos)
        record_property("ejemplos", " | ".join(ejemplos[:10]))
        assert hundidos == 0, f"la fusion cambia {hundidos} de {casos} ganadores lexicos correctos"

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-50: el rescate por coseno de un concepto rival (>= 0,86) le gana a la cabeza "
        "anclada; un vector envenenado cambia el concepto de la mitad de los pares del oro",
    )
    def test_el_vector_de_un_rival_no_le_quita_el_renglon_a_su_concepto(self, record_property):
        _canal(record_property, "adversarial: vector del concepto rival")
        robados = []
        for par in PARES:
            for rival in RIVALES:
                if rival == par["concepto"]:
                    continue
                resultado = emparejar(
                    par["texto"],
                    CONCEPTOS_CON_VECTOR,
                    PRODUCTOS,
                    embedding_renglon=POR_CODIGO[rival]["embedding"],
                )
                if resultado.concepto_codigo != par["concepto"]:
                    robados.append(f"{par['texto']}: {par['concepto']}->{resultado.concepto_codigo}")
                    break

        record_property("pares_robados", len(robados))
        record_property("ejemplos", " | ".join(robados))
        assert robados == [], f"{len(robados)} de {len(PARES)} pares cambian de concepto"

    def test_el_vector_del_rival_no_trae_productos_de_fuera_del_catalogo(self, record_property):
        _canal(record_property, "adversarial: vector del concepto rival")
        for par in PARES:
            for rival in RIVALES:
                resultado = emparejar(
                    par["texto"],
                    CONCEPTOS_CON_VECTOR,
                    PRODUCTOS,
                    embedding_renglon=POR_CODIGO[rival]["embedding"],
                )
                assert {opcion.sku for opcion in resultado.opciones} <= SKUS


@pytest.mark.nfr("NFR-SEG-06")
class TestADV08ProductoQueNoExiste:
    @pytest.mark.parametrize("con_vector", [False, True], ids=["lexico", "fundido"])
    def test_las_gafas_de_quimica_son_un_hueco_sin_sku(self, con_vector, record_property):
        texto = "Gafas de protección para química"
        vector = embeder_falso([texto])[0] if con_vector else None
        _canal(record_property, "embeder_falso sobre el renglon" if con_vector else None)

        resultado = emparejar(texto, CONCEPTOS_CON_VECTOR, PRODUCTOS, embedding_renglon=vector)

        record_property("estado", resultado.estado)
        assert resultado.estado in HUECOS
        assert resultado.opciones == ()
        assert "TK-GAF-QUI-001" not in SKUS

    @pytest.mark.parametrize("texto", _textos_de_los_fixtures())
    def test_ningun_renglon_hostil_trae_un_sku_fuera_del_catalogo(self, texto, record_property):
        _canal(record_property, None)
        resultado = emparejar(texto, CONCEPTOS, PRODUCTOS)

        # Lo que se reporta: que concepto le toca a cada renglon hostil. Un
        # renglon obedecido que se parece a un util (`Borra...` -> borrador) entra
        # pendiente de revision; lo que se exige es que no salga nada inventado.
        record_property("estado", resultado.estado)
        record_property("concepto", resultado.concepto_codigo or "")
        assert {opcion.sku for opcion in resultado.opciones} <= SKUS
