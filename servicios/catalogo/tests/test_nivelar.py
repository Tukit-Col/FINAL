"""Que la reparacion de niveles no invente nada y respete al personaje.

`nivelar` existe porque 36 productos tenian la etiqueta de nivel al reves del
precio. Un arreglo asi es peligroso: si se pasa de listo, reescribe decisiones
de curaduria que nadie le pidio tocar. Estos tests fijan sus dos limites.
"""

from __future__ import annotations

from tukit_catalogo.nivelar import reacomodar, sku


def producto(pid: str, concepto: str, nivel: str, personaje: str = "") -> dict[str, str]:
    return {
        "id": pid,
        "concepto_id": concepto,
        "nivel": nivel,
        "personaje": personaje,
        "activo": "true",
    }


class TestElPrecioManda:
    def test_permuta_las_etiquetas_que_ya_existian(self):
        """No se inventan niveles: se reparten los mismos en orden de precio."""
        productos = [
            producto("a", "C1", "premium"),
            producto("b", "C1", "economico"),
            producto("c", "C1", "confiable"),
        ]
        cambios = reacomodar(productos, {"a": 1000, "b": 3000, "c": 2000})

        assert cambios == {"a": "economico", "b": "premium"}
        # 'c' no se movio porque su etiqueta ya correspondia a su precio.
        assert "c" not in cambios

    def test_no_toca_lo_que_ya_esta_bien(self):
        """Un concepto sano no aparece en el diff. Asi el cambio es auditable."""
        productos = [
            producto("a", "C1", "economico"),
            producto("b", "C1", "confiable"),
            producto("c", "C1", "premium"),
        ]
        assert reacomodar(productos, {"a": 100, "b": 200, "c": 300}) == {}

    def test_el_que_no_tiene_precio_se_queda_quieto(self):
        """Sin precio no hay con que ordenar, y adivinar seria peor que dejarlo."""
        productos = [
            producto("a", "C1", "premium"),
            producto("b", "C1", "economico"),
            producto("sin", "C1", "confiable"),
        ]
        cambios = reacomodar(productos, {"a": 900, "b": 100})

        assert "sin" not in cambios
        # Y los dos que si tienen precio se reparten solo SUS etiquetas, sin
        # robarse la del que quedo fuera.
        assert set(cambios.values()) <= {"premium", "economico"}


class TestElPersonajeEsOtraVia:
    def test_no_se_ordena_contra_los_de_marca_pero_su_etiqueta_no_miente(self):
        """El de Bluey no compite contra el cuaderno pelado, pero no puede mentir.

        Quien pide personalizacion ya escogio otra cosa y suele pagar mas por el
        mismo objeto, asi que meterlo en la escalera de marca empujaria al de
        marca hacia abajo y el nivel hablaria de licencia en vez de calidad.

        Pero si esta solo, no tiene con quien compararse y su etiqueta es la que
        traia de nacimiento, que no significa nada. Entonces se lee de la banda
        de precio de los de marca: el mas caro de todos no puede decir
        'economico', porque el papa que pide lo economico paga menos y punto.
        """
        productos = [
            producto("base_eco", "C1", "economico"),
            producto("base_pre", "C1", "premium"),
            producto("bluey", "C1", "economico", personaje="bluey"),
        ]
        cambios = reacomodar(productos, {"base_eco": 100, "base_pre": 200, "bluey": 9000})

        # Los de marca no se movieron: su orden ya era correcto.
        assert "base_eco" not in cambios and "base_pre" not in cambios
        # Y el de Bluey, mas caro que el premium de marca, queda premium.
        assert cambios == {"bluey": "premium"}

    def test_el_de_personaje_barato_cae_en_la_banda_baja(self):
        """La banda funciona en los dos sentidos, no solo para castigar."""
        productos = [
            producto("base_eco", "C1", "economico"),
            producto("base_pre", "C1", "premium"),
            producto("cars", "C1", "premium", personaje="cars"),
        ]
        cambios = reacomodar(productos, {"base_eco": 1000, "base_pre": 5000, "cars": 900})

        assert cambios == {"cars": "economico"}

    def test_sin_productos_de_marca_no_se_inventa_banda(self):
        """Si el concepto solo tiene productos de personaje, no hay referencia.

        Poner una etiqueta a dedo seria repetir el defecto original, asi que se
        deja como esta y el hueco se ve en el informe de carencias.
        """
        productos = [producto("solo", "C1", "confiable", personaje="frozen")]

        assert reacomodar(productos, {"solo": 4000}) == {}

    def test_ordena_dentro_de_un_mismo_personaje(self):
        """Dentro de una misma licencia si hay escalera y si tiene que ordenar."""
        productos = [
            producto("frozen_pre", "C1", "premium", personaje="frozen"),
            producto("frozen_eco", "C1", "economico", personaje="frozen"),
        ]
        cambios = reacomodar(productos, {"frozen_pre": 100, "frozen_eco": 900})

        assert cambios == {"frozen_pre": "economico", "frozen_eco": "premium"}

    def test_el_sku_conserva_el_personaje(self):
        """Reetiquetar no puede perder la licencia: es parte de la identidad."""
        assert sku("C001", "premium", "bluey") == "TK-C001-PRE-BLUEY"
        assert sku("C001", "economico", "") == "TK-C001-ECO"
