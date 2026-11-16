"""El poller de `lista_verificada`: aprobar la lista de un padre arma su kit.

Cuando un administrador aprueba una version que un acudiente habia subido, el
Catalogo escribe `lista_verificada` en su bandeja (nunca llama a Inteligencia:
eso cerraria un ciclo). Este poller la drena y crea el trabajo de RUTA RAPIDA
del padre con las preferencias que dejo, sin volver a pasar por Identidad.

Lo que se fija aqui:

- Un evento arma un trabajo dirigido al padre (`usuario_id` = su
  `contacto_referencia`), sin llamar a Identidad, y lo procesa por la ruta
  rapida (llama `resueltos`, nunca `emparejar`).
- El trabajo lleva las preferencias del evento.
- El evento se marca publicado: una segunda pasada no arma un segundo kit.
- Un evento de onboarding (sin `contacto_referencia`) o mal formado no arma
  nada, pero se marca publicado para no reintentarlo en vano.
- Al terminar, el pipeline deja `kits_publicados` en la bandeja propia para que
  el repartidor avise al padre.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from _ayudas_inteligencia import (
    BANDEJA_CATALOGO,
    COLEGIO,
    INTERVALO_BUCLE,
    CorteDelBucle,
    EngineIntermitente,
    caidas_de_postgres,
    carga_lista_verificada,
    catalogo_verificado,
    dormir_que_corta,
    sembrar_bandeja,
)
from conftest import CatalogoFalso  # noqa: F401  (reexport para claridad)
from sqlalchemy import func, select
from tukit_comun.bandeja import Resultado
from tukit_comun.consumidor import Consumidor, Decision, RegistroEnTabla
from tukit_comun.mensajes import Evento, cuerpo
from tukit_inteligencia import poller, trabajos
from tukit_inteligencia import poller as modulo
from tukit_inteligencia.modelos import EstadoTrabajo, EventoProcesado
from tukit_inteligencia.poller import Poller


class _CatalogoNoIdentidad:
    """Guarda si alguien intento registrar un contacto. Nunca deberia pasar:
    el poller crea el trabajo con el `usuario_id` que ya venia en el evento."""

    def __init__(self) -> None:
        self.registros: list[Any] = []

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.registros.append((correo, celular))
        return str(uuid.uuid4())


class TestPollerArmaElKitDelPadre:
    async def test_un_evento_arma_un_trabajo_dirigido_por_ruta_rapida(self, motor, monkeypatch):
        # Identidad NO se debe tocar: el poller ya tiene el usuario del evento.
        identidad = _CatalogoNoIdentidad()
        monkeypatch.setattr(trabajos, "ClienteIdentidad", lambda *a, **k: identidad)

        contacto = str(uuid.uuid4())
        await sembrar_bandeja(motor, **carga_lista_verificada(contacto))
        catalogo = catalogo_verificado()

        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)
        arrancados = await poller.pasada()

        assert arrancados == 1
        assert identidad.registros == []  # jamas re-registro el contacto
        assert "resueltos" in catalogo.llamadas
        assert "emparejar" not in catalogo.llamadas

        # El trabajo quedo dirigido al padre y en el estado de la ruta rapida.
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(
                        trabajos.TRABAJO.c.usuario_id,
                        trabajos.TRABAJO.c.estado,
                        trabajos.TRABAJO.c.origen,
                    )
                )
            ).one()
        assert str(fila.usuario_id) == contacto
        # La lista ya la aprobo un admin: el kit se publica directo (el padre lo
        # revisa desde el enlace del correo), no entra a una segunda cola.
        assert fila.estado == EstadoTrabajo.PUBLICADO.value
        assert fila.origen == "lista_verificada"

    async def test_el_trabajo_guarda_el_version_id_de_la_lista(self, motor):
        # El `agregado_id` del evento (el version_id de la version aprobada) queda
        # en `hijos[0]`: es la bisagra que deja unir la lista aprobada con su
        # trabajo en "Mis solicitudes".
        version_id = uuid.uuid4()
        await sembrar_bandeja(motor, agregado_id=version_id, **carga_lista_verificada(str(uuid.uuid4())))
        catalogo = catalogo_verificado()

        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)
        assert await poller.pasada() == 1

        async with motor.engine.begin() as conexion:
            hijos = (await conexion.execute(select(trabajos.TRABAJO.c.hijos))).scalar_one()
        assert hijos[0]["version_id"] == str(version_id)

    async def test_el_trabajo_lleva_las_preferencias_del_evento(self, motor):
        preferencias = {
            "pesos": {"precio": 0.6, "marca_exigida": 0.15, "calidad": 0.2, "personaje": 0.05},
            "disposicion_sobreprecio": 0.05,
        }
        await sembrar_bandeja(motor, **carga_lista_verificada(str(uuid.uuid4()), preferencias))
        catalogo = catalogo_verificado()

        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)
        assert await poller.pasada() == 1

        # Las preferencias se guardan cifradas; se leen con el mismo cifrador.
        from tukit_inteligencia.trabajos import cifrador_desde_entorno

        async with motor.engine.begin() as conexion:
            cifradas = (await conexion.execute(select(trabajos.TRABAJO.c.preferencias_cifradas))).scalar_one()
        guardadas = cifrador_desde_entorno().descifrar_json(cifradas)
        assert guardadas == preferencias

    async def test_al_terminar_deja_kits_publicados_en_la_bandeja_propia(self, motor):
        await sembrar_bandeja(motor, **carga_lista_verificada(str(uuid.uuid4())))
        catalogo = catalogo_verificado()

        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)
        await poller.pasada()

        async with motor.engine.begin() as conexion:
            eventos = list(
                await conexion.execute(
                    select(trabajos.BANDEJA.c.tipo).where(trabajos.BANDEJA.c.tipo == "kits_publicados")
                )
            )
        assert len(eventos) == 1

    async def test_una_segunda_pasada_no_arma_un_segundo_kit(self, motor):
        await sembrar_bandeja(motor, **carga_lista_verificada(str(uuid.uuid4())))
        catalogo = catalogo_verificado()
        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)

        assert await poller.pasada() == 1
        assert await poller.pasada() == 0  # ya publicado: nada que hacer

        async with motor.engine.begin() as conexion:
            trabajos_creados = list(await conexion.execute(select(trabajos.TRABAJO.c.id)))
        assert len(trabajos_creados) == 1


class TestPollerConColegioSinPadre:
    async def test_un_evento_sin_contacto_arma_un_kit_de_colegio_para_revision(self, motor):
        # Onboarding del colegio: sin padre esperando. Ya NO se descarta: arma un
        # trabajo `colegio_grado` (anonimo) que entra a la cola de revision, para
        # que al aprobarlo ahi quede como kit canonico del grado.
        await sembrar_bandeja(
            motor, contacto_referencia=None, colegio_id=COLEGIO, grado="Cuarto", anio_lectivo=2026
        )
        catalogo = catalogo_verificado()
        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)

        assert await poller.pasada() == 1
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(
                        trabajos.TRABAJO.c.usuario_id,
                        trabajos.TRABAJO.c.estado,
                        trabajos.TRABAJO.c.origen,
                    )
                )
            ).one()
            pendientes = list(
                await conexion.execute(
                    select(BANDEJA_CATALOGO.c.id).where(BANDEJA_CATALOGO.c.publicado_en.is_(None))
                )
            )
        # Anonimo, origen de colegio, y en espera de revision (no publicado
        # directo: no hay padre a quien avisar, la persona lo aprueba en la cola).
        assert fila.usuario_id is None
        assert fila.origen == "colegio_grado"
        assert fila.estado == EstadoTrabajo.ESPERA_REVISION.value
        assert pendientes == []  # se marco publicado

    async def test_un_contacto_que_no_es_uuid_se_degrada_a_kit_de_colegio(self, motor):
        # Un contacto ilegible no arma un kit DIRIGIDO (perderiamos a quien
        # avisar), pero tampoco se descarta el evento: se degrada a kit de
        # colegio para revision. Perder el kit del grado es peor que perder el
        # aviso a un contacto que de todas formas no se puede resolver.
        await sembrar_bandeja(motor, **carga_lista_verificada("no-es-un-uuid"))
        catalogo = catalogo_verificado()
        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)

        assert await poller.pasada() == 1
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(select(trabajos.TRABAJO.c.usuario_id, trabajos.TRABAJO.c.origen))
            ).one()
        assert fila.usuario_id is None
        assert fila.origen == "colegio_grado"


class TestPollerUsaLaReferenciaRealDelHijo:
    """El kit lleva la referencia del hijo que subio la lista, no un `hijo-1` fijo.

    `personaje_por_hijo` esta indexado por esa referencia; con la fija, el hijo
    2 que sube su lista salia neutral (su clave no casaba) o, con dos hermanos
    con personaje, recibia el del hijo 1.
    """

    async def _fan(self, motor, catalogo, carga) -> set[tuple[str, str | None]]:
        await sembrar_bandeja(motor, **carga)
        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)
        assert await poller.pasada() == 1
        async with motor.engine.begin() as conexion:
            tid = (await conexion.execute(select(trabajos.TRABAJO.c.id))).scalar_one()
        vista = await trabajos.ver(motor, tid, incluir_kits=True)
        fan = next(k for k in vista["kits"] if k["perfil"] == "Fan")
        return {
            (li["hijo"], (li.get("producto_elegido") or {}).get("personaje"))
            for li in fan["lineas"]
            if li.get("concepto") in {"C001", "C009"}
        }

    async def test_el_hijo_2_que_sube_su_lista_recibe_su_personaje(self, motor):
        from _ayudas_inteligencia import catalogo_realista

        prefs = {"personaje_por_hijo": {"hijo-2": ["spiderman"]}, "pesos": {"personaje": 1}}
        carga = carga_lista_verificada(str(uuid.uuid4()), prefs, referencias=["hijo-2"])
        assert await self._fan(motor, catalogo_realista(), carga) == {("hijo-2", "spiderman")}

    async def test_con_dos_hermanos_cada_lista_lleva_solo_su_personaje(self, motor):
        from _ayudas_inteligencia import CatalogoDosPersonajes, catalogo_verificado

        base = catalogo_verificado(personaje=None)
        catalogo = CatalogoDosPersonajes(revisada=True, items_resueltos=base.items_resueltos)
        prefs = {
            "personaje_por_hijo": {"hijo-1": ["spiderman"], "hijo-2": ["frozen"]},
            "pesos": {"personaje": 1},
        }
        carga = carga_lista_verificada(str(uuid.uuid4()), prefs, referencias=["hijo-2"])
        assert await self._fan(motor, catalogo, carga) == {("hijo-2", "frozen")}

    async def test_un_evento_viejo_sin_referencias_cae_en_hijo_1(self, motor):
        await sembrar_bandeja(motor, **carga_lista_verificada(str(uuid.uuid4())))
        poller = Poller(
            motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo_verificado()
        )
        assert await poller.pasada() == 1
        async with motor.engine.begin() as conexion:
            hijos = (await conexion.execute(select(trabajos.TRABAJO.c.hijos))).scalar_one()
        assert hijos[0]["referencia"] == "hijo-1"


class TestPollerLlevaElApodo:
    async def test_el_trabajo_de_la_lista_aprobada_lleva_el_apodo_del_hijo(self, motor):
        from tukit_inteligencia import apodos_subida

        version_id = uuid.uuid4()
        contacto = str(uuid.uuid4())
        await apodos_subida.guardar(motor, str(version_id), contacto, {"hijo-2": "Luca"})
        carga = carga_lista_verificada(contacto, referencias=["hijo-2"])
        await sembrar_bandeja(motor, agregado_id=version_id, **carga)
        poller = Poller(
            motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo_verificado()
        )
        assert await poller.pasada() == 1
        async with motor.engine.begin() as conexion:
            hijos = (await conexion.execute(select(trabajos.TRABAJO.c.hijos))).scalar_one()
        assert hijos[0]["referencia"] == "hijo-2"
        assert hijos[0]["apodo"] == "Luca"
        # Ya copiado al trabajo, no se guarda dos veces.
        assert await apodos_subida.apodos_de(motor, str(version_id)) == {}

    async def test_sin_apodo_guardado_el_trabajo_no_lleva_la_clave(self, motor):
        await sembrar_bandeja(motor, **carga_lista_verificada(str(uuid.uuid4()), referencias=["hijo-1"]))
        poller = Poller(
            motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo_verificado()
        )
        assert await poller.pasada() == 1
        async with motor.engine.begin() as conexion:
            hijos = (await conexion.execute(select(trabajos.TRABAJO.c.hijos))).scalar_one()
        assert "apodo" not in hijos[0]


# --- Vuelve solo tras una caida de Postgres (H-B-02, ADR 0041) ------------------------------------


class TestElPollerVuelve:
    async def test_tras_una_caida_de_postgres_arma_el_kit(self, motor):
        contacto = str(uuid.uuid4())
        await sembrar_bandeja(motor, **carga_lista_verificada(contacto))
        # Cada pasada lee la bandeja del Catalogo con el mismo motor, que falla
        # tres veces y despues responde.
        catalogo = EngineIntermitente(motor.engine, *caidas_de_postgres())
        esperas: list[float] = []

        with pytest.raises(CorteDelBucle):
            await poller.correr_en_bucle(
                INTERVALO_BUCLE,
                dormir=dormir_que_corta(esperas),
                motor_inteligencia=motor,
                motor_catalogo=catalogo,
                catalogo=catalogo_verificado(),
            )

        assert esperas == [1.0, 2.0, 4.0, INTERVALO_BUCLE]
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(select(trabajos.TRABAJO.c.usuario_id, trabajos.TRABAJO.c.estado))
            ).one()
        assert (str(fila.usuario_id), fila.estado) == (contacto, EstadoTrabajo.PUBLICADO.value)

    async def test_un_error_de_programacion_lo_sigue_terminando(self, motor):
        await sembrar_bandeja(motor, **carga_lista_verificada(str(uuid.uuid4())))
        esperas: list[float] = []

        with pytest.raises(ValueError):
            await poller.correr_en_bucle(
                INTERVALO_BUCLE,
                dormir=dormir_que_corta(esperas),
                motor_inteligencia=motor,
                motor_catalogo=EngineIntermitente(motor.engine, ValueError("bug")),
                catalogo=catalogo_verificado(),
            )

        assert esperas == []


# --- Con RabbitMQ: consume inteligencia.listas (ADR 0046) -----------------------------------------


VERSION = uuid.UUID("22222222-3333-4444-5555-666666666666")


def _evento(id_: int = 1, tipo: str = "lista_verificada", **carga: Any) -> Evento:
    return Evento(
        id=id_,
        origen="catalogo",
        tipo=tipo,
        agregado_tipo="version_lista_oficial",
        agregado_id=VERSION,
        carga={"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026, **carga},
    )


class _Mensaje:
    def __init__(self, evento: Evento) -> None:
        self.body = cuerpo(evento)
        self.headers: dict[str, Any] = {}
        self.acks = 0

    async def ack(self) -> None:
        self.acks += 1


async def _cuantos(motor, tabla) -> int:
    async with motor.engine.begin() as conexion:
        return await conexion.scalar(select(func.count()).select_from(tabla))


def _poller(motor, catalogo=None) -> Poller:
    return Poller(motor_inteligencia=motor, motor_catalogo=None, catalogo=catalogo or catalogo_verificado())


async def test_un_evento_de_la_cola_arma_el_kit_del_padre(motor):
    contacto = str(uuid.uuid4())

    assert await _poller(motor).manejar(_evento(contacto_referencia=contacto)) is Resultado.HECHO

    async with motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(trabajos.TRABAJO.c.usuario_id, trabajos.TRABAJO.c.estado, trabajos.TRABAJO.c.hijos)
            )
        ).one()
        avisos = await conexion.scalar(
            select(func.count()).where(trabajos.BANDEJA.c.tipo == "kits_publicados")
        )
    assert str(fila.usuario_id) == contacto
    assert fila.estado == EstadoTrabajo.PUBLICADO.value
    assert fila.hijos[0]["version_id"] == str(VERSION)
    assert avisos == 1
    assert await _cuantos(motor, EventoProcesado) == 1


async def test_un_evento_repetido_no_arma_un_segundo_kit(motor):
    consumidor = Consumidor(
        cola=modulo.LISTAS, manejar=_poller(motor).manejar, registro=RegistroEnTabla(motor.engine)
    )
    evento = _evento(5, contacto_referencia=str(uuid.uuid4()))
    primero, segundo = _Mensaje(evento), _Mensaje(evento)

    assert await consumidor.procesar(primero) is Decision.HECHO
    assert await consumidor.procesar(segundo) is Decision.DUPLICADO

    assert (primero.acks, segundo.acks) == (1, 1)
    assert await _cuantos(motor, trabajos.TRABAJO) == 1
    assert await _cuantos(motor, EventoProcesado) == 1


async def test_dos_entregas_que_llegan_a_crear_arman_un_solo_kit(motor):
    # El proceso cayo despues de crear el trabajo y antes de confirmar: la
    # segunda entrega no paso por el registro del consumidor, pero `crear` ve la
    # marca que dejo la primera en su misma transaccion.
    poller = _poller(motor)
    evento = _evento(6, contacto_referencia=str(uuid.uuid4()))

    assert await poller.manejar(evento) is Resultado.HECHO
    assert await poller.manejar(evento) is Resultado.OMITIR

    assert await _cuantos(motor, trabajos.TRABAJO) == 1


async def test_si_crear_falla_la_marca_vuelve_atras(motor, monkeypatch):
    poller = _poller(motor)
    evento = _evento(8, contacto_referencia=str(uuid.uuid4()))
    etapas = trabajos.ETAPAS
    # Una etapa sin nombre viola el NOT NULL despues de la marca y del trabajo.
    monkeypatch.setattr(trabajos, "ETAPAS", (None,))

    with pytest.raises(Exception, match="NOT NULL"):
        await poller.manejar(evento)
    assert await _cuantos(motor, EventoProcesado) == 0
    assert await _cuantos(motor, trabajos.TRABAJO) == 0

    monkeypatch.setattr(trabajos, "ETAPAS", etapas)
    assert await poller.manejar(evento) is Resultado.HECHO
    assert await _cuantos(motor, trabajos.TRABAJO) == 1


async def test_un_lista_aprobada_arma_los_canonicos_y_repetido_no_reoptimiza(motor):
    poller = _poller(motor)
    evento = _evento(9, tipo="lista_aprobada")

    assert await poller.manejar(evento) is Resultado.HECHO
    async with motor.engine.begin() as conexion:
        origen = await conexion.scalar(select(trabajos.TRABAJO.c.origen))
    assert origen == trabajos.ORIGEN_CANONICO

    catalogo = catalogo_verificado()
    assert await _poller(motor, catalogo).manejar(evento) is Resultado.OMITIR
    assert "resueltos" not in catalogo.llamadas
    assert await _cuantos(motor, trabajos.TRABAJO) == 1


async def test_otro_tipo_se_omite(motor):
    assert await _poller(motor).manejar(_evento(10, tipo="colegio_verificado")) is Resultado.OMITIR
    assert await _cuantos(motor, trabajos.TRABAJO) == 0


async def test_sin_la_bandeja_del_catalogo_no_hay_pasada(motor):
    with pytest.raises(ValueError):
        await _poller(motor).pasada()


async def test_sin_broker_crear_no_anota_nada(motor):
    await trabajos.crear(motor, hijos=[{"referencia": "hijo-1"}], origen="colegio_grado", en_proceso=True)
    assert await _cuantos(motor, EventoProcesado) == 0


class _MotorFalso:
    engine = object()

    def __init__(self) -> None:
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


def test_con_rabbitmq_url_main_consume_la_cola_y_no_abre_el_catalogo(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@broker:5672/")
    motor_falso = _MotorFalso()
    llamadas: list[dict[str, Any]] = []

    async def consumir(url, consumidor, **opciones):
        llamadas.append({"url": url, "consumidor": consumidor, **opciones})
        return 0

    def _sin_catalogo(servicio):  # pragma: no cover - no debe llamarse
        raise AssertionError(f"abrio la base de {servicio}")

    monkeypatch.setattr(modulo, "crear_motor", lambda servicio: motor_falso)
    monkeypatch.setattr(modulo, "_motor_lectura", _sin_catalogo)
    monkeypatch.setattr(modulo, "consumir", consumir)

    assert modulo.main([]) == 0

    [llamada] = llamadas
    consumidor = llamada["consumidor"]
    assert (consumidor.cola.nombre, llamada["seguir"]) == ("inteligencia.listas", False)
    assert isinstance(consumidor.registro, RegistroEnTabla)
    assert consumidor.registro.motor is motor_falso.engine
    assert llamada["proceso"] == "inteligencia-poller"
    assert motor_falso.cerrado
