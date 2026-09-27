"""El recurso `trabajo` y la cola de revision, tal como los fija el contrato.

`POST /v1/trabajos` devuelve 202 y no el kit, y esa es la decision de diseno
que ordena todo lo demas. El pipeline tarda minutos (OP-03 pide precision por
encima de velocidad) y ademas el flujo exige una pausa humana antes de que el
acudiente vea nada (AD-03 a AD-06). Una API sincronica no puede modelar una
espera que incluye a una persona, asi que el recurso central es el trabajo:
se crea, se consulta, y cuando termina se avisa.

Dos cosas de esta version que conviene tener a mano al leer el codigo:

- La ejecucion de fondo es una tarea del mismo proceso. Es lo que permite
  levantar todo con un comando y es tambien lo primero que hay que cambiar:
  ver la nota de `trabajos.lanzar`.
- `TUKIT_AUTOPUBLICAR` salta la revision humana. Existe para que el frontend
  pueda ver kits mientras se construye la pantalla de Admin, y se anuncia a
  gritos al arrancar porque una valvula silenciosa acaba puesta en
  produccion.

    python -m tukit_inteligencia.api        # localhost:8013
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import uuid
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request
from pydantic import BaseModel, Field
from tukit_comun import derivar
from tukit_comun.bd import crear_motor
from tukit_comun.http import ErrorDominio, crear_app

from . import gemini, metricas, paginas, trabajos
from .modelos import EstadoResolucion, EstadoTrabajo
from .percepcion import LeerPagina, Percepcion, Renderizar, percibir
from .remoto import ClienteCatalogo, ClienteComercio, ClienteIdentidad, url_catalogo, url_identidad

PUERTO_POR_OMISION = 8013

# Los dos puertos de percepcion viven como indireccion de modulo para que el
# onboarding se pueda probar sin pypdfium2 y sin una llave de Gemini: las
# pruebas sustituyen `_RENDERIZAR` y `_LEER` (o el envoltorio completo
# `_percibir_onboarding`) por dobles. En produccion apuntan al render real y
# al adaptador de Gemini, que es el unico sitio que toca la red y la llave.
_RENDERIZAR: Renderizar = paginas.renderizar
_LEER: LeerPagina = gemini.pedir_pagina


def _percibir_onboarding(contenido: bytes) -> Percepcion:
    """Envoltorio con los puertos por omision, monkeypatcheable en pruebas."""
    return percibir(contenido, renderizar=_RENDERIZAR, leer=_LEER)


class PercepcionRechazada(ErrorDominio):
    """Un rechazo de percepcion que ademas puede nombrar los grados vistos.

    Reusa el sobre de `ErrorDominio` (mismo manejador, mismo `error`/`mensaje`)
    y solo agrega `grados_detectados` cuando el archivo traia mas de un grado,
    que es la unica pista que ayuda al acudiente a subir la pagina correcta.
    Nunca lleva el contenido del archivo: el sobre dice QUE paso, no QUE se
    subio.
    """

    def __init__(self, error: str, mensaje: str, *, grados_detectados: tuple[str, ...] = ()) -> None:
        super().__init__(error, mensaje, estado=422)
        self.grados_detectados = grados_detectados

    def cuerpo(self) -> dict[str, Any]:
        sobre = super().cuerpo()
        if self.grados_detectados:
            sobre["grados_detectados"] = list(self.grados_detectados)
        return sobre


class Hijo(BaseModel):
    """Un hijo del hogar. `referencia` la pone el acudiente, no el sistema.

    No lleva nombre de menor a proposito: para armar un kit basta con saber
    de que colegio y grado es la lista, y pedir el nombre seria recoger un
    dato de menor que el flujo no necesita. La referencia ("hijo-1") es lo
    que permite devolver las lineas agrupadas.
    """

    referencia: str = Field(min_length=1, max_length=64)
    colegio_id: str = Field(min_length=1, max_length=64)
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int | None = Field(default=None, ge=2020, le=2100)


class Contacto(BaseModel):
    correo: str = Field(min_length=5, max_length=320)
    celular: str | None = Field(default=None, max_length=32)


class Preferencias(BaseModel):
    """Lo que el acudiente declara. NO se pide el estrato.

    En las 60 respuestas de la encuesta, 41 son estrato 4: no tiene varianza
    suficiente para segmentar y si es dato sensible del hogar de un menor.
    Como ademas la correlacion intuitiva no existe (el segmento que mas gasta
    es el MENOS dispuesto a pagar sobreprecio), quitarlo no cuesta precision.
    """

    pesos: dict[str, float] | None = None
    # Cota DURA, no una pista. Es el uso mas valioso de la encuesta: convierte
    # una opinion en una restriccion que el optimizador puede imponer.
    presupuesto_por_hijo: int | None = Field(default=None, gt=0)
    disposicion_sobreprecio: float | None = Field(default=None, ge=0, le=1)
    personaje_por_hijo: dict[str, list[str]] | None = None
    dolor_declarado: str | None = Field(default=None, max_length=64)


class PeticionTrabajo(BaseModel):
    hijos: list[Hijo] = Field(min_length=1)
    contacto: Contacto | None = None
    preferencias: Preferencias | None = None


class DecisionLinea(BaseModel):
    sku: str | None = Field(default=None, max_length=64)
    motivo: str | None = Field(default=None, max_length=512)
    actor: uuid.UUID | None = None


class ProductoEnLinea(BaseModel):
    sku: str = Field(max_length=64)


class DecisionRevision(BaseModel):
    decision: str = Field(pattern="^(aprobar|devolver)$")
    nota: str | None = Field(default=None, max_length=1024)
    actor: uuid.UUID | None = None


class AplicarCanonico(BaseModel):
    """La ruta rapida del acudiente: su nivel + personaje sobre la cache bendita."""

    colegio_id: str = Field(max_length=64)
    grado: str = Field(max_length=64)
    anio_lectivo: int = Field(ge=2020, le=2100)
    perfil: str = Field(max_length=16)
    personaje: str | None = Field(default=None, max_length=64)
    usuario_id: uuid.UUID | None = None


class EntregaCheckout(BaseModel):
    """La direccion a la que se entrega. Se COPIA congelada en Comercio (ADR 0015)."""

    destinatario: str = Field(min_length=1, max_length=256)
    direccion: str = Field(min_length=1, max_length=512)
    ciudad: str = Field(min_length=1, max_length=128)


class PeticionCheckout(BaseModel):
    """Lo que el navegador manda para pagar: el kit por perfil, correo y direccion.

    Nunca un id de base ni una linea: el trabajo (que Inteligencia si conoce)
    tiene el kit y el `usuario_id`; el navegador solo elige el perfil y a donde
    entregar. Asi el checkout no reintroduce lo que RPO cero saca de la vista.
    """

    perfil: str = Field(max_length=16)
    correo: str = Field(min_length=5, max_length=320)
    entrega: EntregaCheckout
    metodo: str = Field(default="pse", max_length=16)
    url_redireccion: str | None = Field(default=None, max_length=512)


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("inteligencia")
    if trabajos.autopublicar():
        print(
            "[inteligencia] TUKIT_AUTOPUBLICAR esta activo: los trabajos se publican SIN "
            "revision humana. Es un atajo de desarrollo y no debe estar puesto fuera de el."
        )
    print(f"[inteligencia] catalogo en {url_catalogo()}, identidad en {url_identidad()}")


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Inteligencia",
    descripcion=(
        "El recurso `trabajo`: percepcion, normalizacion, resolucion y optimizacion de una "
        "lista escolar en tres kits. Contrato: arquitectura/CONTRATO_API.md secciones 2 a 8."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)


@app.post("/v1/trabajos", tags=["trabajos"], status_code=202, summary="Crea un trabajo y lo encola")
async def crear_trabajo(peticion: PeticionTrabajo) -> dict[str, Any]:
    """La peticion es por HOGAR y no por hijo.

    Es lo que hace posible la consolidacion entre hermanos y el reparto de
    empaques: si cada hijo se pidiera aparte, el optimizador no podria ver
    que dos ninos necesitan un borrador cada uno y que una caja de diez sale
    mejor.
    """
    referencias = [hijo.referencia for hijo in peticion.hijos]
    if len(set(referencias)) != len(referencias):
        raise ErrorDominio(
            "referencias_repetidas",
            "Cada hijo necesita una referencia distinta: es con lo que se agrupan sus lineas.",
            campo="hijos",
        )

    pesos = (peticion.preferencias.pesos if peticion.preferencias else None) or {}
    if pesos and abs(sum(pesos.values()) - 1.0) > 0.01:
        raise ErrorDominio(
            "pesos_no_suman_uno",
            "Los pesos de las preferencias tienen que sumar 1.0.",
            estado=422,
            campo="preferencias.pesos",
        )

    respuesta = await trabajos.crear(
        app.state.motor,
        hijos=[hijo.model_dump() for hijo in peticion.hijos],
        contacto=peticion.contacto.model_dump() if peticion.contacto else None,
        preferencias=(peticion.preferencias.model_dump(exclude_none=True) if peticion.preferencias else {}),
    )
    trabajos.lanzar(app.state.motor, uuid.UUID(respuesta["trabajo_id"]))
    return respuesta


@app.get("/v1/trabajos/{trabajo_id}", tags=["trabajos"], summary="Estado, etapas y kits del trabajo")
async def ver_trabajo(trabajo_id: uuid.UUID) -> dict[str, Any]:
    try:
        return await trabajos.ver(app.state.motor, trabajo_id, catalogo=_catalogo())
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error


@app.post(
    "/v1/trabajos/{trabajo_id}/ordenar",
    tags=["trabajos"],
    status_code=201,
    summary="Checkout: arma la orden del kit elegido y arranca el pago (server-to-server)",
)
async def ordenar_trabajo(trabajo_id: uuid.UUID, cuerpo: PeticionCheckout) -> dict[str, Any]:
    """El acudiente elige perfil + direccion; Inteligencia arma la orden en Comercio.

    El navegador no habla con Comercio: manda `trabajo_id` + perfil + correo +
    direccion, y aqui se resuelve el kit y se cobra. Devuelve la
    `url_redireccion` de la pasarela para mandar al acudiente a pagar.
    """
    try:
        return await trabajos.ordenar(
            app.state.motor,
            trabajo_id,
            perfil=cuerpo.perfil,
            entrega=cuerpo.entrega.model_dump(),
            correo=cuerpo.correo,
            metodo=cuerpo.metodo,
            url_redireccion=cuerpo.url_redireccion,
            comercio=_comercio(),
            catalogo=_catalogo(),
            identidad=_identidad(),
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_ordenable",
            "Ese trabajo no tiene un kit de ese perfil para comprar.",
            estado=404,
        ) from error
    except trabajos.CheckoutRechazado as error:
        # Comercio rechazo por negocio (p.ej. precio_cambiado): se reenvia su
        # cuerpo verbatim y su estado, para que el acudiente vea el motivo.
        raise ErrorDominio(
            str(error.cuerpo.get("error") or "checkout_rechazado"),
            str(error.cuerpo.get("mensaje") or "El pago no se pudo iniciar."),
            estado=error.estado,
        ) from error
    except trabajos.RemotoCaido as error:
        raise ErrorDominio(
            "servicio_no_disponible",
            f"No se pudo completar el checkout: {error.servicio} no respondio.",
            estado=503,
        ) from error


@app.post(
    "/v1/trabajos/{trabajo_id}/reintentar",
    tags=["trabajos"],
    summary="Vuelve a correr un trabajo fallido, sin repetir lo que ya estaba bien",
)
async def reintentar(trabajo_id: uuid.UUID) -> dict[str, Any]:
    """Existe porque un trabajo fallido con diagnostico es reintentable.

    Es la contraparte de la seccion 8: si Gemini o el catalogo no
    respondieron, el trabajo quedo guardado con su error y el acudiente no
    tiene que volver a subir nada.
    """
    try:
        actual = await trabajos.ver(app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error

    if actual["estado"] not in {EstadoTrabajo.FALLIDO.value, EstadoTrabajo.ENCOLADO.value}:
        raise ErrorDominio(
            "estado_incompatible",
            f"Solo se reintenta un trabajo fallido o encolado, y este esta en {actual['estado']}.",
            estado=409,
        )

    trabajos.lanzar(app.state.motor, trabajo_id)
    return {"trabajo_id": str(trabajo_id), "estado": EstadoTrabajo.ENCOLADO.value}


# ---------------------------------------------------------------------------
# Onboarding de listas (apps/admin): un PDF entra, el catalogo recibe la lista
# ---------------------------------------------------------------------------


class ParteMultipart:
    """Una parte de un `multipart/form-data`: su nombre, si es archivo y bytes.

    Se conserva el ORDEN y la REPETICION de las partes (una subida de varios
    hijos manda varios `archivo`/`referencia` con el mismo nombre), cosa que el
    aplanado a diccionario de `_leer_multipart` pierde a proposito para el
    onboarding de un solo PDF.
    """

    __slots__ = ("nombre", "es_archivo", "contenido")

    def __init__(self, nombre: str, es_archivo: bool, contenido: bytes) -> None:
        self.nombre = nombre
        self.es_archivo = es_archivo
        self.contenido = contenido

    def texto(self) -> str:
        return self.contenido.decode("utf-8", "replace")


def _partes_multipart(cuerpo: bytes, tipo_contenido: str) -> list[ParteMultipart]:
    """Trocea un `multipart/form-data` en partes, en orden y con repeticiones.

    Se parsea a mano y no con `UploadFile`/`Form` de FastAPI a proposito: esos
    exigen `python-multipart` en el arranque y este servicio no lo trae. Un
    parseo por frontera alcanza para el punado de campos y archivos que suben
    el onboarding y la subida de listas, sin arrastrar una dependencia nueva.
    """
    marca = "boundary="
    posicion = tipo_contenido.find(marca)
    if posicion < 0:
        raise ErrorDominio("multipart_invalido", "El envio no es un formulario multipart valido.", estado=422)
    frontera = tipo_contenido[posicion + len(marca) :].strip().strip('"')
    separador = b"--" + frontera.encode()

    partes: list[ParteMultipart] = []
    for bruto in cuerpo.split(separador):
        bruto = bruto.strip(b"\r\n")
        if not bruto or bruto == b"--":
            continue
        cabeza, _, contenido = bruto.partition(b"\r\n\r\n")
        disposicion = ""
        for linea in cabeza.split(b"\r\n"):
            if linea.lower().startswith(b"content-disposition"):
                disposicion = linea.decode("latin-1", "replace")
        nombre = re.search(r'name="([^"]*)"', disposicion)
        if not nombre:
            continue
        partes.append(ParteMultipart(nombre.group(1), 'filename="' in disposicion, contenido))
    return partes


def _leer_multipart(cuerpo: bytes, tipo_contenido: str) -> tuple[dict[str, str], dict[str, bytes]]:
    """Separa campos de archivos de un `multipart/form-data`, aplanado a dict.

    Es la vista que le sirve al onboarding, que sube un solo PDF y un punado de
    campos de texto: la ultima parte de cada nombre gana. Para una subida con
    partes repetidas usa `_partes_multipart`, que conserva orden y repeticion.
    """
    campos: dict[str, str] = {}
    archivos: dict[str, bytes] = {}
    for parte in _partes_multipart(cuerpo, tipo_contenido):
        if parte.es_archivo:
            archivos[parte.nombre] = parte.contenido
        else:
            campos[parte.nombre] = parte.texto()
    return campos, archivos


def _catalogo() -> Any:
    """El cliente del catalogo, inyectable por `app.state` para las pruebas."""
    cliente = getattr(app.state, "catalogo", None)
    if cliente is None:
        cliente = ClienteCatalogo()
    return cliente


def _identidad() -> Any:
    """El cliente de Identidad, inyectable por `app.state` para las pruebas."""
    cliente = getattr(app.state, "identidad", None)
    if cliente is None:
        cliente = ClienteIdentidad()
    return cliente


def _comercio() -> Any:
    """El cliente de Comercio, inyectable por `app.state` para las pruebas."""
    cliente = getattr(app.state, "comercio", None)
    if cliente is None:
        cliente = ClienteComercio()
    return cliente


def _items_desde_percepcion(percepcion: Percepcion) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """De una percepcion aceptada a `(items, percepcion_cruda)` para el catalogo.

    Un `descripcion` es el `texto_original` que el catalogo va a emparejar, una
    `cantidad` en null se vuelve 1, y la evidencia por pagina lleva el texto
    leido —`crudo` es una cadena (contrato: `PercepcionCruda`), no una lista de
    objetos: la region 2 la pinta directamente—. La percepcion ya viene agregada
    (sin items por pagina), asi que el texto leido se muestra en la pagina 1.
    """
    items = [
        {
            "texto_original": item.descripcion,
            "cantidad": item.cantidad or 1,
            "confianza": item.confianza,
        }
        for item in percepcion.items
    ]
    leido = "\n".join(
        f"{item.cantidad} {item.descripcion}".strip() if item.cantidad else item.descripcion
        for item in percepcion.items
    )
    percepcion_cruda = [
        {"pagina": numero, "crudo": leido if numero == 1 else ""}
        for numero in range(1, percepcion.paginas + 1)
    ]
    return items, percepcion_cruda


class HijoSubida(BaseModel):
    """Un hijo de una subida de listas: a que (colegio, grado) va su PDF.

    El colegio se designa de UNA de tres formas, y el backend deriva de ellas un
    `colegio_id` estable (`colegio_resuelto`):
      • `colegio_id`: un colegio ALIADO ya conocido (ruta "lista_oficial").
      • `colegio_dane` (+ `colegio_nombre`): elegido del directorio de Bogota al
        subir el archivo; el colegio aun no existe en Tukit y nacera cuando un
        administrador apruebe. El id se deriva del DANE con el contrato compartido.
      • solo `colegio_nombre`: escrito a mano porque no estaba en el directorio;
        el id se deriva del nombre normalizado para que dos acudientes que
        escriban el mismo colegio converjan a la misma version.
    """

    referencia: str = Field(min_length=1, max_length=64)
    colegio_id: str | None = Field(default=None, max_length=64)
    colegio_dane: str | None = Field(default=None, max_length=32)
    colegio_nombre: str | None = Field(default=None, max_length=256)
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int | None = Field(default=None, ge=2020, le=2100)

    def resolver_colegio(self) -> tuple[str, dict[str, Any] | None]:
        """El `colegio_id` estable y, si el colegio aun no existe en Tukit, los
        datos con que la aprobacion creara su identidad.

        Un `colegio_id` explicito (aliado conocido) no trae datos: no hay
        identidad que crear. El directorio y el texto a mano SI los traen, para
        que la cola muestre el nombre y el poller de Identidad haga el upsert.
        """
        if self.colegio_id:
            return self.colegio_id, None
        nombre = (self.colegio_nombre or "").strip()
        if self.colegio_dane:
            colegio_id = str(derivar("colegio", self.colegio_dane))
            datos: dict[str, Any] = {"dane": self.colegio_dane, "nombre": nombre or None}
            return colegio_id, datos
        if nombre:
            # Nombre normalizado (espacios colapsados, minusculas) como llave, para
            # que "  Gimnasio  Del Norte " y "gimnasio del norte" sean el mismo.
            clave = " ".join(nombre.lower().split())
            colegio_id = str(derivar("colegio", "libre", clave))
            return colegio_id, {"dane": None, "nombre": " ".join(nombre.split())}
        raise ErrorDominio(
            "colegio_requerido",
            "Falta el colegio del hijo: elige uno o escribe su nombre.",
            estado=422,
            campo="colegio",
        )


@app.post(
    "/v1/listas/subir",
    tags=["listas"],
    status_code=202,
    summary="§2: un acudiente sube el PDF de cada hijo; cada uno queda como version pendiente",
)
async def subir_listas(peticion: Request) -> dict[str, Any]:
    """La puerta del acudiente: PDFs entran, versiones PENDIENTES salen.

    A diferencia de `POST /v1/trabajos` (que arma un kit desechable) y de
    `POST /v1/admin/onboarding` (la subida de un administrador, un PDF por vez),
    esto percibe el PDF de CADA hijo y lo importa al catalogo como una version
    SIN revisar de esa (colegio, grado), ligada al padre por su
    `contacto_referencia` —el `usuario_id` que Identidad emite; nunca su correo
    ni telefono—. No se crea ningun trabajo: el padre espera a que un
    administrador apruebe la version, y recien ahi se arma su kit.

    Es todo o nada por hogar: si la percepcion rechaza el archivo de un hijo
    (varios grados, pagina a medias, ilegible) no se importa NADA y se responde
    422 con el codigo del rechazo, sin devolver jamas el contenido subido. Dos
    hijos del mismo (colegio, grado) comparten una sola version: se importa una
    vez para no pisar una lista con la otra.
    """
    tipo = peticion.headers.get("content-type", "")
    if "multipart/form-data" not in tipo:
        raise ErrorDominio("multipart_invalido", "Sube las listas como multipart/form-data.", estado=422)

    # Si el acudiente ya viene autenticado, su usuario_id sale de la sesion (lo
    # resuelve Identidad; este servicio no tiene la clave HMAC) y ES la traza
    # que baja al catalogo. Solo el flujo anonimo heredado registra por contacto.
    autorizacion = peticion.headers.get("Authorization", "")
    token = autorizacion[7:] if autorizacion.startswith("Bearer ") else None
    usuario_id = await _identidad().usuario_del_token(token) if token else None

    partes = _partes_multipart(await peticion.body(), tipo)
    hijos_crudo = ""
    contacto_crudo = ""
    preferencias_crudo = ""
    # `archivo` y `referencia` llegan como partes repetidas y APAREADAS por
    # orden (cada `archivo` seguido de su `referencia`), igual que las escribe
    # `crearTrabajo`/el navegador. Se recogen en orden y se aparean por indice.
    archivos_orden: list[bytes] = []
    referencias_orden: list[str] = []
    for parte in partes:
        if parte.nombre == "hijos" and not parte.es_archivo:
            hijos_crudo = parte.texto()
        elif parte.nombre == "contacto" and not parte.es_archivo:
            contacto_crudo = parte.texto()
        elif parte.nombre == "preferencias" and not parte.es_archivo:
            preferencias_crudo = parte.texto()
        elif parte.nombre == "archivo" and parte.es_archivo:
            archivos_orden.append(parte.contenido)
        elif parte.nombre == "referencia" and not parte.es_archivo:
            referencias_orden.append(parte.texto())

    archivos: dict[str, bytes] = {}
    for indice, contenido in enumerate(archivos_orden):
        clave = referencias_orden[indice] if indice < len(referencias_orden) else str(indice)
        archivos[clave] = contenido

    try:
        hijos = [HijoSubida(**h) for h in json.loads(hijos_crudo or "[]")]
    except (ValueError, TypeError) as error:
        raise ErrorDominio(
            "hijos_invalidos",
            "El campo `hijos` no trae una lista de hijos valida.",
            estado=422,
            campo="hijos",
        ) from error
    if not hijos:
        raise ErrorDominio(
            "hijos_requeridos", "Sube al menos un hijo con su archivo.", estado=422, campo="hijos"
        )

    # El contacto es opcional: sin el, la lista igual se importa (perder el
    # aviso es malo, perder la lista por no poder avisar es peor).
    contacto = None
    if contacto_crudo:
        try:
            contacto = Contacto(**json.loads(contacto_crudo))
        except (ValueError, TypeError) as error:
            raise ErrorDominio(
                "contacto_invalido", "El contacto no es valido.", estado=422, campo="contacto"
            ) from error

    # Las preferencias del paso 3 son del HOGAR, no de un hijo: se guardan en
    # cada version importada para que, al aprobarla, el kit del padre se optimice
    # con lo que pidio (pesos, disposicion, personaje) y no con los por omision.
    # Son opcionales: sin ellas la aprobacion cae a los pesos por defecto.
    preferencias: dict[str, Any] | None = None
    if preferencias_crudo:
        try:
            crudo = json.loads(preferencias_crudo)
        except ValueError as error:
            raise ErrorDominio(
                "preferencias_invalidas",
                "Las preferencias no son un JSON valido.",
                estado=422,
                campo="preferencias",
            ) from error
        if not isinstance(crudo, dict):
            raise ErrorDominio(
                "preferencias_invalidas",
                "Las preferencias tienen que ser un objeto.",
                estado=422,
                campo="preferencias",
            )
        preferencias = crudo or None

    # Cada hijo tiene que traer su archivo, por referencia o por orden. Se exige
    # ANTES de tocar Identidad o el catalogo: nada a medias.
    def _archivo_de(indice: int, referencia: str) -> bytes:
        if referencia in archivos:
            return archivos[referencia]
        if str(indice) in archivos:
            return archivos[str(indice)]
        raise ErrorDominio(
            "archivo_faltante",
            "Falta el archivo de un hijo de la subida.",
            estado=422,
            campo="archivo",
        )

    pdf_por_hijo = [_archivo_de(i, h.referencia) for i, h in enumerate(hijos)]

    # Se percibe TODO antes de escribir NADA: si un archivo se rechaza, ni
    # Identidad ni el catalogo se tocan. La percepcion resuelve el grado real
    # del PDF (puede diferir del que el acudiente eligio) para deduplicar bien.
    percibidos: list[tuple[HijoSubida, str, bytes, Percepcion]] = []
    for hijo, pdf in zip(hijos, pdf_por_hijo, strict=True):
        percepcion = _percibir_onboarding(pdf)
        if not percepcion.aceptada:
            raise PercepcionRechazada(
                percepcion.error or "percepcion_rechazada",
                percepcion.mensaje,
                grados_detectados=percepcion.grados,
            )
        grado = percepcion.grados[0] if percepcion.grados else hijo.grado
        percibidos.append((hijo, grado, pdf, percepcion))

    # El contacto se registra UNA vez para el hogar, no una por hijo. Su id es
    # la unica traza que baja al catalogo. Si ya hay sesion, el usuario_id de la
    # sesion es esa traza y no se re-registra nada (refleja trabajos.crear:160).
    contacto_referencia: str | None = usuario_id
    if usuario_id is None and contacto and contacto.correo:
        contacto_referencia = await _identidad().registrar_contacto(contacto.correo, contacto.celular)

    # Se importa una version por (colegio, grado): dos hijos del mismo destino
    # comparten la misma, para no pisar una lista con la otra. El `colegio_id` se
    # DERIVA (del aliado elegido, del DANE del directorio o del nombre a mano) y
    # con el viajan los datos del colegio cuando este aun no existe en Tukit,
    # para que la cola lo muestre y la aprobacion cree su identidad.
    catalogo = _catalogo()
    por_destino: dict[tuple[str, int], str] = {}
    subidas: list[dict[str, Any]] = []
    anio_por_omision = 2026
    for hijo, grado, pdf, percepcion in percibidos:
        colegio_id, colegio_datos = hijo.resolver_colegio()
        # Colegio nuevo elegido del directorio: se pre-llena su perfil (direccion,
        # contacto, sitio) con el DUEB para que la cola no muestre un bloque vacio.
        # El nombre/dane de la subida mandan; el directorio solo tapa huecos.
        if colegio_datos and colegio_datos.get("dane"):
            del_dueb = await _identidad().datos_directorio(colegio_datos["dane"])
            if del_dueb:
                colegio_datos = {**del_dueb, **{k: v for k, v in colegio_datos.items() if v}}
        anio = hijo.anio_lectivo or anio_por_omision
        clave = (f"{colegio_id}|{grado}", anio)
        version_id = por_destino.get(clave)
        if version_id is None:
            items, percepcion_cruda = _items_desde_percepcion(percepcion)
            respuesta = await catalogo.importar_lista(
                colegio_id=colegio_id,
                grado=grado,
                anio_lectivo=anio,
                items=items,
                documento_base64=base64.b64encode(pdf).decode(),
                percepcion_cruda=percepcion_cruda,
                contacto_referencia=contacto_referencia,
                preferencias=preferencias,
                colegio_datos=colegio_datos,
                origen="sugerencia_padre",
            )
            version_id = str(respuesta["version_id"])
            por_destino[clave] = version_id
        subidas.append({"referencia": hijo.referencia, "version_id": version_id, "grado": grado})

    return {"subidas": subidas, "contacto_referencia": contacto_referencia}


@app.post(
    "/v1/admin/onboarding",
    tags=["admin"],
    summary="Sube el PDF de una lista, lo percibe y lo importa al catalogo",
)
async def onboarding(peticion: Request) -> dict[str, Any]:
    """De un PDF a una lista en el catalogo, pasando por la percepcion.

    La percepcion es la unica puerta: si rechaza el archivo (varios grados,
    pagina a medias, ilegible) no se importa nada y se responde 422 con el
    codigo del rechazo. Nunca se le devuelve al cliente el contenido que
    subio, ni siquiera cuando se rechaza. Lo que si viaja al catalogo, cuando
    se acepta, es el PDF en base64 y la percepcion cruda por pagina, para que
    la revision humana del catalogo pueda contrastar.
    """
    tipo = peticion.headers.get("content-type", "")
    if "multipart/form-data" not in tipo:
        raise ErrorDominio("multipart_invalido", "Sube la lista como multipart/form-data.", estado=422)
    campos, archivos = _leer_multipart(await peticion.body(), tipo)

    for requerido in ("colegio_id", "grado", "anio_lectivo"):
        if requerido not in campos:
            raise ErrorDominio(
                "campo_faltante", "Falta un campo del formulario de onboarding.", estado=422, campo=requerido
            )
    archivo = archivos.get("archivo")
    if archivo is None:
        raise ErrorDominio(
            "archivo_faltante", "No llego ningun archivo en el campo `archivo`.", estado=422, campo="archivo"
        )
    try:
        anio_lectivo = int(campos["anio_lectivo"])
    except ValueError as error:
        raise ErrorDominio(
            "anio_invalido", "El anio lectivo tiene que ser un numero.", estado=422, campo="anio_lectivo"
        ) from error

    percepcion = _percibir_onboarding(archivo)
    if not percepcion.aceptada:
        raise PercepcionRechazada(
            percepcion.error or "percepcion_rechazada",
            percepcion.mensaje,
            grados_detectados=percepcion.grados,
        )

    # Mismo mapeo (renglones + evidencia por pagina) que la subida del acudiente.
    items, percepcion_cruda = _items_desde_percepcion(percepcion)

    respuesta = await _catalogo().importar_lista(
        colegio_id=campos["colegio_id"],
        grado=percepcion.grados[0] if percepcion.grados else campos["grado"],
        anio_lectivo=anio_lectivo,
        items=items,
        documento_base64=base64.b64encode(archivo).decode(),
        percepcion_cruda=percepcion_cruda,
    )
    return {
        "version_id": respuesta["version_id"],
        "grado": percepcion.grados[0] if percepcion.grados else campos["grado"],
        "items": len(items),
    }


class PeticionPreview(BaseModel):
    colegio_id: str = Field(min_length=1, max_length=64)
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int = Field(ge=2020, le=2100)


@app.post(
    "/v1/admin/onboarding/{version_id}/preview",
    tags=["admin"],
    summary="Arma los tres kits de una lista recien subida, ANTES de aprobarla",
)
async def preview_onboarding(version_id: str, peticion: PeticionPreview) -> dict[str, Any]:
    """Los tres kits + recomendacion de una version vigente pero SIN revisar.

    El admin acaba de subir un PDF (`POST /v1/admin/onboarding`) y quiere ver
    como quedan Ahorrador/Fan/Premium antes de aprobar la version. Se crea un
    trabajo DESECHABLE con `origen='preview_onboarding'` sobre ese
    (colegio, grado, anio): como la version es vigente pero sin revisar, el
    pipeline toma la ruta LENTA (emparejar + NSGA-II), que es exactamente la
    previsualizacion. No se autopublica: el trabajo se queda en
    `espera_revision`/`fallido` y solo sirve para pintar los kits.

    Se corre de forma SINCRONICA (no `trabajos.lanzar`) para que los kits ya
    esten escritos cuando el admin lea `GET /v1/admin/trabajos/{id}`.

    La guarda evita previsualizar una version que ya quedo atras: se resuelve
    la version vigente del catalogo para ese (colegio, grado, anio) —igual que
    `_listas_por_hijo`, por `listas()` y `lista()`— y si no coincide con la del
    path se responde 409. Si no hay ninguna lista, 404.
    """
    catalogo = _catalogo()
    listas = await catalogo.listas(
        colegio_id=peticion.colegio_id, grado=peticion.grado, anio_lectivo=peticion.anio_lectivo
    )
    if not listas:
        raise ErrorDominio(
            "version_no_existe",
            "No hay ninguna lista publicada para ese colegio, grado y anio.",
            estado=404,
        )
    completa = await catalogo.lista(listas[0]["lista_id"])
    vigente = str(completa.get("version_id") or listas[0].get("version_id") or "")
    if vigente != version_id:
        raise ErrorDominio(
            "version_no_vigente",
            "Existe una version mas nueva; previsualiza esa.",
            estado=409,
        )

    # Previsualizar es idempotente por version: si el admin ya previsualizo
    # este (colegio, grado, anio), su preview anterior se descarta antes de
    # armar el nuevo. Sin esto, cada clic dejaba un trabajo desechable mas en
    # la cola y no habia forma de limpiarlos.
    for viejo in await trabajos.previews_de(
        app.state.motor, peticion.colegio_id, peticion.grado, peticion.anio_lectivo
    ):
        await trabajos.eliminar(app.state.motor, viejo)

    respuesta = await trabajos.crear(
        app.state.motor,
        hijos=[
            {
                "referencia": "preview",
                "colegio_id": peticion.colegio_id,
                "grado": peticion.grado,
                "anio_lectivo": peticion.anio_lectivo,
            }
        ],
        contacto=None,
        preferencias={},
        origen="preview_onboarding",
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    estado = await trabajos.procesar(app.state.motor, trabajo_id, catalogo=catalogo)
    return {"trabajo_id": str(trabajo_id), "estado": estado}


# ---------------------------------------------------------------------------
# Revision humana (apps/admin)
# ---------------------------------------------------------------------------


@app.get("/v1/admin/cola", tags=["admin"], summary="AD-02, AD-03: trabajos esperando a una persona")
async def cola(
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await trabajos.cola(app.state.motor, pagina=pagina, por_pagina=por_pagina)


@app.get(
    "/v1/admin/trabajos/{trabajo_id}",
    tags=["admin"],
    summary="AD-03: el trabajo CON sus kits, aunque todavia no este publicado",
)
async def ver_admin(trabajo_id: uuid.UUID) -> dict[str, Any]:
    """Mismo lector que el del acudiente, con los kits forzados.

    El acudiente no ve un kit sin revisar; Admin tiene que verlo, porque su
    trabajo es justamente revisarlo. Es la misma consulta con una bandera, y
    no dos lectores distintos que se puedan desincronizar.
    """
    try:
        return await trabajos.ver(
            app.state.motor, trabajo_id, incluir_kits=True, incluir_admin=True, catalogo=_catalogo()
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error


@app.delete(
    "/v1/admin/trabajos/{trabajo_id}",
    tags=["admin"],
    status_code=204,
    summary="Borra un trabajo desechable (preview, encolado, fallido). No borra publicados.",
)
async def eliminar_trabajo(trabajo_id: uuid.UUID) -> None:
    """Borra un trabajo y su cascada. Un `publicado` esta protegido (409).

    Existe para limpiar los previews que se acumulan al previsualizar una lista
    varias veces, y cualquier trabajo desechable que ensucie la cola. La cascada
    de FKs se lleva etapas, items, kits y lineas; solo queda la bandeja de
    eventos, que es el log.
    """
    try:
        await trabajos.eliminar(app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error
    except trabajos.TrabajoProtegido as error:
        raise ErrorDominio(
            "trabajo_publicado_protegido",
            "Un trabajo publicado es el kit canonico de su colegio y grado; no se borra.",
            estado=409,
        ) from error


@app.post(
    "/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar",
    tags=["admin"],
    summary="AD-04: una persona da por bueno el emparejamiento",
)
async def validar_linea(trabajo_id: uuid.UUID, item_id: uuid.UUID, decision: DecisionLinea) -> dict[str, Any]:
    try:
        return await trabajos.decidir_linea(
            app.state.motor,
            trabajo_id,
            item_id,
            estado=EstadoResolucion.RESUELTO_AUTO.value,
            sku=decision.sku,
            actor=decision.actor,
            motivo=decision.motivo,
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese trabajo no tiene esa linea.", estado=404) from error


@app.put(
    "/v1/admin/trabajos/{trabajo_id}/kits/{perfil}/lineas/{item_id}/producto",
    tags=["admin"],
    summary="AD-04: fija el producto de UN kit (por-nivel), recalculando su subtotal",
)
async def fijar_producto(
    trabajo_id: uuid.UUID, perfil: str, item_id: uuid.UUID, cuerpo: ProductoEnLinea
) -> dict[str, Any]:
    """Escribe LINEA (no RESOLUCION): la eleccion de producto es por kit.

    A diferencia de `validar_linea` —que confirma el emparejamiento del item en
    los tres kits— esto cambia el producto de UN nivel. Es lo que hace que un
    concepto suba de economico a premium entre kits y que un personaje del Fan
    llegue de verdad al kit publicado.
    """
    try:
        return await trabajos.fijar_producto_en_linea(
            app.state.motor, trabajo_id, perfil, item_id, cuerpo.sku, catalogo=_catalogo()
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "linea_no_existe", "Ese trabajo no tiene esa linea en ese kit.", estado=404
        ) from error


@app.get(
    "/v1/grados-canonicos",
    tags=["trabajos"],
    summary="Los (colegio, grado, anio) con cache bendita, para el selector de /empezar",
)
async def listar_grados_canonicos(
    colegio_id: Annotated[str | None, Query(description="Filtra a un colegio")] = None,
) -> dict[str, Any]:
    grados = await trabajos.grados_canonicos(app.state.motor, colegio_id=colegio_id)
    return {"grados": grados}


@app.post(
    "/v1/trabajos/aplicar-canonico",
    tags=["trabajos"],
    status_code=201,
    summary="Ruta rapida: aplica nivel + personaje a la cache bendita y solicita el pedido",
)
async def aplicar_canonico(cuerpo: AplicarCanonico) -> dict[str, Any]:
    """Sin re-optimizar y sin cola: crea el trabajo del acudiente y su pedido.

    Es la contraparte de subir un PDF (que si entra al pipeline). Un grado con
    cache bendita se resuelve al vuelo; el pedido congelado queda para Comercio.
    """
    try:
        return await trabajos.aplicar_canonico(
            app.state.motor,
            colegio_id=cuerpo.colegio_id,
            grado=cuerpo.grado,
            anio_lectivo=cuerpo.anio_lectivo,
            perfil=cuerpo.perfil,
            personaje=cuerpo.personaje,
            usuario_id=cuerpo.usuario_id,
            catalogo=_catalogo(),
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "cache_no_existe",
            "Ese colegio y grado no tiene todavia un kit publicado; sube la lista.",
            estado=404,
        ) from error


@app.post(
    "/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/sin-coincidencia",
    tags=["admin"],
    summary="AD-04: una persona declara que el catalogo no lo tiene",
)
async def sin_coincidencia(
    trabajo_id: uuid.UUID, item_id: uuid.UUID, decision: DecisionLinea
) -> dict[str, Any]:
    """Marca `HUECO_CATALOGO` y no `SIN_MATCH`, y la diferencia importa.

    Si una persona miro la linea, entendio que pedia y concluyo que no lo
    tenemos, eso es un hueco de catalogo: "te entendi y no lo tengo".
    `SIN_MATCH` significa "no te entendi", y despues de una revision humana
    esa ya no es la verdad. Solo el primero se puede responder con una
    alternativa o con una disculpa util, y solo el primero alimenta la
    metrica de que le falta al catalogo.
    """
    try:
        return await trabajos.decidir_linea(
            app.state.motor,
            trabajo_id,
            item_id,
            estado=EstadoResolucion.HUECO_CATALOGO.value,
            actor=decision.actor,
            motivo=decision.motivo,
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese trabajo no tiene esa linea.", estado=404) from error


@app.post(
    "/v1/admin/trabajos/{trabajo_id}/revision",
    tags=["admin"],
    summary="AD-06: aprobar publica al acudiente, devolver reabre sin avisar",
)
async def revisar(trabajo_id: uuid.UUID, decision: DecisionRevision) -> dict[str, Any]:
    try:
        resultado = await trabajos.revisar(
            app.state.motor,
            trabajo_id,
            decision=decision.decision,
            nota=decision.nota,
            actor=decision.actor,
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error
    except trabajos.TransicionIlegal as error:
        raise ErrorDominio(
            "estado_incompatible",
            f"Un trabajo en {error.actual} no se puede pasar a {error.pedida}.",
            estado=409,
        ) from error
    except trabajos.PreviewNoPublicable as error:
        raise ErrorDominio(
            "preview_no_publicable",
            "Este es un preview de la lista, no tiene acudiente a quien avisar. "
            "Para publicar, aprueba la lista en su revisión (crea el colegio y arma "
            "el trabajo del padre).",
            estado=409,
        ) from error

    if decision.decision == "devolver":
        trabajos.lanzar(app.state.motor, trabajo_id)
    return resultado


@app.get(
    "/v1/metricas/colegios/{colegio_id}",
    tags=["metricas"],
    summary="Metricas en vivo de un colegio: kits armados, cobertura y ahorro.",
)
async def metricas_colegio(colegio_id: str) -> dict[str, Any]:
    """El panel del colegio, calculado sobre los trabajos publicados.

    Cuenta los kits recomendados publicados para el colegio, la cobertura del
    catalogo sobre sus lineas comprables (FU-06 medida, no prometida) y el
    ahorro que la consolidacion entre hermanos imputo. Un colegio sin trabajos
    publicados responde con ceros, no con 404: la ausencia de kits es una
    respuesta valida y el panel la sabe pintar.

    El colegio no es una columna de este servicio: vive en el JSON `hijos` de
    cada trabajo, tal como lo mando el acudiente. Por eso el filtro se hace en
    memoria sobre lo publicado; ver `metricas.py`.

    La ruta cuelga de `/v1/metricas/` y no de `/v1/colegios/` a proposito:
    `/v1/colegios` es superficie de Identidad (el catalogo institucional) y el
    gateway rutea por prefijo. Colgarla ahi la mandaria a Identidad; bajo
    `/v1/metricas` llega a Inteligencia, que es quien tiene los kits.
    """
    return await metricas.metricas_de_colegio(app.state.motor, colegio_id)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API del pipeline de kits.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
