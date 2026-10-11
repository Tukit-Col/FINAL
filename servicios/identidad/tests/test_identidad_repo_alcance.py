"""NFR-MAN-01: el alcance de los datos en el repositorio de Identidad, contra una base de verdad.

`test_autorizacion.py` fija `puede`, `roles_vigentes` y la jerarquia de ambitos.
Lo que sigue sin vigilancia es el SQL que decide QUIEN VE QUE DATO una vez
resuelto el rol, que es donde un filtro olvidado se vuelve una fuga entre
familias:

- `campos_visibles`: el permiso de OTRO recurso o de otra accion no concede
  nada, un permiso general llega hasta su clasificacion y no mas, y el permiso
  de un campo se suma sin abrir el resto;
- `matriculas_visibles`: un rol sobre una sede (o sobre una matricula) alcanza
  solo lo suyo, y un rol caducado o futuro no alcanza nada;
- `hijos_del_padre`, `matriculas_del_titular`, `conteo_matriculas_por_par`:
  filtran por el titular del token, no por el rol; un coordinador que ve la
  matricula de otra familia NO la recibe como si fuera su hijo;
- `padron_acudientes`: solo cuentas reales y activas SIN rol interno vigente;
  acotar por `ids` nunca abre lo que el filtro cerro; nunca baja `clave_hash`;
- `es_staff_vigente`, `armar_sesion`, `nombres_de`: la vigencia de un rol se
  respeta (caducado, futuro) y el nombre de un menor nunca sale por la puerta
  de los adultos;
- el alta de la cuenta: crear, promover al invitado, o rechazar sin tocar nada
  (una ruta publica que mutara una cuenta real dejaria a un tercero colgar
  matriculas de la familia de otro);
- la libreta de direcciones: una direccion ajena o archivada no se ve ni se
  edita, y archivar baja la marca de predeterminada.

Se llaman los metodos del repositorio directamente sobre SQLite en memoria, con
las funciones auxiliares del `conftest`. Todos los nombres, apodos y correos son
ficticios (`@example.test`); el cifrador del entorno es el de texto en claro,
que se ve a simple vista en un volcado.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from tukit_comun import derivar
from tukit_comun.cifrado import VARIABLE_LLAVE as VARIABLE_CIFRADO
from tukit_comun.cifrado import CifradorEnClaro, cifrador_desde_entorno
from tukit_comun.http import ErrorDominio
from tukit_identidad.dominio.autorizacion import Ambito
from tukit_identidad.dominio.matriculas import HijoMatricula
from tukit_identidad.dominio.sesiones import verificar_clave
from tukit_identidad.modelos import (
    AcudienteMatricula,
    AmbitoTipo,
    Base,
    Clasificacion,
    Colegio,
    Estudiante,
    Matricula,
    Permiso,
    Rol,
    Sede,
    Usuario,
)
from tukit_identidad.repositorios.identidad import RepoIdentidad

from tests.conftest import (
    asignar,
    crear_colegio_con_sede,
    crear_matricula,
    crear_rol_con_permisos,
    crear_usuario,
    vincular_acudiente,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

T = Base.metadata.tables
_EN_CLARO = CifradorEnClaro()


@pytest.fixture(autouse=True)
def _cifrado_en_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin llave de cifrado el entorno cae al cifrador de texto en claro."""
    monkeypatch.delenv(VARIABLE_CIFRADO, raising=False)


def _ahora() -> datetime:
    return datetime.now(UTC)


def _claro(texto: str) -> bytes:
    return _EN_CLARO.cifrar(texto.encode("utf-8"))


async def _roles(db, *codigos: str) -> None:
    """Las filas de `rol` que referencian las asignaciones (FK real en Postgres)."""
    for codigo in codigos:
        db.add(Rol(codigo=codigo, nombre=codigo))
    await db.flush()


async def _usuario(
    db,
    correo: str,
    *,
    clave_hash: str = "hash-real",
    nombre: str | None = None,
    activo: bool = True,
    celular: str | None = None,
    creado_en: datetime | None = None,
) -> Usuario:
    campos: dict[str, Any] = {
        "correo": correo,
        "clave_hash": clave_hash,
        "activo": activo,
        "celular": celular,
    }
    if nombre is not None:
        campos["nombre_cifrado"] = _claro(nombre)
    if creado_en is not None:
        campos["creado_en"] = creado_en
    usuario = Usuario(**campos)
    db.add(usuario)
    await db.flush()
    return usuario


async def _hijo(
    db,
    usuario: Usuario,
    sede: Sede,
    *,
    grado: str = "Quinto",
    apodo: str = "Apodo Ficticio",
    anio: int = 2026,
    estado: str = "activa",
    vinculo_hasta: datetime | None = None,
) -> Matricula:
    """Estudiante + matricula + vinculo, con el apodo cifrado como lo guarda el producto."""
    estudiante = Estudiante(nombre_cifrado=_claro(apodo))
    db.add(estudiante)
    await db.flush()
    cierre: dict[str, Any] = {} if estado == "activa" else {"cerrado_en": _ahora()}
    matricula = Matricula(
        estudiante_id=estudiante.id,
        sede_id=sede.id,
        colegio_id=sede.colegio_id,
        grado=grado,
        anio_lectivo=anio,
        estado=estado,
        **cierre,
    )
    db.add(matricula)
    await db.flush()
    vinculo: dict[str, Any] = {}
    if vinculo_hasta is not None:
        vinculo = {"vigente_desde": vinculo_hasta - timedelta(days=30), "vigente_hasta": vinculo_hasta}
    db.add(
        AcudienteMatricula(
            usuario_id=usuario.id, matricula_id=matricula.id, apodo_cifrado=_claro(apodo), **vinculo
        )
    )
    await db.flush()
    return matricula


async def _filas(db, tabla: str) -> list[Any]:
    return list((await db.execute(select(T[tabla]))).all())


async def _contar(db, tabla: str) -> int:
    return int(await db.scalar(select(func.count()).select_from(T[tabla])))


def _permiso(codigo: str, recurso: str, accion: str, minima: Clasificacion, campo: str | None = None):
    return Permiso(
        codigo=codigo, recurso=recurso, accion=accion, campo=campo, clasificacion_minima=minima.value
    )


class TestCamposVisibles:
    CAMPOS = {
        "grado": Clasificacion.PUBLICO,
        "sede": Clasificacion.INTERNO,
        "celular": Clasificacion.PERSONAL,
        "nombre": Clasificacion.MENOR,
    }

    async def test_el_permiso_de_otro_recurso_no_concede_ningun_campo_de_este(self, db):
        usuario = await crear_usuario(db, "contador@example.test")
        await crear_rol_con_permisos(
            db, "contador", [_permiso("pedido:leer", "pedido", "leer", Clasificacion.MENOR)]
        )
        await asignar(db, usuario, "contador", AmbitoTipo.GLOBAL)
        repo = RepoIdentidad(db)

        propio = await repo.campos_visibles(usuario.id, "pedido", Ambito.global_(), self.CAMPOS)
        ajeno = await repo.campos_visibles(usuario.id, "estudiante", Ambito.global_(), self.CAMPOS)

        assert propio == set(self.CAMPOS)  # el permiso existe y llega al techo: control
        assert ajeno == set()

    async def test_solo_la_accion_leer_da_visibilidad_no_la_de_editar(self, db):
        usuario = await crear_usuario(db, "editor@example.test")
        await crear_rol_con_permisos(
            db, "editor", [_permiso("estudiante:editar", "estudiante", "editar", Clasificacion.MENOR)]
        )
        await asignar(db, usuario, "editor", AmbitoTipo.GLOBAL)

        visibles = await RepoIdentidad(db).campos_visibles(
            usuario.id, "estudiante", Ambito.global_(), self.CAMPOS
        )

        assert visibles == set()

    async def test_un_permiso_general_llega_hasta_su_clasificacion_y_no_mas_alla(self, db):
        usuario = await crear_usuario(db, "analista@example.test")
        await crear_rol_con_permisos(
            db, "analista", [_permiso("estudiante:leer", "estudiante", "leer", Clasificacion.INTERNO)]
        )
        await asignar(db, usuario, "analista", AmbitoTipo.GLOBAL)

        visibles = await RepoIdentidad(db).campos_visibles(
            usuario.id, "estudiante", Ambito.global_(), self.CAMPOS
        )

        assert visibles == {"grado", "sede"}
        assert "celular" not in visibles and "nombre" not in visibles

    async def test_con_dos_roles_gana_el_techo_general_mas_alto_y_un_permiso_de_campo_mas_bajo_no_lo_rebaja(
        self, db
    ):
        usuario = await crear_usuario(db, "soporte@example.test")
        await crear_rol_con_permisos(
            db,
            "soporte_basico",
            [_permiso("estudiante:leer:basico", "estudiante", "leer", Clasificacion.INTERNO)],
        )
        await crear_rol_con_permisos(
            db,
            "soporte_ampliado",
            [
                _permiso("estudiante:leer:ampliado", "estudiante", "leer", Clasificacion.PERSONAL),
                _permiso("estudiante:leer:celular", "estudiante", "leer", Clasificacion.INTERNO, "celular"),
            ],
        )
        await asignar(db, usuario, "soporte_basico", AmbitoTipo.GLOBAL)
        await asignar(db, usuario, "soporte_ampliado", AmbitoTipo.GLOBAL)

        visibles = await RepoIdentidad(db).campos_visibles(
            usuario.id, "estudiante", Ambito.global_(), self.CAMPOS
        )

        # El techo general mas alto (PERSONAL) manda; el permiso de `celular` (INTERNO) no lo rebaja.
        # El campo de menor sigue cerrado porque ningun permiso llega a su clasificacion.
        assert visibles == {"grado", "sede", "celular"}

    async def test_un_campo_que_ningun_permiso_nombra_ni_cubre_no_es_visible(self, db):
        usuario = await crear_usuario(db, "puntual@example.test")
        await crear_rol_con_permisos(
            db,
            "puntual",
            [_permiso("estudiante:leer:celular", "estudiante", "leer", Clasificacion.PERSONAL, "celular")],
        )
        await asignar(db, usuario, "puntual", AmbitoTipo.GLOBAL)

        visibles = await RepoIdentidad(db).campos_visibles(
            usuario.id, "estudiante", Ambito.global_(), self.CAMPOS
        )

        assert visibles == {"celular"}


class TestMatriculasVisibles:
    async def test_un_rol_sobre_una_sede_alcanza_sus_matriculas_y_no_las_de_la_sede_vecina(self, db):
        colegio, sede_a = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        sede_b = Sede(colegio_id=colegio.id, nombre="Sede B Ficticia")
        db.add(sede_b)
        await db.flush()
        matricula_a = await crear_matricula(db, sede_a)
        matricula_b = await crear_matricula(db, sede_b)
        coordinador = await crear_usuario(db, "coordinador@example.test")
        await _roles(db, "coordinador")
        await asignar(db, coordinador, "coordinador", AmbitoTipo.SEDE, sede_a.id)

        visibles = await RepoIdentidad(db).matriculas_visibles(coordinador.id)

        assert visibles == {matricula_a.id}
        assert matricula_b.id not in visibles

    async def test_un_rol_sobre_una_matricula_alcanza_solo_esa(self, db):
        _, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        propia = await crear_matricula(db, sede)
        otra = await crear_matricula(db, sede)
        tutor = await crear_usuario(db, "tutor@example.test")
        await _roles(db, "tutor")
        await asignar(db, tutor, "tutor", AmbitoTipo.MATRICULA, propia.id)

        visibles = await RepoIdentidad(db).matriculas_visibles(tutor.id)

        assert visibles == {propia.id}
        assert otra.id not in visibles

    async def test_el_vinculo_de_acudiente_y_el_rol_con_ambito_se_unen(self, db):
        colegio_a, sede_a = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        _, sede_b = await crear_colegio_con_sede(db, "Colegio Ficticio Dos")
        de_la_sede = await crear_matricula(db, sede_a)
        de_la_familia = await crear_matricula(db, sede_b)
        ajena = await crear_matricula(db, sede_b)
        usuario = await crear_usuario(db, "doble@example.test")
        await _roles(db, "rector")
        await asignar(db, usuario, "rector", AmbitoTipo.COLEGIO, colegio_a.id)
        await vincular_acudiente(db, usuario, de_la_familia)

        visibles = await RepoIdentidad(db).matriculas_visibles(usuario.id)

        assert visibles == {de_la_sede.id, de_la_familia.id}
        assert ajena.id not in visibles

    @pytest.mark.parametrize("momento", ["caducado", "futuro"])
    async def test_un_rol_caducado_o_futuro_no_hace_visible_ninguna_matricula(self, db, momento: str):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        await crear_matricula(db, sede)
        usuario = await crear_usuario(db, "vigencia@example.test")
        await _roles(db, "rector")
        ahora = _ahora()
        if momento == "caducado":
            ventana = {
                "vigente_desde": ahora - timedelta(days=10),
                "vigente_hasta": ahora - timedelta(days=1),
            }
        else:
            ventana = {"vigente_desde": ahora + timedelta(days=1)}
        await asignar(db, usuario, "rector", AmbitoTipo.COLEGIO, colegio.id, **ventana)

        assert await RepoIdentidad(db).matriculas_visibles(usuario.id) == set()


class TestColegios:
    async def test_el_listado_trae_solo_colegios_activos_ordenados_y_cuenta_solo_sedes_activas(self, db):
        zeta, _ = await crear_colegio_con_sede(db, "Zeta Colegio Ficticio")
        alfa, _ = await crear_colegio_con_sede(db, "Alfa Colegio Ficticio")
        db.add_all(
            [
                Sede(colegio_id=alfa.id, nombre="Alfa sede dos"),
                Sede(colegio_id=alfa.id, nombre="Alfa sede cerrada", activa=False),
                Colegio(nombre="Beta Colegio Inactivo", activo=False),
            ]
        )
        await db.flush()

        filas = await RepoIdentidad(db).listar_colegios(None)

        assert [(f.nombre, f.sedes) for f in filas] == [
            ("Alfa Colegio Ficticio", 2),
            ("Zeta Colegio Ficticio", 1),
        ]
        assert {f.id for f in filas} == {alfa.id, zeta.id}

    async def test_la_busqueda_ignora_mayusculas_y_filtra_por_trozo_del_nombre(self, db):
        await crear_colegio_con_sede(db, "Colegio Ficticio Norte")
        await crear_colegio_con_sede(db, "Liceo Ficticio Sur")
        repo = RepoIdentidad(db)

        assert [f.nombre for f in await repo.listar_colegios("COLEGIO")] == ["Colegio Ficticio Norte"]
        assert [f.nombre for f in await repo.listar_colegios("ficticio s")] == ["Liceo Ficticio Sur"]
        assert len(await repo.listar_colegios("ficticio")) == 2
        assert await repo.listar_colegios("no-existe-ninguno") == []

    async def test_ver_existe_y_sedes_de_solo_miran_el_colegio_pedido_y_sus_sedes_activas(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        db.add(Sede(colegio_id=colegio.id, nombre="Sede cerrada", activa=False))
        otro, _ = await crear_colegio_con_sede(db, "Colegio Ficticio Dos")
        await db.flush()
        repo = RepoIdentidad(db)

        ficha = await repo.ver_colegio(colegio.id)
        sedes = await repo.sedes_de(colegio.id)

        assert ficha is not None and ficha.nombre == "Colegio Ficticio Uno"
        assert await repo.ver_colegio(uuid.uuid4()) is None
        assert await repo.existe_colegio(colegio.id) == colegio.id
        assert await repo.existe_colegio(uuid.uuid4()) is None
        assert [s.id for s in sedes] == [sede.id]
        assert otro.id not in {s.colegio_id for s in sedes}

    async def test_editar_aplica_solo_lo_pedido_y_sin_valores_no_toca_nada(self, db):
        colegio, _ = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        repo = RepoIdentidad(db)

        await repo.editar_colegio(colegio.id, {})
        sin_cambios = await repo.ver_colegio(colegio.id)
        await repo.editar_colegio(colegio.id, {"sitio_web": "https://uno.example.test"})
        editado = await repo.ver_colegio(colegio.id)

        assert sin_cambios.sitio_web is None
        assert editado.sitio_web == "https://uno.example.test"
        assert editado.nombre == "Colegio Ficticio Uno"


class TestContactoYSesion:
    async def test_registrar_un_contacto_deja_un_invitado_sin_credencial_y_es_idempotente(self, db):
        repo = RepoIdentidad(db)

        primero, creado = await repo.registrar_contacto("invitado@example.test")
        segundo, creado_otra_vez = await repo.registrar_contacto("invitado@example.test")

        assert creado is True and creado_otra_vez is False
        assert segundo == primero
        assert await _contar(db, "usuario") == 1
        fila = await repo.usuario_por_correo("invitado@example.test")
        assert fila.clave_hash == "sin-credencial"
        assert verificar_clave("sin-credencial", fila.clave_hash) is False

    async def test_contacto_de_devuelve_correo_y_estado_o_nada_si_no_existe(self, db):
        usuario = await _usuario(db, "inactivo@example.test", activo=False)
        repo = RepoIdentidad(db)

        fila = await repo.contacto_de(usuario.id)

        assert (fila.correo, fila.activo) == ("inactivo@example.test", False)
        assert await repo.contacto_de(uuid.uuid4()) is None
        assert await repo.usuario_por_correo("nadie@example.test") is None
        assert (await repo.usuario_del_token(uuid.uuid4())) is None

    async def test_la_sesion_trae_el_nombre_descifrado_los_roles_vigentes_y_la_version(self, db):
        colegio, _ = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        usuario = await _usuario(db, "acudiente@example.test", nombre="Acudiente Ficticio")
        await _roles(db, "acudiente", "admin", "rector")
        ahora = _ahora()
        await asignar(db, usuario, "acudiente", AmbitoTipo.COLEGIO, colegio.id)
        await asignar(db, usuario, "admin", AmbitoTipo.GLOBAL)
        await asignar(
            db,
            usuario,
            "rector",
            AmbitoTipo.COLEGIO,
            colegio.id,
            vigente_desde=ahora - timedelta(days=9),
            vigente_hasta=ahora - timedelta(days=1),
        )
        repo = RepoIdentidad(db)

        sesion = await repo.armar_sesion(await repo.usuario_del_token(usuario.id))

        assert sesion["usuario_id"] == str(usuario.id)
        assert sesion["correo"] == "acudiente@example.test"
        assert sesion["nombre"] == "Acudiente Ficticio"
        assert sesion["version_permisos"] == 1
        assert isinstance(sesion["version_permisos"], int)
        assert sorted(sesion["roles"], key=lambda r: r["rol"]) == [
            {"rol": "acudiente", "ambito": {"tipo": "colegio", "id": str(colegio.id)}},
            {"rol": "admin", "ambito": {"tipo": "global", "id": None}},
        ]

    async def test_sin_nombre_cifrado_la_sesion_usa_el_correo_como_nombre(self, db):
        invitado = await _usuario(db, "sinnombre@example.test")
        repo = RepoIdentidad(db)

        sesion = await repo.armar_sesion(await repo.usuario_del_token(invitado.id))

        assert sesion["nombre"] == "sinnombre@example.test"
        assert sesion["roles"] == []


class TestNombresDeAdultos:
    async def test_solo_aparecen_los_adultos_con_nombre_y_su_id_va_como_texto(self, db):
        con_nombre = await _usuario(db, "mama@example.test", nombre="Acudiente Ficticio Uno")
        invitado = await _usuario(db, "invitado@example.test", clave_hash="sin-credencial")

        nombres = await RepoIdentidad(db).nombres_de([con_nombre.id, invitado.id, uuid.uuid4()])

        assert nombres == {str(con_nombre.id): "Acudiente Ficticio Uno"}

    async def test_una_lista_vacia_no_consulta_nada_y_devuelve_vacio(self, db):
        assert await RepoIdentidad(db).nombres_de([]) == {}

    async def test_un_nombre_con_bytes_invalidos_no_rompe_y_se_marca_con_el_caracter_de_reemplazo(self, db):
        usuario = Usuario(
            correo="raro@example.test", clave_hash="hash-real", nombre_cifrado=b"claro:Nombre \xff"
        )
        db.add(usuario)
        await db.flush()

        nombres = await RepoIdentidad(db).nombres_de([usuario.id])

        assert nombres == {str(usuario.id): "Nombre �"}

    async def test_pedir_el_id_de_un_estudiante_nunca_devuelve_el_nombre_del_menor(self, db):
        """`nombres_de` consulta `usuario`, nunca `estudiante`: el id de un menor
        no resuelve nada, aunque su fila guarde un marcador cifrado."""
        _, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        matricula = await _hijo(db, madre, sede, apodo="Estudiante Ficticio Uno")

        nombres = await RepoIdentidad(db).nombres_de([matricula.estudiante_id, matricula.id])

        assert nombres == {}


class TestLibretaDeDirecciones:
    async def _nueva(self, repo: RepoIdentidad, usuario: Usuario, **extra: Any) -> Any:
        valores: dict[str, Any] = {
            "usuario_id": usuario.id,
            "ciudad": "Ciudad Ficticia",
            "linea_cifrada": _claro("Calle Ficticia 1 # 2-3"),
            "predeterminada": False,
        }
        valores.update(extra)
        return await repo.crear_direccion(**valores)

    async def test_crear_devuelve_la_fila_con_etiqueta_por_omision_y_la_lista_solo_trae_las_propias(self, db):
        yo = await crear_usuario(db, "yo@example.test")
        otra = await crear_usuario(db, "otra@example.test")
        repo = RepoIdentidad(db)

        propia = await self._nueva(repo, yo)
        await self._nueva(repo, otra, ciudad="Otra Ciudad")

        assert propia.etiqueta == "casa"
        assert propia.archivada_en is None
        assert [d.id for d in await repo.direcciones_de(yo.id)] == [propia.id]

    async def test_la_predeterminada_va_primero_y_limpiarla_baja_la_marca_para_dar_paso_a_otra(self, db):
        yo = await crear_usuario(db, "yo@example.test")
        repo = RepoIdentidad(db)
        vieja = await self._nueva(repo, yo, predeterminada=True, etiqueta="vieja")
        comun = await self._nueva(repo, yo, etiqueta="comun")

        assert (await repo.direcciones_de(yo.id))[0].id == vieja.id

        await repo.limpiar_predeterminada(yo.id)
        nueva = await self._nueva(repo, yo, predeterminada=True, etiqueta="nueva")

        listadas = await repo.direcciones_de(yo.id)
        assert listadas[0].id == nueva.id
        assert [d.predeterminada for d in listadas].count(True) == 1
        assert {d.id for d in listadas} == {vieja.id, comun.id, nueva.id}

    async def test_una_direccion_ajena_no_se_obtiene_aunque_se_conozca_su_id(self, db):
        yo = await crear_usuario(db, "yo@example.test")
        otra = await crear_usuario(db, "otra@example.test")
        repo = RepoIdentidad(db)
        ajena = await self._nueva(repo, otra)

        assert await repo.obtener_direccion(ajena.id, yo.id) is None
        assert (await repo.obtener_direccion(ajena.id, otra.id)).id == ajena.id

    async def test_editar_cambia_solo_lo_pedido_y_devuelve_la_fila_nueva(self, db):
        yo = await crear_usuario(db, "yo@example.test")
        repo = RepoIdentidad(db)
        direccion = await self._nueva(repo, yo, localidad="Localidad Ficticia")

        editada = await repo.editar_direccion(direccion.id, etiqueta="trabajo")

        assert editada.etiqueta == "trabajo"
        assert editada.ciudad == "Ciudad Ficticia"
        assert editada.localidad == "Localidad Ficticia"
        assert editada.linea_cifrada == direccion.linea_cifrada

    async def test_archivar_es_baja_logica_quita_la_marca_y_solo_el_dueno_puede(self, db):
        yo = await crear_usuario(db, "yo@example.test")
        otra = await crear_usuario(db, "otra@example.test")
        repo = RepoIdentidad(db)
        direccion = await self._nueva(repo, yo, predeterminada=True)

        ajeno = await repo.archivar_direccion(direccion.id, otra.id)
        propio = await repo.archivar_direccion(direccion.id, yo.id)
        repetido = await repo.archivar_direccion(direccion.id, yo.id)

        assert (ajeno, propio, repetido) == (0, 1, 0)
        assert await repo.direcciones_de(yo.id) == []
        assert await repo.obtener_direccion(direccion.id, yo.id) is None
        # La fila sigue existiendo: un envio en curso aun la necesita.
        [fila] = await _filas(db, "direccion")
        assert fila.archivada_en is not None and fila.predeterminada is False


class TestAltaDeCuenta:
    async def test_un_correo_libre_se_crea_con_clave_hasheada_y_nombre_cifrado(self, db):
        repo = RepoIdentidad(db)

        fila, decision = await repo.crear_o_promover_cuenta(
            correo="nueva@example.test",
            clave="clave-ficticia-1",
            nombre="Acudiente Ficticio",
            celular="3000000000",
        )

        assert decision.value == "crear"
        assert fila.correo == "nueva@example.test"
        assert fila.celular == "3000000000"
        assert fila.clave_hash != "clave-ficticia-1"
        assert verificar_clave("clave-ficticia-1", fila.clave_hash) is True
        assert cifrador_desde_entorno().descifrar(fila.nombre_cifrado) == b"Acudiente Ficticio"
        assert await _contar(db, "usuario") == 1

    async def test_un_invitado_se_promueve_conservando_su_id(self, db):
        repo = RepoIdentidad(db)
        invitado, _ = await repo.registrar_contacto("invitado@example.test")

        fila, decision = await repo.crear_o_promover_cuenta(
            correo="invitado@example.test",
            clave="clave-ficticia-2",
            nombre="Acudiente Ficticio",
            celular=None,
        )

        assert decision.value == "promover"
        assert fila.id == invitado
        assert verificar_clave("clave-ficticia-2", fila.clave_hash) is True
        assert fila.nombre_cifrado is not None
        assert await _contar(db, "usuario") == 1

    async def test_una_cuenta_real_es_conflicto_y_no_se_toca_nada(self, db):
        repo = RepoIdentidad(db)
        await repo.crear_o_promover_cuenta(
            correo="real@example.test",
            clave="clave-ficticia-3",
            nombre="Titular Ficticio",
            celular="3000000000",
        )
        antes = await repo.usuario_por_correo("real@example.test")

        fila, decision = await repo.crear_o_promover_cuenta(
            correo="real@example.test", clave="otra-clave-ficticia", nombre="Intruso Ficticio", celular=None
        )

        despues = await repo.usuario_por_correo("real@example.test")
        assert decision.value == "conflicto"
        assert fila.id == antes.id
        assert (despues.clave_hash, despues.nombre_cifrado, despues.celular) == (
            antes.clave_hash,
            antes.nombre_cifrado,
            antes.celular,
        )
        assert verificar_clave("clave-ficticia-3", despues.clave_hash) is True
        assert verificar_clave("otra-clave-ficticia", despues.clave_hash) is False
        assert await _contar(db, "usuario") == 1

    async def test_otorgar_el_rol_acudiente_lo_limita_al_colegio_y_a_sus_sedes(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        otro, otra_sede = await crear_colegio_con_sede(db, "Colegio Ficticio Dos")
        usuario = await crear_usuario(db, "mama@example.test")
        await _roles(db, "acudiente")
        repo = RepoIdentidad(db)

        await repo.otorgar_rol_acudiente(usuario.id, colegio.id)

        assert await repo.roles_vigentes(usuario.id, Ambito.colegio(colegio.id)) == {"acudiente"}
        assert await repo.roles_vigentes(usuario.id, Ambito.sede(sede.id)) == {"acudiente"}
        assert await repo.roles_vigentes(usuario.id, Ambito.colegio(otro.id)) == set()
        assert await repo.roles_vigentes(usuario.id, Ambito.sede(otra_sede.id)) == set()
        [fila] = await _filas(db, "asignacion_rol")
        assert (fila.rol_codigo, fila.ambito_tipo, fila.ambito_id) == ("acudiente", "colegio", colegio.id)
        assert fila.vigente_hasta is None


class TestRegistrarUnHijo:
    async def test_deja_estudiante_matricula_vinculo_y_consentimiento_del_menor_en_un_solo_paso(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        repo = RepoIdentidad(db)

        matricula_id = await repo.registrar_hijo(
            usuario_id=madre.id,
            apodo="Estudiante Ficticio Uno",
            colegio_id=colegio.id,
            sede_id=sede.id,
            grado="Quinto",
            anio_lectivo=2026,
            version_consentimiento="v-ficticia-1",
        )

        [matricula] = await _filas(db, "matricula")
        [vinculo] = await _filas(db, "acudiente_matricula")
        [consentimiento] = await _filas(db, "consentimiento")
        [estudiante] = await _filas(db, "estudiante")
        assert matricula.id == matricula_id
        assert (matricula.colegio_id, matricula.sede_id, matricula.grado) == (colegio.id, sede.id, "Quinto")
        assert (vinculo.usuario_id, vinculo.matricula_id, vinculo.es_principal) == (
            madre.id,
            matricula_id,
            True,
        )
        # El consentimiento de menor dice DE CUAL hijo es (CHECK consentimiento_menor_coherente).
        assert consentimiento.matricula_id == matricula_id
        assert (consentimiento.regimen, consentimiento.version) == ("registro_menor", "v-ficticia-1")
        # Ni el estudiante ni el vinculo guardan el apodo en claro.
        assert b"Estudiante Ficticio Uno" in _EN_CLARO.descifrar(vinculo.apodo_cifrado)
        assert vinculo.apodo_cifrado.startswith(b"claro:")
        assert estudiante.nombre_cifrado.startswith(b"claro:")

    async def test_hijos_del_padre_devuelve_apodo_grado_y_colegio_de_sus_hijos(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        repo = RepoIdentidad(db)
        await repo.registrar_hijo(
            usuario_id=madre.id,
            apodo="Estudiante Ficticio Uno",
            colegio_id=colegio.id,
            sede_id=sede.id,
            grado="Tercero",
            anio_lectivo=2026,
            version_consentimiento="v-ficticia-1",
        )

        hijos = await repo.hijos_del_padre(madre.id)

        assert hijos == [
            {"apodo": "Estudiante Ficticio Uno", "grado": "Tercero", "colegio_id": str(colegio.id)}
        ]

    async def test_sin_vinculos_vigentes_no_hay_hijos(self, db):
        _, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        sin_hijos = await _usuario(db, "sinhijos@example.test")
        await _hijo(db, madre, sede, vinculo_hasta=_ahora() - timedelta(days=1))
        repo = RepoIdentidad(db)

        assert await repo.hijos_del_padre(sin_hijos.id) == []
        assert await repo.hijos_del_padre(madre.id) == []  # su vinculo ya termino

    async def test_un_vinculo_sin_apodo_devuelve_apodo_nulo_no_un_error(self, db):
        _, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await crear_usuario(db, "madre@example.test")
        matricula = await crear_matricula(db, sede, grado="Quinto")
        await vincular_acudiente(db, madre, matricula)

        [hijo] = await RepoIdentidad(db).hijos_del_padre(madre.id)

        assert hijo["apodo"] is None
        assert hijo["grado"] == "Quinto"

    async def test_un_rol_con_ambito_no_convierte_las_matriculas_ajenas_en_hijos_propios(self, db):
        """Un coordinador de la sede VE las matriculas de todas las familias
        (`matriculas_visibles`), pero `hijos_del_padre` filtra ademas por
        vinculo: el apodo de un menor ajeno no se le entrega como suyo."""
        _, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        coordinador = await _usuario(db, "coordinador@example.test")
        familia = await _usuario(db, "familia@example.test")
        propia = await _hijo(db, coordinador, sede, apodo="Hijo Propio Ficticio", grado="Primero")
        ajena = await _hijo(db, familia, sede, apodo="Hijo Ajeno Ficticio", grado="Segundo")
        await _roles(db, "coordinador")
        await asignar(db, coordinador, "coordinador", AmbitoTipo.SEDE, sede.id)
        repo = RepoIdentidad(db)

        assert await repo.matriculas_visibles(coordinador.id) == {propia.id, ajena.id}
        hijos = await repo.hijos_del_padre(coordinador.id)

        assert [h["apodo"] for h in hijos] == ["Hijo Propio Ficticio"]


class TestMaterializarHijos:
    async def _entorno(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        return colegio, sede, madre, RepoIdentidad(db)

    async def test_crea_estudiante_matricula_y_vinculo_con_ids_derivados_y_cuenta_lo_creado(self, db):
        colegio, sede, madre, repo = await self._entorno(db)

        creados = await repo.materializar_hijos(
            madre.id,
            [HijoMatricula(colegio.id, "Quinto", "Estudiante Ficticio Uno")],
            2026,
            cifrador_desde_entorno(),
        )

        estudiante_id = derivar("estudiante", str(madre.id), str(colegio.id), "Quinto", "2026")
        matricula_id = derivar("matricula", str(estudiante_id), str(sede.id), "Quinto", "2026")
        assert creados == 1
        [estudiante] = await _filas(db, "estudiante")
        [matricula] = await _filas(db, "matricula")
        [vinculo] = await _filas(db, "acudiente_matricula")
        assert estudiante.id == estudiante_id
        assert _EN_CLARO.descifrar(estudiante.nombre_cifrado) == b"Estudiante Ficticio Uno"
        assert (matricula.id, matricula.sede_id, matricula.anio_lectivo) == (matricula_id, sede.id, 2026)
        assert (vinculo.usuario_id, vinculo.matricula_id, vinculo.parentesco) == (
            madre.id,
            matricula_id,
            "acudiente",
        )

    async def test_reenviar_lo_mismo_es_idempotente_y_no_cuenta_nada_como_creado(self, db):
        colegio, _, madre, repo = await self._entorno(db)
        hijos = [HijoMatricula(colegio.id, "Quinto", "Estudiante Ficticio Uno")]

        primera = await repo.materializar_hijos(madre.id, hijos, 2026, cifrador_desde_entorno())
        segunda = await repo.materializar_hijos(madre.id, hijos, 2026, cifrador_desde_entorno())

        assert (primera, segunda) == (1, 0)
        for tabla in ("estudiante", "matricula", "acudiente_matricula"):
            assert await _contar(db, tabla) == 1

    async def test_los_gemelos_del_mismo_colegio_y_grado_no_colapsan_en_una_fila(self, db):
        colegio, sede, madre, repo = await self._entorno(db)
        gemelos = [
            HijoMatricula(colegio.id, "Quinto", "Gemelo Ficticio Uno"),
            HijoMatricula(colegio.id, "Quinto", "Gemelo Ficticio Dos"),
        ]

        creados = await repo.materializar_hijos(madre.id, gemelos, 2026, cifrador_desde_entorno())

        assert creados == 2
        primero = derivar("estudiante", str(madre.id), str(colegio.id), "Quinto", "2026")
        segundo = derivar("estudiante", str(madre.id), str(colegio.id), "Quinto", "2026", "2")
        assert {f.id for f in await _filas(db, "estudiante")} == {primero, segundo}
        assert await _contar(db, "matricula") == 2

    async def test_el_conteo_inicial_hace_que_el_hijo_siguiente_tome_el_ordinal_que_sigue(self, db):
        colegio, _, madre, repo = await self._entorno(db)
        cifrador = cifrador_desde_entorno()
        await repo.materializar_hijos(
            madre.id, [HijoMatricula(colegio.id, "Quinto", "Primero")], 2026, cifrador
        )
        conteo = await repo.conteo_matriculas_por_par(madre.id, 2026)

        creados = await repo.materializar_hijos(
            madre.id, [HijoMatricula(colegio.id, "Quinto", "Segundo")], 2026, cifrador, conteo_inicial=conteo
        )

        assert conteo == {(colegio.id, "Quinto"): 1}
        assert creados == 1
        assert await _contar(db, "estudiante") == 2
        assert derivar("estudiante", str(madre.id), str(colegio.id), "Quinto", "2026", "2") in {
            f.id for f in await _filas(db, "estudiante")
        }

    async def test_sin_apodo_el_estudiante_guarda_un_marcador_vacio_y_el_titular_lo_ve_como_nulo(self, db):
        colegio, _, madre, repo = await self._entorno(db)

        await repo.materializar_hijos(
            madre.id, [HijoMatricula(colegio.id, "Once")], 2026, cifrador_desde_entorno()
        )

        [estudiante] = await _filas(db, "estudiante")
        assert _EN_CLARO.descifrar(estudiante.nombre_cifrado) == b""
        [matricula] = await repo.matriculas_del_titular(madre.id)
        assert matricula["apodo"] is None

    async def test_un_grado_que_no_existe_se_rechaza_con_422_antes_de_escribir(self, db):
        colegio, _, madre, repo = await self._entorno(db)

        with pytest.raises(ErrorDominio) as error:
            await repo.materializar_hijos(
                madre.id,
                [HijoMatricula(colegio.id, "Doceavo", "Estudiante Ficticio Uno")],
                2026,
                cifrador_desde_entorno(),
            )

        assert (error.value.error, error.value.estado, error.value.campo) == ("grado_invalido", 422, "grado")
        assert await _contar(db, "estudiante") == 0

    @pytest.mark.parametrize("caso", ["no_existe", "sede_inactiva"])
    async def test_un_colegio_inexistente_o_sin_sede_activa_se_rechaza_con_422(self, db, caso: str):
        colegio, sede, madre, repo = await self._entorno(db)
        colegio_id = uuid.uuid4()
        if caso == "sede_inactiva":
            colegio_id = colegio.id
            sede.activa = False
            await db.flush()

        with pytest.raises(ErrorDominio) as error:
            await repo.materializar_hijos(
                madre.id,
                [HijoMatricula(colegio_id, "Quinto", "Estudiante Ficticio Uno")],
                2026,
                cifrador_desde_entorno(),
            )

        assert (error.value.error, error.value.estado, error.value.campo) == (
            "colegio_sin_sede",
            422,
            "colegio_id",
        )
        assert await _contar(db, "estudiante") == 0


class TestMatriculasDelTitular:
    async def test_devuelve_colegio_grado_anio_y_apodo_y_nada_mas(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        hijo = await _hijo(db, madre, sede, grado="Quinto", apodo="Estudiante Ficticio Uno", anio=2026)

        [matricula] = await RepoIdentidad(db).matriculas_del_titular(madre.id)

        # Desde 6864898 la lista trae `matricula_id` para que el panel quite o cambie
        # de colegio a un hijo (identidad.py:762-764): es el id de la MATRICULA, nunca
        # el del estudiante.
        assert matricula["matricula_id"] != str(hijo.estudiante_id)
        assert matricula == {
            "matricula_id": str(hijo.id),
            "colegio_id": str(colegio.id),
            "grado": "Quinto",
            "anio_lectivo": 2026,
            "apodo": "Estudiante Ficticio Uno",
        }

    async def test_excluye_matriculas_cerradas_vinculos_terminados_y_los_hijos_de_otros(self, db):
        _, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        otra = await _usuario(db, "otra@example.test")
        await _hijo(db, madre, sede, grado="Primero", apodo="Vigente")
        await _hijo(db, madre, sede, grado="Segundo", apodo="Retirado", estado="retirada")
        await _hijo(
            db,
            madre,
            sede,
            grado="Tercero",
            apodo="Vinculo terminado",
            vinculo_hasta=_ahora() - timedelta(days=2),
        )
        await _hijo(db, otra, sede, grado="Cuarto", apodo="De otra familia")

        matriculas = await RepoIdentidad(db).matriculas_del_titular(madre.id)

        assert [m["apodo"] for m in matriculas] == ["Vigente"]

    async def test_se_ordena_por_colegio_y_grado(self, db):
        _, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        await _hijo(db, madre, sede, grado="Sexto", apodo="Sexto Ficticio")
        await _hijo(db, madre, sede, grado="Octavo", apodo="Octavo Ficticio")

        matriculas = await RepoIdentidad(db).matriculas_del_titular(madre.id)

        assert [m["grado"] for m in matriculas] == ["Octavo", "Sexto"]

    async def test_el_conteo_por_par_filtra_por_anio_estado_y_vinculo_vigente(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        otra = await _usuario(db, "otra@example.test")
        await _hijo(db, madre, sede, grado="Quinto", apodo="Uno")
        await _hijo(db, madre, sede, grado="Quinto", apodo="Dos")
        await _hijo(db, madre, sede, grado="Quinto", apodo="Del anio pasado", anio=2025)
        await _hijo(db, madre, sede, grado="Quinto", apodo="Retirado", estado="retirada")
        await _hijo(
            db, madre, sede, grado="Quinto", apodo="Terminado", vinculo_hasta=_ahora() - timedelta(days=2)
        )
        await _hijo(db, madre, sede, grado="Sexto", apodo="Otro grado")
        await _hijo(db, otra, sede, grado="Quinto", apodo="De otra familia")
        repo = RepoIdentidad(db)

        conteo = await repo.conteo_matriculas_por_par(madre.id, 2026)

        assert conteo == {(colegio.id, "Quinto"): 2, (colegio.id, "Sexto"): 1}
        assert await repo.conteo_matriculas_por_par(madre.id, 2030) == {}


class TestStaffVigente:
    @pytest.mark.parametrize("rol", ["admin", "operador"])
    async def test_admin_y_operador_vigentes_son_staff(self, db, rol: str):
        usuario = await _usuario(db, f"{rol}@example.test")
        await _roles(db, rol)
        await asignar(db, usuario, rol, AmbitoTipo.GLOBAL)

        assert await RepoIdentidad(db).es_staff_vigente(usuario.id) is True

    @pytest.mark.parametrize("rol", ["acudiente", "colegio_admin", "colegio_docente", "rector"])
    async def test_los_demas_roles_no_son_staff(self, db, rol: str):
        colegio, _ = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        usuario = await _usuario(db, f"{rol}@example.test")
        await _roles(db, rol)
        await asignar(db, usuario, rol, AmbitoTipo.COLEGIO, colegio.id)

        assert await RepoIdentidad(db).es_staff_vigente(usuario.id) is False

    @pytest.mark.parametrize("momento", ["caducado", "futuro"])
    async def test_un_rol_de_staff_caducado_o_futuro_no_cuenta(self, db, momento: str):
        usuario = await _usuario(db, "exadmin@example.test")
        await _roles(db, "admin")
        ahora = _ahora()
        if momento == "caducado":
            ventana = {
                "vigente_desde": ahora - timedelta(days=10),
                "vigente_hasta": ahora - timedelta(days=1),
            }
        else:
            ventana = {"vigente_desde": ahora + timedelta(days=1)}
        await asignar(db, usuario, "admin", AmbitoTipo.GLOBAL, **ventana)

        assert await RepoIdentidad(db).es_staff_vigente(usuario.id) is False

    async def test_sin_ninguna_asignacion_no_es_staff(self, db):
        usuario = await _usuario(db, "nadie@example.test")

        assert await RepoIdentidad(db).es_staff_vigente(usuario.id) is False

    async def test_el_ambito_de_la_asignacion_no_se_mira_se_confia_en_que_staff_es_global(self, db):
        """Caracterizacion de una suposicion, no de un defecto: `es_staff_vigente`
        no filtra ambito (su docstring lo dice, porque `admin`/`operador` solo se
        siembran globales). Si alguien insertara un `admin` atado a un colegio,
        este predicado lo trataria como staff global. Nada en la base lo impide."""
        colegio, _ = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        usuario = await _usuario(db, "adminacotado@example.test")
        await _roles(db, "admin")
        await asignar(db, usuario, "admin", AmbitoTipo.COLEGIO, colegio.id)

        assert await RepoIdentidad(db).es_staff_vigente(usuario.id) is True


class TestPadronDeAcudientes:
    async def test_solo_cuentas_reales_y_activas_sin_rol_interno_vigente_entran_al_padron(self, db):
        colegio, _ = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        await _roles(db, "admin", "operador", "colegio_admin", "colegio_docente", "acudiente")
        ahora = _ahora()
        familia = await _usuario(db, "familia@example.test", celular="3000000000")
        exstaff = await _usuario(db, "exstaff@example.test")
        await asignar(
            db,
            exstaff,
            "operador",
            AmbitoTipo.GLOBAL,
            vigente_desde=ahora - timedelta(days=9),
            vigente_hasta=ahora - timedelta(days=1),
        )
        await _usuario(db, "invitado@example.test", clave_hash="sin-credencial")
        await _usuario(db, "baja@example.test", activo=False)
        for rol, tipo, ambito in (
            ("admin", AmbitoTipo.GLOBAL, None),
            ("operador", AmbitoTipo.GLOBAL, None),
            ("colegio_admin", AmbitoTipo.COLEGIO, colegio.id),
            ("colegio_docente", AmbitoTipo.COLEGIO, colegio.id),
        ):
            interno = await _usuario(db, f"{rol}@example.test")
            await asignar(db, interno, rol, tipo, ambito)
        await asignar(db, familia, "acudiente", AmbitoTipo.COLEGIO, colegio.id)

        padron = await RepoIdentidad(db).padron_acudientes(None)

        assert {p["correo"] for p in padron} == {"familia@example.test", "exstaff@example.test"}

    async def test_acotar_por_ids_va_sobre_el_filtro_y_nunca_lo_abre(self, db):
        await _roles(db, "admin")
        familia = await _usuario(db, "familia@example.test")
        otra = await _usuario(db, "otra@example.test")
        staff = await _usuario(db, "staff@example.test")
        invitado = await _usuario(db, "invitado@example.test", clave_hash="sin-credencial")
        await asignar(db, staff, "admin", AmbitoTipo.GLOBAL)
        repo = RepoIdentidad(db)

        acotado = await repo.padron_acudientes([familia.id, staff.id, invitado.id, uuid.uuid4()])
        vacio = await repo.padron_acudientes([])

        assert [p["usuario_id"] for p in acotado] == [str(familia.id)]
        assert vacio == []
        assert {p["correo"] for p in await repo.padron_acudientes(None)} == {
            "familia@example.test",
            "otra@example.test",
        }
        assert otra.id not in {uuid.UUID(p["usuario_id"]) for p in acotado}

    async def test_cada_entrada_trae_celular_fecha_e_hijos_y_nunca_la_clave_ni_el_nombre_legal(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(
            db,
            "madre@example.test",
            nombre="Acudiente Ficticio",
            celular="3000000000",
            creado_en=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        )
        await _hijo(db, madre, sede, grado="Quinto", apodo="Estudiante Ficticio Dos")
        await _hijo(db, madre, sede, grado="Primero", apodo="Estudiante Ficticio Uno")

        [entrada] = await RepoIdentidad(db).padron_acudientes(None)

        assert set(entrada) == {"usuario_id", "correo", "celular", "creado_en", "hijos"}
        assert entrada["usuario_id"] == str(madre.id)
        assert entrada["celular"] == "3000000000"
        assert entrada["creado_en"].startswith("2026-03-01T12:00:00")
        assert entrada["hijos"] == [
            {
                "apodo": "Estudiante Ficticio Uno",
                "colegio_id": str(colegio.id),
                "colegio_nombre": "Colegio Ficticio Uno",
                "grado": "Primero",
            },
            {
                "apodo": "Estudiante Ficticio Dos",
                "colegio_id": str(colegio.id),
                "colegio_nombre": "Colegio Ficticio Uno",
                "grado": "Quinto",
            },
        ]
        assert "Acudiente Ficticio" not in repr(entrada)

    async def test_los_hijos_excluyen_matriculas_cerradas_vinculos_terminados_y_los_de_otra_familia(self, db):
        _, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        madre = await _usuario(db, "madre@example.test")
        otra = await _usuario(db, "otra@example.test")
        await _hijo(db, madre, sede, grado="Primero", apodo="Vigente")
        await _hijo(db, madre, sede, grado="Segundo", apodo="Retirado", estado="graduada")
        await _hijo(
            db, madre, sede, grado="Tercero", apodo="Terminado", vinculo_hasta=_ahora() - timedelta(days=2)
        )
        await _hijo(db, otra, sede, grado="Cuarto", apodo="De otra")

        padron = {p["correo"]: p for p in await RepoIdentidad(db).padron_acudientes(None)}

        assert [h["apodo"] for h in padron["madre@example.test"]["hijos"]] == ["Vigente"]
        assert [h["apodo"] for h in padron["otra@example.test"]["hijos"]] == ["De otra"]

    async def test_una_cuenta_sin_hijos_aparece_con_la_lista_vacia(self, db):
        await _usuario(db, "sinhijos@example.test")

        [entrada] = await RepoIdentidad(db).padron_acudientes(None)

        assert entrada["hijos"] == []

    async def test_el_padron_va_de_la_cuenta_mas_nueva_a_la_mas_vieja(self, db):
        for correo, dia in (("mitad@example.test", 2), ("vieja@example.test", 1), ("nueva@example.test", 3)):
            await _usuario(db, correo, creado_en=datetime(2026, 1, dia, 8, 0, tzinfo=UTC))

        padron = await RepoIdentidad(db).padron_acudientes(None)

        assert [p["correo"] for p in padron] == [
            "nueva@example.test",
            "mitad@example.test",
            "vieja@example.test",
        ]


class TestRegistroDelAcudienteConHijos:
    async def _colegio(self, db):
        colegio, sede = await crear_colegio_con_sede(db, "Colegio Ficticio Uno")
        return colegio, sede, RepoIdentidad(db)

    async def test_un_correo_libre_crea_la_cuenta_con_id_derivado_y_matricula_a_sus_hijos(self, db):
        colegio, _, repo = await self._colegio(db)

        usuario_id, creado = await repo.registrar_acudiente_con_hijos(
            "madre@example.test",
            "clave-ficticia-1",
            "3000000000",
            [HijoMatricula(colegio.id, "Quinto", "Estudiante Ficticio Uno")],
            2026,
            cifrador_desde_entorno(),
        )

        assert creado is True
        assert usuario_id == derivar("usuario", "madre@example.test")
        fila = await repo.usuario_por_correo("madre@example.test")
        assert fila.celular == "3000000000"
        assert verificar_clave("clave-ficticia-1", fila.clave_hash) is True
        assert [m["apodo"] for m in await repo.matriculas_del_titular(usuario_id)] == [
            "Estudiante Ficticio Uno"
        ]

    async def test_un_invitado_recibe_clave_y_celular_conservando_su_id_y_sus_hijos_se_matriculan(self, db):
        colegio, _, repo = await self._colegio(db)
        invitado, _ = await repo.registrar_contacto("madre@example.test")

        usuario_id, creado = await repo.registrar_acudiente_con_hijos(
            "madre@example.test",
            "clave-ficticia-2",
            "3000000000",
            [HijoMatricula(colegio.id, "Tercero", "Estudiante Ficticio Dos")],
            2026,
            cifrador_desde_entorno(),
        )

        assert (usuario_id, creado) == (invitado, True)
        fila = await repo.usuario_por_correo("madre@example.test")
        assert verificar_clave("clave-ficticia-2", fila.clave_hash) is True
        assert fila.celular == "3000000000"
        assert await _contar(db, "usuario") == 1
        assert [m["grado"] for m in await repo.matriculas_del_titular(usuario_id)] == ["Tercero"]

    async def test_una_cuenta_real_no_se_muta_ni_se_le_cuelgan_hijos(self, db):
        """La ruta es publica: si mutara una cuenta ya registrada, un tercero
        podria colgarle matriculas a la familia de otro."""
        colegio, _, repo = await self._colegio(db)
        cifrador = cifrador_desde_entorno()
        titular, _ = await repo.registrar_acudiente_con_hijos(
            "madre@example.test", "clave-ficticia-3", "3000000000", [], 2026, cifrador
        )
        antes = await repo.usuario_por_correo("madre@example.test")

        usuario_id, creado = await repo.registrar_acudiente_con_hijos(
            "madre@example.test",
            "clave-del-intruso",
            "3000000001",
            [HijoMatricula(colegio.id, "Once", "Hijo Impostor Ficticio")],
            2026,
            cifrador,
        )

        despues = await repo.usuario_por_correo("madre@example.test")
        assert (usuario_id, creado) == (titular, False)
        assert (despues.clave_hash, despues.celular) == (antes.clave_hash, antes.celular)
        assert verificar_clave("clave-del-intruso", despues.clave_hash) is False
        assert await _contar(db, "estudiante") == 0
        assert await _contar(db, "matricula") == 0

    async def test_un_grado_invalido_se_rechaza_con_422_y_el_llamador_decide_el_rollback(self, db):
        colegio, _, repo = await self._colegio(db)

        with pytest.raises(ErrorDominio) as error:
            await repo.registrar_acudiente_con_hijos(
                "madre@example.test",
                "clave-ficticia-4",
                None,
                [HijoMatricula(colegio.id, "Grado Inventado", "Estudiante Ficticio Uno")],
                2026,
                cifrador_desde_entorno(),
            )

        assert (error.value.error, error.value.estado) == ("grado_invalido", 422)
        assert await _contar(db, "estudiante") == 0
