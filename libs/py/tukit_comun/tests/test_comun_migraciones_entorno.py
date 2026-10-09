"""NFR-MAN-01: el entorno de Alembic compartido, sin Postgres ni un `alembic` real (`migraciones.py`).

`test_indices_ajenos.py` fija el filtro de indices. Aqui se prueba el resto de lo
que se puede afirmar sin una base: como se leen los nombres de indice del SQL de
infraestructura, con que opciones configura Alembic cada modo y en que orden
corre el modo en linea. El objeto `context` de Alembic se sustituye por un doble
que anota las llamadas y el motor por uno que no abre conexiones.

Importa porque un `env.py` mal armado no falla en la prueba sino al migrar una
base con datos: sin `compare_type` un cambio de tipo no genera migracion, sin la
exclusion de indices ajenos cada autogenerate propone borrar el HNSW de
busqueda, y una extension creada DENTRO de la primera migracion llega tarde para
las columnas `vector`. El modo fuera de linea nunca debe conectarse (es como se
revisa el SQL antes de tocar produccion).
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from tukit_comun import migraciones
from tukit_comun.migraciones import correr, indices_de_infraestructura

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class Base(DeclarativeBase):
    pass


class Cosa(Base):
    __tablename__ = "cosa_migraciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class ContextoFalso:
    """Doble del `alembic.context`: anota llamadas, no migra nada."""

    def __init__(self, *, fuera_de_linea: bool, falla: Exception | None = None) -> None:
        self.fuera_de_linea = fuera_de_linea
        self.falla = falla
        self.eventos: list[str] = []
        self.configuraciones: list[dict[str, Any]] = []

    def is_offline_mode(self) -> bool:
        return self.fuera_de_linea

    def configure(self, **opciones: Any) -> None:
        self.eventos.append("configure")
        self.configuraciones.append(opciones)

    @contextmanager
    def begin_transaction(self):
        self.eventos.append("begin")
        yield
        self.eventos.append("commit")

    def run_migrations(self) -> None:
        self.eventos.append("migrar")
        if self.falla is not None:
            raise self.falla


@pytest.fixture
def contexto(monkeypatch: pytest.MonkeyPatch) -> ContextoFalso:
    doble = ContextoFalso(fuera_de_linea=False)
    monkeypatch.setattr(migraciones, "context", doble)
    return doble


class TestLosIndicesSeLeenDelSQL:
    @pytest.fixture
    def carpeta(self, tmp_path, monkeypatch):
        monkeypatch.setattr(migraciones, "_INDICES", tmp_path)
        return tmp_path

    def test_extrae_cada_nombre_con_o_sin_if_not_exists_en_cualquier_capitalizacion(self, carpeta):
        (carpeta / "servicio.sql").write_text(
            "CREATE INDEX IF NOT EXISTS ix_uno\n  ON t USING hnsw (c);\n"
            "create index ix_dos on t (c);\n"
            "Create   Index   If  Not  Exists   ix_tres ON t (c);\n",
            encoding="utf-8",
        )

        assert indices_de_infraestructura("servicio") == frozenset({"ix_uno", "ix_dos", "ix_tres"})

    def test_un_archivo_sin_indices_da_vacio(self, carpeta):
        (carpeta / "servicio.sql").write_text("-- nada que indexar\nSELECT 1;\n", encoding="utf-8")

        assert indices_de_infraestructura("servicio") == frozenset()

    def test_cada_servicio_lee_solo_su_archivo(self, carpeta):
        (carpeta / "uno.sql").write_text("CREATE INDEX IF NOT EXISTS ix_de_uno ON t (c);", encoding="utf-8")
        (carpeta / "dos.sql").write_text("CREATE INDEX IF NOT EXISTS ix_de_dos ON t (c);", encoding="utf-8")

        assert indices_de_infraestructura("uno") == frozenset({"ix_de_uno"})
        assert indices_de_infraestructura("dos") == frozenset({"ix_de_dos"})

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-05: indices_de_infraestructura no reconoce CREATE UNIQUE INDEX, "
            "aunque el repo los admite en infra/postgres/indices"
        ),
    )
    def test_reconoce_tambien_los_indices_unicos(self, carpeta):
        """`test_bd_extensiones.py` trata `CREATE UNIQUE INDEX` como una sentencia
        valida de esos archivos, pero la expresion de migraciones.py:38 exige
        `CREATE INDEX`: un indice unico de infraestructura quedaria fuera del
        filtro y Alembic propondria borrarlo en cada autogenerate (el modo de
        fallar que documenta migraciones.py:41-56). Hoy es latente: ningun SQL
        de `infra/postgres/indices` declara uno."""
        (carpeta / "servicio.sql").write_text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_unico ON t (c);", encoding="utf-8"
        )

        assert indices_de_infraestructura("servicio") == frozenset({"ix_unico"})


class TestConfiguracionEnLinea:
    def test_configura_alembic_para_detectar_cambios_de_tipo_y_de_default(self, contexto):
        conexion, metadata = object(), Base.metadata

        migraciones._configurar(conexion, metadata, "catalogo")

        (opciones,) = contexto.configuraciones
        assert opciones["connection"] is conexion
        assert opciones["target_metadata"] is metadata
        assert opciones["compare_type"] is True  # String(64) -> String(128) SI genera migracion
        assert opciones["compare_server_default"] is True
        assert opciones["render_as_batch"] is False

    def test_el_filtro_instalado_deja_en_paz_los_indices_de_infraestructura_de_ese_servicio(self, contexto):
        migraciones._configurar(object(), Base.metadata, "catalogo")

        incluir = contexto.configuraciones[0]["include_object"]
        assert not incluir(None, "ix_producto_embedding_hnsw", "index", True, None)  # HNSW de infra
        assert incluir(None, "ix_producto_embedding_hnsw", "index", False, None)  # declarado: sigue visible
        assert incluir(None, "ix_otro", "index", True, None)

    def test_un_servicio_sin_indices_de_infraestructura_no_excluye_nada(self, contexto):
        migraciones._configurar(object(), Base.metadata, "identidad")

        incluir = contexto.configuraciones[0]["include_object"]
        assert incluir(None, "ix_producto_embedding_hnsw", "index", True, None)

    def test_sincrono_configura_y_migra_dentro_de_una_transaccion(self, contexto):
        migraciones._sincrono(object(), Base.metadata, "catalogo")

        assert contexto.eventos == ["configure", "begin", "migrar", "commit"]

    def test_si_la_migracion_revienta_la_transaccion_no_se_confirma(self, contexto):
        contexto.falla = RuntimeError("migracion rota")

        with pytest.raises(RuntimeError, match="migracion rota"):
            migraciones._sincrono(object(), Base.metadata, "catalogo")

        assert "commit" not in contexto.eventos


class _MotorFalso:
    """Doble de `MotorServicio` para el modo en linea: anota el orden de los pasos."""

    def __init__(self, eventos: list[str]) -> None:
        self._eventos = eventos
        self.engine = SimpleNamespace(begin=self._begin)

    def _begin(self):
        eventos = self._eventos

        class _Transaccion:
            async def __aenter__(self_inner):
                eventos.append("abre_conexion")
                return SimpleNamespace(run_sync=self._run_sync)

            async def __aexit__(self_inner, *a: Any) -> bool:
                eventos.append("cierra_conexion")
                return False

        return _Transaccion()

    async def _run_sync(self, funcion: Any, *args: Any) -> None:
        self._eventos.append("run_sync")
        funcion(object(), *args)

    async def asegurar_extensiones(self) -> None:
        self._eventos.append("extensiones")

    async def cerrar(self) -> None:
        self._eventos.append("motor_cerrado")


class TestModoEnLinea:
    def test_las_extensiones_van_antes_de_la_primera_migracion_y_el_motor_se_cierra(
        self, contexto, monkeypatch
    ):
        """Un tipo `vector` no se puede usar en el mismo paso en que se instala."""
        pedidos: list[str] = []

        def crear_motor(servicio: str) -> _MotorFalso:
            pedidos.append(servicio)
            return _MotorFalso(contexto.eventos)

        monkeypatch.setattr(migraciones, "crear_motor", crear_motor)

        correr("catalogo", Base)

        assert pedidos == ["catalogo"]
        assert contexto.eventos == [
            "abre_conexion",
            "extensiones",
            "run_sync",
            "configure",
            "begin",
            "migrar",
            "commit",
            "cierra_conexion",
            "motor_cerrado",
        ]
        (opciones,) = contexto.configuraciones
        assert opciones["target_metadata"] is Base.metadata

    def test_si_migrar_falla_el_motor_se_cierra_y_el_error_sale(self, contexto, monkeypatch):
        contexto.falla = RuntimeError("migracion rota")
        monkeypatch.setattr(migraciones, "crear_motor", lambda servicio: _MotorFalso(contexto.eventos))

        with pytest.raises(RuntimeError, match="migracion rota"):
            correr("catalogo", Base)

        assert contexto.eventos[-1] == "motor_cerrado"
        assert "commit" not in contexto.eventos


class TestModoFueraDeLinea:
    @pytest.fixture
    def sin_conexiones(self, monkeypatch):
        def prohibido(*a: Any, **kw: Any):
            raise AssertionError("el modo fuera de linea no debe abrir una conexion")

        monkeypatch.setattr(migraciones, "crear_motor", prohibido)

    def test_genera_el_sql_con_la_url_del_entorno_sin_conectarse(self, monkeypatch, sin_conexiones):
        contexto = ContextoFalso(fuera_de_linea=True)
        monkeypatch.setattr(migraciones, "context", contexto)
        monkeypatch.setenv("TUKIT_CATALOGO_DB_URL", "postgresql+asyncpg://u:c@bd.example.test/tukit_catalogo")

        correr("catalogo", Base)

        (opciones,) = contexto.configuraciones
        assert opciones["url"] == "postgresql+asyncpg://u:c@bd.example.test/tukit_catalogo"
        assert opciones["target_metadata"] is Base.metadata
        assert opciones["literal_binds"] is True  # el SQL se imprime con sus valores, listo para revisar
        assert opciones["dialect_opts"] == {"paramstyle": "named"}
        assert opciones["compare_type"] is True
        assert contexto.eventos == ["configure", "begin", "migrar", "commit"]

    def test_tambien_excluye_los_indices_de_infraestructura(self, monkeypatch, sin_conexiones):
        contexto = ContextoFalso(fuera_de_linea=True)
        monkeypatch.setattr(migraciones, "context", contexto)

        correr("catalogo", Base)

        incluir = contexto.configuraciones[0]["include_object"]
        assert not incluir(None, "ix_producto_nombre_trgm", "index", True, None)
        assert incluir(None, "ix_cualquiera", "index", True, None)
