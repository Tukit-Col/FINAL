"""La subida de listas con el catalogo caido (H-B-01, ADR 0040).

Antes, `POST /v1/listas/subir` percibia cada PDF y lo importaba al catalogo en
la misma peticion. Con el catalogo caido el `RemotoCaido` salia sin manejar: el
acudiente recibia un 500 y la lista, ya percibida, se perdia.

Lo que se fija aqui:

- con el catalogo caido la subida responde 202, cada hijo queda `pendiente` y
  lo percibido (renglones, percepcion cruda y PDF) queda guardado en
  `importacion_lista`;
- cuando el catalogo vuelve, el trabajador la importa una sola vez, con lo ya
  percibido y sin volver a percibir;
- dos reintentos, o una respuesta que se perdio, dan una sola version: cada
  destino viaja con la misma `clave_idempotencia`;
- con el catalogo arriba la respuesta es la de siempre y la fila queda
  `importada`, sin el PDF.
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from test_subir_listas import COLEGIO, CatalogoImportador, IdentidadDoble, _subida
from tukit_inteligencia import api, importaciones, trabajador, trabajos
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import Base
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida
from tukit_inteligencia.remoto import RemotoCaido

IMPORTACION = Base.metadata.tables["importacion_lista"]
PADRE = uuid.UUID("33333333-3333-5333-8333-333333333333")
PDF = b"%PDF-falso"


def _despues() -> datetime:
    """Un momento en que cualquier espera de reintento ya vencio."""
    return datetime.now(UTC) + timedelta(hours=1)


def _con_zona(momento: datetime) -> datetime:
    """SQLite devuelve las fechas sin zona; se guardaron en UTC."""
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


class CatalogoIntermitente(CatalogoImportador):
    """El catalogo que se cae y vuelve, con la idempotencia del de verdad.

    Con `caido`, cada importacion lanza el `RemotoCaido` que lanza el cliente
    cuando el catalogo no responde. Con una clave ya vista devuelve la version
    que ya tenia, como `POST /v1/admin/listas/importar`. `llamadas` solo cuenta
    las importaciones que de verdad crearon una version; `intentos`, todas.
    """

    def __init__(self) -> None:
        super().__init__()
        self.caido = False
        self.rechazo: int | None = None
        self.perder_respuesta = False
        self.intentos: list[str | None] = []
        self._por_clave: dict[str, dict] = {}

    async def importar_lista(self, *, clave_idempotencia: str | None = None, **kw) -> dict:
        self.intentos.append(clave_idempotencia)
        if self.caido:
            raise RemotoCaido(
                "catalogo", "/v1/admin/listas/importar no respondio (All connection attempts failed)"
            )
        if self.rechazo is not None:
            raise RemotoCaido(
                "catalogo", f"/v1/admin/listas/importar respondio {self.rechazo}", estado=self.rechazo
            )
        if clave_idempotencia is not None and clave_idempotencia in self._por_clave:
            return self._por_clave[clave_idempotencia]
        respuesta = await super().importar_lista(clave_idempotencia=clave_idempotencia, **kw)
        if clave_idempotencia is not None:
            self._por_clave[clave_idempotencia] = respuesta
        if self.perder_respuesta:
            # La importacion entro, pero la respuesta no llego (un timeout).
            self.perder_respuesta = False
            raise RemotoCaido("catalogo", "/v1/admin/listas/importar no respondio (ReadTimeout)")
        return respuesta

    async def listas_por_contacto(self, _contacto: str) -> list[dict]:
        if self.caido:
            raise RemotoCaido("catalogo", "/v1/admin/listas no respondio")
        return []


@pytest.fixture()
def catalogo():
    return CatalogoIntermitente()


@pytest.fixture()
def identidad():
    return IdentidadDoble(usuario_id=str(PADRE))


@pytest.fixture()
def lecturas():
    """Cuantas paginas se le pidieron al modelo: la percepcion es la etapa cara."""
    return {"n": 0}


@pytest.fixture()
async def cliente(motor, catalogo, identidad, lecturas, monkeypatch):
    app.state.motor = motor
    app.state.catalogo = catalogo
    app.state.identidad = identidad

    def _leer(_png: bytes, _numero: int) -> PaginaLeida:
        lecturas["n"] += 1
        return PaginaLeida(
            grados=["Cuarto"],
            completa=True,
            items=[
                ItemExtraido(descripcion="2 cuadernos cuadriculados", cantidad=2, confianza=0.91),
                ItemExtraido(descripcion="1 caja de colores", cantidad=None, confianza=0.8),
            ],
        )

    monkeypatch.setattr(api, "_RENDERIZAR", lambda _contenido: [b"p1"])
    monkeypatch.setattr(api, "_LEER", _leer)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http


async def _filas(motor) -> list:
    async with motor.engine.begin() as conexion:
        return list(await conexion.execute(select(IMPORTACION).order_by(IMPORTACION.c.creado_en)))


def _un_hijo(**extra) -> dict:
    hijo = {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}
    hijo.update(extra)
    return hijo


class TestConElCatalogoCaido:
    async def test_responde_202_y_el_hijo_queda_pendiente(self, cliente, catalogo):
        catalogo.caido = True
        respuesta = await cliente.post(
            "/v1/listas/subir", **_subida([_un_hijo()], contacto={"correo": "mama@ejemplo.com"})
        )

        assert respuesta.status_code == 202
        env = respuesta.json()
        assert env["subidas"] == [
            {"referencia": "hijo-1", "version_id": None, "grado": "Cuarto", "estado": "pendiente"}
        ]
        assert env["contacto_referencia"] == str(PADRE)
        assert catalogo.llamadas == []

    async def test_lo_percibido_queda_guardado(self, cliente, catalogo, motor):
        catalogo.caido = True
        preferencias = {"pesos": {"precio": 0.7, "calidad": 0.3}}
        await cliente.post(
            "/v1/listas/subir",
            **_subida([_un_hijo()], contacto={"correo": "mama@ejemplo.com"}, preferencias=preferencias),
        )

        [fila] = await _filas(motor)
        assert fila.estado == "pendiente"
        assert fila.referencias == ["hijo-1"]
        assert fila.colegio_id == COLEGIO
        assert fila.grado == "Cuarto"
        assert fila.anio_lectivo == 2026
        assert fila.contacto_referencia == str(PADRE)
        assert fila.documento == PDF
        assert [i["texto_original"] for i in fila.carga["items"]] == [
            "2 cuadernos cuadriculados",
            "1 caja de colores",
        ]
        assert fila.carga["percepcion_cruda"]
        assert fila.carga["preferencias"] == preferencias
        assert fila.carga["origen"] == "sugerencia_padre"
        assert fila.intentos == 1
        assert "no respondio" in fila.error
        assert fila.version_id is None

    async def test_la_respuesta_no_repite_el_archivo(self, cliente, catalogo):
        catalogo.caido = True
        marcador = b"%PDF-marcador-secreto-del-cliente"
        respuesta = await cliente.post(
            "/v1/listas/subir", **_subida([_un_hijo()], archivos=[("hijo-1", marcador)])
        )

        assert respuesta.status_code == 202
        assert "marcador-secreto" not in respuesta.text
        assert base64.b64encode(marcador).decode() not in respuesta.text

    async def test_dos_hijos_del_mismo_destino_comparten_una_fila(self, cliente, catalogo, motor):
        catalogo.caido = True
        respuesta = await cliente.post(
            "/v1/listas/subir",
            **_subida([_un_hijo(), _un_hijo(referencia="hijo-2")], contacto={"correo": "mama@ejemplo.com"}),
        )

        assert respuesta.status_code == 202
        assert [s["estado"] for s in respuesta.json()["subidas"]] == ["pendiente", "pendiente"]
        [fila] = await _filas(motor)
        assert fila.referencias == ["hijo-1", "hijo-2"]

        catalogo.caido = False
        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues()) == 1
        assert len(catalogo.llamadas) == 1

    async def test_al_primer_destino_caido_no_insiste_con_el_resto(self, cliente, catalogo, motor):
        # Con el catalogo caido cada intento puede costar el tiempo de espera
        # entero del cliente: la peticion no los encadena. El resto queda
        # pendiente, listo para el trabajador.
        catalogo.caido = True
        respuesta = await cliente.post(
            "/v1/listas/subir",
            **_subida(
                [_un_hijo(), _un_hijo(referencia="hijo-2", grado="Quinto", colegio_id=str(uuid.uuid4()))]
            ),
        )

        assert respuesta.status_code == 202
        assert len(catalogo.intentos) == 1
        filas = await _filas(motor)
        assert {f.estado for f in filas} == {"pendiente"}
        # Las dos quedan para dentro de segundos, no para cuando venza la
        # reserva de la peticion.
        pronto = datetime.now(UTC) + timedelta(seconds=30)
        assert all(_con_zona(f.proximo_intento_en) < pronto for f in filas)


class TestCuandoElCatalogoVuelve:
    async def test_el_trabajador_la_importa_una_vez_con_lo_ya_percibido(
        self, cliente, catalogo, motor, lecturas
    ):
        catalogo.caido = True
        await cliente.post(
            "/v1/listas/subir", **_subida([_un_hijo()], contacto={"correo": "mama@ejemplo.com"})
        )
        assert lecturas["n"] == 1
        [pendiente] = await _filas(motor)

        catalogo.caido = False
        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues()) == 1

        # Una importacion, con lo que se percibio en la subida: sin volver a leer.
        assert lecturas["n"] == 1
        [llamada] = catalogo.llamadas
        assert llamada["colegio_id"] == COLEGIO
        assert llamada["grado"] == "Cuarto"
        assert llamada["anio_lectivo"] == 2026
        assert llamada["items"] == pendiente.carga["items"]
        assert llamada["percepcion_cruda"] == pendiente.carga["percepcion_cruda"]
        assert base64.b64decode(llamada["documento_base64"]) == PDF
        assert llamada["contacto_referencia"] == str(PADRE)
        assert llamada["origen"] == "sugerencia_padre"
        assert llamada["clave_idempotencia"] == str(pendiente.clave_idempotencia)

        [fila] = await _filas(motor)
        assert fila.estado == "importada"
        assert fila.version_id == "ver-1"
        # Ya esta en el catalogo: aca no queda copia del PDF ni de lo percibido.
        assert fila.documento is None
        assert fila.carga is None

    async def test_dos_reintentos_dan_una_sola_version(self, cliente, catalogo, motor):
        catalogo.caido = True
        await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))
        catalogo.caido = False

        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues()) == 1
        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues()) == 0
        assert len(catalogo.llamadas) == 1
        assert len(catalogo.intentos) == 2  # el de la subida y el del reintento

    async def test_una_respuesta_perdida_no_duplica_la_version(self, cliente, catalogo, motor):
        # La importacion entra al catalogo pero la respuesta se pierde: la
        # subida la deja pendiente y el reintento manda la MISMA clave, asi que
        # el catalogo devuelve la version que ya tenia en vez de crear otra.
        catalogo.perder_respuesta = True
        respuesta = await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))
        assert respuesta.json()["subidas"][0]["estado"] == "pendiente"

        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues()) == 1
        assert len(catalogo.llamadas) == 1
        assert catalogo.intentos[0] == catalogo.intentos[1]
        [fila] = await _filas(motor)
        assert (fila.estado, fila.version_id) == ("importada", "ver-1")

    async def test_si_sigue_caido_la_espera_se_duplica_con_tope(self, cliente, catalogo, motor):
        catalogo.caido = True
        await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))
        [fila] = await _filas(motor)
        assert fila.intentos == 1

        momento = _despues()
        for espera in (10, 20, 40, 80, 160, 300, 300):
            assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=momento) == 0
            [fila] = await _filas(motor)
            assert fila.estado == "pendiente"
            assert _con_zona(fila.proximo_intento_en) == momento + timedelta(seconds=espera)
            momento += timedelta(seconds=espera)

    async def test_con_el_catalogo_caido_una_pasada_hace_un_solo_intento(self, cliente, catalogo, motor):
        catalogo.caido = True
        await cliente.post(
            "/v1/listas/subir",
            **_subida([_un_hijo(), _un_hijo(referencia="hijo-2", colegio_id=str(uuid.uuid4()))]),
        )
        assert len(catalogo.intentos) == 1

        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues()) == 0
        assert len(catalogo.intentos) == 2

    async def test_no_toma_una_fila_cuya_espera_no_vencio(self, cliente, catalogo, motor):
        catalogo.caido = True
        await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))
        catalogo.caido = False
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                update(IMPORTACION).values(proximo_intento_en=datetime.now(UTC) + timedelta(minutes=5))
            )

        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo) == 0
        assert catalogo.llamadas == []

    async def test_la_vuelta_del_trabajador_reintenta_las_pendientes(
        self, cliente, catalogo, motor, monkeypatch
    ):
        catalogo.caido = True
        await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))
        catalogo.caido = False
        async with motor.engine.begin() as conexion:
            await conexion.execute(update(IMPORTACION).values(proximo_intento_en=datetime.now(UTC)))

        import tukit_comun.bd

        monkeypatch.setattr(tukit_comun.bd, "crear_motor", lambda _servicio: motor)
        monkeypatch.setattr(trabajador, "ClienteCatalogo", lambda: catalogo)
        await trabajador.correr_una_vez()

        assert len(catalogo.llamadas) == 1


class TestConElCatalogoArriba:
    async def test_la_respuesta_es_la_de_siempre_y_la_fila_queda_importada(self, cliente, catalogo, motor):
        respuesta = await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))

        assert respuesta.status_code == 202
        assert respuesta.json()["subidas"] == [
            {"referencia": "hijo-1", "version_id": "ver-1", "grado": "Cuarto"}
        ]
        [fila] = await _filas(motor)
        assert (fila.estado, fila.version_id, fila.intentos) == ("importada", "ver-1", 1)
        assert fila.documento is None
        assert catalogo.llamadas[0]["clave_idempotencia"] == str(fila.clave_idempotencia)
        # Nada queda para el trabajador.
        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues()) == 0
        assert len(catalogo.llamadas) == 1

    async def test_cada_destino_lleva_su_propia_clave(self, cliente, catalogo):
        await cliente.post(
            "/v1/listas/subir",
            **_subida([_un_hijo(), _un_hijo(referencia="hijo-2", colegio_id=str(uuid.uuid4()))]),
        )
        claves = [ll["clave_idempotencia"] for ll in catalogo.llamadas]
        assert len(claves) == 2
        assert len(set(claves)) == 2

    async def test_dos_subidas_iguales_son_dos_claves(self, cliente, catalogo):
        # La clave es por subida y destino: un acudiente que vuelve a subir la
        # misma lista hace una version nueva, igual que antes.
        await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))
        await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))
        assert len({ll["clave_idempotencia"] for ll in catalogo.llamadas}) == 2


class TestUnRechazoDelCatalogo:
    async def test_queda_fallida_y_no_se_reintenta(self, cliente, catalogo, motor):
        # Un 4xx no es una caida: reintentarlo daria lo mismo. Sale como antes
        # y la fila queda con su diagnostico.
        catalogo.rechazo = 422
        with pytest.raises(RemotoCaido):
            await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))

        [fila] = await _filas(motor)
        assert fila.estado == "fallida"
        assert "422" in fila.error

        catalogo.rechazo = None
        assert await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues()) == 0
        assert catalogo.llamadas == []

    @pytest.mark.parametrize("estado", [408, 429, 502, 503])
    async def test_un_408_429_o_5xx_si_es_caida(self, cliente, catalogo, motor, estado):
        catalogo.rechazo = estado
        respuesta = await cliente.post("/v1/listas/subir", **_subida([_un_hijo()]))

        assert respuesta.status_code == 202
        [fila] = await _filas(motor)
        assert fila.estado == "pendiente"


class TestMisSolicitudes:
    async def test_la_pendiente_sale_como_recibida_sin_tarea(self, cliente, catalogo, motor):
        catalogo.caido = True
        await cliente.post(
            "/v1/listas/subir",
            **_subida(
                [{"referencia": "hijo-1", "colegio_nombre": "Gimnasio Ficticio", "grado": "Cuarto"}],
                contacto={"correo": "mama@ejemplo.com"},
            ),
        )

        # Con el catalogo todavia caido: las listas del catalogo no estan, pero
        # la que espera aca si.
        env = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)
        assert env["listas_disponibles"] is False
        [solicitud] = env["solicitudes"]
        assert solicitud["tipo"] == "recibida"
        assert solicitud["tarea_id"] is None
        assert solicitud["colegio_nombre"] == "Gimnasio Ficticio"
        assert solicitud["grado"] == "Cuarto"

        # Ya importada, la muestra el catalogo y no sale dos veces de aca.
        catalogo.caido = False
        await importaciones.reintentar_pendientes(motor, catalogo=catalogo, ahora=_despues())
        env = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)
        assert env["solicitudes"] == []

    async def test_no_muestra_las_de_otro_acudiente(self, cliente, catalogo, motor):
        catalogo.caido = True
        await cliente.post(
            "/v1/listas/subir", **_subida([_un_hijo()], contacto={"correo": "mama@ejemplo.com"})
        )

        env = await trabajos.mis_solicitudes(motor, uuid.uuid4(), catalogo=catalogo)
        assert env["solicitudes"] == []
