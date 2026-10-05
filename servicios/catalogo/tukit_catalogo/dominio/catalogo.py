"""La forma publica de la lectura del catalogo, como dato puro.

Estas funciones convierten una `fila` de la base en el dict que el frontend
pinta, ordenan las ofertas, arman el sobre paginado y validan una edicion. No
tocan la base ni la peticion: reciben datos planos y devuelven datos planos (o
levantan `ErrorDominio`, que es la unica dependencia de `tukit_comun`). El SQL
que produce esas filas vive en `repositorios/catalogo.py` (ADR 0019).

El dinero sale en pesos enteros, no en los centavos en que se guarda: lo fija la
seccion 1.4 del contrato y la conversion se hace aqui una sola vez.
"""

from __future__ import annotations

from typing import Any

from tukit_comun.http import ErrorDominio

# El orden con el que el acudiente compara y el que el catalogo acepta editar.
_ORDEN_NIVEL = ("economico", "confiable", "premium")

# Los campos que una persona puede tocar por PATCH. El concepto NO esta: se
# reasigna por su propia ruta (`/reclasificar`) porque arrastra la invalidacion
# del vector y no es una edicion de texto mas. `sku`, `id`, `curado_*` y
# `embedding*` no se listan porque no se editan: cambiarlos rompe la identidad
# del producto o la huella del canal semantico.
_CAMPOS_EDITABLES = frozenset(
    {
        "nombre",
        "descripcion",
        "marca",
        "nivel",
        "personaje",
        "imagen_url",
        "unidad_base",
        "unidades_por_empaque",
        "atributos",
        "quality_score",
        "es_propio",
    }
)

_UNIDADES_BASE = ("unidad", "hoja", "pliego", "metro", "gramo", "mililitro")

# Cambiar uno de estos cambia el texto del que sale el embedding, asi que hay
# que invalidar `texto_embedding` para que `enriquecer` lo recalcule. El resto
# (marca, precio, imagen) no alimenta el vector y no gasta una re-embebida.
_CAMPOS_QUE_REEMBEBEN = frozenset({"nombre", "atributos"})


def pesos(centavos: int | None) -> int | None:
    """Centavos a pesos enteros. `None` es "no se conoce", no cero.

    La distincion es del contrato y no es cosmetica: un producto sin precio
    observado no se puede sumar a un total, y un cero lo sumaria sin ruido.
    """
    return None if centavos is None else int(centavos) // 100


def _sobre(pagina: int, por_pagina: int, total: int, clave: str, filas: list[Any]) -> dict[str, Any]:
    """El mismo sobre para toda coleccion.

    Que las cuatro colecciones se paginen igual es lo que permite que el
    frontend escriba el componente de paginacion una vez. `total` va siempre,
    tambien cuando cabe en una pagina, porque "cuantos hay" es la pregunta que
    decide si se pinta el paginador.
    """
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, clave: filas}


def _concepto_publico(fila: Any) -> dict[str, Any]:
    return {
        "codigo": fila.codigo,
        "nombre": fila.nombre_canonico,
        "categoria": fila.categoria,
        "tipo_item": fila.tipo_item,
        "sinonimos": list(fila.sinonimos or ()),
        "admite_personaje": bool(fila.admite_personaje),
        # Los dos papeles del atributo, separados tambien en la respuesta. El
        # discriminante filtra y el descriptivo solo cuenta que estas
        # comprando; el frontend los pinta distinto porque son cosas distintas.
        "atributos_discriminantes": list(fila.atributos_discriminantes or ()),
        "atributos_descriptivos": list(fila.atributos_descriptivos or ()),
        "frecuencia_demanda": int(fila.frecuencia_demanda or 0),
    }


def _producto_publico(fila: Any) -> dict[str, Any]:
    return {
        # `sku` y no `sku_interno`: hacia afuera el identificador del producto
        # se llama igual en el catalogo y en el `ProductoKit` de la seccion 5,
        # que es lo que permite que una tarjeta de catalogo y una linea de kit
        # compartan componente. El nombre interno se queda en la base.
        "sku": fila.sku_interno,
        # El EAN no es un adorno: es lo unico que permite reconocer el mismo
        # producto en dos tiendas que lo nombran distinto, y la pantalla de
        # comparacion se apoya en eso. Es nulo cuando la fuente no lo publica.
        "ean": fila.ean,
        "nombre": fila.nombre,
        "marca": fila.marca,
        "nivel": fila.nivel,
        "personaje": fila.personaje,
        "imagen_url": fila.imagen_url,
        "descripcion": fila.descripcion,
        # Marca propia de Tukit. Cambia como se lee el precio -no hay una
        # tienda tercera detras- asi que la pantalla lo etiqueta aparte.
        "es_propio": bool(fila.es_propio),
        # Las dos columnas de las que depende no sumar doce cajas cuando la
        # lista pidio doce lapices. Van en la respuesta porque el frontend
        # tiene que poder decir "una caja de 12" y no "12".
        "unidad_base": fila.unidad_base,
        "unidades_por_empaque": int(fila.unidades_por_empaque or 1),
        "atributos": dict(fila.atributos or {}),
        "quality_score": float(fila.quality_score),
        "concepto": {"codigo": fila.concepto_codigo, "nombre": fila.concepto_nombre},
        "precio_desde": pesos(getattr(fila, "centavos", None)),
        "tiendas": int(getattr(fila, "tiendas", 0) or 0),
    }


def _oferta_publica(fila: Any) -> dict[str, Any]:
    return {
        "tienda": fila.slug,
        "tienda_nombre": fila.tienda_nombre,
        "tipo_tienda": fila.tipo,
        "url": fila.url,
        # Tres valores y no dos: `null` es "la fuente no reporta
        # existencias", que no es lo mismo que "no hay". El canal
        # mayorista nunca las reporta, y forzar `false` descartaria
        # ofertas legitimas por una observacion que nunca se hizo.
        "disponible": fila.disponible,
        "precio": pesos(fila.valor_centavos),
        "vigente_desde": fila.vigente_desde.isoformat() if fila.vigente_desde else None,
        "vigente_hasta": fila.vigente_hasta.isoformat() if fila.vigente_hasta else None,
        # El instante en que se observo el precio que se esta mostrando. La
        # pantalla lo necesita para poder decir "visto el 12/09" en vez de
        # presentar un precio de hace tres meses como si fuera de hoy.
        "visto_en": fila.vigente_desde.isoformat() if fila.vigente_desde else None,
        "fuente_precio": fila.fuente,
        "metodo_vinculacion": fila.metodo_vinculacion,
        "confianza_vinculacion": float(fila.confianza_vinculacion),
    }


def _ordenar_ofertas(ofertas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Las que tienen precio primero y de menor a mayor; las que no, al final.

    Una oferta sin precio no se puede comparar, pero tampoco se esconde:
    existe y el acudiente puede ir a mirarla.
    """
    return sorted(ofertas, key=lambda o: (o["precio"] is None, o["precio"] or 0))


def _validar_edicion(cambios: dict[str, Any]) -> None:
    """Los mismos CHECK del modelo, dichos en el borde como error de dominio.

    Se rechaza antes de que la base lo grite para que el mensaje nombre el campo
    y el SPA lo pinte donde toca. Un cuerpo con una clave que no se edita es un
    400 que la nombra: es un error del cliente, no un dato que se ignora en
    silencio (ignorarlo dejaria creer que se guardo).
    """
    for campo in cambios:
        if campo not in _CAMPOS_EDITABLES:
            raise ErrorDominio(
                "campo_no_editable",
                f"El campo {campo} no se edita por esta ruta.",
                campo=campo,
            )
    if "nivel" in cambios and cambios["nivel"] not in _ORDEN_NIVEL:
        raise ErrorDominio(
            "nivel_invalido", f"El nivel debe ser uno de {', '.join(_ORDEN_NIVEL)}.", campo="nivel"
        )
    if "unidad_base" in cambios and cambios["unidad_base"] not in _UNIDADES_BASE:
        raise ErrorDominio(
            "unidad_base_invalida",
            f"La unidad base debe ser una de {', '.join(_UNIDADES_BASE)}.",
            campo="unidad_base",
        )
    if "unidades_por_empaque" in cambios and int(cambios["unidades_por_empaque"]) < 1:
        raise ErrorDominio(
            "empaque_invalido",
            "Las unidades por empaque tienen que ser al menos 1.",
            campo="unidades_por_empaque",
        )
    if "quality_score" in cambios and not (0 <= float(cambios["quality_score"]) <= 1):
        raise ErrorDominio(
            "quality_score_invalido", "El quality_score va entre 0 y 1.", campo="quality_score"
        )
    if "atributos" in cambios:
        # Los atributos son un mapa de valores ESCALARES (str/int/float/bool o
        # null): el tipo lo fija el cliente y el backend solo lo endurece. Una
        # lista o un dict anidado es basura que no se persiste; se nombra la
        # clave ofensora. bool es subclase de int en Python: ambos valen.
        for clave, valor in (cambios["atributos"] or {}).items():
            if valor is not None and not isinstance(valor, (str, int, float)):
                raise ErrorDominio(
                    "atributos_invalido",
                    f"El atributo '{clave}' debe ser un valor simple.",
                    estado=422,
                    campo="atributos",
                )
