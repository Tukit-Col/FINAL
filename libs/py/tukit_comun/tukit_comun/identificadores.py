"""Identificadores derivados del contenido, iguales en los cinco servicios.

Existe por una necesidad que aparece en cuanto hay mas de una base: dos
servicios tienen que poder referirse a la MISMA entidad sin poder verse. El
colegio `2.4` vive en Identidad y su lista oficial vive en Catalogo, y la
referencia entre las dos es logica, no una llave foranea (ver el manifiesto).
Si cada cargador inventara un UUID aleatorio, la referencia apuntaria a nada
y nada se quejaria: la funcion de aptitud comprueba que la referencia este
DECLARADA, no que resuelva.

La salida es la que ya usaba `tukit_catalogo.cargador._uuid_estable`, letra
por letra, para que el catalogo que hoy esta en la base siga siendo el mismo
despues de mover la funcion aqui. Cambiar el prefijo o el espacio de nombres
no es un refactor: reescribe todas las llaves primarias del catalogo curado.

    derivar("colegio", "2.4")      # el mismo UUID desde Identidad y Catalogo
    derivar("lista", "2.4", "Cuarto", "2026")

Tambien es lo que hace idempotente a un cargador. Con UUID aleatorio, correr
la siembra dos veces duplica todo; con uno derivado de la llave natural, la
segunda corrida actualiza las mismas filas.
"""

from __future__ import annotations

import uuid

# `NAMESPACE_URL` y el prefijo `tukit:` no son una eleccion estetica: son parte
# de la llave primaria de cada fila ya sembrada. Se dejan como constantes con
# nombre para que quede claro que tocarlas es una migracion de datos.
ESPACIO = uuid.NAMESPACE_URL
PREFIJO = "tukit:"


def derivar(*partes: str) -> uuid.UUID:
    """UUID version 5 de la llave natural, estable entre corridas y servicios."""
    return uuid.uuid5(ESPACIO, PREFIJO + ":".join(str(p) for p in partes))
