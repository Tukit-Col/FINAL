"""Pruebas del modelo de roles con ambito.

Cada una reproduce un caso REAL: o un defecto que la auditoria de autorizacion
encontro en el sistema anterior, o una regla de negocio que el modelo plano no
sabia expresar.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from tukit_identidad.dominio.autorizacion import Ambito
from tukit_identidad.modelos import (
    AcudienteMatricula,
    AmbitoTipo,
    Clasificacion,
    Permiso,
)
from tukit_identidad.repositorios.identidad import RepoIdentidad

from tests._ayudas_identidad import (
    asignar,
    crear_colegio_con_sede,
    crear_matricula,
    crear_rol_con_permisos,
    crear_usuario,
    vincular_acudiente,
)


async def puede(db, usuario_id, permiso, ambito):
    return await RepoIdentidad(db).puede(usuario_id, permiso, ambito)


async def roles_vigentes(db, usuario_id, ambito):
    return await RepoIdentidad(db).roles_vigentes(usuario_id, ambito)


async def campos_visibles(db, usuario_id, recurso, ambito, clasificacion_por_campo):
    return await RepoIdentidad(db).campos_visibles(usuario_id, recurso, ambito, clasificacion_por_campo)


async def matriculas_visibles(db, usuario_id):
    return await RepoIdentidad(db).matriculas_visibles(usuario_id)


async def _rol_rector(db):
    return await crear_rol_con_permisos(
        db,
        "rector",
        [
            Permiso(
                codigo="lista_oficial:publicar",
                recurso="lista_oficial",
                accion="publicar",
                clasificacion_minima=Clasificacion.INTERNO.value,
            )
        ],
    )


# --------------------------------------------------------------------------
# El defecto original: el rol plano no distinguia colegios
# --------------------------------------------------------------------------


async def test_el_rector_de_un_colegio_no_manda_en_el_otro(db):
    """`require_rol("rector")` dejaba pasar igual al rector del colegio A y al
    del B. La unica defensa era que cada endpoint se acordara de comparar, y la
    auditoria encontro 22 endpoints donde no se acordaba."""
    await _rol_rector(db)
    rector = await crear_usuario(db, "rector@a.edu.co")
    colegio_a, _ = await crear_colegio_con_sede(db, "Colegio A")
    colegio_b, _ = await crear_colegio_con_sede(db, "Colegio B")
    await asignar(db, rector, "rector", AmbitoTipo.COLEGIO, colegio_a.id)

    assert await puede(db, rector.id, "lista_oficial:publicar", Ambito.colegio(colegio_a.id))
    assert not await puede(db, rector.id, "lista_oficial:publicar", Ambito.colegio(colegio_b.id))


async def test_sin_asignacion_no_puede_nada(db):
    """Falla CERRADA. Las politicas de fila anteriores hacian lo contrario:
    su condicion base era `current_setting(...) IS NULL`, asi que una conexion
    sin contexto veia la tabla completa."""
    await _rol_rector(db)
    nadie = await crear_usuario(db, "nadie@x.com")
    colegio, _ = await crear_colegio_con_sede(db, "Colegio A")

    assert not await puede(db, nadie.id, "lista_oficial:publicar", Ambito.colegio(colegio.id))
    assert await roles_vigentes(db, nadie.id, Ambito.colegio(colegio.id)) == set()


async def test_un_permiso_que_el_rol_no_tiene_se_niega(db):
    await _rol_rector(db)
    rector = await crear_usuario(db, "rector@a.edu.co")
    colegio, _ = await crear_colegio_con_sede(db, "Colegio A")
    await asignar(db, rector, "rector", AmbitoTipo.COLEGIO, colegio.id)

    assert not await puede(db, rector.id, "pedido:reembolsar", Ambito.colegio(colegio.id))


# --------------------------------------------------------------------------
# Jerarquia de ambitos
# --------------------------------------------------------------------------


async def test_el_ambito_de_colegio_alcanza_sus_sedes_y_matriculas(db):
    """Sin esto habria que duplicar la asignacion en cada nivel, y el dia que
    el colegio abra una sede nueva su rector se queda sin acceso a ella."""
    await _rol_rector(db)
    rector = await crear_usuario(db, "rector@a.edu.co")
    colegio, sede = await crear_colegio_con_sede(db, "Colegio A")
    matricula = await crear_matricula(db, sede)
    await asignar(db, rector, "rector", AmbitoTipo.COLEGIO, colegio.id)

    assert await puede(db, rector.id, "lista_oficial:publicar", Ambito.sede(sede.id))
    assert await puede(db, rector.id, "lista_oficial:publicar", Ambito.matricula(matricula.id))


async def test_el_ambito_de_matricula_no_sube_a_la_sede(db):
    """La contencion es en un solo sentido. Ser acudiente de una matricula no
    da autoridad sobre la sede, que es lo que permitiria a un padre ver las
    listas de los demas."""
    await _rol_rector(db)
    padre = await crear_usuario(db, "padre@x.com")
    _colegio, sede = await crear_colegio_con_sede(db, "Colegio A")
    matricula = await crear_matricula(db, sede)
    await asignar(db, padre, "rector", AmbitoTipo.MATRICULA, matricula.id)

    assert await puede(db, padre.id, "lista_oficial:publicar", Ambito.matricula(matricula.id))
    assert not await puede(db, padre.id, "lista_oficial:publicar", Ambito.sede(sede.id))


async def test_el_ambito_global_alcanza_todo(db):
    await _rol_rector(db)
    admin = await crear_usuario(db, "admin@tukit.co")
    colegio, sede = await crear_colegio_con_sede(db, "Colegio A")
    matricula = await crear_matricula(db, sede)
    await asignar(db, admin, "rector", AmbitoTipo.GLOBAL, None)

    for ambito in (
        Ambito.global_(),
        Ambito.colegio(colegio.id),
        Ambito.sede(sede.id),
        Ambito.matricula(matricula.id),
    ):
        assert await puede(db, admin.id, "lista_oficial:publicar", ambito)


# --------------------------------------------------------------------------
# Vigencia y revocacion
# --------------------------------------------------------------------------


async def test_una_asignacion_revocada_deja_de_conceder(db):
    await _rol_rector(db)
    ex = await crear_usuario(db, "exrector@a.edu.co")
    colegio, _ = await crear_colegio_con_sede(db, "Colegio A")
    ayer = datetime.now(UTC) - timedelta(days=1)
    await asignar(
        db,
        ex,
        "rector",
        AmbitoTipo.COLEGIO,
        colegio.id,
        vigente_desde=ayer - timedelta(days=30),
        vigente_hasta=ayer,
    )

    assert not await puede(db, ex.id, "lista_oficial:publicar", Ambito.colegio(colegio.id))


async def test_una_asignacion_futura_todavia_no_concede(db):
    await _rol_rector(db)
    entrante = await crear_usuario(db, "nuevo@a.edu.co")
    colegio, _ = await crear_colegio_con_sede(db, "Colegio A")
    await asignar(
        db,
        entrante,
        "rector",
        AmbitoTipo.COLEGIO,
        colegio.id,
        vigente_desde=datetime.now(UTC) + timedelta(days=7),
    )

    assert not await puede(db, entrante.id, "lista_oficial:publicar", Ambito.colegio(colegio.id))


async def test_se_puede_revocar_y_volver_a_conceder_conservando_el_historial(db):
    """`pertenencias_institucion` tenia `UniqueConstraint(usuario_id, institucion_id)`,
    que obliga a BORRAR la fila para revocar, y con eso se pierde la evidencia
    de quien tuvo acceso a que y cuando. El indice unico parcial lo resuelve."""
    await _rol_rector(db)
    rector = await crear_usuario(db, "rector@a.edu.co")
    colegio, _ = await crear_colegio_con_sede(db, "Colegio A")
    ahora = datetime.now(UTC)

    vieja = await asignar(
        db,
        rector,
        "rector",
        AmbitoTipo.COLEGIO,
        colegio.id,
        vigente_desde=ahora - timedelta(days=365),
        vigente_hasta=ahora - timedelta(days=30),
    )
    nueva = await asignar(db, rector, "rector", AmbitoTipo.COLEGIO, colegio.id)

    assert not vieja.vigente and nueva.vigente
    assert await puede(db, rector.id, "lista_oficial:publicar", Ambito.colegio(colegio.id))


async def test_no_se_permiten_dos_asignaciones_vigentes_identicas(db):
    await _rol_rector(db)
    rector = await crear_usuario(db, "rector@a.edu.co")
    colegio, _ = await crear_colegio_con_sede(db, "Colegio A")
    await asignar(db, rector, "rector", AmbitoTipo.COLEGIO, colegio.id)

    with pytest.raises(IntegrityError):
        await asignar(db, rector, "rector", AmbitoTipo.COLEGIO, colegio.id)


# --------------------------------------------------------------------------
# Matriculas visibles: el caso que invalida `colegio_id` en el usuario
# --------------------------------------------------------------------------


async def test_un_acudiente_con_hijos_en_dos_colegios_ve_los_dos(db):
    """Es la razon por la que la tenencia no puede vivir en la persona. Si el
    usuario tuviera un `colegio_id`, este acudiente perderia a uno de sus dos
    hijos."""
    padre = await crear_usuario(db, "padre@x.com")
    _a, sede_a = await crear_colegio_con_sede(db, "Colegio A")
    _b, sede_b = await crear_colegio_con_sede(db, "Colegio B")
    hijo_a = await crear_matricula(db, sede_a, grado="3")
    hijo_b = await crear_matricula(db, sede_b, grado="7")
    await vincular_acudiente(db, padre, hijo_a)
    await vincular_acudiente(db, padre, hijo_b)

    assert await matriculas_visibles(db, padre.id) == {hijo_a.id, hijo_b.id}


async def test_un_acudiente_no_ve_la_matricula_de_otra_familia(db):
    padre = await crear_usuario(db, "padre@x.com")
    ajeno = await crear_usuario(db, "otro@x.com")
    _colegio, sede = await crear_colegio_con_sede(db, "Colegio A")
    mia = await crear_matricula(db, sede, grado="3")
    suya = await crear_matricula(db, sede, grado="4")
    await vincular_acudiente(db, padre, mia)
    await vincular_acudiente(db, ajeno, suya)

    assert await matriculas_visibles(db, padre.id) == {mia.id}


async def test_un_vinculo_terminado_deja_de_dar_visibilidad(db):
    """Lo que permite distinguir "se fue" de "nunca estuvo", que es lo que
    necesita la regla de supresion: suprimir a un acudiente elimina SU
    vinculo, no el del otro padre."""
    padre = await crear_usuario(db, "padre@x.com")
    _colegio, sede = await crear_colegio_con_sede(db, "Colegio A")
    matricula = await crear_matricula(db, sede)
    await vincular_acudiente(db, padre, matricula)

    ahora = datetime.now(UTC)
    vinculo = await db.get(AcudienteMatricula, (padre.id, matricula.id))
    vinculo.vigente_desde = ahora - timedelta(days=365)
    vinculo.vigente_hasta = ahora - timedelta(days=1)
    await db.flush()

    assert await matriculas_visibles(db, padre.id) == set()


async def test_el_rol_sobre_el_colegio_hace_visibles_sus_matriculas(db):
    rector = await crear_usuario(db, "rector@a.edu.co")
    colegio, sede = await crear_colegio_con_sede(db, "Colegio A")
    uno = await crear_matricula(db, sede, grado="3")
    dos = await crear_matricula(db, sede, grado="4")
    await asignar(db, rector, "rector", AmbitoTipo.COLEGIO, colegio.id)

    assert await matriculas_visibles(db, rector.id) == {uno.id, dos.id}


# --------------------------------------------------------------------------
# Seguridad a nivel de campo: dos ejes, no uno
# --------------------------------------------------------------------------


async def test_un_permiso_interno_no_alcanza_un_campo_de_menor(db):
    """El rediseno afirmaba que los permisos de campo se derivan
    "automaticamente" de la clasificacion. El Anexo M demostro que no: la
    clasificacion mide sensibilidad y el permiso expresa quien ve que.
    """
    await crear_rol_con_permisos(
        db,
        "analista",
        [
            Permiso(
                codigo="estudiante:leer",
                recurso="estudiante",
                accion="leer",
                clasificacion_minima=Clasificacion.INTERNO.value,
            )
        ],
    )
    analista = await crear_usuario(db, "analista@tukit.co")
    colegio, _ = await crear_colegio_con_sede(db, "Colegio A")
    await asignar(db, analista, "analista", AmbitoTipo.COLEGIO, colegio.id)

    clasificacion = {
        "id": Clasificacion.MENOR,
        "nombre_cifrado": Clasificacion.MENOR,
        "grado": Clasificacion.INTERNO,
    }
    visibles = await campos_visibles(db, analista.id, "estudiante", Ambito.colegio(colegio.id), clasificacion)

    assert visibles == {"grado"}


async def test_un_permiso_de_campo_concede_solo_ese_campo(db):
    await crear_rol_con_permisos(
        db,
        "docente",
        [
            Permiso(
                codigo="estudiante:leer",
                recurso="estudiante",
                accion="leer",
                clasificacion_minima=Clasificacion.INTERNO.value,
            ),
            Permiso(
                codigo="estudiante:leer:nombre_cifrado",
                recurso="estudiante",
                accion="leer",
                campo="nombre_cifrado",
                clasificacion_minima=Clasificacion.MENOR.value,
            ),
        ],
    )
    docente = await crear_usuario(db, "docente@a.edu.co")
    colegio, _ = await crear_colegio_con_sede(db, "Colegio A")
    await asignar(db, docente, "docente", AmbitoTipo.COLEGIO, colegio.id)

    clasificacion = {
        "id": Clasificacion.MENOR,
        "nombre_cifrado": Clasificacion.MENOR,
        "grado": Clasificacion.INTERNO,
    }
    visibles = await campos_visibles(db, docente.id, "estudiante", Ambito.colegio(colegio.id), clasificacion)

    # Ve el nombre porque tiene el permiso de ese campo, y NO ve `id` aunque
    # tenga la misma clasificacion: el permiso es por campo, no por nivel.
    assert visibles == {"nombre_cifrado", "grado"}


async def test_sin_rol_en_el_ambito_no_se_ve_ningun_campo(db):
    await crear_rol_con_permisos(
        db,
        "docente",
        [
            Permiso(
                codigo="estudiante:leer",
                recurso="estudiante",
                accion="leer",
                clasificacion_minima=Clasificacion.MENOR.value,
            )
        ],
    )
    docente = await crear_usuario(db, "docente@a.edu.co")
    colegio_a, _ = await crear_colegio_con_sede(db, "Colegio A")
    colegio_b, _ = await crear_colegio_con_sede(db, "Colegio B")
    await asignar(db, docente, "docente", AmbitoTipo.COLEGIO, colegio_a.id)

    visibles = await campos_visibles(
        db, docente.id, "estudiante", Ambito.colegio(colegio_b.id), {"grado": Clasificacion.INTERNO}
    )

    assert visibles == set()
