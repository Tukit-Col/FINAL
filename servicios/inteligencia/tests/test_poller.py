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

from conftest import CatalogoFalso  # noqa: F401  (reexport para claridad)
from sqlalchemy import MetaData, insert, select
from test_fastroute import COLEGIO, _catalogo_verificado
from tukit_comun.bandeja import bandeja_reflejada
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoTrabajo
from tukit_inteligencia.poller import Poller

# La bandeja del Catalogo, aqui montada sobre el MISMO SQLite de prueba: tiene
# la forma comun de bandeja (identica en todos los servicios), asi que la tabla
# reflejada del poller la lee igual que en produccion.
BANDEJA_CATALOGO = bandeja_reflejada(MetaData())


class _CatalogoNoIdentidad:
    """Guarda si alguien intento registrar un contacto. Nunca deberia pasar:
    el poller crea el trabajo con el `usuario_id` que ya venia en el evento."""

    def __init__(self) -> None:
        self.registros: list[Any] = []

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.registros.append((correo, celular))
        return str(uuid.uuid4())


async def _sembrar_bandeja(motor, *, agregado_id: uuid.UUID | None = None, **carga: Any) -> uuid.UUID:
    """Crea la tabla de bandeja del catalogo en el SQLite de prueba y le mete
    un evento `lista_verificada` con la carga dada. Devuelve el `agregado_id`
    (el `version_id` de la version aprobada) para poder aseverarlo."""
    agregado_id = agregado_id or uuid.uuid4()
    async with motor.engine.begin() as conexion:
        await conexion.run_sync(BANDEJA_CATALOGO.metadata.create_all)
        await conexion.execute(
            insert(BANDEJA_CATALOGO).values(
                tipo="lista_verificada",
                agregado_tipo="version_lista_oficial",
                agregado_id=agregado_id,
                carga=carga,
                intentos=0,
            )
        )
    return agregado_id


def _carga(
    contacto: str, preferencias: dict | None = None, referencias: list[str] | None = None
) -> dict[str, Any]:
    carga: dict[str, Any] = {
        "contacto_referencia": contacto,
        "colegio_id": COLEGIO,
        "grado": "Cuarto",
        "anio_lectivo": 2026,
        "preferencias": preferencias,
    }
    if referencias is not None:
        carga["referencias"] = referencias
    return carga


class TestPollerArmaElKitDelPadre:
    async def test_un_evento_arma_un_trabajo_dirigido_por_ruta_rapida(self, motor, monkeypatch):
        # Identidad NO se debe tocar: el poller ya tiene el usuario del evento.
        identidad = _CatalogoNoIdentidad()
        monkeypatch.setattr(trabajos, "ClienteIdentidad", lambda *a, **k: identidad)

        contacto = str(uuid.uuid4())
        await _sembrar_bandeja(motor, **_carga(contacto))
        catalogo = _catalogo_verificado()

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
        await _sembrar_bandeja(motor, agregado_id=version_id, **_carga(str(uuid.uuid4())))
        catalogo = _catalogo_verificado()

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
        await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4()), preferencias))
        catalogo = _catalogo_verificado()

        poller = Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=catalogo)
        assert await poller.pasada() == 1

        # Las preferencias se guardan cifradas; se leen con el mismo cifrador.
        from tukit_inteligencia.trabajos import cifrador_desde_entorno

        async with motor.engine.begin() as conexion:
            cifradas = (await conexion.execute(select(trabajos.TRABAJO.c.preferencias_cifradas))).scalar_one()
        guardadas = cifrador_desde_entorno().descifrar_json(cifradas)
        assert guardadas == preferencias

    async def test_al_terminar_deja_kits_publicados_en_la_bandeja_propia(self, motor):
        await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4())))
        catalogo = _catalogo_verificado()

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
        await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4())))
        catalogo = _catalogo_verificado()
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
        await _sembrar_bandeja(
            motor, contacto_referencia=None, colegio_id=COLEGIO, grado="Cuarto", anio_lectivo=2026
        )
        catalogo = _catalogo_verificado()
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
        await _sembrar_bandeja(motor, **_carga("no-es-un-uuid"))
        catalogo = _catalogo_verificado()
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
        await _sembrar_bandeja(motor, **carga)
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
        from test_fastroute import _catalogo_realista

        prefs = {"personaje_por_hijo": {"hijo-2": ["spiderman"]}, "pesos": {"personaje": 1}}
        carga = _carga(str(uuid.uuid4()), prefs, referencias=["hijo-2"])
        assert await self._fan(motor, _catalogo_realista(), carga) == {("hijo-2", "spiderman")}

    async def test_con_dos_hermanos_cada_lista_lleva_solo_su_personaje(self, motor):
        from test_fastroute import CatalogoDosPersonajes, _catalogo_verificado

        base = _catalogo_verificado(personaje=None)
        catalogo = CatalogoDosPersonajes(revisada=True, items_resueltos=base.items_resueltos)
        prefs = {
            "personaje_por_hijo": {"hijo-1": ["spiderman"], "hijo-2": ["frozen"]},
            "pesos": {"personaje": 1},
        }
        carga = _carga(str(uuid.uuid4()), prefs, referencias=["hijo-2"])
        assert await self._fan(motor, catalogo, carga) == {("hijo-2", "frozen")}

    async def test_un_evento_viejo_sin_referencias_cae_en_hijo_1(self, motor):
        await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4())))
        poller = Poller(
            motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=_catalogo_verificado()
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
        await _sembrar_bandeja(motor, agregado_id=version_id, **_carga(contacto, referencias=["hijo-2"]))
        poller = Poller(
            motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=_catalogo_verificado()
        )
        assert await poller.pasada() == 1
        async with motor.engine.begin() as conexion:
            hijos = (await conexion.execute(select(trabajos.TRABAJO.c.hijos))).scalar_one()
        assert hijos[0]["referencia"] == "hijo-2"
        assert hijos[0]["apodo"] == "Luca"
        # Ya copiado al trabajo, no se guarda dos veces.
        assert await apodos_subida.apodos_de(motor, str(version_id)) == {}

    async def test_sin_apodo_guardado_el_trabajo_no_lleva_la_clave(self, motor):
        await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4()), referencias=["hijo-1"]))
        poller = Poller(
            motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=_catalogo_verificado()
        )
        assert await poller.pasada() == 1
        async with motor.engine.begin() as conexion:
            hijos = (await conexion.execute(select(trabajos.TRABAJO.c.hijos))).scalar_one()
        assert "apodo" not in hijos[0]
