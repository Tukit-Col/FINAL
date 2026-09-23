"""Los indices que aplica la infraestructura no los borra una migracion.

Un indice HNSW o GIN vive en `infra/postgres/indices/*.sql` porque no se puede
declarar en SQLAlchemy sin atarse al dialecto. Alembic lo encuentra en la base,
no lo ve en el metadata y propone borrarlo. Aceptar esa propuesta no rompe
ninguna prueba: las consultas siguen devolviendo lo mismo, solo que recorriendo
la tabla entera. Por eso hace falta una prueba aqui, en el filtro, y no en el
resultado de una busqueda.
"""

from __future__ import annotations

from tukit_comun.migraciones import _filtro, indices_de_infraestructura


class TestLosNombresSalenDelSQL:
    def test_encuentra_los_indices_de_catalogo(self):
        nombres = indices_de_infraestructura("catalogo")
        assert "ix_producto_embedding_hnsw" in nombres
        assert "ix_producto_nombre_trgm" in nombres

    def test_un_servicio_sin_indices_propios_no_es_un_error(self):
        # `identidad` no tiene archivo de indices y su `alembic check` debe
        # correr igual. Que devuelva vacio y no que falle.
        assert indices_de_infraestructura("identidad") == frozenset()
        assert indices_de_infraestructura("no-existe") == frozenset()


class TestQueSeExcluyeYQueNo:
    def test_excluye_el_indice_reflejado_de_infraestructura(self):
        incluir = _filtro(frozenset({"ix_producto_nombre_trgm"}))
        assert not incluir(None, "ix_producto_nombre_trgm", "index", True, None)

    def test_no_esconde_uno_que_un_modelo_declare(self):
        # Si manana alguien declara este indice en un modelo, la diferencia
        # tiene que volver a aparecer. Excluir tambien lo declarado lo
        # esconderia para siempre, que es peor que el problema original.
        incluir = _filtro(frozenset({"ix_producto_nombre_trgm"}))
        assert incluir(None, "ix_producto_nombre_trgm", "index", False, None)

    def test_no_toca_los_demas_indices_ni_las_tablas(self):
        incluir = _filtro(frozenset({"ix_producto_nombre_trgm"}))
        assert incluir(None, "ix_lista_colegio", "index", True, None)
        assert incluir(None, "ix_producto_nombre_trgm", "table", True, None)
