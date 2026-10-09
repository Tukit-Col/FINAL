"""Autenticacion y roles por el gateway, con los usuarios sembrados de cada rol.

La matriz ruta x rol de NFR-SEG-04: sin token 401, sin el rol 403 y nada de
objetos ajenos. Las rutas que hoy cumplen quedan como control; las que no, como
`xfail(strict=True)` contra el hallazgo que las explica (H-C-06 sobre todo), para
que avisen el dia que se corrijan. Las pruebas unitarias de la fase 2 ya lo
reproducen contra la app de cada servicio; aqui se ve desde la puerta, que es
lo que alcanza un cliente cualquiera.
"""

from __future__ import annotations

import httpx
import pytest
from stack_vivo import CLAVE_DEMO, GATEWAY, USUARIOS_DEMO, orden_pagada, portador

pytestmark = pytest.mark.integracion

# El colegio del `colegio_admin` sembrado (`sembrar_acceso`).
_COLEGIO_DEMO = "17127bcf-9134-58a4-aae4-6a2bc6f7bf32"


def _entrar(http: httpx.Client, rol: str) -> dict:
    respuesta = http.post("/v1/sesiones", json={"correo": USUARIOS_DEMO[rol], "clave": CLAVE_DEMO})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


# --------------------------------------------------------------- controles que hoy cumplen

_CON_SESION = ["/v1/cuenta", "/v1/sesiones/actual", "/v1/trabajos", "/v1/mis-solicitudes"]
_SOLO_STAFF = ["/v1/admin/acudientes", f"/v1/metricas/colegios/{_COLEGIO_DEMO}/pedidos"]


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.parametrize(
    "ruta", _CON_SESION + _SOLO_STAFF + ["/v1/usuarios/nombres?ids=00000000-0000-0000-0000-000000000000"]
)
def test_sin_token_la_ruta_protegida_responde_401(cliente: httpx.Client, ruta: str):
    assert cliente.get(ruta).status_code == 401


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.parametrize("ruta", _CON_SESION)
def test_con_sesion_de_acudiente_la_ruta_propia_responde(cliente: httpx.Client, sesiones: dict, ruta: str):
    assert cliente.get(ruta, headers=portador(sesiones, "acudiente")).status_code == 200


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.parametrize("rol", ["acudiente", "colegio_admin"])
@pytest.mark.parametrize("ruta", _SOLO_STAFF)
def test_sin_rol_de_staff_la_ruta_interna_responde_403(
    cliente: httpx.Client, sesiones: dict, rol: str, ruta: str
):
    respuesta = cliente.get(ruta, headers=portador(sesiones, rol))

    assert respuesta.status_code == 403
    assert respuesta.json()["error"] == "acceso_denegado"


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.parametrize("rol", ["operador", "admin"])
@pytest.mark.parametrize("ruta", _SOLO_STAFF)
def test_con_rol_de_staff_la_ruta_interna_responde(
    cliente: httpx.Client, sesiones: dict, rol: str, ruta: str
):
    assert cliente.get(ruta, headers=portador(sesiones, rol)).status_code == 200


@pytest.mark.nfr("NFR-SEG-04")
def test_una_clave_equivocada_no_abre_sesion(cliente: httpx.Client):
    respuesta = cliente.post(
        "/v1/sesiones", json={"correo": USUARIOS_DEMO["admin"], "clave": "no-es-la-clave"}
    )

    assert respuesta.status_code == 401
    assert "token" not in respuesta.json()


@pytest.mark.nfr("NFR-SEG-04")
def test_un_token_alterado_se_rechaza(cliente: httpx.Client, sesiones: dict):
    token = sesiones["acudiente"]["token"]
    alterado = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")

    assert cliente.get("/v1/cuenta", headers={"authorization": f"Bearer {alterado}"}).status_code == 401


# --------------------------------------------------------------- H-C-06: rutas sin autenticar

_ABIERTAS_SIN_TOKEN = [
    "/v1/admin/listas",
    "/v1/admin/sugerencias",
    "/v1/admin/cola",
    f"/v1/admin/colegios/{_COLEGIO_DEMO}/acudientes",
    f"/v1/metricas/colegios/{_COLEGIO_DEMO}",
    "/v1/admin/catalogo/propuestas",
    "/v1/comercio/pedidos",
    "/v1/operacion/casos",
    "/v1/operacion/metricas",
]


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(
    strict=True,
    reason="H-C-06: la ruta de staff atiende sin token (el gateway no valida y el servicio tampoco)",
)
@pytest.mark.parametrize("ruta", _ABIERTAS_SIN_TOKEN)
def test_sin_token_la_ruta_de_staff_responde_401(cliente: httpx.Client, ruta: str):
    respuesta = cliente.get(ruta)

    assert respuesta.status_code == 401, f"{ruta}: {respuesta.status_code}"


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(strict=True, reason="H-C-06: la ruta de staff atiende a un acudiente")
@pytest.mark.parametrize(
    "ruta", ["/v1/admin/cola", "/v1/admin/listas", "/v1/comercio/pedidos", "/v1/operacion/casos"]
)
def test_un_acudiente_no_entra_a_la_ruta_de_staff(cliente: httpx.Client, sesiones: dict, ruta: str):
    assert cliente.get(ruta, headers=portador(sesiones, "acudiente")).status_code == 403


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(
    strict=True, reason="H-C-06: el catalogo busca el producto antes de pedir sesion (404 en vez de 401)"
)
@pytest.mark.parametrize("metodo", ["PATCH", "DELETE"])
def test_sin_token_no_se_edita_el_catalogo(cliente: httpx.Client, metodo: str):
    respuesta = cliente.request(metodo, "/v1/catalogo/productos/QA-NO-EXISTE", json={"nombre": "x"})

    assert respuesta.status_code == 401, respuesta.text


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(
    strict=True, reason="H-C-06: /v1/contactos/{usuario_id} entrega el correo del acudiente sin token"
)
def test_sin_token_no_se_lee_el_contacto_de_un_acudiente(cliente: httpx.Client, sesiones: dict):
    respuesta = cliente.get(f"/v1/contactos/{sesiones['acudiente']['usuario_id']}")

    assert respuesta.status_code == 401, respuesta.text[:200]


# --------------------------------------------------------------- H-C-06: objetos ajenos (IDOR)


@pytest.fixture(scope="module")
def pedido_de_mama(stack, sesiones: dict, producto: dict) -> str:
    """Un pedido pagado de la acudiente 1, creado por la prueba."""
    with httpx.Client(base_url=GATEWAY, timeout=30) as http:
        return orden_pagada(http, sesiones["acudiente"]["usuario_id"], producto)


@pytest.mark.nfr("NFR-SEG-04")
def test_mis_pedidos_con_el_id_propio_trae_el_pedido(
    cliente: httpx.Client, sesiones: dict, pedido_de_mama: str
):
    respuesta = cliente.get(
        "/v1/comercio/mis-pedidos",
        params={"usuario_id": sesiones["acudiente"]["usuario_id"]},
        headers=portador(sesiones, "acudiente"),
    )

    assert respuesta.status_code == 200
    assert pedido_de_mama in {p["pedido_id"] for p in respuesta.json()["pedidos"]}


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(
    strict=True, reason="H-C-06: mis-pedidos filtra por el usuario_id del cliente, no por el portador"
)
@pytest.mark.parametrize("quien", ["otro_acudiente", "anonimo"])
def test_mis_pedidos_no_entrega_los_pedidos_de_otro(
    cliente: httpx.Client, sesiones: dict, pedido_de_mama: str, quien: str
):
    cabeceras = portador(sesiones, "acudiente_2") if quien == "otro_acudiente" else {}
    respuesta = cliente.get(
        "/v1/comercio/mis-pedidos",
        params={"usuario_id": sesiones["acudiente"]["usuario_id"]},
        headers=cabeceras,
    )

    ajenos = (
        {p["pedido_id"] for p in respuesta.json().get("pedidos", [])}
        if respuesta.status_code == 200
        else set()
    )
    assert pedido_de_mama not in ajenos


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(strict=True, reason="H-C-06: el detalle de un pedido se entrega sin token")
@pytest.mark.parametrize("plantilla", ["/v1/ordenes/{}", "/v1/comercio/pedidos/{}"])
def test_sin_token_no_se_lee_un_pedido(cliente: httpx.Client, pedido_de_mama: str, plantilla: str):
    respuesta = cliente.get(plantilla.format(pedido_de_mama))

    assert respuesta.status_code in (401, 404), respuesta.text[:200]


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(strict=True, reason="H-C-06: avanzar el estado de un pedido no pide sesion ni rol")
def test_otro_acudiente_no_avanza_un_pedido_ajeno(cliente: httpx.Client, sesiones: dict, producto: dict):
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    respuesta = cliente.post(
        f"/v1/ordenes/{pedido}/avanzar",
        json={"destino": "en_preparacion"},
        headers=portador(sesiones, "acudiente_2"),
    )

    assert respuesta.status_code in (401, 403), respuesta.text[:200]


# --------------------------------------------------------------- sesiones


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(
    strict=True, reason="H-A-32: cerrar la sesion no revoca el token; sigue abriendo /v1/cuenta"
)
def test_tras_cerrar_la_sesion_el_token_ya_no_sirve(cliente: httpx.Client):
    token = _entrar(cliente, "acudiente")["token"]
    cabeceras = {"authorization": f"Bearer {token}"}
    cierre = cliente.post("/v1/sesiones/cierre", headers=cabeceras)

    assert cierre.status_code in (200, 204)
    assert cliente.get("/v1/cuenta", headers=cabeceras).status_code == 401


@pytest.mark.nfr("NFR-SEG-04")
@pytest.mark.xfail(strict=True, reason="H-A-17: un token con caracteres no ASCII hace responder 500")
def test_un_token_no_ascii_se_rechaza_con_401(cliente: httpx.Client):
    respuesta = cliente.get("/v1/cuenta", headers={"authorization": "Bearer ñandú".encode()})

    assert respuesta.status_code == 401


@pytest.mark.nfr("NFR-SEG-02")
def test_la_sesion_del_administrador_trae_el_rol_global(cliente: httpx.Client):
    """Control: el admin sembrado entra con su clave y su sesion dice `admin` global."""
    roles = _entrar(cliente, "admin")["sesion"]["roles"]

    assert {"rol": "admin", "ambito": {"tipo": "global", "id": None}} in roles


@pytest.mark.nfr("NFR-SEG-02")
@pytest.mark.xfail(
    strict=True, reason="H-C-08: sin segundo factor, la clave sola da una sesion de administrador completa"
)
def test_la_clave_sola_no_abre_las_rutas_del_administrador(cliente: httpx.Client):
    entrada = _entrar(cliente, "admin")
    respuesta = cliente.get("/v1/admin/acudientes", headers={"authorization": f"Bearer {entrada['token']}"})

    assert respuesta.status_code in (401, 403), "la clave sola ya abre /v1/admin/acudientes"
