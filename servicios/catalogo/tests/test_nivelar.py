from __future__ import annotations

from tukit_catalogo.nivelar import reacomodar, sku


def producto(
    pid: str,
    concepto: str,
    nivel: str,
    personaje: str = "",
    representante: bool = True,
) -> dict[str, str]:
    return {
        "id": pid,
        "concepto_id": concepto,
        "nivel": nivel,
        "personaje": personaje,
        "activo": "true",
        "es_representante_canonico": "true" if representante else "false",
    }


class TestElPrecioManda:
    def test_permuta_las_etiquetas_que_ya_existian(self):
        productos = [
            producto("a", "C1", "premium"),
            producto("b", "C1", "economico"),
            producto("c", "C1", "confiable"),
        ]
        cambios = reacomodar(productos, {"a": 1000, "b": 3000, "c": 2000})

        assert cambios == {"a": "economico", "b": "premium"}
        assert "c" not in cambios

    def test_no_toca_lo_que_ya_esta_bien(self):
        productos = [
            producto("a", "C1", "economico"),
            producto("b", "C1", "confiable"),
            producto("c", "C1", "premium"),
        ]
        assert reacomodar(productos, {"a": 100, "b": 200, "c": 300}) == {}

    def test_el_que_no_tiene_precio_se_queda_quieto(self):
        productos = [
            producto("a", "C1", "premium"),
            producto("b", "C1", "economico"),
            producto("sin", "C1", "confiable"),
        ]
        cambios = reacomodar(productos, {"a": 900, "b": 100})

        assert "sin" not in cambios
        assert set(cambios.values()) <= {"premium", "economico"}

    def test_la_profundidad_de_la_cola_no_entra_en_la_escalera(self):
        productos = [
            producto("rep_barato", "C1", "premium"),
            producto("rep_caro", "C1", "economico"),
            producto("depth1", "C1", "confiable", representante=False),
            producto("depth2", "C1", "confiable", representante=False),
        ]
        cambios = reacomodar(
            productos,
            {"rep_barato": 1000, "depth1": 1500, "depth2": 1800, "rep_caro": 3000},
        )

        assert cambios == {"rep_barato": "economico", "rep_caro": "premium"}
        assert "depth1" not in cambios and "depth2" not in cambios


class TestElPersonajeEsOtraVia:
    def test_no_se_ordena_contra_los_de_marca_pero_su_etiqueta_no_miente(self):
        productos = [
            producto("base_eco", "C1", "economico"),
            producto("base_pre", "C1", "premium"),
            producto("bluey", "C1", "economico", personaje="bluey"),
        ]
        cambios = reacomodar(productos, {"base_eco": 100, "base_pre": 200, "bluey": 9000})

        assert "base_eco" not in cambios and "base_pre" not in cambios
        assert cambios == {"bluey": "premium"}

    def test_el_de_personaje_barato_cae_en_la_banda_baja(self):
        productos = [
            producto("base_eco", "C1", "economico"),
            producto("base_pre", "C1", "premium"),
            producto("cars", "C1", "premium", personaje="cars"),
        ]
        cambios = reacomodar(productos, {"base_eco": 1000, "base_pre": 5000, "cars": 900})

        assert cambios == {"cars": "economico"}

    def test_sin_productos_de_marca_no_se_inventa_banda(self):
        productos = [producto("solo", "C1", "confiable", personaje="frozen")]

        assert reacomodar(productos, {"solo": 4000}) == {}

    def test_ordena_dentro_de_un_mismo_personaje(self):
        productos = [
            producto("frozen_pre", "C1", "premium", personaje="frozen"),
            producto("frozen_eco", "C1", "economico", personaje="frozen"),
        ]
        cambios = reacomodar(productos, {"frozen_pre": 100, "frozen_eco": 900})

        assert cambios == {"frozen_pre": "economico", "frozen_eco": "premium"}

    def test_el_sku_conserva_el_personaje(self):
        assert sku("C001", "premium", "bluey") == "TK-C001-PRE-BLUEY"
        assert sku("C001", "economico", "") == "TK-C001-ECO"
