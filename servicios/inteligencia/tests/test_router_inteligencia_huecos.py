"""NFR-MAN-01: La puerta HTTP de Inteligencia: codigos y sobres de error, y quien puede entrar a que.

`test_api_inteligencia.py` y sus hermanos recorren el camino feliz de cada
recurso. Aqui se fijan los bordes del router, que es lo que el frontend lee y lo
que decide quien puede tocar el kit de un hogar:

- cada rechazo de dominio sale con el codigo HTTP y el `error` del contrato
  (404 `trabajo_no_existe`, 409 `estado_incompatible`, 422 `hijos_invalidos`...),
  y el sobre nunca devuelve lo que el cliente envio;
- el checkout reenvia el rechazo de Comercio verbatim y cae a 503 si Comercio no
  responde, en vez de un 500 generico;
- una subida mal formada (sin multipart, sin hijos, sin archivo, JSON roto) se
  rechaza ANTES de percibir nada ni tocar Identidad o el catalogo;
- la revision humana (validar, fijar producto, sin coincidencia, aprobar,
  devolver) deja el trabajo en el estado que promete el contrato.

Control de acceso. La unica ruta del router que exige staff es
`/v1/metricas/colegios/{id}/pedidos` (`_exigir_staff`). Las diez rutas
`/v1/admin/*` no llaman a esa puerta, y las decisiones de revision guardan como
autor el `actor` que viene en el CUERPO, no el de la sesion: cualquiera puede
firmar una aprobacion con el nombre de otro. Eso se fija aqui con pruebas del
comportamiento CORRECTO marcadas `xfail(strict)` (H-C-06), y las rutas que si
funcionan se ejercen con una sesion de operador para que sigan pasando cuando
la puerta exista. Tambien H-C-07: el backend no impone el tope de 10 MB que el
contrato promete y que hoy solo valida el navegador.

Todo con `ASGITransport`, sin uvicorn, sin Postgres y sin red: el motor es el
SQLite de la fixture y Catalogo, Identidad y Comercio son dobles en memoria.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from sqlalchemy import select
from _ayudas_inteligencia import catalogo_simple as _catalogo
from _ayudas_inteligencia import crear_y_procesar as _crear_y_procesar
from _ayudas_inteligencia import sembrar_canonico as _canonico
from tukit_comun.http import ErrorDominio
from tukit_inteligencia import api, trabajos
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import EstadoResolucion, EstadoTrabajo
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida
from tukit_inteligencia.remoto import RemotoCaido
from tukit_inteligencia.routers import inteligencia as router

pytestmark = pytest.mark.nfr("NFR-MAN-01")

COLEGIO = "11111111-1111-5111-8111-111111111111"
OPERADOR_ID = uuid.UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")
ACUDIENTE_ID = uuid.UUID("bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")
FIRMANTE_FALSO = uuid.UUID("dddddddd-dddd-5ddd-8ddd-dddddddddddd")
CONTACTO_ID = "cccccccc-cccc-5ccc-8ccc-cccccccccccc"
OPERADOR = {"Authorization": "Bearer tok-operador"}
ACUDIENTE = {"Authorization": "Bearer tok-acudiente"}
ENTREGA = {"destinatario": "Acudiente Ficticio", "direccion": "Calle Ficticia 1", "ciudad": "Bogota"}
PAGO = {"perfil": "Ahorrador", "correo": "acudiente@example.test", "entrega": ENTREGA}
TOPE_ARCHIVO = 10 * 1024 * 1024
INEXISTENTE = uuid.UUID("99999999-9999-5999-8999-999999999999")


@dataclass
class IdentidadSesiones:
    """Identidad en memoria: token -> (usuario, rol). Un token ausente es una sesion invalida."""

    sesiones: dict[str, tuple[uuid.UUID, str]] = field(
        default_factory=lambda: {
            "tok-operador": (OPERADOR_ID, "operador"),
            "tok-acudiente": (ACUDIENTE_ID, "acudiente"),
        }
    )
    contactos: list[str] = field(default_factory=list)
    directorio: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def colegios_conocidos(self) -> list[dict[str, Any]]:
        # `GET /v1/colegios`: subir listas lo consulta para reusar un colegio ya conocido.
        # La lista vacia es tambien lo que devuelve con Identidad caida.
        return []

    async def sesion(self, token: str) -> dict[str, Any] | None:
        if token not in self.sesiones:
            return None
        usuario, rol = self.sesiones[token]
        return {"usuario_id": str(usuario), "roles": [{"rol": rol, "ambito": None}], "version_permisos": 1}

    async def usuario_del_token(self, token: str) -> str | None:
        sesion = await self.sesion(token)
        return sesion["usuario_id"] if sesion else None

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.contactos.append(correo)
        return CONTACTO_ID

    async def datos_directorio(self, dane: str) -> dict[str, Any] | None:
        return self.directorio.get(dane)


@dataclass
class CatalogoRouter(CatalogoFalso):
    """El catalogo de las pruebas de trabajo, mas lo que el router pide para listas y previews."""

    importadas: list[dict[str, Any]] = field(default_factory=list)

    async def importar_lista(self, **kw: Any) -> dict[str, Any]:
        self.importadas.append(kw)
        return {"version_id": f"ver-{len(self.importadas)}"}

    async def revision(self, version_id: str) -> dict[str, Any]:
        raise RemotoCaido("catalogo", "404 version no encontrada")


class ComercioDoble:
    """Comercio en memoria: guarda lo que recibe y responde con lo programado."""

    def __init__(self, orden: tuple[int, dict] = (201, {}), pago: tuple[int, dict] = (201, {})) -> None:
        self.orden, self.pago = orden, pago
        self.ordenes: list[dict[str, Any]] = []

    async def crear_orden(self, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        self.ordenes.append(cuerpo)
        estado, respuesta = self.orden
        return estado, respuesta or {"pedido_id": "ped-1", "total": 33900}

    async def iniciar_pago(self, pedido_id: str, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        estado, respuesta = self.pago
        return estado, respuesta or {
            "pago_id": "pago-1",
            "url_redireccion": "https://pasarela.example.test/p",
        }


class ComercioCaido(ComercioDoble):
    async def crear_orden(self, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        raise RemotoCaido("comercio", "circuito abierto")


@dataclass
class Entorno:
    http: httpx.AsyncClient
    motor: Any
    catalogo: CatalogoRouter
    identidad: IdentidadSesiones
    comercio: ComercioDoble
    lanzados: list[uuid.UUID]
    lecturas: list[int]


def _catalogo_router() -> CatalogoRouter:
    base = _catalogo()
    return CatalogoRouter(renglones=base.renglones, respuestas=base.respuestas)


@pytest.fixture()
async def entorno(motor, monkeypatch):
    """La app con el motor de prueba y dobles inyectados por `app.state`, todo restaurado al terminar.

    `lanzar` se sustituye (crear/reintentar/devolver solo encolan: que el pipeline
    corra se prueba en `test_trabajos*`), y la percepcion lee una pagina fija de
    grado Cuarto para que la subida de listas no necesite ni PDF ni modelo.
    """
    catalogo, identidad, comercio = _catalogo_router(), IdentidadSesiones(), ComercioDoble()
    lanzados: list[uuid.UUID] = []
    lecturas: list[int] = []

    async def _lanzar(_motor: Any, trabajo_id: uuid.UUID) -> None:
        lanzados.append(trabajo_id)

    def _leer(_png: bytes, numero: int) -> PaginaLeida:
        lecturas.append(numero)
        return PaginaLeida(
            grados=["Cuarto"],
            completa=True,
            items=[ItemExtraido(descripcion="2 cuadernos cuadriculados", cantidad=2, confianza=0.9)],
        )

    for nombre, valor in (
        ("motor", motor),
        ("catalogo", catalogo),
        ("identidad", identidad),
        ("comercio", comercio),
    ):
        monkeypatch.setattr(app.state, nombre, valor, raising=False)
    monkeypatch.setattr(trabajos, "lanzar", _lanzar)
    monkeypatch.setattr(api, "_RENDERIZAR", lambda contenido: [contenido])
    monkeypatch.setattr(api, "_LEER", _leer)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield Entorno(http, motor, catalogo, identidad, comercio, lanzados, lecturas)


def _catalogo_con_ambiguo() -> CatalogoRouter:
    """Como el de siempre, pero el punzon es un emparejamiento dudoso que espera a una persona."""
    catalogo = _catalogo_router()
    catalogo.respuestas["punzon punta metalica de titanio"] = reconocido(
        "punzon punta metalica de titanio",
        "C020",
        [opcion("TK-C020-A", "economico", 3000), opcion("TK-C020-B", "premium", 9000)],
        parecido=0.5,
    )
    return catalogo


async def _item_de(motor: Any, trabajo_id: uuid.UUID, orden: int) -> uuid.UUID:
    async with motor.engine.begin() as conexion:
        return (
            await conexion.execute(
                select(trabajos.ITEM.c.id).where(
                    trabajos.ITEM.c.trabajo_id == trabajo_id, trabajos.ITEM.c.orden == orden
                )
            )
        ).scalar_one()


async def _publicado(entorno: Entorno) -> uuid.UUID:
    """El kit canonico publicado del grado. Desde d37c235 nace de la lista (`canonico_lista`) y no
    de aprobar el trabajo de un papa: el selector y aplicar-canonico solo miran ese origen."""
    return await _canonico(entorno.motor, entorno.catalogo)


def _multipart(partes: list[tuple[str, str | None, bytes]]) -> tuple[bytes, str]:
    """Un multipart escrito a mano: `(nombre, nombre_de_archivo | None, contenido)` en orden."""
    trozos = []
    for nombre, archivo, contenido in partes:
        cabeza = f'Content-Disposition: form-data; name="{nombre}"'
        if archivo:
            cabeza += f'; filename="{archivo}"'
        trozos.append(b"--FRONTERA\r\n" + cabeza.encode() + b"\r\n\r\n" + contenido + b"\r\n")
    return b"".join(trozos) + b"--FRONTERA--\r\n", "multipart/form-data; boundary=FRONTERA"


def _subida(hijos: Any, *, archivo: bytes = b"%PDF-ficticio", **campos: str) -> dict[str, Any]:
    """Los argumentos de httpx para `/v1/listas/subir`. `hijos` puede ser un valor ya serializado."""
    import json

    data = {"hijos": hijos if isinstance(hijos, str) else json.dumps(hijos), **campos}
    return {"data": data, "files": [("archivo", ("lista.pdf", archivo, "application/pdf"))]}


HIJO = {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}


class TestTokenDelEncabezado:
    @pytest.mark.parametrize(
        ("encabezado", "esperado"),
        [
            ("Bearer tok-1", "tok-1"),
            ("bearer   tok-1  ", "tok-1"),
            ("BEARER tok-1", "tok-1"),
            ("tok-1", "tok-1"),  # el token pelado tambien vale, como en Identidad
            ("  tok-1  ", "tok-1"),
            (None, None),
            ("", None),
        ],
    )
    def test_acepta_bearer_o_token_pelado(self, encabezado, esperado):
        assert router.token_bearer(encabezado) == esperado


class TestMultipartAMano:
    def test_conserva_el_orden_y_la_repeticion_de_las_partes(self):
        """Una subida de varios hijos manda `archivo` y `referencia` repetidos: el aplanado los perderia."""
        cuerpo, tipo = _multipart(
            [
                ("archivo", "a.pdf", b"AAA"),
                ("referencia", None, b"hijo-1"),
                ("archivo", "b.pdf", b"BBB"),
                ("referencia", None, b"hijo-2"),
            ]
        )

        partes = router._partes_multipart(cuerpo, tipo)

        assert [(p.nombre, p.es_archivo, p.contenido) for p in partes] == [
            ("archivo", True, b"AAA"),
            ("referencia", False, b"hijo-1"),
            ("archivo", True, b"BBB"),
            ("referencia", False, b"hijo-2"),
        ]
        assert partes[1].texto() == "hijo-1"

    def test_la_frontera_puede_venir_entre_comillas(self):
        cuerpo, _ = _multipart([("grado", None, b"Cuarto")])

        partes = router._partes_multipart(cuerpo, 'multipart/form-data; boundary="FRONTERA"')

        assert [p.nombre for p in partes] == ["grado"]

    def test_sin_frontera_es_un_422_multipart_invalido(self):
        with pytest.raises(ErrorDominio) as info:
            router._partes_multipart(b"cualquier cosa", "multipart/form-data")

        assert (info.value.estado, info.value.error) == (422, "multipart_invalido")

    def test_una_parte_sin_nombre_se_descarta_en_vez_de_tumbar_la_subida(self):
        cuerpo = (
            b"--FRONTERA\r\nContent-Disposition: form-data\r\n\r\nhuerfana\r\n"
            b'--FRONTERA\r\nContent-Disposition: form-data; name="grado"\r\n\r\nCuarto\r\n'
            b"--FRONTERA--\r\n"
        )

        partes = router._partes_multipart(cuerpo, "multipart/form-data; boundary=FRONTERA")

        assert [(p.nombre, p.texto()) for p in partes] == [("grado", "Cuarto")]

    def test_el_texto_con_bytes_invalidos_se_reemplaza_y_no_revienta(self):
        cuerpo, tipo = _multipart([("nombre", None, b"Col\xe9gio")])

        (parte,) = router._partes_multipart(cuerpo, tipo)

        assert parte.texto() == "Col�gio"

    def test_el_aplanado_separa_campos_de_archivos_y_gana_la_ultima_parte(self):
        cuerpo, tipo = _multipart(
            [("grado", None, b"Tercero"), ("grado", None, b"Cuarto"), ("archivo", "l.pdf", b"PDF")]
        )

        campos, archivos = router._leer_multipart(cuerpo, tipo)

        assert campos == {"grado": "Cuarto"}
        assert archivos == {"archivo": b"PDF"}

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-27: el parser de multipart recorta los CR/LF finales del ARCHIVO "
            "(routers/inteligencia.py:409, bruto.strip(b'\\r\\n')): el PDF que llega al catalogo "
            "no es byte a byte el que subio el acudiente"
        ),
    )
    def test_el_archivo_llega_byte_a_byte_aunque_termine_en_salto_de_linea(self):
        """Muchos PDF terminan en `%%EOF\\r\\n`; el documento guardado debe ser el original."""
        original = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\r\n"
        cuerpo, tipo = _multipart([("archivo", "lista.pdf", original)])

        _campos, archivos = router._leer_multipart(cuerpo, tipo)

        assert archivos["archivo"] == original


class TestOrdenarPorHttp:
    async def test_un_trabajo_anonimo_paga_con_el_correo_y_devuelve_el_pedido_y_la_pasarela(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(f"/v1/trabajos/{trabajo_id}/ordenar", json=PAGO)

        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["pedido_id"] == "ped-1" and cuerpo["total"] == 33900
        assert cuerpo["url_redireccion"] == "https://pasarela.example.test/p"
        assert entorno.identidad.contactos == ["acudiente@example.test"]
        assert entorno.comercio.ordenes[0]["usuario_id"] == CONTACTO_ID

    @pytest.mark.parametrize("perfil", ["Inventado", "ahorrador"])
    async def test_un_perfil_que_el_trabajo_no_tiene_es_404_trabajo_no_ordenable(self, entorno, perfil):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(
            f"/v1/trabajos/{trabajo_id}/ordenar", json={**PAGO, "perfil": perfil}
        )

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_ordenable"
        assert entorno.comercio.ordenes == []

    async def test_un_trabajo_que_no_existe_es_404_trabajo_no_ordenable(self, entorno):
        respuesta = await entorno.http.post(f"/v1/trabajos/{INEXISTENTE}/ordenar", json=PAGO)

        assert respuesta.status_code == 404
        assert respuesta.json() == {
            "error": "trabajo_no_ordenable",
            "mensaje": "Ese trabajo no tiene un kit de ese perfil para comprar.",
        }

    async def test_el_rechazo_de_comercio_se_reenvia_con_su_estado_y_su_motivo(self, entorno):
        """El acudiente tiene que ver `precio_cambiado`, no un 500 generico."""
        entorno.comercio.orden = (409, {"error": "precio_cambiado", "mensaje": "El precio cambio."})
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(f"/v1/trabajos/{trabajo_id}/ordenar", json=PAGO)

        assert respuesta.status_code == 409
        assert respuesta.json() == {"error": "precio_cambiado", "mensaje": "El precio cambio."}

    async def test_el_rechazo_del_pago_tambien_se_reenvia(self, entorno):
        entorno.comercio.pago = (422, {"error": "metodo_no_disponible", "mensaje": "PSE no disponible"})
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(f"/v1/trabajos/{trabajo_id}/ordenar", json=PAGO)

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "metodo_no_disponible"

    async def test_un_rechazo_sin_codigo_ni_mensaje_usa_los_textos_por_omision(self, entorno):
        entorno.comercio.orden = (502, {"detalle": "algo interno"})
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(f"/v1/trabajos/{trabajo_id}/ordenar", json=PAGO)

        assert respuesta.status_code == 502
        assert respuesta.json() == {
            "error": "checkout_rechazado",
            "mensaje": "El pago no se pudo iniciar.",
        }
        assert "algo interno" not in respuesta.text  # no se filtra el cuerpo interno del otro servicio

    async def test_un_kit_sin_nada_vendible_es_409_kit_sin_lineas(self, entorno):
        solo_licencia = CatalogoRouter(
            renglones=[
                renglon(
                    1,
                    "Plan lector virtual RAZ-PLUS",
                    tipo_item="licencia_digital",
                    modo_adquisicion="plataforma",
                )
            ]
        )
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, solo_licencia)

        respuesta = await entorno.http.post(f"/v1/trabajos/{trabajo_id}/ordenar", json=PAGO)

        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "kit_sin_lineas"
        assert entorno.comercio.ordenes == []

    async def test_con_comercio_caido_es_503_y_dice_cual_servicio(self, entorno):
        entorno.comercio = ComercioCaido()
        app.state.comercio = entorno.comercio
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(f"/v1/trabajos/{trabajo_id}/ordenar", json=PAGO)

        assert respuesta.status_code == 503
        assert respuesta.json() == {
            "error": "servicio_no_disponible",
            "mensaje": "No se pudo completar el checkout: comercio no respondio.",
        }

    @pytest.mark.parametrize(
        "cuerpo",
        [
            {"perfil": "Ahorrador", "correo": "acudiente@example.test"},
            {**PAGO, "entrega": {"destinatario": "", "direccion": "x", "ciudad": "y"}},
            {**PAGO, "correo": "a@b"},
            {**PAGO, "perfil": "P" * 17},
        ],
        ids=["sin_entrega", "destinatario_vacio", "correo_corto", "perfil_largo"],
    )
    async def test_un_cuerpo_mal_formado_es_400_y_no_llega_a_comercio(self, entorno, cuerpo):
        respuesta = await entorno.http.post(f"/v1/trabajos/{INEXISTENTE}/ordenar", json=cuerpo)

        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "entrada_invalida"
        assert entorno.comercio.ordenes == []


class TestReintentarPorHttp:
    async def test_un_trabajo_que_no_existe_es_404(self, entorno):
        respuesta = await entorno.http.post(f"/v1/trabajos/{INEXISTENTE}/reintentar")

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_existe"
        assert entorno.lanzados == []

    async def test_un_trabajo_fallido_se_vuelve_a_encolar(self, entorno):
        class Caido(CatalogoFalso):
            async def listas(self, **kw: Any) -> Any:
                raise RemotoCaido("catalogo", "conexion rechazada")

        trabajo_id, estado = await _crear_y_procesar(entorno.motor, Caido())
        assert estado == EstadoTrabajo.FALLIDO.value

        respuesta = await entorno.http.post(f"/v1/trabajos/{trabajo_id}/reintentar")

        assert respuesta.status_code == 200
        assert respuesta.json() == {"trabajo_id": str(trabajo_id), "estado": EstadoTrabajo.ENCOLADO.value}
        assert entorno.lanzados == [trabajo_id]

    async def test_un_trabajo_ya_encolado_tambien_se_puede_reintentar(self, entorno):
        creado = await trabajos.crear(
            entorno.motor, hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}]
        )

        respuesta = await entorno.http.post(f"/v1/trabajos/{creado['trabajo_id']}/reintentar")

        assert respuesta.status_code == 200
        assert entorno.lanzados == [uuid.UUID(creado["trabajo_id"])]

    @pytest.mark.parametrize("etapa", ["espera_revision", "publicado"])
    async def test_un_trabajo_que_no_fallo_no_se_reintenta(self, entorno, etapa):
        """Reencolar un kit ya armado lo borraria y lo reharia mientras el acudiente lo mira."""
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)
        if etapa == "publicado":
            await trabajos.revisar(entorno.motor, trabajo_id, decision="aprobar")

        respuesta = await entorno.http.post(f"/v1/trabajos/{trabajo_id}/reintentar")

        assert respuesta.status_code == 409
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "estado_incompatible"
        assert etapa in cuerpo["mensaje"]
        assert entorno.lanzados == []


class TestSubirListasMalFormada:
    """Todo se rechaza ANTES de percibir un archivo, de registrar un contacto o de importar algo."""

    async def _sin_efectos(self, entorno: Entorno) -> None:
        assert entorno.catalogo.importadas == []
        assert entorno.identidad.contactos == []
        assert entorno.lecturas == []

    async def test_sin_multipart_es_422(self, entorno):
        respuesta = await entorno.http.post("/v1/listas/subir", json={"hijos": [HIJO]})

        assert respuesta.status_code == 422
        assert respuesta.json() == {
            "error": "multipart_invalido",
            "mensaje": "Sube las listas como multipart/form-data.",
        }
        await self._sin_efectos(entorno)

    async def test_un_multipart_sin_frontera_es_422(self, entorno):
        respuesta = await entorno.http.post(
            "/v1/listas/subir", content=b"x", headers={"Content-Type": "multipart/form-data"}
        )

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "multipart_invalido"
        await self._sin_efectos(entorno)

    @pytest.mark.parametrize(
        "hijos",
        ["no es json", '{"referencia": "hijo-1"}', '[{"referencia": "hijo-1", "grado": ""}]', "[1]"],
        ids=["no_json", "objeto_en_vez_de_lista", "campo_invalido", "elemento_no_objeto"],
    )
    async def test_hijos_que_no_son_una_lista_de_hijos_validos_es_422(self, entorno, hijos):
        respuesta = await entorno.http.post("/v1/listas/subir", **_subida(hijos))

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "hijos_invalidos"
        assert respuesta.json()["campo"] == "hijos"
        await self._sin_efectos(entorno)

    async def test_una_lista_vacia_de_hijos_es_422_hijos_requeridos(self, entorno):
        respuesta = await entorno.http.post("/v1/listas/subir", **_subida("[]"))

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "hijos_requeridos"
        await self._sin_efectos(entorno)

    @pytest.mark.parametrize(
        "contacto",
        ["no es json", "[]", '{"celular": "3000000000"}', '{"correo": "a@b"}'],
        ids=["no_json", "no_es_objeto", "sin_correo", "correo_corto"],
    )
    async def test_un_contacto_invalido_es_422_y_no_se_registra_nada(self, entorno, contacto):
        respuesta = await entorno.http.post("/v1/listas/subir", **_subida([HIJO], contacto=contacto))

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "contacto_invalido"
        assert respuesta.json()["campo"] == "contacto"
        await self._sin_efectos(entorno)

    @pytest.mark.parametrize(
        ("preferencias", "mensaje"),
        [("{roto", "no son un JSON valido"), ("[1, 2]", "tienen que ser un objeto"), ('"texto"', "objeto")],
        ids=["json_roto", "lista", "cadena"],
    )
    async def test_unas_preferencias_que_no_son_un_objeto_json_son_422(self, entorno, preferencias, mensaje):
        respuesta = await entorno.http.post("/v1/listas/subir", **_subida([HIJO], preferencias=preferencias))

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "preferencias_invalidas"
        assert mensaje in respuesta.json()["mensaje"]
        await self._sin_efectos(entorno)

    async def test_unas_preferencias_vacias_se_tratan_como_ausentes(self, entorno):
        respuesta = await entorno.http.post("/v1/listas/subir", **_subida([HIJO], preferencias="{}"))

        assert respuesta.status_code == 202
        assert entorno.catalogo.importadas[0]["preferencias"] is None

    async def test_sin_archivo_para_ningun_hijo_es_422_archivo_faltante(self, entorno):
        respuesta = await entorno.http.post(
            "/v1/listas/subir",
            data={"hijos": '[{"referencia": "hijo-1", "colegio_id": "x", "grado": "Cuarto"}]'},
            files=[("otro", ("x.txt", b"x", "text/plain"))],
        )

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "archivo_faltante"
        await self._sin_efectos(entorno)


class TestSubirListasEmparejaArchivos:
    async def test_un_archivo_sin_referencia_se_aparea_con_el_hijo_por_orden(self, entorno):
        """Un cliente que sube `archivo` sin `referencia` aun asi liga el primer PDF al primer hijo."""
        respuesta = await entorno.http.post("/v1/listas/subir", **_subida([HIJO]))

        assert respuesta.status_code == 202
        assert respuesta.json()["subidas"] == [
            {"referencia": "hijo-1", "version_id": "ver-1", "grado": "Cuarto"}
        ]
        assert entorno.lecturas == [1]

    async def test_el_directorio_rellena_los_huecos_pero_lo_escrito_manda(self, entorno):
        entorno.identidad.directorio["11001000123"] = {
            "dane": "11001000123",
            "nombre": "Nombre del directorio",
            "direccion": "Calle Ficticia 1",
            "sitio": "https://colegio.example.test",
        }
        hijo = {
            "referencia": "hijo-1",
            "colegio_dane": "11001000123",
            "colegio_nombre": "Nombre escrito",
            "grado": "Cuarto",
        }

        respuesta = await entorno.http.post("/v1/listas/subir", **_subida([hijo]))

        assert respuesta.status_code == 202
        assert entorno.catalogo.importadas[0]["colegio_datos"] == {
            "dane": "11001000123",
            "nombre": "Nombre escrito",
            "direccion": "Calle Ficticia 1",
            "sitio": "https://colegio.example.test",
        }

    async def test_sin_nombre_escrito_se_usa_el_del_directorio(self, entorno):
        entorno.identidad.directorio["11001000123"] = {
            "dane": "11001000123",
            "nombre": "Nombre del directorio",
        }
        hijo = {"referencia": "hijo-1", "colegio_dane": "11001000123", "grado": "Cuarto"}

        await entorno.http.post("/v1/listas/subir", **_subida([hijo]))

        assert entorno.catalogo.importadas[0]["colegio_datos"]["nombre"] == "Nombre del directorio"

    async def test_un_dane_que_el_directorio_no_conoce_degrada_a_dane_y_nombre(self, entorno):
        hijo = {
            "referencia": "hijo-1",
            "colegio_dane": "00000000000",
            "colegio_nombre": "Colegio Ficticio",
            "grado": "Cuarto",
        }

        respuesta = await entorno.http.post("/v1/listas/subir", **_subida([hijo]))

        assert respuesta.status_code == 202
        assert entorno.catalogo.importadas[0]["colegio_datos"] == {
            "dane": "00000000000",
            "nombre": "Colegio Ficticio",
        }


class TestOnboardingMalFormado:
    @staticmethod
    def _campos(**omitir: bool) -> dict[str, str]:
        base = {"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": "2026"}
        return {k: v for k, v in base.items() if k not in omitir}

    @staticmethod
    def _archivo(nombre: str = "archivo") -> list[Any]:
        return [(nombre, ("lista.pdf", b"%PDF-ficticio", "application/pdf"))]

    async def test_sin_multipart_es_422(self, entorno):
        respuesta = await entorno.http.post("/v1/admin/onboarding", headers=OPERADOR, json=self._campos())

        assert respuesta.status_code == 422
        assert respuesta.json() == {
            "error": "multipart_invalido",
            "mensaje": "Sube la lista como multipart/form-data.",
        }

    # El colegio se designa de una de tres formas (id, DANE o nombre, `ColegioElegido`): sin
    # ninguna es `colegio_requerido` sobre `colegio`, antes de percibir.
    @pytest.mark.parametrize(
        ("falta", "error", "campo"),
        [
            ("colegio_id", "colegio_requerido", "colegio"),
            ("grado", "campo_faltante", "grado"),
            ("anio_lectivo", "campo_faltante", "anio_lectivo"),
        ],
    )
    async def test_cada_campo_obligatorio_se_exige_y_se_nombra(self, entorno, falta, error, campo):
        respuesta = await entorno.http.post(
            "/v1/admin/onboarding",
            headers=OPERADOR,
            data=self._campos(**{falta: True}),
            files=self._archivo(),
        )

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == error
        assert respuesta.json()["campo"] == campo
        assert entorno.catalogo.importadas == []

    async def test_sin_el_campo_archivo_es_422_archivo_faltante(self, entorno):
        respuesta = await entorno.http.post(
            "/v1/admin/onboarding", headers=OPERADOR, data=self._campos(), files=self._archivo("otro")
        )

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "archivo_faltante"
        assert respuesta.json()["campo"] == "archivo"
        assert entorno.catalogo.importadas == []

    async def test_un_anio_que_no_es_numero_es_422_antes_de_percibir(self, entorno):
        campos = {**self._campos(), "anio_lectivo": "dos mil veintiseis"}

        respuesta = await entorno.http.post(
            "/v1/admin/onboarding", headers=OPERADOR, data=campos, files=self._archivo()
        )

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "anio_invalido"
        assert respuesta.json()["campo"] == "anio_lectivo"
        assert entorno.lecturas == [] and entorno.catalogo.importadas == []


class TestRevisionHumanaPorHttp:
    """La consola del equipo interno. Todas las llamadas llevan sesion de operador."""

    async def test_el_trabajo_con_sus_kits_aunque_no_este_publicado(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.get(f"/v1/admin/trabajos/{trabajo_id}", headers=OPERADOR)

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == EstadoTrabajo.ESPERA_REVISION.value
        # Sin preferencias salen Ahorrador y Premium (kits a pedido, ADR 0030).
        assert [kit["perfil"] for kit in cuerpo["kits"]] == ["Ahorrador", "Premium"]
        assert len(cuerpo["lineas_pendientes"]) == 1  # el punzon, que nadie ha mirado

    async def test_un_trabajo_que_no_existe_es_404(self, entorno):
        respuesta = await entorno.http.get(f"/v1/admin/trabajos/{INEXISTENTE}", headers=OPERADOR)

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_existe"

    async def test_borrar_un_desechable_responde_204_y_deja_de_existir(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.delete(f"/v1/admin/trabajos/{trabajo_id}", headers=OPERADOR)

        assert respuesta.status_code == 204 and respuesta.content == b""
        assert (await entorno.http.get(f"/v1/trabajos/{trabajo_id}")).status_code == 404

    async def test_borrar_un_trabajo_que_no_existe_es_404(self, entorno):
        respuesta = await entorno.http.delete(f"/v1/admin/trabajos/{INEXISTENTE}", headers=OPERADOR)

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_existe"

    async def test_un_trabajo_publicado_esta_protegido_contra_el_borrado(self, entorno):
        """Es el kit canonico de su colegio y grado: borrarlo perderia una revision humana ya aprobada."""
        trabajo_id = await _publicado(entorno)

        respuesta = await entorno.http.delete(f"/v1/admin/trabajos/{trabajo_id}", headers=OPERADOR)

        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "trabajo_publicado_protegido"
        assert (await entorno.http.get(f"/v1/trabajos/{trabajo_id}")).status_code == 200

    async def test_validar_una_linea_la_deja_resuelta_con_el_producto_elegido(self, entorno):
        entorno.catalogo = _catalogo_con_ambiguo()
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)
        item_id = await _item_de(entorno.motor, trabajo_id, 4)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar",
            json={"sku": "TK-C020-B", "motivo": "el acudiente prefiere el premium"},
            headers=OPERADOR,
        )

        assert respuesta.status_code == 200
        assert respuesta.json() == {
            "item_id": str(item_id),
            "estado": EstadoResolucion.RESUELTO_AUTO.value,
            "sku": "TK-C020-B",
        }
        async with entorno.motor.engine.begin() as conexion:
            estado = await conexion.scalar(
                select(trabajos.RESOLUCION.c.estado).where(trabajos.RESOLUCION.c.item_crudo_id == item_id)
            )
        assert estado == EstadoResolucion.RESUELTO_AUTO.value

    @pytest.mark.parametrize(
        ("catalogo", "cuerpo"),
        [(_catalogo_router, {}), (_catalogo_con_ambiguo, {"sku": "TK-NO-ES-CANDIDATO"})],
        ids=["sin_sku", "sku_ajeno"],
    )
    async def test_validar_con_un_sku_que_no_es_candidato_es_un_error_del_cliente(
        self, entorno, catalogo, cuerpo
    ):
        """Validar sin nada que validar es un 4xx con motivo y la linea sigue esperando (H-A-28).

        Desde 390966b, validar sin `sku` confirma el producto que la linea ya tiene en
        el kit, y un `sku` que no es candidato pero esta en el catalogo se registra
        (`trabajos.py:1825-1830,1861-1867`). El rechazo queda para cuando no hay producto por
        ningun lado: el punzon sin coincidencia y sin `sku`, o un `sku` que el
        catalogo no tiene. Antes, los dos llegaban al CHECK
        `resolucion_resuelta_tiene_candidato` y salia un 500.
        """
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, catalogo())
        item_id = await _item_de(entorno.motor, trabajo_id, 4)

        async def _estado() -> str:
            async with entorno.motor.engine.begin() as conexion:
                return await conexion.scalar(
                    select(trabajos.RESOLUCION.c.estado).where(trabajos.RESOLUCION.c.item_crudo_id == item_id)
                )

        antes = await _estado()
        transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)

        async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
            respuesta = await http.post(
                f"/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar", json=cuerpo, headers=OPERADOR
            )

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "sin_producto_que_validar"
        assert respuesta.json()["campo"] == "sku"
        assert antes != EstadoResolucion.RESUELTO_AUTO.value
        assert await _estado() == antes

    async def test_validar_una_linea_que_no_es_del_trabajo_es_404(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/lineas/{INEXISTENTE}/validar", json={}, headers=OPERADOR
        )

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "linea_no_existe"

    async def test_sin_coincidencia_marca_hueco_de_catalogo_y_no_sin_match(self, entorno):
        """'Te entendi y no lo tengo' no es 'no te entendi': solo lo primero informa al catalogo."""
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)
        item_id = await _item_de(entorno.motor, trabajo_id, 4)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/sin-coincidencia",
            json={"motivo": "el catalogo no maneja titanio"},
            headers=OPERADOR,
        )

        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == EstadoResolucion.HUECO_CATALOGO.value
        assert respuesta.json()["sku"] is None

    async def test_sin_coincidencia_en_una_linea_ajena_es_404(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/lineas/{INEXISTENTE}/sin-coincidencia",
            json={},
            headers=OPERADOR,
        )

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "linea_no_existe"

    async def test_fijar_el_producto_de_un_solo_kit_recalcula_su_subtotal_y_su_total(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)
        item_id = await _item_de(entorno.motor, trabajo_id, 1)
        antes = await trabajos.ver(entorno.motor, trabajo_id, incluir_kits=True)
        total_antes = next(k for k in antes["kits"] if k["perfil"] == "Ahorrador")["total"]

        respuesta = await entorno.http.put(
            f"/v1/admin/trabajos/{trabajo_id}/kits/Ahorrador/lineas/{item_id}/producto",
            json={"sku": "TK-C001-PRE"},
            headers=OPERADOR,
        )

        assert respuesta.status_code == 200
        assert respuesta.json() == {
            "trabajo_id": str(trabajo_id),
            "perfil": "Ahorrador",
            "item_id": str(item_id),
            "sku": "TK-C001-PRE",
        }
        despues = await trabajos.ver(entorno.motor, trabajo_id, incluir_kits=True)
        kit = next(k for k in despues["kits"] if k["perfil"] == "Ahorrador")
        linea = next(x for x in kit["lineas"] if x["item_id"] == str(item_id))
        assert linea["producto_elegido"]["sku"] == "TK-C001-PRE"
        assert linea["subtotal_linea"] == 2 * 12000  # dos cuadernos al precio del premium
        assert kit["total"] == total_antes - 2 * 4500 + 2 * 12000
        # Los otros kits no se tocan: la decision de producto es por nivel.
        otro = next(k for k in despues["kits"] if k["perfil"] == "Premium")
        assert otro["total"] == next(k for k in antes["kits"] if k["perfil"] == "Premium")["total"]

    async def test_fijar_producto_en_una_linea_que_el_kit_no_tiene_es_404(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.put(
            f"/v1/admin/trabajos/{trabajo_id}/kits/Ahorrador/lineas/{INEXISTENTE}/producto",
            json={"sku": "TK-C001-PRE"},
            headers=OPERADOR,
        )

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "linea_no_existe"

    async def test_un_sku_de_mas_de_64_caracteres_es_400(self, entorno):
        respuesta = await entorno.http.put(
            f"/v1/admin/trabajos/{INEXISTENTE}/kits/Ahorrador/lineas/{INEXISTENTE}/producto",
            json={"sku": "S" * 65},
            headers=OPERADOR,
        )

        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "entrada_invalida"

    async def test_aprobar_publica_y_deja_la_nota(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/revision",
            json={"decision": "aprobar", "nota": "revisado contra la lista del colegio"},
            headers=OPERADOR,
        )

        assert respuesta.status_code == 200
        assert respuesta.json() == {
            "trabajo_id": str(trabajo_id),
            "estado": EstadoTrabajo.PUBLICADO.value,
            "nota": "revisado contra la lista del colegio",
        }
        assert entorno.lanzados == []  # aprobar no reencola

    async def test_devolver_reabre_el_trabajo_y_lo_manda_a_la_cola_del_trabajador(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "devolver"}, headers=OPERADOR
        )

        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == EstadoTrabajo.ENCOLADO.value
        assert entorno.lanzados == [trabajo_id]

    async def test_una_decision_que_no_es_aprobar_ni_devolver_es_400(self, entorno):
        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{INEXISTENTE}/revision", json={"decision": "rechazar"}, headers=OPERADOR
        )

        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "entrada_invalida"

    async def test_revisar_un_trabajo_que_no_existe_es_404(self, entorno):
        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{INEXISTENTE}/revision", json={"decision": "aprobar"}, headers=OPERADOR
        )

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_existe"

    async def test_aprobar_dos_veces_es_409_estado_incompatible(self, entorno):
        trabajo_id = await _publicado(entorno)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "aprobar"}, headers=OPERADOR
        )

        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "estado_incompatible"
        assert "publicado" in respuesta.json()["mensaje"]

    async def test_un_preview_no_se_publica_porque_no_tiene_acudiente(self, entorno):
        creado = await trabajos.crear(
            entorno.motor,
            hijos=[{"referencia": "preview", "colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}],
            origen="preview_onboarding",
        )
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(entorno.motor, trabajo_id, catalogo=entorno.catalogo)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "aprobar"}, headers=OPERADOR
        )

        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "preview_no_publicable"

    async def test_no_se_aprueba_un_kit_del_que_nadie_puede_comprar_nada(self, entorno):
        solo_licencia = CatalogoRouter(
            renglones=[
                renglon(
                    1,
                    "Plan lector virtual RAZ-PLUS",
                    tipo_item="licencia_digital",
                    modo_adquisicion="plataforma",
                )
            ]
        )
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, solo_licencia)

        respuesta = await entorno.http.post(
            f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "aprobar"}, headers=OPERADOR
        )

        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "kit_sin_lineas"
        vista = await trabajos.ver(entorno.motor, trabajo_id)
        assert vista["estado"] == EstadoTrabajo.ESPERA_REVISION.value  # la aprobacion no quedo a medias

    async def test_la_cola_lista_los_trabajos_que_esperan_a_una_persona(self, entorno):
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, entorno.catalogo)

        respuesta = await entorno.http.get("/v1/admin/cola", headers=OPERADOR)

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert (cuerpo["total"], cuerpo["pagina"], cuerpo["por_pagina"]) == (1, 1, 50)
        assert cuerpo["trabajos"][0]["trabajo_id"] == str(trabajo_id)
        assert cuerpo["trabajos"][0]["lineas_a_revisar"] == 1

    @pytest.mark.parametrize("consulta", ["pagina=0", "por_pagina=0", "por_pagina=201", "pagina=x"])
    async def test_una_paginacion_fuera_de_rango_es_400(self, entorno, consulta):
        respuesta = await entorno.http.get(f"/v1/admin/cola?{consulta}", headers=OPERADOR)

        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "entrada_invalida"


class TestSelectorYMetricas:
    async def test_los_grados_con_kit_publicado_se_filtran_por_colegio(self, entorno):
        trabajo_id = await _publicado(entorno)

        todos = await entorno.http.get("/v1/grados-canonicos")
        del_colegio = await entorno.http.get("/v1/grados-canonicos", params={"colegio_id": COLEGIO})
        de_otro = await entorno.http.get("/v1/grados-canonicos", params={"colegio_id": str(INEXISTENTE)})

        async with entorno.motor.engine.begin() as conexion:
            publicado_en = await conexion.scalar(
                select(trabajos.TRABAJO.c.terminado_en).where(trabajos.TRABAJO.c.id == trabajo_id)
            )
        # edd9877 agrega cuando se publico y el borrador abierto (ninguno: nadie lo esta editando).
        esperado = {
            "colegio_id": COLEGIO,
            "grado": "Cuarto",
            "anio_lectivo": 2026,
            "trabajo_id": str(trabajo_id),
            "publicado_en": publicado_en.isoformat(),
            "borrador_trabajo_id": None,
        }
        assert todos.json() == {"grados": [esperado]}
        assert del_colegio.json() == {"grados": [esperado]}
        assert de_otro.json() == {"grados": []}

    async def test_las_metricas_de_un_colegio_sin_kits_son_ceros_y_no_un_404(self, entorno):
        respuesta = await entorno.http.get(f"/v1/metricas/colegios/{COLEGIO}")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["colegio_id"] == COLEGIO
        assert cuerpo["kits_armados"] == 0 and cuerpo["cobertura"] == 0

    async def test_las_metricas_cuentan_el_kit_publicado_y_su_cobertura(self, entorno):
        await _publicado(entorno)

        respuesta = await entorno.http.get(f"/v1/metricas/colegios/{COLEGIO}")

        cuerpo = respuesta.json()
        assert cuerpo["kits_armados"] == 1
        # Comprables: cuadernos, colores y el punzon sin match; resueltas, las dos primeras.
        assert (cuerpo["lineas_comprables"], cuerpo["lineas_resueltas"]) == (3, 2)
        assert cuerpo["cobertura"] == round(2 / 3, 4)


# Cada ruta del equipo interno, con lo minimo para que la peticion sea valida: si la puerta
# existiera responderia 401/403 ANTES de mirar el cuerpo o buscar el trabajo.
_PREVIEW = {"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}
# El onboarding ya pasa por `_exigir_staff` (46a0c4a): sale del xfail; las demas siguen abiertas.
_SIN_PUERTA = pytest.mark.xfail(
    strict=True,
    reason=(
        "H-C-06: las rutas /v1/admin/* no llaman a _exigir_staff (routers/inteligencia.py:858-1098, "
        "50-71; solo lo usa :1152): sin token o con rol de acudiente responden como si fueran staff"
    ),
)
RUTAS_ADMIN = [
    pytest.param("GET", "/v1/admin/cola", {}, id="cola", marks=_SIN_PUERTA),
    pytest.param(
        "GET", f"/v1/admin/colegios/{COLEGIO}/acudientes", {}, id="acudientes_de_colegio", marks=_SIN_PUERTA
    ),
    pytest.param("GET", f"/v1/admin/trabajos/{INEXISTENTE}", {}, id="ver_trabajo", marks=_SIN_PUERTA),
    pytest.param("DELETE", f"/v1/admin/trabajos/{INEXISTENTE}", {}, id="eliminar_trabajo", marks=_SIN_PUERTA),
    pytest.param(
        "POST",
        f"/v1/admin/trabajos/{INEXISTENTE}/lineas/{INEXISTENTE}/validar",
        {"json": {}},
        id="validar",
        marks=_SIN_PUERTA,
    ),
    pytest.param(
        "PUT",
        f"/v1/admin/trabajos/{INEXISTENTE}/kits/Ahorrador/lineas/{INEXISTENTE}/producto",
        {"json": {"sku": "TK-C001-ECO"}},
        id="fijar_producto",
        marks=_SIN_PUERTA,
    ),
    pytest.param(
        "POST",
        f"/v1/admin/trabajos/{INEXISTENTE}/lineas/{INEXISTENTE}/sin-coincidencia",
        {"json": {}},
        id="sin_coincidencia",
        marks=_SIN_PUERTA,
    ),
    pytest.param(
        "POST",
        f"/v1/admin/trabajos/{INEXISTENTE}/revision",
        {"json": {"decision": "aprobar"}},
        id="revision",
        marks=_SIN_PUERTA,
    ),
    pytest.param(
        "POST",
        "/v1/admin/onboarding",
        {
            "data": {"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": "2026"},
            "files": [("archivo", ("lista.pdf", b"%PDF-ficticio", "application/pdf"))],
        },
        id="onboarding",
    ),
    pytest.param(
        "POST",
        f"/v1/admin/onboarding/{INEXISTENTE}/preview",
        {"json": _PREVIEW},
        id="preview",
        marks=_SIN_PUERTA,
    ),
]


class TestControlDeAcceso:
    @pytest.mark.parametrize(("metodo", "ruta", "argumentos"), RUTAS_ADMIN)
    async def test_una_ruta_admin_pide_sesion_y_rol_de_staff(self, entorno, metodo, ruta, argumentos):
        """Sin token debe ser 401 y con la sesion de un acudiente 403, como `/v1/metricas/.../pedidos`."""
        sin_token = await entorno.http.request(metodo, ruta, **argumentos)
        de_acudiente = await entorno.http.request(metodo, ruta, headers=ACUDIENTE, **argumentos)

        assert (sin_token.status_code, de_acudiente.status_code) == (401, 403)

    @pytest.mark.parametrize(
        "ruta", ["/v1/admin/cola", f"/v1/admin/colegios/{COLEGIO}/acudientes"], ids=["cola", "acudientes"]
    )
    async def test_un_operador_con_sesion_valida_entra_a_la_consola(self, entorno, ruta):
        """La puerta, cuando exista, no puede cerrarle el paso al equipo interno."""
        respuesta = await entorno.http.get(ruta, headers=OPERADOR)

        assert respuesta.status_code == 200

    # H-C-06 (autor de la decision): corregido en fix/hallazgos-qa, sale XPASS(strict) y se quita el xfail.
    @pytest.mark.parametrize("decision", ["revision", "validar", "sin_coincidencia"])
    async def test_el_autor_de_una_decision_es_el_de_la_sesion_y_no_el_que_dice_el_cuerpo(
        self, entorno, decision
    ):
        """Con el `actor` en el cuerpo, cualquiera firma una aprobacion con el nombre de otro."""
        trabajo_id, _ = await _crear_y_procesar(entorno.motor, _catalogo_con_ambiguo())
        item_id = await _item_de(entorno.motor, trabajo_id, 4)
        base = f"/v1/admin/trabajos/{trabajo_id}"
        ruta, cuerpo = {
            "revision": (f"{base}/revision", {"decision": "aprobar"}),
            "validar": (f"{base}/lineas/{item_id}/validar", {"sku": "TK-C020-B"}),
            "sin_coincidencia": (f"{base}/lineas/{item_id}/sin-coincidencia", {}),
        }[decision]

        respuesta = await entorno.http.post(
            ruta, json={**cuerpo, "actor": str(FIRMANTE_FALSO)}, headers=OPERADOR
        )

        assert respuesta.status_code == 200
        async with entorno.motor.engine.begin() as conexion:
            if decision == "revision":
                firmante = await conexion.scalar(
                    select(trabajos.TRABAJO.c.revisado_por).where(trabajos.TRABAJO.c.id == trabajo_id)
                )
            else:
                firmante = await conexion.scalar(
                    select(trabajos.RESOLUCION.c.decidido_por).where(
                        trabajos.RESOLUCION.c.item_crudo_id == item_id
                    )
                )
        assert firmante == OPERADOR_ID

    # H-C-06 (aplicar-canonico): corregido en fix/hallazgos-qa, sale XPASS(strict) y se quita el xfail.
    async def test_un_anonimo_no_crea_un_pedido_a_nombre_de_otro_usuario(self, entorno):
        await _publicado(entorno)

        await entorno.http.post(
            "/v1/trabajos/aplicar-canonico",
            json={
                "colegio_id": COLEGIO,
                "grado": "Cuarto",
                "anio_lectivo": 2026,
                "perfil": "Ahorrador",
                "usuario_id": str(ACUDIENTE_ID),
            },
        )

        async with entorno.motor.engine.begin() as conexion:
            suplantados = (
                await conexion.execute(
                    select(trabajos.TRABAJO.c.id).where(trabajos.TRABAJO.c.usuario_id == ACUDIENTE_ID)
                )
            ).all()
        assert suplantados == []

    async def test_con_sesion_el_dueno_del_pedido_es_el_de_la_sesion_aunque_el_cuerpo_diga_otro(
        self, entorno
    ):
        await _publicado(entorno)

        respuesta = await entorno.http.post(
            "/v1/trabajos/aplicar-canonico",
            json={
                "colegio_id": COLEGIO,
                "grado": "Cuarto",
                "anio_lectivo": 2026,
                "perfil": "Ahorrador",
                "usuario_id": str(FIRMANTE_FALSO),
            },
            headers=ACUDIENTE,
        )

        assert respuesta.status_code == 201
        async with entorno.motor.engine.begin() as conexion:
            dueno = await conexion.scalar(
                select(trabajos.TRABAJO.c.usuario_id).where(
                    trabajos.TRABAJO.c.id == uuid.UUID(respuesta.json()["trabajo_id"])
                )
            )
        assert dueno == ACUDIENTE_ID

    async def test_un_perfil_sin_cache_publicada_es_404_cache_no_existe(self, entorno):
        respuesta = await entorno.http.post(
            "/v1/trabajos/aplicar-canonico",
            json={"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026, "perfil": "Ahorrador"},
        )

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "cache_no_existe"


class TestTopeDeArchivo:
    """El contrato promete 10 MB (CONTRATO_API.md:171-175) y hoy solo lo valida el navegador."""

    # H-C-07 (tope de 10 MB): corregido en fix/hallazgos-qa, sale XPASS(strict) y se quita el xfail.
    async def test_una_subida_de_mas_de_10_mb_se_rechaza_sin_percibirla(self, entorno):
        grande = b"%PDF-" + b"0" * TOPE_ARCHIVO

        respuesta = await entorno.http.post("/v1/listas/subir", **_subida([HIJO], archivo=grande))

        assert respuesta.status_code in (413, 422)
        assert entorno.lecturas == [] and entorno.catalogo.importadas == []

    # H-C-07 (tope de 10 MB): corregido en fix/hallazgos-qa, sale XPASS(strict) y se quita el xfail.
    async def test_un_onboarding_de_mas_de_10_mb_se_rechaza_sin_percibirlo(self, entorno):
        grande = b"%PDF-" + b"0" * TOPE_ARCHIVO

        respuesta = await entorno.http.post(
            "/v1/admin/onboarding",
            data={"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": "2026"},
            files=[("archivo", ("lista.pdf", grande, "application/pdf"))],
            headers=OPERADOR,
        )

        assert respuesta.status_code in (413, 422)
        assert entorno.lecturas == [] and entorno.catalogo.importadas == []

    async def test_un_archivo_de_exactamente_10_mb_se_acepta(self, entorno):
        """El tope es inclusivo: 10 MB justos es un archivo valido para el contrato."""
        justo = b"%PDF-" + b"0" * (TOPE_ARCHIVO - 5)

        respuesta = await entorno.http.post("/v1/listas/subir", **_subida([HIJO], archivo=justo))

        assert respuesta.status_code == 202
        assert len(entorno.catalogo.importadas) == 1
