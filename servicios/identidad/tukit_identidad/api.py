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
un nombre de menor, un documento ni un `estudiante_id`. Esa superficie
necesita control de acceso por clasificacion de dato, y abrirla sin eso seria
exactamente el defecto que el Anexo M documenta.

**La excepcion, y hay que nombrarla:** `GET /v1/cuenta/matriculas` (autenticada,
Bearer) devuelve la matricula —solo `{colegio_id, grado, anio_lectivo}`— del
PROPIO portador del token. Nace porque el frontend ya la necesita: quien vuelve
a `/empezar` con sesion no debe re-teclear a sus hijos. Se defiende por tres
recortes que la prueba de superficie fija: exige token, alcanza solo lo del
portador (nunca lo de otro acudiente por rol) y no expone ni un campo de menor
(ni nombre, ni apodo, ni documento, ni `estudiante_id`). Colegio, grado y anio
no singularizan a un menor: son el ambito de tenencia, no su identidad.

Y `POST /v1/registro` (sin sesion) es el registro de verdad que el docstring de
`registrar_contacto` anticipaba: da credencial usable a una cuenta y persiste
las matriculas de sus hijos usando un apodo opcional cifrado como
`nombre_cifrado` —nunca el nombre legal, por minimizacion (Ley 1581 de 2012,
Art. 4)—. Solo ESCRIBE; no devuelve ningun dato de menor.

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
from sqlalchemy import and_, func, insert, or_, select, update
from tukit_comun.bd import crear_motor
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.http import ErrorDominio, crear_app, iso as _iso
from tukit_comun.identificadores import derivar

from .modelos import Base
from .sesiones import emitir_token, hashear_clave, leer_token, verificar_clave

PUERTO_POR_OMISION = 8011

# Forma minima de un correo: algo, arroba, algo con punto. No pretende cubrir
# la RFC, que admite cosas que ningun proveedor acepta; pretende que
# `papa` o `papa@ejemplo` no creen una cuenta.
_FORMA_CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

COLEGIO = Base.metadata.tables["colegio"]
SEDE = Base.metadata.tables["sede"]
USUARIO = Base.metadata.tables["usuario"]
ASIGNACION_ROL = Base.metadata.tables["asignacion_rol"]
DIRECCION = Base.metadata.tables["direccion"]
ESTUDIANTE = Base.metadata.tables["estudiante"]
MATRICULA = Base.metadata.tables["matricula"]
ACUDIENTE_MATRICULA = Base.metadata.tables["acudiente_matricula"]

# El centinela con que nace un contacto sin registro (`registrar_contacto`). No
# valida contra ninguna clave; distinguirlo de un hash real es lo que permite a
# `POST /v1/registro` ascender ese contacto a cuenta sin pisar una credencial de
# verdad.
_CLAVE_CENTINELA = "sin-credencial"

# Los roles que PUEDEN llamar al padron de acudientes: el equipo interno de
# Tukit, que se siembra a ambito global. Es la puerta 403.
_ROLES_STAFF = ("admin", "operador")

# Los roles INTERNOS cuyo portador NO es acudiente y por tanto queda FUERA del
# padron. Superset de _ROLES_STAFF: suma los del colegio. La exclusion es por
# ROL vigente, no por ausencia de hijos: un interno con un hijo matriculado
# sigue siendo interno y no aparece en el padron.
_ROLES_INTERNOS = ("admin", "operador", "colegio_admin", "colegio_docente")

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
            COLEGIO.c.dane,
            COLEGIO.c.logo_url,
            func.count(SEDE.c.id).label("sedes"),
        )
        .select_from(
            COLEGIO.outerjoin(SEDE, and_(SEDE.c.colegio_id == COLEGIO.c.id, SEDE.c.activa.is_(True)))
        )
        .where(COLEGIO.c.activo.is_(True))
        .group_by(COLEGIO.c.id, COLEGIO.c.nombre, COLEGIO.c.dane, COLEGIO.c.logo_url)
        .order_by(COLEGIO.c.nombre)
    )
    if busqueda:
        consulta = consulta.where(func.lower(COLEGIO.c.nombre).like(f"%{busqueda.lower()}%"))

    async with app.state.motor.engine.begin() as conexion:
        # El logo va aqui porque el desplegable del padre pinta la tarjeta sin
        # abrir el detalle; los contactos no, que son de la pantalla admin. El
        # DANE tambien: el buscador de `/empezar` lo casa contra el directorio de
        # Bogota para reconducir por `colegio_id` al aliado que comparte ese DANE
        # (y no darlo de alta de nuevo como colegio del directorio).
        datos = [
            {
                "colegio_id": str(f.id),
                "nombre": f.nombre,
                "dane": f.dane,
                "sedes": int(f.sedes),
                "logo_url": f.logo_url,
            }
            for f in await conexion.execute(consulta)
        ]
    return {"total": len(datos), "colegios": datos}


@app.get(
    "/v1/directorio/{dane}",
    tags=["colegios"],
    summary="Datos DUEB de un colegio del directorio, para pre-llenar el perfil del nuevo",
)
async def datos_directorio(
    dane: str,
    # Por defecto se devuelven SOLO los 7 campos del alta. La subida de listas
    # (inteligencia) vuelca TODO lo que reciba de aqui en `colegio_datos`, que
    # Catalogo persiste como JSON sin validar; si el default trajera sector,
    # localidad, rector, telefonos y correos, se filtrarian a cada colegio nuevo.
    # El admin pide la ficha completa a proposito con `?completo=true`.
    completo: Annotated[bool, Query(description="Trae la ficha DUEB completa (admin)")] = False,
) -> dict[str, Any]:
    """El bloque del DUEB para un DANE. Por defecto, SOLO los 7 campos del alta
    (direccion, contacto, sitio): es lo que la subida vuelca sin filtrar en
    `colegio_datos`, asi que el default se mantiene minimo para no ensuciar cada
    colegio nuevo. Con `?completo=true` agrega sector, localidad, rector y las
    listas de telefonos/correos, para el detalle del colegio en el admin. 404 si
    el DANE no esta en el directorio (colegio de otra ciudad o escrito a mano):
    quien llama degrada a solo nombre+dane."""
    from .directorio_bogota import datos_colegio_nuevo_por_dane, ficha_directorio_por_dane

    datos = ficha_directorio_por_dane(dane) if completo else datos_colegio_nuevo_por_dane(dane)
    if datos is None:
        raise ErrorDominio(
            "dane_no_en_directorio", f"El DANE {dane} no esta en el directorio de Bogota.", estado=404
        )
    return datos


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


# Los campos institucionales que el administrador puede completar. El nombre y
# el NIT NO estan aqui a proposito: son la identidad de la institucion y
# Catalogo referencia al colegio por su id derivado, asi que cambiarlos por esta
# puerta romperia esa referencia. Son datos de la INSTITUCION, no del menor: no
# les toca el cifrado del Anexo M que si protege al estudiante en el mismo
# modelo, por eso viajan y se guardan en claro.
#
# El `dane` SI es editable: aqui el `colegio_id` es un UUID que ya viene fijado
# al crear el colegio (no se re-deriva del DANE en esta base), asi que escribir
# el codigo DANE cuando falta —para poder leer su ficha del directorio— no mueve
# ninguna referencia. Distinto del NIT, que sigue fijo.
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


@app.patch("/v1/colegios/{colegio_id}", tags=["colegios"], summary="Editar el perfil institucional")
async def editar_colegio(colegio_id: uuid.UUID, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """El administrador completa el perfil que el padre reconoce en la tarjeta.

    Solo se aceptan los campos institucionales; un intento de tocar `nombre` o
    `nit` se rechaza con 400 antes de escribir nada, porque esa identidad es fija
    y Catalogo la referencia por id. Devuelve la MISMA forma que el detalle, para
    que la pantalla admin refresque sin una segunda llamada.
    """
    for campo in _CAMPOS_FIJOS:
        if campo in cuerpo:
            raise ErrorDominio(
                "campo_no_editable",
                "El nombre y el NIT son la identidad de la institucion y no se editan aqui.",
                estado=400,
                campo=campo,
            )
    # El DANE es la llave del directorio DUEB: o son 12 digitos exactos, o es
    # `null` para vaciarlo. Cualquier otra cosa (menos digitos, letras, un numero)
    # se rechaza antes de escribir, para no guardar una llave que nunca casara con
    # el directorio.
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

    async with app.state.motor.engine.begin() as conexion:
        existe = await conexion.scalar(select(COLEGIO.c.id).where(COLEGIO.c.id == colegio_id))
        if existe is None:
            raise ErrorDominio(
                "colegio_no_existe", "No hay ningun colegio con ese identificador.", estado=404
            )
        if valores:
            await conexion.execute(update(COLEGIO).where(COLEGIO.c.id == colegio_id).values(**valores))
    return await ver_colegio(colegio_id)


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


@app.get(
    "/v1/contactos/{usuario_id}",
    tags=["contacto"],
    summary="Resuelve un id a su contacto para enviar. Efimero: nadie lo guarda.",
)
async def resolver_contacto(usuario_id: uuid.UUID) -> dict[str, Any]:
    """Devuelve el contacto de un usuario para que el repartidor de Operacion
    pueda entregar el aviso SIN guardar el dato.

    Es la contraparte de `POST /v1/contactos`: alli el correo entra y se cambia
    por un id; aqui el id se cambia por el correo, justo en el momento del
    envio. La razon de que exista es precisamente la deuda del manifiesto: el
    contacto vive en un solo sitio (aqui), la notificacion lo referencia por id,
    y el derecho al olvido lo alcanza en un unico lugar.

    `celular` es hoy nulo: el sistema no persiste el celular del acudiente en
    ninguna tabla, asi que el envio por wa-link cae a correo mientras no exista
    esa columna. Se devuelve el campo igual para que el contrato del repartidor
    no cambie el dia que el celular se capture.
    """
    async with app.state.motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(USUARIO.c.correo, USUARIO.c.activo).where(USUARIO.c.id == usuario_id)
            )
        ).one_or_none()
    if fila is None or not fila.activo:
        raise ErrorDominio(
            "usuario_no_existe",
            "No hay ningun usuario activo con ese identificador.",
            estado=404,
        )
    return {"usuario_id": str(usuario_id), "correo": fila.correo, "celular": None}


# ---------------------------------------------------------------- registro
#
# El registro de verdad que `registrar_contacto` anticipaba. Da credencial
# usable a una cuenta (o la crea) y persiste las matriculas de sus hijos. Es
# la unica ruta publica que escribe en la tabla de menores, y por eso lleva
# tres cuidados: solo el apodo (opcional, cifrado) toca al menor y nunca su
# nombre legal (minimizacion, Ley 1581 de 2012, Art. 4); todo se deriva para
# ser idempotente; y si el correo ya tiene una credencial REAL, la ruta no
# escribe nada —ni la clave ni los hijos— para que un tercero sin sesion no
# pueda inyectar matriculas en la cuenta de otra familia.


class HijoRegistro(BaseModel):
    """Un hijo tal como el formulario lo manda: colegio y grado bastan para
    armar el kit. El `apodo` es opcional y es lo unico que identifica al menor;
    se guarda cifrado. NO se pide el nombre legal: no hace falta para la
    finalidad (armar la lista) y recolectarlo violaria el principio de
    necesidad."""

    colegio_id: uuid.UUID
    grado: str = Field(min_length=1, max_length=32)
    apodo: str | None = Field(default=None, max_length=120)


class Registro(BaseModel):
    """El alta del acudiente nuevo: su credencial, su celular para el aviso y
    sus hijos. La clave pide un minimo de 8 para no crear cuentas triviales;
    no se valida mas forma porque la politica real vive en un solo sitio el dia
    que endurezca, y aqui solo se hashea."""

    correo: str = Field(min_length=5, max_length=320)
    clave: str = Field(min_length=8, max_length=256)
    celular: str | None = Field(default=None, max_length=32)
    hijos: list[HijoRegistro] = Field(default_factory=list)


async def _materializar_hijos(
    conexion: Any,
    usuario_id: uuid.UUID,
    hijos: list[HijoRegistro],
    anio_lectivo: int,
    cifrador: Any,
    conteo_inicial: dict[tuple[uuid.UUID, str], int] | None = None,
) -> int:
    """Materializa cada hijo como estudiante + matricula + vinculo del acudiente
    (UUID derivado + SELECT-then-INSERT). Reutilizable por el registro y por
    `POST /v1/cuenta/matriculas` (y a futuro el poller); corre dentro de una
    transaccion que abre el llamador.

    POR QUE cuenta repeticiones: dos hijos con el MISMO (colegio, grado) —gemelos—
    derivarian el mismo `estudiante_id` y colapsarian en una sola fila. Se lleva un
    conteo por (colegio_id, grado): la aparicion nº1 conserva la derivacion
    historica intacta —no se le agrega nada, o reescribiria PKs ya sembradas por
    `sembrar_acceso`—; desde la nº2 se agrega el ordinal, y como `matricula_id`
    deriva de `estudiante_id`, tambien diverge.

    POR QUE un `conteo_inicial` opcional: el registro no lo pasa —arranca en 0, y
    reenviar la MISMA peticion cae en las mismas filas derivadas (idempotente)—.
    Pero la ruta de sesion SI lo pasa, con las repeticiones que el portador YA
    tiene guardadas en cada (colegio, grado). Sin eso, "agregar" un segundo hijo al
    mismo par arrancaria de nuevo en la aparicion nº1, cuya derivacion coincide
    EXACTAMENTE con la del hijo existente: el SELECT lo encontraria, no insertaria
    nada y el apodo del hijo nuevo se perderia. Con el conteo previo, el hijo nuevo
    toma el ordinal SIGUIENTE y cae en una fila distinta.

    Devuelve cuantos hijos se CREARON de verdad (vinculo nuevo), no cuantos se
    recibieron: si una derivacion cae en una fila ya existente, no cuenta.
    """
    # Copia, para no mutar el dict del llamador al ir contando dentro del bucle.
    conteo: dict[tuple[uuid.UUID, str], int] = dict(conteo_inicial or {})
    creados = 0
    for hijo in hijos:
        # El grado se valida tambien aqui (no solo en el pre-check del registro):
        # el endpoint de sesion no tiene pre-check y debe quedar cubierto por el
        # mismo 422.
        if hijo.grado not in GRADOS:
            raise ErrorDominio(
                "grado_invalido", f"'{hijo.grado}' no es un grado escolar.", estado=422, campo="grado"
            )

        # La sede activa del colegio. En el piloto es unica ("Sede unica");
        # colegios multi-sede quedan como brecha conocida (se toma la primera
        # activa por nombre).
        sede_id = await conexion.scalar(
            select(SEDE.c.id)
            .where(SEDE.c.colegio_id == hijo.colegio_id, SEDE.c.activa.is_(True))
            .order_by(SEDE.c.nombre)
            .limit(1)
        )
        if sede_id is None:
            raise ErrorDominio(
                "colegio_sin_sede",
                "El colegio no existe o no tiene una sede activa.",
                estado=422,
                campo="colegio_id",
            )

        clave = (hijo.colegio_id, hijo.grado)
        conteo[clave] = conteo.get(clave, 0) + 1
        repeticion = conteo[clave]
        # Aparicion nº1 (incluye el conteo previo del portador): derivacion HISTORICA
        # intacta (misma tupla que `sembrar_acceso`), para no reescribir filas ya
        # existentes. De la nº2 en adelante se agrega el ordinal para separar gemelos
        # —y a los hijos que se agregan sobre un par que el portador ya tenia— en
        # estudiantes distintos.
        if repeticion == 1:
            estudiante_id = derivar(
                "estudiante", str(usuario_id), str(hijo.colegio_id), hijo.grado, str(anio_lectivo)
            )
        else:
            estudiante_id = derivar(
                "estudiante",
                str(usuario_id),
                str(hijo.colegio_id),
                hijo.grado,
                str(anio_lectivo),
                str(repeticion),
            )

        if await conexion.scalar(select(ESTUDIANTE.c.id).where(ESTUDIANTE.c.id == estudiante_id)) is None:
            await conexion.execute(
                insert(ESTUDIANTE).values(
                    id=estudiante_id,
                    nombre_cifrado=cifrador.cifrar((hijo.apodo or "").encode("utf-8")),
                )
            )

        matricula_id = derivar("matricula", str(estudiante_id), str(sede_id), hijo.grado, str(anio_lectivo))
        if await conexion.scalar(select(MATRICULA.c.id).where(MATRICULA.c.id == matricula_id)) is None:
            await conexion.execute(
                insert(MATRICULA).values(
                    id=matricula_id,
                    estudiante_id=estudiante_id,
                    sede_id=sede_id,
                    colegio_id=hijo.colegio_id,
                    grado=hijo.grado,
                    anio_lectivo=anio_lectivo,
                )
            )

        vinculo = await conexion.scalar(
            select(ACUDIENTE_MATRICULA.c.usuario_id).where(
                ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
                ACUDIENTE_MATRICULA.c.matricula_id == matricula_id,
            )
        )
        if vinculo is None:
            await conexion.execute(
                insert(ACUDIENTE_MATRICULA).values(
                    usuario_id=usuario_id,
                    matricula_id=matricula_id,
                    parentesco="acudiente",
                    es_principal=True,
                )
            )
            # Solo aqui se cuenta: el vinculo nuevo es la unidad de "hijo agregado a
            # ESTA cuenta". Si la derivacion cayo en una fila ya existente, no suma.
            creados += 1
    return creados


@app.post(
    "/v1/registro",
    tags=["registro"],
    status_code=201,
    summary="Alta del acudiente: credencial + matriculas de sus hijos. No devuelve menores.",
)
async def registrar_acudiente(registro: Registro) -> dict[str, Any]:
    """Alta idempotente y orden-independiente con `POST /v1/contactos`.

    Tres caminos segun el estado del correo:

    - **No existe:** se crea la cuenta con clave hasheada y celular.
    - **Existe como contacto sin credencial** (`clave_hash` centinela): se le
      pone la clave y el celular. Es el caso de quien primero pidio un kit
      (que creo el contacto) y ahora se registra.
    - **Existe con credencial real:** NO se escribe nada y se devuelve
      `creado=False`. La ruta es publica; permitir mutar una cuenta ya
      registrada dejaria a un tercero colgar matriculas de la familia de otro.

    Los hijos solo se persisten cuando la ruta establece la credencial (los dos
    primeros casos). Cada hijo se materializa como estudiante + matricula +
    vinculo, todo con UUID derivado para que reenviar el formulario no duplique.
    El `nombre_cifrado` del estudiante es el apodo cifrado (o cadena vacia
    cifrada si no vino): la columna es NOT NULL, pero jamas guarda el nombre
    legal.
    """
    correo = str(registro.correo).strip().lower()
    if not _FORMA_CORREO.fullmatch(correo):
        raise ErrorDominio(
            "correo_invalido", "El correo no tiene una forma valida.", estado=422, campo="correo"
        )
    for hijo in registro.hijos:
        # El grado se compara contra el catalogo escolar (no contra las listas
        # cargadas): un grado que el sistema no nombra es una entrada corrupta.
        # Este pre-check corre ANTES de la transaccion y para TODOS los caminos
        # (incluido el correo ya-registrado que retorna temprano sin materializar):
        # es redundante con la validacion de `_materializar_hijos`, pero deliberado,
        # para que un grado invalido sea 422 aunque no se llegue a materializar.
        if hijo.grado not in GRADOS:
            raise ErrorDominio(
                "grado_invalido", f"'{hijo.grado}' no es un grado escolar.", estado=422, campo="grado"
            )

    cifrador = cifrador_desde_entorno()
    anio_lectivo = datetime.now(UTC).year

    async with app.state.motor.engine.begin() as conexion:
        existente = (
            await conexion.execute(
                select(USUARIO.c.id, USUARIO.c.clave_hash).where(USUARIO.c.correo == correo)
            )
        ).one_or_none()

        if existente is not None and existente.clave_hash != _CLAVE_CENTINELA:
            # Ya es una cuenta de verdad: sin sesion no se toca. Quien ya tiene
            # cuenta entra por el otro camino ("ya tengo cuenta"), no por aqui.
            return {"usuario_id": str(existente.id), "creado": False}

        if existente is None:
            usuario_id = derivar("usuario", correo)
            await conexion.execute(
                insert(USUARIO).values(
                    id=usuario_id,
                    correo=correo,
                    clave_hash=hashear_clave(registro.clave),
                    celular=registro.celular,
                )
            )
        else:
            usuario_id = existente.id
            await conexion.execute(
                update(USUARIO)
                .where(USUARIO.c.id == usuario_id)
                .values(clave_hash=hashear_clave(registro.clave), celular=registro.celular)
            )

        # Cada hijo se materializa como estudiante + matricula + vinculo, con UUID
        # derivado para que reenviar el formulario no duplique. Los gemelos (mismo
        # colegio y grado en la misma peticion) caen en estudiantes distintos.
        await _materializar_hijos(conexion, usuario_id, registro.hijos, anio_lectivo, cifrador)

    return {"usuario_id": str(usuario_id), "creado": True}


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


# ------------------------------------------------------------------ cuenta
#
# La superficie de "mi cuenta" del acudiente: quien soy y mi libreta de
# direcciones. El dashboard del padre corria sobre datos de muestra porque esta
# superficie no existia; aqui nace, sobre el token que ya emite `iniciar_sesion`.
#
# La libreta vive en Identidad y no en Comercio porque es dato personal de una
# familia con menores y la supresion tiene que alcanzarla (ADR 0015). La linea
# de la direccion y el telefono viajan cifrados en la base y se descifran aqui
# con el cifrador del entorno (en desarrollo, `CifradorEnClaro`, que lo dice).


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


async def _usuario_del_token(authorization: str | None, conexion: Any) -> Any:
    """El usuario activo portador del token, o 401. Reusa la misma verificacion
    de firma/expiracion y revocacion por `version_permisos` que `sesion_actual`."""
    token = _token_del_encabezado(authorization)
    payload = leer_token(token) if token else None
    if payload is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    usuario_id = uuid.UUID(payload["sub"])
    fila = (await conexion.execute(select(USUARIO).where(USUARIO.c.id == usuario_id))).one_or_none()
    if fila is None or not fila.activo:
        raise ErrorDominio("sesion_invalida", "La cuenta ya no esta activa.", estado=401)
    if int(payload.get("vp", -1)) != int(fila.version_permisos):
        raise ErrorDominio("sesion_revocada", "La sesion fue revocada. Vuelve a entrar.", estado=401)
    return fila


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


async def _direcciones_de(conexion: Any, usuario_id: uuid.UUID) -> list[dict[str, Any]]:
    filas = await conexion.execute(
        select(DIRECCION)
        .where(DIRECCION.c.usuario_id == usuario_id, DIRECCION.c.archivada_en.is_(None))
        .order_by(DIRECCION.c.predeterminada.desc(), DIRECCION.c.creado_en)
    )
    return [_direccion_publica(f) for f in filas]


@app.get("/v1/cuenta", tags=["cuenta"], summary="Quien soy: el portador de este token.")
async def ver_cuenta(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """La identidad del acudiente para su propio panel. El nombre va descifrado;
    el correo es el de la cuenta. No devuelve menores: esa superficie sigue
    cerrada (ver la prueba de superficie)."""
    async with app.state.motor.engine.begin() as conexion:
        fila = await _usuario_del_token(authorization, conexion)
        nombre = fila.correo
        if fila.nombre_cifrado is not None:
            nombre = cifrador_desde_entorno().descifrar(fila.nombre_cifrado).decode("utf-8", errors="replace")
    return {"usuario_id": str(fila.id), "correo": fila.correo, "nombre": nombre}


@app.get(
    "/v1/cuenta/matriculas",
    tags=["cuenta"],
    summary="El ambito de tenencia de MIS hijos: colegio, grado y anio. Sin datos de menor.",
)
async def listar_matriculas(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """Lo justo para precargar `/empezar` sin re-teclear a los hijos.

    Devuelve `{colegio_id, grado, anio_lectivo, apodo}` de las matriculas activas
    vinculadas al portador con vinculo vigente. El `apodo` (descifrado en servidor;
    vacio -> null) SI baja: el PADRE puede ver el apodo de SUS hijos —es el portador
    del token y ya lo escribio el mismo—, para precargarlo en `/empezar`. Sigue sin
    devolver el nombre legal, el `estudiante_id`, el documento ni la marca de tiempo:
    nada mas que singularice al menor. Se filtra por el `usuario_id` del token, no
    por rol: un colegio_admin no ve por aqui a los hijos de su colegio, solo el
    acudiente ve los suyos (misma clasificacion que `/v1/admin/acudientes`, pero
    autenticado y limitado a lo propio).
    """
    async with app.state.motor.engine.begin() as conexion:
        fila = await _usuario_del_token(authorization, conexion)
        cifrador = cifrador_desde_entorno()
        filas = await conexion.execute(
            select(
                MATRICULA.c.colegio_id,
                MATRICULA.c.grado,
                MATRICULA.c.anio_lectivo,
                ESTUDIANTE.c.nombre_cifrado,
            )
            .select_from(
                ACUDIENTE_MATRICULA.join(
                    MATRICULA, ACUDIENTE_MATRICULA.c.matricula_id == MATRICULA.c.id
                ).join(ESTUDIANTE, MATRICULA.c.estudiante_id == ESTUDIANTE.c.id)
            )
            .where(
                ACUDIENTE_MATRICULA.c.usuario_id == fila.id,
                ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
                MATRICULA.c.estado == "activa",
            )
            .order_by(MATRICULA.c.colegio_id, MATRICULA.c.grado)
        )
        matriculas = []
        for f in filas:
            # Mismo patron de descifrado que `listar_acudientes`: vacio -> None.
            apodo = cifrador.descifrar(f.nombre_cifrado).decode("utf-8", errors="replace")
            matriculas.append(
                {
                    "colegio_id": str(f.colegio_id),
                    "grado": f.grado,
                    "anio_lectivo": int(f.anio_lectivo),
                    "apodo": apodo or None,
                }
            )
    return {"total": len(matriculas), "matriculas": matriculas}


class MatriculasNuevas(BaseModel):
    """Hijos que un acudiente YA autenticado agrega a su cuenta desde `/empezar`.
    Reusa `HijoRegistro`: misma forma `{colegio_id, grado, apodo?}` y mismas reglas
    de validacion que el alta del registro."""

    hijos: list[HijoRegistro] = Field(default_factory=list)


@app.post(
    "/v1/cuenta/matriculas",
    tags=["cuenta"],
    status_code=201,
    summary="Agrega matriculas de MIS hijos con sesion. Solo escribe; no devuelve menores.",
)
async def guardar_matriculas(
    cuerpo: MatriculasNuevas,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Equivalente autenticado del alta de hijos de `POST /v1/registro`: el portador
    del token agrega a sus propios hijos sin re-registrar la cuenta. Mismas
    validaciones (grado en catalogo, colegio con sede activa -> 422). Solo escribe
    tenencia del PORTADOR; la respuesta es `{total}` con los hijos REALMENTE creados,
    sin ningun dato de menor. Un grado invalido de un hijo posterior aborta la
    transaccion completa (rollback), asi que no hace falta pre-check aparte.

    "Agregar" SIEMPRE crea un hijo nuevo, con el ordinal siguiente: se le pasa a
    `_materializar_hijos` cuantos hijos tiene ya el portador en cada (colegio, grado)
    de este anio, para que el hijo nuevo no reciba la derivacion de "primera
    aparicion" —que coincide con la del hijo existente y colapsaria en su fila,
    perdiendo el apodo—. Por eso el endpoint NO es idempotente ante reenvios: la
    proteccion contra reenvios la da la firma del formulario (`matriculasFirma`), no
    esta ruta.
    """
    cifrador = cifrador_desde_entorno()
    anio_lectivo = datetime.now(UTC).year
    async with app.state.motor.engine.begin() as conexion:
        # Se resuelve el portador ANTES de escribir: sin token valido, 401 y nada
        # se materializa.
        fila = await _usuario_del_token(authorization, conexion)
        # Cuantas matriculas tiene ya el portador en cada (colegio, grado) de este
        # anio, con el MISMO filtro de vigencia que `listar_matriculas` (vinculo
        # vigente + matricula activa). Ese conteo previo es lo que hace que agregar
        # otro hijo al mismo par tome el ordinal siguiente en vez de re-derivar la
        # fila que ya existe. La clave se normaliza a uuid.UUID para casar con la que
        # usa `_materializar_hijos` (`hijo.colegio_id`, un uuid.UUID de pydantic).
        filas_previas = await conexion.execute(
            select(MATRICULA.c.colegio_id, MATRICULA.c.grado, func.count().label("n"))
            .select_from(
                ACUDIENTE_MATRICULA.join(MATRICULA, ACUDIENTE_MATRICULA.c.matricula_id == MATRICULA.c.id)
            )
            .where(
                ACUDIENTE_MATRICULA.c.usuario_id == fila.id,
                ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
                MATRICULA.c.estado == "activa",
                MATRICULA.c.anio_lectivo == anio_lectivo,
            )
            .group_by(MATRICULA.c.colegio_id, MATRICULA.c.grado)
        )
        conteo_inicial = {
            (uuid.UUID(str(f.colegio_id)), f.grado): int(f.n) for f in filas_previas
        }
        total = await _materializar_hijos(
            conexion, fila.id, cuerpo.hijos, anio_lectivo, cifrador, conteo_inicial
        )
    return {"total": total}


@app.get("/v1/cuenta/direcciones", tags=["cuenta"], summary="Mi libreta de direcciones, descifrada.")
async def listar_direcciones(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    async with app.state.motor.engine.begin() as conexion:
        fila = await _usuario_del_token(authorization, conexion)
        direcciones = await _direcciones_de(conexion, fila.id)
    return {"total": len(direcciones), "direcciones": direcciones}


async def _limpiar_predeterminada(conexion: Any, usuario_id: uuid.UUID) -> None:
    """Baja la marca de la anterior predeterminada, para que el indice unico
    parcial no choque cuando llega una nueva."""
    await conexion.execute(
        update(DIRECCION)
        .where(
            DIRECCION.c.usuario_id == usuario_id,
            DIRECCION.c.predeterminada.is_(True),
            DIRECCION.c.archivada_en.is_(None),
        )
        .values(predeterminada=False)
    )


@app.post(
    "/v1/cuenta/direcciones",
    tags=["cuenta"],
    status_code=201,
    summary="Agrega una direccion a mi libreta. La linea y el contacto se cifran.",
)
async def crear_direccion(
    entrada: DireccionEntrada, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    cifrador = cifrador_desde_entorno()
    async with app.state.motor.engine.begin() as conexion:
        fila = await _usuario_del_token(authorization, conexion)
        if entrada.predeterminada:
            await _limpiar_predeterminada(conexion, fila.id)
        nueva = uuid.uuid4()
        await conexion.execute(
            insert(DIRECCION).values(
                id=nueva,
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
        )
        creada = (await conexion.execute(select(DIRECCION).where(DIRECCION.c.id == nueva))).one()
    return _direccion_publica(creada)


@app.patch(
    "/v1/cuenta/direcciones/{direccion_id}",
    tags=["cuenta"],
    summary="Edita una direccion mia. Solo la mia (404 si no).",
)
async def editar_direccion(
    direccion_id: uuid.UUID,
    entrada: DireccionEntrada,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    cifrador = cifrador_desde_entorno()
    async with app.state.motor.engine.begin() as conexion:
        fila = await _usuario_del_token(authorization, conexion)
        actual = (
            await conexion.execute(
                select(DIRECCION).where(
                    DIRECCION.c.id == direccion_id,
                    DIRECCION.c.usuario_id == fila.id,
                    DIRECCION.c.archivada_en.is_(None),
                )
            )
        ).one_or_none()
        if actual is None:
            raise ErrorDominio("direccion_no_existe", "No hay ninguna direccion tuya con ese id.", estado=404)
        if entrada.predeterminada:
            await _limpiar_predeterminada(conexion, fila.id)
        await conexion.execute(
            update(DIRECCION)
            .where(DIRECCION.c.id == direccion_id)
            .values(
                etiqueta=entrada.etiqueta,
                ciudad=entrada.ciudad,
                localidad=entrada.localidad,
                linea_cifrada=cifrador.cifrar(entrada.linea.encode("utf-8")),
                contacto_cifrado=(
                    cifrador.cifrar(entrada.contacto.encode("utf-8")) if entrada.contacto else None
                ),
                predeterminada=entrada.predeterminada,
            )
        )
        editada = (await conexion.execute(select(DIRECCION).where(DIRECCION.c.id == direccion_id))).one()
    return _direccion_publica(editada)


@app.delete(
    "/v1/cuenta/direcciones/{direccion_id}",
    tags=["cuenta"],
    status_code=204,
    summary="Archiva una direccion mia. Baja logica: un envio en curso la sigue viendo.",
)
async def archivar_direccion(
    direccion_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> None:
    """Baja logica y no borrado (ADR 0015): un envio en curso todavia necesita
    que la direccion exista mientras se entrega. La copia congelada del envio
    vive en Comercio y no se toca."""
    async with app.state.motor.engine.begin() as conexion:
        fila = await _usuario_del_token(authorization, conexion)
        resultado = await conexion.execute(
            update(DIRECCION)
            .where(
                DIRECCION.c.id == direccion_id,
                DIRECCION.c.usuario_id == fila.id,
                DIRECCION.c.archivada_en.is_(None),
            )
            .values(archivada_en=datetime.now(UTC), predeterminada=False)
        )
        if resultado.rowcount == 0:
            raise ErrorDominio("direccion_no_existe", "No hay ninguna direccion tuya con ese id.", estado=404)
    return None


# ------------------------------------------------------------------ admin
#
# La primera puerta que expone dato de menor (el apodo) por la superficie
# publica, y por eso la mas vigilada. Se abre SOLO al equipo interno
# (admin/operador) y devuelve unicamente a las familias registradas (credencial
# real, sin rol interno). Nunca clave_hash, documento, fecha de nacimiento ni
# nombre legal: el modelo ni siquiera los selecciona.


@app.get(
    "/v1/admin/acudientes",
    tags=["admin"],
    summary="Padron de acudientes registrados y sus hijos. Solo equipo interno.",
)
async def listar_acudientes(
    authorization: Annotated[str | None, Header()] = None,
    ids: Annotated[str | None, Query(description="UUIDs separados por coma para acotar")] = None,
) -> dict[str, Any]:
    ahora = datetime.now(UTC)
    async with app.state.motor.engine.begin() as conexion:
        # 1) Puerta: token valido (401 si no) ...
        solicitante = await _usuario_del_token(authorization, conexion)
        # 2) ... y rol de staff VIGENTE (403 si no). Mismo predicado de vigencia
        #    que _armar_sesion. No se filtra ambito: admin/operador solo se
        #    siembran a ambito global y el codigo de rol ya los singulariza.
        es_staff = await conexion.scalar(
            select(ASIGNACION_ROL.c.id)
            .where(
                ASIGNACION_ROL.c.usuario_id == solicitante.id,
                ASIGNACION_ROL.c.rol_codigo.in_(_ROLES_STAFF),
                ASIGNACION_ROL.c.vigente_desde <= ahora,
                or_(ASIGNACION_ROL.c.vigente_hasta.is_(None), ASIGNACION_ROL.c.vigente_hasta > ahora),
            )
            .limit(1)
        )
        if es_staff is None:
            raise ErrorDominio(
                "acceso_denegado",
                "Esta vista es solo para el equipo interno de Tukit.",
                estado=403,
            )

        # ids -> lista de UUID, ya PASADA la puerta: un id mal formado responde
        # 400, pero solo a quien ya autentico y tiene rol. Antes del gate, un
        # `?ids=nope` sin token debe seguir siendo 401 (no revelar la forma del
        # endpoint). Se acota luego SOBRE el filtro de poblacion; nunca lo relaja.
        ids_filtrados: list[uuid.UUID] | None = None
        if ids is not None:
            crudos = [p.strip() for p in ids.split(",") if p.strip()]
            try:
                ids_filtrados = [uuid.UUID(p) for p in crudos]
            except ValueError:
                raise ErrorDominio(
                    "ids_invalido", "El parametro ids trae un UUID mal formado.", estado=400, campo="ids"
                )

        # 3) La poblacion: credencial REAL, activo, y SIN ningun rol interno
        #    vigente (NOT EXISTS correlado, mismo predicado de vigencia).
        sin_rol_interno = ~(
            select(ASIGNACION_ROL.c.id)
            .where(
                ASIGNACION_ROL.c.usuario_id == USUARIO.c.id,
                ASIGNACION_ROL.c.rol_codigo.in_(_ROLES_INTERNOS),
                ASIGNACION_ROL.c.vigente_desde <= ahora,
                or_(ASIGNACION_ROL.c.vigente_hasta.is_(None), ASIGNACION_ROL.c.vigente_hasta > ahora),
            )
            .exists()
        )
        consulta = (
            select(USUARIO.c.id, USUARIO.c.correo, USUARIO.c.celular, USUARIO.c.creado_en)
            .where(
                USUARIO.c.clave_hash != _CLAVE_CENTINELA,
                USUARIO.c.activo.is_(True),
                sin_rol_interno,
            )
            .order_by(USUARIO.c.creado_en.desc())
        )
        # El acote por ids va SOBRE el filtro (AND), nunca lo abre: el id de un
        # usuario interno sigue excluido por el NOT EXISTS de arriba.
        if ids_filtrados is not None:
            consulta = consulta.where(USUARIO.c.id.in_(ids_filtrados))

        usuarios = list(await conexion.execute(consulta))

        # 4) Los hijos en UNA consulta acotada a esos usuarios; se agrupan en
        #    Python. Vinculo vigente + matricula activa, igual que
        #    listar_matriculas. colegio_id esta desnormalizado en matricula:
        #    join directo a colegio.nombre.
        hijos_por_usuario: dict[uuid.UUID, list[dict[str, Any]]] = {}
        if usuarios:
            cifrador = cifrador_desde_entorno()
            filas_hijos = await conexion.execute(
                select(
                    ACUDIENTE_MATRICULA.c.usuario_id,
                    ESTUDIANTE.c.nombre_cifrado,
                    MATRICULA.c.colegio_id,
                    MATRICULA.c.grado,
                    COLEGIO.c.nombre,
                )
                .select_from(
                    ACUDIENTE_MATRICULA.join(
                        MATRICULA, ACUDIENTE_MATRICULA.c.matricula_id == MATRICULA.c.id
                    )
                    .join(ESTUDIANTE, MATRICULA.c.estudiante_id == ESTUDIANTE.c.id)
                    .join(COLEGIO, MATRICULA.c.colegio_id == COLEGIO.c.id)
                )
                .where(
                    ACUDIENTE_MATRICULA.c.usuario_id.in_([u.id for u in usuarios]),
                    ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
                    MATRICULA.c.estado == "activa",
                )
                .order_by(ACUDIENTE_MATRICULA.c.usuario_id, MATRICULA.c.grado)
            )
            for h in filas_hijos:
                apodo = cifrador.descifrar(h.nombre_cifrado).decode("utf-8", errors="replace")
                hijos_por_usuario.setdefault(h.usuario_id, []).append(
                    {
                        "apodo": apodo or None,
                        "colegio_id": str(h.colegio_id),
                        "colegio_nombre": h.nombre,
                        "grado": h.grado,
                    }
                )

    acudientes = [
        {
            "usuario_id": str(u.id),
            "correo": u.correo,
            "celular": u.celular,
            "creado_en": _iso(u.creado_en),
            "hijos": hijos_por_usuario.get(u.id, []),
        }
        for u in usuarios
    ]
    return {"total": len(acudientes), "acudientes": acudientes}


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
