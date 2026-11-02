"""Los filtros duros del asistente NL2C llegan al optimizador (cierra la brecha declarada).

`marcas_excluidas` y `solo_disponibles` se aplican a los candidatos ANTES del
frente. Lo que se defiende aqui: que la marca excluida no aparece en NINGUN kit,
que la marca que el colegio exige se respeta aunque el acudiente la haya
excluido, y que una linea que se queda sin candidatos sale como hueco explicado
en vez de rellenarse con lo prohibido.
"""

from __future__ import annotations

import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from tukit_inteligencia.dominio.pipeline import inyectar_personaje_fan
from tukit_inteligencia.modelos import PerfilKit
from tukit_inteligencia.optimizador import (
    Candidato,
    Renglon,
    aplicar_filtros_duros,
    armar_los_tres,
    filtros_de,
)


def _cand(sku: str, nivel: str, precio: int | None, marca: str | None, **kw) -> Candidato:
    return Candidato(sku=sku, nombre=f"Producto {sku}", nivel=nivel, precio_cop=precio, marca=marca, **kw)


def _reng(orden: int, texto: str, candidatos: tuple[Candidato, ...], **kw) -> Renglon:
    return Renglon(
        hijo="hijo-1",
        orden=orden,
        texto=texto,
        tipo_item="util",
        modo_adquisicion="mercado_abierto",
        cantidad=1,
        estado_resolucion="RESUELTO_AUTO",
        candidatos=candidatos,
        **kw,
    )


CUADERNOS = (
    _cand("N", "economico", 3000, "Norma"),
    _cand("F", "confiable", 6000, "Faber-Castell"),
    _cand("P", "premium", 9000, "Pelikan"),
)
LAPICES = (
    _cand("L1", "economico", 1000, "FABER CASTELL"),
    _cand("L2", "premium", 4000, "Staedtler"),
)


def _skus_elegidos(kits) -> set[str]:
    return {li.elegido.sku for kit in kits for li in kit.lineas if li.elegido}


class TestMarcasExcluidas:
    def test_la_marca_no_sale_en_ningun_kit_ni_sus_alternativas(self):
        renglones = [_reng(1, "cuaderno", CUADERNOS), _reng(2, "lapices", LAPICES)]
        # Sin filtro, Faber-Castell si aparece: el filtro es lo que la saca.
        assert {"F", "L1"} & _skus_elegidos(armar_los_tres(renglones))

        kits = armar_los_tres(renglones, {"marcas_excluidas": ["faber-castell"]})
        assert not ({"F", "L1"} & _skus_elegidos(kits))
        for kit in kits:
            for linea in kit.lineas:
                assert all(a.sku not in {"F", "L1"} for a in linea.alternativas)

    def test_casa_sin_importar_mayusculas_tildes_ni_guiones(self):
        c = (_cand("A", "economico", 100, "Pelíkan"), _cand("B", "premium", 900, "Otra"))
        r = aplicar_filtros_duros([_reng(1, "x", c)], {"marcas_excluidas": ["PELIKAN"]})
        assert [x.sku for x in r[0].candidatos] == ["B"]

    def test_no_confunde_una_marca_con_otra_que_la_contiene(self):
        c = (_cand("A", "economico", 100, "Normalizado S.A."), _cand("B", "premium", 900, "Otra"))
        r = aplicar_filtros_duros([_reng(1, "x", c)], {"marcas_excluidas": ["Norma"]})
        assert [x.sku for x in r[0].candidatos] == ["A", "B"]

    def test_sin_marca_en_el_catalogo_se_mira_el_nombre(self):
        c = (
            Candidato(sku="A", nombre="Cuaderno Norma 100h", nivel="economico", precio_cop=100, marca=None),
            _cand("B", "premium", 900, "Otra"),
        )
        r = aplicar_filtros_duros([_reng(1, "x", c)], {"marcas_excluidas": ["Norma"]})
        assert [x.sku for x in r[0].candidatos] == ["B"]

    def test_la_marca_que_exige_el_colegio_se_conserva_y_se_explica(self):
        renglones = [_reng(1, "Cuaderno Norma cuadriculado", CUADERNOS)]
        r = aplicar_filtros_duros(renglones, {"marcas_excluidas": ["Norma", "Pelikan"]})
        # Norma se queda (la pide la lista); Pelikan, que nadie exige, se va.
        assert [x.sku for x in r[0].candidatos] == ["N", "F"]
        assert "El colegio pide Norma" in (r[0].mensaje or "")

    def test_la_exigida_llega_al_kit_aunque_se_haya_excluido(self):
        renglones = [_reng(1, "Cuaderno Norma", CUADERNOS)]
        kits = armar_los_tres(renglones, {"marcas_excluidas": ["Norma"]})
        assert any(li.elegido and li.elegido.sku == "N" for kit in kits for li in kit.lineas)

    def test_linea_sin_candidatos_queda_como_hueco_con_mensaje(self):
        solo_faber = (_cand("F", "confiable", 6000, "Faber-Castell"),)
        renglones = [_reng(1, "colores", solo_faber), _reng(2, "cuaderno", CUADERNOS)]
        kits = armar_los_tres(renglones, {"marcas_excluidas": ["Faber Castell"]})
        for kit in kits:
            colores = next(li for li in kit.lineas if li.orden == 1)
            assert colores.elegido is None and colores.subtotal_cop is None
            assert colores.estado_resolucion == "HUECO_CATALOGO"
            assert "Faber Castell" in (colores.mensaje or "")
            # El hueco no se cobra: el total es solo lo que si hay.
            assert kit.total_cop == sum(li.subtotal_cop or 0 for li in kit.lineas)

    def test_sin_filtros_devuelve_los_mismos_renglones(self):
        renglones = [_reng(1, "cuaderno", CUADERNOS)]
        assert aplicar_filtros_duros(renglones, {}) is renglones
        assert aplicar_filtros_duros(renglones, {"solo_disponibles": False}) is renglones

    def test_el_swap_de_personaje_del_fan_respeta_la_marca_excluida(self):
        renglones = [_reng(1, "cuaderno", CUADERNOS, concepto_codigo="C001")]
        prefs = {"personaje_por_hijo": {"hijo-1": ["spiderman"]}, "marcas_excluidas": ["Faber-Castell"]}
        kits = armar_los_tres(renglones, prefs)
        swaps = {
            "C001": {
                "sku": "SP",
                "nombre": "Cuaderno Spiderman",
                "marca": "Faber-Castell",
                "nivel": "confiable",
                "precio_desde": 5000,
                "personaje": "spiderman",
            }
        }
        kits = inyectar_personaje_fan(kits, swaps, prefs)
        fan = next(k for k in kits if k.perfil == PerfilKit.FAN.value)
        assert all(li.elegido is None or li.elegido.sku != "SP" for li in fan.lineas)


class TestSoloDisponibles:
    def test_solo_quedan_los_candidatos_con_precio_vigente(self):
        c = (_cand("A", "economico", None, "Norma"), _cand("B", "premium", 900, "Otra"))
        r = aplicar_filtros_duros([_reng(1, "x", c)], {"solo_disponibles": True})
        assert [x.sku for x in r[0].candidatos] == ["B"]

    def test_sin_el_filtro_el_candidato_sin_precio_sigue_siendo_admisible(self):
        c = (_cand("A", "economico", None, "Norma"), _cand("B", "premium", 900, "Otra"))
        r = aplicar_filtros_duros([_reng(1, "x", c)], {})
        assert len(r[0].candidatos) == 2

    def test_linea_sin_ninguna_oferta_queda_como_hueco_explicado(self):
        solo_sin_precio = (_cand("A", "economico", None, "Norma"),)
        kits = armar_los_tres([_reng(1, "x", solo_sin_precio)], {"solo_disponibles": True})
        linea = kits[0].lineas[0]
        assert linea.elegido is None and linea.estado_resolucion == "HUECO_CATALOGO"
        assert "precio vigente" in (linea.mensaje or "")

    def test_la_exencion_de_marca_exigida_no_salta_la_disponibilidad(self):
        # La marca exigida no se quita, pero un producto sin oferta tampoco se ofrece.
        c = (_cand("N", "economico", None, "Norma"), _cand("N2", "confiable", 4000, "Norma"))
        r = aplicar_filtros_duros(
            [_reng(1, "Cuaderno Norma", c)], {"marcas_excluidas": ["Norma"], "solo_disponibles": True}
        )
        assert [x.sku for x in r[0].candidatos] == ["N2"]

    def test_no_dice_que_conserva_la_exigida_si_solo_quedo_otra_marca(self):
        # La Norma exigida no tiene precio hoy: el kit llevara otra marca, y la
        # nota "no la quitamos" seria falsa.
        c = (_cand("N", "economico", None, "Norma"), _cand("B", "confiable", 100, "Otra"))
        r = aplicar_filtros_duros(
            [_reng(1, "Cuaderno Norma 100 hojas", c)],
            {"marcas_excluidas": ["Norma"], "solo_disponibles": True},
        )
        assert [x.sku for x in r[0].candidatos] == ["B"]
        assert "no la quitamos" not in (r[0].mensaje or "")


class TestLecturaDefensiva:
    @pytest.mark.parametrize(
        "crudo",
        [None, "Norma", 7, [None, 3, "", "  "], {"a": 1}],
    )
    def test_marcas_con_forma_rara_no_filtran_ni_rompen(self, crudo):
        assert filtros_de({"marcas_excluidas": crudo}).marcas_excluidas == ()

    def test_solo_un_true_de_verdad_enciende_solo_disponibles(self):
        assert not filtros_de({"solo_disponibles": "false"}).solo_disponibles
        assert not filtros_de({"solo_disponibles": 1}).solo_disponibles
        assert filtros_de({"solo_disponibles": True}).solo_disponibles

    def test_acota_cantidad_y_largo_de_marcas(self):
        f = filtros_de({"marcas_excluidas": [f"m{i}" for i in range(50)] + ["x" * 500]})
        assert len(f.marcas_excluidas) == 10
        f = filtros_de({"marcas_excluidas": ["y" * 500]})
        assert len(f.marcas_excluidas[0][1]) == 40


# --- De punta a punta: HTTP -> preferencias guardadas -> pipeline -> kits ----
COLEGIO = "11111111-1111-5111-8111-111111111111"


def _catalogo_con_marcas():
    return CatalogoFalso(
        renglones=[renglon(1, "cuaderno cuadriculado"), renglon(2, "colores x12")],
        respuestas={
            "cuaderno cuadriculado": reconocido(
                "cuaderno cuadriculado",
                "C001",
                [
                    opcion("N", "economico", 3000, marca="Norma"),
                    opcion("F", "premium", 9000, marca="Faber-Castell"),
                ],
            ),
            # Solo una marca: al excluirla la linea queda como hueco explicado.
            "colores x12": reconocido(
                "colores x12", "C004", [opcion("CF", "confiable", 24900, marca="Faber Castell")]
            ),
        },
    )


class TestDeAPuntaAPunta:
    async def test_los_filtros_sobreviven_al_guardado_y_gobiernan_los_kits(self, motor):
        import uuid

        from sqlalchemy import select
        from tukit_comun.cifrado import cifrador_desde_entorno
        from tukit_inteligencia import trabajos

        prefs = {"marcas_excluidas": ["Faber-Castell"], "solo_disponibles": True}
        creado = await trabajos.crear(
            motor,
            hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            preferencias=prefs,
        )
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        async with motor.engine.begin() as conexion:
            guardado = await conexion.scalar(
                select(trabajos.TRABAJO.c.preferencias_cifradas).where(trabajos.TRABAJO.c.id == trabajo_id)
            )
        assert cifrador_desde_entorno().descifrar_json(guardado) == prefs

        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo_con_marcas())
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
        for kit in vista["kits"]:
            marcas = [ln["producto_elegido"]["marca"] for ln in kit["lineas"] if ln.get("producto_elegido")]
            assert marcas == ["Norma"]
            colores = next(ln for ln in kit["lineas"] if ln["orden"] == 2)
            assert not colores.get("producto_elegido")
            assert "Faber-Castell" in (colores.get("mensaje") or "")

    async def test_el_borde_http_acepta_y_acota_los_filtros(self):
        import httpx
        from tukit_inteligencia.api import app

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://p") as http:
            demasiadas = await http.post(
                "/v1/trabajos",
                json={
                    "hijos": [{"referencia": "h", "colegio_id": COLEGIO, "grado": "Cuarto"}],
                    "preferencias": {"marcas_excluidas": [f"m{i}" for i in range(11)]},
                },
            )
            assert demasiadas.status_code == 400

    async def test_aplicar_canonico_rechaza_filtros_en_vez_de_ignorarlos(self):
        import httpx
        from tukit_inteligencia.api import app

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://p") as http:
            r = await http.post(
                "/v1/trabajos/aplicar-canonico",
                json={
                    "colegio_id": COLEGIO,
                    "grado": "Cuarto",
                    "anio_lectivo": 2026,
                    "perfil": "Ahorrador",
                    "solo_disponibles": True,
                },
            )
            assert r.status_code == 422
            assert r.json()["error"] == "filtros_requieren_recalculo"
