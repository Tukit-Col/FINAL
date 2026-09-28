"""Siembra los roles del sistema y unos usuarios de demostracion con clave.

Es la contraparte de `cargador.py` (que siembra colegios y sedes) para la capa
de acceso. Existe por una razon concreta: el modelo de autorizacion (ADR 0013)
dice que un rol es una FILA, no un valor de enumerado, asi que los roles del
sistema hay que sembrarlos en algun lado, y `cargador.py` no es ese lado -no
tiene por que saber de roles-.

Lo que siembra, todo idempotente (`ON CONFLICT DO UPDATE` / `DO NOTHING`):

- **Los cinco roles del sistema** (ADR 0008): `acudiente`, `colegio_admin`,
  `colegio_docente`, `operador`, `admin`. Van marcados `del_sistema=True`.
- **Un puñado de permisos** y su union rol-permiso. Es el minimo para que
  `puede()` responda algo distinto de "todo denegado"; no pretende ser el
  catalogo completo de permisos, que crece con cada servicio.
- **Usuarios de demostracion CON credencial** (a diferencia del contacto sin
  clave que crea `registrar_contacto`). Son los que el frontend en modo `api`
  usa para entrar y ver el enrutado por rol. La clave por omision es
  `demo1234` y se dice aqui y en pantalla: no es un secreto, es un banco de
  pruebas. Sus ambitos apuntan a un colegio REAL derivado por `derivar`, el
  mismo UUID que `cargador.py` siembra para ese codigo.

    python -m tukit_identidad.sembrar_acceso
    python -m tukit_identidad.sembrar_acceso --clave otra
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from tukit_comun import derivar

from .dominio.sesiones import hashear_clave
from .modelos import AmbitoTipo, Base, Clasificacion

# El colegio del piloto, para anclar el ambito del acudiente y del colegio en
# algo que `cargador.py` tambien siembra (mismo UUID, derivado del codigo).
COLEGIO_PILOTO = "2.13"

CLAVE_DEMO = "demo1234"

ROLES: list[dict[str, object]] = [
    {
        "codigo": "acudiente",
        "nombre": "Acudiente",
        "descripcion": "Arma la lista de sus hijos.",
        "del_sistema": True,
    },
    {
        "codigo": "colegio_admin",
        "nombre": "Administrador de colegio",
        "descripcion": "Publica la lista oficial y ve el panel institucional.",
        "del_sistema": True,
    },
    {
        "codigo": "colegio_docente",
        "nombre": "Docente",
        "descripcion": "Consulta institucional del colegio.",
        "del_sistema": True,
    },
    {
        "codigo": "operador",
        "nombre": "Operador Tukit",
        "descripcion": "Revisa la cola y valida lineas.",
        "del_sistema": True,
    },
    {
        "codigo": "admin",
        "nombre": "Administrador Tukit",
        "descripcion": "Superset del equipo interno.",
        "del_sistema": True,
    },
]

# Permisos minimos: `recurso:accion`. La clasificacion por omision es interno;
# lo que toca dato de menor se marca aparte, para no colar seguridad de campo
# por la puerta de atras.
PERMISOS: list[dict[str, object]] = [
    {
        "codigo": "trabajo:crear",
        "recurso": "trabajo",
        "accion": "crear",
        "campo": None,
        "clasificacion_minima": Clasificacion.PERSONAL.value,
    },
    {
        "codigo": "trabajo:leer",
        "recurso": "trabajo",
        "accion": "leer",
        "campo": None,
        "clasificacion_minima": Clasificacion.PERSONAL.value,
    },
    {
        "codigo": "cola:leer",
        "recurso": "cola",
        "accion": "leer",
        "campo": None,
        "clasificacion_minima": Clasificacion.INTERNO.value,
    },
    {
        "codigo": "linea:validar",
        "recurso": "linea",
        "accion": "validar",
        "campo": None,
        "clasificacion_minima": Clasificacion.INTERNO.value,
    },
    {
        "codigo": "lista:publicar",
        "recurso": "lista",
        "accion": "publicar",
        "campo": None,
        "clasificacion_minima": Clasificacion.INTERNO.value,
    },
    {
        "codigo": "estudiante:leer:apodo",
        "recurso": "estudiante",
        "accion": "leer",
        "campo": "apodo",
        "clasificacion_minima": Clasificacion.MENOR.value,
    },
    {
        "codigo": "usuario:leer:nombre",
        "recurso": "usuario",
        "accion": "leer",
        "campo": "nombre",
        # PERSONAL, no MENOR: es el nombre del acudiente adulto. La
        # clasificacion mide sensibilidad del dato, no quien lo ve.
        "clasificacion_minima": Clasificacion.PERSONAL.value,
    },
]

ROL_PERMISO: list[tuple[str, str]] = [
    ("acudiente", "trabajo:crear"),
    ("acudiente", "trabajo:leer"),
    ("colegio_admin", "lista:publicar"),
    ("colegio_docente", "lista:publicar"),
    ("operador", "cola:leer"),
    ("operador", "linea:validar"),
    ("admin", "cola:leer"),
    ("admin", "linea:validar"),
    ("admin", "lista:publicar"),
    ("admin", "trabajo:leer"),
    ("acudiente", "estudiante:leer:apodo"),
    ("admin", "usuario:leer:nombre"),
    ("operador", "usuario:leer:nombre"),
]


def _colegio_piloto_id() -> uuid.UUID:
    return derivar("colegio", COLEGIO_PILOTO)


def usuarios_demo(clave: str) -> list[dict[str, object]]:
    """Filas de usuario + su asignacion de rol. El UUID del usuario se deriva
    del correo, para que sembrar dos veces no cree dos cuentas."""
    piloto = _colegio_piloto_id()
    plan = [
        ("mama@ejemplo.com", "acudiente", AmbitoTipo.COLEGIO, piloto),
        ("papa@ejemplo.com", "acudiente", AmbitoTipo.COLEGIO, piloto),
        ("rectoria@colegio.edu.co", "colegio_admin", AmbitoTipo.COLEGIO, piloto),
        ("docente@colegio.edu.co", "colegio_docente", AmbitoTipo.COLEGIO, piloto),
        ("operador@tukit.co", "operador", AmbitoTipo.GLOBAL, None),
        ("admin@tukit.co", "admin", AmbitoTipo.GLOBAL, None),
    ]
    filas = []
    for correo, rol, tipo, ambito_id in plan:
        usuario_id = derivar("usuario", correo)
        filas.append(
            {
                "usuario": {
                    "id": usuario_id,
                    "correo": correo,
                    "clave_hash": hashear_clave(clave),
                    "activo": True,
                },
                "asignacion": {
                    "id": derivar("asignacion", correo, rol),
                    "usuario_id": usuario_id,
                    "rol_codigo": rol,
                    "ambito_tipo": tipo.value,
                    "ambito_id": ambito_id,
                },
            }
        )
    return filas


async def sembrar(clave: str) -> dict[str, int]:
    from sqlalchemy.dialects.postgresql import insert
    from tukit_comun.bd import crear_motor

    rol = Base.metadata.tables["rol"]
    permiso = Base.metadata.tables["permiso"]
    rol_permiso = Base.metadata.tables["rol_permiso"]
    usuario = Base.metadata.tables["usuario"]
    asignacion = Base.metadata.tables["asignacion_rol"]

    demo = usuarios_demo(clave)
    escritos: dict[str, int] = {}
    motor = crear_motor("identidad")
    try:
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                insert(rol)
                .values(ROLES)
                .on_conflict_do_update(
                    index_elements=["codigo"],
                    set_={
                        "nombre": insert(rol).excluded.nombre,
                        "descripcion": insert(rol).excluded.descripcion,
                    },
                )
            )
            escritos["rol"] = len(ROLES)

            await conexion.execute(
                insert(permiso).values(PERMISOS).on_conflict_do_nothing(index_elements=["codigo"])
            )
            escritos["permiso"] = len(PERMISOS)

            await conexion.execute(
                insert(rol_permiso)
                .values([{"rol_codigo": r, "permiso_codigo": p} for r, p in ROL_PERMISO])
                .on_conflict_do_nothing()
            )
            escritos["rol_permiso"] = len(ROL_PERMISO)

            # La clave cambia en cada corrida (la sal es aleatoria), asi que el
            # upsert actualiza el hash: reejecutar re-siembra la misma cuenta
            # con una clave fresca, no crea una segunda.
            await conexion.execute(
                insert(usuario)
                .values([d["usuario"] for d in demo])
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "clave_hash": insert(usuario).excluded.clave_hash,
                        "activo": insert(usuario).excluded.activo,
                    },
                )
            )
            escritos["usuario"] = len(demo)

            await conexion.execute(
                insert(asignacion)
                .values([d["asignacion"] for d in demo])
                .on_conflict_do_nothing(index_elements=["id"])
            )
            escritos["asignacion_rol"] = len(demo)
    finally:
        await motor.cerrar()
    return escritos


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--clave", default=CLAVE_DEMO, help="Clave de los usuarios de demostracion.")
    args = analizador.parse_args(argv)

    escritos = asyncio.run(sembrar(args.clave))
    print("\n=== acceso sembrado ===")
    for tabla, n in escritos.items():
        print(f"  {tabla:20} {n:4}")
    print(f"\nUsuarios de demostracion con clave `{args.clave}`. No es un secreto: es un banco de pruebas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
