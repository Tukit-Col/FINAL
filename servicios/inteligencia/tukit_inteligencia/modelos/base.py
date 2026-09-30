"""Base declarativa y vocabulario del servicio de Inteligencia.

Los enums de aqui son los del contrato, no una traduccion suya. Cuando el
contrato dice que `EstadoResolucion` tiene cuatro valores y que la diferencia
entre `SIN_MATCH` y `HUECO_CATALOGO` es la que permite decir "no tengo block
oficio" en vez de ofrecer origami, esa diferencia tiene que existir en la
columna o el contrato no la puede cumplir.
"""

from __future__ import annotations

import enum

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Mismo criterio que en Catalogo: nativo en Postgres, degradado en SQLite,
# para que el mismo modelo corra en la prueba y en el motor real.
Texto = JSON().with_variant(JSONB(), "postgresql")


class EstadoTrabajo(enum.StrEnum):
    """Los cinco estados del recurso central, tal como los fija el contrato.

    `ESPERA_REVISION` no es un estado tecnico sino de negocio: el flujo
    exige una pausa humana (AD-03, AD-04) antes de que el acudiente vea nada
    (AD-06). Una API sincronica no puede modelar una espera que incluye a una
    persona, y por eso el recurso es el trabajo y no el kit.
    """

    ENCOLADO = "encolado"
    PROCESANDO = "procesando"
    ESPERA_REVISION = "espera_revision"
    PUBLICADO = "publicado"
    FALLIDO = "fallido"


# Desde donde se puede llegar a cada estado. Vive como dato y no como una
# cadena de `if`, porque la pregunta que hay que poder responder rapido es
# "por que esta transicion es ilegal", y un diccionario la responde sola.
#
# Publicar dos veces no es idempotente sino un segundo aviso al acudiente, asi
# que `publicado` es terminal. `fallido` si se puede reintentar: el trabajo
# guarda su estado por etapas justo para no volver a pagar la percepcion.
TRANSICIONES: dict[EstadoTrabajo, frozenset[EstadoTrabajo]] = {
    EstadoTrabajo.ENCOLADO: frozenset({EstadoTrabajo.PROCESANDO, EstadoTrabajo.FALLIDO}),
    EstadoTrabajo.PROCESANDO: frozenset(
        {EstadoTrabajo.ESPERA_REVISION, EstadoTrabajo.FALLIDO, EstadoTrabajo.PUBLICADO}
    ),
    # Devolver un trabajo en revision lo REENCOLA (ADR 0024): el trabajador
    # durable lo retoma, en vez de que el API arranque la corrutina. PROCESANDO
    # se conserva por si un flujo lo mueve directo (no lo hace hoy).
    EstadoTrabajo.ESPERA_REVISION: frozenset(
        {EstadoTrabajo.PUBLICADO, EstadoTrabajo.PROCESANDO, EstadoTrabajo.ENCOLADO}
    ),
    EstadoTrabajo.PUBLICADO: frozenset(),
    EstadoTrabajo.FALLIDO: frozenset({EstadoTrabajo.ENCOLADO}),
}


class EstadoEtapa(enum.StrEnum):
    """Como le fue a una etapa.

    `DEGRADADA` existe aparte de `OK` y de `FALLIDA` por la seccion 8 del
    contrato: sin reranker el pipeline sigue y responde, pero la respuesta no
    es la misma y hay que decirlo. Colapsarla en `OK` esconde la degradacion,
    y colapsarla en `FALLIDA` tumba un trabajo que si tiene salida.
    """

    PENDIENTE = "pendiente"
    OK = "ok"
    DEGRADADA = "degradada"
    FALLIDA = "fallida"
    OMITIDA = "omitida"


class EstadoResolucion(enum.StrEnum):
    """Que le paso a un renglon contra el catalogo.

    `SIN_MATCH` es "no te entendi"; `HUECO_CATALOGO` es "te entendi y no lo
    tengo". Solo el segundo se puede responder con una alternativa o con una
    disculpa util, y por eso son dos valores y no uno.
    """

    RESUELTO_AUTO = "RESUELTO_AUTO"
    AMBIGUO = "AMBIGUO"
    SIN_MATCH = "SIN_MATCH"
    HUECO_CATALOGO = "HUECO_CATALOGO"


class PerfilKit(enum.StrEnum):
    """Los tres kits de OP-01 y UI-02.

    NO confundir con el `nivel` de un producto (`economico|confiable|premium`).
    Son ejes distintos que comparten la palabra "premium": el nivel describe
    un producto, el perfil describe una ponderacion de objetivos sobre el kit
    completo. Un kit Ahorrador puede llevar un producto premium si resulto mas
    barato por empaque.
    """

    AHORRADOR = "Ahorrador"
    FAN = "Fan"
    PREMIUM = "Premium"


# Los pesos por omision, medidos en la P21 de la encuesta y normalizados. No
# son un invento: 42 de 60 encuestados pagan como maximo 5 % mas, y el
# personaje quedo ultimo (1,87 contra 2,85 del precio).
PESOS_POR_OMISION: dict[str, float] = {
    "precio": 0.35,
    "marca_exigida": 0.30,
    "calidad": 0.25,
    "personaje": 0.10,
}
