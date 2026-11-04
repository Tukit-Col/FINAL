"""El dueno del kit, contra el stack vivo (oe5, `0c9d1e1`).

Un trabajo cuyo dueno tiene clave solo lo lee la sesion de ese dueno o la del equipo
interno (`_exigir_dueno_del_trabajo`, `routers/inteligencia.py:94-139`): con otra
cuenta es 404, para no confirmar que el id existe, y sin sesion es 401. Y solo su
dueno lo paga (`trabajos.ordenar`: `solicitud_ajena`, 403). Si el dueno es un contacto
sin clave (la ruta rapida con correo) o no hay dueno, el enlace es el unico acceso y
el kit se lee por id.

oe5 ya prueba la puerta con dobles (`servicios/inteligencia/tests/test_api_inteligencia.py`
y `test_trabajos.py`). Aqui va lo que solo se ve con los procesos de verdad: la sesion
cruza la puerta, Inteligencia le pregunta a Identidad si el dueno tiene clave, y el
trabajo nace por la ruta rapida (`aplicar-canonico`), sin cola ni modelo.

Cada prueba registra su acudiente, con su propia IP (N-120). Decision N-163.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from stack_vivo import ENTREGA_FICTICIA, GATEWAY, cabecera_de_familia, portador

pytestmark = [pytest.mark.integracion, pytest.mark.nfr("NFR-SEG-04")]

# El perfil que se aplica sobre el kit canonico. `Ahorrador` es el que todo canonico trae
# (`test_e2e_ruta_rapida.py` lo exige) y no pide personaje.
PERFIL = "Ahorrador"


# --------------------------------------------------------------- ayudantes


def _codigo(respuesta: httpx.Response) -> str | None:
    try:
        return respuesta.json().get("error")
    except ValueError:
        return None


def _registrar(http: httpx.Client) -> dict[str, Any]:
    """Un acudiente ficticio con clave y su sesion, con su IP."""
    correo = f"qa-dueno-{uuid.uuid4().hex[:10]}@example.test"
    clave = "clave-ficticia-qa"
    ip = cabecera_de_familia()
    registro = http.post(
        "/v1/registro", headers=ip, json={"correo": correo, "clave": clave, "acepta_terminos": True}
    )
    assert registro.status_code == 201, registro.text
    sesion = http.post("/v1/sesiones", headers=ip, json={"correo": correo, "clave": clave})
    assert sesion.status_code == 200, sesion.text
    cuerpo = sesion.json()
    return {
        "correo": correo,
        "usuario_id": cuerpo["sesion"]["usuario_id"],
        "cabecera": {"authorization": f"Bearer {cuerpo['token']}", **ip},
    }


def _aplicar(
    http: httpx.Client,
    canonico: dict[str, Any],
    *,
    cabecera: dict[str, str] | None = None,
    usuario_id: str | None = None,
) -> str:
    """Crea un trabajo por la ruta rapida y devuelve su id.

    Con sesion, el dueno sale del token. Sin sesion, del `usuario_id` del cuerpo (el
    respaldo server-to-server) o de nadie."""
    cuerpo = {
        "colegio_id": canonico["colegio_id"],
        "grado": canonico["grado"],
        "anio_lectivo": canonico["anio_lectivo"],
        "perfil": PERFIL,
    }
    if usuario_id is not None:
        cuerpo["usuario_id"] = usuario_id
    respuesta = http.post("/v1/trabajos/aplicar-canonico", headers=cabecera or {}, json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["trabajo_id"]


def _ordenar(http: httpx.Client, trabajo_id: str, correo: str, cabecera: dict[str, str]) -> httpx.Response:
    return http.post(
        f"/v1/trabajos/{trabajo_id}/ordenar",
        headers=cabecera,
        json={"perfil": PERFIL, "correo": correo, "entrega": ENTREGA_FICTICIA, "metodo": "pse"},
    )


# --------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def canonico() -> dict[str, Any]:
    """Un (colegio, grado, anio) con kit canonico, sobre el que la ruta rapida aplica."""
    grados = httpx.get(f"{GATEWAY}/v1/grados-canonicos", timeout=30).json()["grados"]
    if not grados:
        pytest.fail(
            "no hay ningun kit canonico: falta `make curaduria-importar` o que el poller y el "
            "trabajador armen sus kits"
        )
    return sorted(grados, key=lambda g: (g["colegio_id"], g["grado"]))[0]


@pytest.fixture
def dueno(cliente: httpx.Client) -> dict[str, Any]:
    return _registrar(cliente)


@pytest.fixture
def otro(cliente: httpx.Client) -> dict[str, Any]:
    return _registrar(cliente)


@pytest.fixture
def kit_con_dueno(cliente: httpx.Client, canonico: dict[str, Any], dueno: dict[str, Any]) -> str:
    return _aplicar(cliente, canonico, cabecera=dueno["cabecera"])


# --------------------------------------------------------------- las pruebas


def test_sin_sesion_el_kit_de_un_dueno_con_clave_pide_iniciar_sesion(
    cliente: httpx.Client, kit_con_dueno: str, record_property
):
    """Sin sesion es 401 `sesion_requerida`: la web lo usa para mandar a /ingresar."""
    vista = cliente.get(f"/v1/trabajos/{kit_con_dueno}")
    record_property("estado_sin_sesion", vista.status_code)

    assert (vista.status_code, _codigo(vista)) == (401, "sesion_requerida")


def test_otra_cuenta_no_lee_el_kit_y_no_sabe_que_existe(
    cliente: httpx.Client, kit_con_dueno: str, otro: dict[str, Any], record_property
):
    """Con otra cuenta, la vista y las opciones de un renglon dan el mismo 404 que un id
    que no existe: la puerta no confirma que el trabajo es de alguien."""
    ajena = cliente.get(f"/v1/trabajos/{kit_con_dueno}", headers=otro["cabecera"])
    inexistente = cliente.get(f"/v1/trabajos/{uuid.uuid4()}", headers=otro["cabecera"])
    opciones = cliente.get(
        f"/v1/trabajos/{kit_con_dueno}/kits/{PERFIL}/lineas/{uuid.uuid4()}/opciones",
        headers=otro["cabecera"],
    )
    record_property("estados", f"{ajena.status_code},{inexistente.status_code},{opciones.status_code}")

    assert (ajena.status_code, _codigo(ajena)) == (404, "trabajo_no_existe")
    assert (inexistente.status_code, _codigo(inexistente)) == (404, "trabajo_no_existe")
    assert ajena.json() == inexistente.json()
    # La puerta va antes que la busqueda del renglon: el 404 es del trabajo, no de la linea.
    assert (opciones.status_code, _codigo(opciones)) == (404, "trabajo_no_existe")


def test_el_dueno_y_el_equipo_interno_si_leen_el_kit(
    cliente: httpx.Client,
    kit_con_dueno: str,
    dueno: dict[str, Any],
    sesiones: dict[str, dict[str, str]],
):
    propia = cliente.get(f"/v1/trabajos/{kit_con_dueno}", headers=dueno["cabecera"])
    operador = cliente.get(f"/v1/trabajos/{kit_con_dueno}", headers=portador(sesiones, "operador"))

    assert propia.status_code == 200, propia.text
    assert operador.status_code == 200, operador.text
    assert propia.json()["kits"], "el kit de la ruta rapida llega sin kits"


def test_solo_el_dueno_paga_su_kit(
    cliente: httpx.Client, kit_con_dueno: str, dueno: dict[str, Any], otro: dict[str, Any], record_property
):
    """Otra sesion, o ninguna, recibe 403 `solicitud_ajena` y no se cobra nada; el dueno
    si arranca el pago. El correo del cuerpo no cambia quien paga."""
    ajena = _ordenar(cliente, kit_con_dueno, otro["correo"], otro["cabecera"])
    sin_sesion = _ordenar(cliente, kit_con_dueno, dueno["correo"], {})
    propia = _ordenar(cliente, kit_con_dueno, dueno["correo"], dueno["cabecera"])
    record_property("estados", f"{ajena.status_code},{sin_sesion.status_code},{propia.status_code}")

    assert (ajena.status_code, _codigo(ajena)) == (403, "solicitud_ajena")
    assert (sin_sesion.status_code, _codigo(sin_sesion)) == (403, "solicitud_ajena")
    assert propia.status_code == 201, propia.text
    assert propia.json().get("url_redireccion")


def test_el_enlace_de_la_ruta_rapida_sigue_sirviendo(
    cliente: httpx.Client, canonico: dict[str, Any], otro: dict[str, Any], record_property
):
    """Sin dueno, el kit de la ruta rapida se lee por su enlace, con o sin sesion, y se
    paga sin sesion: Inteligencia registra el contacto con el correo del pago."""
    trabajo_id = _aplicar(cliente, canonico)
    sin_sesion = cliente.get(f"/v1/trabajos/{trabajo_id}")
    con_otra = cliente.get(f"/v1/trabajos/{trabajo_id}", headers=otro["cabecera"])
    pago = _ordenar(cliente, trabajo_id, f"qa-enlace-{uuid.uuid4().hex[:10]}@example.test", {})
    record_property("estados", f"{sin_sesion.status_code},{con_otra.status_code},{pago.status_code}")

    assert sin_sesion.status_code == 200, sin_sesion.text
    assert con_otra.status_code == 200, con_otra.text
    assert pago.status_code == 201, pago.text


def test_el_kit_de_un_contacto_sin_clave_se_lee_por_su_enlace(
    cliente: httpx.Client, canonico: dict[str, Any], otro: dict[str, Any]
):
    """El dueno es un contacto sin clave (`POST /v1/contactos`): no puede iniciar sesion,
    asi que el enlace del correo es su unico acceso y el kit se lee por id."""
    contacto = cliente.post(
        "/v1/contactos", json={"correo": f"qa-contacto-{uuid.uuid4().hex[:10]}@example.test"}
    )
    assert contacto.status_code == 201, contacto.text
    trabajo_id = _aplicar(cliente, canonico, usuario_id=contacto.json()["usuario_id"])

    sin_sesion = cliente.get(f"/v1/trabajos/{trabajo_id}")
    con_otra = cliente.get(f"/v1/trabajos/{trabajo_id}", headers=otro["cabecera"])

    assert sin_sesion.status_code == 200, sin_sesion.text
    assert con_otra.status_code == 200, con_otra.text
