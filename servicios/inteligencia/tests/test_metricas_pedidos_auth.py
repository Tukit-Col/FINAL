"""La puerta operador/admin de `GET /v1/metricas/colegios/{id}/pedidos`.

El cruce lista los `usuario_id` de los padres que pagaron: dato sensible, así que
el endpoint exige Bearer de operador/admin con la MISMA semántica que
`/v1/admin/acudientes` (401 sin token o token inválido, 403 si el rol no es
staff). Inteligencia no puede leer la base de identidad (invariantes 1 y 3):
valida por HTTP contra `GET /v1/sesiones/actual`. Aquí ese cliente se sustituye
por un doble en memoria (`IdentidadFalsa`) que mapea token→roles; una caída de
identidad (`RemotoCaido`) debe FALLAR CERRADA con 503, nunca abrir el acceso.

Se prueba con `ASGITransport`, sin uvicorn ni Postgres: se inyecta el motor de
prueba, el doble de identidad y `ComercioFalso` por `app.state`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from test_metricas_pedidos import ComercioFalso
from tukit_inteligencia.api import app
from tukit_inteligencia.remoto import RemotoCaido

COLEGIO = "22222222-2222-5222-8222-222222222222"


@dataclass
class IdentidadFalsa:
    """Doble del puerto hacia identidad: solo `sesion`, mapeando token→roles.

    Un token ausente del mapa vale como inválido (`None`, => 401). Si `caida` es
    `True`, `sesion` lanza `RemotoCaido` para probar el fallo cerrado (503)."""

    roles_por_token: dict[str, list[str]] = field(default_factory=dict)
    caida: bool = False

    async def sesion(self, token: str) -> dict[str, Any] | None:
        if self.caida:
            raise RemotoCaido("identidad", "simulada")
        if token not in self.roles_por_token:
            return None
        return {
            "usuario_id": f"u-{token}",
            "correo": f"{token}@tukit.co",
            "nombre": token,
            "roles": [{"rol": r, "ambito": None} for r in self.roles_por_token[token]],
            "version_permisos": 1,
        }


@pytest.fixture()
async def cliente(motor):
    app.state.motor = motor
    app.state.comercio = ComercioFalso([])
    app.state.identidad = IdentidadFalsa(
        roles_por_token={
            "tok-operador": ["operador"],
            "tok-admin": ["admin"],
            "tok-acudiente": ["acudiente"],
        }
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    # `app.state` es del módulo y sobrevive entre pruebas: se limpia lo inyectado
    # para no contaminar a las demás suites que comparten esta app.
    for attr in ("identidad", "comercio"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


RUTA = f"/v1/metricas/colegios/{COLEGIO}/pedidos"


async def test_sin_token_es_401(cliente):
    respuesta = await cliente.get(RUTA)
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "sesion_invalida"


async def test_token_invalido_es_401(cliente):
    respuesta = await cliente.get(RUTA, headers={"Authorization": "Bearer no-existe"})
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "sesion_invalida"


async def test_rol_acudiente_es_403(cliente):
    respuesta = await cliente.get(RUTA, headers={"Authorization": "Bearer tok-acudiente"})
    assert respuesta.status_code == 403
    assert respuesta.json()["error"] == "acceso_denegado"


async def test_operador_pasa_y_ve_el_resumen(cliente):
    respuesta = await cliente.get(RUTA, headers={"Authorization": "Bearer tok-operador"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["colegio_id"] == COLEGIO
    assert set(cuerpo) >= {"total_padres", "total_ninos", "por_padre", "por_grado", "estados_trabajos"}


async def test_admin_tambien_pasa(cliente):
    respuesta = await cliente.get(RUTA, headers={"Authorization": "Bearer tok-admin"})
    assert respuesta.status_code == 200


async def test_identidad_caida_falla_cerrada_503(motor):
    # Con identidad caída no se puede validar: el endpoint NO abre el acceso, lo
    # cierra con 503 (ni 200 ni un 500 pelado).
    app.state.motor = motor
    app.state.comercio = ComercioFalso([])
    app.state.identidad = IdentidadFalsa(caida=True)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.get(RUTA, headers={"Authorization": "Bearer tok-operador"})
        assert respuesta.status_code == 503
        assert respuesta.json()["error"] == "identidad_no_disponible"
    finally:
        for attr in ("identidad", "comercio"):
            if hasattr(app.state, attr):
                delattr(app.state, attr)
