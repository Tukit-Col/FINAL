"""La lectura guardada con la app de inteligencia y un Redis de verdad (ADR 0047).

Es la prueba de punta a punta de la cache de lecturas: la API que arranca
`make arriba` no deja cambiar el lector por el doble sin tocar codigo de
produccion, asi que se corre la app aqui, en el proceso de la prueba, contra el
Redis de `TUKIT_PRUEBAS_REDIS_URL`. Dos subidas del mismo PDF leen una vez, y lo
que queda en Redis es la lectura, con su vencimiento, y nada mas.
"""

from __future__ import annotations

import json

import httpx
import pytest
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import clientes_de_prueba, lo_guardado
from tukit_inteligencia import cache_lecturas
from tukit_inteligencia.api import app
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida

pytestmark = pytest.mark.redis

COLEGIO = "11111111-1111-5111-8111-111111111111"
CORREO = "papa.prueba@ejemplo.com"


class Catalogo:
    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    async def importar_lista(self, **campos) -> dict:
        self.llamadas.append(campos)
        n = len(self.llamadas)
        return {"version_id": f"ver-{n}", "tarea_id": f"tar-{n}", "items": len(campos["items"])}


class Identidad:
    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        return "usr-1"

    async def usuario_del_token(self, token: str) -> str | None:
        return None

    async def datos_directorio(self, dane: str) -> dict | None:
        return None


def _subida(pdf: bytes, referencia: str) -> dict:
    hijos = [{"referencia": referencia, "colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}]
    return {
        "data": {"hijos": json.dumps(hijos), "contacto": json.dumps({"correo": CORREO})},
        "files": [("archivo", ("lista.pdf", pdf, "application/pdf")), ("referencia", (None, referencia))],
    }


async def test_dos_subidas_del_mismo_pdf_leen_una_vez_contra_redis(motor):
    lecturas: list[int] = []

    def _leer(_png: bytes, numero: int) -> PaginaLeida:
        lecturas.append(numero)
        return PaginaLeida(
            grados=["Cuarto"],
            items=[ItemExtraido(descripcion="2 cuadernos cuadriculados", cantidad=2, confianza=0.9)],
        )

    app.state.renderizar = lambda _contenido: [b"p1", b"p2"]
    app.state.leer = _leer
    app.state.motor = motor
    app.state.catalogo = Catalogo()
    app.state.identidad = Identidad()
    pdf = b"%PDF-lista-de-cuarto-de-prueba"

    async with clientes_de_prueba() as (cliente,):
        usar_cliente(cliente)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            primera = await http.post("/v1/listas/subir", **_subida(pdf, "hijo-1"))
            segunda = await http.post("/v1/listas/subir", **_subida(pdf, "hijo-2"))

        assert primera.status_code == segunda.status_code == 202
        assert lecturas == [1, 2]
        assert not cliente.degradado

        guardado = await lo_guardado(cliente.prefijo)

    assert list(guardado) == [cliente.prefijo + cache_lecturas.clave(pdf)]
    (lectura,) = guardado.values()
    assert set(json.loads(lectura.valor)) == {"grados", "paginas", "items"}
    assert CORREO.encode() not in lectura.valor
    ttl_ms = 30 * 24 * 3600 * 1000  # el contrato de la ADR 0047
    assert ttl_ms - 60_000 < lectura.vence_en_ms <= ttl_ms
