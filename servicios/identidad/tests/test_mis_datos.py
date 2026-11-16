"""El panel de privacidad del titular: consulta, exportacion y supresion (Ley 1581).

Contra la app real sobre SQLite en memoria. Los otros servicios se sustituyen
por un doble en `app.state.inventario` que guarda con que token se le pregunto:
asi se prueba que Identidad pregunta por EL titular del token y por nadie mas.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from sqlalchemy import select
from tukit_comun.identificadores import derivar
from tukit_identidad.api import app
from tukit_identidad.dominio.privacidad import (
    FRASE_CONFIRMACION,
    confirmacion_valida,
    enmascarar_correo,
    enmascarar_telefono,
)
from tukit_identidad.dominio.sesiones import leer_token
from tukit_identidad.modelos import Base

from tests._ayudas_identidad import cliente_api, sembrar_rol_acudiente_y_colegio

CLAVE = "clave1234"
CONFIRMACION = {"confirmacion": FRASE_CONFIRMACION}


class InventarioDoble:
    """Hace de Comercio, Operacion e Inteligencia. Responde por titular."""

    def __init__(self) -> None:
        self.pedidos: dict[str, list[dict]] = {}
        self.preguntas: list[str] = []

    async def resumen(self, token: str) -> dict:
        self.preguntas.append(token)
        uid = leer_token(token)["sub"]
        pedidos = self.pedidos.get(uid, [])
        return {
            "pedidos": {"disponible": True, "total": len(pedidos), "elementos": pedidos},
            "casos": {"disponible": True, "total": 0, "elementos": []},
            "trabajos_kit": {"disponible": False},
        }


@pytest.fixture()
async def entorno():
    doble = InventarioDoble()
    async with cliente_api(sembrar_rol_acudiente_y_colegio) as http:
        app.state.inventario = doble
        try:
            yield http, doble, app.state.motor.engine
        finally:
            del app.state.inventario


async def _cuenta(http, correo: str, nombre: str = "Ana Ruiz", celular: str | None = "+57 300 555 4567"):
    r = await http.post(
        "/v1/cuenta",
        json={
            "correo": correo,
            "clave": CLAVE,
            "nombre": nombre,
            "celular": celular,
            "acepta_terminos": True,
        },
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    return cuerpo["sesion"]["usuario_id"], {"Authorization": f"Bearer {cuerpo['token']}"}


async def _con_hijo_y_direccion(http, tok) -> None:
    r = await http.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={
            "apodo": "Pepito",
            "colegio_id": str(derivar("colegio", "2.4")),
            "sede_id": str(derivar("sede", "2.4", "u")),
            "grado": "Tercero",
            "anio_lectivo": 2026,
            "consentimiento": True,
        },
    )
    assert r.status_code == 201, r.text
    r = await http.post(
        "/v1/cuenta/direcciones",
        headers=tok,
        json={"ciudad": "Bogota", "linea": "Calle 1 # 2-3", "contacto": "3001112233"},
    )
    assert r.status_code == 201, r.text


# ----------------------------------------------------------------- puras


def test_la_confirmacion_ignora_mayusculas_tildes_y_espacios():
    assert confirmacion_valida("eliminar  mis datos ")
    assert confirmacion_valida("Eliminar mis datos")
    assert not confirmacion_valida("eliminar")
    assert not confirmacion_valida(None)


def test_el_contacto_sale_enmascarado():
    assert enmascarar_correo("ana.maria@ejemplo.com") == "a***@ejemplo.com"
    assert enmascarar_telefono("+57 300 555 4567") == "*** *** 4567"
    assert enmascarar_telefono(None) is None


# ----------------------------------------------------------------- inventario


async def test_el_inventario_lista_cuenta_hijos_matriculas_y_consentimientos(entorno):
    http, doble, _ = entorno
    uid, tok = await _cuenta(http, "ana@ejemplo.com")
    await _con_hijo_y_direccion(http, tok)
    doble.pedidos[uid] = [{"pedido_id": "p1", "estado": "pagado"}]

    r = await http.get("/v1/cuenta/mis-datos", headers=tok)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["cuenta"]["correo"] == "a***@ejemplo.com"
    assert datos["cuenta"]["celular"] == "*** *** 4567"
    assert datos["cuenta"]["nombre"] == "Ana Ruiz"
    assert [h["apodo"] for h in datos["hijos"]] == ["Pepito"]
    assert datos["matriculas"][0]["grado"] == "Tercero"
    assert len(datos["direcciones"]) == 1
    assert "Calle" not in json.dumps(datos["direcciones"])  # la linea no sale en la vista
    assert datos["consentimientos"][0]["version"]
    assert datos["consentimientos"][0]["aceptado_en"]
    assert datos["pedidos"]["total"] == 1
    assert datos["trabajos_kit"] == {"disponible": False}
    assert datos["supresion"]["conservado"][0]["fundamento"]


async def test_el_inventario_de_otro_titular_no_trae_lo_mio(entorno):
    http, doble, _ = entorno
    uid_a, tok_a = await _cuenta(http, "ana@ejemplo.com")
    await _con_hijo_y_direccion(http, tok_a)
    doble.pedidos[uid_a] = [{"pedido_id": "p1", "estado": "pagado"}]
    _, tok_b = await _cuenta(http, "beto@ejemplo.com", nombre="Beto")

    r = await http.get("/v1/cuenta/mis-datos", headers=tok_b)
    assert r.status_code == 200
    datos = r.json()
    assert datos["cuenta"]["usuario_id"] != uid_a
    assert datos["hijos"] == [] and datos["direcciones"] == []
    assert datos["pedidos"]["total"] == 0
    assert "Pepito" not in r.text and "ana@" not in r.text
    # Identidad le pregunta a los otros servicios con el token del portador.
    assert doble.preguntas[-1] == tok_b["Authorization"].removeprefix("Bearer ")


async def test_la_exportacion_es_un_adjunto_json_completo(entorno):
    http, _, _ = entorno
    _, tok = await _cuenta(http, "ana@ejemplo.com")
    await _con_hijo_y_direccion(http, tok)

    r = await http.get("/v1/cuenta/mis-datos/exportar", headers=tok)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    disposicion = r.headers["content-disposition"]
    assert disposicion.startswith("attachment;") and "tukit-mis-datos-" in disposicion
    datos = r.json()
    # Es la copia del titular: el contacto va completo.
    assert datos["cuenta"]["correo"] == "ana@ejemplo.com"
    assert datos["direcciones"][0]["linea"] == "Calle 1 # 2-3"
    assert datos["exportado_en"]


# ----------------------------------------------------------------- supresion


async def test_suprimir_sin_la_frase_es_422_y_no_toca_nada(entorno):
    http, _, _ = entorno
    _, tok = await _cuenta(http, "ana@ejemplo.com")
    r = await http.post("/v1/cuenta/supresion", headers=tok, json={"confirmacion": "si"})
    assert r.status_code == 422
    assert r.json()["error"] == "confirmacion_requerida"
    cuenta = await http.get("/v1/cuenta", headers=tok)
    assert cuenta.status_code == 200
    assert cuenta.json()["correo"] == "ana@ejemplo.com"


async def test_suprimir_borra_lo_personal_conserva_pedidos_y_cierra_la_cuenta(entorno):
    http, doble, engine = entorno
    uid, tok = await _cuenta(http, "ana@ejemplo.com")
    await _con_hijo_y_direccion(http, tok)
    doble.pedidos[uid] = [{"pedido_id": "p1", "estado": "pagado"}]

    r = await http.post("/v1/cuenta/supresion", headers=tok, json=CONFIRMACION)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "propagando"
    assert {s["dato"] for s in cuerpo["suprimido"]} >= {"nombre", "correo", "direcciones", "hijos"}
    conservado = {c["dato"]: c for c in cuerpo["conservado"]}
    assert "Estatuto Tributario" in conservado["pedidos_y_facturas"]["fundamento"]
    assert "1480" in conservado["garantia"]["fundamento"]
    assert cuerpo["pedidos_conservados"] == 1

    # La sesion quedo revocada y ya no se puede volver a entrar.
    assert (await http.get("/v1/cuenta", headers=tok)).status_code == 401
    login = await http.post("/v1/sesiones", json={"correo": "ana@ejemplo.com", "clave": CLAVE})
    assert login.status_code == 401

    t = Base.metadata.tables
    async with engine.connect() as c:
        usuario = (await c.execute(select(t["usuario"]).where(t["usuario"].c.id == uuid.UUID(uid)))).one()
        assert usuario.correo != "ana@ejemplo.com" and usuario.correo.endswith(".invalid")
        assert usuario.nombre_cifrado is None and usuario.celular is None
        assert usuario.activo is False and usuario.anonimizado_en is not None
        assert (
            await c.execute(select(t["direccion"]).where(t["direccion"].c.usuario_id == uuid.UUID(uid)))
        ).all() == []
        nombres = [f.nombre_cifrado for f in (await c.execute(select(t["estudiante"]))).all()]
        assert all(b"Pepito" not in n for n in nombres)
        vinculos = (await c.execute(select(t["acudiente_matricula"]))).all()
        assert all(v.vigente_hasta is not None and v.apodo_cifrado is None for v in vinculos)
        consentimientos = (await c.execute(select(t["consentimiento"]))).all()
        assert consentimientos and all(x.revocado_en is not None for x in consentimientos)
        solicitud = (await c.execute(select(t["solicitud_supresion"]))).one()
        assert solicitud.estado == "propagando"
        evento = (await c.execute(select(t["bandeja_salida"]))).one()
        assert evento.tipo == "titular_suprimido"
        # El evento auditable no lleva datos personales.
        assert "ana@" not in json.dumps(evento.carga) and "Ana" not in json.dumps(evento.carga)
        assert evento.carga["usuario_id"] == uid

    # El correo queda libre: quien lo use despues abre una cuenta nueva y vacia.
    nuevo_uid, _ = await _cuenta(http, "ana@ejemplo.com")
    assert nuevo_uid != uid


async def test_suprimir_con_el_token_de_otro_no_toca_mi_cuenta(entorno):
    http, _, _ = entorno
    uid_a, tok_a = await _cuenta(http, "ana@ejemplo.com")
    _, tok_b = await _cuenta(http, "beto@ejemplo.com", nombre="Beto")
    r = await http.post("/v1/cuenta/supresion", headers=tok_b, json=CONFIRMACION)
    assert r.status_code == 200
    assert r.json()["estado"] == "propagando"
    # Se suprimio el portador del token (Beto) y Ana sigue intacta.
    assert (await http.get("/v1/cuenta", headers=tok_b)).status_code == 401
    cuenta_a = await http.get("/v1/cuenta", headers=tok_a)
    assert cuenta_a.status_code == 200
    assert cuenta_a.json() == {"usuario_id": uid_a, "correo": "ana@ejemplo.com", "nombre": "Ana Ruiz"}
    login = await http.post("/v1/sesiones", json={"correo": "ana@ejemplo.com", "clave": CLAVE})
    assert login.status_code == 200
    assert login.json()["sesion"]["usuario_id"] == uid_a


async def test_revocar_consentimiento_sin_suprimir(entorno):
    http, _, _ = entorno
    _, tok = await _cuenta(http, "ana@ejemplo.com")
    await _con_hijo_y_direccion(http, tok)
    r = await http.post("/v1/cuenta/consentimientos/revocar", headers=tok)
    assert r.status_code == 200
    assert r.json()["revocados"] >= 1
    datos = (await http.get("/v1/cuenta/mis-datos", headers=tok)).json()
    assert all(c["revocado_en"] for c in datos["consentimientos"])


# ----------------------------------------------------------------- remoto


async def test_el_inventario_remoto_reenvia_el_bearer_y_degrada_por_seccion():
    from tukit_identidad.remoto import InventarioRemoto

    vistos: list[tuple[str, str | None]] = []

    def responder(peticion: httpx.Request) -> httpx.Response:
        vistos.append((peticion.url.path, peticion.headers.get("authorization")))
        if peticion.url.path == "/v1/operacion/mis-casos":
            return httpx.Response(503)
        if peticion.url.path == "/v1/trabajos":
            raise httpx.ConnectError("caido")
        return httpx.Response(
            200, json={"total": 1, "pedidos": [{"pedido_id": "p1", "estado": "pagado", "envio": {"x": 1}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cliente:
        r = await InventarioRemoto(cliente=cliente).resumen("tok-ana")
    assert r["pedidos"] == {
        "disponible": True,
        "total": 1,
        "elementos": [{"pedido_id": "p1", "estado": "pagado"}],
    }
    assert r["casos"] == {"disponible": False}
    assert r["trabajos_kit"] == {"disponible": False}
    assert all(auth == "Bearer tok-ana" for _, auth in vistos)
