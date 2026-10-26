"""La puerta reusa UN cliente httpx para todo el proceso.

El defecto que esto fija: `reenviar` y `/v1/servicios` abrian un
`httpx.AsyncClient` por peticion. Construirlo arma un `SSLContext` de forma
sincrona (~480 ms en Windows), con el bucle congelado mientras tanto: cada
peticion por la puerta tardaba ~500 ms aunque el servicio respondiera en 9, 20
concurrentes tardaban 10 s, y las esperas de Redis del limite vencian y la
puerta contaba en memoria. El cliente se crea al arrancar y se cierra al apagar.
"""

from __future__ import annotations

import httpx
from tukit_gateway.api import app


def _contar_construcciones(monkeypatch) -> list[object]:
    """Anota cada `httpx.AsyncClient` que se construya desde aqui."""
    hechos: list[object] = []
    original = httpx.AsyncClient.__init__

    def espia(self, *args, **kwargs):
        hechos.append(self)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", espia)
    return hechos


class TestUnSoloClientePorProceso:
    async def test_el_arranque_crea_uno_y_el_apagado_lo_cierra(self):
        async with app.router.lifespan_context(app):
            cliente = app.state.cliente
            assert isinstance(cliente, httpx.AsyncClient)
            assert not cliente.is_closed
        assert cliente.is_closed

    async def test_las_peticiones_no_construyen_clientes(self, monkeypatch):
        # Servicios a un puerto cerrado: el reenvio falla rapido con 503, pero
        # recorre el camino entero, que es lo que se mide.
        for variable in (
            "TUKIT_CATALOGO_URL",
            "TUKIT_IDENTIDAD_URL",
            "TUKIT_INTELIGENCIA_URL",
            "TUKIT_COMERCIO_URL",
            "TUKIT_OPERACION_URL",
        ):
            monkeypatch.setenv(variable, "http://127.0.0.1:1")

        async with app.router.lifespan_context(app):
            compartido = app.state.cliente
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://prueba"
            ) as cliente:
                hechos = _contar_construcciones(monkeypatch)
                for _ in range(5):
                    assert (await cliente.get("/v1/catalogo/conceptos")).status_code == 503
                assert (await cliente.get("/v1/servicios")).status_code == 200

            assert hechos == [], f"se construyeron {len(hechos)} clientes en 6 peticiones"
            assert app.state.cliente is compartido
