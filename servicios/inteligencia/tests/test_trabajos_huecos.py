"""NFR-MAN-01: El ciclo del trabajo en sus bordes: fallos, reintento, checkout y lecturas de la consola.

`test_trabajos.py` recorre el camino principal (crear, procesar, revisar, aplicar
el canonico, ordenar con exito). Aqui se fijan las ramas donde el pipeline
decide que hacer cuando algo sale distinto, que es donde un trabajo se queda
colgado o un acudiente paga de mas:

- `procesar` nunca deja un trabajo colgado: un fallo de dependencia es
  `dependencia_caida` y uno inesperado es `error_interno`, los dos `fallido`,
  con diagnostico y reintentables; reprocesar un `fallido` limpia el error;
- `lanzar` solo reencola lo reencolable (un `fallido`); no pisa un `publicado`;
- un texto escolar de edicion cerrada llega al kit como linea sin match, sin
  consolidar y con su enlace, en vez de desaparecer;
- `ordenar` (el checkout) registra el contacto del pago si el trabajo es
  anonimo, no cobra un kit sin nada vendible y reenvia el rechazo de Comercio
  tanto de la orden como del pago;
- `ver` con `incluir_admin` entrega a la consola los ids pendientes y el
  contacto, y `ver` a secas no los entrega;
- los umbrales y fechas auxiliares (`tau`, `_a_consciente`) degradan sin lanzar.

Todo contra el SQLite de la fixture y dobles en memoria de Catalogo, Identidad
y Comercio: ni Postgres ni red.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from sqlalchemy import select
from test_trabajos import COLEGIO, _canonico, _catalogo, _crear_y_procesar
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoResolucion, EstadoTrabajo
from tukit_inteligencia.remoto import RemotoCaido

pytestmark = pytest.mark.nfr("NFR-MAN-01")

ENTREGA = {"destinatario": "Acudiente Ficticio", "direccion": "Calle Ficticia 1", "ciudad": "Bogota"}
CORREO = "acudiente@example.test"


async def _crear(motor, **kw: Any) -> uuid.UUID:
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        **kw,
    )
    return uuid.UUID(respuesta["trabajo_id"])


class ComercioFalso:
    """Comercio en memoria: guarda lo que recibe y responde con lo programado."""

    def __init__(self, orden=(201, None), pago=(201, None)) -> None:
        self.orden = orden
        self.pago = pago
        self.ordenes: list[dict[str, Any]] = []
        self.pagos: list[tuple[str, dict[str, Any]]] = []

    async def crear_orden(self, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        self.ordenes.append(cuerpo)
        estado, respuesta = self.orden
        return estado, respuesta or {"pedido_id": "ped-1", "total": 12345}

    async def iniciar_pago(self, pedido_id: str, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        self.pagos.append((pedido_id, cuerpo))
        estado, respuesta = self.pago
        return estado, respuesta or {
            "pago_id": "pago-1",
            "url_redireccion": "https://pasarela.example.test/p",
        }


class IdentidadFalsa:
    def __init__(self, usuario: str | None) -> None:
        self.usuario = usuario
        self.correos: list[str] = []

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.correos.append(correo)
        return self.usuario


class TestCrearConContacto:
    HIJO = {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}

    async def test_el_contacto_se_registra_en_identidad_y_solo_queda_su_identificador(self, motor):
        usuario = uuid.uuid4()
        identidad = IdentidadFalsa(str(usuario))

        respuesta = await trabajos.crear(
            motor,
            hijos=[self.HIJO],
            contacto={"correo": CORREO, "celular": "3000000000"},
            identidad=identidad,
        )
        vista = await trabajos.ver(motor, uuid.UUID(respuesta["trabajo_id"]), incluir_admin=True)

        assert identidad.correos == [CORREO]
        assert respuesta["degradaciones"] == []
        assert vista["contacto_id"] == str(usuario)
        assert CORREO not in str(vista) and "3000000000" not in str(vista)  # PII fuera del trabajo

    async def test_si_identidad_no_devuelve_usuario_el_trabajo_se_crea_con_la_degradacion_anotada(
        self, motor
    ):
        """Perder el aviso es malo; perder el kit por no poder avisar es peor."""
        respuesta = await trabajos.crear(
            motor, hijos=[self.HIJO], contacto={"correo": CORREO}, identidad=IdentidadFalsa(None)
        )

        assert respuesta["estado"] == EstadoTrabajo.ENCOLADO.value
        assert respuesta["degradaciones"] == [
            {
                "dependencia": "identidad",
                "efecto": "el trabajo corre sin destinatario: no habra aviso al terminar",
                "lineas_afectadas": 0,
            }
        ]
        vista = await trabajos.ver(motor, uuid.UUID(respuesta["trabajo_id"]), incluir_admin=True)
        assert vista["contacto_id"] == ""

    async def test_un_contacto_sin_correo_no_llama_a_identidad(self, motor):
        identidad = IdentidadFalsa(str(uuid.uuid4()))

        respuesta = await trabajos.crear(
            motor, hijos=[self.HIJO], contacto={"celular": "3000000000"}, identidad=identidad
        )

        assert identidad.correos == []
        assert respuesta["degradaciones"] == []

    async def test_un_usuario_ya_identificado_gana_sobre_el_contacto(self, motor):
        """El poller crea el trabajo del padre que ya esta en la tarea: no se le registra de nuevo."""
        usuario = uuid.uuid4()
        identidad = IdentidadFalsa(str(uuid.uuid4()))

        respuesta = await trabajos.crear(
            motor, hijos=[self.HIJO], contacto={"correo": CORREO}, identidad=identidad, usuario_id=usuario
        )
        vista = await trabajos.ver(motor, uuid.UUID(respuesta["trabajo_id"]), incluir_admin=True)

        assert identidad.correos == []
        assert vista["contacto_id"] == str(usuario)


class TestTauYFechas:
    def test_tau_por_omision_es_el_umbral_de_confianza_del_contrato(self, monkeypatch):
        monkeypatch.delenv("TUKIT_TAU", raising=False)

        assert trabajos.tau() == trabajos.TAU_POR_OMISION == 0.75

    def test_tau_se_puede_ajustar_por_entorno_sin_tocar_codigo(self, monkeypatch):
        monkeypatch.setenv("TUKIT_TAU", "0.9")

        assert trabajos.tau() == 0.9

    @pytest.mark.parametrize("basura", ["alto", "", "0,9x"])
    def test_un_tau_ilegible_vuelve_al_valor_por_omision_en_vez_de_tumbar_el_pipeline(
        self, monkeypatch, basura
    ):
        monkeypatch.setenv("TUKIT_TAU", basura)

        assert trabajos.tau() == 0.75

    def test_none_cae_al_final_y_naive_se_vuelve_utc(self):
        """Mezclar fechas naive (SQLite) y aware (Postgres) en un `sort` levanta TypeError."""
        naive = datetime(2026, 3, 1, 10, 0)
        aware = datetime(2026, 3, 1, 10, 0, tzinfo=timezone(timedelta(hours=-5)))

        assert trabajos._a_consciente(None) == datetime.min.replace(tzinfo=UTC)
        assert trabajos._a_consciente(naive) == naive.replace(tzinfo=UTC)
        assert trabajos._a_consciente(aware) == aware  # la zona propia se respeta
        assert trabajos._a_consciente("2026-03-01T10:00:00+00:00") == naive.replace(tzinfo=UTC)
        ordenadas = sorted([aware, naive, None, "2026-01-01T00:00:00"], key=trabajos._a_consciente)
        assert ordenadas[0] is None
        assert ordenadas[1] == "2026-01-01T00:00:00"


class TestProcesarNuncaDejaColgado:
    async def test_un_trabajo_que_no_existe_es_el_unico_error_que_sube(self, motor):
        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.procesar(motor, uuid.uuid4(), catalogo=_catalogo())

    async def test_un_error_inesperado_deja_fallido_con_diagnostico_y_no_procesando(self, motor):
        class CatalogoRoto(CatalogoFalso):
            async def listas(self, **kw: Any) -> Any:
                raise ValueError("el catalogo contesto algo que no es JSON")

        trabajo_id, estado = await _crear_y_procesar(motor, CatalogoRoto())
        vista = await trabajos.ver(motor, trabajo_id)

        assert estado == EstadoTrabajo.FALLIDO.value
        assert vista["estado"] == EstadoTrabajo.FALLIDO.value
        assert vista["error"] == "error_interno"
        assert vista["mensaje"] == "El pipeline fallo: el catalogo contesto algo que no es JSON"
        assert vista["terminado_en"] is not None

    async def test_reprocesar_un_fallido_lo_reencola_y_limpia_el_diagnostico(self, motor):
        """El reintento no arrastra el error viejo: un trabajo recuperado no debe seguir diciendo 'fallo'."""

        class Caido(CatalogoFalso):
            async def listas(self, **kw: Any) -> Any:
                raise RemotoCaido("catalogo", "conexion rechazada")

        trabajo_id, estado = await _crear_y_procesar(motor, Caido())
        assert estado == EstadoTrabajo.FALLIDO.value
        assert (await trabajos.ver(motor, trabajo_id))["error"] == "dependencia_caida"

        reintento = await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert reintento == EstadoTrabajo.ESPERA_REVISION.value
        assert vista["error"] is None and vista["mensaje"] is None
        # Sin preferencias salen Ahorrador y Premium (kits a pedido, ADR 0030).
        assert [kit["perfil"] for kit in vista["kits"]] == ["Ahorrador", "Premium"]

    async def test_la_dependencia_caida_dice_que_servicio_y_que_se_puede_reintentar(self, motor):
        class Caido(CatalogoFalso):
            async def listas(self, **kw: Any) -> Any:
                raise RemotoCaido("catalogo", "circuito abierto")

        trabajo_id, _ = await _crear_y_procesar(motor, Caido())
        vista = await trabajos.ver(motor, trabajo_id)

        assert vista["mensaje"] == (
            "El servicio de catalogo no respondio (circuito abierto). "
            "El trabajo quedo guardado y se puede reintentar."
        )


class TestLanzarSoloReencolaLoReencolable:
    async def _estado(self, motor, trabajo_id: uuid.UUID) -> str:
        return (await trabajos.ver(motor, trabajo_id))["estado"]

    async def test_un_trabajo_recien_creado_ya_esta_encolado_y_no_cambia(self, motor):
        trabajo_id = await _crear(motor)

        await trabajos.lanzar(motor, trabajo_id)

        assert await self._estado(motor, trabajo_id) == EstadoTrabajo.ENCOLADO.value

    async def test_un_fallido_se_reencola_para_el_siguiente_pase_del_trabajador(self, motor):
        class Caido(CatalogoFalso):
            async def listas(self, **kw: Any) -> Any:
                raise RemotoCaido("catalogo", "conexion rechazada")

        trabajo_id, _ = await _crear_y_procesar(motor, Caido())
        assert await self._estado(motor, trabajo_id) == EstadoTrabajo.FALLIDO.value

        await trabajos.lanzar(motor, trabajo_id)

        assert await self._estado(motor, trabajo_id) == EstadoTrabajo.ENCOLADO.value

    async def test_un_trabajo_publicado_no_se_puede_reencolar(self, motor):
        """Reencolar un publicado reprocesaria (y borraria) un kit que el acudiente ya puede ver."""
        trabajo_id, _ = await _crear_y_procesar(motor)
        await trabajos.revisar(motor, trabajo_id, decision="aprobar")

        with pytest.raises(trabajos.TransicionIlegal):
            await trabajos.lanzar(motor, trabajo_id)

        assert await self._estado(motor, trabajo_id) == EstadoTrabajo.PUBLICADO.value


class TestUnTextoEscolar:
    """Un texto escolar nunca se busca en la tienda de utiles, pero tampoco desaparece del kit."""

    @staticmethod
    def _con_espia(catalogo: CatalogoFalso) -> list[str]:
        consultados: list[str] = []
        emparejar = catalogo.emparejar

        # 677f749: el pipeline tambien manda el concepto de la lista (`conceptos=`).
        async def _espia(textos: list[str], **kw: Any) -> list[dict[str, Any]]:
            consultados.extend(textos)
            return await emparejar(textos, **kw)

        catalogo.emparejar = _espia  # type: ignore[method-assign]
        return consultados

    async def test_un_texto_de_mercado_abierto_queda_sin_match_en_vez_de_desaparecer(self, motor):
        """Ocultarlo dejaria al acudiente con un hueco que descubre tarde, ya con el pedido pagado."""
        catalogo = _catalogo()
        catalogo.renglones.append(renglon(5, "Matematicas 4 edicion oficial", tipo_item="texto"))
        consultados = self._con_espia(catalogo)

        trabajo_id, estado = await _crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        assert not any("Matematicas" in texto for texto in consultados)  # no se busco entre los utiles
        for kit in vista["kits"]:
            linea = next(x for x in kit["lineas"] if x["descripcion"].startswith("Matematicas 4"))
            assert linea["tipo"] == "texto"
            assert linea["estado_resolucion"] == EstadoResolucion.SIN_MATCH.value
            assert linea["informativa"] is False  # es papel comprable: solo falta quien resuelva la edicion
            assert linea["unidades_a_comprar"] == 0 and linea["subtotal_linea"] is None
            assert "producto_elegido" not in linea  # no se inventa un producto

    async def test_un_texto_de_edicion_exclusiva_es_informativo_y_no_consolidable_con_su_enlace(self, motor):
        """La edicion cerrada se muestra con su enlace, no se cobra y no se junta entre hermanos."""
        catalogo = _catalogo()
        catalogo.renglones.append(
            renglon(
                5,
                "Matematicas 4 edicion exclusiva",
                tipo_item="texto",
                modo_adquisicion="edicion_exclusiva",
                url_externa="https://editorial.example.test/matematicas-4",
            )
        )
        consultados = self._con_espia(catalogo)

        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert not any("Matematicas" in texto for texto in consultados)
        for kit in vista["kits"]:
            linea = next(x for x in kit["lineas"] if x["descripcion"].startswith("Matematicas 4"))
            assert linea["informativa"] is True
            assert linea["estado_resolucion"] == EstadoResolucion.RESUELTO_AUTO.value
            assert linea["url_externa"] == "https://editorial.example.test/matematicas-4"
            assert linea["no_consolidable"] is True
            assert linea["motivo_no_consolidable"] == "Dos ediciones del mismo titulo no son sustituibles."
            assert linea["unidades_a_comprar"] == 0 and linea["subtotal_linea"] is None

    async def test_una_linea_comun_no_lleva_los_campos_de_texto(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        lineas = vista["kits"][0]["lineas"]
        cuaderno = next(x for x in lineas if x["descripcion"].startswith("2 cuadernos"))
        assert "no_consolidable" not in cuaderno and "url_externa" not in cuaderno


class TestVerParaLaConsola:
    async def test_un_trabajo_inexistente_es_trabajo_no_existe(self, motor):
        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.ver(motor, uuid.uuid4())

    async def test_incluir_admin_entrega_los_ids_pendientes_y_el_contacto(self, motor):
        usuario = uuid.uuid4()
        respuesta = await trabajos.crear(
            motor,
            hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            usuario_id=usuario,
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True, incluir_admin=True)

        assert vista["contacto_id"] == str(usuario)  # el identificador, nunca el correo ni el celular
        assert vista["recibido_en"] == vista["creado_en"]
        # El punzon quedo sin match: es la unica linea que espera a una persona.
        async with motor.engine.begin() as conexion:
            esperado = (
                await conexion.execute(
                    select(trabajos.ITEM.c.id).where(
                        trabajos.ITEM.c.trabajo_id == trabajo_id, trabajos.ITEM.c.orden == 4
                    )
                )
            ).scalar_one()
        assert vista["lineas_pendientes"] == [str(esperado)]

    async def test_un_trabajo_anonimo_tiene_contacto_vacio(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)

        vista = await trabajos.ver(motor, trabajo_id, incluir_admin=True)

        assert vista["contacto_id"] == ""

    async def test_sin_incluir_admin_el_acudiente_no_recibe_esos_campos(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)

        vista = await trabajos.ver(motor, trabajo_id)

        assert not {"contacto_id", "lineas_pendientes", "recibido_en"} & set(vista)


class TestDecidirLinea:
    async def _item_sin_match(self, motor, trabajo_id: uuid.UUID) -> uuid.UUID:
        async with motor.engine.begin() as conexion:
            return (
                await conexion.execute(
                    select(trabajos.ITEM.c.id).where(
                        trabajos.ITEM.c.trabajo_id == trabajo_id, trabajos.ITEM.c.orden == 4
                    )
                )
            ).scalar_one()

    async def test_un_item_que_no_existe_no_se_decide(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)

        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.decidir_linea(
                motor, trabajo_id, uuid.uuid4(), estado=EstadoResolucion.SIN_MATCH.value
            )

    async def test_aceptar_con_sku_elige_ese_candidato_y_deja_quien_decidio(self, motor):
        catalogo = _catalogo()
        catalogo.respuestas["punzon punta metalica de titanio"] = reconocido(
            "punzon punta metalica de titanio",
            "C020",
            [opcion("TK-C020-A", "economico", 3000), opcion("TK-C020-B", "premium", 9000)],
            parecido=0.5,  # por debajo de tau: queda ambiguo y espera a una persona
        )
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)
        item_id = await self._item_sin_match(motor, trabajo_id)
        actor = uuid.uuid4()

        resultado = await trabajos.decidir_linea(
            motor,
            trabajo_id,
            item_id,
            estado=EstadoResolucion.RESUELTO_AUTO.value,
            sku="TK-C020-B",
            actor=actor,
            motivo="el acudiente prefiere el premium",
        )

        assert resultado == {
            "item_id": str(item_id),
            "estado": EstadoResolucion.RESUELTO_AUTO.value,
            "sku": "TK-C020-B",
        }
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(
                        trabajos.RESOLUCION.c.estado,
                        trabajos.RESOLUCION.c.decidido_por,
                        trabajos.RESOLUCION.c.candidato_item_id,
                    ).where(trabajos.RESOLUCION.c.item_crudo_id == item_id)
                )
            ).one()
            sku_elegido = await conexion.scalar(
                select(trabajos.CANDIDATO.c.sku).where(trabajos.CANDIDATO.c.id == fila.candidato_item_id)
            )
            transicion = (
                await conexion.execute(
                    select(
                        trabajos.TRANSICION.c.estado_anterior,
                        trabajos.TRANSICION.c.estado_nuevo,
                        trabajos.TRANSICION.c.motivo,
                        trabajos.TRANSICION.c.decidida_por,
                    )
                )
            ).all()[-1]
        assert fila.estado == EstadoResolucion.RESUELTO_AUTO.value and fila.decidido_por == actor
        assert sku_elegido == "TK-C020-B"
        assert transicion.estado_anterior == EstadoResolucion.AMBIGUO.value
        assert transicion.estado_nuevo == EstadoResolucion.RESUELTO_AUTO.value
        assert transicion.motivo == "el acudiente prefiere el premium"
        assert transicion.decidida_por == actor


class TestCheckout:
    async def test_un_trabajo_inexistente_no_se_cobra(self, motor):
        comercio = ComercioFalso()

        with pytest.raises(trabajos.TrabajoNoExiste):
            await trabajos.ordenar(
                motor,
                uuid.uuid4(),
                perfil="Ahorrador",
                entrega=ENTREGA,
                correo=CORREO,
                comercio=comercio,
                catalogo=_catalogo(),
            )

        assert comercio.ordenes == []

    async def test_un_trabajo_anonimo_registra_el_contacto_del_pago_y_cobra_a_ese_usuario(self, motor):
        """Sin `usuario_id` Comercio no cierra la orden: se registra el correo del pago, no se degrada."""
        trabajo_id, _ = await _crear_y_procesar(motor)
        comercio, usuario = ComercioFalso(), str(uuid.uuid4())
        identidad = IdentidadFalsa(usuario)

        resultado = await trabajos.ordenar(
            motor,
            trabajo_id,
            perfil="Ahorrador",
            entrega=ENTREGA,
            correo=CORREO,
            comercio=comercio,
            catalogo=_catalogo(),
            identidad=identidad,
        )

        assert identidad.correos == [CORREO]
        assert comercio.ordenes[0]["usuario_id"] == usuario
        assert resultado["pedido_id"] == "ped-1" and resultado["url_redireccion"].startswith("https://")

    async def test_si_identidad_no_registra_el_contacto_no_hay_orden(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)
        comercio = ComercioFalso()

        with pytest.raises(RemotoCaido) as info:
            await trabajos.ordenar(
                motor,
                trabajo_id,
                perfil="Ahorrador",
                entrega=ENTREGA,
                correo=CORREO,
                comercio=comercio,
                catalogo=_catalogo(),
                identidad=IdentidadFalsa(None),
            )

        assert info.value.servicio == "identidad"
        assert comercio.ordenes == [] and comercio.pagos == []  # sin destinatario no hay a quien cobrarle

    async def test_un_trabajo_con_usuario_no_vuelve_a_registrar_el_contacto(self, motor):
        usuario = uuid.uuid4()
        trabajo_id = await _crear(motor, usuario_id=usuario)
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())
        identidad = IdentidadFalsa(str(uuid.uuid4()))
        comercio = ComercioFalso()

        # Un trabajo con dueno solo lo paga su dueno (oe5): el portador es el mismo usuario.
        await trabajos.ordenar(
            motor,
            trabajo_id,
            portador=usuario,
            perfil="Ahorrador",
            entrega=ENTREGA,
            correo=CORREO,
            comercio=comercio,
            catalogo=_catalogo(),
            identidad=identidad,
        )

        assert identidad.correos == []
        assert comercio.ordenes[0]["usuario_id"] == str(usuario)

    async def test_la_orden_lleva_solo_lo_comprable_y_el_pago_el_correo_y_el_metodo(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)
        comercio = ComercioFalso()

        await trabajos.ordenar(
            motor,
            trabajo_id,
            perfil="Ahorrador",
            entrega=ENTREGA,
            correo=CORREO,
            comercio=comercio,
            catalogo=_catalogo(),
            identidad=IdentidadFalsa(str(uuid.uuid4())),
            url_redireccion="https://tukit.example.test/gracias",
        )

        orden = comercio.ordenes[0]
        # El punzon (sin match) y la licencia digital (informativa) no se cobran.
        assert sorted(linea["sku"] for linea in orden["lineas"]) == ["TK-C001-ECO", "TK-C004-CON"]
        assert orden["hijos"] == 1 and orden["colegios"] == [COLEGIO]
        assert orden["entrega"] == ENTREGA
        assert orden["trabajo_id"] == str(trabajo_id)
        assert all(
            set(linea) == {"sku", "nombre", "cantidad", "precio_unitario"} for linea in orden["lineas"]
        )
        pedido_id, pago = comercio.pagos[0]
        assert pedido_id == "ped-1"
        assert pago == {
            "correo_cliente": CORREO,
            "metodo": "pse",  # el metodo por omision
            "url_redireccion": "https://tukit.example.test/gracias",
        }

    async def test_un_perfil_que_no_existe_es_trabajo_no_existe(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)
        comercio = ComercioFalso()

        with pytest.raises(trabajos.TrabajoNoExiste, match="Inventado"):
            await trabajos.ordenar(
                motor,
                trabajo_id,
                perfil="Inventado",
                entrega=ENTREGA,
                correo=CORREO,
                comercio=comercio,
                catalogo=_catalogo(),
                identidad=IdentidadFalsa(str(uuid.uuid4())),
            )

        assert comercio.ordenes == []

    async def test_un_kit_sin_nada_vendible_se_rechaza_con_409_antes_de_llamar_a_comercio(self, motor):
        """Distinto del 404: el kit existe, pero ninguna linea tiene producto y precio que Tukit cobre."""
        solo_licencia = CatalogoFalso(
            renglones=[
                renglon(
                    1,
                    "Plan lector virtual RAZ-PLUS",
                    tipo_item="licencia_digital",
                    modo_adquisicion="plataforma",
                    instruccion_colegio="Se adquiere con QUOVIX.",
                )
            ]
        )
        trabajo_id, estado = await _crear_y_procesar(motor, solo_licencia)
        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        comercio = ComercioFalso()

        with pytest.raises(trabajos.CheckoutRechazado) as info:
            await trabajos.ordenar(
                motor,
                trabajo_id,
                perfil="Ahorrador",
                entrega=ENTREGA,
                correo=CORREO,
                comercio=comercio,
                catalogo=solo_licencia,
                identidad=IdentidadFalsa(str(uuid.uuid4())),
            )

        assert info.value.estado == 409
        assert info.value.cuerpo["error"] == "kit_sin_lineas"
        assert comercio.ordenes == []

    async def test_si_el_pago_se_rechaza_se_reenvia_su_estado_y_cuerpo(self, motor):
        trabajo_id, _ = await _crear_y_procesar(motor)
        comercio = ComercioFalso(
            pago=(422, {"error": "metodo_no_disponible", "mensaje": "PSE no disponible"})
        )

        with pytest.raises(trabajos.CheckoutRechazado) as info:
            await trabajos.ordenar(
                motor,
                trabajo_id,
                perfil="Ahorrador",
                entrega=ENTREGA,
                correo=CORREO,
                comercio=comercio,
                catalogo=_catalogo(),
                identidad=IdentidadFalsa(str(uuid.uuid4())),
            )

        assert info.value.estado == 422
        assert info.value.cuerpo["error"] == "metodo_no_disponible"
        assert str(info.value) == "metodo_no_disponible"
        assert len(comercio.ordenes) == 1  # la orden se creo; el rechazo es del pago


class TestCanonicoYSelector:
    """El canonico nace de la LISTA aprobada (`origen=ORIGEN_CANONICO`), no de aprobar el trabajo
    de un papa: aprobar ese ya no deja `kit_canonico`. Se usa `_canonico` de `test_trabajos`."""

    async def test_aplicar_un_perfil_que_el_canonico_no_tiene_es_trabajo_no_existe(self, motor):
        await _canonico(motor)

        with pytest.raises(trabajos.TrabajoNoExiste, match="Inexistente"):
            await trabajos.aplicar_canonico(
                motor,
                colegio_id=COLEGIO,
                grado="Cuarto",
                anio_lectivo=2026,
                perfil="Inexistente",
                catalogo=_catalogo(),
            )

    async def test_el_selector_lista_los_grados_con_cache_y_filtra_por_colegio(self, motor):
        canonico = await _canonico(motor)

        todos = await trabajos.grados_canonicos(motor)
        del_colegio = await trabajos.grados_canonicos(motor, colegio_id=COLEGIO)
        de_otro = await trabajos.grados_canonicos(motor, colegio_id=str(uuid.uuid4()))

        async with motor.engine.begin() as conexion:
            publicado_en = await conexion.scalar(
                select(trabajos.TRABAJO.c.terminado_en).where(trabajos.TRABAJO.c.id == canonico)
            )
        # edd9877 agrega cuando se publico y el borrador abierto (ninguno: nadie lo esta editando).
        esperado = [
            {
                "colegio_id": COLEGIO,
                "grado": "Cuarto",
                "anio_lectivo": 2026,
                "trabajo_id": str(canonico),
                "publicado_en": publicado_en.isoformat(),
                "borrador_trabajo_id": None,
            }
        ]
        assert todos == esperado
        assert del_colegio == esperado
        assert de_otro == []

    async def test_sin_ninguna_cache_el_selector_esta_vacio(self, motor):
        assert await trabajos.grados_canonicos(motor) == []


class TestPreviews:
    async def test_un_preview_sin_hijo_se_ignora_y_el_que_cuadra_se_devuelve(self, motor):
        """Un `hijos` vacio no debe tumbar la busqueda de previews desechables."""
        valido = uuid.UUID(
            (
                await trabajos.crear(
                    motor,
                    hijos=[
                        {"referencia": "h", "colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}
                    ],
                    origen="preview_onboarding",
                )
            )["trabajo_id"]
        )
        await trabajos.crear(motor, hijos=[], origen="preview_onboarding")

        encontrados = await trabajos.previews_de(motor, COLEGIO, "Cuarto", 2026)

        assert encontrados == [valido]
