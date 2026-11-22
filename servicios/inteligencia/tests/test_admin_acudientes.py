from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import insert
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import Base

COLEGIO = "11111111-1111-5111-8111-111111111111"
OTRO = "22222222-2222-5222-8222-222222222222"
TRABAJO = Base.metadata.tables["trabajo_pipeline"]


@pytest.fixture()
async def cliente(motor):
    app.state.motor = motor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http


async def _sembrar(motor, *, usuario_id, estado, colegio, actualizado_en, grado="Cuarto", preferencias=None):
    from tukit_comun.cifrado import cifrador_desde_entorno

    cifradas = cifrador_desde_entorno().cifrar_json(preferencias) if preferencias is not None else None
    async with motor.engine.begin() as conexion:
        await conexion.execute(
            insert(TRABAJO).values(
                id=uuid.uuid4(),
                usuario_id=usuario_id,
                estado=estado,
                origen="colegio_grado",
                hijos=[{"referencia": "h1", "colegio_id": colegio, "grado": grado}],
                preferencias_cifradas=cifradas,
                degradaciones=[],
                estimado_segundos=180,
                creado_en=actualizado_en,
                actualizado_en=actualizado_en,
            )
        )


class TestAcudientesDeColegio:
    async def test_agrupa_por_usuario_con_ultimo_estado(self, cliente, motor):
        u1, u2 = uuid.uuid4(), uuid.uuid4()
        base = datetime(2026, 9, 1, tzinfo=UTC)
        await _sembrar(motor, usuario_id=u1, estado="publicado", colegio=COLEGIO, actualizado_en=base)
        await _sembrar(
            motor,
            usuario_id=u1,
            estado="procesando",
            colegio=COLEGIO,
            actualizado_en=base + timedelta(hours=2),
        )
        await _sembrar(
            motor,
            usuario_id=u2,
            estado="espera_revision",
            colegio=COLEGIO,
            actualizado_en=base + timedelta(hours=1),
        )

        respuesta = await cliente.get(f"/v1/admin/colegios/{COLEGIO}/acudientes")

        assert respuesta.status_code == 200
        filas = respuesta.json()["acudientes"]
        assert len(filas) == 2
        por_id = {f["usuario_id"]: f for f in filas}
        assert por_id[str(u1)]["estado"] == "procesando"
        assert por_id[str(u2)]["estado"] == "espera_revision"
        assert "actualizado_en" in por_id[str(u1)]
        assert "trabajo_id" in por_id[str(u1)]

    async def test_otro_colegio_y_anonimos_no_aparecen(self, cliente, motor):
        u1 = uuid.uuid4()
        base = datetime(2026, 9, 1, tzinfo=UTC)
        await _sembrar(motor, usuario_id=u1, estado="publicado", colegio=OTRO, actualizado_en=base)
        await _sembrar(motor, usuario_id=None, estado="encolado", colegio=COLEGIO, actualizado_en=base)

        respuesta = await cliente.get(f"/v1/admin/colegios/{COLEGIO}/acudientes")

        assert respuesta.status_code == 200
        assert respuesta.json()["acudientes"] == []

    async def test_no_filtra_datos_de_menores(self, cliente, motor):
        u1 = uuid.uuid4()
        await _sembrar(
            motor,
            usuario_id=u1,
            estado="publicado",
            colegio=COLEGIO,
            actualizado_en=datetime(2026, 9, 1, tzinfo=UTC),
        )
        respuesta = await cliente.get(f"/v1/admin/colegios/{COLEGIO}/acudientes")
        cuerpo = respuesta.json()["acudientes"][0]
        assert set(cuerpo) == {
            "usuario_id",
            "estado",
            "actualizado_en",
            "trabajo_id",
            "grados",
            "preferencias",
        }

    async def test_trae_grados_del_colegio_y_preferencias_descifradas(self, cliente, motor):
        u1 = uuid.uuid4()
        base = datetime(2026, 9, 1, tzinfo=UTC)
        prefs = {"presupuesto_por_hijo": 700000, "dolor_declarado": "libros"}
        await _sembrar(
            motor,
            usuario_id=u1,
            estado="publicado",
            colegio=COLEGIO,
            actualizado_en=base + timedelta(hours=1),
            grado="Quinto",
            preferencias=prefs,
        )
        await _sembrar(
            motor,
            usuario_id=u1,
            estado="publicado",
            colegio=OTRO,
            actualizado_en=base,
            grado="Sexto",
        )
        respuesta = await cliente.get(f"/v1/admin/colegios/{COLEGIO}/acudientes")
        cuerpo = respuesta.json()["acudientes"][0]
        assert cuerpo["grados"] == ["Quinto"]
        assert cuerpo["preferencias"] == prefs
