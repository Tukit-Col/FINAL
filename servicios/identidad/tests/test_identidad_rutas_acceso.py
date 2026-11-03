"""NFR-MAN-01: el control de acceso y el alcance de los datos de las rutas HTTP de Identidad.

Las rutas de Identidad exponen el unico dato de menor que sale por la superficie
publica (el apodo del hijo) y el unico nombre de adulto en claro, asi que lo que
hay que fijar es QUIEN puede llamarlas y QUE ve cada quien:

- 401 sin testigo (token): ninguna ruta protegida responde sin sesion valida, y
  una peticion rechazada no escribe nada; el token alterado, vencido, revocado
  (`version_permisos`), de una cuenta dada de baja o de un usuario que no existe
  tampoco abre nada;
- 403 sin rol: el padron de acudientes es solo del equipo interno vigente
  (admin/operador; un rol caducado o `colegio_admin` no basta) y los nombres de
  adultos exigen `usuario:leer:nombre`; el orden de las puertas es token, luego
  rol, luego forma de la entrada (un `?ids=` mal formado sin token sigue siendo 401);
- alcance por actor: cada acudiente ve solo SUS hijos, SUS matriculas y SUS
  direcciones (una direccion ajena es 404, no 403: no se confirma que exista); el
  padron no incluye staff, invitados ni cuentas dadas de baja y no trae claves;
  `nombres` nunca resuelve el id de un menor;
- el alta publica (`/v1/registro`, `/v1/cuenta`, `/v1/contactos`) no muta una
  cuenta real ni deja a medias una transaccion que falla;
- el catalogo institucional (`/v1/colegios`, `/v1/directorio`, `/v1/grados`) y su
  edicion (`PATCH`), cuyas puertas HOY no existen (H-C-06, ver los xfail).

Un xfail estricto marca cada conducta que contradice el contrato o el control de
acceso esperado; cuando el producto se corrija, el xfail fallara y obligara a
quitarlo. La app es la global de `tukit_identidad.api` sobre SQLite en memoria
(`StaticPool`); `raise_app_exceptions=False` permite ver un 500 como respuesta en
vez de como excepcion. Todos los nombres, apodos y correos son ficticios.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun import derivar
from tukit_comun.bd import MotorServicio
from tukit_comun.cifrado import VARIABLE_LLAVE as VARIABLE_CIFRADO
from tukit_comun.cifrado import CifradorEnClaro
from tukit_comun.http import ErrorDominio
from tukit_identidad.api import app
from tukit_identidad.dominio.sesiones import VIDA_SEGUNDOS, emitir_token, hashear_clave
from tukit_identidad.modelos import (
    AcudienteMatricula,
    AsignacionRol,
    Base,
    Clasificacion,
    Colegio,
    Estudiante,
    Matricula,
    Permiso,
    Rol,
    RolPermiso,
    Sede,
    Usuario,
)
from tukit_identidad.routers import identidad as rutas

pytestmark = pytest.mark.nfr("NFR-MAN-01")

T = Base.metadata.tables
_EN_CLARO = CifradorEnClaro()
CLAVE = "clave-ficticia-1"
DANE_REAL = "311001105731"  # directorio publico de instituciones (no es dato de menores)


@pytest.fixture(scope="module")
def clave_hash() -> str:
    """PBKDF2 es lento a proposito: se calcula una vez por modulo."""
    return hashear_clave(CLAVE)


@dataclass
class Mundo:
    """Una base con dos colegios, dos familias y el personal interno, y su cliente."""

    http: httpx.AsyncClient
    fabrica: async_sessionmaker[AsyncSession]
    ids: dict[str, uuid.UUID]
    colegio_a: uuid.UUID
    colegio_b: uuid.UUID
    sede_a: uuid.UUID
    sede_b: uuid.UUID
    estudiante_mama: uuid.UUID

    def token(self, quien: str, version: int = 1) -> str:
        return emitir_token(self.ids[quien], version_permisos=version)

    def con(self, quien: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(quien)}"}

    async def contar(self, tabla: str) -> int:
        async with self.fabrica() as s:
            return int(await s.scalar(select(func.count()).select_from(T[tabla])))

    async def filas(self, tabla: str) -> list[Any]:
        async with self.fabrica() as s:
            return list((await s.execute(select(T[tabla]))).all())

    async def ejecutar(self, sentencia: Any) -> None:
        async with self.fabrica() as s:
            await s.execute(sentencia)
            await s.commit()


def _claro(texto: str) -> bytes:
    return _EN_CLARO.cifrar(texto.encode("utf-8"))


@pytest.fixture
async def mundo(monkeypatch: pytest.MonkeyPatch, clave_hash: str) -> AsyncIterator[Mundo]:
    monkeypatch.delenv(VARIABLE_CIFRADO, raising=False)
    monkeypatch.setenv("TUKIT_LLAVE_SESION", "llave-de-prueba-ficticia-no-es-un-secreto")
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    ahora = datetime.now(UTC)

    async with fabrica() as s:
        s.add_all(
            [
                Rol(codigo=codigo, nombre=codigo, del_sistema=True)
                for codigo in ("admin", "operador", "acudiente", "colegio_admin")
            ]
        )
        s.add(
            Permiso(
                codigo="usuario:leer:nombre",
                recurso="usuario",
                accion="leer",
                campo="nombre",
                clasificacion_minima=Clasificacion.PERSONAL.value,
            )
        )
        await s.flush()
        s.add_all(
            [
                RolPermiso(rol_codigo="admin", permiso_codigo="usuario:leer:nombre"),
                RolPermiso(rol_codigo="operador", permiso_codigo="usuario:leer:nombre"),
            ]
        )
        colegio_a = Colegio(nombre="Colegio Ficticio Uno")
        colegio_b = Colegio(nombre="Colegio Ficticio Dos")
        s.add_all([colegio_a, colegio_b])
        await s.flush()
        sede_a = Sede(colegio_id=colegio_a.id, nombre="Sede Ficticia Uno")
        sede_b = Sede(colegio_id=colegio_b.id, nombre="Sede Ficticia Dos")
        s.add_all([sede_a, sede_b])

        usuarios = {
            "admin": Usuario(correo="admin@example.test", clave_hash=clave_hash),
            "operador": Usuario(correo="operador@example.test", clave_hash=clave_hash),
            "exadmin": Usuario(correo="exadmin@example.test", clave_hash=clave_hash),
            "colegio_admin": Usuario(correo="colegio.admin@example.test", clave_hash=clave_hash),
            "mama": Usuario(
                correo="mama@example.test",
                clave_hash=clave_hash,
                nombre_cifrado=_claro("Acudiente Ficticio Uno"),
                celular="3000000000",
            ),
            "papa": Usuario(
                correo="papa@example.test",
                clave_hash=clave_hash,
                nombre_cifrado=_claro("Acudiente Ficticio Dos"),
            ),
            "invitado": Usuario(correo="invitado@example.test", clave_hash="sin-credencial"),
            "baja": Usuario(correo="baja@example.test", clave_hash=clave_hash, activo=False),
        }
        s.add_all(usuarios.values())
        await s.flush()

        s.add_all(
            [
                AsignacionRol(usuario_id=usuarios["admin"].id, rol_codigo="admin", ambito_tipo="global"),
                AsignacionRol(
                    usuario_id=usuarios["operador"].id, rol_codigo="operador", ambito_tipo="global"
                ),
                AsignacionRol(
                    usuario_id=usuarios["exadmin"].id,
                    rol_codigo="admin",
                    ambito_tipo="global",
                    vigente_desde=ahora - timedelta(days=9),
                    vigente_hasta=ahora - timedelta(days=1),
                ),
                AsignacionRol(
                    usuario_id=usuarios["colegio_admin"].id,
                    rol_codigo="colegio_admin",
                    ambito_tipo="colegio",
                    ambito_id=colegio_a.id,
                ),
                AsignacionRol(
                    usuario_id=usuarios["mama"].id,
                    rol_codigo="acudiente",
                    ambito_tipo="colegio",
                    ambito_id=colegio_a.id,
                ),
                AsignacionRol(
                    usuario_id=usuarios["papa"].id,
                    rol_codigo="acudiente",
                    ambito_tipo="colegio",
                    ambito_id=colegio_b.id,
                ),
            ]
        )

        estudiantes = {
            "mama": Estudiante(nombre_cifrado=_claro("Estudiante Ficticio Uno")),
            "papa": Estudiante(nombre_cifrado=_claro("Estudiante Ficticio Dos")),
        }
        s.add_all(estudiantes.values())
        await s.flush()
        destino = {
            "mama": (sede_a, "Quinto", "Estudiante Ficticio Uno"),
            "papa": (sede_b, "Tercero", "Estudiante Ficticio Dos"),
        }
        for dueno, (sede, grado, apodo) in destino.items():
            matricula = Matricula(
                estudiante_id=estudiantes[dueno].id,
                sede_id=sede.id,
                colegio_id=sede.colegio_id,
                grado=grado,
                anio_lectivo=2026,
            )
            s.add(matricula)
            await s.flush()
            s.add(
                AcudienteMatricula(
                    usuario_id=usuarios[dueno].id, matricula_id=matricula.id, apodo_cifrado=_claro(apodo)
                )
            )
        await s.commit()
        mundo_ids = {nombre: u.id for nombre, u in usuarios.items()}
        datos = (colegio_a.id, colegio_b.id, sede_a.id, sede_b.id, estudiantes["mama"].id)

    monkeypatch.setattr(
        app.state, "motor", MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica), raising=False
    )
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        yield Mundo(http, fabrica, mundo_ids, *datos)
    await engine.dispose()


def _codigo(respuesta: httpx.Response) -> str:
    return respuesta.json()["error"]


_OTRO_ID = uuid.uuid4()
_DIRECCION = {"ciudad": "Ciudad Ficticia", "linea": "Calle Ficticia 1 # 2-3"}
_HIJO = {
    "apodo": "Estudiante Ficticio Tres",
    "colegio_id": str(uuid.uuid4()),
    "sede_id": str(uuid.uuid4()),
    "grado": "Quinto",
    "anio_lectivo": 2026,
    "consentimiento": True,
}
_PROTEGIDAS: list[tuple[str, str, dict | None]] = [
    ("GET", "/v1/sesiones/actual", None),
    ("GET", "/v1/cuenta", None),
    ("GET", "/v1/cuenta/hijos", None),
    ("POST", "/v1/cuenta/hijos", _HIJO),
    ("GET", "/v1/cuenta/matriculas", None),
    ("POST", "/v1/cuenta/matriculas", {"hijos": [{"colegio_id": str(_OTRO_ID), "grado": "Quinto"}]}),
    ("GET", "/v1/cuenta/direcciones", None),
    ("POST", "/v1/cuenta/direcciones", _DIRECCION),
    ("PATCH", f"/v1/cuenta/direcciones/{_OTRO_ID}", _DIRECCION),
    ("DELETE", f"/v1/cuenta/direcciones/{_OTRO_ID}", None),
    ("GET", "/v1/admin/acudientes", None),
    ("GET", f"/v1/usuarios/nombres?ids={_OTRO_ID}", None),
]
_TABLAS_DE_ESCRITURA = (
    "usuario",
    "direccion",
    "estudiante",
    "matricula",
    "acudiente_matricula",
    "consentimiento",
)


class TestSinTestigo401:
    @pytest.mark.parametrize(
        ("metodo", "ruta", "cuerpo"), _PROTEGIDAS, ids=[f"{m} {r.split('?')[0]}" for m, r, _ in _PROTEGIDAS]
    )
    async def test_ninguna_ruta_protegida_responde_sin_token_y_no_escribe_nada(
        self, mundo: Mundo, metodo: str, ruta: str, cuerpo: dict | None
    ):
        antes = {tabla: await mundo.contar(tabla) for tabla in _TABLAS_DE_ESCRITURA}

        respuesta = await mundo.http.request(metodo, ruta, json=cuerpo)

        assert respuesta.status_code == 401
        assert _codigo(respuesta) == "sesion_invalida"
        assert {tabla: await mundo.contar(tabla) for tabla in _TABLAS_DE_ESCRITURA} == antes

    async def test_un_token_con_la_firma_alterada_no_abre_la_cuenta(self, mundo: Mundo):
        cuerpo, firma = mundo.token("mama").split(".")
        alterada = f"{cuerpo}.{firma[:-2]}{'AA' if not firma.endswith('AA') else 'BB'}"

        respuesta = await mundo.http.get("/v1/cuenta", headers={"Authorization": f"Bearer {alterada}"})

        assert respuesta.status_code == 401
        assert _codigo(respuesta) == "sesion_invalida"

    async def test_un_token_de_otro_usuario_con_el_cuerpo_cambiado_no_abre_la_cuenta_ajena(
        self, mundo: Mundo
    ):
        """Cambiar el `sub` del cuerpo sin recalcular la firma no sirve para suplantar."""
        cuerpo_papa, _ = mundo.token("papa").split(".")
        _, firma_mama = mundo.token("mama").split(".")

        respuesta = await mundo.http.get(
            "/v1/cuenta", headers={"Authorization": f"Bearer {cuerpo_papa}.{firma_mama}"}
        )

        assert respuesta.status_code == 401

    @pytest.mark.parametrize("basura", ["no-es-un-token", "a.b.c", ".", "Bearer", "Bearer "])
    async def test_un_encabezado_con_basura_es_401_y_no_error_del_servidor(self, mundo: Mundo, basura: str):
        respuesta = await mundo.http.get("/v1/cuenta", headers={"Authorization": basura})

        assert respuesta.status_code == 401
        assert _codigo(respuesta) == "sesion_invalida"

    async def test_un_token_vencido_es_401(self, mundo: Mundo):
        vencido = emitir_token(mundo.ids["mama"], 1, ahora=time.time() - VIDA_SEGUNDOS - 60)

        respuesta = await mundo.http.get("/v1/cuenta", headers={"Authorization": f"Bearer {vencido}"})

        assert respuesta.status_code == 401
        assert _codigo(respuesta) == "sesion_invalida"

    async def test_un_token_de_un_usuario_que_no_existe_es_401(self, mundo: Mundo):
        huerfano = emitir_token(uuid.uuid4(), 1)

        respuesta = await mundo.http.get("/v1/cuenta", headers={"Authorization": f"Bearer {huerfano}"})

        assert respuesta.status_code == 401
        assert _codigo(respuesta) == "sesion_invalida"

    async def test_una_cuenta_dada_de_baja_pierde_el_acceso_aunque_su_token_siga_vigente(self, mundo: Mundo):
        respuesta = await mundo.http.get("/v1/cuenta", headers=mundo.con("baja"))

        assert respuesta.status_code == 401
        assert respuesta.json()["mensaje"] == "La cuenta ya no esta activa."

    async def test_subir_la_version_de_permisos_revoca_los_tokens_anteriores(self, mundo: Mundo):
        viejo = mundo.con("mama")
        assert (await mundo.http.get("/v1/cuenta", headers=viejo)).status_code == 200

        await mundo.ejecutar(
            update(Usuario).where(Usuario.id == mundo.ids["mama"]).values(version_permisos=2)
        )

        revocado = await mundo.http.get("/v1/cuenta", headers=viejo)
        nuevo = await mundo.http.get(
            "/v1/cuenta", headers={"Authorization": f"Bearer {mundo.token('mama', version=2)}"}
        )
        assert revocado.status_code == 401
        assert _codigo(revocado) == "sesion_revocada"
        assert nuevo.status_code == 200

    async def test_un_admin_revocado_tampoco_lee_el_padron(self, mundo: Mundo):
        viejo = mundo.con("admin")
        await mundo.ejecutar(
            update(Usuario).where(Usuario.id == mundo.ids["admin"]).values(version_permisos=2)
        )

        respuesta = await mundo.http.get("/v1/admin/acudientes", headers=viejo)

        assert respuesta.status_code == 401
        assert _codigo(respuesta) == "sesion_revocada"

    async def test_el_encabezado_sin_la_palabra_bearer_tambien_se_acepta(self, mundo: Mundo):
        """Caracterizacion de un parser laxo (`_token_del_encabezado`): el token
        solo, sin `Bearer`, se toma como valido. La firma sigue mandando, asi que
        no abre nada que un token valido no abriera."""
        respuesta = await mundo.http.get("/v1/cuenta", headers={"Authorization": mundo.token("mama")})

        assert respuesta.status_code == 200
        assert respuesta.json()["correo"] == "mama@example.test"

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-17: un token con caracteres no ASCII revienta en leer_token (cuerpo.encode('ascii') "
            "y compare_digest, sesiones.py:150-151) y la ruta responde 500 en vez de 401; el docstring "
            "(sesiones.py:140-146) promete que un token de forma rara devuelve None"
        ),
    )
    async def test_un_token_con_caracteres_no_ascii_es_401_y_no_un_error_del_servidor(self, mundo: Mundo):
        respuesta = await mundo.http.get(
            "/v1/cuenta", headers={"Authorization": "Bearer ñandú.firma".encode("latin-1")}
        )

        assert respuesta.status_code == 401


class TestSinRol403:
    async def test_un_acudiente_no_lee_el_padron_de_acudientes(self, mundo: Mundo):
        respuesta = await mundo.http.get("/v1/admin/acudientes", headers=mundo.con("mama"))

        assert respuesta.status_code == 403
        assert _codigo(respuesta) == "acceso_denegado"
        assert "papa@example.test" not in respuesta.text

    @pytest.mark.parametrize("quien", ["colegio_admin", "exadmin", "invitado"])
    async def test_ni_el_rol_de_colegio_ni_un_admin_caducado_ni_un_invitado_leen_el_padron(
        self, mundo: Mundo, quien: str
    ):
        """Un token firmado de un invitado (o de quien fue admin) existe; lo que
        decide es el rol VIGENTE del usuario, no el token."""
        respuesta = await mundo.http.get("/v1/admin/acudientes", headers=mundo.con(quien))

        assert respuesta.status_code == 403
        assert _codigo(respuesta) == "acceso_denegado"

    @pytest.mark.parametrize("quien", ["admin", "operador"])
    async def test_el_equipo_interno_vigente_si_lee_el_padron(self, mundo: Mundo, quien: str):
        respuesta = await mundo.http.get("/v1/admin/acudientes", headers=mundo.con(quien))

        assert respuesta.status_code == 200
        assert respuesta.json()["total"] == 3  # mama, papa y el exadmin (sin rol interno vigente)

    @pytest.mark.parametrize("quien", ["mama", "colegio_admin", "exadmin"])
    async def test_sin_el_permiso_de_leer_nombres_no_se_resuelve_ningun_nombre(
        self, mundo: Mundo, quien: str
    ):
        respuesta = await mundo.http.get(
            "/v1/usuarios/nombres", params={"ids": str(mundo.ids["papa"])}, headers=mundo.con(quien)
        )

        assert respuesta.status_code == 403
        assert _codigo(respuesta) == "sin_permiso"
        assert "Acudiente Ficticio" not in respuesta.text

    async def test_las_puertas_van_en_orden_token_rol_y_despues_la_forma_de_los_ids(self, mundo: Mundo):
        sin_token = await mundo.http.get("/v1/admin/acudientes", params={"ids": "no-es-uuid"})
        sin_rol = await mundo.http.get(
            "/v1/admin/acudientes", params={"ids": "no-es-uuid"}, headers=mundo.con("mama")
        )
        con_rol = await mundo.http.get(
            "/v1/admin/acudientes", params={"ids": "no-es-uuid"}, headers=mundo.con("admin")
        )

        assert (sin_token.status_code, _codigo(sin_token)) == (401, "sesion_invalida")
        assert (sin_rol.status_code, _codigo(sin_rol)) == (403, "acceso_denegado")
        assert (con_rol.status_code, _codigo(con_rol)) == (400, "ids_invalido")
        assert con_rol.json()["campo"] == "ids"


class TestAlcancePorActor:
    async def test_cada_acudiente_ve_solo_sus_hijos_y_nunca_el_apodo_del_otro(self, mundo: Mundo):
        de_mama = await mundo.http.get("/v1/cuenta/hijos", headers=mundo.con("mama"))
        de_papa = await mundo.http.get("/v1/cuenta/hijos", headers=mundo.con("papa"))

        assert de_mama.json() == {
            "total": 1,
            "hijos": [
                {"apodo": "Estudiante Ficticio Uno", "grado": "Quinto", "colegio_id": str(mundo.colegio_a)}
            ],
        }
        assert de_papa.json() == {
            "total": 1,
            "hijos": [
                {"apodo": "Estudiante Ficticio Dos", "grado": "Tercero", "colegio_id": str(mundo.colegio_b)}
            ],
        }
        assert "Estudiante Ficticio Dos" not in de_mama.text
        assert "Estudiante Ficticio Uno" not in de_papa.text

    async def test_las_matriculas_del_titular_solo_traen_colegio_grado_anio_y_apodo(self, mundo: Mundo):
        respuesta = await mundo.http.get("/v1/cuenta/matriculas", headers=mundo.con("mama"))
        [suya] = [f.id for f in await mundo.filas("matricula") if f.estudiante_id == mundo.estudiante_mama]

        # Desde 6864898 (contrato 1.6) cada fila trae `matricula_id`, el id de la
        # MATRICULA con que el panel la quita o la cambia; el del estudiante no baja.
        assert respuesta.json() == {
            "total": 1,
            "matriculas": [
                {
                    "matricula_id": str(suya),
                    "colegio_id": str(mundo.colegio_a),
                    "grado": "Quinto",
                    "anio_lectivo": 2026,
                    "apodo": "Estudiante Ficticio Uno",
                }
            ],
        }
        assert str(mundo.estudiante_mama) not in respuesta.text

    async def test_quien_no_tiene_hijos_recibe_listas_vacias_no_los_de_otros(self, mundo: Mundo):
        hijos = await mundo.http.get("/v1/cuenta/hijos", headers=mundo.con("colegio_admin"))
        matriculas = await mundo.http.get("/v1/cuenta/matriculas", headers=mundo.con("colegio_admin"))

        assert hijos.json() == {"total": 0, "hijos": []}
        assert matriculas.json() == {"total": 0, "matriculas": []}

    async def test_la_sesion_actual_trae_solo_los_roles_vigentes_del_portador(self, mundo: Mundo):
        mama = await mundo.http.get("/v1/sesiones/actual", headers=mundo.con("mama"))
        exadmin = await mundo.http.get("/v1/sesiones/actual", headers=mundo.con("exadmin"))

        assert mama.json()["nombre"] == "Acudiente Ficticio Uno"
        assert mama.json()["roles"] == [
            {"rol": "acudiente", "ambito": {"tipo": "colegio", "id": str(mundo.colegio_a)}}
        ]
        assert exadmin.json()["roles"] == []  # el rol admin caduco: no figura
        assert exadmin.json()["nombre"] == "exadmin@example.test"  # sin nombre cifrado, el correo

    async def test_el_padron_trae_solo_familias_reales_con_sus_hijos_y_nunca_claves(self, mundo: Mundo):
        respuesta = await mundo.http.get("/v1/admin/acudientes", headers=mundo.con("admin"))

        cuerpo = respuesta.json()
        por_correo = {a["correo"]: a for a in cuerpo["acudientes"]}
        assert cuerpo["total"] == 3
        # Quien fue admin y ya no tiene rol interno vigente es una cuenta real sin hijos: figura.
        assert set(por_correo) == {"mama@example.test", "papa@example.test", "exadmin@example.test"}
        assert por_correo["exadmin@example.test"]["hijos"] == []
        assert por_correo["mama@example.test"]["hijos"] == [
            {
                "apodo": "Estudiante Ficticio Uno",
                "colegio_id": str(mundo.colegio_a),
                "colegio_nombre": "Colegio Ficticio Uno",
                "grado": "Quinto",
            }
        ]
        assert por_correo["mama@example.test"]["celular"] == "3000000000"
        # Ni el equipo interno vigente, ni el rol de colegio, ni el invitado, ni la baja son "acudientes".
        for excluido in ("admin", "operador", "colegio.admin", "invitado", "baja"):
            assert f"{excluido}@example.test" not in por_correo
        for prohibido in ("clave", "hash", "pbkdf2", "nombre_cifrado", "Acudiente Ficticio"):
            assert prohibido not in respuesta.text

    async def test_el_padron_se_acota_por_ids_sin_abrir_staff_invitados_ni_ids_ajenos(self, mundo: Mundo):
        ids = ",".join(str(mundo.ids[n]) for n in ("mama", "admin", "invitado", "baja")) + f",{uuid.uuid4()}"

        acotado = await mundo.http.get(
            "/v1/admin/acudientes", params={"ids": ids}, headers=mundo.con("admin")
        )
        vacio = await mundo.http.get("/v1/admin/acudientes", params={"ids": ""}, headers=mundo.con("admin"))
        con_comas = await mundo.http.get(
            "/v1/admin/acudientes",
            params={"ids": f" {mundo.ids['papa']} ,, "},
            headers=mundo.con("operador"),
        )

        assert [a["correo"] for a in acotado.json()["acudientes"]] == ["mama@example.test"]
        # `ids` vacio acota a nadie; no se interpreta como "sin acotar".
        assert vacio.json() == {"total": 0, "acudientes": []}
        assert [a["correo"] for a in con_comas.json()["acudientes"]] == ["papa@example.test"]

    async def test_los_nombres_se_resuelven_solo_para_adultos_con_nombre_y_nunca_para_un_menor(
        self, mundo: Mundo
    ):
        ids = [mundo.ids["mama"], mundo.ids["invitado"], mundo.estudiante_mama, uuid.uuid4()]

        respuesta = await mundo.http.get(
            "/v1/usuarios/nombres", params={"ids": [str(i) for i in ids]}, headers=mundo.con("operador")
        )

        assert respuesta.status_code == 200
        assert respuesta.json() == {"nombres": {str(mundo.ids["mama"]): "Acudiente Ficticio Uno"}}
        assert "Estudiante Ficticio" not in respuesta.text

    async def test_una_direccion_ajena_es_404_para_editar_y_archivar_y_no_se_altera(self, mundo: Mundo):
        creada = await mundo.http.post("/v1/cuenta/direcciones", json=_DIRECCION, headers=mundo.con("mama"))
        direccion_id = creada.json()["direccion_id"]

        editar = await mundo.http.patch(
            f"/v1/cuenta/direcciones/{direccion_id}",
            json={"ciudad": "Ciudad Del Intruso", "linea": "Calle Del Intruso"},
            headers=mundo.con("papa"),
        )
        archivar = await mundo.http.delete(
            f"/v1/cuenta/direcciones/{direccion_id}", headers=mundo.con("papa")
        )
        de_papa = await mundo.http.get("/v1/cuenta/direcciones", headers=mundo.con("papa"))
        de_mama = await mundo.http.get("/v1/cuenta/direcciones", headers=mundo.con("mama"))

        assert (editar.status_code, _codigo(editar)) == (404, "direccion_no_existe")
        assert (archivar.status_code, _codigo(archivar)) == (404, "direccion_no_existe")
        assert de_papa.json() == {"total": 0, "direcciones": []}
        [propia] = de_mama.json()["direcciones"]
        assert (propia["ciudad"], propia["linea"]) == ("Ciudad Ficticia", "Calle Ficticia 1 # 2-3")


class TestLibretaDeDirecciones:
    async def test_la_linea_y_el_contacto_se_guardan_cifrados_y_vuelven_descifrados_a_su_dueno(
        self, mundo: Mundo
    ):
        creada = await mundo.http.post(
            "/v1/cuenta/direcciones",
            json={**_DIRECCION, "localidad": "Localidad Ficticia", "contacto": "3000000000"},
            headers=mundo.con("mama"),
        )

        assert creada.status_code == 201
        assert creada.json() | {"direccion_id": "x"} == {
            "direccion_id": "x",
            "etiqueta": "casa",
            "ciudad": "Ciudad Ficticia",
            "localidad": "Localidad Ficticia",
            "linea": "Calle Ficticia 1 # 2-3",
            "contacto": "3000000000",
            "predeterminada": False,
        }
        [fila] = await mundo.filas("direccion")
        assert fila.linea_cifrada == _claro("Calle Ficticia 1 # 2-3")  # el cifrador del entorno, no el texto
        assert fila.linea_cifrada != b"Calle Ficticia 1 # 2-3"
        assert fila.contacto_cifrado == _claro("3000000000")

    async def test_sin_contacto_el_campo_queda_nulo_y_no_se_cifra_una_cadena_vacia(self, mundo: Mundo):
        creada = await mundo.http.post(
            "/v1/cuenta/direcciones", json={**_DIRECCION, "contacto": ""}, headers=mundo.con("mama")
        )

        assert creada.json()["contacto"] is None
        [fila] = await mundo.filas("direccion")
        assert fila.contacto_cifrado is None

    async def test_solo_una_direccion_es_la_predeterminada_y_va_primero_en_la_lista(self, mundo: Mundo):
        casa = await mundo.http.post(
            "/v1/cuenta/direcciones", json={**_DIRECCION, "predeterminada": True}, headers=mundo.con("mama")
        )
        trabajo = await mundo.http.post(
            "/v1/cuenta/direcciones",
            json={**_DIRECCION, "etiqueta": "trabajo", "predeterminada": True},
            headers=mundo.con("mama"),
        )

        lista = (await mundo.http.get("/v1/cuenta/direcciones", headers=mundo.con("mama"))).json()

        assert lista["total"] == 2
        assert [d["predeterminada"] for d in lista["direcciones"]] == [True, False]
        assert lista["direcciones"][0]["direccion_id"] == trabajo.json()["direccion_id"]
        assert casa.json()["direccion_id"] in {d["direccion_id"] for d in lista["direcciones"]}

    async def test_editar_la_propia_cambia_los_campos_y_pasar_a_predeterminada_baja_a_la_anterior(
        self, mundo: Mundo
    ):
        vieja = (
            await mundo.http.post(
                "/v1/cuenta/direcciones",
                json={**_DIRECCION, "predeterminada": True},
                headers=mundo.con("mama"),
            )
        ).json()
        otra = (
            await mundo.http.post("/v1/cuenta/direcciones", json=_DIRECCION, headers=mundo.con("mama"))
        ).json()

        editada = await mundo.http.patch(
            f"/v1/cuenta/direcciones/{otra['direccion_id']}",
            json={"ciudad": "Otra Ciudad Ficticia", "linea": "Carrera Ficticia 9", "predeterminada": True},
            headers=mundo.con("mama"),
        )

        assert editada.status_code == 200
        assert (editada.json()["ciudad"], editada.json()["linea"], editada.json()["predeterminada"]) == (
            "Otra Ciudad Ficticia",
            "Carrera Ficticia 9",
            True,
        )
        lista = (await mundo.http.get("/v1/cuenta/direcciones", headers=mundo.con("mama"))).json()[
            "direcciones"
        ]
        assert {d["direccion_id"]: d["predeterminada"] for d in lista} == {
            otra["direccion_id"]: True,
            vieja["direccion_id"]: False,
        }

    async def test_archivar_es_204_baja_logica_y_repetirlo_es_404(self, mundo: Mundo):
        creada = (
            await mundo.http.post("/v1/cuenta/direcciones", json=_DIRECCION, headers=mundo.con("mama"))
        ).json()
        ruta = f"/v1/cuenta/direcciones/{creada['direccion_id']}"

        primera = await mundo.http.delete(ruta, headers=mundo.con("mama"))
        segunda = await mundo.http.delete(ruta, headers=mundo.con("mama"))
        editar = await mundo.http.patch(ruta, json=_DIRECCION, headers=mundo.con("mama"))

        assert (primera.status_code, primera.content) == (204, b"")
        assert (segunda.status_code, _codigo(segunda)) == (404, "direccion_no_existe")
        assert (editar.status_code, _codigo(editar)) == (404, "direccion_no_existe")
        assert (await mundo.http.get("/v1/cuenta/direcciones", headers=mundo.con("mama"))).json()[
            "total"
        ] == 0
        assert len(await mundo.filas("direccion")) == 1  # la fila sigue: un envio en curso la necesita

    @pytest.mark.parametrize(
        "cuerpo", [{"linea": "Calle Ficticia 1"}, {"ciudad": "", "linea": "x"}, {"ciudad": "x", "linea": ""}]
    )
    async def test_una_direccion_sin_ciudad_o_sin_linea_es_400_y_no_repite_lo_enviado(
        self, mundo: Mundo, cuerpo: dict
    ):
        respuesta = await mundo.http.post("/v1/cuenta/direcciones", json=cuerpo, headers=mundo.con("mama"))

        assert respuesta.status_code == 400
        assert _codigo(respuesta) == "entrada_invalida"
        assert "input" not in respuesta.json()
        assert await mundo.contar("direccion") == 0


class TestSesiones:
    async def test_iniciar_sesion_devuelve_la_sesion_publica_y_un_token_que_abre_la_cuenta(
        self, mundo: Mundo
    ):
        respuesta = await mundo.http.post(
            "/v1/sesiones", json={"correo": "  MAMA@Example.Test ", "clave": CLAVE}
        )

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["sesion"]["usuario_id"] == str(mundo.ids["mama"])
        assert cuerpo["sesion"]["nombre"] == "Acudiente Ficticio Uno"
        assert cuerpo["sesion"]["version_permisos"] == 1
        assert "clave" not in respuesta.text and "hash" not in respuesta.text
        cuenta = await mundo.http.get("/v1/cuenta", headers={"Authorization": f"Bearer {cuerpo['token']}"})
        assert cuenta.json() == {
            "usuario_id": str(mundo.ids["mama"]),
            "correo": "mama@example.test",
            "nombre": "Acudiente Ficticio Uno",
        }

    @pytest.mark.parametrize(
        ("correo", "clave"),
        [
            ("mama@example.test", "clave-equivocada"),
            ("nadie@example.test", CLAVE),
            ("baja@example.test", CLAVE),
            ("invitado@example.test", "sin-credencial"),
            ("invitado@example.test", CLAVE),
        ],
        ids=[
            "clave_mala",
            "correo_inexistente",
            "cuenta_de_baja",
            "invitado_con_el_centinela",
            "invitado_con_clave",
        ],
    )
    async def test_credenciales_malas_dan_el_mismo_401_sin_decir_cual_de_las_dos_fallo(
        self, mundo: Mundo, correo: str, clave: str
    ):
        respuesta = await mundo.http.post("/v1/sesiones", json={"correo": correo, "clave": clave})

        assert respuesta.status_code == 401
        assert respuesta.json() == {
            "error": "credenciales_invalidas",
            "mensaje": "El correo o la clave no son correctos.",
            "campo": "correo",
        }

    async def test_el_cierre_de_sesion_es_204_sin_estado_en_el_servidor(self, mundo: Mundo):
        """El token es autocontenido: cerrar no lo invalida (para eso esta la
        version de permisos). Caracteriza que el cierre no toca la base."""
        antes = {tabla: await mundo.contar(tabla) for tabla in _TABLAS_DE_ESCRITURA}

        cierre = await mundo.http.post("/v1/sesiones/cierre", headers=mundo.con("mama"))
        despues = await mundo.http.get("/v1/cuenta", headers=mundo.con("mama"))

        assert (cierre.status_code, cierre.content) == (204, b"")
        assert despues.status_code == 200
        assert {tabla: await mundo.contar(tabla) for tabla in _TABLAS_DE_ESCRITURA} == antes


class TestAltaPublica:
    async def test_registrar_un_acudiente_crea_cuenta_y_matriculas_y_puede_entrar_con_esa_clave(
        self, mundo: Mundo
    ):
        respuesta = await mundo.http.post(
            "/v1/registro",
            json={
                "correo": " Nueva@Example.Test ",
                "clave": "clave-ficticia-9",
                "acepta_terminos": True,
                "celular": "3000000000",
                "hijos": [
                    {
                        "colegio_id": str(mundo.colegio_a),
                        "grado": "Quinto",
                        "apodo": "Estudiante Ficticio Tres",
                    }
                ],
            },
        )

        assert respuesta.status_code == 201
        assert respuesta.json() == {
            "usuario_id": str(derivar("usuario", "nueva@example.test")),
            "creado": True,
        }
        entrada = await mundo.http.post(
            "/v1/sesiones", json={"correo": "nueva@example.test", "clave": "clave-ficticia-9"}
        )
        token = {"Authorization": f"Bearer {entrada.json()['token']}"}
        matriculas = (await mundo.http.get("/v1/cuenta/matriculas", headers=token)).json()["matriculas"]
        assert [(m["colegio_id"], m["grado"], m["apodo"]) for m in matriculas] == [
            (str(mundo.colegio_a), "Quinto", "Estudiante Ficticio Tres")
        ]
        assert matriculas[0]["anio_lectivo"] == datetime.now(UTC).year

    async def test_reenviar_el_registro_es_idempotente_y_no_cambia_la_clave_ni_duplica_hijos(
        self, mundo: Mundo
    ):
        cuerpo = {
            "correo": "nueva@example.test",
            "clave": "clave-ficticia-9",
            "acepta_terminos": True,
            "hijos": [{"colegio_id": str(mundo.colegio_a), "grado": "Quinto"}],
        }
        await mundo.http.post("/v1/registro", json=cuerpo)

        otra_vez = await mundo.http.post("/v1/registro", json={**cuerpo, "clave": "clave-del-intruso-1"})

        assert otra_vez.status_code == 201
        assert otra_vez.json()["creado"] is False
        assert await mundo.contar("matricula") == 3  # las 2 sembradas + la unica de la nueva
        vieja = await mundo.http.post(
            "/v1/sesiones", json={"correo": "nueva@example.test", "clave": "clave-ficticia-9"}
        )
        nueva = await mundo.http.post(
            "/v1/sesiones", json={"correo": "nueva@example.test", "clave": "clave-del-intruso-1"}
        )
        assert (vieja.status_code, nueva.status_code) == (200, 401)

    async def test_registrar_con_el_correo_de_una_cuenta_real_no_le_cuelga_hijos(self, mundo: Mundo):
        """La ruta es publica: si mutara una cuenta real, un tercero sin sesion
        podria agregar matriculas a la familia de otro."""
        respuesta = await mundo.http.post(
            "/v1/registro",
            json={
                "correo": "mama@example.test",
                "clave": "clave-del-intruso-1",
                "acepta_terminos": True,
                "hijos": [
                    {"colegio_id": str(mundo.colegio_b), "grado": "Once", "apodo": "Hijo Impostor Ficticio"}
                ],
            },
        )

        assert respuesta.status_code == 201
        assert respuesta.json() == {"usuario_id": str(mundo.ids["mama"]), "creado": False}
        hijos = (await mundo.http.get("/v1/cuenta/hijos", headers=mundo.con("mama"))).json()
        assert [h["apodo"] for h in hijos["hijos"]] == ["Estudiante Ficticio Uno"]
        assert await mundo.contar("matricula") == 2

    async def test_un_hijo_con_colegio_inexistente_deshace_todo_el_registro(self, mundo: Mundo):
        usuarios_antes = await mundo.contar("usuario")

        respuesta = await mundo.http.post(
            "/v1/registro",
            json={
                "correo": "nueva@example.test",
                "clave": "clave-ficticia-9",
                "acepta_terminos": True,
                "hijos": [
                    {"colegio_id": str(mundo.colegio_a), "grado": "Quinto"},
                    {"colegio_id": str(uuid.uuid4()), "grado": "Quinto"},
                ],
            },
        )

        assert respuesta.status_code == 422
        assert _codigo(respuesta) == "colegio_sin_sede"
        assert await mundo.contar("usuario") == usuarios_antes  # ni la cuenta ni el primer hijo quedaron
        assert await mundo.contar("matricula") == 2
        intento = await mundo.http.post(
            "/v1/sesiones", json={"correo": "nueva@example.test", "clave": "clave-ficticia-9"}
        )
        assert intento.status_code == 401

    @pytest.mark.parametrize(
        ("cuerpo", "estado", "codigo"),
        [
            (
                {"correo": "no-es-un-correo", "clave": "clave-ficticia-9", "acepta_terminos": True},
                422,
                "correo_invalido",
            ),
            (
                {
                    "correo": "nueva@example.test",
                    "clave": "clave-ficticia-9",
                    "acepta_terminos": True,
                    "hijos": [{"colegio_id": str(uuid.uuid4()), "grado": "Doceavo"}],
                },
                422,
                "grado_invalido",
            ),
            (
                {"correo": "nueva@example.test", "clave": "corta", "acepta_terminos": True},
                400,
                "entrada_invalida",
            ),
            (
                {
                    "correo": "nueva@example.test",
                    "clave": "clave-ficticia-9",
                    "acepta_terminos": True,
                    "hijos": [{"grado": "Quinto"}],
                },
                400,
                "entrada_invalida",
            ),
        ],
        ids=["correo_sin_forma", "grado_que_no_existe", "clave_de_menos_de_8", "hijo_sin_colegio"],
    )
    async def test_un_registro_invalido_se_rechaza_antes_de_escribir(
        self, mundo: Mundo, cuerpo: dict, estado: int, codigo: str
    ):
        respuesta = await mundo.http.post("/v1/registro", json=cuerpo)

        assert (respuesta.status_code, _codigo(respuesta)) == (estado, codigo)
        assert await mundo.contar("usuario") == 8

    async def test_un_contacto_invitado_que_se_registra_conserva_su_identificador(self, mundo: Mundo):
        contacto = (await mundo.http.post("/v1/contactos", json={"correo": "Pendiente@Example.Test "})).json()

        registro = await mundo.http.post(
            "/v1/registro",
            json={"correo": "pendiente@example.test", "clave": "clave-ficticia-9", "acepta_terminos": True},
        )

        assert contacto["creado"] is True
        assert registro.json() == {"usuario_id": contacto["usuario_id"], "creado": True}

    async def test_crear_la_cuenta_devuelve_la_sesion_y_un_token_que_ya_sirve(self, mundo: Mundo):
        respuesta = await mundo.http.post(
            "/v1/cuenta",
            json={
                "correo": " Nueva@Example.Test",
                "clave": "clave-ficticia-9",
                "acepta_terminos": True,
                "nombre": "Acudiente Ficticio Tres",
            },
        )

        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["sesion"]["correo"] == "nueva@example.test"
        assert cuerpo["sesion"]["nombre"] == "Acudiente Ficticio Tres"
        assert cuerpo["sesion"]["roles"] == []
        cuenta = await mundo.http.get("/v1/cuenta", headers={"Authorization": f"Bearer {cuerpo['token']}"})
        assert cuenta.json()["nombre"] == "Acudiente Ficticio Tres"

    async def test_crear_la_cuenta_sobre_un_invitado_lo_promueve_y_sobre_una_real_es_409(self, mundo: Mundo):
        contacto = (await mundo.http.post("/v1/contactos", json={"correo": "pendiente@example.test"})).json()

        promovido = await mundo.http.post(
            "/v1/cuenta",
            json={
                "correo": "pendiente@example.test",
                "clave": "clave-ficticia-9",
                "acepta_terminos": True,
                "nombre": "Acudiente Ficticio Tres",
            },
        )
        repetido = await mundo.http.post(
            "/v1/cuenta",
            json={
                "correo": "pendiente@example.test",
                "clave": "otra-clave-ficticia",
                "acepta_terminos": True,
                "nombre": "Intruso Ficticio",
            },
        )

        assert promovido.status_code == 201
        assert promovido.json()["sesion"]["usuario_id"] == contacto["usuario_id"]
        assert repetido.status_code == 409
        assert repetido.json() == {
            "error": "correo_ya_registrado",
            "mensaje": "Ese correo ya tiene una cuenta. Inicia sesion.",
            "campo": "correo",
        }
        entrada = await mundo.http.post(
            "/v1/sesiones", json={"correo": "pendiente@example.test", "clave": "clave-ficticia-9"}
        )
        assert entrada.status_code == 200  # el 409 no cambio la clave

    @pytest.mark.parametrize(
        ("cuerpo", "codigo", "campo"),
        [
            (
                {
                    "correo": "nueva@example.test",
                    "clave": "corta",
                    "nombre": "Acudiente Ficticio",
                    "acepta_terminos": True,
                },
                "clave_debil",
                "clave",
            ),
            (
                {
                    "correo": "sin-arroba",
                    "clave": "clave-ficticia-9",
                    "nombre": "Acudiente Ficticio",
                    "acepta_terminos": True,
                },
                "correo_invalido",
                "correo",
            ),
        ],
    )
    async def test_crear_la_cuenta_con_clave_corta_o_correo_sin_forma_es_422(
        self, mundo: Mundo, cuerpo: dict, codigo: str, campo: str
    ):
        respuesta = await mundo.http.post("/v1/cuenta", json=cuerpo)

        assert respuesta.status_code == 422
        assert (_codigo(respuesta), respuesta.json()["campo"]) == (codigo, campo)
        assert "clave-ficticia-9" not in respuesta.text and "corta" not in respuesta.text

    async def test_registrar_un_contacto_es_idempotente_y_no_devuelve_el_correo(self, mundo: Mundo):
        primero = await mundo.http.post("/v1/contactos", json={"correo": " Contacto@Example.Test "})
        segundo = await mundo.http.post("/v1/contactos", json={"correo": "contacto@example.test"})

        assert primero.status_code == 201
        assert primero.json()["creado"] is True and segundo.json()["creado"] is False
        assert primero.json()["usuario_id"] == segundo.json()["usuario_id"]
        assert "example.test" not in primero.text

    @pytest.mark.parametrize(
        "correo", ["sin-arroba", "dos@@example.test", "con espacio@example.test", "ab@cd"]
    )
    async def test_un_contacto_con_un_correo_sin_forma_valida_es_422(self, mundo: Mundo, correo: str):
        respuesta = await mundo.http.post("/v1/contactos", json={"correo": correo})

        assert (respuesta.status_code, _codigo(respuesta)) == (422, "correo_invalido")

    async def test_resolver_un_contacto_devuelve_el_correo_y_404_si_no_existe_o_esta_inactivo(
        self, mundo: Mundo
    ):
        existente = await mundo.http.get(f"/v1/contactos/{mundo.ids['mama']}")
        inactivo = await mundo.http.get(f"/v1/contactos/{mundo.ids['baja']}")
        inexistente = await mundo.http.get(f"/v1/contactos/{uuid.uuid4()}")

        assert existente.json() == {
            "usuario_id": str(mundo.ids["mama"]),
            "correo": "mama@example.test",
            "celular": None,
        }
        assert (inactivo.status_code, _codigo(inactivo)) == (404, "usuario_no_existe")
        assert (inexistente.status_code, _codigo(inexistente)) == (404, "usuario_no_existe")


class TestHijosDeLaCuenta:
    async def _cuenta_nueva(self, mundo: Mundo) -> dict[str, str]:
        creada = await mundo.http.post(
            "/v1/cuenta",
            json={
                "correo": "nueva@example.test",
                "clave": "clave-ficticia-9",
                "acepta_terminos": True,
                "nombre": "Acudiente Ficticio Tres",
            },
        )
        return {"Authorization": f"Bearer {creada.json()['token']}"}

    def _hijo(self, mundo: Mundo, **cambios: Any) -> dict[str, Any]:
        return {
            "apodo": "Estudiante Ficticio Tres",
            "colegio_id": str(mundo.colegio_a),
            "sede_id": str(mundo.sede_a),
            "grado": "Quinto",
            "anio_lectivo": 2026,
            "consentimiento": True,
        } | cambios

    async def test_registrar_un_hijo_deja_matricula_vinculo_consentimiento_y_el_rol_de_acudiente(
        self, mundo: Mundo
    ):
        token = await self._cuenta_nueva(mundo)

        respuesta = await mundo.http.post("/v1/cuenta/hijos", json=self._hijo(mundo), headers=token)

        assert respuesta.status_code == 201
        matricula_id = uuid.UUID(respuesta.json()["matricula_id"])
        # La cuenta nueva ya trae el del titular (`registro_titular`, oe5); el del hijo es aparte.
        [consentimiento] = [f for f in await mundo.filas("consentimiento") if f.regimen == "registro_menor"]
        assert consentimiento.matricula_id == matricula_id  # no hay hijo sin consentimiento propio
        assert (consentimiento.regimen, consentimiento.version) == ("registro_menor", "2026-09")
        hijos = (await mundo.http.get("/v1/cuenta/hijos", headers=token)).json()
        assert hijos["hijos"] == [
            {"apodo": "Estudiante Ficticio Tres", "grado": "Quinto", "colegio_id": str(mundo.colegio_a)}
        ]
        sesion = (await mundo.http.get("/v1/sesiones/actual", headers=token)).json()
        assert sesion["roles"] == [
            {"rol": "acudiente", "ambito": {"tipo": "colegio", "id": str(mundo.colegio_a)}}
        ]

    async def test_sin_consentimiento_o_sin_colegio_se_rechaza_con_422_y_no_se_escribe_nada(
        self, mundo: Mundo
    ):
        token = await self._cuenta_nueva(mundo)
        antes = {tabla: await mundo.contar(tabla) for tabla in _TABLAS_DE_ESCRITURA}

        sin_consentimiento = await mundo.http.post(
            "/v1/cuenta/hijos", json=self._hijo(mundo, consentimiento=False), headers=token
        )
        sin_colegio = await mundo.http.post(
            "/v1/cuenta/hijos", json=self._hijo(mundo, colegio_id=None), headers=token
        )
        sin_sede = await mundo.http.post(
            "/v1/cuenta/hijos", json=self._hijo(mundo, sede_id=None), headers=token
        )

        assert (sin_consentimiento.status_code, _codigo(sin_consentimiento)) == (
            422,
            "consentimiento_requerido",
        )
        assert (sin_colegio.status_code, _codigo(sin_colegio)) == (422, "hijo_sin_colegio")
        assert (sin_sede.status_code, _codigo(sin_sede)) == (422, "hijo_sin_colegio")
        assert {tabla: await mundo.contar(tabla) for tabla in _TABLAS_DE_ESCRITURA} == antes

    async def test_agregar_matriculas_con_sesion_toma_el_ordinal_siguiente_y_no_pisa_a_los_ya_registrados(
        self, mundo: Mundo
    ):
        cuerpo = {
            "hijos": [{"colegio_id": str(mundo.colegio_a), "grado": "Quinto", "apodo": "Gemelo Ficticio Dos"}]
        }

        primera = await mundo.http.post("/v1/cuenta/matriculas", json=cuerpo, headers=mundo.con("mama"))
        segunda = await mundo.http.post("/v1/cuenta/matriculas", json=cuerpo, headers=mundo.con("mama"))

        assert (primera.status_code, primera.json()) == (201, {"total": 1})
        assert (segunda.status_code, segunda.json()) == (201, {"total": 1})  # agregar NO es idempotente
        apodos = [
            m["apodo"]
            for m in (await mundo.http.get("/v1/cuenta/matriculas", headers=mundo.con("mama"))).json()[
                "matriculas"
            ]
        ]
        assert sorted(apodos) == ["Estudiante Ficticio Uno", "Gemelo Ficticio Dos", "Gemelo Ficticio Dos"]
        assert (await mundo.http.get("/v1/cuenta/matriculas", headers=mundo.con("papa"))).json()["total"] == 1

    async def test_agregar_matriculas_con_un_grado_o_colegio_invalido_es_422(self, mundo: Mundo):
        grado = await mundo.http.post(
            "/v1/cuenta/matriculas",
            json={"hijos": [{"colegio_id": str(mundo.colegio_a), "grado": "Doceavo"}]},
            headers=mundo.con("mama"),
        )
        colegio = await mundo.http.post(
            "/v1/cuenta/matriculas",
            json={"hijos": [{"colegio_id": str(uuid.uuid4()), "grado": "Quinto"}]},
            headers=mundo.con("mama"),
        )

        assert (grado.status_code, _codigo(grado)) == (422, "grado_invalido")
        assert (colegio.status_code, _codigo(colegio)) == (422, "colegio_sin_sede")
        assert (await mundo.http.get("/v1/cuenta/matriculas", headers=mundo.con("mama"))).json()["total"] == 1

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-20: el segundo hijo del mismo colegio revienta con 500 (IntegrityError sobre "
            "uq_asignacion_rol_vigente): routers/identidad.py:523 vuelve a otorgar el rol acudiente sin "
            "comprobar si ya existe (repositorios/identidad.py:444-455, modelos/autorizacion.py:127-135) "
            "y la transaccion entera se deshace"
        ),
    )
    async def test_registrar_un_segundo_hijo_en_el_mismo_colegio_es_201(self, mundo: Mundo):
        token = await self._cuenta_nueva(mundo)
        primero = await mundo.http.post("/v1/cuenta/hijos", json=self._hijo(mundo), headers=token)

        segundo = await mundo.http.post(
            "/v1/cuenta/hijos",
            json=self._hijo(mundo, apodo="Estudiante Ficticio Cuatro", grado="Tercero"),
            headers=token,
        )

        assert primero.status_code == 201
        assert segundo.status_code == 201

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-21: un colegio_id que no es UUID revienta con 500 (ValueError) en vez de 400/422: "
            "NuevoHijo lo tipa como str (routers/identidad.py:374-375) y el handler hace uuid.UUID(...) "
            "sin validar (:517-518, :523); CONTRATO_API 11 manda 400 para entrada invalida"
        ),
    )
    async def test_un_colegio_id_que_no_es_uuid_es_un_rechazo_de_cliente_y_no_un_500(self, mundo: Mundo):
        token = await self._cuenta_nueva(mundo)

        respuesta = await mundo.http.post(
            "/v1/cuenta/hijos", json=self._hijo(mundo, colegio_id="no-es-un-uuid"), headers=token
        )

        assert 400 <= respuesta.status_code < 500

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-22: POST /v1/cuenta/hijos acepta cualquier texto como grado y guarda la matricula; "
            "POST /v1/registro (routers/identidad.py:438-442) y POST /v1/cuenta/matriculas "
            "(repositorios/identidad.py:592-596) rechazan con 422 grado_invalido lo que no esta en los 15 "
            "grados, asi que el hijo queda con un grado al que ninguna lista oficial casa"
        ),
    )
    async def test_registrar_un_hijo_con_un_grado_que_no_existe_es_422_como_en_las_otras_rutas(
        self, mundo: Mundo
    ):
        token = await self._cuenta_nueva(mundo)

        respuesta = await mundo.http.post(
            "/v1/cuenta/hijos", json=self._hijo(mundo, grado="Grado Inventado"), headers=token
        )

        assert (respuesta.status_code, respuesta.json().get("error")) == (422, "grado_invalido")


class TestColegiosYDirectorio:
    async def test_el_listado_trae_los_colegios_activos_con_su_numero_de_sedes_y_se_busca_por_nombre(
        self, mundo: Mundo
    ):
        todos = await mundo.http.get("/v1/colegios")
        busqueda = await mundo.http.get("/v1/colegios", params={"busqueda": "DOS"})

        assert todos.status_code == 200
        assert [(c["nombre"], c["sedes"]) for c in todos.json()["colegios"]] == [
            ("Colegio Ficticio Dos", 1),
            ("Colegio Ficticio Uno", 1),
        ]
        assert [c["colegio_id"] for c in busqueda.json()["colegios"]] == [str(mundo.colegio_b)]
        assert busqueda.json()["total"] == 1

    async def test_el_detalle_trae_sus_sedes_y_un_id_desconocido_es_404(self, mundo: Mundo):
        detalle = await mundo.http.get(f"/v1/colegios/{mundo.colegio_a}")
        desconocido = await mundo.http.get(f"/v1/colegios/{uuid.uuid4()}")
        mal_formado = await mundo.http.get("/v1/colegios/no-es-uuid")

        assert detalle.json()["nombre"] == "Colegio Ficticio Uno"
        assert detalle.json()["sedes"] == [{"sede_id": str(mundo.sede_a), "nombre": "Sede Ficticia Uno"}]
        assert (desconocido.status_code, _codigo(desconocido)) == (404, "colegio_no_existe")
        assert (mal_formado.status_code, _codigo(mal_formado)) == (400, "entrada_invalida")

    async def test_los_grados_son_los_quince_en_orden_escolar(self, mundo: Mundo):
        respuesta = await mundo.http.get("/v1/grados")

        cuerpo = respuesta.json()
        assert cuerpo["total"] == 15
        assert cuerpo["grados"][0] == "Parvulos" and cuerpo["grados"][-1] == "Once"
        assert cuerpo["grados"].index("Transicion") < cuerpo["grados"].index("Primero")

    async def test_el_directorio_devuelve_los_siete_campos_del_alta_y_la_ficha_completa_a_peticion(
        self, mundo: Mundo
    ):
        alta = (await mundo.http.get(f"/v1/directorio/{DANE_REAL}")).json()
        completa = (await mundo.http.get(f"/v1/directorio/{DANE_REAL}", params={"completo": "true"})).json()

        assert set(alta) == {
            "dane",
            "nombre",
            "direccion",
            "sitio_web",
            "contacto_email",
            "contacto_telefono",
            "contacto_nombre",
        }
        assert alta["dane"] == DANE_REAL and alta["nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"
        assert {k: completa[k] for k in alta} == alta
        assert {"sector", "localidad", "rector", "telefonos", "correos"} <= set(completa)

    @pytest.mark.parametrize("completo", ["false", "true"])
    async def test_un_dane_que_no_esta_en_el_directorio_es_404(self, mundo: Mundo, completo: str):
        respuesta = await mundo.http.get("/v1/directorio/000000000000", params={"completo": completo})

        assert respuesta.status_code == 404
        assert _codigo(respuesta) == "dane_no_en_directorio"


class TestEdicionDelPerfilDelColegio:
    async def test_editar_el_perfil_devuelve_el_detalle_actualizado_y_no_toca_nombre_ni_sedes(
        self, mundo: Mundo
    ):
        respuesta = await mundo.http.patch(
            f"/v1/colegios/{mundo.colegio_a}",
            json={
                "dane": DANE_REAL,
                "sitio_web": "https://uno.example.test",
                "contacto_email": "contacto@example.test",
            },
        )

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["dane"] == DANE_REAL
        assert cuerpo["sitio_web"] == "https://uno.example.test"
        assert cuerpo["contacto_email"] == "contacto@example.test"
        assert cuerpo["nombre"] == "Colegio Ficticio Uno"
        assert cuerpo["sedes"] == [{"sede_id": str(mundo.sede_a), "nombre": "Sede Ficticia Uno"}]
        assert (await mundo.http.get(f"/v1/colegios/{mundo.colegio_a}")).json() == cuerpo

    async def test_un_cuerpo_vacio_o_con_claves_ajenas_al_perfil_no_cambia_nada(self, mundo: Mundo):
        """Solo los campos de perfil se escriben: `activo` o `id` en el cuerpo se ignoran."""
        antes = (await mundo.http.get(f"/v1/colegios/{mundo.colegio_a}")).json()

        vacio = await mundo.http.patch(f"/v1/colegios/{mundo.colegio_a}", json={})
        ajeno = await mundo.http.patch(
            f"/v1/colegios/{mundo.colegio_a}", json={"activo": False, "id": str(uuid.uuid4())}
        )

        assert vacio.json() == antes and ajeno.json() == antes
        assert mundo.colegio_a in {
            uuid.UUID(c["colegio_id"]) for c in (await mundo.http.get("/v1/colegios")).json()["colegios"]
        }

    @pytest.mark.parametrize("campo", ["nombre", "nit"])
    async def test_el_nombre_y_el_nit_no_se_editan_y_el_rechazo_no_escribe_lo_demas(
        self, mundo: Mundo, campo: str
    ):
        respuesta = await mundo.http.patch(
            f"/v1/colegios/{mundo.colegio_a}",
            json={campo: "Otro Valor", "sitio_web": "https://no-debe-quedar.example.test"},
        )

        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "campo_no_editable"
        assert respuesta.json()["campo"] == campo
        assert (await mundo.http.get(f"/v1/colegios/{mundo.colegio_a}")).json()["sitio_web"] is None

    @pytest.mark.parametrize("dane", ["123", "12345678901a", "1234567890123", 311001105731, True, ""])
    async def test_un_dane_que_no_son_doce_digitos_se_rechaza_con_400(self, mundo: Mundo, dane: Any):
        respuesta = await mundo.http.patch(f"/v1/colegios/{mundo.colegio_a}", json={"dane": dane})

        assert (respuesta.status_code, _codigo(respuesta)) == (400, "dane_invalido")
        assert (await mundo.http.get(f"/v1/colegios/{mundo.colegio_a}")).json()["dane"] is None

    async def test_el_dane_se_puede_vaciar_con_null(self, mundo: Mundo):
        await mundo.http.patch(f"/v1/colegios/{mundo.colegio_a}", json={"dane": DANE_REAL})

        vaciado = await mundo.http.patch(f"/v1/colegios/{mundo.colegio_a}", json={"dane": None})

        assert vaciado.status_code == 200 and vaciado.json()["dane"] is None

    async def test_editar_un_colegio_que_no_existe_es_404(self, mundo: Mundo):
        respuesta = await mundo.http.patch(
            f"/v1/colegios/{uuid.uuid4()}", json={"sitio_web": "https://x.example.test"}
        )

        assert (respuesta.status_code, _codigo(respuesta)) == (404, "colegio_no_existe")

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-C-06: PATCH /v1/colegios/{id} no exige sesion ni rol: editar_colegio no recibe Authorization "
            "ni llama a _usuario_del_token/es_staff_vigente (routers/identidad.py:242-279), y su docstring "
            "dice 'el administrador completa el perfil'; cualquiera reescribe el DANE, el logo y contactos"
        ),
    )
    @pytest.mark.parametrize("quien", [None, "mama"], ids=["sin_token", "acudiente"])
    async def test_solo_el_equipo_interno_edita_el_perfil_de_un_colegio(
        self, mundo: Mundo, quien: str | None
    ):
        encabezado = mundo.con(quien) if quien else {}

        respuesta = await mundo.http.patch(
            f"/v1/colegios/{mundo.colegio_a}",
            json={"sitio_web": "https://intruso.example.test"},
            headers=encabezado,
        )

        assert respuesta.status_code == (401 if quien is None else 403)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-21: un valor que no es texto en el PATCH del perfil llega sin validar a la base y "
            "responde 500 (ProgrammingError al enlazar el parametro): el cuerpo es dict[str, Any] "
            "(routers/identidad.py:243) y solo se valida el dane (:261-269, :270); CONTRATO_API 11 manda 400"
        ),
    )
    async def test_un_valor_que_no_es_texto_en_el_perfil_es_400_y_no_un_500(self, mundo: Mundo):
        respuesta = await mundo.http.patch(
            f"/v1/colegios/{mundo.colegio_a}", json={"sitio_web": {"no": "es texto"}}
        )

        assert respuesta.status_code == 400

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-23: el DANE se valida con str.isdigit() (routers/identidad.py:263), que acepta "
            "digitos Unicode no ASCII (fullwidth, superindices); se guarda una llave que nunca casara con "
            "el directorio, y el comentario de :258-260 promete '12 digitos exactos'"
        ),
    )
    async def test_un_dane_con_digitos_que_no_son_ascii_se_rechaza(self, mundo: Mundo):
        respuesta = await mundo.http.patch(
            f"/v1/colegios/{mundo.colegio_a}", json={"dane": "１２３４５６７８９０１２"}
        )

        assert (respuesta.status_code, respuesta.json().get("error")) == (400, "dane_invalido")


def _peticion() -> Any:
    """Lo unico que los manejadores leen de `Request`: `app.state.motor`."""
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(motor=app.state.motor)))


def _bearer(mundo: Mundo, quien: str) -> str:
    return f"Bearer {mundo.token(quien)}"


async def _rechazo(corutina: Any) -> ErrorDominio:
    """Espera la corrutina, exige que levante `ErrorDominio` y devuelve el error."""
    with pytest.raises(ErrorDominio) as capturado:
        await corutina
    return capturado.value


class TestManejadoresSinHttp:
    """Las mismas reglas de acceso, una capa por debajo de HTTP.

    Cada manejador se llama como funcion con una peticion falsa: asi se fija lo
    que DEVUELVE o LEVANTA (`ErrorDominio` con su codigo y estado) sin depender
    de como el envoltorio lo serialice. Sirve ademas para que `coverage` registre
    el cuerpo de los manejadores: el trazador por omision pierde las lineas que
    siguen a un `await` de SQLAlchemy cuando corren dentro de ASGI.
    """

    async def test_el_token_de_una_cuenta_inactiva_o_revocada_levanta_401_con_su_codigo(self, mundo: Mundo):
        baja = await _rechazo(rutas.ver_cuenta(_peticion(), _bearer(mundo, "baja")))
        await mundo.ejecutar(
            update(Usuario).where(Usuario.id == mundo.ids["mama"]).values(version_permisos=7)
        )
        revocada = await _rechazo(rutas.ver_cuenta(_peticion(), _bearer(mundo, "mama")))
        sin_encabezado = await _rechazo(rutas.ver_cuenta(_peticion(), None))

        assert (baja.estado, baja.error) == (401, "sesion_invalida")
        assert (revocada.estado, revocada.error) == (401, "sesion_revocada")
        assert (sin_encabezado.estado, sin_encabezado.error) == (401, "sesion_invalida")

    async def test_la_cuenta_devuelve_el_nombre_descifrado_o_el_correo_si_no_hay_nombre(self, mundo: Mundo):
        con_nombre = await rutas.ver_cuenta(_peticion(), _bearer(mundo, "mama"))
        sin_nombre = await rutas.ver_cuenta(_peticion(), _bearer(mundo, "admin"))

        assert con_nombre == {
            "usuario_id": str(mundo.ids["mama"]),
            "correo": "mama@example.test",
            "nombre": "Acudiente Ficticio Uno",
        }
        assert sin_nombre["nombre"] == "admin@example.test"

    async def test_editar_un_colegio_inexistente_levanta_404_y_uno_real_devuelve_el_detalle(
        self, mundo: Mundo
    ):
        inexistente = await _rechazo(
            rutas.editar_colegio(_peticion(), uuid.uuid4(), {"sitio_web": "https://x.example.test"})
        )
        detalle = await rutas.editar_colegio(_peticion(), mundo.colegio_a, {"dane": DANE_REAL})
        ver_inexistente = await _rechazo(rutas.ver_colegio(_peticion(), uuid.uuid4()))

        assert (inexistente.estado, inexistente.error) == (404, "colegio_no_existe")
        assert (ver_inexistente.estado, ver_inexistente.error) == (404, "colegio_no_existe")
        assert detalle["dane"] == DANE_REAL and detalle["colegio_id"] == str(mundo.colegio_a)

    async def test_los_nombres_exigen_el_permiso_y_solo_el_equipo_interno_lo_tiene(self, mundo: Mundo):
        ids = [mundo.ids["mama"], mundo.ids["papa"]]

        sin_permiso = await _rechazo(rutas.nombres_de_usuarios(_peticion(), ids, _bearer(mundo, "mama")))
        resueltos = await rutas.nombres_de_usuarios(_peticion(), ids, _bearer(mundo, "operador"))

        assert (sin_permiso.estado, sin_permiso.error) == (403, "sin_permiso")
        assert resueltos == {
            "nombres": {
                str(mundo.ids["mama"]): "Acudiente Ficticio Uno",
                str(mundo.ids["papa"]): "Acudiente Ficticio Dos",
            }
        }

    async def test_el_padron_levanta_403_al_acudiente_400_al_admin_con_ids_rotos_y_lista_al_admin(
        self, mundo: Mundo
    ):
        peticion = _peticion()

        sin_rol = await _rechazo(rutas.listar_acudientes(peticion, _bearer(mundo, "mama"), None))
        ids_rotos = await _rechazo(rutas.listar_acudientes(peticion, _bearer(mundo, "admin"), "uno,dos"))
        propios = await rutas.listar_acudientes(peticion, _bearer(mundo, "admin"), str(mundo.ids["papa"]))

        assert (sin_rol.estado, sin_rol.error) == (403, "acceso_denegado")
        assert (ids_rotos.estado, ids_rotos.error, ids_rotos.campo) == (400, "ids_invalido", "ids")
        assert [a["correo"] for a in propios["acudientes"]] == ["papa@example.test"]
        assert propios["total"] == 1

    async def test_crear_cuenta_levanta_409_si_el_correo_ya_es_real_y_devuelve_sesion_y_token_si_es_nuevo(
        self, mundo: Mundo
    ):
        repetida = await _rechazo(
            rutas.crear_cuenta(
                _peticion(),
                rutas.NuevaCuenta(
                    correo="mama@example.test",
                    clave="clave-ficticia-9",
                    nombre="Intruso Ficticio",
                    acepta_terminos=True,
                ),
            )
        )
        nueva = await rutas.crear_cuenta(
            _peticion(),
            rutas.NuevaCuenta(
                correo="nueva@example.test",
                clave="clave-ficticia-9",
                nombre="Acudiente Ficticio Tres",
                acepta_terminos=True,
            ),
        )

        assert (repetida.estado, repetida.error, repetida.campo) == (409, "correo_ya_registrado", "correo")
        assert nueva["sesion"]["correo"] == "nueva@example.test"
        assert nueva["token"].count(".") == 1

    async def test_iniciar_sesion_levanta_401_ante_una_clave_mala_y_entrega_token_ante_una_buena(
        self, mundo: Mundo
    ):
        mala = await _rechazo(
            rutas.iniciar_sesion(
                _peticion(), rutas.Credenciales(correo="mama@example.test", clave="clave-equivocada")
            )
        )
        buena = await rutas.iniciar_sesion(
            _peticion(), rutas.Credenciales(correo="mama@example.test", clave=CLAVE)
        )

        assert (mala.estado, mala.error) == (401, "credenciales_invalidas")
        assert buena["sesion"]["usuario_id"] == str(mundo.ids["mama"])
        assert (await rutas.sesion_actual(_peticion(), f"Bearer {buena['token']}"))["usuario_id"] == str(
            mundo.ids["mama"]
        )

    async def test_hijos_y_matriculas_son_los_del_portador_y_agregar_suma_al_conteo(self, mundo: Mundo):
        peticion = _peticion()
        autorizacion = _bearer(mundo, "mama")

        hijos = await rutas.listar_hijos(peticion, autorizacion)
        agregadas = await rutas.guardar_matriculas(
            peticion,
            rutas.MatriculasNuevas(
                hijos=[rutas.HijoRegistro(colegio_id=mundo.colegio_a, grado="Sexto", apodo="Gemelo Ficticio")]
            ),
            autorizacion,
        )
        matriculas = await rutas.listar_matriculas(peticion, autorizacion)

        assert hijos["total"] == 1 and hijos["hijos"][0]["apodo"] == "Estudiante Ficticio Uno"
        assert agregadas == {"total": 1}
        assert matriculas["total"] == 2
        assert {m["grado"] for m in matriculas["matriculas"]} == {"Quinto", "Sexto"}

    async def test_registrar_un_hijo_devuelve_la_matricula_y_deja_el_rol_de_acudiente_en_su_colegio(
        self, mundo: Mundo
    ):
        nueva = await rutas.crear_cuenta(
            _peticion(),
            rutas.NuevaCuenta(
                correo="nueva@example.test",
                clave="clave-ficticia-9",
                nombre="Acudiente Ficticio Tres",
                acepta_terminos=True,
            ),
        )
        autorizacion = f"Bearer {nueva['token']}"

        creado = await rutas.registrar_hijo(
            _peticion(),
            rutas.NuevoHijo(
                apodo="Estudiante Ficticio Tres",
                colegio_id=str(mundo.colegio_b),
                sede_id=str(mundo.sede_b),
                grado="Tercero",
                anio_lectivo=2026,
                consentimiento=True,
            ),
            autorizacion,
        )

        assert uuid.UUID(creado["matricula_id"])
        sesion = await rutas.sesion_actual(_peticion(), autorizacion)
        assert sesion["roles"] == [
            {"rol": "acudiente", "ambito": {"tipo": "colegio", "id": str(mundo.colegio_b)}}
        ]

    async def test_la_libreta_de_direcciones_se_crea_edita_y_archiva_solo_por_su_dueno(self, mundo: Mundo):
        peticion = _peticion()
        dueno, ajeno = _bearer(mundo, "mama"), _bearer(mundo, "papa")
        entrada = rutas.DireccionEntrada(
            ciudad="Ciudad Ficticia", linea="Calle Ficticia 1", predeterminada=True
        )

        creada = await rutas.crear_direccion(peticion, entrada, dueno)
        direccion_id = uuid.UUID(creada["direccion_id"])
        editada = await rutas.editar_direccion(
            peticion,
            direccion_id,
            rutas.DireccionEntrada(
                ciudad="Otra Ciudad Ficticia", linea="Carrera Ficticia 2", predeterminada=True
            ),
            dueno,
        )
        edicion_ajena = await _rechazo(rutas.editar_direccion(peticion, direccion_id, entrada, ajeno))
        archivado_ajeno = await _rechazo(rutas.archivar_direccion(peticion, direccion_id, ajeno))
        lista_ajena = await rutas.listar_direcciones(peticion, ajeno)
        archivada = await rutas.archivar_direccion(peticion, direccion_id, dueno)
        repetido = await _rechazo(rutas.archivar_direccion(peticion, direccion_id, dueno))

        assert creada["predeterminada"] is True and creada["linea"] == "Calle Ficticia 1"
        assert (editada["ciudad"], editada["linea"]) == ("Otra Ciudad Ficticia", "Carrera Ficticia 2")
        assert (edicion_ajena.estado, edicion_ajena.error) == (404, "direccion_no_existe")
        assert (archivado_ajeno.estado, archivado_ajeno.error) == (404, "direccion_no_existe")
        assert lista_ajena == {"total": 0, "direcciones": []}
        assert archivada is None
        assert (repetido.estado, repetido.error) == (404, "direccion_no_existe")
        assert (await rutas.listar_direcciones(peticion, dueno))["total"] == 0
