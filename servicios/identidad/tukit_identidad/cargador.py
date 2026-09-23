"""Siembra los colegios y sus sedes desde el CSV versionado del monorepo.

Es la mitad de Identidad de una siembra que ocurre en dos bases y no se puede
hacer con una transaccion. El colegio `2.4` vive aqui y la lista de utiles que
publico vive en Catalogo, y entre las dos no hay ni puede haber una llave
foranea: son bases distintas, esa es la frontera y no un descuido.

Lo que sostiene la referencia es `tukit_comun.derivar`. El identificador del
colegio no se inventa: se deriva de su codigo, asi que los dos cargadores
llegan al mismo UUID sin hablarse y sin que ninguno importe al otro. Esto
importa mas de lo que parece, porque la funcion de aptitud de la regla 4
comprueba que la referencia cruzada este DECLARADA en el manifiesto, no que
resuelva. Con UUID aleatorio, la siembra pasaria todas las pruebas de
arquitectura y dejaria una lista oficial colgando de un colegio inexistente.

Sobre por que hay un `Problema` y un `Informe` aqui teniendo Catalogo los
suyos: no se pueden compartir. Un servicio no importa codigo de otro (regla 1)
y estas dos piezas son treinta lineas de presentacion, no dominio compartido;
subirlas a `libs/` para ahorrar treinta lineas seria empezar a llenar la
libreria comun de cosas que no son comunes, que es como una libreria
compartida se convierte en el sexto servicio del que dependen los cinco.

La siembra es idempotente por construccion. Volver a correrla actualiza las
mismas 17 filas en vez de duplicarlas, porque la llave primaria sale del
contenido y la escritura va por `ON CONFLICT DO UPDATE`.

Uso:

    python -m tukit_identidad.cargador
    python -m tukit_identidad.cargador --datos ../../datos/listas
    python -m tukit_identidad.cargador --solo-validar
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tukit_comun import derivar

# El corpus no distingue sedes. Se siembra una igual porque `matricula` cuelga
# de la sede y no del colegio: sin sede no hay donde matricular a nadie, y la
# tenencia -que es lo unico que este servicio aporta al resto del sistema-
# quedaria sin ancla.
SEDE_POR_OMISION = "Sede unica"


@dataclass(frozen=True)
class Problema:
    """Algo que esta mal en los datos.

    `bloqueante` separa lo que impide sembrar de lo que solo se ve feo. Un
    codigo de colegio repetido bloquea, porque los dos colegios derivarian el
    mismo UUID y uno se comeria al otro en silencio. Un colegio sin nombre
    propio no bloquea: se carga, se ve mal, y se reporta.
    """

    bloqueante: bool
    clase: str
    detalle: str

    def __str__(self) -> str:
        marca = "BLOQUEA" if self.bloqueante else "carencia"
        return f"[{marca}] {self.clase}: {self.detalle}"


@dataclass
class Informe:
    """Lo que se sembro y lo que le falta.

    Se imprime siempre, tambien cuando todo sale bien. El dato util no es
    "cargo 17 colegios" sino "cargo 17, de los cuales 9 se le muestran al papa
    como `Colegio 1.1`".
    """

    escritos: dict[str, int] = field(default_factory=dict)
    problemas: list[Problema] = field(default_factory=list)
    carencias: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def bloqueado(self) -> bool:
        return any(p.bloqueante for p in self.problemas)

    def imprimir(self) -> None:
        print("\n=== sembrado ===")
        for tabla, n in self.escritos.items():
            print(f"  {tabla:24} {n:5}")

        bloqueantes = [p for p in self.problemas if p.bloqueante]
        if bloqueantes:
            print(f"\n=== {len(bloqueantes)} problema(s) que BLOQUEAN ===")
            for p in bloqueantes[:20]:
                print(f"  {p}")
            if len(bloqueantes) > 20:
                print(f"  ... y {len(bloqueantes) - 20} mas")

        if self.carencias:
            print("\n=== lo que falta para poder mostrarlo a un papa ===")
            for que, (faltan, total) in sorted(self.carencias.items()):
                pct = 100 * faltan / total if total else 0
                print(f"  {que:38} {faltan:5}/{total:<5} ({pct:.0f}%)")

        otros = [p for p in self.problemas if not p.bloqueante]
        if otros:
            print(f"\n=== {len(otros)} carencia(s) con nombre propio ===")
            for p in otros[:15]:
                print(f"  {p}")
            if len(otros) > 15:
                print(f"  ... y {len(otros) - 15} mas")


def id_colegio(codigo: str) -> uuid.UUID:
    """El UUID del colegio, derivado de su codigo y de nada mas.

    Vive en una funcion con nombre en vez de estar escrito en medio del
    armado, porque es LA pieza que comparten dos bases. Cambiar el orden o el
    numero de partes aqui no es un refactor: desconecta cada lista oficial ya
    sembrada de su colegio, y lo hace sin error, porque la referencia es
    logica y nadie la impone.
    """
    return derivar("colegio", codigo)


def id_sede(codigo: str, sede_nombre: str) -> uuid.UUID:
    """El UUID de la sede. El nombre entra en la llave porque un colegio puede
    tener varias, y el codigo solo no las distinguiria."""
    return derivar("sede", codigo, sede_nombre)


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _texto(crudo: str | None) -> str:
    return (crudo or "").strip()


def es_nombre_de_relleno(codigo: str, nombre: str) -> bool:
    """Si el nombre es el codigo disfrazado.

    `Colegio 2.5` no es un nombre, es lo que quedo cuando el PDF fuente no
    decia de que colegio era la lista. Se cuenta aparte porque es la carencia
    que un papa ve primero: abre Tukit para la lista de su hijo y lo que
    encuentra es un codigo anonimizado.
    """
    return nombre == f"Colegio {codigo}"


class Cargador:
    def __init__(self, directorio: Path) -> None:
        self.dir = directorio
        self.problemas: list[Problema] = []
        self.carencias: dict[str, tuple[int, int]] = {}

    # -- armado en memoria -------------------------------------------------

    def armar(self) -> dict[str, list[dict[str, Any]]]:
        filas = leer_csv(self.dir / "colegios.csv")
        if not filas:
            self.problemas.append(Problema(True, "datos", f"no hay colegios.csv en {self.dir} o esta vacio"))
            return {"colegio": [], "sede": []}

        colegios: list[dict[str, Any]] = []
        sedes: list[dict[str, Any]] = []
        vistos: dict[str, int] = {}

        for numero, fila in enumerate(filas, start=2):
            codigo = _texto(fila.get("codigo"))
            if not codigo:
                self.problemas.append(Problema(True, "codigo", f"fila {numero} sin codigo de colegio"))
                continue
            # Dos filas con el mismo codigo derivan el MISMO UUID, asi que la
            # segunda no duplicaria nada: pisaria a la primera en el upsert y
            # el informe diria que sembro dos colegios. Un colegio perdido sin
            # un solo mensaje de error es exactamente el modo de falla que
            # este cargador existe para no tener.
            if codigo in vistos:
                self.problemas.append(
                    Problema(True, "codigo", f"`{codigo}` repetido en las filas {vistos[codigo]} y {numero}")
                )
                continue
            vistos[codigo] = numero

            nombre = _texto(fila.get("nombre")) or f"Colegio {codigo}"
            sede_nombre = _texto(fila.get("sede_nombre")) or SEDE_POR_OMISION
            if not _texto(fila.get("sede_nombre")):
                self.problemas.append(
                    Problema(False, "sede", f"`{codigo}` sin sede declarada: se asume `{SEDE_POR_OMISION}`")
                )

            colegios.append(
                {
                    "id": id_colegio(codigo),
                    "nombre": nombre,
                    # El corpus esta anonimizado y el NIT identificaria al
                    # colegio, que es justo lo que la anonimizacion evito. Se
                    # deja nulo y se cuenta como carencia en vez de inventar
                    # uno: la columna es unica, y un NIT falso convertiria un
                    # dato vacio en un dato erroneo que nadie volveria a mirar.
                    "nit": None,
                    "activo": True,
                }
            )
            sedes.append(
                {
                    "id": id_sede(codigo, sede_nombre),
                    "colegio_id": id_colegio(codigo),
                    "nombre": sede_nombre,
                    "activa": True,
                }
            )

        self._medir_carencias(list(vistos), colegios)
        return {"colegio": colegios, "sede": sedes}

    def _medir_carencias(self, codigos: list[str], colegios: list[dict[str, Any]]) -> None:
        """Los codigos llegan aparte y no se releen del CSV a proposito.

        Releerlos volveria a contar las filas que el armado descarto, y las
        dos listas se desalinearian en cuanto hubiera un codigo repetido:
        el nombre de un colegio se compararia contra el codigo de otro.
        """
        total = len(colegios)
        if not total:
            return
        self.carencias["colegios sin nombre propio"] = (
            sum(
                1
                for codigo, colegio in zip(codigos, colegios, strict=True)
                if es_nombre_de_relleno(codigo, colegio["nombre"])
            ),
            total,
        )
        self.carencias["colegios sin NIT"] = (sum(1 for c in colegios if not c["nit"]), total)

    # -- escritura --------------------------------------------------------

    async def escribir(self, datos: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        from sqlalchemy.dialects.postgresql import insert
        from tukit_comun.bd import crear_motor

        from .modelos import Base

        motor = crear_motor("identidad")
        escritos: dict[str, int] = {}
        try:
            async with motor.engine.begin() as conexion:
                # El orden es el de las dependencias: la sede tiene una llave
                # foranea real hacia el colegio, dentro de esta misma base.
                for tabla in ("colegio", "sede"):
                    filas = datos.get(tabla, [])
                    if not filas:
                        escritos[tabla] = 0
                        continue
                    objeto = Base.metadata.tables[tabla]
                    sentencia = insert(objeto).values(filas)
                    # `ON CONFLICT DO UPDATE` sobre la llave primaria es lo que
                    # hace la siembra repetible. `creado_en` no entra en el
                    # conjunto actualizable porque no esta en las filas: la
                    # pone la base la primera vez y volver a sembrar no debe
                    # mover la fecha en que el colegio entro al sistema.
                    actualizables = {
                        c.name: sentencia.excluded[c.name]
                        for c in objeto.columns
                        if c.name not in [k.name for k in objeto.primary_key.columns] and c.name in filas[0]
                    }
                    if actualizables:
                        sentencia = sentencia.on_conflict_do_update(
                            index_elements=[c.name for c in objeto.primary_key.columns],
                            set_=actualizables,
                        )
                    else:
                        sentencia = sentencia.on_conflict_do_nothing()
                    await conexion.execute(sentencia)
                    escritos[tabla] = len(filas)
        finally:
            await motor.cerrar()
        return escritos


async def _principal(directorio: Path, solo_validar: bool) -> int:
    cargador = Cargador(directorio)
    datos = cargador.armar()

    informe = Informe(
        escritos={t: len(f) for t, f in datos.items()},
        problemas=cargador.problemas,
        carencias=cargador.carencias,
    )

    if informe.bloqueado:
        print("No se escribio nada: hay codigos de colegio rotos o repetidos.")
        informe.imprimir()
        return 1

    if not solo_validar:
        informe.escritos = await cargador.escribir(datos)

    informe.imprimir()
    if solo_validar:
        print("\n(--solo-validar: no se escribio nada en la base)")
    else:
        print("\nLas listas de estos colegios las siembra Catalogo, contra los mismos UUID.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--datos", type=Path, default=Path("datos/listas"))
    analizador.add_argument("--solo-validar", action="store_true")
    args = analizador.parse_args()

    directorio = args.datos
    if not directorio.exists():
        print(f"No existe el directorio de datos: {directorio}")
        return 2

    return asyncio.run(_principal(directorio, args.solo_validar))


if __name__ == "__main__":
    sys.exit(main())
