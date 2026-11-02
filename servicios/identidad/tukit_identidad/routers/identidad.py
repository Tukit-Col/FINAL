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
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import BaseModel, Field
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.http import ErrorDominio

from ..dominio.autorizacion import Ambito
from ..dominio.matriculas import HijoMatricula
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
# El `dane` SI es editable: aqui el `colegio_id` es un UUID ya fijado al crear el
# colegio (no se re-deriva del DANE en esta base), asi que escribir el codigo DANE
# cuando falta —para poder leer su ficha del directorio— no mueve ninguna
# referencia. Distinto del NIT, que sigue fijo.
_CAMPOS_PERFIL = (
    "dane",
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
        "dane": fila.dane,
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
        {
            "colegio_id": str(f.id),
            "nombre": f.nombre,
            "dane": f.dane,
            "sedes": int(f.sedes),
            "logo_url": f.logo_url,
        }
        for f in filas
    ]
    return {"total": len(datos), "colegios": datos}


@router.get(
    "/v1/directorio/{dane}",
    tags=["colegios"],
    summary="Datos DUEB de un colegio del directorio, para pre-llenar el perfil del nuevo",
)
async def datos_directorio(
    dane: str,
    completo: Annotated[bool, Query(description="La ficha completa del admin, no solo el alta")] = False,
) -> dict[str, Any]:
    """El bloque del DUEB para un DANE. Dos formas en la MISMA ruta: por defecto
    solo los 7 campos del alta (lo que la subida vuelca sin filtrar en
    `colegio_datos`, asi que un campo de mas se filtraria a cada colegio nuevo);
    con `?completo=true`, el superconjunto del admin (sector, localidad, rector,
    telefonos, correos). 404 si el DANE no esta en el directorio."""
    from ..dominio.directorio import datos_colegio_nuevo_por_dane, ficha_directorio_por_dane

    datos = ficha_directorio_por_dane(dane) if completo else datos_colegio_nuevo_por_dane(dane)
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
    # El DANE es la llave del directorio DUEB: o son 12 digitos exactos, o `null`
    # para vaciarlo. Cualquier otra cosa se rechaza antes de escribir, para no
    # guardar una llave que nunca casara con el directorio.
    if "dane" in cuerpo:
        dane = cuerpo["dane"]
        if dane is not None and not (isinstance(dane, str) and dane.isdigit() and len(dane) == 12):
            raise ErrorDominio(
                "dane_invalido",
                "El codigo DANE debe tener exactamente 12 digitos, o null para vaciarlo.",
                estado=400,
                campo="dane",
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
        raise ErrorDominio(
            "correo_invalido", "El correo no tiene una forma valida.", estado=422, campo="correo"
        )

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


@router.get(
    "/v1/contactos/{usuario_id}/credencial",
    tags=["contacto"],
    summary="Si el usuario puede iniciar sesion. Interno: no devuelve datos personales.",
)
async def credencial_del_contacto(peticion: Request, usuario_id: uuid.UUID) -> dict[str, bool]:
    """Lo consulta Inteligencia para decidir si un kit exige la sesion de su dueno.

    El acudiente de la ruta rapida es un contacto sin clave: no puede iniciar
    sesion, asi que su unico acceso al kit es el enlace del correo. Quien si
    tiene clave debe abrir su kit con su sesion. La respuesta es un booleano y
    nada mas, para que preguntarlo no filtre el correo ni el nombre. Cuelga de
    `/v1/contactos/`, que la puerta del gateway ya bloquea: solo se llega de
    servicio a servicio."""
    async with peticion.app.state.motor.sesion() as db:
        tiene = await RepoIdentidad(await db.connection()).tiene_credencial(usuario_id)
    return {"tiene_credencial": tiene}


@router.get(
    "/v1/usuarios/nombres",
    tags=["contacto"],
    summary="Nombres de acudientes adultos por id, para el panel del back-office.",
)
async def nombres_de_usuarios(
    peticion: Request,
    ids: Annotated[list[uuid.UUID], Query(description="usuario_id a resolver")],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """El nombre en claro de uno o varios acudientes ADULTOS, para que el panel
    de acudientes del colegio muestre quien pidio en vez de un id. Es PII
    (§Anexo M: el nombre del adulto es PERSONAL), asi que exige el permiso
    `usuario:leer:nombre` sobre el ambito global —solo admin y operador lo
    tienen— y devuelve 403 a quien no. Nunca resuelve un nombre de menor: solo
    lee la tabla `usuario`."""
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        quien = await _usuario_del_token(authorization, repo)
        if not await repo.puede(quien.id, "usuario:leer:nombre", Ambito.global_()):
            raise ErrorDominio("sin_permiso", "No puedes leer nombres de acudientes.", estado=403)
        return {"nombres": await repo.nombres_de(ids)}


# --------------------------------------------------------------- cuenta del acudiente


class NuevaCuenta(BaseModel):
    correo: str = Field(min_length=5, max_length=320)
    clave: str = Field(min_length=1, max_length=256)
    nombre: str = Field(min_length=1, max_length=256)
    celular: str | None = Field(default=None, max_length=32)
    acepta_terminos: bool = False


class NuevoHijo(BaseModel):
    apodo: str = Field(min_length=1, max_length=64)
    colegio_id: str | None = None
    sede_id: str | None = None
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int = Field(ge=2020, le=2100)
    consentimiento: bool = False


_VERSION_CONSENTIMIENTO_MENOR = "2026-09"
# Version de la politica de datos y los terminos que el titular acepta al
# registrarse (los textos de `/legal` en la web). Sube cuando el texto cambie.
_VERSION_TERMINOS_TITULAR = "2026-11"


class HijoRegistro(BaseModel):
    """Un hijo tal como el formulario lo manda: colegio y grado bastan para armar
    el kit. El `apodo` es opcional y es lo unico que identifica al menor; se
    guarda cifrado. NO se pide el nombre legal: no hace falta para la finalidad
    (armar la lista) y recolectarlo violaria el principio de necesidad."""

    colegio_id: uuid.UUID
    grado: str = Field(min_length=1, max_length=32)
    apodo: str | None = Field(default=None, max_length=120)

    def a_dominio(self) -> HijoMatricula:
        return HijoMatricula(colegio_id=self.colegio_id, grado=self.grado, apodo=self.apodo)


class Registro(BaseModel):
    """El alta del acudiente nuevo: su credencial, su celular para el aviso y sus
    hijos. La clave pide un minimo de 8 para no crear cuentas triviales; no se
    valida mas forma porque la politica real vive en un solo sitio."""

    correo: str = Field(min_length=5, max_length=320)
    clave: str = Field(min_length=8, max_length=256)
    celular: str | None = Field(default=None, max_length=32)
    hijos: list[HijoRegistro] = Field(default_factory=list)
    # El titular marco la casilla de la politica de datos y los terminos. Se
    # registra como consentimiento `registro_titular` solo al crear la cuenta.
    acepta_terminos: bool = False


class MatriculasNuevas(BaseModel):
    """Hijos que un acudiente YA autenticado agrega a su cuenta desde `/empezar`.
    Reusa `HijoRegistro`: misma forma y mismas reglas de validacion."""

    hijos: list[HijoRegistro] = Field(default_factory=list)


@router.post(
    "/v1/registro",
    tags=["registro"],
    status_code=201,
    summary="Alta del acudiente: credencial + matriculas de sus hijos. No devuelve menores.",
)
async def registrar_acudiente(peticion: Request, registro: Registro) -> dict[str, Any]:
    """Alta idempotente y orden-independiente con `POST /v1/contactos`. La unica
    ruta publica que escribe en la tabla de menores: solo el apodo (opcional,
    cifrado) toca al menor y nunca su nombre legal (Ley 1581 Art. 4); todo se
    deriva para ser idempotente; y si el correo ya tiene credencial REAL no
    escribe nada, para que un tercero sin sesion no inyecte matriculas en la
    cuenta de otra familia."""
    # El consentimiento se exige aqui y no solo en la casilla del formulario: un
    # cliente que llame directo a la API se saltaria la casilla y la cuenta
    # nacera sin el registro de consentimiento que pide la Ley 1581. Se rechaza
    # antes de tocar nada. Los demas altas (contacto del pago, cuenta, staff) son
    # otras rutas y no pasan por aqui.
    if not registro.acepta_terminos:
        raise ErrorDominio(
            "consentimiento_requerido",
            "Para crear la cuenta debes aceptar la politica de datos y los terminos.",
            estado=422,
            campo="acepta_terminos",
        )
    correo = str(registro.correo).strip().lower()
    if not _FORMA_CORREO.fullmatch(correo):
        raise ErrorDominio(
            "correo_invalido", "El correo no tiene una forma valida.", estado=422, campo="correo"
        )
    # Pre-check de grado ANTES de la transaccion y para TODOS los caminos (incluido
    # el correo ya-registrado que retorna temprano): redundante con la validacion
    # del repo, pero deliberado, para que un grado invalido sea 422 aunque no se
    # llegue a materializar.
    for hijo in registro.hijos:
        if hijo.grado not in GRADOS:
            raise ErrorDominio(
                "grado_invalido", f"'{hijo.grado}' no es un grado escolar.", estado=422, campo="grado"
            )

    cifrador = cifrador_desde_entorno()
    anio_lectivo = datetime.now(UTC).year
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        usuario_id, creado = await repo.registrar_acudiente_con_hijos(
            correo,
            registro.clave,
            registro.celular,
            [h.a_dominio() for h in registro.hijos],
            anio_lectivo,
            cifrador,
        )
        if creado:
            await repo.registrar_consentimiento_titular(usuario_id, _VERSION_TERMINOS_TITULAR)
    return {"usuario_id": str(usuario_id), "creado": creado}


@router.post("/v1/cuenta", tags=["cuenta"], status_code=201, summary="Crea la cuenta del acudiente.")
async def crear_cuenta(peticion: Request, datos: NuevaCuenta) -> dict[str, Any]:
    from ..dominio.cuenta import ClaveDebil, Decision, validar_clave

    # Mismo consentimiento que pide /v1/registro: esta ruta tambien crea cuentas
    # con clave, y sin esta exigencia seria el camino para saltarse la Ley 1581.
    if not datos.acepta_terminos:
        raise ErrorDominio(
            "consentimiento_requerido",
            "Para crear la cuenta debes aceptar la politica de datos y los terminos.",
            estado=422,
            campo="acepta_terminos",
        )
    try:
        validar_clave(datos.clave)
    except ClaveDebil:
        raise ErrorDominio(
            "clave_debil", "La clave necesita al menos 8 caracteres.", estado=422, campo="clave"
        ) from None

    correo = datos.correo.strip().lower()
    if not _FORMA_CORREO.fullmatch(correo):
        raise ErrorDominio(
            "correo_invalido", "El correo no tiene una forma valida.", estado=422, campo="correo"
        )

    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila, decision = await repo.crear_o_promover_cuenta(
            correo=correo, clave=datos.clave, nombre=datos.nombre, celular=datos.celular
        )
        if decision is Decision.CONFLICTO:
            raise ErrorDominio(
                "correo_ya_registrado",
                "Ese correo ya tiene una cuenta. Inicia sesion.",
                estado=409,
                campo="correo",
            )
        await repo.registrar_consentimiento_titular(fila.id, _VERSION_TERMINOS_TITULAR)
        sesion = await repo.armar_sesion(fila)
    token = emitir_token(fila.id, fila.version_permisos)
    return {"sesion": sesion, "token": token}


@router.post(
    "/v1/cuenta/hijos", tags=["cuenta"], status_code=201, summary="Registra un hijo del acudiente (apodo)."
)
async def registrar_hijo(
    peticion: Request, datos: NuevoHijo, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    if not datos.consentimiento:
        raise ErrorDominio(
            "consentimiento_requerido",
            "Hay que autorizar el tratamiento del dato del menor (Ley 1581).",
            estado=422,
            campo="consentimiento",
        )
    if not datos.colegio_id or not datos.sede_id:
        raise ErrorDominio(
            "hijo_sin_colegio", "El hijo necesita un colegio y una sede.", estado=422, campo="colegio_id"
        )

    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        matricula_id = await repo.registrar_hijo(
            usuario_id=fila.id,
            apodo=datos.apodo,
            colegio_id=uuid.UUID(datos.colegio_id),
            sede_id=uuid.UUID(datos.sede_id),
            grado=datos.grado,
            anio_lectivo=datos.anio_lectivo,
            version_consentimiento=_VERSION_CONSENTIMIENTO_MENOR,
        )
        await repo.otorgar_rol_acudiente(fila.id, uuid.UUID(datos.colegio_id))
    return {"matricula_id": str(matricula_id)}


@router.get("/v1/cuenta/hijos", tags=["cuenta"], summary="Mis hijos, por apodo. Nunca nombres reales.")
async def listar_hijos(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        hijos = await repo.hijos_del_padre(fila.id)
    return {"total": len(hijos), "hijos": hijos}


@router.get(
    "/v1/cuenta/matriculas",
    tags=["cuenta"],
    summary="El ambito de tenencia de MIS hijos: colegio, grado y anio. Sin datos de menor.",
)
async def listar_matriculas(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """Lo justo para precargar `/empezar` sin re-teclear a los hijos: colegio,
    grado, anio y el apodo (el PADRE puede ver el de SUS hijos). Se filtra por el
    usuario del token, no por rol."""
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        matriculas = await repo.matriculas_del_titular(fila.id)
    return {"total": len(matriculas), "matriculas": matriculas}


@router.post(
    "/v1/cuenta/matriculas",
    tags=["cuenta"],
    status_code=201,
    summary="Agrega matriculas de MIS hijos con sesion. Solo escribe; no devuelve menores.",
)
async def guardar_matriculas(
    peticion: Request,
    cuerpo: MatriculasNuevas,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Equivalente autenticado del alta de hijos de `POST /v1/registro`: el
    portador agrega a sus propios hijos sin re-registrar la cuenta. "Agregar"
    SIEMPRE crea un hijo nuevo con el ordinal siguiente (se le pasa al repo el
    conteo previo del portador en cada par), asi que NO es idempotente ante
    reenvios; la proteccion la da la firma del formulario, no esta ruta."""
    cifrador = cifrador_desde_entorno()
    anio_lectivo = datetime.now(UTC).year
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        conteo_inicial = await repo.conteo_matriculas_por_par(fila.id, anio_lectivo)
        total = await repo.materializar_hijos(
            fila.id, [h.a_dominio() for h in cuerpo.hijos], anio_lectivo, cifrador, conteo_inicial
        )
    return {"total": total}


class CambioDeHijo(BaseModel):
    """El colegio y el grado nuevos de un hijo; el apodo, si se quiere cambiar."""

    colegio_id: uuid.UUID
    grado: str = Field(min_length=1, max_length=32)
    apodo: str | None = Field(default=None, max_length=120)


@router.delete(
    "/v1/cuenta/matriculas/{matricula_id}",
    tags=["cuenta"],
    status_code=204,
    summary="Quita a un hijo de MI cuenta (cierra el vinculo; no borra datos)",
)
async def quitar_matricula(
    peticion: Request,
    matricula_id: uuid.UUID,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        await repo.matricula_del_portador(fila.id, matricula_id)
        await repo.retirar_matricula(fila.id, matricula_id)
    return Response(status_code=204)


@router.put(
    "/v1/cuenta/matriculas/{matricula_id}",
    tags=["cuenta"],
    summary="Cambia el colegio o el grado de un hijo de MI cuenta, con su apodo",
)
async def cambiar_matricula(
    peticion: Request,
    matricula_id: uuid.UUID,
    cuerpo: CambioDeHijo,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Retira la matricula vieja y crea la del colegio y grado nuevos.

    Todo en una transaccion: si el colegio no tiene sede o el grado no existe
    (422), no se retira nada. El apodo se conserva salvo que venga uno nuevo.
    Una matricula es (estudiante, sede, grado, anio), asi que cambiar de colegio
    es otra matricula, no una edicion de la misma.
    """
    cifrador = cifrador_desde_entorno()
    anio_lectivo = datetime.now(UTC).year
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        actual = await repo.matricula_del_portador(fila.id, matricula_id)
        apodo = cuerpo.apodo
        if apodo is None:
            apodo = cifrador.descifrar(actual.nombre_cifrado).decode("utf-8", errors="replace") or None
        await repo.retirar_matricula(fila.id, matricula_id)
        conteo_inicial = await repo.conteo_matriculas_por_par(fila.id, anio_lectivo)
        total = await repo.materializar_hijos(
            fila.id,
            [HijoMatricula(colegio_id=cuerpo.colegio_id, grado=cuerpo.grado, apodo=apodo)],
            anio_lectivo,
            cifrador,
            conteo_inicial,
        )
    return {"total": total}


# --------------------------------------------------------------- admin
#
# La primera puerta que expone dato de menor (el apodo) por la superficie
# publica, y por eso la mas vigilada: se abre SOLO al equipo interno
# (admin/operador) y devuelve unicamente a las familias registradas.


@router.get(
    "/v1/admin/acudientes",
    tags=["admin"],
    summary="Padron de acudientes registrados y sus hijos. Solo equipo interno.",
)
async def listar_acudientes(
    peticion: Request,
    authorization: Annotated[str | None, Header()] = None,
    ids: Annotated[str | None, Query(description="UUIDs separados por coma para acotar")] = None,
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        # 1) Puerta: token valido (401 si no) ...
        solicitante = await _usuario_del_token(authorization, repo)
        # 2) ... y rol de staff VIGENTE (403 si no).
        if not await repo.es_staff_vigente(solicitante.id):
            raise ErrorDominio(
                "acceso_denegado", "Esta vista es solo para el equipo interno de Tukit.", estado=403
            )
        # ids -> lista de UUID, ya PASADA la puerta: un id mal formado responde 400,
        # pero solo a quien ya autentico. Antes del gate, un `?ids=nope` sin token
        # sigue siendo 401 (no revelar la forma del endpoint).
        ids_filtrados: list[uuid.UUID] | None = None
        if ids is not None:
            crudos = [p.strip() for p in ids.split(",") if p.strip()]
            try:
                ids_filtrados = [uuid.UUID(p) for p in crudos]
            except ValueError:
                raise ErrorDominio(
                    "ids_invalido", "El parametro ids trae un UUID mal formado.", estado=400, campo="ids"
                ) from None
        acudientes = await repo.padron_acudientes(ids_filtrados)
    return {"total": len(acudientes), "acudientes": acudientes}


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
    summary="Cierra la sesion y revoca el token.",
)
async def cerrar_sesion(peticion: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    """Revoca el token subiendo la `version_permisos` del portador.

    El token es autocontenido: borrar la cookie no bastaba, porque quien lo
    hubiera copiado seguia entrando hasta que expirara. La revocacion es por
    cuenta y no por token, asi que cierra la sesion en todos sus dispositivos:
    es lo mas seguro y no pide guardar una lista de tokens revocados. Cerrar es
    idempotente: sin token, o con uno que ya no vale, responde igual."""
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        try:
            fila = await _usuario_del_token(authorization, repo)
        except ErrorDominio:
            return None
        await repo.revocar_sesiones(fila.id)
    return None


# --------------------------------------------------------------- cuenta


@router.get("/v1/cuenta", tags=["cuenta"], summary="Quien soy: el portador de este token.")
async def ver_cuenta(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
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
            contacto_cifrado=(
                cifrador.cifrar(entrada.contacto.encode("utf-8")) if entrada.contacto else None
            ),
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
            contacto_cifrado=(
                cifrador.cifrar(entrada.contacto.encode("utf-8")) if entrada.contacto else None
            ),
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


# --------------------------------------------------------------- privacidad
# Los derechos del titular (Ley 1581 de 2012, art. 8; Decreto 1377 de 2013):
# conocer (inventario), obtener copia (exportacion), suprimir y revocar. Todo
# sale del portador del token: no hay ruta con el id de otro titular, asi que
# no hay forma de pedir los datos de nadie mas.


class PeticionSupresion(BaseModel):
    confirmacion: str = Field(default="", max_length=64)


def _inventario_remoto(peticion: Request) -> Any:
    from ..remoto import InventarioRemoto

    inventario = getattr(peticion.app.state, "inventario", None)
    if inventario is None:
        inventario = InventarioRemoto()
        peticion.app.state.inventario = inventario
    return inventario


def _iso_o_none(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor is not None else None


async def _mis_datos(peticion: Request, authorization: str | None, *, completo: bool) -> dict[str, Any]:
    """El inventario del titular. `completo` es la copia exportable: el contacto
    y las direcciones van enteros. Sin `completo`, enmascarados."""
    from ..dominio.privacidad import (
        CONSERVADO,
        FRASE_CONFIRMACION,
        SUPRIMIDO,
        enmascarar_correo,
        enmascarar_telefono,
    )

    cifrador = cifrador_desde_entorno()
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        nombre = None
        if fila.nombre_cifrado is not None:
            nombre = cifrador.descifrar(fila.nombre_cifrado).decode("utf-8", errors="replace")
        direcciones = [_direccion_publica(d) for d in await repo.direcciones_de(fila.id)]
        matriculas = await repo.matriculas_del_titular(fila.id)
        consentimientos = await repo.consentimientos_de(fila.id)

    if not completo:
        direcciones = [
            {
                "direccion_id": d["direccion_id"],
                "etiqueta": d["etiqueta"],
                "ciudad": d["ciudad"],
                "localidad": d["localidad"],
                "tiene_contacto": d["contacto"] is not None,
            }
            for d in direcciones
        ]
    remotos = await _inventario_remoto(peticion).resumen(_token_del_encabezado(authorization) or "")
    return {
        "cuenta": {
            "usuario_id": str(fila.id),
            "nombre": nombre,
            "correo": fila.correo if completo else enmascarar_correo(fila.correo),
            "celular": fila.celular if completo else enmascarar_telefono(fila.celular),
            "creado_en": _iso_o_none(fila.creado_en),
        },
        "hijos": [
            {"matricula_id": m["matricula_id"], "apodo": m["apodo"], "grado": m["grado"]} for m in matriculas
        ],
        "matriculas": matriculas,
        "direcciones": direcciones,
        "consentimientos": consentimientos,
        "pedidos": remotos.get("pedidos", {"disponible": False}),
        "casos": remotos.get("casos", {"disponible": False}),
        "trabajos_kit": remotos.get("trabajos_kit", {"disponible": False}),
        "supresion": {
            "frase_confirmacion": FRASE_CONFIRMACION,
            "suprimido": list(SUPRIMIDO),
            "conservado": list(CONSERVADO),
        },
    }


@router.get(
    "/v1/cuenta/mis-datos",
    tags=["privacidad"],
    summary="Que datos mios tiene Tukit: cuenta, hijos, consentimientos y punteros a pedidos y casos.",
)
async def mis_datos(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    return await _mis_datos(peticion, authorization, completo=False)


@router.get(
    "/v1/cuenta/mis-datos/exportar",
    tags=["privacidad"],
    summary="Mi copia completa en JSON, como archivo descargable.",
)
async def exportar_mis_datos(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> Response:
    import json

    datos = await _mis_datos(peticion, authorization, completo=True)
    ahora = datetime.now(UTC)
    datos["exportado_en"] = ahora.isoformat()
    return Response(
        content=json.dumps(datos, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="tukit-mis-datos-{ahora:%Y-%m-%d}.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/v1/cuenta/consentimientos/revocar",
    tags=["privacidad"],
    summary="Revoca mis autorizaciones de tratamiento sin borrar la cuenta.",
)
async def revocar_mis_consentimientos(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(authorization, repo)
        revocados = await repo.revocar_consentimientos(fila.id, datetime.now(UTC))
    return {"revocados": revocados}


@router.post(
    "/v1/cuenta/supresion",
    tags=["privacidad"],
    summary="Suprime mis datos personales y cierra la cuenta. Lo que la ley obliga a guardar se desvincula.",
)
async def suprimir_mis_datos(
    peticion: Request,
    cuerpo: PeticionSupresion,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Supresion (Ley 1581, art. 8 lit. e y art. 15). Pide la frase escrita.

    Antes de borrar se cuenta cuantos pedidos quedan conservados, para
    decirselo al titular. Ese conteo es la unica llamada afuera y es de solo
    lectura; si falla, la supresion sigue y el conteo sale `None`.
    """
    import logging

    from ..dominio.privacidad import CONSERVADO, SUPRIMIDO, confirmacion_valida, correo_suprimido

    async with peticion.app.state.motor.sesion() as db:
        await _usuario_del_token(authorization, RepoIdentidad(await db.connection()))
    if not confirmacion_valida(cuerpo.confirmacion):
        raise ErrorDominio(
            "confirmacion_requerida",
            "Para borrar tus datos escribe la frase de confirmacion tal como aparece.",
            estado=422,
            campo="confirmacion",
        )
    remotos = await _inventario_remoto(peticion).resumen(_token_del_encabezado(authorization) or "")
    pedidos = remotos.get("pedidos", {})
    conservados = pedidos.get("total") if pedidos.get("disponible") else None

    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        # Se vuelve a verificar dentro de la transaccion que escribe.
        fila = await _usuario_del_token(authorization, repo)
        solicitud_id = await repo.suprimir_titular(fila.id, correo_nuevo=correo_suprimido(str(fila.id)))
    # Bitacora sin datos personales: id seudonimo y solicitud, nada mas.
    logging.getLogger(__name__).info("supresion titular=%s solicitud=%s", fila.id, solicitud_id)
    return {
        "solicitud_id": str(solicitud_id),
        "estado": "propagando",
        "suprimido": list(SUPRIMIDO),
        "conservado": list(CONSERVADO),
        "pedidos_conservados": conservados,
        "mensaje": (
            "Borramos tus datos personales y cerramos tu cuenta. Lo que la ley nos "
            "obliga a guardar quedo desvinculado de tu nombre y tu correo."
        ),
    }
