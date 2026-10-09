"""NFR-MAN-01: la siembra de roles, permisos y usuarios de demostracion del acceso.

`sembrar_acceso` es la unica fuente de los cinco roles del sistema, de los
permisos minimos y de las cuentas con las que el frontend entra en modo `api`.
`test_sembrar_acceso.py` solo fija tres constantes; aqui se fija lo que decide
si la siembra sirve de verdad:

- los datos son COHERENTES entre si (todo rol asignado existe, todo par
  rol-permiso apunta a filas que se siembran, los ambitos respetan el CHECK
  global/no global) y las claves se guardan como hash con sal, nunca en claro;
- el hijo de la mama de demostracion sale por la MISMA derivacion que el
  registro real (`materializar_hijos`), asi que sembrar y registrarse producen
  las mismas filas, y su apodo va cifrado;
- sembrar es idempotente (no duplica) y re-sembrar REFRESCA la clave y el texto
  de los roles, pero no pisa un permiso que alguien ya ajusto (`DO NOTHING`);
- lo sembrado responde a `puede()` como promete el modelo de autorizacion: el
  admin lee nombres de adultos, la mama ve el apodo de SU colegio y nada mas, la
  rectoria publica la lista de SU colegio y no la de otro;
- por HTTP, la mama de demostracion entra con la clave publica `demo1234` y ve
  solo su propio hijo.

La base es un archivo SQLite temporal elegido por `TUKIT_IDENTIDAD_DB_URL` (el
`INSERT ... ON CONFLICT` de Postgres compila igual en SQLite). Los correos
`@ejemplo.com` y `@colegio.edu.co` y el apodo "Pipe" son las constantes de
demostracion del propio producto, no datos de personas; los datos que agrega la
prueba son ficticios.
"""

from __future__ import annotations

import runpy
import sys
import types
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun import derivar
from tukit_comun.bd import MotorServicio
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_identidad import sembrar_acceso
from tukit_identidad.api import app
from tukit_identidad.cargador import Cargador
from tukit_identidad.dominio.autorizacion import Ambito
from tukit_identidad.dominio.matriculas import HijoMatricula
from tukit_identidad.dominio.sesiones import verificar_clave
from tukit_identidad.modelos import (
    AcudienteMatricula,
    AmbitoTipo,
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
from tukit_identidad.repositorios.identidad import RepoIdentidad
from tukit_identidad.sembrar_acceso import (
    CLAVE_DEMO,
    COLEGIO_PILOTO,
    PERMISOS,
    ROL_PERMISO,
    ROLES,
    SEDE_PILOTO,
    hijo_demo_de_mama,
    sembrar,
    usuarios_demo,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

RAIZ = Path(__file__).resolve().parents[3]
ANIO_FIJO = 2031
CONTEO_ESPERADO = {
    "rol": 5,
    "permiso": 7,
    "rol_permiso": 13,
    "usuario": 6,
    "asignacion_rol": 6,
    "estudiante": 1,
    "matricula": 1,
    "acudiente_matricula": 1,
}
TABLAS = {
    "rol": Rol,
    "permiso": Permiso,
    "rol_permiso": RolPermiso,
    "usuario": Usuario,
    "asignacion_rol": AsignacionRol,
    "estudiante": Estudiante,
    "matricula": Matricula,
    "acudiente_matricula": AcudienteMatricula,
}


def _piloto() -> uuid.UUID:
    return derivar("colegio", COLEGIO_PILOTO)


def _sede_piloto() -> uuid.UUID:
    return derivar("sede", COLEGIO_PILOTO, SEDE_PILOTO)


@pytest.fixture(autouse=True)
def _cifrado_en_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin llave de cifrado en el entorno el apodo se guarda con `CifradorEnClaro`:
    asi la prueba no depende de `cryptography` ni de una llave."""
    monkeypatch.delenv("TUKIT_LLAVE_CIFRADO", raising=False)


@pytest.fixture
def reloj_fijo(monkeypatch: pytest.MonkeyPatch) -> int:
    """`hijo_demo_de_mama` toma el anio de `datetime.now(UTC)`: se fija el reloj
    que ve ese modulo (y solo ese) para que el anio lectivo no dependa de hoy."""
    fijo = datetime(ANIO_FIJO, 6, 1, tzinfo=UTC)
    monkeypatch.setattr(sembrar_acceso, "datetime", types.SimpleNamespace(now=lambda tz=None: fijo))
    return ANIO_FIJO


@pytest.fixture
def bd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Archivo SQLite con el esquema de Identidad y el colegio piloto ya
    sembrado (la siembra de acceso depende de que `cargador` lo haya hecho).
    Devuelve `(url_asincrona, consultar)`; `consultar` lee por una conexion
    sincrona aparte."""
    ruta = tmp_path / "identidad.db"
    url = f"sqlite+aiosqlite:///{ruta}"
    monkeypatch.setenv("TUKIT_IDENTIDAD_DB_URL", url)
    motor = create_engine(f"sqlite:///{ruta}")
    Base.metadata.create_all(motor)
    with motor.begin() as conexion:
        conexion.execute(insert(Colegio.__table__).values(id=_piloto(), nombre="Colegio Piloto Ficticio"))
        conexion.execute(
            insert(Sede.__table__).values(id=_sede_piloto(), colegio_id=_piloto(), nombre=SEDE_PILOTO)
        )

    def consultar(consulta):
        with motor.connect() as conexion:
            return list(conexion.execute(consulta))

    def contar(tabla: str) -> int:
        return consultar(select(func.count()).select_from(TABLAS[tabla].__table__))[0][0]

    consultar.contar = contar  # type: ignore[attr-defined]
    yield url, consultar
    motor.dispose()


class TestDatosDeLaSiembra:
    """Las constantes y las filas demo, sin base de datos."""

    def test_los_roles_los_permisos_y_sus_uniones_son_coherentes_entre_si(self):
        roles = {r["codigo"] for r in ROLES}
        permisos = {p["codigo"] for p in PERMISOS}

        assert len(roles) == len(ROLES) == 5
        assert len(permisos) == len(PERMISOS) == 7
        assert all(r["del_sistema"] is True for r in ROLES)
        # Cada union apunta a un rol y a un permiso que de verdad se siembran.
        assert all(rol in roles and permiso in permisos for rol, permiso in ROL_PERMISO)
        assert len(set(ROL_PERMISO)) == len(ROL_PERMISO) == 13
        # El codigo del permiso es `recurso:accion[:campo]`, y la clasificacion existe.
        valores = {c.value for c in Clasificacion}
        for p in PERMISOS:
            partes = [p["recurso"], p["accion"]] + ([p["campo"]] if p["campo"] else [])
            assert p["codigo"] == ":".join(partes)  # type: ignore[arg-type]
            assert p["clasificacion_minima"] in valores

    def test_hay_seis_usuarios_demo_con_id_derivado_del_correo_y_un_rol_cada_uno(self):
        filas = usuarios_demo(CLAVE_DEMO)

        correos = [f["usuario"]["correo"] for f in filas]  # type: ignore[index]
        assert correos == [
            "mama@ejemplo.com",
            "papa@ejemplo.com",
            "rectoria@colegio.edu.co",
            "docente@colegio.edu.co",
            "operador@tukit.co",
            "admin@tukit.co",
        ]
        roles = {f["usuario"]["correo"]: f["asignacion"]["rol_codigo"] for f in filas}  # type: ignore[index]
        assert roles["mama@ejemplo.com"] == roles["papa@ejemplo.com"] == "acudiente"
        assert {roles["operador@tukit.co"], roles["admin@tukit.co"]} == {"operador", "admin"}
        for f in filas:
            usuario, asignacion = f["usuario"], f["asignacion"]
            assert usuario["id"] == derivar("usuario", usuario["correo"])  # type: ignore[index]
            assert asignacion["usuario_id"] == usuario["id"]  # type: ignore[index]
            assert asignacion["id"] == derivar("asignacion", usuario["correo"], asignacion["rol_codigo"])  # type: ignore[index]
            assert usuario["activo"] is True  # type: ignore[index]
            assert asignacion["rol_codigo"] in {r["codigo"] for r in ROLES}  # type: ignore[index]

    def test_los_ambitos_demo_son_coherentes_colegio_piloto_o_global(self):
        """Mismo invariante que el CHECK `asignacion_ambito_coherente`: construir
        el `Ambito` con los datos de cada fila no puede lanzar, y los tres roles
        de colegio apuntan al colegio piloto que `cargador` siembra."""
        for f in usuarios_demo(CLAVE_DEMO):
            asignacion = f["asignacion"]
            ambito = Ambito(AmbitoTipo(asignacion["ambito_tipo"]), asignacion["ambito_id"])  # type: ignore[arg-type]
            if asignacion["rol_codigo"] in {"operador", "admin"}:
                assert ambito == Ambito.global_()
            else:
                assert ambito == Ambito.colegio(_piloto())

    def test_las_claves_se_guardan_como_hash_con_sal_y_verifican_solo_la_clave_dada(self):
        filas = usuarios_demo("clave-ficticia-demo")
        hashes = [f["usuario"]["clave_hash"] for f in filas]  # type: ignore[index]

        assert all(h.startswith("pbkdf2_sha256$") for h in hashes)
        assert "clave-ficticia-demo" not in "".join(hashes)
        # Sal aleatoria: la misma clave da un hash distinto para cada usuario.
        assert len(set(hashes)) == len(hashes)
        assert all(verificar_clave("clave-ficticia-demo", h) for h in hashes)
        assert not any(verificar_clave(CLAVE_DEMO, h) for h in hashes)

    def test_el_colegio_piloto_es_el_2_13_del_corpus_con_el_mismo_uuid_que_deriva_el_cargador(self):
        """La promesa de la cabecera del modulo: el colegio y la sede que usan
        las asignaciones y el hijo demo son los que `cargador` siembra para ese
        codigo, y ese codigo existe en el corpus versionado."""
        corpus = Cargador(RAIZ / "datos" / "listas")
        datos = corpus.armar()
        colegios = {c["id"]: c["nombre"] for c in datos["colegio"]}
        sedes = {s["id"]: s["colegio_id"] for s in datos["sede"]}

        assert _piloto() in colegios
        assert sedes[_sede_piloto()] == _piloto()
        assert hijo_demo_de_mama()["matricula"]["sede_id"] == _sede_piloto()


class TestHijoDemo:
    def test_los_ids_y_el_anio_salen_de_la_derivacion_del_registro_real(self, reloj_fijo: int):
        hijo = hijo_demo_de_mama()

        estudiante, matricula, vinculo = hijo["estudiante"], hijo["matricula"], hijo["vinculo"]
        mama = derivar("usuario", "mama@ejemplo.com")
        assert matricula["anio_lectivo"] == ANIO_FIJO
        assert matricula["grado"] == "Quinto"
        assert matricula["colegio_id"] == _piloto()
        assert matricula["estudiante_id"] == estudiante["id"]
        assert vinculo == {
            "usuario_id": mama,
            "matricula_id": matricula["id"],
            "parentesco": "acudiente",
            "es_principal": True,
        }

    def test_el_apodo_es_lo_unico_del_menor_y_va_cifrado_no_en_claro(self, reloj_fijo: int):
        guardado = hijo_demo_de_mama()["estudiante"]["nombre_cifrado"]

        assert isinstance(guardado, bytes)
        assert cifrador_desde_entorno().descifrar(guardado) == b"Pipe"
        # Con el cifrador en claro el dato lleva el prefijo que delata que NO esta cifrado de verdad.
        assert guardado.startswith(b"claro:")

    async def test_sembrar_y_registrar_al_hijo_producen_exactamente_las_mismas_filas(
        self, db, reloj_fijo: int
    ):
        """`materializar_hijos` (registro y /empezar) y la siembra derivan el
        mismo estudiante y la misma matricula para el mismo (usuario, colegio,
        grado, anio): la siembra es un atajo del registro, no un formato aparte."""
        mama = derivar("usuario", "mama@ejemplo.com")
        db.add_all(
            [
                Colegio(id=_piloto(), nombre="Colegio Piloto Ficticio"),
                Usuario(id=mama, correo="mama@ejemplo.com", clave_hash="x"),
            ]
        )
        await db.flush()
        db.add(Sede(id=_sede_piloto(), colegio_id=_piloto(), nombre=SEDE_PILOTO))
        await db.flush()
        conexion = await db.connection()
        sembrado = hijo_demo_de_mama()

        creados = await RepoIdentidad(conexion).materializar_hijos(
            mama,
            [HijoMatricula(colegio_id=_piloto(), grado="Quinto", apodo="Pipe")],
            ANIO_FIJO,
            cifrador_desde_entorno(),
        )

        assert creados == 1
        matricula = await db.get(Matricula, sembrado["matricula"]["id"])
        assert matricula is not None
        assert matricula.estudiante_id == sembrado["estudiante"]["id"]
        assert (matricula.sede_id, matricula.colegio_id) == (_sede_piloto(), _piloto())
        estudiante = await db.get(Estudiante, sembrado["estudiante"]["id"])
        assert estudiante is not None
        assert estudiante.nombre_cifrado == sembrado["estudiante"]["nombre_cifrado"]


class TestSembrar:
    async def test_escribe_lo_que_informa_y_deja_las_filas_con_sus_ids_derivados(self, bd):
        _, consultar = bd

        escritos = await sembrar(CLAVE_DEMO)

        assert escritos == CONTEO_ESPERADO
        for tabla, esperado in CONTEO_ESPERADO.items():
            assert consultar.contar(tabla) == esperado, tabla
        usuarios = {f.correo: f for f in consultar(select(Usuario.__table__))}
        assert set(usuarios) == {f["usuario"]["correo"] for f in usuarios_demo(CLAVE_DEMO)}  # type: ignore[index]
        assert usuarios["admin@tukit.co"].id == derivar("usuario", "admin@tukit.co")
        assert all(verificar_clave(CLAVE_DEMO, u.clave_hash) for u in usuarios.values())
        roles = {f.codigo: f for f in consultar(select(Rol.__table__))}
        assert set(roles) == {"acudiente", "colegio_admin", "colegio_docente", "operador", "admin"}
        assert all(r.del_sistema for r in roles.values())

    async def test_sembrar_dos_veces_no_duplica_nada(self, bd):
        _, consultar = bd

        await sembrar(CLAVE_DEMO)
        segunda = await sembrar(CLAVE_DEMO)

        assert segunda == CONTEO_ESPERADO  # lo que informa es lo que intento, no lo que creo
        for tabla, esperado in CONTEO_ESPERADO.items():
            assert consultar.contar(tabla) == esperado, tabla

    async def test_re_sembrar_con_otra_clave_la_refresca_en_la_misma_cuenta(self, bd):
        """El upsert actualiza `clave_hash`: re-ejecutar con `--clave` es la
        forma de rotar la clave de la demostracion sin crear una segunda cuenta."""
        _, consultar = bd
        await sembrar("clave-uno-ficticia")
        antes = consultar(select(Usuario.__table__.c.id, Usuario.__table__.c.clave_hash))

        await sembrar("clave-dos-ficticia")
        despues = {f.id: f.clave_hash for f in consultar(select(Usuario.__table__))}

        assert set(despues) == {f.id for f in antes}
        assert all(verificar_clave("clave-dos-ficticia", h) for h in despues.values())
        assert not any(verificar_clave("clave-uno-ficticia", h) for h in despues.values())

    async def test_re_sembrar_restaura_el_texto_del_rol_pero_respeta_un_permiso_ajustado(self, bd):
        """Roles: `DO UPDATE` (nombre y descripcion). Permisos: `DO NOTHING`, asi
        que una clasificacion que alguien endurecio a mano sobrevive a re-sembrar."""
        url, consultar = bd
        await sembrar(CLAVE_DEMO)
        motor = create_async_engine(url)
        async with motor.begin() as conexion:
            await conexion.execute(
                Rol.__table__.update()
                .where(Rol.__table__.c.codigo == "acudiente")
                .values(descripcion="editada")
            )
            await conexion.execute(
                Permiso.__table__.update()
                .where(Permiso.__table__.c.codigo == "trabajo:crear")
                .values(clasificacion_minima=Clasificacion.MENOR.value)
            )
        await motor.dispose()

        await sembrar(CLAVE_DEMO)

        [rol] = consultar(select(Rol.__table__).where(Rol.__table__.c.codigo == "acudiente"))
        assert rol.descripcion == "Arma la lista de sus hijos."
        [permiso] = consultar(select(Permiso.__table__).where(Permiso.__table__.c.codigo == "trabajo:crear"))
        assert permiso.clasificacion_minima == Clasificacion.MENOR.value

    async def test_el_hijo_de_mama_queda_vinculado_a_ella_y_a_nadie_mas(self, bd, reloj_fijo: int):
        _, consultar = bd

        await sembrar(CLAVE_DEMO)

        [vinculo] = consultar(select(AcudienteMatricula.__table__))
        assert vinculo.usuario_id == derivar("usuario", "mama@ejemplo.com")
        assert vinculo.es_principal is True
        [matricula] = consultar(select(Matricula.__table__))
        assert (matricula.grado, matricula.anio_lectivo) == ("Quinto", ANIO_FIJO)
        assert matricula.id == vinculo.matricula_id


class TestLoSembradoResponde:
    """Los permisos sembrados contra `puede()`, el punto donde el modelo de
    autorizacion se vuelve decision."""

    @pytest.fixture
    async def conexion(self, bd):
        url, _ = bd
        await sembrar(CLAVE_DEMO)
        motor = create_async_engine(url)
        async with motor.connect() as conexion:
            yield RepoIdentidad(conexion)
        await motor.dispose()

    async def test_el_admin_y_el_operador_leen_nombres_de_adultos_a_nivel_global_la_mama_no(self, conexion):
        admin, operador, mama = (
            derivar("usuario", c) for c in ("admin@tukit.co", "operador@tukit.co", "mama@ejemplo.com")
        )

        assert await conexion.puede(admin, "usuario:leer:nombre", Ambito.global_()) is True
        assert await conexion.puede(operador, "usuario:leer:nombre", Ambito.global_()) is True
        assert await conexion.puede(mama, "usuario:leer:nombre", Ambito.global_()) is False

    async def test_la_mama_ve_apodos_en_su_colegio_pero_no_en_otro_ni_publica_listas(self, conexion):
        mama = derivar("usuario", "mama@ejemplo.com")
        otro_colegio = Ambito.colegio(derivar("colegio", "9.99"))

        assert await conexion.puede(mama, "estudiante:leer:apodo", Ambito.colegio(_piloto())) is True
        assert await conexion.puede(mama, "estudiante:leer:apodo", Ambito.sede(_sede_piloto())) is True
        assert await conexion.puede(mama, "estudiante:leer:apodo", otro_colegio) is False
        assert await conexion.puede(mama, "lista:publicar", Ambito.colegio(_piloto())) is False

    async def test_la_rectoria_publica_la_lista_de_su_colegio_y_no_la_de_otro(self, conexion):
        rectoria = derivar("usuario", "rectoria@colegio.edu.co")

        assert await conexion.puede(rectoria, "lista:publicar", Ambito.colegio(_piloto())) is True
        assert (
            await conexion.puede(rectoria, "lista:publicar", Ambito.colegio(derivar("colegio", "9.99")))
            is False
        )
        assert await conexion.puede(rectoria, "cola:leer", Ambito.colegio(_piloto())) is False

    async def test_ningun_rol_demo_puede_leer_el_apodo_si_no_es_acudiente(self, conexion):
        for correo in (
            "rectoria@colegio.edu.co",
            "docente@colegio.edu.co",
            "operador@tukit.co",
            "admin@tukit.co",
        ):
            assert (
                await conexion.puede(
                    derivar("usuario", correo), "estudiante:leer:apodo", Ambito.colegio(_piloto())
                )
                is False
            ), correo


class TestEntrarConLaClaveDeDemostracion:
    @pytest.fixture
    async def cliente(self, bd):
        url, _ = bd
        await sembrar(CLAVE_DEMO)
        motor = create_async_engine(url)
        app.state.motor = MotorServicio(
            servicio="identidad", engine=motor, _fabrica=async_sessionmaker(motor, expire_on_commit=False)
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            yield http
        await motor.dispose()

    async def _token(self, cliente: httpx.AsyncClient, correo: str, clave: str = CLAVE_DEMO) -> str:
        respuesta = await cliente.post("/v1/sesiones", json={"correo": correo, "clave": clave})
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()["token"]

    async def test_la_mama_entra_con_demo1234_y_la_sesion_trae_su_rol(self, cliente):
        respuesta = await cliente.post(
            "/v1/sesiones", json={"correo": "mama@ejemplo.com", "clave": "demo1234"}
        )

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["token"]
        assert [r["rol"] for r in cuerpo["sesion"]["roles"]] == ["acudiente"]

    async def test_una_clave_equivocada_es_401_con_el_mismo_mensaje_que_un_correo_inexistente(self, cliente):
        mala = await cliente.post("/v1/sesiones", json={"correo": "mama@ejemplo.com", "clave": "incorrecta1"})
        ajena = await cliente.post("/v1/sesiones", json={"correo": "nadie@example.test", "clave": "demo1234"})

        assert mala.status_code == ajena.status_code == 401
        assert mala.json() == ajena.json()
        assert mala.json()["error"] == "credenciales_invalidas"

    async def test_cada_acudiente_ve_solo_su_hijo_y_el_padre_sin_hijos_no_ve_el_de_ella(self, cliente):
        token_mama = await self._token(cliente, "mama@ejemplo.com")
        token_papa = await self._token(cliente, "papa@ejemplo.com")

        de_mama = await cliente.get(
            "/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token_mama}"}
        )
        de_papa = await cliente.get(
            "/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token_papa}"}
        )

        assert de_mama.status_code == de_papa.status_code == 200
        assert de_mama.json()["total"] == 1
        [matricula] = de_mama.json()["matriculas"]
        assert matricula["grado"] == "Quinto"
        assert matricula["apodo"] == "Pipe"
        assert matricula["colegio_id"] == str(_piloto())
        assert de_papa.json() == {"total": 0, "matriculas": []}


class TestMain:
    """`main` corre `asyncio.run(sembrar(...))`: las pruebas son sincronas."""

    def test_imprime_el_informe_por_tabla_y_la_clave_y_sale_con_0(
        self, bd, capsys: pytest.CaptureFixture[str]
    ):
        _, consultar = bd

        assert sembrar_acceso.main(["--clave", "clave-ficticia-cli"]) == 0

        salida = capsys.readouterr().out
        assert "=== acceso sembrado ===" in salida
        for tabla, n in CONTEO_ESPERADO.items():
            assert f"  {tabla:20} {n:4}" in salida
        assert "Usuarios de demostracion con clave `clave-ficticia-cli`." in salida
        usuarios = consultar(select(Usuario.__table__))
        assert len(usuarios) == 6
        assert all(verificar_clave("clave-ficticia-cli", u.clave_hash) for u in usuarios)

    def test_sin_argumentos_usa_la_clave_publica_de_demostracion(
        self, bd, capsys: pytest.CaptureFixture[str]
    ):
        _, consultar = bd

        assert sembrar_acceso.main([]) == 0

        assert f"con clave `{CLAVE_DEMO}`" in capsys.readouterr().out
        assert all(verificar_clave(CLAVE_DEMO, u.clave_hash) for u in consultar(select(Usuario.__table__)))

    def test_un_argumento_desconocido_lo_rechaza_el_analizador_con_2(
        self, bd, capsys: pytest.CaptureFixture[str]
    ):
        _, consultar = bd

        with pytest.raises(SystemExit) as salida:
            sembrar_acceso.main(["--no-existe"])

        assert salida.value.code == 2
        assert consultar.contar("usuario") == 0

    def test_ejecutado_como_script_siembra_y_sale_con_el_codigo_de_main(
        self, bd, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        _, consultar = bd
        monkeypatch.delitem(sys.modules, "tukit_identidad.sembrar_acceso")
        monkeypatch.setattr(sys, "argv", ["sembrar_acceso", "--clave", "clave-ficticia-script"])

        with pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_identidad.sembrar_acceso", run_name="__main__")

        assert salida.value.code == 0
        assert "=== acceso sembrado ===" in capsys.readouterr().out
        assert consultar.contar("usuario") == 6
