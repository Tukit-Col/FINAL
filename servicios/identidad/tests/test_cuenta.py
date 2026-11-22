from __future__ import annotations

import uuid

import pytest
from tukit_identidad.dominio.sesiones import emitir_token, hashear_clave
from tukit_identidad.modelos import Usuario

from tests._ayudas_identidad import cliente_api


@pytest.fixture()
async def cliente():
    sembrado: dict[str, uuid.UUID] = {}

    async def _sembrar(sesion) -> None:
        usuario = Usuario(correo="mama@ejemplo.com", clave_hash=hashear_clave("demo1234"))
        sesion.add(usuario)
        await sesion.flush()
        sembrado["uid"] = usuario.id

    async with cliente_api(_sembrar) as http:
        uid = sembrado["uid"]
        http.headers["Authorization"] = f"Bearer {emitir_token(uid, version_permisos=1)}"
        http.usuario_id = str(uid)  # type: ignore[attr-defined]
        yield http


async def test_ver_cuenta_devuelve_al_portador(cliente):
    respuesta = await cliente.get("/v1/cuenta")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["usuario_id"] == cliente.usuario_id
    assert cuerpo["correo"] == "mama@ejemplo.com"


async def test_crear_direccion_cifra_la_linea_y_la_devuelve_descifrada(cliente):
    respuesta = await cliente.post(
        "/v1/cuenta/direcciones",
        json={
            "etiqueta": "casa",
            "ciudad": "Bogota",
            "localidad": "Chapinero",
            "linea": "Calle 1 # 2-3 apto 401",
            "contacto": "3001234567",
            "predeterminada": True,
        },
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["linea"] == "Calle 1 # 2-3 apto 401"
    assert cuerpo["contacto"] == "3001234567"
    assert cuerpo["predeterminada"] is True

    lista = (await cliente.get("/v1/cuenta/direcciones")).json()
    assert lista["total"] == 1
    assert lista["direcciones"][0]["ciudad"] == "Bogota"


async def test_solo_una_predeterminada(cliente):
    await cliente.post(
        "/v1/cuenta/direcciones",
        json={"ciudad": "Bogota", "linea": "Calle 1", "predeterminada": True},
    )
    await cliente.post(
        "/v1/cuenta/direcciones",
        json={"ciudad": "Medellin", "linea": "Carrera 2", "predeterminada": True},
    )
    lista = (await cliente.get("/v1/cuenta/direcciones")).json()
    predeterminadas = [d for d in lista["direcciones"] if d["predeterminada"]]
    assert len(predeterminadas) == 1
    assert predeterminadas[0]["ciudad"] == "Medellin"


async def test_editar_direccion_ajena_da_404(cliente):
    respuesta = await cliente.patch(
        f"/v1/cuenta/direcciones/{uuid.uuid4()}",
        json={"ciudad": "Cali", "linea": "Avenida 3"},
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "direccion_no_existe"


async def test_archivar_es_baja_logica(cliente):
    creada = (
        await cliente.post(
            "/v1/cuenta/direcciones",
            json={"ciudad": "Bogota", "linea": "Calle 1"},
        )
    ).json()

    borrado = await cliente.delete(f"/v1/cuenta/direcciones/{creada['direccion_id']}")
    assert borrado.status_code == 204

    lista = (await cliente.get("/v1/cuenta/direcciones")).json()
    assert lista["total"] == 0
    otra_vez = await cliente.delete(f"/v1/cuenta/direcciones/{creada['direccion_id']}")
    assert otra_vez.status_code == 404
