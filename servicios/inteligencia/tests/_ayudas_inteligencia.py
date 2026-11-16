"""Dobles y sembradores que comparten varios archivos de prueba de Inteligencia.

Antes vivian dentro de un archivo de prueba y los demas los importaban de ahi
(`from test_fastroute import ...`), lo que ataba cada archivo a la forma de
otro. Aqui solo hay ayudas: ninguna prueba.

- `CatalogoVerificado` y sus variantes: el catalogo con la lista ya revisada y
  el endpoint `/resueltos` (la ruta rapida).
- `catalogo_simple()`: la lista de cuatro renglones de la ruta lenta.
- Sembradores de la bandeja del Catalogo, de trabajos y de previews.
- Los dobles de una base que se cae y vuelve, para los bucles de fondo.
- `candidato` y `renglon_optimizador`: las piezas de entrada del optimizador.
"""

from __future__ import annotations

import socket
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from conftest import COLEGIO, CatalogoFalso, opcion, reconocido, renglon
from sqlalchemy import MetaData, insert, select
from tukit_comun.bandeja import bandeja_reflejada
from tukit_comun.texto import normalizar_personaje
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import Base, EstadoTrabajo
from tukit_inteligencia.optimizador import Candidato, Renglon
from tukit_inteligencia.remoto import RemotoCaido

TRABAJO = Base.metadata.tables["trabajo_pipeline"]
# El colegio de las pruebas de "Mis solicitudes" y de cancelar: otro que el de
# `conftest`, para que una fila sembrada aqui no se confunda con las de alla.
COLEGIO_SOLICITUDES = "22222222-2222-5222-8222-222222222222"
VERSION_VIGENTE = "ver-vigente-1"
# Dos acudientes reales (UUID validos): el token resuelve a uno de ellos.
PADRE = uuid.UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")
OTRO_PADRE = uuid.UUID("bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")


def candidato_dict(sku: str, nivel: str, precio: int | None, **kw: Any) -> dict[str, Any]:
    base = opcion(sku, nivel, precio, **kw)
    base["producto_id"] = kw.get("producto_id") or str(uuid.uuid4())
    return base


def item_resuelto(
    orden: int,
    texto: str,
    concepto_codigo: str | None,
    candidatos: list[dict[str, Any]],
    **kw: Any,
) -> dict[str, Any]:
    return {
        "item_id": str(uuid.uuid4()),
        "orden": orden,
        "texto_original": texto,
        "cantidad": kw.get("cantidad", 1),
        "tipo_item": kw.get("tipo_item", "util"),
        "modo_adquisicion": kw.get("modo_adquisicion", "mercado_abierto"),
        "concepto_codigo": concepto_codigo,
        "concepto_nombre": kw.get("concepto_nombre", (concepto_codigo or "").lower()),
        "instruccion_colegio": kw.get("instruccion_colegio"),
        "url_externa": kw.get("url_externa"),
        "candidatos": candidatos,
        "atributos_impuestos": kw.get("atributos_impuestos", {}),
        "atributos_por_revisar": kw.get("atributos_por_revisar", []),
        "uno_por_estudiante": kw.get("uno_por_estudiante", False),
        "posible_repetido_de": kw.get("posible_repetido_de"),
    }


@dataclass
class CatalogoVerificado(CatalogoFalso):
    """Catalogo con la lista marcada como revisada y el endpoint /resueltos."""

    revisada: bool = True
    items_resueltos: list[dict[str, Any]] = field(default_factory=list)

    async def listas(self, *, colegio_id: str, grado: str, anio_lectivo: int | None = None) -> list[dict]:
        self.llamadas.append("listas")
        if grado != self.grado:
            return []
        return [
            {
                "lista_id": "lista-1",
                "version_id": "ver-1",
                "grado": grado,
                "anio_lectivo": anio_lectivo or 2026,
                "revisada": self.revisada,
            }
        ]

    async def lista(self, lista_id: str) -> dict[str, Any]:
        self.llamadas.append("lista")
        return {
            "lista_id": lista_id,
            "version_id": "ver-1",
            "grado": self.grado,
            "revisada": self.revisada,
            "total_items": len(self.items_resueltos or self.renglones),
            "items": self.renglones,
        }

    async def revision(self, version_id: str) -> dict[str, Any]:
        # Misma forma que `lista()` pero por `version_id` explicito: es el camino
        # que toma el pipeline cuando el poller estampa el `version_id` del evento
        # en el hijo (para unir la lista aprobada con su trabajo en "Mis
        # solicitudes"). El fake devuelve la version pedida, revisada, con items.
        self.llamadas.append("revision")
        return {
            "lista_id": "lista-1",
            "version_id": version_id,
            "grado": self.grado,
            "revisada": self.revisada,
            "total_items": len(self.items_resueltos or self.renglones),
            "items": self.renglones,
        }

    async def resueltos(self, version_id: str) -> dict[str, Any]:
        self.llamadas.append("resueltos")
        return {
            "version_id": version_id,
            "revisada": True,
            "colegio_id": COLEGIO,
            "grado": self.grado,
            "anio_lectivo": 2026,
            "items": self.items_resueltos,
        }


def catalogo_verificado(personaje: str | None = None) -> CatalogoVerificado:
    p = personaje
    return CatalogoVerificado(
        revisada=True,
        items_resueltos=[
            item_resuelto(
                1,
                "cuaderno cuadriculado",
                "C001",
                [
                    candidato_dict("TK-C001-ECO", "economico", 4500),
                    candidato_dict("TK-C001-FAN", "confiable", 6000, personaje=p),
                ],
                cantidad=2,
            ),
            item_resuelto(
                2,
                "cartuchera",
                "C009",
                [
                    candidato_dict("TK-C009-ECO", "economico", 8000),
                    candidato_dict("TK-C009-FAN", "confiable", 15000, personaje=p),
                ],
            ),
            item_resuelto(
                3,
                "caja de colores",
                "C004",
                [candidato_dict("TK-C004-CON", "confiable", 24900)],
            ),
            item_resuelto(
                4,
                "Plan lector RAZ",
                None,
                [],
                tipo_item="licencia_digital",
                modo_adquisicion="plataforma",
                instruccion_colegio="Se adquiere con QUOVIX.",
            ),
        ],
    )


async def crear_y_procesar(motor, catalogo=None, preferencias=None):
    """Un trabajo de un hijo, creado y procesado; por omision con `catalogo_simple()`."""
    catalogo = catalogo or catalogo_simple()
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias=preferencias or {},
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    estado = await trabajos.procesar(motor, trabajo_id, catalogo=catalogo)
    return trabajo_id, estado


@dataclass
class CatalogoRealista(CatalogoVerificado):
    """Modela el catalogo REAL: /resueltos NO trae la variante de personaje.

    El bug que esto defiende: `_elegir_por_nivel` del catalogo colapsa a una
    opcion por nivel y deja fuera la de personaje (es una via aparte, curada),
    asi que `/resueltos` nunca la entrega. El interruptor del Fan la pide por
    separado con `producto_de_personaje`. La fixture vieja horneaba el personaje
    dentro de los candidatos de /resueltos —ficcion que el catalogo real no
    produce— y por eso el bug pasaba verde.
    """

    async def producto_de_personaje(self, concepto: str, personaje: str) -> dict[str, Any] | None:
        self.llamadas.append("producto_de_personaje")
        # El catalogo real compara normalizado ("Spider-Man" == "spiderman").
        if normalizar_personaje(personaje) != "spiderman":
            return None
        # El catalogo surte las cuatro anclas con spiderman (precio_desde, como
        # el endpoint publico de productos). La maleta (C086) no esta en la lista
        # de esta prueba, asi que solo C001/C009 caen en anclas presentes.
        return {
            "sku": f"SPIDEY-{concepto}",
            "nombre": f"{concepto} Spiderman",
            "marca": "Marvel",
            "nivel": "confiable",
            "personaje": "spiderman",
            "precio_desde": 20000,
            "unidades_por_empaque": 1,
        }


def catalogo_realista() -> CatalogoRealista:
    # Mismos items que catalogo_verificado pero SIN personaje en /resueltos:
    # es lo que el catalogo real entrega tras _elegir_por_nivel.
    base = catalogo_verificado(personaje=None)
    return CatalogoRealista(revisada=True, items_resueltos=base.items_resueltos)


@dataclass
class CatalogoDosPersonajes(CatalogoRealista):
    """Surte spiderman y frozen en las cuatro anclas; el resto no lo surte."""

    async def producto_de_personaje(self, concepto: str, personaje: str) -> dict[str, Any] | None:
        self.llamadas.append("producto_de_personaje")
        if personaje.lower() not in {"spiderman", "frozen"}:
            return None
        return {
            "sku": f"{personaje.upper()}-{concepto}",
            "nombre": f"{concepto} {personaje}",
            "nivel": "confiable",
            "personaje": personaje.lower(),
            "precio_desde": 20000,
            "unidades_por_empaque": 1,
        }


def catalogo_simple() -> CatalogoFalso:
    return CatalogoFalso(
        renglones=[
            renglon(1, "2 cuadernos cuadriculados", cantidad=2),
            renglon(2, "caja de colores x12"),
            renglon(
                3,
                "Plan lector virtual RAZ-PLUS",
                tipo_item="licencia_digital",
                modo_adquisicion="plataforma",
                instruccion_colegio="Se adquiere con QUOVIX.",
            ),
            renglon(4, "punzon punta metalica de titanio"),
        ],
        respuestas={
            "2 cuadernos cuadriculados": reconocido(
                "2 cuadernos cuadriculados",
                "C001",
                [
                    opcion("TK-C001-ECO", "economico", 4500),
                    opcion("TK-C001-PRE", "premium", 12000),
                ],
            ),
            "caja de colores x12": reconocido(
                "caja de colores x12",
                "C004",
                [opcion("TK-C004-CON", "confiable", 24900, unidades_por_empaque=12)],
            ),
        },
    )


async def sembrar_canonico(motor, catalogo=None):
    """El kit canonico del grado como nace en produccion: de la LISTA aprobada
    (`canonico_lista`, sin acudiente ni preferencias), no del trabajo de un papa."""
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "canonico", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
        origen=trabajos.ORIGEN_CANONICO,
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    estado = await trabajos.procesar(motor, trabajo_id, catalogo=catalogo or catalogo_simple())
    assert estado == EstadoTrabajo.PUBLICADO.value
    return trabajo_id


def linea_del_kit(vista: dict, perfil: str, inicio: str) -> dict:
    kit = next(k for k in vista["kits"] if k["perfil"] == perfil)
    return next(linea for linea in kit["lineas"] if linea["descripcion"].startswith(inicio))


def total_del_kit(vista: dict, perfil: str) -> int:
    return next(k for k in vista["kits"] if k["perfil"] == perfil)["total"]


# La bandeja del Catalogo, aqui montada sobre el MISMO SQLite de prueba: tiene
# la forma comun de bandeja (identica en todos los servicios), asi que la tabla
# reflejada del poller la lee igual que en produccion.
BANDEJA_CATALOGO = bandeja_reflejada(MetaData())


async def sembrar_bandeja(motor, *, agregado_id: uuid.UUID | None = None, **carga: Any) -> uuid.UUID:
    """Crea la tabla de bandeja del catalogo en el SQLite de prueba y le mete
    un evento `lista_verificada` con la carga dada. Devuelve el `agregado_id`
    (el `version_id` de la version aprobada) para poder aseverarlo."""
    agregado_id = agregado_id or uuid.uuid4()
    async with motor.engine.begin() as conexion:
        await conexion.run_sync(BANDEJA_CATALOGO.metadata.create_all)
        await conexion.execute(
            insert(BANDEJA_CATALOGO).values(
                tipo="lista_verificada",
                agregado_tipo="version_lista_oficial",
                agregado_id=agregado_id,
                carga=carga,
                intentos=0,
            )
        )
    return agregado_id


def carga_lista_verificada(
    contacto: str, preferencias: dict | None = None, referencias: list[str] | None = None
) -> dict[str, Any]:
    carga: dict[str, Any] = {
        "contacto_referencia": contacto,
        "colegio_id": COLEGIO,
        "grado": "Cuarto",
        "anio_lectivo": 2026,
        "preferencias": preferencias,
    }
    if referencias is not None:
        carga["referencias"] = referencias
    return carga


async def encolar(motor) -> uuid.UUID:
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
    )
    return uuid.UUID(respuesta["trabajo_id"])


GRADO = "Cuarto"


async def sembrar_preview(motor, version_id: uuid.UUID) -> uuid.UUID:
    """Un preview de onboarding ya procesado, en `espera_revision`."""
    creado = await trabajos.crear(
        motor,
        hijos=[
            {
                "referencia": "preview",
                "colegio_id": COLEGIO,
                "grado": GRADO,
                "anio_lectivo": 2026,
                "version_id": str(version_id),
            }
        ],
        contacto=None,
        preferencias={},
        origen="preview_onboarding",
    )
    trabajo_id = uuid.UUID(creado["trabajo_id"])
    estado = await trabajos.procesar(motor, trabajo_id, catalogo=catalogo_verificado())
    assert estado == EstadoTrabajo.ESPERA_REVISION.value
    return trabajo_id


async def puntero_canonico(motor) -> Any:
    async with motor.engine.begin() as conexion:
        return (
            await conexion.execute(
                select(trabajos.KIT_CANONICO.c.trabajo_id).where(
                    trabajos.KIT_CANONICO.c.colegio_id == COLEGIO,
                    trabajos.KIT_CANONICO.c.grado == GRADO,
                )
            )
        ).scalar_one_or_none()


class CatalogoPreview(CatalogoFalso):
    """CatalogoFalso que resuelve versiones por id con `revision()`.

    `self.versiones` es el conjunto de version_id que EXISTEN para
    (COLEGIO, self.grado, 2026); `revision(vid)` devuelve la cabecera + items de
    una de ellas, o levanta `RemotoCaido` (que el endpoint traduce a 404) si no
    existe —igual que el catalogo real, que resuelve `/revision` por version_id
    sin importar si es la vigente—. Registra las llamadas en `self.llamadas`.
    """

    def __init__(self, *, version_vigente: str | None = VERSION_VIGENTE, versiones=None, **kw):
        super().__init__(**kw)
        if versiones is None:
            versiones = [] if version_vigente is None else [version_vigente]
        self.versiones = list(versiones)

    async def revision(self, version_id: str) -> dict:
        self.llamadas.append("revision")
        if version_id not in self.versiones:
            raise RemotoCaido("catalogo", "/revision respondio 404")
        return {
            "version_id": version_id,
            "lista_id": "lista-1",
            "colegio_id": COLEGIO,
            "grado": self.grado,
            "anio_lectivo": 2026,
            "revisada": False,
            "total_items": len(self.renglones),
            "items": self.renglones,
        }


@dataclass
class IdentidadFalsa:
    """Doble del puerto hacia identidad: token→usuario_id (UUID). Un token
    ausente vale como inválido (`None` => 401); `caida=True` lanza `RemotoCaido`
    para probar el fallo cerrado (503)."""

    usuario_por_token: dict[str, uuid.UUID] = field(default_factory=dict)
    caida: bool = False

    async def sesion(self, token: str) -> dict[str, Any] | None:
        if self.caida:
            raise RemotoCaido("identidad", "simulada")
        if token not in self.usuario_por_token:
            return None
        return {
            "usuario_id": str(self.usuario_por_token[token]),
            "correo": f"{token}@tukit.co",
            "nombre": token,
            "roles": [{"rol": "acudiente", "ambito": None}],
            "version_permisos": 1,
        }


async def sembrar_trabajo(
    motor,
    *,
    usuario_id: uuid.UUID,
    estado: str = EstadoTrabajo.PUBLICADO.value,
    origen: str = "colegio_grado",
    hijos: list[dict[str, Any]],
    creado_en: datetime | None = None,
) -> uuid.UUID:
    trabajo_id = uuid.uuid4()
    error = "prueba" if estado == EstadoTrabajo.FALLIDO.value else None
    valores: dict[str, Any] = {
        "id": trabajo_id,
        "usuario_id": usuario_id,
        "estado": estado,
        "origen": origen,
        "hijos": hijos,
        "error": error,
    }
    if creado_en is not None:
        valores["creado_en"] = creado_en
    async with motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(insert(TRABAJO).values(**valores))
    return trabajo_id


def lista_del_catalogo(
    *,
    version_id: str | None,
    revisada: bool,
    grado: str = "Quinto",
    colegio_nombre: str | None = None,
    creada_en: str,
) -> dict[str, Any]:
    return {
        "version_id": version_id,
        "colegio_id": COLEGIO_SOLICITUDES,
        "colegio_nombre": colegio_nombre,
        "grado": grado,
        "anio_lectivo": 2026,
        "revisada_en": creada_en if revisada else None,
        "creada_en": creada_en,
    }


INTERVALO_BUCLE = 5.0


class CorteDelBucle(Exception):
    """La lanza el `dormir` de la prueba para salir del bucle infinito."""


def caidas_de_postgres() -> list[BaseException]:
    return [
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        socket.gaierror(8, "nodename nor servname provided, or not known"),
    ]


class EngineIntermitente:
    """Un `AsyncEngine` cuya base no responde las primeras veces que se abre.

    Lanza los errores dados, en orden, al abrir una transaccion o una conexion,
    como asyncpg con Postgres caido; despues delega en el engine de verdad. No
    se cierra: la base en memoria de la prueba se perderia.
    """

    def __init__(self, real: Any, *errores: BaseException) -> None:
        self.real = real
        self.errores = list(errores)

    def _quizas_caer(self) -> None:
        if self.errores:
            raise self.errores.pop(0)

    @asynccontextmanager
    async def begin(self):
        self._quizas_caer()
        async with self.real.begin() as conexion:
            yield conexion

    @asynccontextmanager
    async def connect(self):
        self._quizas_caer()
        async with self.real.connect() as conexion:
            yield conexion

    async def dispose(self) -> None:
        pass

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


class MotorDePrueba:
    """El `MotorServicio` de la prueba, con el engine dado, que no se cierra."""

    def __init__(self, real: Any, engine: Any = None) -> None:
        self.real = real
        self.engine = engine if engine is not None else real.engine

    def sesion(self):
        return self.real.sesion()

    async def cerrar(self) -> None:
        pass


def dormir_que_corta(esperas: list[float]):
    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if segundos == INTERVALO_BUCLE:
            raise CorteDelBucle

    return dormir


def candidato(sku: str, nivel: str, precio: int | None, **kw) -> Candidato:
    return Candidato(sku=sku, nombre=f"Producto {sku}", nivel=nivel, precio_cop=precio, **kw)


def renglon_optimizador(orden: int, texto: str, candidatos: tuple[Candidato, ...] = (), **kw) -> Renglon:
    return Renglon(
        hijo=kw.pop("hijo", "hijo-1"),
        orden=orden,
        texto=texto,
        tipo_item=kw.pop("tipo_item", "util"),
        modo_adquisicion=kw.pop("modo_adquisicion", "mercado_abierto"),
        cantidad=kw.pop("cantidad", 1),
        estado_resolucion=kw.pop("estado_resolucion", "RESUELTO_AUTO"),
        candidatos=candidatos,
        **kw,
    )
