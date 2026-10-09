"""NFR-MAN-01: lo que el poller de `colegio_verificado` hace cuando el evento viene mal y cuando se ejecuta.

`test_poller.py` fija el camino feliz (alta del colegio, sede, idempotencia y
matricula del hijo). Falta lo que protege a la bandeja y al operador:

- un evento cuyo `colegio_id` no es un UUID se marca publicado SIN dar de alta
  nada (reintentarlo cada pasada no arreglaria el dato);
- la matricula del hijo que esperaba es BEST-EFFORT: una referencia, un grado
  o un cifrador rotos no tumban el alta del colegio ni dejan filas a medias, y
  el motivo se imprime para que alguien lo vea;
- el apodo del menor NO viaja por el Catalogo: el hijo queda con el apodo vacio;
- el motor de lectura se arma desde la variable de entorno del Catalogo, y
  `correr_una_vez` cierra los DOS motores aunque la pasada reviente;
- `_bucle` imprime solo cuando hubo trabajo y duerme el intervalo pedido;
- `main` traduce `--seguir`/`--intervalo` y sale con 0.

Las dos bases son archivos SQLite temporales elegidos por
`TUKIT_IDENTIDAD_DB_URL` y `TUKIT_CATALOGO_DB_URL` (como en produccion, pero sin
Postgres ni red). El tiempo se inyecta: `asyncio.sleep` se sustituye en el
modulo del poller, asi que ninguna prueba duerme de verdad. Los datos son
ficticios (correos `@example.test`, colegios "COLEGIO FICTICIO ...").
"""

from __future__ import annotations

import runpy
import sys
import types
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import MetaData, create_engine, func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from tukit_comun.bandeja import bandeja_reflejada
from tukit_comun.bd import MotorServicio
from tukit_identidad import poller
from tukit_identidad.modelos import (
    AcudienteMatricula,
    Base,
    Colegio,
    Estudiante,
    Matricula,
    Sede,
    Usuario,
)
from tukit_identidad.poller import Poller, _dane_de_carga

pytestmark = pytest.mark.nfr("NFR-MAN-01")

BANDEJA = bandeja_reflejada(MetaData())
COLEGIO = uuid.uuid4()
PADRE = uuid.uuid4()
_SIGUIENTE = [1000]


def _carga(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "colegio_id": str(COLEGIO),
        "grado": "Cuarto",
        "nombre": "COLEGIO FICTICIO UNO",
        "nit": "900.123.456-7",
        "direccion": "Calle 1 # 2-3",
    }
    base.update(extra)
    return base


def _fila_de_bandeja(carga: dict[str, Any]) -> dict[str, Any]:
    """Una fila de la bandeja con `agregado_id` propio: el `colegio_id` de la
    carga puede ser basura, y la columna `agregado_id` exige un UUID."""
    _SIGUIENTE[0] += 1
    return {
        "id": _SIGUIENTE[0],
        "tipo": "colegio_verificado",
        "agregado_tipo": "colegio",
        "agregado_id": uuid.uuid4(),
        "carga": carga,
        "intentos": 0,
    }


async def _encolar(motor_catalogo: AsyncEngine, **carga: Any) -> None:
    async with motor_catalogo.begin() as conexion:
        await conexion.execute(insert(BANDEJA).values(_fila_de_bandeja(carga)))


async def _pendientes(motor_catalogo: AsyncEngine) -> int:
    async with motor_catalogo.begin() as conexion:
        return await conexion.scalar(
            select(func.count()).select_from(BANDEJA).where(BANDEJA.c.publicado_en.is_(None))
        )


async def _contar(motor: MotorServicio) -> tuple[int, int, int]:
    async with motor.sesion() as db:
        estudiantes = (await db.execute(select(func.count()).select_from(Estudiante))).scalar_one()
        matriculas = (await db.execute(select(func.count()).select_from(Matricula))).scalar_one()
        vinculos = (await db.execute(select(func.count()).select_from(AcudienteMatricula))).scalar_one()
    return estudiantes, matriculas, vinculos


async def _colegios(motor: MotorServicio) -> list[Colegio]:
    async with motor.sesion() as db:
        return list((await db.execute(select(Colegio))).scalars())


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield MotorServicio(
        servicio="identidad", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    await engine.dispose()


@pytest_asyncio.fixture
async def motor_catalogo() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(BANDEJA.metadata.create_all)
    yield engine
    await engine.dispose()


async def _sembrar_padre(motor: MotorServicio) -> None:
    async with motor.sesion() as db:
        db.add(Usuario(id=PADRE, correo="acudiente.ficticio@example.test", clave_hash="x"))


class _CifradorRoto:
    """Un cifrador que falla al cifrar, para forzar el error dentro de la
    transaccion de la matricula (despues de que el colegio ya se confirmo)."""

    nombre = "roto"

    def cifrar(self, datos: bytes) -> bytes:
        raise RuntimeError("cifrador roto de prueba")

    def descifrar(self, datos: bytes) -> bytes:
        return datos


class _CifradorDePrueba:
    nombre = "claro-de-prueba"

    def cifrar(self, datos: bytes) -> bytes:
        return b"claro:" + datos

    def descifrar(self, datos: bytes) -> bytes:
        return datos.removeprefix(b"claro:")


class TestEventosQueNoSirvenSeMarcanPublicados:
    @pytest.mark.parametrize("colegio_id", ["no-es-un-uuid", "12345", "00000000-zzzz", 987654321])
    async def test_un_colegio_id_que_no_es_uuid_no_da_de_alta_pero_se_marca_publicado(
        self, motor, motor_catalogo, colegio_id: Any
    ):
        """Reintentar un evento con un id imposible no lo arreglaria: se omite
        (no cuenta) y sale de la bandeja para no volver a leerlo en cada pasada."""
        await _encolar(motor_catalogo, **_carga(colegio_id=colegio_id))
        elpoller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await elpoller.pasada() == 0

        assert await _colegios(motor) == []
        assert await _pendientes(motor_catalogo) == 0

    async def test_un_evento_sin_nombre_ni_clave_nombre_tampoco_da_de_alta(self, motor, motor_catalogo):
        carga = _carga()
        del carga["nombre"]
        await _encolar(motor_catalogo, **carga)

        assert await Poller(motor_identidad=motor, motor_catalogo=motor_catalogo).pasada() == 0

        assert await _colegios(motor) == []
        assert await _pendientes(motor_catalogo) == 0

    async def test_un_evento_valido_junto_a_uno_roto_se_procesa_igual(self, motor, motor_catalogo):
        await _encolar(motor_catalogo, **_carga(colegio_id="no-es-un-uuid"))
        await _encolar(motor_catalogo, **_carga())

        aplicados = await Poller(motor_identidad=motor, motor_catalogo=motor_catalogo).pasada()

        assert aplicados == 1
        [colegio] = await _colegios(motor)
        assert colegio.id == COLEGIO
        assert await _pendientes(motor_catalogo) == 0


class TestDaneDeLaCarga:
    @pytest.mark.parametrize(
        ("carga", "esperado"),
        [
            ({"dane": "311001105731"}, "311001105731"),
            ({"nit": "311001105731"}, "311001105731"),
            # El `dane` explicito manda sobre el `nit`.
            ({"dane": "111111111111", "nit": "222222222222"}, "111111111111"),
            ({"nit": "31100110573"}, None),  # 11 digitos
            ({"nit": "3110011057311"}, None),  # 13 digitos
            ({"nit": "900.123.456-7"}, None),  # NIT tributario con puntuacion
            ({"nit": 311001105731}, None),  # un entero no es un DANE
            ({"dane": "ABCDEFGHIJKL"}, None),
            ({}, None),
        ],
    )
    def test_solo_un_texto_de_exactamente_doce_digitos_es_un_dane(self, carga: dict, esperado: str | None):
        assert _dane_de_carga(carga) == esperado

    async def test_un_segundo_evento_completa_el_dane_vacio_pero_no_pisa_el_que_ya_hay(
        self, motor, motor_catalogo
    ):
        elpoller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)
        await _encolar(motor_catalogo, **_carga(nit="900.123.456-7"))
        await elpoller.pasada()
        [inicial] = await _colegios(motor)
        assert inicial.dane is None

        await _encolar(motor_catalogo, **_carga(dane="311001105731"))
        assert await elpoller.pasada() == 1
        [completado] = await _colegios(motor)
        assert completado.dane == "311001105731"
        assert completado.nit == "900.123.456-7"  # el NIT del revisor no se toca

        await _encolar(motor_catalogo, **_carga(dane="311001999999"))
        await elpoller.pasada()
        [final] = await _colegios(motor)
        assert final.dane == "311001105731"


class TestMatricularAlHijoEsBestEffort:
    @pytest.mark.parametrize("referencia", ["no-es-un-uuid", "12345", 12345, "", None])
    async def test_una_referencia_que_no_es_un_usuario_valido_no_matricula_ni_avisa(
        self, motor, motor_catalogo, referencia: Any, capsys: pytest.CaptureFixture[str]
    ):
        await _sembrar_padre(motor)
        elpoller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        resultado = await elpoller._matricular_al_hijo_que_esperaba(
            _carga(contacto_referencia=referencia), COLEGIO
        )

        assert resultado is None
        assert await _contar(motor) == (0, 0, 0)
        assert capsys.readouterr().out == ""

    @pytest.mark.parametrize("grado", ["", None, "   ", "5", "cuarto", "Decimoquinto"])
    async def test_un_grado_que_no_es_canonico_no_matricula(
        self, motor, motor_catalogo, grado: Any, capsys: pytest.CaptureFixture[str]
    ):
        """Los grados son los quince canonicos (`GRADOS`), con su ortografia: "5"
        o "cuarto" no se adivinan, porque derivarian un id distinto al del registro."""
        await _sembrar_padre(motor)
        elpoller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        await elpoller._matricular_al_hijo_que_esperaba(
            _carga(contacto_referencia=str(PADRE), grado=grado), COLEGIO
        )

        assert await _contar(motor) == (0, 0, 0)
        assert capsys.readouterr().out == ""

    async def test_el_grado_con_espacios_se_recorta_y_el_apodo_del_menor_queda_vacio(
        self, motor, motor_catalogo
    ):
        """El apodo del menor no viaja por el Catalogo: el hijo queda con el apodo
        vacio (cifrado), nunca con un valor tomado del evento."""
        await _sembrar_padre(motor)
        await _encolar(
            motor_catalogo,
            **_carga(contacto_referencia=str(PADRE), grado="  Cuarto  ", apodo="Dato que no debe usarse"),
        )
        cifrador = _CifradorDePrueba()

        aplicados = await Poller(
            motor_identidad=motor, motor_catalogo=motor_catalogo, cifrador=cifrador
        ).pasada()

        assert aplicados == 1
        async with motor.sesion() as db:
            matricula = (await db.execute(select(Matricula))).scalar_one()
            estudiante = (await db.execute(select(Estudiante))).scalar_one()
        assert matricula.grado == "Cuarto"
        assert matricula.colegio_id == COLEGIO
        assert cifrador.descifrar(estudiante.nombre_cifrado) == b""

    async def test_un_fallo_al_matricular_no_tumba_el_alta_y_se_imprime_el_motivo(
        self, motor, motor_catalogo, capsys: pytest.CaptureFixture[str]
    ):
        """El colegio y su sede ya estan confirmados cuando se matricula: si la
        matricula falla, el evento igual cuenta como hecho, no se reprocesa el
        lote y no queda ninguna fila a medias (la transaccion se revierte)."""
        await _sembrar_padre(motor)
        await _encolar(motor_catalogo, **_carga(contacto_referencia=str(PADRE)))
        elpoller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo, cifrador=_CifradorRoto())

        aplicados = await elpoller.pasada()

        assert aplicados == 1
        [colegio] = await _colegios(motor)
        assert colegio.id == COLEGIO
        async with motor.sesion() as db:
            sedes = (await db.execute(select(func.count()).select_from(Sede))).scalar_one()
        assert sedes == 1
        assert await _contar(motor) == (0, 0, 0)
        assert await _pendientes(motor_catalogo) == 0
        assert (
            f"[poller-identidad] no se pudo matricular al hijo de {COLEGIO}: cifrador roto de prueba"
            in capsys.readouterr().out
        )

    async def test_un_colegio_sin_sede_activa_falla_dentro_del_best_effort_sin_lanzar(
        self, motor, motor_catalogo, capsys: pytest.CaptureFixture[str]
    ):
        """Llamado directo sobre un colegio que Identidad no tiene: el 422
        `colegio_sin_sede` del repo se captura e imprime, no sube al drenador."""
        await _sembrar_padre(motor)
        otro = uuid.uuid4()
        elpoller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        await elpoller._matricular_al_hijo_que_esperaba(_carga(contacto_referencia=str(PADRE)), otro)

        assert await _contar(motor) == (0, 0, 0)
        salida = capsys.readouterr().out
        assert f"no se pudo matricular al hijo de {otro}" in salida
        assert "no tiene una sede activa" in salida


@pytest.fixture
def bases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[types.SimpleNamespace]:
    """Dos archivos SQLite: la base propia y la del Catalogo, elegidas por las
    variables de entorno que lee la libreria. Se preparan con motores
    SINCRONOS para que las pruebas de `main` puedan usar `asyncio.run` sin
    chocar con un bucle ya abierto."""
    ruta_identidad = tmp_path / "identidad.db"
    ruta_catalogo = tmp_path / "catalogo.db"
    monkeypatch.setenv("TUKIT_IDENTIDAD_DB_URL", f"sqlite+aiosqlite:///{ruta_identidad}")
    monkeypatch.setenv("TUKIT_CATALOGO_DB_URL", f"sqlite+aiosqlite:///{ruta_catalogo}")
    sync_identidad = create_engine(f"sqlite:///{ruta_identidad}")
    sync_catalogo = create_engine(f"sqlite:///{ruta_catalogo}")
    Base.metadata.create_all(sync_identidad)
    BANDEJA.metadata.create_all(sync_catalogo)

    def encolar(**carga: Any) -> None:
        with sync_catalogo.begin() as conexion:
            conexion.execute(insert(BANDEJA).values(_fila_de_bandeja(carga)))

    def colegios() -> list[Any]:
        with sync_identidad.connect() as conexion:
            return list(conexion.execute(select(Colegio.__table__)))

    def pendientes() -> int:
        with sync_catalogo.connect() as conexion:
            return conexion.scalar(
                select(func.count()).select_from(BANDEJA).where(BANDEJA.c.publicado_en.is_(None))
            )

    yield types.SimpleNamespace(
        ruta_identidad=ruta_identidad,
        ruta_catalogo=ruta_catalogo,
        encolar=encolar,
        colegios=colegios,
        pendientes=pendientes,
    )
    sync_identidad.dispose()
    sync_catalogo.dispose()


class TestMotorDeLectura:
    def test_se_arma_desde_la_variable_del_catalogo_y_no_de_la_propia(self, bases):
        motor = poller._motor_lectura("catalogo")

        try:
            assert isinstance(motor, AsyncEngine)
            assert motor.url.database == str(bases.ruta_catalogo)
            assert motor.url.database != str(bases.ruta_identidad)
        finally:
            # Sin conexiones abiertas: descartar el motor es sincrono y no necesita bucle.
            motor.sync_engine.dispose()


class TestCorrerUnaVez:
    async def test_drena_la_bandeja_del_catalogo_y_da_de_alta_en_la_base_propia(self, bases):
        bases.encolar(**_carga())

        aplicados = await poller.correr_una_vez()

        assert aplicados == 1
        [colegio] = bases.colegios()
        assert colegio.id == COLEGIO
        assert colegio.nombre == "COLEGIO FICTICIO UNO"
        assert bases.pendientes() == 0

    async def test_con_la_bandeja_vacia_devuelve_cero(self, bases):
        assert await poller.correr_una_vez() == 0
        assert bases.colegios() == []

    async def test_cierra_los_dos_motores_al_terminar(self, bases, monkeypatch: pytest.MonkeyPatch):
        cerrados: list[str] = []
        original = AsyncEngine.dispose

        async def espia(self: AsyncEngine, close: bool = True) -> None:
            cerrados.append(str(self.url.database))
            await original(self, close=close)

        monkeypatch.setattr(AsyncEngine, "dispose", espia)

        await poller.correr_una_vez()

        assert sorted(cerrados) == sorted([str(bases.ruta_identidad), str(bases.ruta_catalogo)])

    async def test_cierra_los_dos_motores_aunque_la_pasada_reviente(
        self, bases, monkeypatch: pytest.MonkeyPatch
    ):
        cerrados: list[str] = []
        original = AsyncEngine.dispose

        async def espia(self: AsyncEngine, close: bool = True) -> None:
            cerrados.append(str(self.url.database))
            await original(self, close=close)

        async def pasada_rota(self: Poller, *, limite: int = 100) -> int:
            raise RuntimeError("pasada rota de prueba")

        monkeypatch.setattr(AsyncEngine, "dispose", espia)
        monkeypatch.setattr(Poller, "pasada", pasada_rota)

        with pytest.raises(RuntimeError, match="pasada rota de prueba"):
            await poller.correr_una_vez()

        assert sorted(cerrados) == sorted([str(bases.ruta_identidad), str(bases.ruta_catalogo)])


class _Parar(Exception):
    """Corta el bucle infinito de `_bucle` desde el `sleep` sustituido."""


class TestBucle:
    async def test_imprime_solo_cuando_hubo_trabajo_y_duerme_el_intervalo_pedido(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        resultados = iter([2, 0, 3])
        dormidos: list[float] = []

        async def una_vez() -> int:
            return next(resultados)

        async def dormir(segundos: float) -> None:
            dormidos.append(segundos)
            if len(dormidos) == 3:
                raise _Parar

        monkeypatch.setattr(poller, "correr_una_vez", una_vez)
        # Solo el `asyncio` que ve el poller: el reloj del bucle de pytest no se toca.
        monkeypatch.setattr(poller, "asyncio", types.SimpleNamespace(sleep=dormir))

        with pytest.raises(_Parar):
            await poller._bucle(7.5)

        assert dormidos == [7.5, 7.5, 7.5]
        assert capsys.readouterr().out == (
            "[poller-identidad] colegios dados de alta/actualizados: 2\n"
            "[poller-identidad] colegios dados de alta/actualizados: 3\n"
        )


class TestMain:
    """`main` llama a `asyncio.run`: pruebas sincronas sobre archivos SQLite."""

    def test_una_pasada_da_de_alta_imprime_el_conteo_y_sale_con_0(
        self, bases, capsys: pytest.CaptureFixture[str]
    ):
        bases.encolar(**_carga())

        assert poller.main([]) == 0

        assert capsys.readouterr().out == "[poller-identidad] colegios dados de alta/actualizados: 1\n"
        assert [c.nombre for c in bases.colegios()] == ["COLEGIO FICTICIO UNO"]
        assert bases.pendientes() == 0

    def test_una_pasada_sin_eventos_imprime_cero(self, bases, capsys: pytest.CaptureFixture[str]):
        assert poller.main([]) == 0

        assert capsys.readouterr().out == "[poller-identidad] colegios dados de alta/actualizados: 0\n"

    def test_seguir_corre_el_bucle_con_el_intervalo_dado_y_no_hace_una_pasada(
        self, bases, monkeypatch: pytest.MonkeyPatch
    ):
        recibidos: list[float] = []
        pasadas: list[int] = []

        async def bucle_falso(intervalo: float) -> None:
            recibidos.append(intervalo)

        async def una_vez() -> int:
            pasadas.append(1)
            return 0

        monkeypatch.setattr(poller, "_bucle", bucle_falso)
        monkeypatch.setattr(poller, "correr_una_vez", una_vez)

        assert poller.main(["--seguir", "--intervalo", "2.5"]) == 0

        assert recibidos == [2.5]
        assert pasadas == []

    def test_el_intervalo_por_omision_son_cinco_segundos(self, bases, monkeypatch: pytest.MonkeyPatch):
        recibidos: list[float] = []

        async def bucle_falso(intervalo: float) -> None:
            recibidos.append(intervalo)

        monkeypatch.setattr(poller, "_bucle", bucle_falso)

        poller.main(["--seguir"])

        assert recibidos == [5.0]

    def test_un_intervalo_que_no_es_numero_lo_rechaza_el_analizador_con_2(self, bases):
        with pytest.raises(SystemExit) as salida:
            poller.main(["--seguir", "--intervalo", "mucho"])

        assert salida.value.code == 2

    def test_ejecutado_como_script_hace_una_pasada_y_sale_con_el_codigo_de_main(
        self, bases, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        bases.encolar(**_carga())
        monkeypatch.delitem(sys.modules, "tukit_identidad.poller")
        monkeypatch.setattr(sys, "argv", ["poller"])

        with pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_identidad.poller", run_name="__main__")

        assert salida.value.code == 0
        assert "colegios dados de alta/actualizados: 1" in capsys.readouterr().out
        assert len(bases.colegios()) == 1
