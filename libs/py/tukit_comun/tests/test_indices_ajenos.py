from __future__ import annotations

from tukit_comun.migraciones import _filtro, indices_de_infraestructura


class TestLosNombresSalenDelSQL:
    def test_encuentra_los_indices_de_catalogo(self):
        nombres = indices_de_infraestructura("catalogo")
        assert "ix_producto_embedding_hnsw" in nombres
        assert "ix_producto_nombre_trgm" in nombres

    def test_un_servicio_sin_indices_propios_no_es_un_error(self):
        assert indices_de_infraestructura("identidad") == frozenset()
        assert indices_de_infraestructura("no-existe") == frozenset()


class TestQueSeExcluyeYQueNo:
    def test_excluye_el_indice_reflejado_de_infraestructura(self):
        incluir = _filtro(frozenset({"ix_producto_nombre_trgm"}))
        assert not incluir(None, "ix_producto_nombre_trgm", "index", True, None)

    def test_no_esconde_uno_que_un_modelo_declare(self):
        incluir = _filtro(frozenset({"ix_producto_nombre_trgm"}))
        assert incluir(None, "ix_producto_nombre_trgm", "index", False, None)

    def test_no_toca_los_demas_indices_ni_las_tablas(self):
        incluir = _filtro(frozenset({"ix_producto_nombre_trgm"}))
        assert incluir(None, "ix_lista_colegio", "index", True, None)
        assert incluir(None, "ix_producto_nombre_trgm", "table", True, None)
