"""Fase 3 de QA: la entrega entre servicios con el stack vivo, con broker o sondeando.

`test_integracion_bandeja.py` ya fija que el pago escribe su evento en la misma transaccion y que
el repartidor avisa una vez. Aqui va lo que ninguna prueba del stack mira:

- la entrega de punta a punta va por el modo que declara el lanzador (`QA_MODO`, PEN-92, ADR 0046):
  con broker estan los tres publicadores; sin el, nadie publica y los consumidores sondean (N-142);
- un evento que se vuelve a entregar no da un segundo aviso (ADR 0042). La reentrega se provoca
  dejando sin publicar el evento del pedido de la propia prueba (N-144);
- aprobar la lista de un colegio escrito a mano lo da de alta con el id que derivo la subida
  (ADR 0045);
- la lista que el catalogo no recibe queda pendiente y el trabajador la importa despues (ADR 0040);
- en el modo completo, la misma lista subida dos veces se lee una sola vez (ADR 0047). Lleva el
  marcador `redis` y queda fuera de `-m integracion` salvo que se pida: con `redis` en la expresion
  de `-m` o con `TUKIT_PRUEBAS_REDIS_OBLIGATORIO=1`, que el lanzador exporta en el modo completo
  (`conftest.py`). Pedida, si el Redis de `TUKIT_PRUEBAS_REDIS_URL` no responde, falla (N-143).

Las subidas pasan por una copia de inteligencia con el lector grabado
(`inteligencia_lector_grabado.py`): sin clave, sin red y con la cuenta de sus lecturas.
"""

from __future__ import annotations

import contextlib
import hashlib
import inspect
import io
import json
import os
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image, ImageDraw
from stack_vivo import EJECUCION, GATEWAY, instancia, orden_pagada, portador, procesos_del_stack, puerto_libre
from tukit_comun import derivar
from tukit_comun.cache import PREFIJO, entero_de_entorno, responde
from tukit_comun.pruebas_redis import borrar_prefijo, lo_guardado, url_de_pruebas
from tukit_inteligencia import cache_lecturas

pytestmark = pytest.mark.integracion

# Varias pasadas de los procesos de fondo (`--intervalo` 5 s) y, en el ADR 0040, la primera espera
# de 5 s tras la caida.
_TOPE_SEGUNDOS = 45.0
# Con broker, el repartidor toma de la cola lo que el publicador ya marco como publicado.
_ESPERA_DEL_CONSUMIDOR = 10.0
_PUBLICADORES = {"publicador-catalogo", "publicador-comercio", "publicador-inteligencia"}

_EVENTO_DEL_PEDIDO = "select id from bandeja_salida where tipo = 'pedido_pagado' and agregado_id::text = :p"
_IMPORTACION_DE_LA_PAGINA = (
    "select id::text, estado, intentos from importacion_lista where encode(sha256(documento), 'hex') = :h"
)
_AVISOS_DEL_PEDIDO = """
    select canal, estado, evento_origen, evento_id from notificacion
    where plantilla = 'pedido_pagado' and usuario_id::text = :u and datos->>'pedido' = :corto
"""


@pytest.fixture(scope="module")
def colegio_aliado(stack: dict[str, Any]) -> str:
    colegios = httpx.get(f"{GATEWAY}/v1/colegios", timeout=30).json()["colegios"]
    if not colegios:
        pytest.fail("no hay colegios aliados sembrados; falta `make bd-sembrar`")
    return colegios[0]["colegio_id"]


@contextlib.contextmanager
def _inteligencia_grabada(carpeta: Path, **entorno: str) -> Iterator[tuple[str, Path]]:
    """Una inteligencia aparte con el lector grabado; devuelve su URL y la carpeta de lo leido."""
    capturas = carpeta / "capturas"
    with instancia(
        "inteligencia_lector_grabado",
        carpeta / "inteligencia.log",
        PYTHONPATH=str(Path(__file__).resolve().parent),
        TUKIT_QA_CAPTURAS=str(capturas),
        **entorno,
    ) as base:
        yield base, capturas


def _pagina(marca: str) -> bytes:
    """Una lista de mentira, unica por prueba: su huella es la clave de la cache."""
    imagen = Image.new("RGB", (900, 240), "white")
    lienzo = ImageDraw.Draw(imagen)
    lienzo.text((30, 30), "LISTA DE UTILES 2026 - GRADO PRIMERO", fill="black")
    lienzo.text((30, 80), "2  Cuaderno cuadriculado de 100 hojas", fill="black")
    lienzo.text((30, 130), f"QA {marca}", fill="black")
    salida = io.BytesIO()
    imagen.save(salida, format="PNG")
    return salida.getvalue()


def _subir(base: str, colegio: dict[str, str], pagina: bytes) -> httpx.Response:
    hijos = [{"referencia": "hijo-1", "grado": "Primero", **colegio}]
    return httpx.post(
        f"{base}/v1/listas/subir",
        data={"hijos": json.dumps(hijos), "referencia": "hijo-1"},
        files={"archivo": ("lista.png", pagina, "image/png")},
        timeout=60,
    )


def _lecturas(capturas: Path) -> int:
    registro = capturas / "lecturas.log"
    return len(registro.read_text().splitlines()) if registro.exists() else 0


def _con_broker() -> bool:
    """Si `make arriba` arranco con RabbitMQ: deja la URL en `broker` solo si el broker respondio."""
    broker = EJECUCION / "broker"
    return broker.is_file() and broker.stat().st_size > 0


async def _esperar(sondeo: Callable[[], Any], tope: float = _TOPE_SEGUNDOS) -> tuple[Any, float]:
    """Repite `sondeo` hasta que devuelva algo o pase el tope; devuelve lo ultimo y los segundos."""
    inicio = time.monotonic()
    while True:
        valor = sondeo()
        if inspect.isawaitable(valor):
            valor = await valor
        segundos = time.monotonic() - inicio
        if valor or segundos > tope:
            return valor, segundos
        time.sleep(0.5)


async def _publicado(consultar, evento: int) -> Any:
    filas = await consultar("comercio", "select publicado_en from bandeja_salida where id = :e", e=evento)
    return filas[0][0]


# ---------------------------------------------------------------- la entrega (ADR 0046, ADR 0042)


@pytest.mark.nfr("NFR-DIS-05")
async def test_la_entrega_de_punta_a_punta_va_por_el_modo_del_lanzador(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar, record_property
):
    modo = os.environ.get("QA_MODO")
    con_broker = _con_broker()
    publicadores = {nombre for nombre in procesos_del_stack().values() if nombre.startswith("publicador-")}
    record_property("modo", modo or "sin lanzador")
    record_property("con_broker", con_broker)
    if modo is not None:
        assert con_broker == (modo == "completo"), f"QA_MODO={modo} y el stack con_broker={con_broker}"
    assert publicadores == (_PUBLICADORES if con_broker else set())

    usuario_id = sesiones["acudiente"]["usuario_id"]
    pedido = orden_pagada(cliente, usuario_id, producto)
    avisos, segundos = await _esperar(
        lambda: consultar("operacion", _AVISOS_DEL_PEDIDO, u=usuario_id, corto=pedido[:8].upper())
    )

    record_property("segundos_hasta_el_aviso", round(segundos, 2))
    assert len(avisos) == 1, avisos
    assert (avisos[0][0], avisos[0][1]) == ("correo", "enviada")


@pytest.mark.nfr("NFR-DIS-05")
async def test_el_evento_que_se_vuelve_a_entregar_no_da_un_segundo_aviso(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar, record_property
):
    usuario_id = sesiones["acudiente"]["usuario_id"]
    pedido = orden_pagada(cliente, usuario_id, producto)
    filas = await consultar("comercio", _EVENTO_DEL_PEDIDO, p=pedido)
    evento = filas[0][0]
    primero, _ = await _esperar(
        lambda: consultar("operacion", _AVISOS_DEL_PEDIDO, u=usuario_id, corto=pedido[:8].upper())
    )
    assert len(primero) == 1, f"el primer aviso no llego en {_TOPE_SEGUNDOS:.0f} s"
    publicado, _ = await _esperar(lambda: _publicado(consultar, evento))
    assert publicado, f"el evento {evento} sigue sin publicar a los {_TOPE_SEGUNDOS:.0f} s"

    # La reentrega: el evento vuelve a quedar sin publicar, como si la pasada que aviso no hubiera
    # alcanzado a marcarlo. Sondeando lo toma el repartidor; con broker, el publicador lo vuelve a
    # poner en la cola con el mismo id.
    await consultar("comercio", "update bandeja_salida set publicado_en = null where id = :e", e=evento)
    republicado, segundos = await _esperar(lambda: _publicado(consultar, evento))
    time.sleep(_ESPERA_DEL_CONSUMIDOR)
    avisos = await consultar("operacion", _AVISOS_DEL_PEDIDO, u=usuario_id, corto=pedido[:8].upper())

    record_property("segundos_hasta_volver_a_publicar", round(segundos, 2))
    record_property("evento_origen", str(avisos[0][2]) if avisos else "")
    assert republicado, f"el evento reentregado sigue sin publicar a los {_TOPE_SEGUNDOS:.0f} s"
    assert len(avisos) == 1, avisos
    assert avisos[0][3] == evento


# ---------------------------------------------------------------- el colegio nuevo (ADR 0045)


@pytest.mark.nfr("NFR-ESC-07")
async def test_aprobar_la_lista_de_un_colegio_escrito_a_mano_lo_da_de_alta(
    tmp_path: Path, cliente: httpx.Client, sesiones: dict, consultar, record_property
):
    nombre = f"Colegio Ficticio QA alta {uuid.uuid4().hex[:8]}"
    colegio_id = str(derivar("colegio", "libre", " ".join(nombre.lower().split())))

    def _el_colegio() -> dict | None:
        respuesta = cliente.get("/v1/colegios", params={"busqueda": nombre})
        assert respuesta.status_code == 200, respuesta.text
        return next((c for c in respuesta.json()["colegios"] if c["colegio_id"] == colegio_id), None)

    with _inteligencia_grabada(tmp_path) as (base, _):
        subida = _subir(base, {"colegio_nombre": nombre}, _pagina(nombre))
    assert subida.status_code == 202, subida.text
    version_id = subida.json()["subidas"][0]["version_id"]
    assert _el_colegio() is None

    cierre = cliente.post(f"/v1/admin/listas/{version_id}/cerrar", headers=portador(sesiones, "admin"))
    assert cierre.status_code == 200, cierre.text
    colegio, segundos = await _esperar(_el_colegio)
    eventos = await consultar(
        "catalogo",
        "select count(*) from bandeja_salida where tipo = 'colegio_verificado' and agregado_id::text = :c",
        c=colegio_id,
    )

    record_property("segundos_hasta_el_alta", round(segundos, 2))
    assert colegio is not None, f"el colegio {colegio_id} no aparece a los {_TOPE_SEGUNDOS:.0f} s"
    assert colegio["nombre"] == nombre
    assert colegio["sedes"] == 1
    assert eventos[0][0] == 1


# ---------------------------------------------------------------- la importacion pendiente (ADR 0040)


@pytest.mark.nfr("NFR-DIS-05")
async def test_la_lista_que_el_catalogo_no_recibe_se_importa_despues(
    tmp_path: Path, colegio_aliado: str, consultar, record_property
):
    pagina = _pagina(uuid.uuid4().hex)
    # La copia apunta a un puerto donde nadie escucha: el catalogo rechaza la conexion.
    sin_catalogo = f"http://127.0.0.1:{puerto_libre()}"
    with _inteligencia_grabada(tmp_path, TUKIT_CATALOGO_URL=sin_catalogo) as (base, _):
        subida = _subir(base, {"colegio_id": colegio_aliado}, pagina)

    assert subida.status_code == 202, subida.text
    assert subida.json()["subidas"] == [
        {"referencia": "hijo-1", "version_id": None, "grado": "Primero", "estado": "pendiente"}
    ]
    filas = await consultar("inteligencia", _IMPORTACION_DE_LA_PAGINA, h=hashlib.sha256(pagina).hexdigest())
    assert len(filas) == 1, filas
    fila_id, estado, intentos = filas[0]
    assert (estado, intentos) == ("pendiente", 1)

    async def _resuelta() -> Any:
        fila = (
            await consultar(
                "inteligencia",
                "select estado, version_id, intentos from importacion_lista where id::text = :i",
                i=fila_id,
            )
        )[0]
        return fila if fila[0] != "pendiente" else None

    resuelta, segundos = await _esperar(_resuelta)

    record_property("segundos_hasta_importar", round(segundos, 2))
    assert resuelta is not None, f"la importacion sigue pendiente a los {_TOPE_SEGUNDOS:.0f} s"
    estado, version_id, intentos = resuelta
    record_property("intentos", intentos)
    assert estado == "importada"
    assert version_id
    version = await consultar(
        "catalogo", "select count(*) from version_lista_oficial where id::text = :v", v=version_id
    )
    assert version[0][0] == 1


# ---------------------------------------------------------------- una sola lectura (ADR 0047)


@pytest.mark.redis
@pytest.mark.nfr("NFR-REN-11")
async def test_la_misma_lista_subida_dos_veces_se_lee_una_sola_vez(
    tmp_path: Path, colegio_aliado: str, record_property
):
    url = url_de_pruebas()
    motivo = await responde(url)
    if motivo is not None:
        pytest.fail(f"la prueba pide Redis y el de TUKIT_PRUEBAS_REDIS_URL no responde ({motivo})")
    pagina = _pagina(uuid.uuid4().hex)
    clave = PREFIJO + cache_lecturas.clave(pagina)

    try:
        with _inteligencia_grabada(tmp_path, REDIS_URL=url) as (base, capturas):
            primera = _subir(base, {"colegio_id": colegio_aliado}, pagina)
            segunda = _subir(base, {"colegio_id": colegio_aliado}, pagina)
        guardado = await lo_guardado(clave)
    finally:
        await borrar_prefijo(url, clave)

    lecturas = _lecturas(capturas)
    record_property("lecturas", lecturas)
    assert primera.status_code == segunda.status_code == 202, (primera.text, segunda.text)
    assert lecturas == 1
    assert list(guardado) == [clave]
    ttl = entero_de_entorno("TUKIT_CACHE_PERCEPCION_SEGUNDOS", cache_lecturas.TTL_POR_OMISION)
    assert guardado[clave].vence_en_ms / 1000 == pytest.approx(ttl, abs=60)
