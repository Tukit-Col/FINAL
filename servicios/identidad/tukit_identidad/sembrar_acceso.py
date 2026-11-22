from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime

from tukit_comun import derivar
from tukit_comun.cifrado import cifrador_desde_entorno

from .dominio.sesiones import hashear_clave
from .modelos import AmbitoTipo, Base, Clasificacion

COLEGIO_PILOTO = "2.13"
SEDE_PILOTO = "Sede unica"
GRADO_DEMO = "Quinto"
APODO_DEMO = "Pipe"

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


def hijo_demo_de_mama() -> dict[str, dict[str, object]]:
    usuario_id = derivar("usuario", "mama@ejemplo.com")
    colegio_id = derivar("colegio", COLEGIO_PILOTO)
    sede_id = derivar("sede", COLEGIO_PILOTO, SEDE_PILOTO)
    anio = datetime.now(UTC).year
    estudiante_id = derivar("estudiante", str(usuario_id), str(colegio_id), GRADO_DEMO, str(anio))
    matricula_id = derivar("matricula", str(estudiante_id), str(sede_id), GRADO_DEMO, str(anio))
    return {
        "estudiante": {
            "id": estudiante_id,
            "nombre_cifrado": cifrador_desde_entorno().cifrar(APODO_DEMO.encode("utf-8")),
        },
        "matricula": {
            "id": matricula_id,
            "estudiante_id": estudiante_id,
            "sede_id": sede_id,
            "colegio_id": colegio_id,
            "grado": GRADO_DEMO,
            "anio_lectivo": anio,
        },
        "vinculo": {
            "usuario_id": usuario_id,
            "matricula_id": matricula_id,
            "parentesco": "acudiente",
            "es_principal": True,
        },
    }


async def sembrar(clave: str) -> dict[str, int]:
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert
    from tukit_comun.bd import crear_motor

    rol = Base.metadata.tables["rol"]
    permiso = Base.metadata.tables["permiso"]
    rol_permiso = Base.metadata.tables["rol_permiso"]
    usuario = Base.metadata.tables["usuario"]
    asignacion = Base.metadata.tables["asignacion_rol"]
    estudiante = Base.metadata.tables["estudiante"]
    matricula = Base.metadata.tables["matricula"]
    acudiente_matricula = Base.metadata.tables["acudiente_matricula"]

    demo = usuarios_demo(clave)
    hijo = hijo_demo_de_mama()
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

            colegio = Base.metadata.tables["colegio"]
            sede = Base.metadata.tables["sede"]
            piloto = (
                await conexion.execute(
                    select(colegio.c.id).where(colegio.c.id == hijo["matricula"]["colegio_id"])
                )
            ).first()
            sede_piloto = (
                await conexion.execute(select(sede.c.id).where(sede.c.id == hijo["matricula"]["sede_id"]))
            ).first()
            if piloto is None or sede_piloto is None:
                print(f"(sin el colegio piloto {COLEGIO_PILOTO}: no se siembra el hijo de mama)")
                return escritos
            await conexion.execute(
                insert(estudiante).values(hijo["estudiante"]).on_conflict_do_nothing(index_elements=["id"])
            )
            escritos["estudiante"] = 1
            await conexion.execute(
                insert(matricula).values(hijo["matricula"]).on_conflict_do_nothing(index_elements=["id"])
            )
            escritos["matricula"] = 1
            await conexion.execute(
                insert(acudiente_matricula).values(hijo["vinculo"]).on_conflict_do_nothing()
            )
            escritos["acudiente_matricula"] = 1
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
