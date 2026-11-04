"""La privacidad del titular de punta a punta (Ley 1581, ADR 0048), contra el stack vivo.

oe5 ya prueba cada pieza por separado: la solicitud y la frase en Identidad
(`test_privacidad.py`, `test_mis_datos.py`), cada consumidor de la supresion
(`test_supresion_*.py` de comercio, operacion e inteligencia), la confirmacion
(`test_supresion_confirmada.py`) y el barrido (`test_barrido_supresion.py`). Aqui
va lo que solo se ve con los procesos de verdad:

- nadie consulta, exporta, suprime ni revoca con la sesion de otro acudiente;
- con broker, `titular_suprimido` llega a Comercio, Operacion e Inteligencia, las
  tres confirmaciones vuelven a Identidad y la solicitud queda `completada`;
- despues de suprimir no queda un dato personal del titular en ninguna base;
- CH-35 simplificado: con los consumidores detenidos la solicitud queda en
  `propagando`, visible, y al volver se completa una sola vez;
- el barrido retoma una solicitud atascada;
- el consentimiento que deja el registro, del titular y de cada hijo, con su version;
- la revocacion del consentimiento.

La supresion solo viaja con broker (los consumidores son de RabbitMQ y el propio
codigo lo dice), asi que las pruebas que la siguen exigen el modo completo del
lanzador y fallan en el otro: no se saltan (H-C-03).

`POST /v1/cuenta/supresion` tiene su propio nivel en la puerta, 5 por token y 10 por
IP cada hora: cada prueba registra su titular, que llega con su propia IP (N-120).

Las que esperan la supresion `completada` van a dar rojo mientras Operacion no
tenga publicador de su bandeja: su `supresion_confirmada` se queda ahi y nunca
llega a Identidad. Van con la expectativa del ADR 0048 y sin xfail (decision N-160).
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from stack_vivo import (
    GATEWAY,
    RAIZ,
    SERVICIOS_CON_BASE,
    cabecera_de_familia,
    conexion_a,
    crear_orden,
    pagar,
    procesos_del_stack,
)
from tukit_comun.supresion import MARCA_SUPRIMIDO, SUSCRIPTORES_SUPRESION

pytestmark = pytest.mark.integracion

# La frase que pide la supresion (`tukit_identidad.dominio.privacidad.FRASE_CONFIRMACION`).
FRASE = "ELIMINAR MIS DATOS"
# Lo que tarda en cerrarse una supresion con los tres consumidores arriba. El barrido la
# da por atascada a la hora (`REENVIAR_TRAS_POR_OMISION`); la propagacion normal es de segundos.
ESPERA_PROPAGACION = float(os.environ.get("TUKIT_QA_ESPERA_SUPRESION", "60"))
# Los consumidores de la supresion como los nombra `make arriba` en `.ejecucion/<nombre>.pid`.
CONSUMIDORES = tuple(f"supresion-{s}" for s in sorted(SUSCRIPTORES_SUPRESION))

_COLUMNAS = """
    select table_name, column_name, data_type from information_schema.columns
    where table_schema = 'public'
      and data_type in ('text', 'character varying', 'character', 'json', 'jsonb', 'bytea')
    order by table_name, column_name
"""


# --------------------------------------------------------------- ayudantes


def _marca(prefijo: str) -> str:
    """Un dato ficticio con sufijo unico, para buscarlo en las bases sin ruido."""
    return f"{prefijo}{uuid.uuid4().hex[:10]}"


def _registrar(http: httpx.Client, colegio_id: str) -> dict[str, Any]:
    """Registra un titular ficticio con un hijo de apodo unico y abre su sesion, con su IP."""
    correo = f"qa-priv-{uuid.uuid4().hex[:10]}@example.test"
    clave = "clave-ficticia-qa"
    apodo = _marca("Privalina")
    ip = cabecera_de_familia()
    registro = http.post(
        "/v1/registro",
        headers=ip,
        json={
            "correo": correo,
            "clave": clave,
            "acepta_terminos": True,
            "hijos": [{"colegio_id": colegio_id, "grado": "Primero", "apodo": apodo}],
        },
    )
    assert registro.status_code == 201, registro.text
    sesion = http.post("/v1/sesiones", headers=ip, json={"correo": correo, "clave": clave})
    assert sesion.status_code == 200, sesion.text
    cuerpo = sesion.json()
    return {
        "correo": correo,
        "clave": clave,
        "apodo": apodo,
        "ip": ip,
        "usuario_id": cuerpo["sesion"]["usuario_id"],
        "cabecera": {"authorization": f"Bearer {cuerpo['token']}", **ip},
    }


def _suprimir(http: httpx.Client, titular: dict[str, Any], **extra: Any) -> dict[str, Any]:
    respuesta = http.post(
        "/v1/cuenta/supresion", headers=titular["cabecera"], json={"confirmacion": FRASE, **extra}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


async def _uno(servicio: str, sql: str, **parametros: Any) -> Any:
    async with conexion_a(servicio) as conexion:
        resultado = await conexion.execute(text(sql), parametros)
        filas = list(resultado) if resultado.returns_rows else []
        await conexion.commit()
        return filas


async def _solicitud(solicitud_id: str) -> dict[str, Any]:
    filas = await _uno(
        "identidad",
        "select estado, suscriptores_confirmados, resuelto_en from solicitud_supresion where id::text = :s",
        s=solicitud_id,
    )
    assert filas, f"identidad no guardo la solicitud {solicitud_id}"
    estado, confirmados, resuelto_en = filas[0]
    if isinstance(confirmados, str):
        confirmados = json.loads(confirmados)
    return {"estado": estado, "confirmados": sorted(confirmados or []), "resuelto_en": resuelto_en}


async def _esperar_cierre(solicitud_id: str, espera: float = ESPERA_PROPAGACION) -> dict[str, Any]:
    """Sondea la solicitud hasta que deja `propagando` o se acaba la espera; devuelve la ultima."""
    limite = time.monotonic() + espera
    while True:
        actual = await _solicitud(solicitud_id)
        if actual["estado"] != "propagando" or time.monotonic() > limite:
            return actual
        time.sleep(1.0)


async def _confirmaciones(solicitud_id: str) -> dict[str, dict[str, int]]:
    """Por servicio, cuantas `supresion_confirmada` escribio en su bandeja y cuantas publico."""
    cuenta = {}
    for servicio in sorted(SUSCRIPTORES_SUPRESION):
        (escritas, publicadas), *_ = await _uno(
            servicio,
            "select count(*), count(publicado_en) from bandeja_salida "
            "where tipo = 'supresion_confirmada' and agregado_id::text = :s",
            s=solicitud_id,
        )
        cuenta[servicio] = {"escritas": escritas, "publicadas": publicadas}
    return cuenta


async def _apariciones(marcas: list[str]) -> list[str]:
    """`base.tabla.columna: marca` de cada columna de las cinco bases que guarda una marca en claro."""
    encontradas = []
    for servicio in SERVICIOS_CON_BASE:
        async with conexion_a(servicio) as conexion:
            columnas = [tuple(f) for f in await conexion.execute(text(_COLUMNAS))]
            for tabla, columna, tipo in columnas:
                if tipo == "bytea":
                    condicion = f"position(convert_to(:marca, 'UTF8') in \"{columna}\") > 0"
                else:
                    condicion = f'strpos("{columna}"::text, :marca) > 0'
                consulta = text(f'select count(*) from "{tabla}" where {condicion}')
                for marca in marcas:
                    if (await conexion.execute(consulta, {"marca": marca})).scalar_one():
                        encontradas.append(f"{servicio}.{tabla}.{columna}: {marca}")
    return encontradas


def _modo_completo() -> None:
    """La supresion solo viaja con broker: sin el modo completo la prueba falla, no se salta."""
    modo = os.environ.get("QA_MODO", "")
    if modo != "completo":
        pytest.fail(
            f"QA_MODO={modo or '(sin definir)'}: la supresion solo viaja con RabbitMQ; "
            "correr con el lanzador en modo completo"
        )


def _pids_de(nombres: tuple[str, ...]) -> dict[str, int]:
    vivos = {nombre: pid for pid, nombre in procesos_del_stack().items()}
    faltan = [n for n in nombres if n not in vivos]
    if faltan:
        pytest.fail(
            f"no estan los pid de {faltan} en .ejecucion/: esta prueba necesita los consumidores "
            "que lanza `make arriba` con broker (ver «verificar en la corrida», D3a)"
        )
    return {n: vivos[n] for n in nombres}


@contextlib.contextmanager
def _detenidos(nombres: tuple[str, ...]) -> Iterator[dict[str, int]]:
    """Detiene los procesos con SIGSTOP y los reanuda con SIGCONT al salir, pase lo que pase.

    Detenido, el proceso no consume ni confirma, pero conserva su pid y su conexion; al
    reanudar retoma la cola. Si el broker cerro la conexion por latido, el mensaje sin
    confirmar vuelve a la cola y se entrega otra vez: eso prueba tambien la idempotencia.
    """
    pids = _pids_de(nombres)
    detenidos = []
    try:
        for pid in pids.values():
            os.kill(pid, signal.SIGSTOP)
            detenidos.append(pid)
        yield pids
    finally:
        for pid in detenidos:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGCONT)


# --------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def colegio_aliado() -> str:
    colegios = httpx.get(f"{GATEWAY}/v1/colegios", timeout=30).json()["colegios"]
    if not colegios:
        pytest.fail("no hay colegios aliados sembrados; falta `make bd-sembrar`")
    return colegios[0]["colegio_id"]


@pytest.fixture
def titular(cliente: httpx.Client, colegio_aliado: str) -> dict[str, Any]:
    return _registrar(cliente, colegio_aliado)


@pytest.fixture
def otro_titular(cliente: httpx.Client, colegio_aliado: str) -> dict[str, Any]:
    return _registrar(cliente, colegio_aliado)


# --------------------------------------------------------------- nadie toca los datos de otro


@pytest.mark.nfr("NFR-SEG-10")
def test_nadie_consulta_ni_exporta_los_datos_de_otro_acudiente(
    cliente: httpx.Client, titular: dict, otro_titular: dict, record_property
):
    """Las rutas de privacidad salen del token: no hay un id que cambiar para leer a otro."""
    ajeno = {"usuario_id": otro_titular["usuario_id"]}
    sin_sesion = cliente.get("/v1/cuenta/mis-datos")
    consulta = cliente.get("/v1/cuenta/mis-datos", headers=titular["cabecera"], params=ajeno)
    exportacion = cliente.get("/v1/cuenta/mis-datos/exportar", headers=titular["cabecera"], params=ajeno)
    sin_sesion_exportar = cliente.get("/v1/cuenta/mis-datos/exportar")

    record_property("sin_sesion", f"{sin_sesion.status_code},{sin_sesion_exportar.status_code}")
    assert sin_sesion.status_code == 401, sin_sesion.text
    assert sin_sesion_exportar.status_code == 401, sin_sesion_exportar.text
    assert consulta.status_code == 200, consulta.text
    assert exportacion.status_code == 200, exportacion.text
    assert consulta.json()["cuenta"]["usuario_id"] == titular["usuario_id"]
    assert exportacion.json()["cuenta"]["usuario_id"] == titular["usuario_id"]
    assert exportacion.json()["cuenta"]["correo"] == titular["correo"]
    for cuerpo in (consulta.text, exportacion.text):
        assert otro_titular["usuario_id"] not in cuerpo
        assert otro_titular["correo"] not in cuerpo
        assert otro_titular["apodo"] not in cuerpo
    assert "no-store" in exportacion.headers.get("cache-control", "")


@pytest.mark.nfr("NFR-SEG-10")
async def test_nadie_suprime_ni_revoca_los_datos_de_otro_acudiente(
    cliente: httpx.Client, titular: dict, otro_titular: dict, record_property
):
    """Un `usuario_id` ajeno en el cuerpo se ignora: se suprime y se revoca al portador, y al
    otro no le pasa nada. Sin sesion, las dos rutas responden 401."""
    ajeno = {"usuario_id": otro_titular["usuario_id"]}
    sin_sesion = [
        cliente.post("/v1/cuenta/supresion", json={"confirmacion": FRASE, **ajeno}).status_code,
        cliente.post("/v1/cuenta/consentimientos/revocar", json=ajeno).status_code,
    ]
    revocacion = cliente.post("/v1/cuenta/consentimientos/revocar", headers=titular["cabecera"], json=ajeno)
    supresion = _suprimir(cliente, titular, **ajeno)
    solicitudes = await _uno(
        "identidad",
        "select usuario_id::text from solicitud_supresion where id::text = :s",
        s=supresion["solicitud_id"],
    )
    revocados_del_otro = await _uno(
        "identidad",
        "select count(*) from consentimiento where usuario_id::text = :u and revocado_en is not null",
        u=otro_titular["usuario_id"],
    )
    sesion_del_otro = cliente.post(
        "/v1/sesiones",
        headers=otro_titular["ip"],
        json={"correo": otro_titular["correo"], "clave": otro_titular["clave"]},
    )
    datos_del_otro = cliente.get("/v1/cuenta/mis-datos", headers=otro_titular["cabecera"])

    record_property("sin_sesion", ",".join(map(str, sin_sesion)))
    assert sin_sesion == [401, 401]
    assert revocacion.status_code == 200, revocacion.text
    assert solicitudes == [(titular["usuario_id"],)]
    assert revocados_del_otro[0][0] == 0
    assert sesion_del_otro.status_code == 200, sesion_del_otro.text
    assert datos_del_otro.status_code == 200, datos_del_otro.text
    assert datos_del_otro.json()["cuenta"]["correo"] == otro_titular["correo"]
    assert otro_titular["apodo"] in {h["apodo"] for h in datos_del_otro.json()["hijos"]}


# --------------------------------------------------------------- el consentimiento guardado (D3b)

# Las versiones de los textos que se aceptan (`routers/identidad.py:401-404`): la politica de
# datos y los terminos del titular, y la autorizacion del dato del menor.
VERSION_TITULAR = "2026-11"
VERSION_MENOR = "2026-09"


@pytest.mark.nfr("NFR-SEG-10")
def test_el_registro_deja_el_consentimiento_del_titular_con_su_version(
    cliente: httpx.Client, titular: dict, record_property
):
    """El rechazo sin `acepta_terminos` ya lo prueban `test_api_identidad.py` y
    `test_cuenta_acudiente.py` de oe5. Aqui: por la puerta, el alta deja una sola
    autorizacion `registro_titular`, vigente, sin matricula y con la version del texto, y el
    titular la ve en su consulta (N-162)."""
    datos = cliente.get("/v1/cuenta/mis-datos", headers=titular["cabecera"])
    assert datos.status_code == 200, datos.text
    consentimientos = datos.json()["consentimientos"]
    record_property("consentimientos", json.dumps(consentimientos))

    titulares = [c for c in consentimientos if c["regimen"] == "registro_titular"]
    assert [(c["version"], c["matricula_id"], c["revocado_en"]) for c in titulares] == [
        (VERSION_TITULAR, None, None)
    ]


@pytest.mark.nfr("NFR-SEG-10")
def test_cada_hijo_del_registro_lleva_su_consentimiento_de_menor_con_su_version(
    cliente: httpx.Client, titular: dict, record_property
):
    """Cada matricula que nace en `POST /v1/registro` lleva su `registro_menor`, con la version
    de la autorizacion del menor (spec de identidad y cuenta §4.1: no hay matricula sin
    consentimiento propio). `POST /v1/cuenta/hijos` ya lo prueba
    `test_identidad_rutas_acceso.py`; el alta con hijos no lo prueba nadie.

    Se espera roja, sin xfail: `materializar_hijos` no escribe consentimiento (N-162,
    «candidatos a hallazgo»)."""
    datos = cliente.get("/v1/cuenta/mis-datos", headers=titular["cabecera"])
    assert datos.status_code == 200, datos.text
    cuerpo = datos.json()
    matriculas = sorted(m["matricula_id"] for m in cuerpo["matriculas"])
    menores = [c for c in cuerpo["consentimientos"] if c["regimen"] == "registro_menor"]
    record_property("matriculas", len(matriculas))
    record_property("consentimientos_menor", json.dumps(menores))

    assert matriculas, "el titular de la prueba se registra con un hijo"
    assert sorted(c["matricula_id"] for c in menores) == matriculas
    assert {c["version"] for c in menores} == {VERSION_MENOR}


# --------------------------------------------------------------- la revocacion del consentimiento


@pytest.mark.nfr("NFR-SEG-10")
async def test_la_revocacion_del_consentimiento_cierra_las_autorizaciones_y_deja_la_cuenta(
    cliente: httpx.Client, titular: dict, record_property
):
    """Revocar marca `revocado_en` en cada autorizacion vigente del titular, sin borrar la cuenta;
    revocar otra vez no encuentra nada que revocar."""
    vigentes_antes = await _uno(
        "identidad",
        "select count(*) from consentimiento where usuario_id::text = :u and revocado_en is null",
        u=titular["usuario_id"],
    )
    primera = cliente.post("/v1/cuenta/consentimientos/revocar", headers=titular["cabecera"])
    segunda = cliente.post("/v1/cuenta/consentimientos/revocar", headers=titular["cabecera"])
    vigentes_despues = await _uno(
        "identidad",
        "select count(*) from consentimiento where usuario_id::text = :u and revocado_en is null",
        u=titular["usuario_id"],
    )
    cuenta = cliente.get("/v1/cuenta", headers=titular["cabecera"])
    sesion = cliente.post(
        "/v1/sesiones", headers=titular["ip"], json={"correo": titular["correo"], "clave": titular["clave"]}
    )

    record_property("vigentes_antes", vigentes_antes[0][0])
    record_property("revocados", json.dumps([primera.json(), segunda.json()]))
    assert vigentes_antes[0][0] >= 1, "el registro con acepta_terminos no dejo ningun consentimiento"
    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert primera.json()["revocados"] == vigentes_antes[0][0]
    assert segunda.json()["revocados"] == 0
    assert vigentes_despues[0][0] == 0
    assert cuenta.status_code == 200, cuenta.text
    assert sesion.status_code == 200, sesion.text


# --------------------------------------------------------------- la supresion de punta a punta


def _sembrar_datos(http: httpx.Client, titular: dict[str, Any], producto: dict[str, Any]) -> list[str]:
    """Deja datos del titular en Comercio (la entrega de un pedido) y en Operacion (un caso),
    cada uno con una marca unica; devuelve las marcas que la supresion debe borrar."""
    destinatario, direccion = _marca("Destinalia"), _marca("Calle Privalia ")
    asunto, descripcion = _marca("Asunto privado "), _marca("Mi celular es el de Privalia ")
    orden = crear_orden(
        http,
        titular["usuario_id"],
        producto,
        entrega={"destinatario": destinatario, "direccion": direccion, "ciudad": "Bogota"},
    )
    assert orden.status_code == 201, orden.text
    pagar(http, orden.json()["pedido_id"])
    caso = http.post(
        "/v1/operacion/mis-casos",
        headers=titular["cabecera"],
        json={"categoria": "peticion", "asunto": asunto, "descripcion": descripcion},
    )
    assert caso.status_code == 201, caso.text
    return [destinatario, direccion, asunto, descripcion]


async def _esperar_publicado(solicitud_id: str, espera: float = ESPERA_PROPAGACION) -> list[Any]:
    """Los `titular_suprimido` de la solicitud en la bandeja de Identidad, cuando el publicador
    ya los saco al broker."""
    limite = time.monotonic() + espera
    while True:
        envios = await _uno(
            "identidad",
            "select id, publicado_en, carga, creado_en from bandeja_salida "
            "where tipo = 'titular_suprimido' and agregado_id::text = :s order by id",
            s=solicitud_id,
        )
        if (envios and all(e[1] is not None for e in envios)) or time.monotonic() > limite:
            return envios
        time.sleep(1.0)


@pytest.mark.nfr("NFR-SEG-10")
async def test_con_broker_la_supresion_llega_a_los_tres_servicios_y_queda_completada(
    cliente: httpx.Client, titular: dict, producto: dict, record_property
):
    """ADR 0048: Comercio, Operacion e Inteligencia confirman y la solicitud pasa a `completada`.

    Candidato a hallazgo: Operacion no tiene publicador de su bandeja, asi que su confirmacion
    se queda escrita y sin publicar, y la solicitud no sale de `propagando`. Sin xfail (N-160)."""
    _modo_completo()
    _sembrar_datos(cliente, titular, producto)
    respuesta = _suprimir(cliente, titular)
    solicitud_id = respuesta["solicitud_id"]
    envios = await _esperar_publicado(solicitud_id)
    final = await _esperar_cierre(solicitud_id)
    confirmaciones = await _confirmaciones(solicitud_id)

    record_property("estado_final", final["estado"])
    record_property("confirmados", ",".join(final["confirmados"]) or "0")
    record_property("confirmaciones", json.dumps(confirmaciones, sort_keys=True))
    assert respuesta["estado"] == "propagando"
    assert envios and envios[0][1] is not None, "identidad no publico titular_suprimido"
    assert {s for s, c in confirmaciones.items() if c["escritas"] == 1} == set(SUSCRIPTORES_SUPRESION)
    assert {s for s, c in confirmaciones.items() if c["publicadas"] == 1} == set(SUSCRIPTORES_SUPRESION)
    assert final["confirmados"] == sorted(SUSCRIPTORES_SUPRESION)
    assert final["estado"] == "completada"
    assert final["resuelto_en"] is not None


@pytest.mark.nfr("NFR-SEG-10")
async def test_despues_de_suprimir_no_quedan_datos_personales_del_titular_en_los_servicios(
    cliente: httpx.Client, titular: dict, producto: dict, record_property
):
    """El correo, el apodo del hijo, la entrega del pedido y el texto del caso no quedan en claro en
    ninguna de las cinco bases. Comercio y Operacion dejan la marca en su lugar, y el pedido se
    conserva (Ley 1480 y soportes contables)."""
    _modo_completo()
    marcas = _sembrar_datos(cliente, titular, producto)
    solicitud_id = _suprimir(cliente, titular)["solicitud_id"]
    # Comercio y Operacion borran al consumir, aunque la solicitud no llegue a `completada`.
    limite = time.monotonic() + ESPERA_PROPAGACION
    while True:
        confirmaciones = await _confirmaciones(solicitud_id)
        if all(c["escritas"] for c in confirmaciones.values()) or time.monotonic() > limite:
            break
        time.sleep(1.0)
    apariciones = await _apariciones([titular["correo"], titular["apodo"], *marcas])
    pedidos = await _uno(
        "comercio", "select count(*) from pedido where usuario_id::text = :u", u=titular["usuario_id"]
    )
    marcados = {
        "comercio": await _uno(
            "comercio", "select count(*) from envio where destinatario = :m", m=MARCA_SUPRIMIDO
        ),
        "operacion": await _uno(
            "operacion",
            "select count(*) from caso where usuario_id::text = :u and asunto = :m",
            u=titular["usuario_id"],
            m=MARCA_SUPRIMIDO,
        ),
    }

    record_property("apariciones", ";".join(apariciones) or "0")
    record_property("confirmaciones", json.dumps(confirmaciones, sort_keys=True))
    assert all(c["escritas"] == 1 for c in confirmaciones.values()), confirmaciones
    assert apariciones == []
    assert pedidos[0][0] == 1, "la supresion no debe borrar el pedido: se conserva desvinculado"
    assert marcados["comercio"][0][0] >= 1
    assert marcados["operacion"][0][0] == 1


@pytest.mark.nfr("NFR-SEG-10")
def test_el_titular_suprimido_ya_no_entra_ni_vuelve_a_suprimir(
    cliente: httpx.Client, titular: dict, record_property
):
    """La cuenta queda cerrada: el correo ya no abre sesion y el token viejo ya no sirve, ni para
    leer sus datos ni para pedir otra supresion."""
    _suprimir(cliente, titular)
    sesion = cliente.post(
        "/v1/sesiones", headers=titular["ip"], json={"correo": titular["correo"], "clave": titular["clave"]}
    )
    datos = cliente.get("/v1/cuenta/mis-datos", headers=titular["cabecera"])
    otra = cliente.post("/v1/cuenta/supresion", headers=titular["cabecera"], json={"confirmacion": FRASE})

    record_property("estados", f"{sesion.status_code},{datos.status_code},{otra.status_code}")
    assert sesion.status_code == 401, sesion.text
    assert datos.status_code == 401, datos.text
    assert otra.status_code == 401, otra.text


# --------------------------------------------------------------- CH-35 simplificado y el barrido


async def _esperar_confirmaciones(solicitud_id: str, espera: float = ESPERA_PROPAGACION) -> dict:
    limite = time.monotonic() + espera
    while True:
        confirmaciones = await _confirmaciones(solicitud_id)
        if all(c["escritas"] for c in confirmaciones.values()) or time.monotonic() > limite:
            return confirmaciones
        time.sleep(1.0)


@pytest.mark.nfr("NFR-SEG-10")
async def test_ch35_con_los_consumidores_detenidos_queda_pendiente_y_al_volver_se_completa_una_vez(
    cliente: httpx.Client, titular: dict, record_property
):
    """CH-35 simplificado: los tres consumidores de la supresion se detienen (SIGSTOP), no se
    matan. La solicitud queda en `propagando`, sin confirmaciones y con su evento publicado
    esperando en las colas; al reanudarlos, cada servicio confirma una sola vez y la solicitud
    se cierra. El cierre va a dar rojo mientras Operacion no publique su bandeja (N-160)."""
    _modo_completo()
    with _detenidos(CONSUMIDORES) as pids:
        solicitud_id = _suprimir(cliente, titular)["solicitud_id"]
        envios = await _esperar_publicado(solicitud_id)
        time.sleep(3.0)
        detenida = await _solicitud(solicitud_id)
        sin_confirmar = await _confirmaciones(solicitud_id)
    vuelta = await _esperar_cierre(solicitud_id)
    # Un rato mas, por si algun consumidor recibe el evento dos veces al reconectarse.
    time.sleep(3.0)
    confirmaciones = await _confirmaciones(solicitud_id)

    record_property("detenidos", ",".join(f"{n}={p}" for n, p in pids.items()))
    record_property("estado_detenidos", detenida["estado"])
    record_property("estado_al_volver", vuelta["estado"])
    record_property("confirmaciones", json.dumps(confirmaciones, sort_keys=True))
    assert envios and envios[0][1] is not None, "identidad no publico titular_suprimido"
    assert detenida["estado"] == "propagando"
    assert detenida["confirmados"] == []
    assert all(c["escritas"] == 0 for c in sin_confirmar.values()), sin_confirmar
    assert all(c["escritas"] == 1 for c in confirmaciones.values()), confirmaciones
    assert vuelta["estado"] == "completada"
    assert vuelta["confirmados"] == sorted(SUSCRIPTORES_SUPRESION)


def _barrer_una_vez() -> subprocess.CompletedProcess[str]:
    """Una pasada del barrido, como `make barrido-supresion`: solo lee y escribe Identidad."""
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GEMINI")}
    return subprocess.run(
        [sys.executable, "-m", "tukit_identidad.barrido_supresion"],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.nfr("NFR-SEG-10")
async def test_el_barrido_retoma_una_solicitud_atascada(
    cliente: httpx.Client, titular: dict, record_property
):
    """Con los consumidores detenidos, la solicitud y su envio se envejecen dos horas (el barrido
    reenvia tras una). Una pasada del barrido escribe otro `titular_suprimido` con los tres
    servicios pendientes; al volver, cada servicio recibe dos eventos y confirma una sola vez."""
    _modo_completo()
    with _detenidos(CONSUMIDORES):
        solicitud_id = _suprimir(cliente, titular)["solicitud_id"]
        primeros = await _esperar_publicado(solicitud_id)
        assert len(primeros) == 1 and primeros[0][1] is not None, primeros
        await _uno(
            "identidad",
            "update solicitud_supresion set creado_en = creado_en - interval '2 hours' where id::text = :s",
            s=solicitud_id,
        )
        await _uno(
            "identidad",
            "update bandeja_salida set creado_en = creado_en - interval '2 hours' "
            "where tipo = 'titular_suprimido' and agregado_id::text = :s",
            s=solicitud_id,
        )
        pasada = _barrer_una_vez()
        envios = await _esperar_publicado(solicitud_id)
        atascada = await _solicitud(solicitud_id)
    confirmaciones = await _esperar_confirmaciones(solicitud_id)
    time.sleep(3.0)
    confirmaciones = await _confirmaciones(solicitud_id)

    record_property("barrido_salida", pasada.returncode)
    record_property("envios", len(envios))
    record_property("confirmaciones", json.dumps(confirmaciones, sort_keys=True))
    assert pasada.returncode == 0, pasada.stdout + pasada.stderr
    assert atascada["estado"] == "propagando"
    assert len(envios) == 2, f"el barrido no reenvio: {len(envios)} envio(s)"
    carga = envios[-1][2] if isinstance(envios[-1][2], dict) else json.loads(envios[-1][2])
    assert carga["solicitud_id"] == solicitud_id
    assert carga["usuario_id"] == titular["usuario_id"]
    assert carga["reenvio"] == 1
    assert sorted(carga["pendientes"]) == sorted(SUSCRIPTORES_SUPRESION)
    assert envios[-1][1] is not None, "el reenvio no salio de la bandeja de identidad"
    assert all(c["escritas"] == 1 for c in confirmaciones.values()), confirmaciones
