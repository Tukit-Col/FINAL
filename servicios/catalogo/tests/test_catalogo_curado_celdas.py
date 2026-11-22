# ruff: noqa: F811

from __future__ import annotations

import uuid
from collections import Counter, defaultdict

from _ayudas_catalogo_curado import (  # noqa: F401  (los fixtures se reusan tal cual)
    _es_true,
    _precio_minimo_por_producto,
    _representantes,
    cargado,
    catalogo,
)
from sqlalchemy.orm import Session
from tukit_catalogo.modelos import (
    Concepto,
    Nivel,
    ProductoCanonico,
)

QUITADOS_A_MANO: dict[str, int] = {}


class TestDemandaAlta:

    @staticmethod
    def _alta_demanda(cargado: Session) -> list[Concepto]:
        conceptos = sorted(cargado.query(Concepto), key=lambda c: (-c.frecuencia_demanda, c.codigo))
        total = sum(c.frecuencia_demanda for c in conceptos)
        acumulado, seleccion = 0, []
        for concepto in conceptos:
            if acumulado / total >= 0.80:
                break
            acumulado += concepto.frecuencia_demanda
            seleccion.append(concepto)
        return seleccion

    def test_son_veinticinco_conceptos(self, cargado):
        assert len(self._alta_demanda(cargado)) == 25

    def test_ninguno_se_queda_sin_producto(self, cargado):
        for concepto in self._alta_demanda(cargado):
            productos = cargado.query(ProductoCanonico).filter_by(concepto_id=concepto.id).count()
            assert productos > 0, f"{concepto.codigo} {concepto.nombre_canonico} sin producto"

    def test_tiene_tantos_niveles_como_representantes_dio_el_universo(self, cargado):
        for concepto in self._alta_demanda(cargado):
            genericos = [p for p in _representantes(cargado, concepto_id=concepto.id) if not p.personaje]
            niveles = {p.nivel for p in genericos}
            esperado = min(3, len(genericos)) - QUITADOS_A_MANO.get(concepto.codigo, 0)
            assert len(niveles) == esperado, (
                f"{concepto.codigo} {concepto.nombre_canonico}: "
                f"{sorted(niveles)} con {len(genericos)} representantes genericos"
            )

    def test_el_precio_ordena_los_niveles_dentro_de_cada_escalera(self, cargado):
        barato = _precio_minimo_por_producto(cargado)

        orden = {n.value: i for i, n in enumerate(Nivel)}
        escaleras: dict[tuple[uuid.UUID, str], list[tuple[int, str, str]]] = {}
        for p in _representantes(cargado, activo=True):
            if p.id in barato:
                clave = (p.concepto_id, p.personaje or "")
                escaleras.setdefault(clave, []).append((barato[p.id], p.nivel, p.sku_interno))

        assert escaleras, "sin precios no se puede comprobar nada"
        for peldanos in escaleras.values():
            tope_mas_barato = -1
            for precio in sorted({p for p, _, _ in peldanos}):
                grupo = [(n, s) for p, n, s in peldanos if p == precio]
                for nivel, sku in grupo:
                    assert orden[nivel] >= tope_mas_barato, (
                        f"{sku} vale ${precio // 100:,} y es {nivel}, "
                        f"pero algo estrictamente mas barato de su escalera "
                        f"lleva un nivel mas alto"
                    )
                tope_mas_barato = max(orden[n] for n, _ in grupo)

    def test_ningun_economico_cuesta_mas_que_un_premium_del_mismo_concepto(self, cargado):
        barato = _precio_minimo_por_producto(cargado)

        por_concepto: dict[uuid.UUID, list[ProductoCanonico]] = defaultdict(list)
        for p in _representantes(cargado, activo=True):
            if p.id in barato:
                por_concepto[p.concepto_id].append(p)

        for productos in por_concepto.values():
            economicos = [p for p in productos if p.nivel == Nivel.ECONOMICO.value]
            premium = [p for p in productos if p.nivel == Nivel.PREMIUM.value]
            if not economicos or not premium:
                continue
            caro = max(economicos, key=lambda p: barato[p.id])
            barato_premium = min(premium, key=lambda p: barato[p.id])
            assert barato[caro.id] <= barato[barato_premium.id], (
                f"{caro.sku_interno} es economico y vale "
                f"${barato[caro.id] // 100:,}, pero "
                f"{barato_premium.sku_interno} es premium y vale "
                f"${barato[barato_premium.id] // 100:,}"
            )

    def test_los_conceptos_sin_producto_son_los_documentados(self, cargado, catalogo):
        sin_producto = set(catalogo["metricas"]["catalogo"]["conceptos_sin_producto"])
        assert len(sin_producto) <= 17
        alta = {c.codigo for c in self._alta_demanda(cargado)}
        assert not (sin_producto & alta)


class TestSinDuplicados:
    def test_el_sku_interno_es_unico(self, catalogo):
        skus = [p["sku_interno"] for p in catalogo["productos_canonicos"]]
        assert len(skus) == len(set(skus))

    def test_el_ean_no_se_repite_entre_productos(self, catalogo):
        eans = [p["ean"] for p in catalogo["productos_canonicos"] if p["ean"]]
        assert len(eans) == len(set(eans))
        for ean in eans:
            assert len(ean) == 13 and ean.isdigit()

    def test_una_celda_util_tiene_exactamente_un_representante(self, catalogo):
        es_libro = {
            c["id"]
            for c in catalogo["conceptos"]
            if c["tipo_item"] == "libro_libre" or "libro" in (c["categoria"] or "").lower()
        }
        utiles = [
            p
            for p in catalogo["productos_canonicos"]
            if p["concepto_id"] not in es_libro and _es_true(p["activo"])
        ]
        representantes_por_celda = Counter(
            (p["concepto_id"], p["nivel"], p["personaje"])
            for p in utiles
            if _es_true(p["es_representante_canonico"])
        )
        con_varios = [c for c, n in representantes_por_celda.items() if n > 1]
        assert con_varios == [], f"celdas util con mas de un representante: {con_varios}"

        escaleras = {(p["concepto_id"], p["personaje"]) for p in utiles}
        con_representante = {
            (p["concepto_id"], p["personaje"]) for p in utiles if _es_true(p["es_representante_canonico"])
        }
        sin_representante = sorted(escaleras - con_representante)
        assert sin_representante == [], f"escaleras util sin representante: {sin_representante}"

    def test_la_profundidad_detras_del_representante_es_de_la_cola(self, catalogo):
        es_libro = {
            c["id"]
            for c in catalogo["conceptos"]
            if c["tipo_item"] == "libro_libre" or "libro" in (c["categoria"] or "").lower()
        }
        por_celda: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for p in catalogo["productos_canonicos"]:
            if p["concepto_id"] not in es_libro and _es_true(p["activo"]):
                por_celda[p["concepto_id"], p["nivel"], p["personaje"]].append(p)

        intrusos = [
            p["sku_interno"]
            for productos in por_celda.values()
            if len(productos) > 1
            for p in productos
            if not _es_true(p["es_representante_canonico"]) and not p["sku_interno"].startswith("TK-REV-")
        ]
        assert intrusos == [], f"semillas no representativas compartiendo celda: {intrusos}"

    def test_una_tienda_no_ofrece_dos_veces_el_mismo_producto(self, catalogo):
        pares = Counter((o["producto_canonico_id"], o["tienda_id"]) for o in catalogo["ofertas_tienda"])
        assert [p for p, n in pares.items() if n > 1] == []

    def test_una_referencia_de_tienda_apunta_a_un_solo_producto(self, catalogo):
        pares = Counter((o["tienda_id"], o["referencia_externa"]) for o in catalogo["ofertas_tienda"])
        assert [p for p, n in pares.items() if n > 1] == []

    def test_los_identificadores_no_colisionan(self, catalogo):
        for tabla in ("conceptos", "productos_canonicos", "ofertas_tienda", "precios_oferta"):
            ids = [f["id"] for f in catalogo[tabla]]
            assert len(ids) == len(set(ids)), tabla
