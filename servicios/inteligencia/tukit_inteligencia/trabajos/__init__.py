"""El recurso `trabajo`: crear, procesar por etapas, consultar y revisar.

Aqui vive la maquina de estados que el contrato promete y la orquestacion de
las cuatro etapas. Lo que hay que entender de este modulo es que **el estado
no vive en el proceso**: cada transicion y cada etapa se escriben en la base
antes de seguir. La consecuencia practica es que reiniciar el servicio no
pierde los trabajos en vuelo, que `GET /v1/trabajos/{id}` puede responder
desde otro proceso, y que reanudar no vuelve a pagar la percepcion, que es la
etapa cara.

La ejecucion de fondo es DURABLE (ADR 0024): `lanzar` solo deja el trabajo
`encolado`, y `tukit_inteligencia.trabajador` lo drena con `SELECT … FOR UPDATE
SKIP LOCKED` —el mismo mecanismo del outbox—, lo mueve a `procesando` y corre
`procesar`. Una caida de proceso ya no pierde el trabajo: la fila sigue en la
base y otro worker (o el reinicio) la retoma. `procesar` es idempotente en el
claim (borra ITEM/KIT y reejecuta), asi que retomar no duplica.
"""

from __future__ import annotations

from ..remoto import RemotoCaido  # noqa: F401  (los routers lo leen como `trabajos.RemotoCaido`)
from ..repositorios.trabajos import TrabajoNoExiste, TransicionIlegal  # noqa: F401  (idem)
from .anclas import (
    _ANCLAS_AVISADAS,
    _TOPE_ANCLAS_AVISADAS,
    anclas_por_hijo,
)  # noqa: F401
from .base import (
    ANIO_LECTIVO_POR_OMISION,
    BANDEJA,
    CANDIDATO,
    ETAPA,
    IMPORTACION,
    ITEM,
    KIT,
    KIT_CANONICO,
    LINEA,
    ORIGEN_CANONICO,
    RESOLUCION,
    TRABAJO,
    TRANSICION,
    BorradorDesactualizado,
    CambioNoPermitido,
    CheckoutRechazado,
    KitsPublicadosNoEditables,
    NoCanonizable,
    PreviewNoPublicable,
    SinProductoQueValidar,
    SolicitudNoCancelable,
    TrabajoProtegido,
    _estado,
    _pasar_a,
    _publicar_evento,
    ahora,
    autopublicar,
    tau,
)  # noqa: F401
from .cambios import (
    aplicar_canonico,
    cambiar_producto_del_acudiente,
    descartar_linea_del_acudiente,
    opciones_de_la_linea,
    opciones_de_una_linea,
)  # noqa: F401
from .lectura import (
    dueno,
    ordenar,
    ver,
)  # noqa: F401
from .pipeline import (
    EventoRepetido,
    _finalizar,
    _listas_por_hijo,
    _tipo_del_concepto_manda,
    alguna_lista_para,
    crear,
    lanzar,
    procesar,
)  # noqa: F401
from .revision import (
    _fijar_canonico,
    decidir_linea,
    fijar_como_canonico,
    fijar_producto_en_linea,
    fijar_producto_en_todos_los_kits,
    revisar,
    version_canonica,
)  # noqa: F401
from .solicitudes import (
    cancelar_lista_subida,
    cancelar_solicitud,
    cola,
    eliminar,
    mis_solicitudes,
    previews_de,
)  # noqa: F401
from .versiones import (
    abrir_borrador,
    acudientes_de_colegio,
    grados_canonicos,
    mis_trabajos,
)  # noqa: F401

__all__ = [
    "ANIO_LECTIVO_POR_OMISION",
    "BANDEJA",
    "BorradorDesactualizado",
    "CANDIDATO",
    "CambioNoPermitido",
    "CheckoutRechazado",
    "ETAPA",
    "EventoRepetido",
    "IMPORTACION",
    "ITEM",
    "KIT",
    "KIT_CANONICO",
    "KitsPublicadosNoEditables",
    "LINEA",
    "NoCanonizable",
    "ORIGEN_CANONICO",
    "PreviewNoPublicable",
    "RESOLUCION",
    "SinProductoQueValidar",
    "SolicitudNoCancelable",
    "TRABAJO",
    "TRANSICION",
    "TrabajoProtegido",
    "_ANCLAS_AVISADAS",
    "_TOPE_ANCLAS_AVISADAS",
    "_estado",
    "_fijar_canonico",
    "_finalizar",
    "_listas_por_hijo",
    "_pasar_a",
    "_publicar_evento",
    "_tipo_del_concepto_manda",
    "abrir_borrador",
    "acudientes_de_colegio",
    "ahora",
    "alguna_lista_para",
    "anclas_por_hijo",
    "aplicar_canonico",
    "autopublicar",
    "cambiar_producto_del_acudiente",
    "cancelar_lista_subida",
    "cancelar_solicitud",
    "cola",
    "crear",
    "decidir_linea",
    "descartar_linea_del_acudiente",
    "dueno",
    "eliminar",
    "fijar_como_canonico",
    "fijar_producto_en_linea",
    "fijar_producto_en_todos_los_kits",
    "grados_canonicos",
    "lanzar",
    "mis_solicitudes",
    "mis_trabajos",
    "opciones_de_la_linea",
    "opciones_de_una_linea",
    "ordenar",
    "previews_de",
    "procesar",
    "revisar",
    "tau",
    "ver",
    "version_canonica",
]
