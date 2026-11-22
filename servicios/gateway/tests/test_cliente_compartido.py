from __future__ import annotations

import httpx
from tukit_gateway.api import RUTAS, app


class TestUnSoloClientePorProceso:
    async def test_el_arranque_crea_uno_y_el_apagado_lo_cierra(self):
        async with app.router.lifespan_context(app):
            cliente = app.state.cliente
            assert isinstance(cliente, httpx.AsyncClient)
            assert not cliente.is_closed
        assert cliente.is_closed

    async def test_reenvio_y_sonda_salen_por_el_cliente_compartido(self):
        salidas: list[str] = []

        def anotar(peticion: httpx.Request) -> httpx.Response:
            salidas.append(peticion.url.path)
            return httpx.Response(200, json={"ok": True})

        compartido = httpx.AsyncClient(transport=httpx.MockTransport(anotar))
        app.state.cliente = compartido
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
            for _ in range(5):
                assert (await cliente.get("/v1/catalogo/conceptos")).json() == {"ok": True}
            sonda = (await cliente.get("/v1/servicios")).json()

        servicios = set(RUTAS.values())
        assert sonda["todos_arriba"] is True
        assert set(sonda["servicios"]) == servicios
        assert salidas == ["/v1/catalogo/conceptos"] * 5 + ["/health/ready"] * len(servicios)
        assert app.state.cliente is compartido
