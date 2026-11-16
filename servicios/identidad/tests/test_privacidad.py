"""Pruebas de consentimiento, supresion y direccion.

Cada una fija un invariante que el modelo anterior no sabia sostener, y que el
Anexo M documento como defecto. No son pruebas de que SQLAlchemy funcione: son
pruebas de que la politica legal es ejecutable contra este esquema.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from tukit_identidad.modelos import (
    Consentimiento,
    ConsentimientoFinalidad,
    Direccion,
    SolicitudSupresion,
)

from tests._ayudas_identidad import crear_colegio_con_sede, crear_matricula, crear_usuario

SUSCRIPTORES = frozenset({"catalogo", "inteligencia", "comercio", "operacion"})


# --------------------------------------------------------------------------
# Consentimiento de menor: de CUAL hijo
# --------------------------------------------------------------------------


async def test_el_consentimiento_de_menor_exige_decir_de_cual(db):
    """El defecto mas concreto del modelo anterior.

    `consentimientos_menor_registro` registraba que un acudiente autorizo el
    tratamiento del dato de un hijo, pero no tenia ninguna columna que dijera
    de cual. Con dos hijos, una sola fila los cubria de forma indistinguible.
    """
    padre = await crear_usuario(db, "padre@x.com")
    db.add(Consentimiento(usuario_id=padre.id, regimen="registro_menor", version="v2"))

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_el_consentimiento_del_titular_no_lleva_matricula(db):
    """La coherencia va en los dos sentidos: el CHECK es una equivalencia, no
    una implicacion. Si no, un consentimiento de titular podria colgar de la
    matricula de cualquiera."""
    padre = await crear_usuario(db, "padre@x.com")
    _colegio, sede = await crear_colegio_con_sede(db, "Colegio A")
    matricula = await crear_matricula(db, sede)
    db.add(
        Consentimiento(
            usuario_id=padre.id, regimen="registro_titular", version="v2", matricula_id=matricula.id
        )
    )

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_se_revoca_el_consentimiento_de_un_hijo_sin_tocar_el_del_otro(db):
    """La revocacion parcial, que es lo que el modelo anterior hacia imposible."""
    padre = await crear_usuario(db, "padre@x.com")
    _a, sede_a = await crear_colegio_con_sede(db, "Colegio A")
    _b, sede_b = await crear_colegio_con_sede(db, "Colegio B")
    hijo_a = await crear_matricula(db, sede_a, grado="3")
    hijo_b = await crear_matricula(db, sede_b, grado="7")

    for matricula in (hijo_a, hijo_b):
        db.add(
            Consentimiento(
                usuario_id=padre.id, regimen="registro_menor", version="v2", matricula_id=matricula.id
            )
        )
    await db.flush()

    del_a = await db.scalar(select(Consentimiento).where(Consentimiento.matricula_id == hijo_a.id))
    del_a.revocado_en = datetime.now(UTC)
    await db.flush()

    vigentes = (
        await db.scalars(select(Consentimiento.matricula_id).where(Consentimiento.revocado_en.is_(None)))
    ).all()
    assert list(vigentes) == [hijo_b.id]


async def test_la_revocatoria_no_borra_la_evidencia_de_lo_revocado(db):
    """Un `PUT` que sobreescribe la fila no sirve ni al titular ni a la prueba
    de cumplimiento: no queda rastro de que se autorizo ni de cuando."""
    padre = await crear_usuario(db, "padre@x.com")
    aceptado = datetime.now(UTC) - timedelta(days=100)
    consentimiento = Consentimiento(
        usuario_id=padre.id, regimen="registro_titular", version="v2", aceptado_en=aceptado
    )
    db.add(consentimiento)
    await db.flush()

    consentimiento.revocado_en = datetime.now(UTC)
    await db.flush()

    assert not consentimiento.vigente
    assert consentimiento.version == "v2"
    assert consentimiento.aceptado_en == aceptado


# --------------------------------------------------------------------------
# Finalidades: versionadas y con historial
# --------------------------------------------------------------------------


async def test_solo_una_decision_vigente_por_finalidad(db):
    usuario = await crear_usuario(db, "u@x.com")
    for _ in range(2):
        db.add(
            ConsentimientoFinalidad(usuario_id=usuario.id, finalidad="analitica", version="v1", aceptado=True)
        )

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_cambiar_de_opinion_conserva_la_decision_anterior(db):
    """El esquema anterior tenia clave primaria `(usuario_id, finalidad)`, asi
    que aceptar y luego rechazar borraba la constancia de haber aceptado."""
    usuario = await crear_usuario(db, "u@x.com")
    ahora = datetime.now(UTC)

    antigua = ConsentimientoFinalidad(
        usuario_id=usuario.id,
        finalidad="analitica",
        version="v1",
        aceptado=True,
        vigente_desde=ahora - timedelta(days=200),
        vigente_hasta=ahora - timedelta(days=10),
    )
    nueva = ConsentimientoFinalidad(
        usuario_id=usuario.id, finalidad="analitica", version="v2", aceptado=False
    )
    db.add_all([antigua, nueva])
    await db.flush()

    assert not antigua.vigente and nueva.vigente
    assert antigua.aceptado is True and nueva.aceptado is False


async def test_una_finalidad_que_no_existe_se_rechaza(db):
    usuario = await crear_usuario(db, "u@x.com")
    db.add(
        ConsentimientoFinalidad(
            usuario_id=usuario.id, finalidad="venta_a_terceros", version="v1", aceptado=True
        )
    )

    with pytest.raises(IntegrityError):
        await db.flush()


# --------------------------------------------------------------------------
# Supresion: `completada` tiene que significar completada
# --------------------------------------------------------------------------


async def test_no_se_puede_marcar_completada_sin_fecha_de_resolucion(db):
    """El worker anterior marcaba `completada` justo despues de anonimizar la
    fila local, sin esperar confirmacion de nadie. El sistema le respondia al
    titular que su dato fue suprimido cuando, en el mejor caso, lo fue en una
    de las cinco bases."""
    usuario = await crear_usuario(db, "u@x.com")
    db.add(SolicitudSupresion(usuario_id=usuario.id, estado="completada"))

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_la_solicitud_no_se_completa_hasta_que_confirmen_todos(db):
    usuario = await crear_usuario(db, "u@x.com")
    solicitud = SolicitudSupresion(usuario_id=usuario.id, estado="propagando")
    db.add(solicitud)
    await db.flush()

    assert not solicitud.confirmar("catalogo", SUSCRIPTORES)
    assert not solicitud.confirmar("inteligencia", SUSCRIPTORES)
    assert not solicitud.confirmar("comercio", SUSCRIPTORES)
    assert solicitud.confirmar("operacion", SUSCRIPTORES)


async def test_la_confirmacion_repetida_no_adelanta_el_cierre(db):
    """Las colas entregan mas de una vez. Si confirmar dos veces el mismo
    servicio contara como dos, un reintento cerraria una supresion que no
    ocurrio."""
    usuario = await crear_usuario(db, "u@x.com")
    solicitud = SolicitudSupresion(usuario_id=usuario.id, estado="propagando")
    db.add(solicitud)
    await db.flush()

    for _ in range(5):
        assert not solicitud.confirmar("catalogo", SUSCRIPTORES)
    assert solicitud.suscriptores_confirmados == ["catalogo"]


async def test_dos_solicitudes_con_la_misma_clave_de_idempotencia_chocan(db):
    usuario = await crear_usuario(db, "u@x.com")
    for _ in range(2):
        db.add(SolicitudSupresion(usuario_id=usuario.id, idempotency_key="abc"))

    with pytest.raises(IntegrityError):
        await db.flush()


# --------------------------------------------------------------------------
# Direccion de entrega: no existia ninguna en todo el sistema
# --------------------------------------------------------------------------


async def test_solo_una_direccion_predeterminada_por_usuario(db):
    usuario = await crear_usuario(db, "u@x.com")
    for etiqueta in ("casa", "oficina"):
        db.add(
            Direccion(
                usuario_id=usuario.id,
                etiqueta=etiqueta,
                ciudad="Bogota",
                linea_cifrada=b"cifrada",
                predeterminada=True,
            )
        )

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_archivar_la_predeterminada_libera_el_lugar(db):
    """Sin el indice parcial, cambiar de direccion obligaria a borrar la
    anterior, y un envio en curso se quedaria sin a donde ir."""
    usuario = await crear_usuario(db, "u@x.com")
    vieja = Direccion(usuario_id=usuario.id, ciudad="Bogota", linea_cifrada=b"vieja", predeterminada=True)
    db.add(vieja)
    await db.flush()

    vieja.archivada_en = datetime.now(UTC)
    nueva = Direccion(usuario_id=usuario.id, ciudad="Bogota", linea_cifrada=b"nueva", predeterminada=True)
    db.add(nueva)
    await db.flush()

    assert not vieja.activa and nueva.activa


async def test_la_ciudad_queda_en_claro_y_la_calle_no(db):
    """Minimizacion: repartir una ruta necesita la zona, no el apartamento.

    La prueba fija el contrato de tipos, que es lo que impide que alguien
    "simplifique" mas adelante agregando una columna `direccion_texto` en
    claro al lado de la cifrada.
    """
    usuario = await crear_usuario(db, "u@x.com")
    direccion = Direccion(
        usuario_id=usuario.id, ciudad="Bogota", localidad="Suba", linea_cifrada=b"\x01\x02cifrado"
    )
    db.add(direccion)
    await db.flush()

    assert isinstance(direccion.ciudad, str)
    assert isinstance(direccion.linea_cifrada, bytes)
    columnas = {c.name for c in Direccion.__table__.columns}
    assert not {"linea", "direccion_texto", "calle"} & columnas
