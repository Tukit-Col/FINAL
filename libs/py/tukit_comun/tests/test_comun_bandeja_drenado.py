"""NFR-MAN-01: garantias del drenador del outbox que no fijan las pruebas basicas.

`test_bandeja.py` cubre el camino feliz de cada `Resultado`. Aqui se caracteriza
lo que protege los datos cuando algo sale mal: el orden y el limite de cada
pasada, que los reintentos se acumulan sin perder el evento, que un `manejar` o
un broker que revientan dejan TODA la pasada pendiente (nada se marca publicado
sin haberse entregado: at-least-once, ADR 0022) y que el id de correlacion que
se re-vincula para cada evento no se filtra al contexto del llamador.

Importa porque el outbox es la fuente de verdad de los avisos y de la saga de
pago: un evento marcado publicado sin entregar es un aviso perdido para siempre.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import MetaData, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bandeja import Resultado, bandeja_reflejada, con_correlacion, drenar
from tukit_comun.http import fijar_correlacion, id_de_correlacion, reset_correlacion

pytestmark = pytest.mark.nfr("NFR-MAN-01")

BANDEJA = bandeja_reflejada(MetaData())


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(BANDEJA.metadata.create_all)
    yield engine
    await engine.dispose()


async def _sembrar(motor: AsyncEngine, *filas: dict[str, Any]) -> None:
    # SQLite no autoincrementa un BigInteger: el id se asigna aqui, en orden de llegada.
    async with motor.begin() as conexion:
        for i, fila in enumerate(filas, start=1):
            await conexion.execute(insert(BANDEJA).values(**{"id": i, "intentos": 0, **fila}))


async def _estado(motor: AsyncEngine) -> dict[int, Any]:
    """`id -> fila` de toda la bandeja, para afirmar sobre lo persistido."""
    async with motor.connect() as conexion:
        return {f.id: f for f in await conexion.execute(select(BANDEJA).order_by(BANDEJA.c.id))}


def _hecho(vistos: list[Any] | None = None):
    async def manejar(conexion: Any, fila: Any) -> Resultado:
        if vistos is not None:
            vistos.append(fila.id)
        return Resultado.HECHO

    return manejar


class TestCadaPasadaTieneOrdenYLimite:
    async def test_procesa_en_orden_de_id_y_respeta_el_limite(self, motor):
        await _sembrar(motor, *({"tipo": "pedido_pagado", "carga": {"n": i}} for i in range(5)))
        vistos: list[int] = []

        entregados = await drenar(motor, _hecho(vistos), limite=2)

        assert entregados == 2
        assert vistos == [1, 2]
        estado = await _estado(motor)
        assert [i for i, f in estado.items() if f.publicado_en is not None] == [1, 2]
        assert [i for i, f in estado.items() if f.publicado_en is None] == [3, 4, 5]

    async def test_la_siguiente_pasada_retoma_donde_quedo_la_anterior(self, motor):
        await _sembrar(motor, *({"tipo": "pedido_pagado", "carga": {}} for _ in range(3)))
        vistos: list[int] = []

        assert await drenar(motor, _hecho(vistos), limite=2) == 2
        assert await drenar(motor, _hecho(vistos), limite=2) == 1
        assert await drenar(motor, _hecho(vistos), limite=2) == 0

        assert vistos == [1, 2, 3]  # ningun evento se procesa dos veces

    async def test_una_bandeja_vacia_no_llama_al_manejador(self, motor):
        vistos: list[int] = []
        assert await drenar(motor, _hecho(vistos)) == 0
        assert vistos == []

    async def test_el_filtro_por_tipo_no_marca_los_de_otro_tipo(self, motor):
        await _sembrar(
            motor,
            {"tipo": "kits_publicados", "carga": {}},
            {"tipo": "pedido_pagado", "carga": {}},
        )

        assert await drenar(motor, _hecho(), tipo="pedido_pagado") == 1

        estado = await _estado(motor)
        assert estado[1].publicado_en is None  # el otro tipo sigue esperando a su drenador
        assert estado[2].publicado_en is not None


class TestLosReintentosSeAcumulanSinPerderElEvento:
    async def test_cada_pasada_fallida_suma_un_intento_y_el_exito_final_lo_publica(self, motor):
        await _sembrar(motor, {"tipo": "kits_publicados", "carga": {}})
        resultados = iter([Resultado.REINTENTAR, Resultado.REINTENTAR, Resultado.HECHO])

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            return next(resultados)

        assert await drenar(motor, manejar) == 0
        assert await drenar(motor, manejar) == 0
        assert (await _estado(motor))[1].intentos == 2
        assert (await _estado(motor))[1].publicado_en is None

        assert await drenar(motor, manejar) == 1
        final = (await _estado(motor))[1]
        assert final.publicado_en is not None
        assert final.intentos == 2  # el historial de intentos se conserva

    async def test_un_intentos_nulo_se_trata_como_cero(self, motor):
        await _sembrar(motor, {"tipo": "kits_publicados", "carga": {}, "intentos": None})

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            return Resultado.REINTENTAR

        await drenar(motor, manejar)

        assert (await _estado(motor))[1].intentos == 1

    async def test_un_evento_que_reintenta_no_bloquea_a_los_demas_de_la_pasada(self, motor):
        await _sembrar(
            motor,
            {"tipo": "kits_publicados", "carga": {"n": 1}},
            {"tipo": "pedido_pagado", "carga": {"n": 2}},
        )

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            return Resultado.REINTENTAR if fila.tipo == "kits_publicados" else Resultado.HECHO

        assert await drenar(motor, manejar) == 1

        estado = await _estado(motor)
        assert estado[1].publicado_en is None and estado[1].intentos == 1
        assert estado[2].publicado_en is not None


class TestUnFalloDeEntregaNoMarcaNadaComoPublicado:
    async def test_si_el_broker_cae_a_mitad_de_pasada_todo_queda_pendiente(self, motor):
        """El outbox nunca pierde un evento: si `sink.publicar` levanta, la
        transaccion de la pasada se revierte y TODOS los eventos se reintentan
        (at-least-once; los consumidores son idempotentes, ADR 0022)."""
        await _sembrar(
            motor,
            {"tipo": "pedido_pagado", "carga": {"n": 1}},
            {"tipo": "pedido_pagado", "carga": {"n": 2}},
        )

        class BrokerCaido:
            def __init__(self) -> None:
                self.publicados: list[int] = []

            async def publicar(self, fila: Any) -> None:
                if fila.id == 2:
                    raise ConnectionError("broker caido")
                self.publicados.append(fila.id)

        sink = BrokerCaido()
        with pytest.raises(ConnectionError):
            await drenar(motor, _hecho(), sink=sink)

        assert sink.publicados == [1]
        assert all(f.publicado_en is None for f in (await _estado(motor)).values())

        # Con el broker de vuelta, la siguiente pasada entrega los dos.
        class BrokerSano:
            def __init__(self) -> None:
                self.publicados: list[int] = []

            async def publicar(self, fila: Any) -> None:
                self.publicados.append(fila.id)

        sano = BrokerSano()
        assert await drenar(motor, _hecho(), sink=sano) == 2
        assert sano.publicados == [1, 2]

    async def test_si_el_manejador_revienta_la_excepcion_sale_y_no_se_marca_nada(self, motor):
        await _sembrar(motor, {"tipo": "pedido_pagado", "carga": {}})

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            raise RuntimeError("fallo inesperado del manejador")

        with pytest.raises(RuntimeError, match="inesperado"):
            await drenar(motor, manejar)

        fila = (await _estado(motor))[1]
        assert fila.publicado_en is None
        assert fila.intentos == 0

    async def test_el_sink_solo_ve_lo_que_el_manejador_dio_por_hecho(self, motor):
        await _sembrar(
            motor,
            {"tipo": "kits_publicados", "carga": {}},
            {"tipo": "pedido_pagado", "carga": {}},
            {"tipo": "ajeno", "carga": {}},
        )
        publicados: list[str] = []

        class Sink:
            async def publicar(self, fila: Any) -> None:
                publicados.append(fila.tipo)

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            return {
                "kits_publicados": Resultado.REINTENTAR,
                "pedido_pagado": Resultado.HECHO,
                "ajeno": Resultado.OMITIR,
            }[fila.tipo]

        assert await drenar(motor, manejar, sink=Sink()) == 1
        assert publicados == ["pedido_pagado"]


class TestLaCorrelacionSeRevinculaYNoSeFiltra:
    async def test_cada_evento_ve_su_propio_id_y_el_contexto_del_llamador_se_restaura(self, motor):
        await _sembrar(
            motor,
            {"tipo": "pedido_pagado", "carga": {"correlacion_id": "req-uno"}},
            {"tipo": "pedido_pagado", "carga": {"correlacion_id": "req-dos"}},
            {"tipo": "pedido_pagado", "carga": {}},
        )
        vistos: list[str | None] = []

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            vistos.append(id_de_correlacion())
            return Resultado.HECHO

        token = fijar_correlacion("contexto-del-llamador")
        try:
            await drenar(motor, manejar)
            despues = id_de_correlacion()
        finally:
            reset_correlacion(token)

        # El evento sin id NO hereda el del llamador: se ve como "sin correlacion".
        assert vistos == ["req-uno", "req-dos", None]
        assert despues == "contexto-del-llamador"

    async def test_si_el_manejador_revienta_el_contexto_tambien_se_restaura(self, motor):
        await _sembrar(motor, {"tipo": "pedido_pagado", "carga": {"correlacion_id": "req-roto"}})

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            assert id_de_correlacion() == "req-roto"
            raise RuntimeError("revienta")

        with pytest.raises(RuntimeError):
            await drenar(motor, manejar)

        assert id_de_correlacion() is None  # el id del evento no se quedo pegado

    @pytest.mark.parametrize("carga", [None, [1, 2, 3], "texto"])
    async def test_una_carga_que_no_es_un_objeto_se_entrega_sin_correlacion(self, motor, carga):
        await _sembrar(motor, {"tipo": "pedido_pagado", "carga": carga})
        vistos: list[Any] = []

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            vistos.append(id_de_correlacion())
            return Resultado.HECHO

        assert await drenar(motor, manejar) == 1
        assert vistos == [None]


class TestLaCargaLlevaElHiloDeLaPeticion:
    def test_con_correlacion_devuelve_una_copia_y_no_muta_la_carga_original(self):
        original = {"pedido_id": "p1"}
        token = fijar_correlacion("req-9")
        try:
            estampada = con_correlacion(original)
        finally:
            reset_correlacion(token)

        assert estampada == {"pedido_id": "p1", "correlacion_id": "req-9"}
        assert original == {"pedido_id": "p1"}

    async def test_ida_y_vuelta_por_el_outbox(self, motor):
        """El productor estampa el id al escribir y el drenador lo recupera al leer."""
        token = fijar_correlacion("req-ida-y-vuelta")
        try:
            carga = con_correlacion({"pedido_id": "p1"})
        finally:
            reset_correlacion(token)
        await _sembrar(motor, {"tipo": "pedido_pagado", "carga": carga})
        vistos: list[str | None] = []

        async def manejar(conexion: Any, fila: Any) -> Resultado:
            vistos.append(id_de_correlacion())
            return Resultado.HECHO

        await drenar(motor, manejar)

        assert vistos == ["req-ida-y-vuelta"]


class TestLaTablaReflejada:
    def test_declara_solo_las_columnas_comunes_a_todos_los_servicios(self):
        tabla = bandeja_reflejada()
        assert tabla.name == "bandeja_salida"
        assert set(tabla.c.keys()) == {
            "id",
            "tipo",
            "agregado_tipo",
            "agregado_id",
            "carga",
            "publicado_en",
            "intentos",
        }

    def test_cada_llamada_usa_su_propio_metadata(self):
        """Dos bandejas reflejadas en el mismo proceso no deben chocar."""
        a = bandeja_reflejada()
        b = bandeja_reflejada()
        assert a is not b
        assert a.metadata is not b.metadata
