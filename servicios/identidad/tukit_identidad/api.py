"""La superficie minima de Identidad: quienes son los colegios y quien pregunta.

Son cuatro rutas y no mas, y el recorte es deliberado. Identidad es la
frontera de cumplimiento del sistema: aqui viven los datos de menores, asi
que cada ruta que se abre hay que poder defenderla. Las que existen son las
dos que el frontend no puede resolver de otra forma:

- **Los colegios y sus sedes.** El acudiente elige colegio y grado antes de
  que exista nada mas, y ese catalogo institucional vive aqui porque la
  tenencia es de Identidad (ADR 0013). Catalogo guarda la lista de utiles y
  la referencia por `colegio_id`, pero no sabe como se llama el colegio.
- **El contacto.** El contrato exige que el trabajo del pipeline referencie
  al acudiente por identificador y NUNCA copiando su correo. Para poder
  cumplirlo hace falta un sitio donde el correo se convierta en un
  identificador, y ese sitio es este.

Lo que NO hay aqui, y la ausencia es la parte importante: nada que devuelva
un estudiante, un nombre de menor ni una matricula. Esa superficie necesita
autenticacion y control de acceso por clasificacion de dato, y abrirla sin
eso seria exactamente el defecto que el Anexo M documenta. Mientras el
frontend no la necesite, no existe.

    python -m tukit_identidad.api            # localhost:8011
"""

from __future__ import annotations

import argparse
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import FastAPI, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, insert, or_, select
from tukit_comun.bd import crear_motor
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.http import ErrorDominio, crear_app

from .modelos import Base
from .sesiones import emitir_token, leer_token, verificar_clave

PUERTO_POR_OMISION = 8011

# Forma minima de un correo: algo, arroba, algo con punto. No pretende cubrir
# la RFC, que admite cosas que ningun proveedor acepta; pretende que
# `papa` o `papa@ejemplo` no creen una cuenta.
_FORMA_CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

COLEGIO = Base.metadata.tables["colegio"]
SEDE = Base.metadata.tables["sede"]
USUARIO = Base.metadata.tables["usuario"]
ASIGNACION_ROL = Base.metadata.tables["asignacion_rol"]

# Los quince grados del corpus, en el orden en que un colegio los nombra. Va
# como constante y no como consulta porque no es un dato del sistema sino del
# sistema educativo colombiano: derivarlo de las listas cargadas haria que un
# colegio sin lista publicada desapareciera del desplegable.
GRADOS = (
    "Parvulos",
    "Prejardin",
    "Jardin",
    "Transicion",
    "Primero",
    "Segundo",
    "Tercero",
    "Cuarto",
    "Quinto",
    "Sexto",
    "Septimo",
    "Octavo",
    "Noveno",
    "Decimo",
    "Once",
)


class Contacto(BaseModel):
    """Como avisarle al acudiente cuando su trabajo termine.

    El correo se valida por forma y no con el `EmailStr` de pydantic, que
    arrastraria `email-validator` como dependencia. La diferencia practica es
    nula: un correo bien formado puede no existir igual, y quien decide si el
    aviso llego es el envio y no el parser. Lo que si hace falta es rechazar
    una cadena que claramente no es un correo, para no crear una cuenta por
    una entrada equivocada.
    """

    correo: str = Field(min_length=5, max_length=320)
    celular: str | None = Field(default=None, max_length=32)


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("identidad")


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Identidad",
    descripcion=(
        "Colegios, sedes y grados para que el acudiente escoja, y registro del contacto "
        "que convierte un correo en un identificador. Contrato: seccion 12.4."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)


@app.get("/v1/colegios", tags=["colegios"], summary="Colegios activos, con su numero de sedes")
async def listar_colegios(
    busqueda: Annotated[str | None, Query(description="Texto en el nombre")] = None,
) -> dict[str, Any]:
    consulta = (
        select(
            COLEGIO.c.id,
            COLEGIO.c.nombre,
            func.count(SEDE.c.id).label("sedes"),
        )
        .select_from(
            COLEGIO.outerjoin(SEDE, and_(SEDE.c.colegio_id == COLEGIO.c.id, SEDE.c.activa.is_(True)))
        )
        .where(COLEGIO.c.activo.is_(True))
        .group_by(COLEGIO.c.id, COLEGIO.c.nombre)
        .order_by(COLEGIO.c.nombre)
    )
    if busqueda:
        consulta = consulta.where(func.lower(COLEGIO.c.nombre).like(f"%{busqueda.lower()}%"))

    async with app.state.motor.engine.begin() as conexion:
        datos = [
            {"colegio_id": str(f.id), "nombre": f.nombre, "sedes": int(f.sedes)}
            for f in await conexion.execute(consulta)
        ]
    return {"total": len(datos), "colegios": datos}


@app.get("/v1/colegios/{colegio_id}", tags=["colegios"], summary="Un colegio con sus sedes")
async def ver_colegio(colegio_id: uuid.UUID) -> dict[str, Any]:
    async with app.state.motor.engine.begin() as conexion:
        fila = (await conexion.execute(select(COLEGIO).where(COLEGIO.c.id == colegio_id))).one_or_none()
        if fila is None:
            raise ErrorDominio(
                "colegio_no_existe", "No hay ningun colegio con ese identificador.", estado=404
            )
        sedes = [
            {"sede_id": str(s.id), "nombre": s.nombre}
            for s in await conexion.execute(
                select(SEDE).where(SEDE.c.colegio_id == colegio_id, SEDE.c.activa.is_(True))
            )
        ]
    return {"colegio_id": str(fila.id), "nombre": fila.nombre, "sedes": sedes}


@app.get("/v1/grados", tags=["colegios"], summary="Los grados, en orden escolar")
async def listar_grados() -> dict[str, Any]:
    return {"total": len(GRADOS), "grados": list(GRADOS)}


@app.post(
    "/v1/contactos",
    tags=["contacto"],
    status_code=201,
    summary="Convierte un correo en un identificador. No devuelve el correo.",
)
async def registrar_contacto(contacto: Contacto) -> dict[str, Any]:
    """Alta idempotente por correo, para que el pipeline solo guarde un id.

    Es lo que hace cumplible la nota del manifiesto: `trabajo_pipeline` y
    `operacion.notificacion` referencian al acudiente por identificador y el
    correo real vive en un solo sitio, que es el unico donde el derecho al
    olvido lo puede alcanzar.

    **Sin contrasena y sin sesion, y hay que decirlo.** Esto crea una cuenta
    sin credencial utilizable (`clave_hash` queda en un centinela que ningun
    verificador acepta) porque el flujo de hoy no autentica al acudiente: el
    contrato lo pide solo como destinatario del aviso. Cuando entre el
    registro de verdad, esta ruta pasa a ser el camino del invitado y no la
    forma normal de nacer un usuario.
    """
    correo = str(contacto.correo).strip().lower()
    if not _FORMA_CORREO.fullmatch(correo):
        raise ErrorDominio(
            "correo_invalido",
            "El correo no tiene una forma valida.",
            estado=422,
            campo="correo",
        )

    async with app.state.motor.engine.begin() as conexion:
        existente = await conexion.scalar(select(USUARIO.c.id).where(USUARIO.c.correo == correo))
        if existente is not None:
            return {"usuario_id": str(existente), "creado": False}
        nuevo = uuid.uuid4()
        await conexion.execute(
            insert(USUARIO).values(
                id=nuevo,
                correo=correo,
                # Centinela y no cadena vacia: una cadena vacia se parece
                # demasiado a un hash y algun verificador la podria comparar.
                # Esto no valida contra nada.
                clave_hash="sin-credencial",
            )
        )
    return {"usuario_id": str(nuevo), "creado": True}


# ---------------------------------------------------------------- sesiones
#
# La superficie de autenticacion (seccion 12.4 del contrato). Es lo que el
# frontend necesita para entrar y ser enrutado por rol (ADR 0008), y lo que
# hace cumplible la revocacion por `version_permisos` (ADR 0016): el token la
# lleva y el gateway la compara.


class Credenciales(BaseModel):
    """Lo minimo para autenticar. La clave no se valida por forma: o coincide
    con el hash guardado o no, y el mensaje de error no dice cual de las dos
    partes fallo, para no ayudar a enumerar correos."""

    correo: str = Field(min_length=5, max_length=320)
    clave: str = Field(min_length=1, max_length=256)


async def _armar_sesion(conexion: Any, fila_usuario: Any) -> dict[str, Any]:
    """La Sesion publica: quien es y que roles vigentes tiene.

    Los roles salen de `asignacion_rol` (las asignaciones vigentes, sin
    caducar), no de una columna plana: es la misma fuente que `roles_vigentes`
    usa para `puede()`. El nombre va descifrado con el cifrador del entorno,
    que en desarrollo es `CifradorEnClaro` y lo dice.
    """
    ahora = datetime.now(UTC)
    filas = await conexion.execute(
        select(ASIGNACION_ROL.c.rol_codigo, ASIGNACION_ROL.c.ambito_tipo, ASIGNACION_ROL.c.ambito_id).where(
            ASIGNACION_ROL.c.usuario_id == fila_usuario.id,
            ASIGNACION_ROL.c.vigente_desde <= ahora,
            or_(ASIGNACION_ROL.c.vigente_hasta.is_(None), ASIGNACION_ROL.c.vigente_hasta > ahora),
        )
    )
    roles = [
        {
            "rol": f.rol_codigo,
            "ambito": {
                "tipo": f.ambito_tipo,
                "id": str(f.ambito_id) if f.ambito_id is not None else None,
            },
        }
        for f in filas
    ]

    nombre = fila_usuario.correo
    if fila_usuario.nombre_cifrado is not None:
        descifrado = cifrador_desde_entorno().descifrar(fila_usuario.nombre_cifrado)
        nombre = descifrado.decode("utf-8", errors="replace")

    return {
        "usuario_id": str(fila_usuario.id),
        "correo": fila_usuario.correo,
        "nombre": nombre,
        "roles": roles,
        "version_permisos": int(fila_usuario.version_permisos),
    }


@app.post(
    "/v1/sesiones",
    tags=["sesion"],
    summary="Inicia sesion: correo + clave -> token con roles.",
)
async def iniciar_sesion(credenciales: Credenciales) -> dict[str, Any]:
    correo = str(credenciales.correo).strip().lower()
    async with app.state.motor.engine.begin() as conexion:
        fila = (await conexion.execute(select(USUARIO).where(USUARIO.c.correo == correo))).one_or_none()
        # Mismo mensaje para "no existe" y "clave mala": distinguirlos deja
        # enumerar que correos tienen cuenta.
        if fila is None or not fila.activo or not verificar_clave(credenciales.clave, fila.clave_hash):
            raise ErrorDominio(
                "credenciales_invalidas",
                "El correo o la clave no son correctos.",
                estado=401,
                campo="correo",
            )
        sesion = await _armar_sesion(conexion, fila)

    token = emitir_token(fila.id, fila.version_permisos)
    return {"sesion": sesion, "token": token}


@app.get(
    "/v1/sesiones/actual",
    tags=["sesion"],
    summary="Quien es el portador de este token, o 401 si no vale.",
)
async def sesion_actual(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    token = _token_del_encabezado(authorization)
    payload = leer_token(token) if token else None
    if payload is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)

    usuario_id = uuid.UUID(payload["sub"])
    async with app.state.motor.engine.begin() as conexion:
        fila = (await conexion.execute(select(USUARIO).where(USUARIO.c.id == usuario_id))).one_or_none()
        if fila is None or not fila.activo:
            raise ErrorDominio("sesion_invalida", "La cuenta ya no esta activa.", estado=401)
        # La revocacion vive aqui: si la version del token quedo atras respecto
        # a la vigente, la sesion ya no vale aunque el token no haya expirado
        # (ADR 0016). El gateway hace esta misma comparacion sin consultar; este
        # es el chequeo autoritativo contra la base.
        if int(payload.get("vp", -1)) != int(fila.version_permisos):
            raise ErrorDominio("sesion_revocada", "La sesion fue revocada. Vuelve a entrar.", estado=401)
        return await _armar_sesion(conexion, fila)


@app.post(
    "/v1/sesiones/cierre",
    tags=["sesion"],
    status_code=204,
    summary="Cierra la sesion. El estado de sesion vive en el cliente.",
)
async def cerrar_sesion(authorization: Annotated[str | None, Header()] = None) -> None:
    """Sin estado de servidor que invalidar: el token es autocontenido y la
    cookie la borra quien la puso (el Route Handler del frontend). Para
    invalidar TODOS los tokens de un usuario ya existe la palanca correcta:
    incrementar su `version_permisos`. Esta ruta existe para cerrar el contrato
    y para poder auditar el cierre el dia que haga falta."""
    return None


def _token_del_encabezado(authorization: str | None) -> str | None:
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return authorization.strip()


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de Identidad.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
