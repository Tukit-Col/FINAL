"""NFR-MAN-01: el repositorio y el router de casos de Operacion contra SQLite real (bandeja, series, alta).

`test_api_operacion.py` fija el camino feliz del contrato y `test_dominio_casos.py` las reglas puras.
Aqui se ejerce el SQL de `RepoCasos` (ADR 0019: contra una base real, no un doble) y los bordes del
router que quedaban sin dueno: que cuenta cada tarjeta del resumen (con reloj inyectado), en que orden
sale la bandeja, como se filtran las series, que se guarda al abrir una PQRS y que NO (el contacto), y
que pasa cuando Identidad no contesta o la entrada es mala (400 sin eco de lo enviado).

Importa porque la bandeja es lo primero que ve el operador cada manana: un conteo mal acotado esconde un
caso vencido, y un alta que guarde el contacto o filtre el correo en un error rompe la promesa de la Ley
1581. Se caracteriza ademas el hallazgo H-C-06: las rutas del back-office (bandeja, caso y series) no
piden credencial alguna. Los datos son ficticios; no hay red ni Identidad real.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.api import app
from tukit_operacion.modelos import Base
from tukit_operacion.repositorios import RepoCasos
from tukit_operacion.repositorios.casos import CASO, METRICA, serializar_caso

pytestmark = pytest.mark.nfr("NFR-MAN-01")

CORREO = "acudiente.ficticio@example.test"
CELULAR = "3000000000"
USUARIO = "22222222-2222-5222-8222-222222222222"
TRABAJO = "44444444-4444-5444-8444-444444444444"
AHORA = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)


def _utc(dia: int, hora: int = 0, minuto: int = 0, segundo: int = 0, mes: int = 9) -> datetime:
    return datetime(2026, mes, dia, hora, minuto, segundo, tzinfo=UTC)


TOKEN_OPERADOR = "token-ficticio-del-operador"
# Desde oe5 (cef2c25) la bandeja y el detalle de un caso son solo del equipo (`_exigir_staff`): las
# lecturas de estas pruebas llegan con la sesion de un operador (decision N-149).
OPERADOR = {"authorization": f"Bearer {TOKEN_OPERADOR}"}
_SESIONES = {
    TOKEN_OPERADOR: {
        "usuario_id": "66666666-6666-5666-8666-666666666666",
        "correo": "operador@example.test",
        "roles": [{"rol": "operador", "ambito": None}],
    },
    # La de `CREDENCIALES`: una sesion valida, pero de un acudiente.
    "sesion-ficticia-de-un-acudiente": {
        "usuario_id": USUARIO,
        "correo": CORREO,
        "roles": [{"rol": "acudiente", "ambito": None}],
    },
}


class IdentidadDoble:
    """Identidad de mentira: devuelve un titular fijo, o `None` si se la marca caida.

    Valida dos tokens, el del operador y el de un acudiente; cualquier otro es una sesion que no
    existe."""

    def __init__(self) -> None:
        self.caida = False
        self.llamadas: list[tuple[str, str | None]] = []

    async def resolver_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.llamadas.append((correo, celular))
        return None if self.caida else USUARIO

    async def sesion(self, token: str) -> dict[str, Any] | None:
        return _SESIONES.get(token)


@dataclass
class Entorno:
    http: httpx.AsyncClient
    motor: MotorServicio
    identidad: IdentidadDoble


@pytest_asyncio.fixture
async def entorno(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Entorno]:
    """La app real sobre SQLite en memoria; el estado compartido de `app` se restaura al terminar."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="operacion", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    identidad = IdentidadDoble()
    monkeypatch.setattr(app.state, "motor", motor, raising=False)
    monkeypatch.setattr(app.state, "identidad", identidad, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield Entorno(http, motor, identidad)
    await engine.dispose()


async def _sembrar_caso(motor: MotorServicio, **campos: Any) -> uuid.UUID:
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "origen": "sistema",
        "categoria": "pago",
        "estado": "abierto",
        "prioridad": "media",
        "asunto": "Asunto Ficticio",
        "descripcion": "",
        "abierto_en": _utc(1),
        **campos,
    }
    async with motor.sesion() as db:
        await db.execute(insert(CASO).values(**valores))
    return valores["id"]


async def _sembrar_metricas(motor: MotorServicio, *filas: tuple[datetime, str, str | None, str, int]) -> None:
    async with motor.sesion() as db:
        for fecha, dimension, dimension_id, metrica, valor in filas:
            await db.execute(
                insert(METRICA).values(
                    id=uuid.uuid4(),
                    fecha=fecha.date(),
                    dimension=dimension,
                    dimension_id=dimension_id,
                    metrica=metrica,
                    valor=valor,
                )
            )


async def _casos_guardados(motor: MotorServicio) -> list[Any]:
    async with motor.sesion() as db:
        return list(await (await db.connection()).execute(select(CASO)))


def _solicitud(**cambios: Any) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "categoria": "peticion",
        "asunto": "Asunto ficticio del caso",
        "descripcion": "Descripcion ficticia del caso.",
        "contacto": {"correo": CORREO, "celular": CELULAR},
    }
    cuerpo.update(cambios)
    return cuerpo


# ---------------------------------------------------------------------------
# RepoCasos.resumen: que cuenta cada tarjeta de la bandeja
# ---------------------------------------------------------------------------


class TestElResumenDeLaBandeja:
    async def test_sin_casos_todo_es_cero_y_entero(self, entorno):
        async with entorno.motor.sesion() as db:
            resumen = await RepoCasos(await db.connection()).resumen(AHORA)

        assert resumen == {"abiertos": 0, "urgentes": 0, "vencen_hoy": 0, "resueltos_semana": 0}

    async def test_cada_tarjeta_cuenta_lo_que_dice_su_nombre(self, entorno):
        motor = entorno.motor
        # Activos: cuentan en abiertos. vence_en decide "vencen hoy" (el vencido tambien cuenta).
        await _sembrar_caso(motor, estado="abierto", prioridad="media", vence_en=_utc(25, 18))
        await _sembrar_caso(motor, estado="en_gestion", prioridad="urgente", vence_en=_utc(20))
        await _sembrar_caso(motor, estado="esperando_tercero", prioridad="alta", vence_en=_utc(26))
        await _sembrar_caso(motor, estado="abierto", prioridad="baja", vence_en=None)
        # Inactivos: no son abiertos, ni urgentes, ni vencen, aunque su fecha o prioridad lo sugiera.
        await _sembrar_caso(
            motor, estado="resuelto", prioridad="urgente", vence_en=_utc(25, 12), resuelto_en=_utc(24)
        )
        await _sembrar_caso(motor, estado="cerrado", prioridad="media", resuelto_en=_utc(10))

        async with motor.sesion() as db:
            resumen = await RepoCasos(await db.connection()).resumen(AHORA)

        assert resumen == {
            "abiertos": 4,
            "urgentes": 1,  # el urgente resuelto no cuenta
            "vencen_hoy": 2,  # el de hoy y el ya vencido; ni el de manana ni el sin termino ni el resuelto
            "resueltos_semana": 1,  # el resuelto de ayer; el cerrado del dia 10 ya salio de la ventana
        }

    @pytest.mark.parametrize(
        ("vence", "cuenta"),
        [
            (_utc(25, 23, 59, 59), True),  # el ultimo segundo del dia todavia es "hoy"
            (_utc(26, 0, 0, 0), False),  # la medianoche ya es manana
            (_utc(1), True),  # un caso vencido hace semanas sigue pendiente: no se esconde
        ],
        ids=["ultimo-segundo", "medianoche", "vencido-hace-semanas"],
    )
    async def test_el_limite_de_vencen_hoy(self, entorno, vence, cuenta):
        await _sembrar_caso(entorno.motor, vence_en=vence)

        async with entorno.motor.sesion() as db:
            resumen = await RepoCasos(await db.connection()).resumen(AHORA)

        assert resumen["vencen_hoy"] == int(cuenta)

    @pytest.mark.parametrize(
        ("resuelto_en", "cuenta"),
        [
            (AHORA - timedelta(days=7), True),  # exactamente hace siete dias: dentro (>=)
            (AHORA - timedelta(days=7, seconds=1), False),
            (AHORA, True),
        ],
        ids=["siete-dias-exactos", "un-segundo-fuera", "ahora-mismo"],
    )
    async def test_la_ventana_de_resueltos_de_la_semana_incluye_su_borde(self, entorno, resuelto_en, cuenta):
        await _sembrar_caso(entorno.motor, estado="resuelto", resuelto_en=resuelto_en)

        async with entorno.motor.sesion() as db:
            resumen = await RepoCasos(await db.connection()).resumen(AHORA)

        assert resumen["resueltos_semana"] == int(cuenta)


# ---------------------------------------------------------------------------
# RepoCasos: lectura de un caso, serializacion y alta
# ---------------------------------------------------------------------------


class TestLecturaYAltaEnElRepositorio:
    async def test_obtener_devuelve_la_fila_o_none_si_no_existe(self, entorno):
        caso_id = await _sembrar_caso(entorno.motor, asunto="Asunto Ficticio Buscado")

        async with entorno.motor.sesion() as db:
            repo = RepoCasos(await db.connection())
            encontrado = await repo.obtener(caso_id)
            ausente = await repo.obtener(uuid.uuid4())

        assert encontrado is not None
        assert encontrado.asunto == "Asunto Ficticio Buscado"
        assert ausente is None

    async def test_listar_casos_devuelve_todas_las_filas_sin_filtrar_por_estado(self, entorno):
        await _sembrar_caso(entorno.motor, estado="abierto")
        await _sembrar_caso(entorno.motor, estado="cerrado")

        async with entorno.motor.sesion() as db:
            filas = await RepoCasos(await db.connection()).listar_casos()

        assert sorted(f.estado for f in filas) == ["abierto", "cerrado"]

    async def test_serializar_caso_publica_el_contrato_de_lectura_y_nunca_titular_ni_descripcion(
        self, entorno
    ):
        referencias = {name: uuid.uuid4() for name in ("trabajo_id", "pedido_id", "asignado_a_id")}
        caso_id = await _sembrar_caso(
            entorno.motor,
            origen="acudiente",
            descripcion="Descripcion ficticia privada",
            usuario_id=uuid.UUID(USUARIO),
            vence_en=_utc(30, 8),
            **referencias,
        )
        async with entorno.motor.sesion() as db:
            fila = await RepoCasos(await db.connection()).obtener(caso_id)

        publicado = serializar_caso(fila)

        assert publicado == {
            "caso_id": str(caso_id),
            "origen": "acudiente",
            "categoria": "pago",
            "estado": "abierto",
            "prioridad": "media",
            "asunto": "Asunto Ficticio",
            "abierto_en": "2026-09-01T00:00:00",
            "vence_en": "2026-09-30T08:00:00",
            "trabajo_id": str(referencias["trabajo_id"]),
            "pedido_id": str(referencias["pedido_id"]),
            "asignado_a": str(referencias["asignado_a_id"]),
        }
        assert USUARIO not in str(publicado)  # el titular no sale por la bandeja
        assert "privada" not in str(publicado)

    async def test_serializar_caso_deja_en_none_lo_que_no_tiene(self, entorno):
        caso_id = await _sembrar_caso(entorno.motor)
        async with entorno.motor.sesion() as db:
            fila = await RepoCasos(await db.connection()).obtener(caso_id)

        publicado = serializar_caso(fila)

        assert (
            publicado["vence_en"],
            publicado["trabajo_id"],
            publicado["pedido_id"],
            publicado["asignado_a"],
        ) == (
            None,
            None,
            None,
            None,
        )

    async def test_insertar_caso_abre_un_caso_de_origen_acudiente_en_estado_abierto(self, entorno):
        caso_id, usuario, trabajo = uuid.uuid4(), uuid.UUID(USUARIO), uuid.UUID(TRABAJO)

        async with entorno.motor.sesion() as db:
            await RepoCasos(await db.connection()).insertar_caso(
                caso_id=caso_id,
                categoria="reclamo",
                prioridad="alta",
                asunto="Asunto ficticio",
                descripcion="Descripcion ficticia",
                usuario_id=usuario,
                trabajo_id=trabajo,
                abierto_en=_utc(25, 10),
                vence_en=_utc(30, 10),
            )

        (fila,) = await _casos_guardados(entorno.motor)
        assert (fila.id, fila.origen, fila.estado, fila.categoria, fila.prioridad) == (
            caso_id,
            "acudiente",
            "abierto",
            "reclamo",
            "alta",
        )
        assert (fila.usuario_id, fila.trabajo_id, fila.pedido_id, fila.asignado_a_id) == (
            usuario,
            trabajo,
            None,
            None,
        )
        assert (fila.asunto, fila.descripcion) == ("Asunto ficticio", "Descripcion ficticia")

    async def test_insertar_caso_sin_titular_ni_trabajo_ni_termino_es_valido(self, entorno):
        async with entorno.motor.sesion() as db:
            await RepoCasos(await db.connection()).insertar_caso(
                caso_id=uuid.uuid4(),
                categoria="sugerencia",
                prioridad="baja",
                asunto="Asunto ficticio",
                descripcion="Descripcion ficticia",
                usuario_id=None,
                trabajo_id=None,
                abierto_en=_utc(25),
                vence_en=None,
            )

        (fila,) = await _casos_guardados(entorno.motor)
        assert (fila.usuario_id, fila.trabajo_id, fila.vence_en) == (None, None, None)


# ---------------------------------------------------------------------------
# La bandeja y el detalle por HTTP
# ---------------------------------------------------------------------------


class TestLaBandeja:
    async def test_ordena_por_prioridad_luego_por_vencimiento_y_deja_al_final_a_los_sin_termino(
        self, entorno
    ):
        motor = entorno.motor
        # Se siembran desordenados: el orden de salida no puede ser el de insercion.
        baja = await _sembrar_caso(motor, prioridad="baja", vence_en=_utc(2))
        urgente_sin_termino = await _sembrar_caso(motor, prioridad="urgente", vence_en=None)
        urgente_tardio = await _sembrar_caso(motor, prioridad="urgente", vence_en=_utc(1, mes=10))
        media = await _sembrar_caso(motor, prioridad="media", vence_en=_utc(2))
        urgente_proximo = await _sembrar_caso(motor, prioridad="urgente", vence_en=_utc(28, 12))
        alta = await _sembrar_caso(motor, prioridad="alta", vence_en=_utc(30))

        respuesta = await entorno.http.get("/v1/operacion/casos", headers=OPERADOR)

        assert respuesta.status_code == 200
        assert [c["caso_id"] for c in respuesta.json()["casos"]] == [
            str(i) for i in (urgente_proximo, urgente_tardio, urgente_sin_termino, alta, media, baja)
        ]

    async def test_sin_casos_devuelve_resumen_en_ceros_y_lista_vacia(self, entorno):
        respuesta = await entorno.http.get("/v1/operacion/casos", headers=OPERADOR)

        assert respuesta.status_code == 200
        assert respuesta.json() == {
            "resumen": {"abiertos": 0, "urgentes": 0, "vencen_hoy": 0, "resueltos_semana": 0},
            "casos": [],
        }

    async def test_la_lista_trae_todos_los_casos_y_el_resumen_solo_los_activos(self, entorno):
        """La lista trae TODOS los casos (el filtro es de la pantalla); el resumen solo los activos."""
        await _sembrar_caso(entorno.motor, estado="abierto", prioridad="urgente")
        await _sembrar_caso(entorno.motor, estado="resuelto", prioridad="urgente", resuelto_en=_utc(1))

        cuerpo = (await entorno.http.get("/v1/operacion/casos", headers=OPERADOR)).json()

        assert len(cuerpo["casos"]) == 2
        assert (cuerpo["resumen"]["abiertos"], cuerpo["resumen"]["urgentes"]) == (1, 1)


class TestElDetalleDeUnCaso:
    async def test_devuelve_el_caso_con_su_forma_de_contrato(self, entorno):
        pedido = uuid.uuid4()
        caso_id = await _sembrar_caso(entorno.motor, categoria="entrega", prioridad="alta", pedido_id=pedido)

        respuesta = await entorno.http.get(f"/v1/operacion/casos/{caso_id}", headers=OPERADOR)

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        # Desde oe5 (cef2c25) el detalle del back-office es el de `serializar_detalle_caso` mas la
        # historia del ticket: suma el cuerpo de la PQRS, el titular, la resolucion y los eventos.
        assert set(cuerpo) == {
            "caso_id",
            "origen",
            "categoria",
            "estado",
            "prioridad",
            "asunto",
            "abierto_en",
            "vence_en",
            "trabajo_id",
            "pedido_id",
            "asignado_a",
            "descripcion",
            "usuario_id",
            "resuelto_en",
            "eventos",
        }
        assert cuerpo["eventos"] == []
        assert (cuerpo["caso_id"], cuerpo["categoria"], cuerpo["pedido_id"]) == (
            str(caso_id),
            "entrega",
            str(pedido),
        )

    async def test_un_identificador_que_no_es_uuid_es_una_entrada_invalida_y_no_un_404(self, entorno):
        respuesta = await entorno.http.get("/v1/operacion/casos/no-es-un-uuid", headers=OPERADOR)

        assert respuesta.status_code == 400
        assert respuesta.json() == {
            "error": "entrada_invalida",
            "mensaje": "La peticion no tiene la forma que el contrato espera.",
            "campo": "caso_id",
        }

    async def test_el_404_trae_el_sobre_de_error_del_dominio(self, entorno):
        respuesta = await entorno.http.get(f"/v1/operacion/casos/{uuid.uuid4()}", headers=OPERADOR)

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "caso_no_existe"


# ---------------------------------------------------------------------------
# Las series de metricas: filtros y orden
# ---------------------------------------------------------------------------

DIA_24 = _utc(24)
DIA_25 = _utc(25)

METRICAS = (
    (DIA_25, "global", None, "cobertura_bps", 5000),
    (DIA_25, "colegio", "col-1", "kits_armados", 4),
    (DIA_24, "colegio", "col-1", "kits_armados", 3),
    (DIA_25, "colegio", "col-2", "cobertura_bps", 7000),
    (DIA_24, "catalogo", None, "conceptos", 10),
    (DIA_25, "catalogo", None, "conceptos", 11),
)


def _clave(punto: dict[str, Any]) -> tuple[str, str, str | None, str, int]:
    return (punto["fecha"], punto["dimension"], punto["dimension_id"], punto["metrica"], punto["valor"])


class TestLasSeriesDeMetricas:
    @pytest.fixture(autouse=True)
    async def _sembrar(self, entorno: Entorno) -> None:
        await _sembrar_metricas(entorno.motor, *METRICAS)

    async def _pedir(self, entorno: Entorno, **parametros: str) -> list[tuple[Any, ...]]:
        respuesta = await entorno.http.get("/v1/operacion/metricas", params=parametros)
        assert respuesta.status_code == 200
        return [_clave(p) for p in respuesta.json()["puntos"]]

    async def test_sin_filtros_devuelve_toda_la_traza_por_fecha_dimension_y_metrica(self, entorno):
        assert await self._pedir(entorno) == [
            ("2026-09-24", "catalogo", None, "conceptos", 10),
            ("2026-09-24", "colegio", "col-1", "kits_armados", 3),
            ("2026-09-25", "catalogo", None, "conceptos", 11),
            ("2026-09-25", "colegio", "col-2", "cobertura_bps", 7000),
            ("2026-09-25", "colegio", "col-1", "kits_armados", 4),
            ("2026-09-25", "global", None, "cobertura_bps", 5000),
        ]

    async def test_la_dimension_acota_la_serie(self, entorno):
        puntos = await self._pedir(entorno, dimension="colegio")

        assert {p[1] for p in puntos} == {"colegio"}
        assert len(puntos) == 3

    async def test_el_id_de_dimension_acota_aunque_no_se_pida_la_dimension(self, entorno):
        puntos = await self._pedir(entorno, dimension_id="col-1")

        assert [(p[0], p[3], p[4]) for p in puntos] == [
            ("2026-09-24", "kits_armados", 3),
            ("2026-09-25", "kits_armados", 4),
        ]

    async def test_dimension_e_id_se_combinan(self, entorno):
        assert await self._pedir(entorno, dimension="colegio", dimension_id="col-2") == [
            ("2026-09-25", "colegio", "col-2", "cobertura_bps", 7000)
        ]
        assert await self._pedir(entorno, dimension="global", dimension_id="col-2") == []

    @pytest.mark.parametrize(
        "desde",
        ["2026-09-25", "2026-09-25T23:59:59"],
        ids=["fecha", "fecha-con-hora"],
    )
    async def test_desde_es_inclusivo_y_solo_mira_el_dia(self, entorno, desde):
        puntos = await self._pedir(entorno, desde=desde)

        assert {p[0] for p in puntos} == {"2026-09-25"}
        assert len(puntos) == 4

    async def test_desde_posterior_a_todo_lo_congelado_da_una_serie_vacia_y_no_un_404(self, entorno):
        assert await self._pedir(entorno, desde="2026-12-31") == []

    async def test_una_dimension_sin_datos_da_una_serie_vacia(self, entorno):
        assert await self._pedir(entorno, dimension="inexistente") == []

    async def test_los_filtros_vacios_no_filtran(self, entorno):
        todo = await self._pedir(entorno)

        assert await self._pedir(entorno, dimension="", dimension_id="", desde="") == todo

    async def test_el_filtro_de_fecha_se_combina_con_el_de_dimension(self, entorno):
        assert await self._pedir(entorno, dimension="catalogo", desde="2026-09-25") == [
            ("2026-09-25", "catalogo", None, "conceptos", 11)
        ]


# ---------------------------------------------------------------------------
# El alta de una PQRS
# ---------------------------------------------------------------------------


class TestAbrirUnCaso:
    async def test_responde_201_con_el_recibo_y_guarda_el_caso_con_el_titular_ya_resuelto(self, entorno):
        respuesta = await entorno.http.post("/v1/operacion/casos", json=_solicitud(categoria="reclamo"))

        recibo = respuesta.json()
        assert respuesta.status_code == 201
        assert set(recibo) == {"caso_id", "estado", "categoria", "recibido_en", "vence_en"}
        assert (recibo["estado"], recibo["categoria"]) == ("abierto", "reclamo")
        (fila,) = await _casos_guardados(entorno.motor)
        assert str(fila.id) == recibo["caso_id"]
        assert (fila.origen, fila.estado, fila.usuario_id) == ("acudiente", "abierto", uuid.UUID(USUARIO))
        assert (fila.asunto, fila.descripcion) == (
            "Asunto ficticio del caso",
            "Descripcion ficticia del caso.",
        )

    async def test_el_contacto_viaja_a_identidad_y_no_queda_en_ninguna_columna(self, entorno):
        await entorno.http.post("/v1/operacion/casos", json=_solicitud())

        (fila,) = await _casos_guardados(entorno.motor)
        assert entorno.identidad.llamadas == [(CORREO, CELULAR)]
        assert CORREO not in str(tuple(fila))
        assert CELULAR not in str(tuple(fila))

    @pytest.mark.parametrize(
        ("categoria", "prioridad", "horas"),
        [
            ("peticion", "media", 360),
            ("queja", "media", 360),
            ("reclamo", "alta", 360),
            ("sugerencia", "baja", 720),
            ("pago", "urgente", 24),
            ("entrega", "alta", 48),
        ],
    )
    async def test_cada_categoria_nace_con_su_prioridad_y_su_plazo(
        self, entorno, categoria, prioridad, horas
    ):
        recibo = (await entorno.http.post("/v1/operacion/casos", json=_solicitud(categoria=categoria))).json()

        leido = await entorno.http.get(f"/v1/operacion/casos/{recibo['caso_id']}", headers=OPERADOR)
        detalle = leido.json()
        plazo = datetime.fromisoformat(recibo["vence_en"]) - datetime.fromisoformat(recibo["recibido_en"])
        assert detalle["prioridad"] == prioridad
        assert plazo == timedelta(hours=horas)

    async def test_si_identidad_no_contesta_el_caso_se_abre_igual_sin_titular(self, entorno):
        entorno.identidad.caida = True

        respuesta = await entorno.http.post("/v1/operacion/casos", json=_solicitud())

        assert respuesta.status_code == 201
        (fila,) = await _casos_guardados(entorno.motor)
        assert fila.usuario_id is None
        assert CORREO not in str(tuple(fila))  # sin titular, el contacto tampoco se guarda "por si acaso"

    async def test_un_trabajo_valido_queda_referenciado_en_el_caso(self, entorno):
        respuesta = await entorno.http.post("/v1/operacion/casos", json=_solicitud(trabajo_id=TRABAJO))

        assert respuesta.status_code == 201
        (fila,) = await _casos_guardados(entorno.motor)
        assert fila.trabajo_id == uuid.UUID(TRABAJO)

    @pytest.mark.parametrize("trabajo", [None, ""], ids=["nulo", "vacio"])
    async def test_sin_trabajo_el_caso_no_referencia_ninguno(self, entorno, trabajo):
        await entorno.http.post("/v1/operacion/casos", json=_solicitud(trabajo_id=trabajo))

        (fila,) = await _casos_guardados(entorno.motor)
        assert fila.trabajo_id is None

    async def test_un_trabajo_mal_formado_se_rechaza_antes_de_hablar_con_identidad(self, entorno):
        respuesta = await entorno.http.post("/v1/operacion/casos", json=_solicitud(trabajo_id="no-es-uuid"))

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "trabajo_invalido"
        assert respuesta.json()["campo"] == "trabajo_id"
        assert entorno.identidad.llamadas == []
        assert await _casos_guardados(entorno.motor) == []

    @pytest.mark.parametrize("categoria", ["inventada", "mapeo_lista", "autenticacion", "stock"])
    async def test_una_categoria_rechazada_no_manda_el_contacto_a_identidad_ni_guarda_nada(
        self, entorno, categoria
    ):
        """Minimizacion: lo que se va a rechazar no tiene por que entregar el contacto a otro servicio."""
        respuesta = await entorno.http.post("/v1/operacion/casos", json=_solicitud(categoria=categoria))

        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "categoria"
        assert entorno.identidad.llamadas == []
        assert await _casos_guardados(entorno.motor) == []

    @pytest.mark.parametrize(
        ("cambios", "campo"),
        [
            pytest.param({"asunto": ""}, "asunto", id="asunto-vacio"),
            pytest.param({"asunto": "a" * 257}, "asunto", id="asunto-de-257"),
            pytest.param({"descripcion": ""}, "descripcion", id="descripcion-vacia"),
            pytest.param({"descripcion": "d" * 4097}, "descripcion", id="descripcion-de-4097"),
            pytest.param({"categoria": "c" * 25}, "categoria", id="categoria-de-25"),
            pytest.param(
                {"contacto": {"correo": "a@b", "celular": CELULAR}}, "contacto.correo", id="correo-corto"
            ),
            pytest.param(
                {"contacto": {"correo": CORREO, "celular": ""}}, "contacto.celular", id="celular-vacio"
            ),
            pytest.param({"contacto": {"correo": CORREO}}, "contacto.celular", id="sin-celular"),
            pytest.param({"contacto": None}, "contacto", id="contacto-nulo"),
        ],
    )
    async def test_una_entrada_mala_es_400_sin_eco_de_lo_enviado_y_no_toca_identidad(
        self, entorno, cambios, campo
    ):
        respuesta = await entorno.http.post("/v1/operacion/casos", json=_solicitud(**cambios))

        assert respuesta.status_code == 400
        assert respuesta.json() == {
            "error": "entrada_invalida",
            "mensaje": "La peticion no tiene la forma que el contrato espera.",
            "campo": campo,
        }
        assert CORREO not in respuesta.text  # el sobre de error nunca repite el contacto
        assert entorno.identidad.llamadas == []
        assert await _casos_guardados(entorno.motor) == []

    async def test_los_limites_exactos_de_longitud_se_aceptan(self, entorno):
        respuesta = await entorno.http.post(
            "/v1/operacion/casos", json=_solicitud(asunto="a" * 256, descripcion="d" * 4096)
        )

        assert respuesta.status_code == 201
        (fila,) = await _casos_guardados(entorno.motor)
        assert (len(fila.asunto), len(fila.descripcion)) == (256, 4096)

    async def test_un_cuerpo_que_no_es_json_es_400(self, entorno):
        respuesta = await entorno.http.post(
            "/v1/operacion/casos", content=b"no es json", headers={"content-type": "application/json"}
        )

        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "entrada_invalida"
        assert entorno.identidad.llamadas == []


# ---------------------------------------------------------------------------
# H-C-06: las rutas del back-office no piden credencial
# ---------------------------------------------------------------------------

CREDENCIALES = pytest.mark.parametrize(
    "cabeceras",
    [{}, {"authorization": "Bearer sesion-ficticia-de-un-acudiente"}],
    ids=["sin_credencial", "con_sesion_de_acudiente"],
)


class TestControlDeAccesoDelBackOffice:
    """El contrato de hoy declara "Ninguna ruta pide token" (CONTRATO_API.md:1195): es el hallazgo
    H-C-06. Se fija la conducta CORRECTA (la bandeja, el caso y las series son del operador: sin
    credencial de staff responden 401/403 y no filtran asuntos) para que, al cerrarlo, estas pruebas
    dejen de ser xfail y protejan la regresion."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-C-06: la bandeja del back-office no exige staff y entrega los casos de todos a cualquiera: "
            "routers/operacion.py:63-72 (sin dependencia de autenticacion)"
        ),
    )
    @CREDENCIALES
    async def test_la_bandeja_exige_staff_y_no_filtra_los_casos(self, entorno, cabeceras):
        await _sembrar_caso(entorno.motor, asunto="Asunto Ficticio Confidencial")

        respuesta = await entorno.http.get("/v1/operacion/casos", headers=cabeceras)

        assert respuesta.status_code in (401, 403)
        assert "Asunto Ficticio Confidencial" not in respuesta.text

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-C-06: el detalle de un caso no exige staff ni que el caso sea del solicitante: "
            "routers/operacion.py:75-81 (sin dependencia de autenticacion)"
        ),
    )
    @CREDENCIALES
    async def test_el_detalle_de_un_caso_exige_staff_y_no_lo_entrega_a_cualquiera(self, entorno, cabeceras):
        caso_id = await _sembrar_caso(entorno.motor, asunto="Asunto Ficticio Confidencial")

        respuesta = await entorno.http.get(f"/v1/operacion/casos/{caso_id}", headers=cabeceras)

        assert respuesta.status_code in (401, 403)
        assert "Asunto Ficticio Confidencial" not in respuesta.text

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-C-06: las series de calidad del panel del operador no exigen staff: "
            "routers/operacion.py:84-129 (sin dependencia de autenticacion)"
        ),
    )
    @CREDENCIALES
    async def test_las_series_de_metricas_exigen_staff(self, entorno, cabeceras):
        await _sembrar_metricas(entorno.motor, (DIA_25, "global", None, "cobertura_bps", 5000))

        respuesta = await entorno.http.get("/v1/operacion/metricas", headers=cabeceras)

        assert respuesta.status_code in (401, 403)
        assert "cobertura_bps" not in respuesta.text
