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
import re
import uuid
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request
from pydantic import BaseModel, Field
from tukit_comun.bd import crear_motor
from tukit_comun.http import ErrorDominio, crear_app

from . import gemini, paginas, trabajos
from .modelos import EstadoResolucion, EstadoTrabajo
from .percepcion import LeerPagina, Percepcion, Renderizar, percibir
from .remoto import ClienteCatalogo, url_catalogo, url_identidad

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

    def __init__(
        self, error: str, mensaje: str, *, grados_detectados: tuple[str, ...] = ()
    ) -> None:
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


class DecisionRevision(BaseModel):
    decision: str = Field(pattern="^(aprobar|devolver)$")
    nota: str | None = Field(default=None, max_length=1024)
    actor: uuid.UUID | None = None


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
        return await trabajos.ver(app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
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


def _leer_multipart(cuerpo: bytes, tipo_contenido: str) -> tuple[dict[str, str], dict[str, bytes]]:
    """Separa campos de archivos de un `multipart/form-data`.

    Se parsea a mano y no con `UploadFile`/`Form` de FastAPI a proposito: esos
    exigen `python-multipart` en el arranque y este servicio no lo trae. El
    onboarding sube un solo PDF y un punado de campos de texto, asi que un
    parseo por frontera alcanza y no arrastra una dependencia nueva.
    """
    marca = "boundary="
    posicion = tipo_contenido.find(marca)
    if posicion < 0:
        raise ErrorDominio(
            "multipart_invalido", "El envio no es un formulario multipart valido.", estado=422
        )
    frontera = tipo_contenido[posicion + len(marca):].strip().strip('"')
    separador = b"--" + frontera.encode()

    campos: dict[str, str] = {}
    archivos: dict[str, bytes] = {}
    for parte in cuerpo.split(separador):
        parte = parte.strip(b"\r\n")
        if not parte or parte == b"--":
            continue
        cabeza, _, contenido = parte.partition(b"\r\n\r\n")
        disposicion = ""
        for linea in cabeza.split(b"\r\n"):
            if linea.lower().startswith(b"content-disposition"):
                disposicion = linea.decode("latin-1", "replace")
        nombre = re.search(r'name="([^"]*)"', disposicion)
        if not nombre:
            continue
        if 'filename="' in disposicion:
            archivos[nombre.group(1)] = contenido
        else:
            campos[nombre.group(1)] = contenido.decode("utf-8", "replace")
    return campos, archivos


def _catalogo() -> Any:
    """El cliente del catalogo, inyectable por `app.state` para las pruebas."""
    cliente = getattr(app.state, "catalogo", None)
    if cliente is None:
        cliente = ClienteCatalogo()
    return cliente


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
        raise ErrorDominio(
            "multipart_invalido", "Sube la lista como multipart/form-data.", estado=422
        )
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

    # Un item leido se vuelve un renglon del contrato: la cantidad en null se
    # vuelve 1 (un item pedido al menos una vez), y el texto del modelo es el
    # texto_original que el catalogo va a emparejar.
    items = [
        {
            "texto_original": item.descripcion,
            "cantidad": item.cantidad or 1,
            "confianza": item.confianza,
        }
        for item in percepcion.items
    ]
    # La evidencia por pagina agrupa los items que se leyeron en cada una. No
    # se guarda el texto por separado del modelo (no lo devuelve la Percepcion
    # ya agregada), pero si el crudo estructurado que si viaja.
    percepcion_cruda = [
        {
            "pagina": numero,
            "crudo": [item.model_dump() for item in percepcion.items] if numero == 1 else [],
        }
        for numero in range(1, percepcion.paginas + 1)
    ]

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
        return await trabajos.ver(app.state.motor, trabajo_id, incluir_kits=True)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
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

    if decision.decision == "devolver":
        trabajos.lanzar(app.state.motor, trabajo_id)
    return resultado


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
