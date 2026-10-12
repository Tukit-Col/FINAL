"""Lleva la curaduria de listas de la base a git, y de git a otra base.

El problema que resuelve. Curar una lista es decidir, renglon por renglon, a
que concepto corresponde lo que el colegio escribio, y cerrarla. Ese trabajo
vivia solo en `item_lista_oficial` de UNA base local: `volcar` exporta
productos, no listas; `items_lista.csv` ni siquiera tiene columna de concepto,
y `cargador_listas` vuelve a ADIVINAR el concepto por parecido. Un compañero
que clonaba el repositorio no recibia nada de lo curado, y la lista que ya
estaba resuelta volvia a pasar por la percepcion (Gemini) y por la cola.

Que viaja, y a donde:

- `datos/curaduria/listas_revisadas.csv`: un renglon por item de cada version
  VIGENTE y REVISADA. El concepto va por `codigo` (C001...), no por UUID, para
  que el diff se pueda leer.
- `datos/catalogo/conceptos.csv`: los conceptos que se crearon curando (el
  "Crear concepto" de la cola) se AGREGAN, y los existentes se actualizan
  desde la base. Sin esto un renglon apuntaria a un concepto que el otro lado
  no tiene.

Los colegios NO se exportan aqui: son de Identidad, y este servicio no lee esa
base (regla 3). El modulo `curaduria` de Identidad lee el CSV de listas que
sale de aqui y exporta los colegios que ese CSV nombra.

Lo que NO viaja, a proposito: el PDF original y la percepcion cruda
(`tarea_importacion`). Pesan, y el PDF puede traer nombres de menores; la
version publicada ya guarda su texto redactado, pero el documento no.

Uso (desde la raiz, con el entorno del servicio):

    python -m tukit_catalogo.curaduria exportar
    python -m tukit_catalogo.curaduria importar
    python -m tukit_catalogo.curaduria importar --solo-validar

`importar` supone que los conceptos ya estan cargados (`make bd-cargar`), y es
idempotente: una lista cuya version vigente ya dice lo mismo no se toca.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection

from .cargador import CONCEPTOS_LIBRO
from .modelos import Base

RAIZ = Path(__file__).resolve().parents[3]
DATOS = RAIZ / "datos"

ARCHIVO_LISTAS = Path("curaduria") / "listas_revisadas.csv"
ARCHIVO_CONCEPTOS = Path("catalogo") / "conceptos.csv"

COLUMNAS_LISTAS = [
    "colegio_id",
    "sede_id",
    "grado",
    "anio_lectivo",
    "revisada_en",
    "orden",
    "texto_original",
    "concepto",
    "cantidad",
    "unidad",
    "tipo_item",
    "modo_adquisicion",
    "instruccion_colegio",
    "url_externa",
    "atributos",
    "requiere_revision",
    "avisos_descartados",
]

COLUMNAS_CONCEPTOS = [
    "id",
    "codigo",
    "nombre_canonico",
    "sinonimos",
    "categoria",
    "tipo_item",
    "atributos_discriminantes",
    "atributos_descriptivos",
    "admite_personaje",
    "frecuencia_demanda",
    "activo",
    "uno_por_estudiante",
]

# Columnas que el CSV conserva aunque la base diga otra cosa. `admite_personaje`
# la deduce la base de los productos (el cargador no la pisa) y
# `frecuencia_demanda` es una medida del corpus, no algo que se cure en la cola.
# Reescribirlas desde la base llenaria el diff de cambios que nadie hizo.
COLUMNAS_PROPIAS_DEL_CSV = frozenset({"admite_personaje", "frecuencia_demanda"})

LISTA = Base.metadata.tables["lista_oficial"]
VERSION = Base.metadata.tables["version_lista_oficial"]
ITEM = Base.metadata.tables["item_lista_oficial"]
CONCEPTO = Base.metadata.tables["concepto"]
BANDEJA = Base.metadata.tables["bandeja_salida"]


# ---------------------------------------------------------------------------
# Serializacion: una sola forma de escribir cada valor, para que exportar dos
# veces la misma base de el mismo archivo byte a byte.
# ---------------------------------------------------------------------------


def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor)


def _bool(valor: Any) -> str:
    return "true" if valor else "false"


def _atributos(valor: dict[str, Any] | None) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True) if valor else ""


def _nulo(valor: str | None) -> str | None:
    limpio = (valor or "").strip()
    return limpio or None


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def escribir_csv(ruta: Path, columnas: list[str], filas: list[dict[str, str]]) -> None:
    """Escribe respetando el fin de linea que el archivo ya tenia.

    Git en Windows puede haber dejado `\\r\\n` o `\\n` segun la configuracion de
    quien lo clono; cambiarlo marcaria el archivo entero como modificado.
    """
    fin = "\r\n" if ruta.exists() and b"\r\n" in ruta.read_bytes()[:4096] else "\n"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, lineterminator=fin)
        escritor.writeheader()
        escritor.writerows(filas)


# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------


def filas_de_listas(conexion: Connection) -> list[dict[str, str]]:
    """Los renglones de la ultima version revisada de cada lista, en orden estable.

    La ultima revisada y no la vigente: volver a subir una lista deja vigente
    una version sin revisar, y exigir las dos cosas sacaba de git la lista ya
    curada mientras la nueva esperaba en la cola.
    """
    otra = VERSION.alias("otra")
    ultima_revisada = (
        select(otra.c.id)
        .where(otra.c.lista_id == LISTA.c.id, otra.c.revisada_en.is_not(None))
        .order_by(otra.c.revisada_en.desc(), otra.c.numero.desc())
        .limit(1)
        .correlate(LISTA)
        .scalar_subquery()
    )
    consulta = (
        select(
            LISTA.c.colegio_id,
            LISTA.c.sede_id,
            LISTA.c.grado,
            LISTA.c.anio_lectivo,
            VERSION.c.revisada_en,
            ITEM.c.orden,
            ITEM.c.texto_original,
            CONCEPTO.c.codigo,
            ITEM.c.cantidad,
            ITEM.c.unidad,
            ITEM.c.tipo_item,
            ITEM.c.modo_adquisicion,
            ITEM.c.instruccion_colegio,
            ITEM.c.url_externa,
            ITEM.c.atributos,
            ITEM.c.requiere_revision,
            ITEM.c.avisos_descartados,
        )
        .select_from(
            LISTA.join(VERSION, VERSION.c.lista_id == LISTA.c.id)
            .join(ITEM, ITEM.c.version_id == VERSION.c.id)
            .outerjoin(CONCEPTO, CONCEPTO.c.id == ITEM.c.concepto_id)
        )
        .where(VERSION.c.id == ultima_revisada)
    )
    filas = [
        {
            "colegio_id": str(f.colegio_id),
            "sede_id": _texto(f.sede_id),
            "grado": f.grado,
            "anio_lectivo": str(f.anio_lectivo),
            "revisada_en": f.revisada_en.isoformat(),
            "orden": str(f.orden),
            "texto_original": f.texto_original,
            "concepto": _texto(f.codigo),
            "cantidad": str(f.cantidad),
            "unidad": _texto(f.unidad),
            "tipo_item": _texto(f.tipo_item),
            "modo_adquisicion": f.modo_adquisicion,
            "instruccion_colegio": _texto(f.instruccion_colegio),
            "url_externa": _texto(f.url_externa),
            "atributos": _atributos(f.atributos),
            "requiere_revision": _bool(f.requiere_revision),
            "avisos_descartados": "|".join(f.avisos_descartados or ()),
        }
        for f in conexion.execute(consulta)
    ]
    filas.sort(key=lambda f: (f["colegio_id"], f["sede_id"], f["grado"], f["anio_lectivo"], int(f["orden"])))
    return filas


def _fila_concepto(f: Any) -> dict[str, str]:
    return {
        "id": str(f.id),
        "codigo": f.codigo,
        "nombre_canonico": f.nombre_canonico,
        "sinonimos": "|".join(f.sinonimos or ()),
        "categoria": f.categoria,
        "tipo_item": f.tipo_item,
        "atributos_discriminantes": "|".join(f.atributos_discriminantes or ()),
        "atributos_descriptivos": "|".join(f.atributos_descriptivos or ()),
        "admite_personaje": _bool(f.admite_personaje),
        "frecuencia_demanda": str(f.frecuencia_demanda),
        "activo": _bool(f.activo),
        "uno_por_estudiante": _bool(f.uno_por_estudiante),
    }


def fusionar_conceptos(
    en_csv: list[dict[str, str]], en_base: list[dict[str, str]]
) -> tuple[list[dict[str, str]], int, int]:
    """El CSV con lo que la base agrego o cambio. Devuelve (filas, nuevos, cambiados).

    No se borra ninguna fila del CSV: un concepto que falta en la base es una
    base a medio cargar, no una decision de quitarlo. Los conceptos de libros
    (`CONCEPTOS_LIBRO`) no se tocan: el cargador los reescribe en cada carga
    (su `tipo_item` pasa a `libro_libre`), asi que la base siempre diferiria del
    CSV y el volcado los marcaria cambiados sin que nadie los curara.
    """
    por_codigo = {f["codigo"]: f for f in en_base}
    salida: list[dict[str, str]] = []
    cambiados = 0
    for fila in en_csv:
        viva = por_codigo.pop(fila["codigo"], None)
        if viva is None or fila["codigo"] in CONCEPTOS_LIBRO:
            salida.append(fila)
            continue
        # Una columna que la base todavia no tiene (una base sin la ultima
        # migracion) no borra lo que el CSV ya decia.
        nueva = {
            c: fila.get(c, "") if c in COLUMNAS_PROPIAS_DEL_CSV else viva.get(c, fila.get(c, ""))
            for c in COLUMNAS_CONCEPTOS
        }
        if any(nueva[c] != fila.get(c, "") for c in COLUMNAS_CONCEPTOS):
            cambiados += 1
        salida.append(nueva)
    nuevos = [f for codigo, f in sorted(por_codigo.items()) if codigo not in CONCEPTOS_LIBRO]
    return salida + nuevos, len(nuevos), cambiados


def conceptos_de_base(conexion: Connection) -> list[dict[str, str]]:
    return [_fila_concepto(f) for f in conexion.execute(select(CONCEPTO))]


# ---------------------------------------------------------------------------
# Importar
# ---------------------------------------------------------------------------


@dataclass
class ListaCurada:
    colegio_id: uuid.UUID
    sede_id: uuid.UUID | None
    grado: str
    anio_lectivo: int
    revisada_en: datetime
    renglones: list[dict[str, str]] = field(default_factory=list)

    @property
    def nombre(self) -> str:
        return f"{self.colegio_id} · {self.grado} · {self.anio_lectivo}"


@dataclass
class Resultado:
    nuevas: list[str] = field(default_factory=list)
    actualizadas: list[str] = field(default_factory=list)
    al_dia: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    def imprimir(self) -> None:
        print("=== listas curadas ===")
        print(f"  nuevas          {len(self.nuevas):5}")
        print(f"  actualizadas    {len(self.actualizadas):5}")
        print(f"  ya al dia       {len(self.al_dia):5}")
        for nombre in self.actualizadas:
            print(f"    reemplazada la version vigente de {nombre}")
        if self.errores:
            print(f"\n{len(self.errores)} lista(s) NO se importaron:")
            for error in self.errores:
                print(f"  - {error}")


def agrupar(filas: list[dict[str, str]]) -> list[ListaCurada]:
    grupos: dict[tuple[str, str, str, str], ListaCurada] = {}
    for fila in filas:
        llave = (fila["colegio_id"], fila["sede_id"], fila["grado"], fila["anio_lectivo"])
        if llave not in grupos:
            grupos[llave] = ListaCurada(
                colegio_id=uuid.UUID(fila["colegio_id"]),
                sede_id=uuid.UUID(fila["sede_id"]) if fila["sede_id"] else None,
                grado=fila["grado"],
                anio_lectivo=int(fila["anio_lectivo"]),
                revisada_en=datetime.fromisoformat(fila["revisada_en"]),
            )
        grupos[llave].renglones.append(fila)
    for lista in grupos.values():
        lista.renglones.sort(key=lambda f: int(f["orden"]))
    return list(grupos.values())


def _item(renglon: dict[str, str], conceptos: dict[str, uuid.UUID]) -> dict[str, Any]:
    codigo = _nulo(renglon["concepto"])
    return {
        "orden": int(renglon["orden"]),
        "texto_original": renglon["texto_original"],
        "concepto_id": conceptos[codigo] if codigo else None,
        "cantidad": int(renglon["cantidad"]),
        "unidad": _nulo(renglon["unidad"]),
        "tipo_item": _nulo(renglon["tipo_item"]),
        "modo_adquisicion": renglon["modo_adquisicion"],
        "instruccion_colegio": _nulo(renglon["instruccion_colegio"]),
        "url_externa": _nulo(renglon["url_externa"]),
        "atributos": json.loads(renglon["atributos"]) if renglon["atributos"] else {},
        "requiere_revision": renglon["requiere_revision"] == "true",
        # Columna nueva: un CSV exportado antes de ella no la trae.
        "avisos_descartados": [a for a in (renglon.get("avisos_descartados") or "").split("|") if a],
    }


_CAMPOS_ITEM = (
    "orden",
    "texto_original",
    "concepto_id",
    "cantidad",
    "unidad",
    "tipo_item",
    "modo_adquisicion",
    "instruccion_colegio",
    "url_externa",
    "atributos",
    "requiere_revision",
    "avisos_descartados",
)


def _huella(items: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return sorted(
        tuple(json.dumps(i[c] or {}, sort_keys=True) if c == "atributos" else i[c] for c in _CAMPOS_ITEM)
        for i in items
    )


def importar_listas(conexion: Connection, listas: list[ListaCurada]) -> Resultado:
    """Deja cada lista curada como la version vigente y revisada de su lista.

    Si la vigente local ya es revisada y dice lo mismo, no se toca. Si no, se
    crea una version nueva (numero siguiente) y la anterior deja de ser vigente:
    se versiona, no se sobreescribe, igual que al corregir desde la cola, para
    que quien compro contra la anterior siga sabiendo contra que compro.

    Los kits canonicos no viajan en el CSV: viven en la base de Inteligencia, que
    este servicio no toca. Por cada lista importada se deja el mismo
    `lista_aprobada` que deja aprobarla en la cola, y el poller de Inteligencia
    los arma en esta maquina. Tambien para las listas que ya estaban al dia: asi
    importar de nuevo repara una base que tiene las listas pero no sus kits. El
    poller no vuelve a optimizar una version que ya tiene canonico.
    """
    conceptos = {f.codigo: f.id for f in conexion.execute(select(CONCEPTO.c.codigo, CONCEPTO.c.id))}
    resultado = Resultado()

    for lista in listas:
        faltan = sorted(
            {r["concepto"] for r in lista.renglones if r["concepto"] and r["concepto"] not in conceptos}
        )
        if faltan:
            resultado.errores.append(
                f"{lista.nombre}: la base no tiene los conceptos {', '.join(faltan)} "
                "(corre primero bd-cargar)"
            )
            continue
        items = [_item(r, conceptos) for r in lista.renglones]

        filtro_sede = LISTA.c.sede_id.is_(None) if lista.sede_id is None else LISTA.c.sede_id == lista.sede_id
        lista_id = conexion.execute(
            select(LISTA.c.id).where(
                LISTA.c.colegio_id == lista.colegio_id,
                filtro_sede,
                LISTA.c.grado == lista.grado,
                LISTA.c.anio_lectivo == lista.anio_lectivo,
            )
        ).scalar_one_or_none()
        existia = lista_id is not None
        if lista_id is None:
            lista_id = uuid.uuid4()
            conexion.execute(
                LISTA.insert().values(
                    id=lista_id,
                    colegio_id=lista.colegio_id,
                    sede_id=lista.sede_id,
                    grado=lista.grado,
                    anio_lectivo=lista.anio_lectivo,
                    activa=True,
                )
            )

        vigente = conexion.execute(
            select(VERSION.c.id, VERSION.c.revisada_en).where(
                VERSION.c.lista_id == lista_id, VERSION.c.vigente.is_(True)
            )
        ).first()
        if vigente is not None and vigente.revisada_en is not None:
            actuales = [
                dict(f._mapping)
                for f in conexion.execute(
                    select(*(ITEM.c[c] for c in _CAMPOS_ITEM)).where(ITEM.c.version_id == vigente.id)
                )
            ]
            if _huella(actuales) == _huella(items):
                _pedir_canonicos(conexion, lista, vigente.id)
                resultado.al_dia.append(lista.nombre)
                continue

        numero = (
            conexion.execute(
                select(func.max(VERSION.c.numero)).where(VERSION.c.lista_id == lista_id)
            ).scalar()
            or 0
        ) + 1
        # Primero se apaga la vigente: el indice unico parcial sobre `vigente`
        # no admite dos a la vez ni por un instante.
        conexion.execute(update(VERSION).where(VERSION.c.lista_id == lista_id).values(vigente=False))
        version_id = uuid.uuid4()
        conexion.execute(
            VERSION.insert().values(
                id=version_id,
                lista_id=lista_id,
                numero=numero,
                vigente=True,
                revisada_en=lista.revisada_en,
            )
        )
        conexion.execute(
            ITEM.insert(), [{"id": uuid.uuid4(), "version_id": version_id, **item} for item in items]
        )
        _pedir_canonicos(conexion, lista, version_id)
        (resultado.actualizadas if existia and vigente is not None else resultado.nuevas).append(lista.nombre)

    return resultado


def _pedir_canonicos(conexion: Connection, lista: ListaCurada, version_id: uuid.UUID) -> None:
    """Deja `lista_aprobada` en la bandeja, igual que `cerrar_version` (ADR 0030)."""
    conexion.execute(
        BANDEJA.insert().values(
            tipo="lista_aprobada",
            agregado_tipo="version_lista_oficial",
            agregado_id=version_id,
            carga={
                "colegio_id": str(lista.colegio_id),
                "grado": lista.grado,
                "anio_lectivo": lista.anio_lectivo,
            },
        )
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def _exportar(datos: Path) -> int:
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.connect() as conexion:
            listas = await conexion.run_sync(filas_de_listas)
            conceptos = await conexion.run_sync(conceptos_de_base)
    finally:
        await motor.cerrar()

    escribir_csv(datos / ARCHIVO_LISTAS, COLUMNAS_LISTAS, listas)
    ruta_conceptos = datos / ARCHIVO_CONCEPTOS
    fusion, nuevos, cambiados = fusionar_conceptos(leer_csv(ruta_conceptos), conceptos)
    escribir_csv(ruta_conceptos, COLUMNAS_CONCEPTOS, fusion)

    print("=== curaduria exportada ===")
    print(f"  listas revisadas      {len(agrupar(listas)):5}   ({len(listas)} renglones)")
    print(f"  conceptos nuevos      {nuevos:5}")
    print(f"  conceptos cambiados   {cambiados:5}")
    print(f"\n  {datos / ARCHIVO_LISTAS}")
    print(f"  {ruta_conceptos}")
    return 0


async def _importar(datos: Path, solo_validar: bool) -> int:
    from tukit_comun.bd import crear_motor

    ruta = datos / ARCHIVO_LISTAS
    if not ruta.exists():
        print(f"No hay curaduria que importar: falta {ruta}")
        return 0
    listas = agrupar(leer_csv(ruta))

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.connect() as conexion:
            resultado = await conexion.run_sync(importar_listas, listas)
            if solo_validar or resultado.errores:
                await conexion.rollback()
            else:
                await conexion.commit()
    finally:
        await motor.cerrar()

    resultado.imprimir()
    if resultado.errores:
        print("\nNo se escribio nada: primero hay que resolver lo de arriba.")
        return 1
    if solo_validar:
        print("\n(--solo-validar: no se escribio nada)")
    return 0


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Exporta o importa la curaduria de listas.")
    analizador.add_argument("accion", choices=["exportar", "importar"])
    analizador.add_argument("--datos", type=Path, default=DATOS, help="la carpeta datos/ del repositorio")
    analizador.add_argument("--solo-validar", action="store_true", help="importar sin escribir")
    args = analizador.parse_args(argv)

    if args.accion == "exportar":
        return asyncio.run(_exportar(args.datos))
    return asyncio.run(_importar(args.datos, args.solo_validar))


if __name__ == "__main__":
    sys.exit(main())
