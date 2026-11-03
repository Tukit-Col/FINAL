"""Los pasos que comparten los E2E de la fase 4: subir, revisar, aprobar, esperar el kit.

Va aparte del `conftest.py` para poder importarlo desde las pruebas
(`from e2e_flujo import ...`). Cada paso es una llamada HTTP a la puerta de los
E2E, la misma que usaria el navegador o la consola de administracion.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from stack_vivo import RAIZ, cabecera_de_familia, conexion_a

GOLDEN = RAIZ / "datos" / "golden"
ESPERADOS: dict[str, dict[str, Any]] = {
    ruta.stem: json.loads(ruta.read_text()) for ruta in sorted((GOLDEN / "esperado").glob("G*.json"))
}
ACEPTADAS = sorted(v for v, e in ESPERADOS.items() if e["aceptada"])
# `esperado/Gnn.json` es la respuesta grabada del modelo y no cambia. Lo que un humano
# espera de cada renglon sale de `oracle.json`, que se recalibra contra el catalogo de hoy
# (`construir.RECALIBRADO_CATALOGO`: desde 44309fa el compas de precision se surte, y la
# plataforma y el uniforme tienen concepto propio).
_ORO = {
    fuente: {clave: par[clave] for clave in ("estado", "concepto", "nivel")}
    for par in json.loads((GOLDEN / "esperado" / "oracle.json").read_text())["pares"]
    for fuente in par["fuentes"]
}
ANIO_LECTIVO = 2026
# ADR 0030 (efb0827): siempre Ahorrador y Premium; el Fan solo si el acudiente pide un personaje.
PERFILES = ("Ahorrador", "Premium")
PERFILES_CON_PERSONAJE = ("Ahorrador", "Fan", "Premium")
ETAPAS = ("percepcion", "normalizacion", "resolucion", "optimizacion")
TERMINALES = ("publicado", "espera_revision", "fallido")
_TIPOS_DE_ARCHIVO = {".png": "image/png", ".jpg": "image/jpeg", ".pdf": "application/pdf"}


def colegio_ficticio(variante: str) -> str:
    """Un colegio escrito a mano y unico por corrida: cada lista es la primera de su grado."""
    return f"Colegio Ficticio QA {variante} {uuid.uuid4().hex[:8]}"


def registrar_acudiente(http: httpx.Client, colegio_id: str, grado: str = "Tercero") -> dict[str, Any]:
    """Registra un acudiente ficticio con un hijo y abre su sesion.

    Cada acudiente es una familia con su IP (N-120): el registro, la sesion y todo lo que vaya con
    su `cabecera` llegan a la puerta desde esa IP, y el limite (ADR 0047) le cuenta su cupo aparte."""
    correo = f"qa-e2e-{uuid.uuid4().hex[:10]}@example.test"
    clave = "clave-ficticia-qa"
    ip = cabecera_de_familia()
    registro = http.post(
        "/v1/registro",
        headers=ip,
        json={
            "correo": correo,
            "clave": clave,
            "acepta_terminos": True,
            "hijos": [{"colegio_id": colegio_id, "grado": grado, "apodo": f"QA-{uuid.uuid4().hex[:6]}"}],
        },
    )
    assert registro.status_code == 201, registro.text
    sesion = http.post("/v1/sesiones", headers=ip, json={"correo": correo, "clave": clave})
    assert sesion.status_code == 200, sesion.text
    cuerpo = sesion.json()
    return {
        "correo": correo,
        "usuario_id": cuerpo["sesion"]["usuario_id"],
        "cabecera": {"authorization": f"Bearer {cuerpo['token']}", **ip},
        "registro": registro.json(),
    }


def archivo(variante: str) -> tuple[str, bytes, str]:
    ruta = GOLDEN / ESPERADOS[variante]["archivo"]
    tipo = _TIPOS_DE_ARCHIVO.get(ruta.suffix, "application/octet-stream")
    return ruta.name, ruta.read_bytes(), tipo


def subir(http: httpx.Client, cabecera: dict[str, str], variante: str, colegio_nombre: str) -> httpx.Response:
    """La subida del acudiente (`/subir`, paso 2): un hijo, su colegio escrito a mano y su archivo."""
    hijos = [{"referencia": "hijo-1", "colegio_nombre": colegio_nombre, "grado": "Tercero"}]
    return http.post(
        "/v1/listas/subir",
        headers=cabecera,
        data={"hijos": json.dumps(hijos), "referencia": "hijo-1"},
        files={"archivo": archivo(variante)},
    )


def revision(http: httpx.Client, admin: dict[str, str], version_id: str) -> dict[str, Any]:
    respuesta = http.get(f"/v1/admin/listas/{version_id}/revision", headers=admin)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def quitar_concepto_sin_producto(
    http: httpx.Client, admin: dict[str, str], version_id: str, sin_producto: set[str]
) -> list[int]:
    """La correccion minima del revisor: el renglon cuyo concepto no tiene producto queda sin concepto.

    Es lo que la pantalla de revision permite (`PATCH` del renglon). Hasta b97ce00
    hacia falta para que la aprobacion no dejara al acudiente sin kit (H-A-41).
    Devuelve el `orden` de los renglones corregidos.
    """
    corregidos = []
    for item in revision(http, admin, version_id)["items"]:
        if (item["concepto"] or {}).get("codigo") in sin_producto:
            respuesta = http.patch(
                f"/v1/admin/listas/{version_id}/items/{item['item_id']}",
                headers=admin,
                json={"concepto_codigo": None, "requiere_revision": True},
            )
            assert respuesta.status_code == 200, respuesta.text
            corregidos.append(item["orden"])
    return corregidos


def cerrar(http: httpx.Client, admin: dict[str, str], version_id: str) -> None:
    respuesta = http.post(f"/v1/admin/listas/{version_id}/cerrar", headers=admin)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["revisada"] is True


def esperar_trabajo_del_acudiente(
    http: httpx.Client, cabecera: dict[str, str], version_id: str, plazo: float = 90.0
) -> dict[str, Any]:
    """Espera a que el poller arme el trabajo de esa lista y lo deje en un estado terminal."""
    limite = time.monotonic() + plazo
    while time.monotonic() < limite:
        mios = http.get("/v1/trabajos", headers=cabecera)
        assert mios.status_code == 200, mios.text
        for trabajo in mios.json()["trabajos"]:
            es_suyo = any(h.get("version_id") == version_id for h in trabajo["hijos"])
            if es_suyo and trabajo["estado"] in TERMINALES:
                vista = http.get(f"/v1/trabajos/{trabajo['trabajo_id']}", headers=cabecera)
                assert vista.status_code == 200, vista.text
                return vista.json()
        time.sleep(0.5)
    pytest.fail(f"el poller no armo el trabajo de la version {version_id} en {plazo} s")


def sondear(http: httpx.Client, trabajo_id: str, plazo: float = 120.0) -> list[dict[str, Any]]:
    """Sondea `GET /v1/trabajos/{id}` como lo hace la web, hasta un estado terminal."""
    sondeos = []
    limite = time.monotonic() + plazo
    while time.monotonic() < limite:
        respuesta = http.get(f"/v1/trabajos/{trabajo_id}")
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        sondeos.append({"t": time.monotonic(), "codigo": respuesta.status_code, **cuerpo})
        if cuerpo["estado"] in TERMINALES:
            return sondeos
        time.sleep(0.1)
    pytest.fail(f"el trabajo {trabajo_id} no termino en {plazo} s")


def lineas(vista: dict[str, Any]):
    for kit in vista["kits"]:
        for linea in kit["lineas"]:
            yield kit, linea


def por_orden(variante: str) -> dict[int, dict[str, Any]]:
    return {
        fila["orden"]: {
            **fila,
            "emparejamiento": {**fila["emparejamiento"], **_ORO.get(f"{variante}#{fila['orden']}", {})},
        }
        for fila in ESPERADOS[variante]["renglones"]
    }


def ordenes(variante: str, nivel: str) -> set[int]:
    return {o for o, f in por_orden(variante).items() if f["emparejamiento"]["nivel"] == nivel}


async def catalogo_vivo() -> dict[str, Any]:
    """Lo que hay en el catalogo del stack: SKU e id de cada producto y los conceptos sin producto.

    Solo cuentan los conceptos que se buscan en el catalogo (`parseo.BUSCA_EN_CATALOGO`): desde
    44309fa hay conceptos informativos (uniforme, licencia digital) que no tienen producto a
    proposito, y quitarles el concepto ya no es la revision minima.
    """
    async with conexion_a("catalogo") as conexion:
        productos = (
            await conexion.execute(text("select id::text, sku_interno from producto_canonico"))
        ).all()
        sin_producto = (
            await conexion.execute(
                text(
                    "select c.codigo from concepto c where c.activo "
                    "and c.tipo_item in ('util', 'libro_libre') and not exists "
                    "(select 1 from producto_canonico p where p.concepto_id = c.id and p.activo)"
                )
            )
        ).all()
    return {
        "skus": {sku for _, sku in productos if sku},
        "ids": {id_ for id_, _ in productos},
        "sin_producto": {codigo for (codigo,) in sin_producto},
    }


async def productos_de_los_kits(trabajo_id: str) -> list[tuple[str, str | None, str | None]]:
    """`(perfil, producto_canonico_id, sku)` de cada linea de los kits del trabajo, leidos de la base."""
    async with conexion_a("inteligencia") as conexion:
        filas = await conexion.execute(
            text(
                "select k.perfil, l.producto_canonico_id::text, l.sku from linea_kit l "
                "join kit k on k.id = l.kit_id where k.trabajo_id = cast(:t as uuid)"
            ),
            {"t": trabajo_id},
        )
        return [tuple(f) for f in filas]
