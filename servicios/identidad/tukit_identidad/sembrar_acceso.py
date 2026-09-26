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
from datetime import UTC, datetime

from tukit_comun import derivar
from tukit_comun.cifrado import cifrador_desde_entorno

from .modelos import AmbitoTipo, Base, Clasificacion
from .sesiones import hashear_clave

# El colegio del piloto, para anclar el ambito del acudiente y del colegio en
# algo que `cargador.py` tambien siembra (mismo UUID, derivado del codigo).
COLEGIO_PILOTO = "2.13"
# La sede unica del piloto: mismo UUID que deriva `cargador.py` de su nombre.
SEDE_PILOTO = "Sede unica"
# El grado del hijo sembrado. Canonico ("Quinto", no "5") porque asi lo nombra
# el catalogo escolar y asi valida la lista oficial contra la que se arma el kit.
GRADO_DEMO = "Quinto"
# Un apodo, no un nombre legal: es lo unico que se guarda del menor y va cifrado,
# igual que lo hara el registro real (minimizacion, Ley 1581 de 2012, Art. 4).
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


def hijo_demo_de_mama() -> dict[str, dict[str, object]]:
    """Un hijo para `mama@ejemplo.com`, para que el camino "ya tengo cuenta"
    tenga algo que precargar en `/empezar`.

    Los UUID se derivan igual que en `POST /v1/registro`, asi que una mama
    sembrada y una mama registrada producen exactamente las mismas filas: la
    siembra es solo un atajo del registro real, no un formato aparte. El apodo
    va cifrado con el cifrador del entorno (en desarrollo, `CifradorEnClaro`).
    """
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

            # El hijo de mama. UUID derivados, asi que re-sembrar cae en las
            # mismas filas y no duplica. Depende de que `cargador.py` ya haya
            # sembrado el colegio piloto y su sede (mismo UUID derivado).
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
