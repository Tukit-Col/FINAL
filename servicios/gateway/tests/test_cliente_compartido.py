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
from tukit_gateway.api import RUTAS, app


class TestUnSoloClientePorProceso:
    async def test_el_arranque_crea_uno_y_el_apagado_lo_cierra(self):
        async with app.router.lifespan_context(app):
            cliente = app.state.cliente
            assert isinstance(cliente, httpx.AsyncClient)
            assert not cliente.is_closed
        assert cliente.is_closed

    async def test_reenvio_y_sonda_salen_por_el_cliente_compartido(self):
        # El cliente compartido es un httpx de verdad con un transporte que anota
        # cada salida. Si la puerta construyera otro cliente por peticion, esas
        # salidas no pasarian por aqui y la cuenta no cuadraria.
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
