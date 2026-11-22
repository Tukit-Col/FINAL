"""Siembra las listas oficiales de los 17 colegios del corpus.

Cierra el ultimo hueco de la cadena. El catalogo curado ya estaba en la base y
`descubrir` ya sabia revisar una lista y dar de alta lo que le falta, pero no
habia ninguna lista: `--listas` imprimia "No hay listas cargadas todavia" y la
unica puerta por la que el sistema sale a una tienda estaba cerrada porque no
existia nada que abrirla. Esto es lo que mete los 4.719 renglones que el
corpus transcribio de los PDF de los colegios.

Tres decisiones que el modelo impone y que conviene leer antes de tocar nada:

1. **La version nace SIN revisar.** `revisada_en` se deja en nulo a proposito.
   El modelo documenta que una version sin revisar es la que habilita el
   descubrimiento, y que una vez cerrada no se vuelve a abrir. Sembrar las
   listas ya revisadas seria sembrarlas muertas: ningun renglon podria salir
   nunca a buscar producto, y el catalogo dejaria de poder crecer con lo que
   los colegios piden.

2. **Un renglon sin concepto NO se fuerza al concepto mas parecido.** Por
   debajo de 0,5 de parecido queda `concepto_id` nulo y `requiere_revision`
   en verdadero, que es lo que la restriccion `item_sin_concepto_va_a_revision`
   exige. El informe dice cuantos quedaron asi y en que porcentaje. Ese numero
   NO es un fallo del cargador: es la medida honesta de cuanto del corpus
   nuestro vocabulario todavia no cubre, y taparlo colgando renglones del
   concepto que mas se le parezca es como se llega a ofrecerle plastilina a
   quien pidio pompones.

3. **Lo que Tukit no surte tiene que decir como se consigue.** La restriccion
   `item_no_surtible_explica_como_conseguirlo` no admite un renglon de
   plataforma o de edicion exclusiva sin instruccion. El CSV ya los trae, pero
   el cargador los rellena igual si llegan vacios, porque reventar a mitad de
   una carga de 4.719 filas por una restriccion de la base deja la siembra a
   medias y no dice cual fue la fila.

El `colegio_id` de cada lista sale de `derivar("colegio", codigo)`, la misma
funcion que usa el cargador de Identidad. Es lo unico que sostiene una
referencia que cruza dos bases y que ninguna llave foranea puede imponer: si
cada lado inventara su UUID, la funcion de aptitud seguiria en verde -mira
que la referencia este declarada, no que resuelva- y la lista quedaria
colgando de un colegio que no existe.

Uso:

    python -m tukit_catalogo.cargador_listas --datos ../../datos/listas
    python -m tukit_catalogo.cargador_listas --anio 2026 --solo-validar
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

from .clasificacion import clasificar
from .modelos.base import MODOS_SURTIBLES, ModoAdquisicion, TipoItem

ANIO_POR_OMISION = 2026

# Por debajo de este parecido el renglon no se cuelga de un concepto que ya
# existe. Es el mismo umbral que usa `descubrir.proponer`, y tiene que serlo:
# si el cargador resolviera con un umbral mas flojo que el que decide salir a
# una tienda, habria renglones dados por resueltos que la revision nunca
# vuelve a mirar.
UMBRAL_CONCEPTO = 0.5

MODOS_VALIDOS = frozenset(m.value for m in ModoAdquisicion)
TIPOS_VALIDOS = frozenset(t.value for t in TipoItem)
VALORES_SURTIBLES = frozenset(m.value for m in MODOS_SURTIBLES)

# Que decirle al acudiente cuando Tukit no puede poner el renglon en el
# carrito. Es una red de seguridad, no la fuente: los textos buenos los genera
# `datos/listas/construir.py` desde el corpus y viajan en el CSV.
#
# Existe de todos modos porque la invariante la impone la BASE, y un cargador
# no puede dar por hecho que su entrada la cumple. Sin esto, un CSV con una
# celda vacia no falla al leerse: falla dentro del INSERT, con el nombre de
# una restriccion, despues de haber escrito las listas y las versiones.
INSTRUCCION_POR_MODO: dict[str, str] = {
    "plataforma": (
        "El colegio indica que se adquiere por plataforma externa. "
        "Sigue el enlace o las instrucciones que el colegio publico en su lista."
    ),
    "venta_directa_editorial": (
        "El colegio indica que la editorial lo vende directamente a las familias, "
        "por lo general en una jornada de venta en el plantel."
    ),
    "edicion_exclusiva": (
        "El colegio indica que es una edicion exclusiva para la institucion: "
        "solo se consigue por el canal que el colegio senale."
    ),
    "diferido": (
        "El colegio indica que se pide mas adelante en el ano lectivo. Todavia no hay que comprarlo."
    ),
}

# Cuantas filas van en cada INSERT.
#
# No es afinamiento: el protocolo extendido de Postgres cuenta los parametros
# de una sentencia en un entero de 16 bits, asi que una sola con las 4.719
# filas y sus catorce columnas se pasa del limite y el driver la rechaza antes
# de enviarla. Partirla es obligatorio; 400 deja margen de sobra para la tabla
# mas ancha.
FILAS_POR_BLOQUE = 400


@dataclass(frozen=True)
class Problema:
    """Algo que esta mal en los datos.

    `bloqueante` separa lo que impide sembrar de lo que solo hay que reportar.
    Un renglon de un colegio que no esta en `colegios.csv` bloquea, porque su
    lista quedaria apuntando a un colegio inexistente. Un renglon cuyo
    concepto no se resolvio no bloquea: se siembra marcado para revision, que
    es justo lo que el modelo quiere que pase.
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

    Se imprime siempre. El numero que importa no es "4.719 renglones": es
    cuantos de esos renglones el catalogo supo reconocer.
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


# ---------------------------------------------------------------------------
# Piezas puras. Sin base de datos: es donde estan las decisiones, y por eso es
# lo que las pruebas fijan.
# ---------------------------------------------------------------------------


def id_colegio(codigo: str) -> uuid.UUID:
    """El UUID del colegio segun Identidad, derivado aqui sin preguntarle.

    Identidad tiene esta misma funcion y las dos tienen que dar lo mismo. No
    se comparte el codigo porque un servicio no importa codigo de otro; lo que
    se comparte es `derivar`, que vive en la libreria comun, y el acuerdo de
    que la llave natural del colegio es su codigo y nada mas.
    """
    return derivar("colegio", codigo)


def id_sede(codigo: str, sede_nombre: str) -> uuid.UUID:
    return derivar("sede", codigo, sede_nombre)


def id_lista(codigo: str, grado: str, anio: int) -> uuid.UUID:
    return derivar("lista", codigo, grado, str(anio))


def id_version(codigo: str, grado: str, anio: int, numero: int = 1) -> uuid.UUID:
    return derivar("version_lista", codigo, grado, str(anio), str(numero))


def id_item(codigo: str, grado: str, orden: int) -> uuid.UUID:
    """La llave del renglon, sin el ano lectivo dentro.

    Es deliberado y tiene un limite que hay que conocer: mientras solo haya un
    ano sembrado, la llave natural de un renglon es su lugar en la lista de un
    colegio y un grado. El dia que se siembre un segundo ano lectivo hay que
    meter el ano aqui, porque si no el renglon 7 de Cuarto de 2027 derivaria
    el identificador del renglon 7 de Cuarto de 2026 y el upsert lo movería de
    version en vez de crear uno nuevo.
    """
    return derivar("item_lista", codigo, grado, str(orden))


def normalizar_modo(crudo: str | None) -> str:
    """`desconocido` no es un modo: es que el PDF no lo dijo.

    El corpus lo trae en 736 renglones y no es un valor de `ModoAdquisicion`,
    asi que la restriccion `item_modo_adquisicion_valido` lo rechazaria. Cae
    en `mercado_abierto` porque el error barato es intentar surtirlo y no
    encontrar edicion, que se ve; el caro es marcarlo cerrado e inventarle al
    papa una instruccion que ningun colegio dio.
    """
    limpio = (crudo or "").strip()
    if not limpio or limpio not in MODOS_VALIDOS:
        return ModoAdquisicion.MERCADO_ABIERTO.value
    return limpio


def normalizar_tipo(crudo: str | None) -> str | None:
    """Nulo significa "lo que diga el concepto", que no es lo mismo que `util`.

    Por eso un tipo que no se reconoce se deja en nulo en vez de caer en el
    valor por omision: el renglon hereda el tipo de su concepto, que es una
    decision de catalogo, en lugar de afirmar por su cuenta que es papeleria.
    """
    limpio = (crudo or "").strip()
    return limpio if limpio in TIPOS_VALIDOS else None


def cantidad_valida(crudo: str | None) -> int:
    """Al menos uno: `item_cantidad_positiva` no admite cero.

    Un cero no significa que el colegio no lo pida, significa que la
    transcripcion no encontro el numero en el PDF. Uno es la lectura
    conservadora y la unica que la base acepta.
    """
    try:
        cantidad = int(float((crudo or "").strip()))
    except ValueError:
        return 1
    return cantidad if cantidad > 0 else 1


def instruccion_para(modo: str, declarada: str | None) -> str | None:
    """Lo que el colegio dijo, y si no dijo nada, lo que el modo implica.

    Devuelve nulo para lo surtible: la columna solo tiene sentido cuando Tukit
    no puede poner el renglon en el carrito, y llenarla siempre convertiria un
    aviso en ruido.
    """
    texto = (declarada or "").strip()
    if texto:
        return texto
    if modo in VALORES_SURTIBLES:
        return None
    return INSTRUCCION_POR_MODO.get(
        modo, "El colegio indica que este renglon no se compra en el mercado abierto."
    )


def _texto(crudo: str | None) -> str | None:
    limpio = (crudo or "").strip()
    return limpio or None


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class Cargador:
    def __init__(self, directorio: Path, anio: int = ANIO_POR_OMISION) -> None:
        self.dir = directorio
        self.anio = anio
        self.problemas: list[Problema] = []
        self.carencias: dict[str, tuple[int, int]] = {}
        self.sin_concepto = 0
        self.total_items = 0

    # -- armado en memoria -------------------------------------------------

    def armar(self, conceptos: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Arma las tres capas en memoria contra el vocabulario que se le pase.

        Los conceptos entran por parametro y no se leen aqui adentro para que
        el armado entero -que es donde estan todas las decisiones- se pueda
        probar sin una base de datos. Es la misma razon por la que el cargador
        del catalogo separa `armar` de `escribir`.
        """
        sedes = self._sedes()
        filas = leer_csv(self.dir / "items_lista.csv")
        if not filas:
            self.problemas.append(
                Problema(True, "datos", f"no hay items_lista.csv en {self.dir} o esta vacio")
            )
            return {"lista_oficial": [], "version_lista_oficial": [], "item_lista_oficial": []}

        listas: dict[tuple[str, str], dict[str, Any]] = {}
        versiones: dict[tuple[str, str], dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        ordenes: set[tuple[str, str, int]] = set()
        # El mismo renglon aparece en varios grados y en varios colegios
        # ("Borrador de Nata" esta 40 veces). Clasificar es comparar la frase
        # contra cada sinonimo de cada concepto, asi que repetirlo por cada
        # aparicion multiplica el trabajo sin cambiar el resultado.
        resueltos: dict[str, tuple[uuid.UUID | None, float]] = {}

        for numero, fila in enumerate(filas, start=2):
            codigo = (fila.get("colegio_codigo") or "").strip()
            grado = (fila.get("grado") or "").strip()
            texto = (fila.get("texto_original") or "").strip()
            if not codigo or not grado or not texto:
                self.problemas.append(Problema(True, "fila", f"fila {numero}: falta colegio, grado o texto"))
                continue
            if codigo not in sedes:
                self.problemas.append(
                    Problema(True, "colegio", f"fila {numero}: `{codigo}` no esta en colegios.csv")
                )
                continue

            try:
                orden = int((fila.get("orden") or "").strip())
            except ValueError:
                self.problemas.append(Problema(True, "orden", f"fila {numero}: orden no numerico"))
                continue
            # `uq_item_version_orden` lo impondria la base, pero lo haria
            # abortando la transaccion entera sin decir que dos filas del CSV
            # chocaron. Aqui se listan todas de una vez.
            if (codigo, grado, orden) in ordenes:
                self.problemas.append(
                    Problema(True, "orden", f"fila {numero}: {codigo} {grado} repite el orden {orden}")
                )
                continue
            ordenes.add((codigo, grado, orden))

            clave = (codigo, grado)
            if clave not in listas:
                listas[clave] = {
                    "id": id_lista(codigo, grado, self.anio),
                    "colegio_id": id_colegio(codigo),
                    "sede_id": id_sede(codigo, sedes[codigo]),
                    "grado": grado,
                    "anio_lectivo": self.anio,
                    "activa": True,
                }
                versiones[clave] = {
                    "id": id_version(codigo, grado, self.anio),
                    "lista_id": listas[clave]["id"],
                    "numero": 1,
                    # El texto crudo de la lista no se persiste aqui. La
                    # columna es `contenido_redactado` y el nombre no es
                    # decorativo: lo que va ahi tiene que haber pasado por la
                    # redaccion de nombres de menores. El corpus ya viene
                    # renglon a renglon, asi que no hace falta el volcado.
                    "contenido_redactado": None,
                    "hash_origen": None,
                    "vigente": True,
                    # SIN revisar, y es la decision de fondo de este cargador.
                    # Una version revisada no vuelve a abrirse y ya no puede
                    # salir a dar de alta lo que el catalogo no tiene.
                    "revisada_en": None,
                }

            if texto not in resueltos:
                concepto_id, _nombre, parecido = clasificar(texto, conceptos)
                resueltos[texto] = (
                    (concepto_id, parecido) if parecido >= UMBRAL_CONCEPTO else (None, parecido)
                )
            concepto_id, parecido = resueltos[texto]

            modo = normalizar_modo(fila.get("modo_adquisicion"))
            instruccion = instruccion_para(modo, fila.get("instruccion_colegio"))
            categoria = _texto(fila.get("categoria"))

            items.append(
                {
                    "id": id_item(codigo, grado, orden),
                    "version_id": versiones[clave]["id"],
                    "orden": orden,
                    "texto_original": texto,
                    "concepto_id": concepto_id,
                    "cantidad": cantidad_valida(fila.get("cantidad")),
                    # El corpus no transcribio la unidad del renglon y no se
                    # adivina del texto aqui: `item_unidad_valida` solo admite
                    # el vocabulario de `UnidadBase`, y nulo significa contar
                    # por pieza, que es lo correcto para la mayoria.
                    "unidad": None,
                    "tipo_item": normalizar_tipo(fila.get("tipo_item")),
                    "modo_adquisicion": modo,
                    "instruccion_colegio": instruccion,
                    "url_externa": _texto(fila.get("url_externa")),
                    # La categoria del corpus no tiene columna propia y no se
                    # inventa una: es la etiqueta con la que se transcribio,
                    # util para auditar de donde salio cada renglon, no un
                    # concepto ni un tipo.
                    "atributos": {"categoria": categoria} if categoria else {},
                    "confianza_normalizacion": round(parecido, 3),
                    # La restriccion `item_sin_concepto_va_a_revision` lo
                    # exige, y con razon: un renglon que nadie resolvio y que
                    # ademas nadie tiene que mirar desaparece del kit sin que
                    # el papa se entere de que falta algo.
                    "requiere_revision": concepto_id is None,
                }
            )

        self.total_items = len(items)
        self.sin_concepto = sum(1 for i in items if i["concepto_id"] is None)
        self._medir_carencias(items, conceptos)

        return {
            "lista_oficial": list(listas.values()),
            "version_lista_oficial": list(versiones.values()),
            "item_lista_oficial": items,
        }

    def _sedes(self) -> dict[str, str]:
        """Codigo de colegio -> nombre de su sede, leido de `colegios.csv`.

        Se lee el mismo fichero que siembra Identidad, y no se consulta a
        Identidad, porque el nombre de la sede solo hace falta para DERIVAR su
        identificador. Pedirlo por HTTP ataria la siembra del catalogo a que
        el otro servicio este arriba, para conseguir un dato que ya esta en el
        repositorio.
        """
        filas = leer_csv(self.dir / "colegios.csv")
        if not filas:
            self.problemas.append(
                Problema(True, "datos", f"no hay colegios.csv en {self.dir}: sin el no hay sede_id")
            )
        return {
            (f.get("codigo") or "").strip(): (f.get("sede_nombre") or "Sede unica").strip()
            for f in filas
            if (f.get("codigo") or "").strip()
        }

    def _medir_carencias(self, items: list[dict[str, Any]], conceptos: list[dict[str, Any]]) -> None:
        """Lo que falta para que estas listas se puedan responder con un kit.

        El orden es el de cuanto duelen. Un renglon sin concepto no se puede
        emparejar con ningun producto: es un hueco en el kit. Uno que Tukit no
        surte no es un hueco, es una linea informativa, y por eso se cuenta
        aparte aunque tampoco llegue al carrito.
        """
        total = len(items)
        if not total:
            return
        self.carencias["renglones sin concepto resuelto"] = (
            sum(1 for i in items if i["concepto_id"] is None),
            total,
        )
        self.carencias["renglones que Tukit no puede surtir"] = (
            sum(1 for i in items if i["modo_adquisicion"] not in VALORES_SURTIBLES),
            total,
        )
        self.carencias["renglones sin unidad declarada"] = (
            sum(1 for i in items if i["unidad"] is None),
            total,
        )
        if conceptos:
            pedidos = {str(i["concepto_id"]) for i in items if i["concepto_id"]}
            self.carencias["conceptos del catalogo que nadie pide"] = (
                sum(1 for c in conceptos if str(c["id"]) not in pedidos),
                len(conceptos),
            )

    # -- escritura --------------------------------------------------------

    async def escribir(self, datos: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        from sqlalchemy.dialects.postgresql import insert
        from tukit_comun.bd import crear_motor

        from .modelos import Base

        motor = crear_motor("catalogo")
        escritos: dict[str, int] = {}
        try:
            async with motor.engine.begin() as conexion:
                # El orden es el de las dependencias, que aqui son llaves
                # foraneas de verdad dentro de la misma base: no hay version
                # sin lista ni renglon sin version.
                for tabla in ("lista_oficial", "version_lista_oficial", "item_lista_oficial"):
                    filas = datos.get(tabla, [])
                    if not filas:
                        escritos[tabla] = 0
                        continue
                    objeto = Base.metadata.tables[tabla]
                    claves = [c.name for c in objeto.primary_key.columns]
                    for bloque in _en_bloques(filas, FILAS_POR_BLOQUE):
                        sentencia = insert(objeto).values(bloque)
                        # `ON CONFLICT DO UPDATE` sobre la llave primaria es lo
                        # que hace la siembra repetible: los identificadores se
                        # derivan del contenido, asi que la segunda corrida
                        # actualiza las mismas filas en vez de duplicarlas.
                        actualizables = {
                            c.name: sentencia.excluded[c.name]
                            for c in objeto.columns
                            if c.name not in claves and c.name in bloque[0]
                        }
                        if actualizables:
                            sentencia = sentencia.on_conflict_do_update(
                                index_elements=claves, set_=actualizables
                            )
                        else:
                            sentencia = sentencia.on_conflict_do_nothing()
                        await conexion.execute(sentencia)
                    escritos[tabla] = len(filas)
        finally:
            await motor.cerrar()
        return escritos


def _en_bloques(filas: list[dict[str, Any]], tamano: int):
    for inicio in range(0, len(filas), tamano):
        yield filas[inicio : inicio + tamano]


async def leer_conceptos() -> list[dict[str, Any]]:
    """El vocabulario contra el que se resuelve cada renglon.

    Se lee de la base y no del CSV curado porque la base es la que esta al
    dia: `descubrir --aprobar` crea conceptos que ningun CSV tiene, y resolver
    contra el fichero mandaria a revision renglones que el catalogo ya sabe
    reconocer. Es la misma fuente que usa `descubrir`, con la misma forma, para
    que el cargador y la revision clasifiquen igual.
    """
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            return [
                {"id": f.id, "nombre": f.nombre_canonico, "sinonimos": list(f.sinonimos or ())}
                for f in await conexion.execute(
                    select(concepto.c.id, concepto.c.nombre_canonico, concepto.c.sinonimos).where(
                        concepto.c.activo
                    )
                )
            ]
    finally:
        await motor.cerrar()


async def _principal(directorio: Path, anio: int, solo_validar: bool) -> int:
    # Los conceptos se leen tambien con `--solo-validar`. Es una lectura, no
    # una escritura, y sin ella el informe diria que el 100 % de los renglones
    # quedo sin concepto, que es el numero equivocado y ademas alarmante.
    conceptos = await leer_conceptos()
    print(f"Vocabulario activo del catalogo: {len(conceptos)} conceptos")

    cargador = Cargador(directorio, anio)
    datos = cargador.armar(conceptos)

    informe = Informe(
        escritos={t: len(f) for t, f in datos.items()},
        problemas=cargador.problemas,
        carencias=cargador.carencias,
    )

    if informe.bloqueado:
        print("No se escribio nada: hay filas que romperian las restricciones de la base.")
        informe.imprimir()
        return 1

    if not solo_validar:
        informe.escritos = await cargador.escribir(datos)

    informe.imprimir()

    total = cargador.total_items
    sin = cargador.sin_concepto
    pct = 100 * sin / total if total else 0
    print(f"\nRenglones sin concepto resuelto: {sin}/{total} ({pct:.1f}%)")
    print("No es un fallo: es lo que nuestro vocabulario todavia no cubre, y va a revision.")
    if solo_validar:
        print("\n(--solo-validar: no se escribio nada en la base)")
    else:
        print("Las versiones quedan SIN revisar: mira cuales con  --listas  de `descubrir`.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--datos", type=Path, default=Path("datos/listas"))
    analizador.add_argument("--anio", type=int, default=ANIO_POR_OMISION)
    analizador.add_argument("--solo-validar", action="store_true")
    args = analizador.parse_args()

    directorio = args.datos
    if not directorio.exists():
        print(f"No existe el directorio de datos: {directorio}")
        return 2

    return asyncio.run(_principal(directorio, args.anio, args.solo_validar))


if __name__ == "__main__":
    sys.exit(main())
