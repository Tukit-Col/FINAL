"""Las rutas de Identidad: parsear, verificar token, llamar al repo, traducir.

Tres superficies, todas de la seccion 12.4 del contrato:

- **Colegios y grados** (`GET /v1/colegios`, `/{id}`, `PATCH /{id}`,
  `/v1/directorio/{dane}`, `/v1/grados`): el catalogo institucional que el
  acudiente escoge antes de que exista nada mas.
- **Contacto** (`POST /v1/contactos`, `GET /v1/contactos/{id}`): convierte un
  correo en un identificador y de vuelta, para que el pipeline nunca copie el
  correo.
- **Sesion y cuenta** (`/v1/sesiones*`, `/v1/cuenta*`): autenticacion por token
  con revocacion por `version_permisos`, y la libreta de direcciones del
  acudiente, cifrada en reposo.

Lo que NO hay, y la ausencia es la parte importante: nada que devuelva un
estudiante, un nombre de menor ni una matricula (Anexo M). El router parsea,
resuelve el token y traduce; el SQL vive en `repositorios/identidad.py` y las
reglas puras en `dominio/` (ADR 0019).
"""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, Field
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.http import ErrorDominio

from ..dominio.sesiones import emitir_token, leer_token, verificar_clave
from ..repositorios import RepoIdentidad

router = APIRouter()

# Forma minima de un correo: algo, arroba, algo con punto. No pretende cubrir
# la RFC; pretende que `papa` o `papa@ejemplo` no creen una cuenta.
_FORMA_CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

# Los quince grados del corpus, en orden escolar. Va como constante y no como
# consulta porque no es un dato del sistema sino del sistema educativo
# colombiano: derivarlo de las listas cargadas haria que un colegio sin lista
# publicada desapareciera del desplegable.
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

# Los campos institucionales que el administrador puede completar. `nombre` y
# `nit` NO estan aqui a proposito: son la identidad de la institucion y Catalogo
# la referencia por id derivado. Son datos de la INSTITUCION, no del menor: no
# les toca el cifrado del Anexo M, por eso viajan y se guardan en claro.
_CAMPOS_PERFIL = (
    "logo_url",
    "sitio_web",
    "contacto_nombre",
    "contacto_email",
    "contacto_telefono",
    "direccion",
)
_CAMPOS_FIJOS = ("nombre", "nit")


# --------------------------------------------------------------- puras
# Parseo y forma; no tocan la base.


def _token_del_encabezado(authorization: str | None) -> str | None:
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return authorization.strip()


def _direccion_publica(fila: Any) -> dict[str, Any]:
    """Una direccion descifrada para que la vea su dueno. La linea y el contacto
    se descifran aqui; en la base viajan cifrados."""
    cifrador = cifrador_desde_entorno()
    linea = cifrador.descifrar(fila.linea_cifrada).decode("utf-8", errors="replace")
    contacto = None
    if fila.contacto_cifrado is not None:
        contacto = cifrador.descifrar(fila.contacto_cifrado).decode("utf-8", errors="replace")
    return {
        "direccion_id": str(fila.id),
        "etiqueta": fila.etiqueta,
        "ciudad": fila.ciudad,
        "localidad": fila.localidad,
        "linea": linea,
        "contacto": contacto,
        "predeterminada": bool(fila.predeterminada),
    }


async def _usuario_del_token(authorization: str | None, repo: RepoIdentidad) -> Any:
    """El usuario activo portador del token, o 401. Reusa la verificacion de
    firma/expiracion y la revocacion por `version_permisos`."""
    token = _token_del_encabezado(authorization)
    payload = leer_token(token) if token else None
    if payload is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    fila = await repo.usuario_del_token(uuid.UUID(payload["sub"]))
    if fila is None or not fila.activo:
        raise ErrorDominio("sesion_invalida", "La cuenta ya no esta activa.", estado=401)
    if int(payload.get("vp", -1)) != int(fila.version_permisos):
        raise ErrorDominio("sesion_revocada", "La sesion fue revocada. Vuelve a entrar.", estado=401)
    return fila


async def _detalle_colegio(repo: RepoIdentidad, colegio_id: uuid.UUID) -> dict[str, Any]:
    """El colegio con sus sedes, o 404. Compartido por `ver_colegio` y por el
    refresco que devuelve `editar_colegio`."""
    fila = await repo.ver_colegio(colegio_id)
    if fila is None:
        raise ErrorDominio("colegio_no_existe", "No hay ningun colegio con ese identificador.", estado=404)
    sedes = [{"sede_id": str(s.id), "nombre": s.nombre} for s in await repo.sedes_de(colegio_id)]
    return {
        "colegio_id": str(fila.id),
        "nombre": fila.nombre,
        "logo_url": fila.logo_url,
        "sitio_web": fila.sitio_web,
        "contacto_nombre": fila.contacto_nombre,
        "contacto_email": fila.contacto_email,
        "contacto_telefono": fila.contacto_telefono,
        "direccion": fila.direccion,
        "sedes": sedes,
    }


# --------------------------------------------------------------- modelos de entrada


class Contacto(BaseModel):
    """Como avisarle al acudiente cuando su trabajo termine. El correo se valida
    por forma y no con `EmailStr`, que arrastraria `email-validator`."""

    correo: str = Field(min_length=5, max_length=320)
    celular: str | None = Field(default=None, max_length=32)


class Credenciales(BaseModel):
    """Lo minimo para autenticar. La clave no se valida por forma: o coincide
    con el hash guardado o no, y el mensaje de error no dice cual de las dos
    partes fallo, para no ayudar a enumerar correos."""

    correo: str = Field(min_length=5, max_length=320)
    clave: str = Field(min_length=1, max_length=256)


class DireccionEntrada(BaseModel):
    """Lo que el acudiente escribe en su libreta. `ciudad`/`localidad` quedan en
    claro (de ellas depende la zona de reparto); la linea y el contacto se
    cifran antes de guardarse."""

    etiqueta: str = Field(default="casa", max_length=64)
    ciudad: str = Field(min_length=1, max_length=128)
    localidad: str | None = Field(default=None, max_length=128)
    linea: str = Field(min_length=1, max_length=512)
    contacto: str | None = Field(default=None, max_length=64)
    predeterminada: bool = False


# --------------------------------------------------------------- colegios y grados


@router.get("/v1/colegios", tags=["colegios"], summary="Colegios activos, con su numero de sedes")
async def listar_colegios(
    peticion: Request,
    busqueda: Annotated[str | None, Query(description="Texto en el nombre")] = None,
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        filas = await RepoIdentidad(await db.connection()).listar_colegios(busqueda)
    # El logo va aqui porque el desplegable del padre pinta la tarjeta sin abrir
    # el detalle; los contactos no, que son de la pantalla admin.
    datos = [
        {"colegio_id": str(f.id), "nombre": f.nombre, "sedes": int(f.sedes), "logo_url": f.logo_url}
        for f in filas
    ]
    return {"total": len(datos), "colegios": datos}


@router.get(
    "/v1/directorio/{dane}",
    tags=["colegios"],
    summary="Datos DUEB de un colegio del directorio, para pre-llenar el perfil del nuevo",
)
async def datos_directorio(dane: str) -> dict[str, Any]:
    """El bloque del DUEB para un DANE: direccion, contacto, sitio. Lo consume la
    subida para enriquecer `colegio_datos` de una lista de colegio nuevo, y la
    cola lo muestra pre-llenado. 404 si el DANE no esta en el directorio."""
    from ..dominio.directorio import datos_colegio_nuevo_por_dane

    datos = datos_colegio_nuevo_por_dane(dane)
    if datos is None:
        raise ErrorDominio(
            "dane_no_en_directorio", f"El DANE {dane} no esta en el directorio de Bogota.", estado=404
        )
    return datos


@router.get("/v1/colegios/{colegio_id}", tags=["colegios"], summary="Un colegio con sus sedes")
async def ver_colegio(peticion: Request, colegio_id: uuid.UUID) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        return await _detalle_colegio(RepoIdentidad(await db.connection()), colegio_id)


@router.patch("/v1/colegios/{colegio_id}", tags=["colegios"], summary="Editar el perfil institucional")
async def editar_colegio(peticion: Request, colegio_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """El administrador completa el perfil que el padre reconoce en la tarjeta.

    Solo se aceptan los campos institucionales; un intento de tocar `nombre` o
    `nit` se rechaza con 400 antes de escribir nada. Devuelve la MISMA forma que
    el detalle, para que la pantalla admin refresque sin una segunda llamada.
    """
    for campo in _CAMPOS_FIJOS:
        if campo in cuerpo:
            raise ErrorDominio(
                "campo_no_editable",
                "El nombre y el NIT son la identidad de la institucion y no se editan aqui.",
                estado=400,
                campo=campo,
            )
    valores = {c: cuerpo[c] for c in _CAMPOS_PERFIL if c in cuerpo}

    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        if await repo.existe_colegio(colegio_id) is None:
            raise ErrorDominio(
                "colegio_no_existe", "No hay ningun colegio con ese identificador.", estado=404
            )
        await repo.editar_colegio(colegio_id, valores)
        return await _detalle_colegio(repo, colegio_id)


@router.get("/v1/grados", tags=["colegios"], summary="Los grados, en orden escolar")
async def listar_grados() -> dict[str, Any]:
    return {"total": len(GRADOS), "grados": list(GRADOS)}


# --------------------------------------------------------------- contacto


@router.post(
    "/v1/contactos",
    tags=["contacto"],
    status_code=201,
    summary="Convierte un correo en un identificador. No devuelve el correo.",
)
async def registrar_contacto(peticion: Request, contacto: Contacto) -> dict[str, Any]:
    """Alta idempotente por correo, para que el pipeline solo guarde un id.

    **Sin contrasena y sin sesion, y hay que decirlo.** Esto crea una cuenta sin
    credencial utilizable (`clave_hash` queda en un centinela que ningun
    verificador acepta) porque el flujo de hoy no autentica al acudiente: el
    contrato lo pide solo como destinatario del aviso.
    """
    correo = str(contacto.correo).strip().lower()
    if not _FORMA_CORREO.fullmatch(correo):
        raise ErrorDominio("correo_invalido", "El correo no tiene una forma valida.", estado=422, campo="correo")

    async with peticion.app.state.motor.sesion() as db:
        usuario_id, creado = await RepoIdentidad(await db.connection()).registrar_contacto(correo)
    return {"usuario_id": str(usuario_id), "creado": creado}


@router.get(
    "/v1/contactos/{usuario_id}",
    tags=["contacto"],
    summary="Resuelve un id a su contacto para enviar. Efimero: nadie lo guarda.",
)
async def resolver_contacto(peticion: Request, usuario_id: uuid.UUID) -> dict[str, Any]:
    """Devuelve el contacto de un usuario para que el repartidor de Operacion
    pueda entregar el aviso SIN guardar el dato. Es la contraparte de
    `POST /v1/contactos`.

    `celular` es hoy nulo: el sistema no persiste el celular del acudiente en
    ninguna tabla. Se devuelve el campo igual para que el contrato del
    repartidor no cambie el dia que el celular se capture.
    """
    async with peticion.app.state.motor.sesion() as db:
        fila = await RepoIdentidad(await db.connection()).contacto_de(usuario_id)
    if fila is None or not fila.activo:
        raise ErrorDominio(
            "usuario_no_existe", "No hay ningun usuario activo con ese identificador.", estado=404
        )
    return {"usuario_id": str(usuario_id), "correo": fila.correo, "celular": None}


# --------------------------------------------------------------- sesiones


@router.post("/v1/sesiones", tags=["sesion"], summary="Inicia sesion: correo + clave -> token con roles.")
async def iniciar_sesion(peticion: Request, credenciales: Credenciales) -> dict[str, Any]:
    correo = str(credenciales.correo).strip().lower()
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await repo.usuario_por_correo(correo)
        # Mismo mensaje para "no existe" y "clave mala": distinguirlos deja
        # enumerar que correos tienen cuenta.
        if fila is None or not fila.activo or not verificar_clave(credenciales.clave, fila.clave_hash):
            raise ErrorDominio(
                "credenciales_invalidas", "El correo o la clave no son correctos.", estado=401, campo="correo"
            )
        sesion = await repo.armar_sesion(fila)
    token = emitir_token(fila.id, fila.version_permisos)
    return {"sesion": sesion, "token": token}


@router.get(
    "/v1/sesiones/actual",
    tags=["sesion"],
    summary="Quien es el portador de este token, o 401 si no vale.",
)
async def sesion_actual(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        return await repo.armar_sesion(fila)


@router.post(
    "/v1/sesiones/cierre",
    tags=["sesion"],
    status_code=204,
    summary="Cierra la sesion. El estado de sesion vive en el cliente.",
)
async def cerrar_sesion(authorization: Annotated[str | None, Header()] = None) -> None:
    """Sin estado de servidor que invalidar: el token es autocontenido y la
    cookie la borra quien la puso. Para invalidar TODOS los tokens de un usuario
    ya existe la palanca correcta: incrementar su `version_permisos`."""
    return None


# --------------------------------------------------------------- cuenta


@router.get("/v1/cuenta", tags=["cuenta"], summary="Quien soy: el portador de este token.")
async def ver_cuenta(peticion: Request, authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """La identidad del acudiente para su propio panel. El nombre va descifrado;
    el correo es el de la cuenta. No devuelve menores."""
    async with peticion.app.state.motor.sesion() as db:
        fila = await _usuario_del_token(authorization, RepoIdentidad(await db.connection()))
        nombre = fila.correo
        if fila.nombre_cifrado is not None:
            nombre = cifrador_desde_entorno().descifrar(fila.nombre_cifrado).decode("utf-8", errors="replace")
    return {"usuario_id": str(fila.id), "correo": fila.correo, "nombre": nombre}


@router.get("/v1/cuenta/direcciones", tags=["cuenta"], summary="Mi libreta de direcciones, descifrada.")
async def listar_direcciones(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        direcciones = [_direccion_publica(f) for f in await repo.direcciones_de(fila.id)]
    return {"total": len(direcciones), "direcciones": direcciones}


@router.post(
    "/v1/cuenta/direcciones",
    tags=["cuenta"],
    status_code=201,
    summary="Agrega una direccion a mi libreta. La linea y el contacto se cifran.",
)
async def crear_direccion(
    peticion: Request,
    entrada: DireccionEntrada,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    cifrador = cifrador_desde_entorno()
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        if entrada.predeterminada:
            await repo.limpiar_predeterminada(fila.id)
        creada = await repo.crear_direccion(
            usuario_id=fila.id,
            etiqueta=entrada.etiqueta,
            ciudad=entrada.ciudad,
            localidad=entrada.localidad,
            linea_cifrada=cifrador.cifrar(entrada.linea.encode("utf-8")),
            contacto_cifrado=(cifrador.cifrar(entrada.contacto.encode("utf-8")) if entrada.contacto else None),
            predeterminada=entrada.predeterminada,
        )
    return _direccion_publica(creada)


@router.patch(
    "/v1/cuenta/direcciones/{direccion_id}",
    tags=["cuenta"],
    summary="Edita una direccion mia. Solo la mia (404 si no).",
)
async def editar_direccion(
    peticion: Request,
    direccion_id: uuid.UUID,
    entrada: DireccionEntrada,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    cifrador = cifrador_desde_entorno()
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        if await repo.obtener_direccion(direccion_id, fila.id) is None:
            raise ErrorDominio("direccion_no_existe", "No hay ninguna direccion tuya con ese id.", estado=404)
        if entrada.predeterminada:
            await repo.limpiar_predeterminada(fila.id)
        editada = await repo.editar_direccion(
            direccion_id,
            etiqueta=entrada.etiqueta,
            ciudad=entrada.ciudad,
            localidad=entrada.localidad,
            linea_cifrada=cifrador.cifrar(entrada.linea.encode("utf-8")),
            contacto_cifrado=(cifrador.cifrar(entrada.contacto.encode("utf-8")) if entrada.contacto else None),
            predeterminada=entrada.predeterminada,
        )
    return _direccion_publica(editada)


@router.delete(
    "/v1/cuenta/direcciones/{direccion_id}",
    tags=["cuenta"],
    status_code=204,
    summary="Archiva una direccion mia. Baja logica: un envio en curso la sigue viendo.",
)
async def archivar_direccion(
    peticion: Request,
    direccion_id: uuid.UUID,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Baja logica y no borrado (ADR 0015): un envio en curso todavia necesita
    que la direccion exista mientras se entrega. La copia congelada del envio
    vive en Comercio y no se toca."""
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        if await repo.archivar_direccion(direccion_id, fila.id) == 0:
            raise ErrorDominio("direccion_no_existe", "No hay ninguna direccion tuya con ese id.", estado=404)
    return None
