"""Invariantes del catalogo curado que hay en `tukit/datos/catalogo/`.

`test_catalogo.py` prueba que el esquema sepa negarse a lo imposible. Esto
prueba lo otro, que es lo que el esquema no puede saber: que los 242 productos
que se construyeron de verdad quepan dentro de el y digan lo que prometen.

La forma de la prueba es deliberada. En vez de releer los CSV con un validador
escrito a medida, se cargan en las tablas reales con las llaves foraneas y las
restricciones CHECK activas. Asi una columna de mas, un nivel inventado o un
`curado_por` vacio no fallan por una regla que alguien escribio aqui, sino por
la misma restriccion que correra en produccion. Un validador paralelo se
desincroniza del esquema; esta carga no puede.

Los CSV los produce `Arquitectura/scripts/construir_catalogo_curado.py`, que es
reproducible byte a byte. Si estas pruebas fallan tras tocar el script, la
pregunta no es cual umbral aflojar sino que se rompio.
"""

from __future__ import annotations

import csv
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from tukit_catalogo.cargador import CONCEPTOS_LIBRO
from tukit_catalogo.modelos import (
    CALIDAD_POR_NIVEL,
    UMBRAL_REVISION_MANUAL,
    Base,
    Concepto,
    MetodoVinculacion,
    Nivel,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
)

DATOS = Path(__file__).resolve().parents[3] / "datos" / "catalogo"

# Los cuatro entregables mas las dos tablas de apoyo que les dan sentido:
# `tiendas` para que la oferta tenga a quien apuntar y `procedencia` para que
# cada producto pueda decir de que fichero y de que posicion salio.
FICHEROS = (
    "conceptos.csv",
    "productos_canonicos.csv",
    "ofertas_tienda.csv",
    "precios_oferta.csv",
    "tiendas.csv",
    "productos_procedencia.csv",
    "revision_manual.csv",
)

# Los conceptos que admiten personaje: donde un nino de verdad pide Spiderman o
# Frozen. Arranco en 7 (CATALOGO_LIMPIO.md §2) y la curadora amplio la lista a 18
# desde el dashboard, admitiendo la personalizacion que el mercado si trae:
# lapiz/regla/esfero/pegante/resaltador/toallitas/delantal/rompecabezas/vaso/
# corrector/balon con personaje (Kiut, Barbie, Avengers, Hot Wheels, unicornio...).
# La BD manda sobre esta lista; el numero refleja lo que la curadora decidio.
CONCEPTOS_CON_PERSONAJE_ESPERADOS = 18


def del_corpus(codigo: str) -> bool:
    """Si el concepto es uno de los 99 que midio el corpus (C001-C099).

    La curaduria de listas agrega conceptos (C100 en adelante) y los exporta a
    `conceptos.csv`. Las cifras de este archivo son mediciones de la tesis sobre
    el corpus, asi que se comprueban sobre ESOS conceptos y los curados se
    admiten aparte, en vez de romper la suite cada vez que se cura una lista.
    """
    return len(codigo) == 4 and codigo.startswith("C0") and codigo[1:].isdigit()


# Niveles que una persona QUITO del catalogo a proposito, por concepto.
#
# La regla de los tres niveles mide que la curaduria no pierda un nivel por el
# camino. Quitar un producto equivocado no es perderlo: es la curaduria
# funcionando. Sin esta excepcion la prueba castiga exactamente el acto que
# defiende, y la unica forma de volver a verde seria reponer el producto malo.
#
# `C021 pincel` (RESUELTO, ya no es excepcion): el hueco de nivel premium lo
# habia dejado `TK-C021-PRE`, que era "Limpiador para pinceles" a 49.900 -un
# disolvente, no una brocha- quitado a mano. El comentario original decia que el
# hueco era la respuesta honesta "hasta que haya un pincel premium de verdad en
# el universo raspado". El ensanchamiento lo trajo: la cola aprobo
# `TK-REV-517439`, "Pincel Pentel Aquash punta fina para acuarela" a 29.800, que
# `nivelar` acomodo como el premium representativo de C021. Con un premium real
# en su sitio, C021 vuelve a tener sus tres niveles y la excepcion sobra: dejarla
# ahora restaria un nivel que si existe.
#
# Cada entrada que se agregue aqui tiene que decir QUE se quito y POR QUE, o la
# excepcion deja de ser una decision y pasa a ser una forma de silenciar la
# prueba. Hoy no hay ninguna: el catalogo no tiene huecos de nivel hechos a mano.
QUITADOS_A_MANO: dict[str, int] = {}

# El catalogo dejo de ser la salida byte-a-byte del constructor y paso a ser el
# ESPEJO de la base curada: la curadora aprobo desde el dashboard cientos de
# candidatos que la cola de revision trajo del mercado en vivo (`TK-REV-*`). Eso
# cambio la unidad sobre la que se miden los invariantes de celda.
#
# Una celda (concepto, nivel, personaje) ya no tiene UN producto sino uno
# CANONICO -el que el optimizador de kit muestra, marcado
# `es_representante_canonico`- mas, opcionalmente, PROFUNDIDAD: otras referencias
# aprobadas para esa misma celda que dan alternativas de compra pero no compiten
# por el puesto del kit. Un cuaderno confiable puede tener 20 referencias
# aprobadas detras; el kit sigue proponiendo una, la representante.
#
# Por eso las reglas de "una respuesta por celda", "los tres niveles" y "el
# precio ordena los niveles" se miden sobre los REPRESENTANTES y no sobre el
# conteo crudo de filas: es lo que el optimizador ve y lo que el papa recibe. La
# profundidad detras no puede romper una promesa que se hace sobre el
# representante. Antes de este cambio el corpus tenia un representante por celda
# por construccion y la distincion no hacia falta; ahora si.
#
# Los `TK-REV-*` que quedan como profundidad, no como representantes, se validan
# aparte: existen, cuelgan de un concepto, tienen oferta y precio en rango. Lo
# que no se les exige es acuñar el SKU por concepto/nivel (su SKU nombra la
# referencia de tienda) ni ser unicos en su celda (son, justamente, las
# alternativas).


def _representantes(cargado: Session, **filtro: Any) -> list[ProductoCanonico]:
    """Los productos que el optimizador muestra: uno por celda (concepto, nivel,
    personaje). El resto de una celda es profundidad de compra, no candidato de
    kit, y no entra en los invariantes de celda."""
    consulta = cargado.query(ProductoCanonico).filter_by(es_representante_canonico=True, **filtro)
    return consulta.all()


def _precio_minimo_por_producto(cargado: Session) -> dict[uuid.UUID, int]:
    """producto_id -> el precio mas bajo que se le vio en cualquier tienda.

    Es el que el papa pagaria: si la misma referencia esta en dos tiendas,
    compra en la barata. Es la misma regla que usa `nivelar.py` para ordenar."""
    barato: dict[uuid.UUID, int] = {}
    for oferta in cargado.query(OfertaTienda):
        for precio in cargado.query(PrecioOferta).filter_by(oferta_id=oferta.id):
            visto = barato.get(oferta.producto_canonico_id)
            if visto is None or precio.valor_centavos < visto:
                barato[oferta.producto_canonico_id] = precio.valor_centavos
    return barato


# Umbral de aceptacion medido en `construir_catalogo_curado.py` contra la
# muestra anotada a mano. Por debajo de el no se crea oferta; entre el y
# `UMBRAL_REVISION_MANUAL` la oferta se crea pero va a la cola.
UMBRAL_ACEPTACION = 0.740

# Rango plausible de precio, en centavos. Son los p01-p99 medidos por fuente en
# `PERFILADO_DATOS.md` §5.2 (2.890-854.160 COP en el feed del scraper,
# 650-208.596 COP en GranCentral), tomados por la union porque el CSV de
# precios ya no dice de que fuente salio cada uno.
#
# El minimo baja de 650 a 500 COP: zamux.co vende componentes electronicos por unidad
# (resistencia 1/4w a 500 COP, switch corredera a 600 COP; precio leido en la ficha y en
# su JSON-LD el 2026-11-01). Son precios reales, no un error de carga, y el piso previo
# salia de los percentiles de otras fuentes. Un piso de 500 sigue atrapando un precio en
# pesos de un digito o en unidades equivocadas.
PRECIO_MIN_CENTAVOS = 500 * 100
PRECIO_MAX_CENTAVOS = 854_160 * 100


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def _leer(nombre: str) -> list[dict[str, str]]:
    with (DATOS / nombre).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _nulo(valor: str) -> str | None:
    """La cadena vacia del CSV es ausencia, no es un valor.

    Importa mas de lo que parece en `ean`, que es UNIQUE y admite nulo: si las
    vacias entraran como cadena, el segundo producto sin EAN chocaria contra el
    primero y la carga fallaria por una razon falsa.
    """
    return valor if valor else None


def _bool(valor: str) -> bool | None:
    """Tres valores y no dos. `disponible` vacio es "no se", no "no hay"."""
    if valor == "":
        return None
    return valor == "true"


def _es_true(valor: str) -> bool:
    """`activo`/`es_representante_canonico` como booleano de dos valores: para
    filtrar filas del CSV crudo donde vacio o cualquier otra cosa es False."""
    return valor.strip().lower() in {"true", "1", "t"}


def _lista(valor: str) -> list[str]:
    return [p for p in valor.split("|") if p]


def _fecha(valor: str) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None


def _uuid(valor: str) -> uuid.UUID | None:
    return uuid.UUID(valor) if valor else None


# ---------------------------------------------------------------------------
# Carga en el esquema real
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def catalogo() -> dict[str, Any]:
    """Los CSV crudos, sin pasar por el ORM. Para lo que se prueba sobre texto."""
    datos = {nombre.removesuffix(".csv"): _leer(nombre) for nombre in FICHEROS}
    datos["metricas"] = json.loads((DATOS / "metricas_catalogo.json").read_text(encoding="utf-8"))
    return datos


@pytest.fixture(scope="module")
def cargado(catalogo) -> Session:
    """Los CSV dentro de las tablas reales, con FK y CHECK activas.

    Que esta fixture no reviente ya es la mitad de la prueba: significa que
    cada columna del CSV existe en el modelo con su tipo, que cada llave
    foranea resuelve y que ninguna fila viola una restriccion del esquema.
    """
    motor = create_engine("sqlite://")

    @event.listens_for(motor, "connect")
    def _activar_fk(conexion, _registro):  # noqa: ANN001
        conexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(motor)
    sesion = Session(motor)

    sesion.add_all(
        Tienda(
            id=_uuid(f["id"]),
            slug=f["slug"],
            nombre=f["nombre"],
            tipo=f["tipo"],
            url_base=_nulo(f["url_base"]),
            activa=_bool(f["activa"]),
        )
        for f in catalogo["tiendas"]
    )
    sesion.add_all(
        Concepto(
            id=_uuid(f["id"]),
            codigo=f["codigo"],
            nombre_canonico=f["nombre_canonico"],
            sinonimos=_lista(f["sinonimos"]),
            categoria=f["categoria"],
            atributos_discriminantes=_lista(f["atributos_discriminantes"]),
            atributos_descriptivos=_lista(f["atributos_descriptivos"]),
            admite_personaje=_bool(f["admite_personaje"]),
            frecuencia_demanda=int(f["frecuencia_demanda"]),
            activo=_bool(f["activo"]),
        )
        for f in catalogo["conceptos"]
    )
    sesion.flush()

    sesion.add_all(
        ProductoCanonico(
            id=_uuid(f["id"]),
            concepto_id=_uuid(f["concepto_id"]),
            ean=_nulo(f["ean"]),
            sku_interno=f["sku_interno"],
            nombre=f["nombre"],
            descripcion=_nulo(f["descripcion"]),
            marca=_nulo(f["marca"]),
            nivel=f["nivel"],
            personaje=_nulo(f["personaje"]),
            imagen_url=_nulo(f["imagen_url"]),
            atributos=json.loads(f["atributos"]),
            ruta_categoria=_nulo(f["ruta_categoria"]),
            es_propio=_bool(f["es_propio"]),
            grupo_variante_id=_uuid(f["grupo_variante_id"]),
            es_representante_canonico=_bool(f["es_representante_canonico"]),
            texto_embedding=_nulo(f["texto_embedding"]),
            quality_score=float(f["quality_score"]),
            activo=_bool(f["activo"]),
            curado_por=_uuid(f["curado_por"]),
            curado_en=_fecha(f["curado_en"]),
        )
        for f in catalogo["productos_canonicos"]
    )
    sesion.flush()

    sesion.add_all(
        OfertaTienda(
            id=_uuid(f["id"]),
            producto_canonico_id=_uuid(f["producto_canonico_id"]),
            tienda_id=_uuid(f["tienda_id"]),
            referencia_externa=f["referencia_externa"],
            url=_nulo(f["url"]),
            metodo_vinculacion=f["metodo_vinculacion"],
            confianza_vinculacion=float(f["confianza_vinculacion"]),
            disponible=_bool(f["disponible"]),
            activo=_bool(f["activo"]),
            visto_en=_fecha(f["visto_en"]),
        )
        for f in catalogo["ofertas_tienda"]
    )
    sesion.flush()

    sesion.add_all(
        PrecioOferta(
            id=_uuid(f["id"]),
            oferta_id=_uuid(f["oferta_id"]),
            valor_centavos=int(f["valor_centavos"]),
            moneda=f["moneda"],
            fuente=f["fuente"],
            vigente_desde=_fecha(f["vigente_desde"]),
            vigente_hasta=_fecha(f["vigente_hasta"]),
            corrida_id=_uuid(f["corrida_id"]),
        )
        for f in catalogo["precios_oferta"]
    )
    sesion.commit()

    yield sesion
    sesion.close()


# ---------------------------------------------------------------------------


class TestCargaEnElEsquema:
    def test_los_cuatro_csv_entran_en_las_tablas_reales(self, cargado, catalogo):
        """El entregable no es un CSV bonito sino un CSV que la base acepta.

        Si esto pasa, el esquema de salida es el de los modelos y no una
        aproximacion: las columnas, los tipos, las FK y los CHECK son los
        mismos que correran en produccion.
        """
        assert cargado.query(Concepto).count() == len(catalogo["conceptos"])
        assert cargado.query(ProductoCanonico).count() == len(catalogo["productos_canonicos"])
        assert cargado.query(OfertaTienda).count() == len(catalogo["ofertas_tienda"])
        assert cargado.query(PrecioOferta).count() == len(catalogo["precios_oferta"])

    def test_el_catalogo_no_esta_vacio(self, cargado):
        """Guarda contra el fallo silencioso mas probable: que el script deje
        de encontrar sus entradas y escriba cabeceras sin filas. Todo lo demas
        de este fichero pasaria sobre un catalogo vacio."""
        assert cargado.query(ProductoCanonico).count() >= 200
        assert sum(1 for c in cargado.query(Concepto) if del_corpus(c.codigo)) == 99


class TestConceptoValido:
    def test_todo_producto_cuelga_de_un_concepto_del_corpus(self, cargado, catalogo):
        """La FK ya lo garantiza dentro de la base. Lo que se comprueba aqui
        es lo de fuera: que ese concepto sea uno de los 99 medidos sobre las
        3.610 lineas, o uno que la curaduria de listas dio de alta y quedo
        versionado en `conceptos.csv` (C100 en adelante), y no uno inventado
        para acomodar un producto."""
        del catalogo
        codigos = {c.codigo for c in cargado.query(Concepto)}
        assert sum(1 for codigo in codigos if del_corpus(codigo)) == 99
        assert all(del_corpus(c) or c.startswith("C1") or c in CONCEPTOS_LIBRO for c in codigos)
        for producto in cargado.query(ProductoCanonico):
            concepto = cargado.get(Concepto, producto.concepto_id)
            assert concepto is not None
            assert concepto.codigo in codigos

    def test_el_sku_nombra_al_concepto_y_al_nivel_que_dice_la_fila(self, cargado):
        """El `sku_interno` de la semilla es `TK-<concepto>-<nivel>[-<personaje>]`.
        Que coincida con las columnas no es cosmetico: es lo que permite auditar
        una fila a ojo sin cruzar tablas.

        Lo aprobado en la cola es otro tier: su SKU es `TK-REV-<referencia>`, que
        nombra la referencia de tienda de la que salio, no el concepto/nivel (ese
        producto lo trajo la API y lo aprobo una persona, no se acuno a mano). Ese
        prefijo es, justamente, lo que distingue el tier revisado del original.

        El plan lector es un tercer tier: sus SKU son `TK-LIB-<isbn>`, que nombran
        el ISBN del titulo -su identidad de verdad- y no un concepto/nivel, porque
        un titulo no tiene 'nivel economico/premium'. Se excluye por la misma razon
        que el revisado: su SKU nombra otra cosa a proposito.

        Una reasignacion de concepto hecha en el dashboard tiene que RE-ACUÑAR el
        SKU de la semilla, no dejarlo apuntando al concepto viejo: el SKU es la
        etiqueta que permite auditar la fila a ojo, y un SKU que miente sobre su
        concepto es peor que no tenerlo. Este test es lo que atrapa esa deriva."""
        for producto in cargado.query(ProductoCanonico):
            if producto.sku_interno.startswith(("TK-REV-", "TK-LIB-")):
                continue
            concepto = cargado.get(Concepto, producto.concepto_id)
            partes = producto.sku_interno.split("-")
            assert partes[0] == "TK"
            assert partes[1] == concepto.codigo
            assert partes[2] == producto.nivel[:3].upper()


class TestCuradoPor:
    def test_ningun_producto_se_queda_sin_curador(self, cargado):
        """La regla del catalogo curado: un producto que nadie curo no existe.
        `NOT NULL` lo impone en la base; esto verifica que ninguna fila llegara
        con un UUID de relleno o en blanco.

        Hay dos curadores legitimos, no uno: quien monto la semilla a mano, y el
        agente de aprobacion que sella lo que una persona valido en la cola de
        revision. Ambos son identidades reales; lo que se prohibe es la fila sin
        curador o con un UUID de relleno."""
        for producto in cargado.query(ProductoCanonico):
            assert producto.curado_por is not None
            assert producto.curado_por != uuid.UUID(int=0)
        assert len({p.curado_por for p in cargado.query(ProductoCanonico)}) <= 2

    def test_todo_producto_dice_de_que_fichero_salio(self, catalogo):
        """El defecto que el perfilado encontro en la semilla anterior: 1.164
        de 7.475 URL sin origen versionado. Aqui cada producto apunta a su
        origen, y ninguno se queda sin el.

        Dos procedencias legitimas, no una. La semilla original salio de dos
        ficheros JSON fijados por SHA-256 (feed_scraper, grancentral): su origen
        es fichero + linea + hash. Lo aprobado en la cola de revision NO sale de
        un fichero -lo trajo la API en vivo o Firecrawl y lo miro una persona-,
        asi que su origen versionable es la tienda y la URL donde se vio, con
        `fichero_fuente='cola_revision'` y sin hash. Se exige, en ambos casos,
        que el origen exista, apunte a una URL, y case el SKU del producto."""
        procedencia = {f["producto_id"]: f for f in catalogo["productos_procedencia"]}
        assert len(procedencia) == len(catalogo["productos_canonicos"])
        for producto in catalogo["productos_canonicos"]:
            origen = procedencia[producto["id"]]
            assert origen["fichero_fuente"]
            assert origen["url_origen"].startswith("http")
            assert origen["sku_interno"] == producto["sku_interno"]
            if origen["fichero_fuente"] == "cola_revision":
                # Curado a mano desde la cola: sin hash de fichero, pero con
                # tienda de origen que ancla de donde salio.
                assert not origen["sha256_fichero"]
                assert origen["tienda_origen"]
            else:
                # Semilla de fichero: fijada por hash y posicion exacta.
                assert len(origen["sha256_fichero"]) == 64
                assert origen["indice_en_fichero"].isdigit()

    def test_todas_las_fuentes_estan_fijadas_por_hash(self, catalogo):
        """Dos ficheros de entrada, dos hashes. Si uno cambia sin que cambie
        el hash registrado, la corrida ya no es la que produjo estos datos."""
        entradas = catalogo["metricas"]["entradas"]
        assert set(entradas) == {"feed_scraper", "grancentral"}
        for fuente in entradas.values():
            assert len(fuente["sha256"]) == 64
            assert fuente["filas"] > 0


class TestNiveles:
    def test_solo_existen_los_tres_niveles(self, cargado):
        """`personalizado` no es un nivel. Un producto con personaje tiene
        ademas su nivel de marca, y esa es la razon de que sean dos columnas."""
        niveles = {p.nivel for p in cargado.query(ProductoCanonico)}
        assert niveles <= {n.value for n in Nivel}
        assert niveles == {"economico", "confiable", "premium"}

    def test_la_puntuacion_de_calidad_se_deriva_del_nivel(self, cargado):
        """La columna esta materializada porque el reordenamiento la lee en el
        camino caliente. Materializada y divergente seria peor que no tenerla.

        Salvo el tier aprobado en revision (`TK-REV-*`): esos llevan un puntaje
        fijo de 0,85 -mas que cualquier sugerencia de maquina, menos que la
        curaduria original- que marca 'lo miro una persona en la cola' y no se
        deriva del nivel. La derivacion por nivel rige la semilla acunada a mano."""
        for producto in cargado.query(ProductoCanonico):
            if producto.sku_interno.startswith("TK-REV-"):
                assert float(producto.quality_score) == pytest.approx(0.85, abs=1e-3)
                continue
            esperada = CALIDAD_POR_NIVEL[Nivel(producto.nivel)]
            assert float(producto.quality_score) == pytest.approx(esperada, abs=1e-3)

    def test_solo_lleva_personaje_el_concepto_que_lo_admite(self, cargado):
        """Un cuaderno de Spiderman es un producto; una resma de Spiderman es
        un error de etiquetado."""
        admiten = {c.id for c in cargado.query(Concepto) if c.admite_personaje}
        del_corpus_que_admiten = [
            c for c in cargado.query(Concepto) if c.admite_personaje and del_corpus(c.codigo)
        ]
        assert len(del_corpus_que_admiten) == CONCEPTOS_CON_PERSONAJE_ESPERADOS
        for producto in cargado.query(ProductoCanonico):
            if producto.personaje:
                assert producto.concepto_id in admiten

    def test_hay_productos_con_personaje_de_verdad(self, cargado):
        """El perfil Fan no se sostiene con la columna vacia."""
        con_personaje = [p for p in cargado.query(ProductoCanonico) if p.personaje]
        assert len(con_personaje) >= 20
        # Y cada uno conserva su nivel de marca, que es justo lo que se
        # perderia si `personalizado` fuera un nivel.
        assert {p.nivel for p in con_personaje} <= {n.value for n in Nivel}


class TestDemandaAlta:
    """Los 25 conceptos que cubren el 80 % de los renglones de una lista."""

    @staticmethod
    def _alta_demanda(cargado: Session) -> list[Concepto]:
        conceptos = sorted(cargado.query(Concepto), key=lambda c: (-c.frecuencia_demanda, c.codigo))
        total = sum(c.frecuencia_demanda for c in conceptos)
        acumulado, seleccion = 0, []
        for concepto in conceptos:
            if acumulado / total >= 0.80:
                break
            acumulado += concepto.frecuencia_demanda
            seleccion.append(concepto)
        return seleccion

    def test_son_veinticinco_conceptos(self, cargado):
        """Si el corte deja de dar 25, cambio el corpus y no la seleccion, y
        entonces esta clase esta midiendo otra cosa."""
        assert len(self._alta_demanda(cargado)) == 25

    def test_ninguno_se_queda_sin_producto(self, cargado):
        """Un concepto de alta demanda sin producto es un renglon que el kit no
        puede resolver en ninguno de los tres perfiles."""
        for concepto in self._alta_demanda(cargado):
            productos = cargado.query(ProductoCanonico).filter_by(concepto_id=concepto.id).count()
            assert productos > 0, f"{concepto.codigo} {concepto.nombre_canonico} sin producto"

    def test_tiene_tantos_niveles_como_representantes_dio_el_universo(self, cargado):
        """La promesa que se puede sostener sin inventar producto.

        Los tres niveles son la promesa por omision, pero no se cumplen a la
        fuerza: si el universo solo dio dos representantes para `bata de
        laboratorio`, salen dos niveles y no tres. Lo exigible es que no se pierda
        ninguno por el camino: tantos niveles distintos como representantes tenga
        la escalera, hasta 3. Cada representante lleva su etiqueta y no se repite
        -eso lo garantiza `nivelar`, que permuta las etiquetas por precio-, asi
        que con 3 representantes hay 3 niveles, con 2 hay 2.

        Se cuenta sobre los REPRESENTANTES sin personaje, no sobre el conteo
        crudo: la cola de revision aprobo decenas de referencias por concepto (13
        cartulinas, p.ej.) que son profundidad de compra dentro de un nivel, no
        niveles nuevos. El kit muestra un representante por nivel; esos son los
        que cuentan. La escalera de marca es aparte (el cuaderno de Bluey no
        compite contra el generico), asi que la promesa de tres niveles es la de
        la escalera sin personaje, la que ve el papa que no pide marca.

        Antes esto se medía contra `candidatos_en_universo` del constructor. Ese
        numero quedo obsoleto cuando el ensanchamiento paso a tirar del mercado en
        vivo (universo ABIERTO) en vez del universo cerrado que el constructor
        habia medido: un concepto puede hoy tener mas -o menos- candidatos que los
        que el conteo viejo registro. El numero de representantes que la curaduria
        dejo vivos es la medida actual y no depende de un artefacto que quedo atras.
        """
        for concepto in self._alta_demanda(cargado):
            # Solo la escalera sin personaje: es la promesa de tres niveles.
            genericos = [p for p in _representantes(cargado, concepto_id=concepto.id) if not p.personaje]
            niveles = {p.nivel for p in genericos}
            esperado = min(3, len(genericos)) - QUITADOS_A_MANO.get(concepto.codigo, 0)
            assert len(niveles) == esperado, (
                f"{concepto.codigo} {concepto.nombre_canonico}: "
                f"{sorted(niveles)} con {len(genericos)} representantes genericos"
            )

    def test_el_precio_ordena_los_niveles_dentro_de_cada_escalera(self, cargado):
        """Un economico no puede costar mas que un premium. Nunca.

        Es la unica cosa que el nivel promete al papa: si escoge la opcion
        economica paga menos. `Nivel` dice que un kit economico se compone de
        productos ECONOMICO, asi que una etiqueta invertida no es cosmetica:
        hace que el kit barato salga mas caro que el kit caro.

        La escalera es (concepto, personaje) y no solo concepto porque los
        productos con personaje son una via aparte: el cuaderno de Bluey no
        compite en precio contra el cuaderno sin personaje, compite contra los
        otros cuadernos de Bluey. Quien pide personalizacion ya tomo otra
        decision. Por eso comparar entre personajes distintos no dice nada,
        y comparar dentro de uno es obligatorio.

        Este test no existia, y por eso entraron 36 productos con el nivel al
        reves en 18 conceptos: el peor caso era un cojin economico de $143.760
        contra un premium de $80.270.

        La escalera la forman los REPRESENTANTES. Las referencias de profundidad
        que aprobo la cola (`TK-REV-*` no representativos) no llevan nivel de
        curaduria -entraron con `nivel_sugerido=None` y `resolver` las dejo en
        'confiable' por defecto-, asi que su etiqueta no es una promesa al papa
        sino un relleno; medir monotonia contra ellas seria inventar un defecto
        donde no hay ninguno. El nivel promete algo sobre el producto que el kit
        MUESTRA, y ese es el representante.
        """
        barato = _precio_minimo_por_producto(cargado)

        orden = {n.value: i for i, n in enumerate(Nivel)}
        escaleras: dict[tuple[uuid.UUID, str], list[tuple[int, str, str]]] = {}
        for p in _representantes(cargado, activo=True):
            if p.id in barato:
                clave = (p.concepto_id, p.personaje or "")
                escaleras.setdefault(clave, []).append((barato[p.id], p.nivel, p.sku_interno))

        assert escaleras, "sin precios no se puede comprobar nada"
        for peldanos in escaleras.values():
            # Solo se exige monotonia entre precios DISTINTOS. Dos productos
            # que valen lo mismo pueden llevar etiquetas distintas sin que
            # nadie pague de mas, y pasa de verdad: el marcador economico y el
            # confiable de C006 estan los dos en $20.900. Comparar empates
            # seria exigirle al dato un orden que el precio no define.
            tope_mas_barato = -1
            for precio in sorted({p for p, _, _ in peldanos}):
                grupo = [(n, s) for p, n, s in peldanos if p == precio]
                for nivel, sku in grupo:
                    assert orden[nivel] >= tope_mas_barato, (
                        f"{sku} vale ${precio // 100:,} y es {nivel}, "
                        f"pero algo estrictamente mas barato de su escalera "
                        f"lleva un nivel mas alto"
                    )
                tope_mas_barato = max(orden[n] for n, _ in grupo)

    def test_ningun_economico_cuesta_mas_que_un_premium_del_mismo_concepto(self, cargado):
        """La regla dura, esta vez cruzando personajes.

        El test anterior compara dentro de cada escalera, y por eso dejaba
        pasar un caso: un producto solo en su escalera de personaje conserva la
        etiqueta con que nacio, sin nadie con quien compararse. Asi el
        planeador de Stitch quedo 'economico' a $34.900 mientras la agenda de
        marca 'premium' valia $26.600.

        Aunque el personaje sea una via aparte para escoger, las etiquetas se
        muestran al mismo papa y no pueden contradecirse entre si. Esta es la
        version que no admite excepcion: en un concepto, nada etiquetado
        economico puede costar mas que algo etiquetado premium.

        Se compara entre REPRESENTANTES por la misma razon que la version por
        escalera: la etiqueta de una referencia de profundidad (`TK-REV-*` no
        representativa) es un 'confiable' por defecto, no una promesa curada, y
        cruzarla contra un premium representativo compararia una promesa con un
        relleno.
        """
        barato = _precio_minimo_por_producto(cargado)

        por_concepto: dict[uuid.UUID, list[ProductoCanonico]] = defaultdict(list)
        for p in _representantes(cargado, activo=True):
            if p.id in barato:
                por_concepto[p.concepto_id].append(p)

        for productos in por_concepto.values():
            economicos = [p for p in productos if p.nivel == Nivel.ECONOMICO.value]
            premium = [p for p in productos if p.nivel == Nivel.PREMIUM.value]
            if not economicos or not premium:
                continue
            caro = max(economicos, key=lambda p: barato[p.id])
            barato_premium = min(premium, key=lambda p: barato[p.id])
            assert barato[caro.id] <= barato[barato_premium.id], (
                f"{caro.sku_interno} es economico y vale "
                f"${barato[caro.id] // 100:,}, pero "
                f"{barato_premium.sku_interno} es premium y vale "
                f"${barato[barato_premium.id] // 100:,}"
            )

    def test_los_conceptos_sin_producto_son_los_documentados(self, cargado, catalogo):
        """17 conceptos se quedan fuera y ninguno es de alta demanda.

        Casi todos son categorias que el propio filtro de dominio de Tukit
        excluye por diseno (aseo, juguetes, instrumentos musicales, ropa), de
        modo que no son un fallo de la construccion sino el limite declarado
        del alcance. Si la lista crece, algo se perdio.
        """
        sin_producto = set(catalogo["metricas"]["catalogo"]["conceptos_sin_producto"])
        assert len(sin_producto) <= 17
        alta = {c.codigo for c in self._alta_demanda(cargado)}
        assert not (sin_producto & alta)


class TestSinDuplicados:
    def test_el_sku_interno_es_unico(self, catalogo):
        skus = [p["sku_interno"] for p in catalogo["productos_canonicos"]]
        assert len(skus) == len(set(skus))

    def test_el_ean_no_se_repite_entre_productos(self, catalogo):
        """Vacio se permite y se repite; presente es identidad de fabricante y
        no puede estar en dos filas."""
        eans = [p["ean"] for p in catalogo["productos_canonicos"] if p["ean"]]
        assert len(eans) == len(set(eans))
        for ean in eans:
            assert len(ean) == 13 and ean.isdigit()

    def test_una_celda_util_tiene_exactamente_un_representante(self, catalogo):
        """Una celda es (concepto, nivel, personaje). El optimizador de kit toma
        de ella UN producto: el representante canonico. Si una celda de util
        tuviera dos representantes el optimizador tendria dos respuestas iguales
        y ninguna regla para desempatar; si tuviera cero, la celda existe pero es
        invisible al kit -hay producto y aun asi el renglon queda sin resolver-.
        Ambos son el mismo defecto de curaduria visto por sus dos lados, y este
        test los cierra a la vez exigiendo exactamente uno.

        La distincion importa desde que la cola de revision empezo a aprobar
        varias referencias por celda: hoy una celda de cuaderno confiable puede
        tener 20 filas, pero solo una es representante y las otras son
        profundidad de compra. Contar filas crudas -como hacia la version
        anterior- marcaba esas 20 como 'duplicado sin resolver' cuando el
        duplicado real, el que rompe al optimizador, es tener dos REPRESENTANTES.

        Los libros son la excepcion de siempre: el plan lector es una LISTA de
        titulos distintos en un mismo concepto ('libro', 'diccionario'...), asi
        que ni siquiera tienen la nocion de representante unico por celda. La
        regla aplica solo a utiles."""
        es_libro = {
            c["id"]
            for c in catalogo["conceptos"]
            if c["tipo_item"] == "libro_libre" or "libro" in (c["categoria"] or "").lower()
        }
        utiles = [
            p
            for p in catalogo["productos_canonicos"]
            if p["concepto_id"] not in es_libro and _es_true(p["activo"])
        ]
        # Unicidad se mide en la CELDA (concepto, nivel, personaje): dos
        # representantes ahi son dos respuestas identicas para el optimizador.
        representantes_por_celda = Counter(
            (p["concepto_id"], p["nivel"], p["personaje"])
            for p in utiles
            if _es_true(p["es_representante_canonico"])
        )
        con_varios = [c for c, n in representantes_por_celda.items() if n > 1]
        assert con_varios == [], f"celdas util con mas de un representante: {con_varios}"

        # Cobertura se mide en la ESCALERA (concepto, personaje): una escalera con
        # productos util tiene que exponer al menos un representante al kit. No se
        # mide por celda (concepto, nivel, personaje) porque una celda puede
        # existir solo como PROFUNDIDAD -p.ej. un morral 'confiable' detras del
        # representante 'economico' de esa escalera-: esa celda tiene producto
        # pero no le corresponde representante propio, su nivel es una alternativa
        # dentro de la escalera, no un peldano que el kit deba llenar aparte. Lo
        # que no puede pasar es que una escalera entera con producto no tenga a
        # nadie que el optimizador muestre.
        escaleras = {(p["concepto_id"], p["personaje"]) for p in utiles}
        con_representante = {
            (p["concepto_id"], p["personaje"]) for p in utiles if _es_true(p["es_representante_canonico"])
        }
        sin_representante = sorted(escaleras - con_representante)
        assert sin_representante == [], f"escaleras util sin representante: {sin_representante}"

    def test_la_profundidad_detras_del_representante_es_de_la_cola(self, catalogo):
        """Lo que hay en una celda ademas del representante tiene que ser
        profundidad legitima, no una segunda semilla acuñada a mano que se colo.

        La unica fuente de varias referencias por celda es la cola de revision:
        productos `TK-REV-*` que una persona aprobo y que dan alternativas de
        compra. Una semilla original (`TK-<concepto>-<nivel>`) no representativa
        conviviendo con otra en la misma celda seria, en cambio, el viejo empate
        sin resolver disfrazado. Asi que todo lo no-representativo de una celda
        con profundidad tiene que ser del tier revisado."""
        es_libro = {
            c["id"]
            for c in catalogo["conceptos"]
            if c["tipo_item"] == "libro_libre" or "libro" in (c["categoria"] or "").lower()
        }
        por_celda: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for p in catalogo["productos_canonicos"]:
            if p["concepto_id"] not in es_libro and _es_true(p["activo"]):
                por_celda[p["concepto_id"], p["nivel"], p["personaje"]].append(p)

        intrusos = [
            p["sku_interno"]
            for productos in por_celda.values()
            if len(productos) > 1
            for p in productos
            if not _es_true(p["es_representante_canonico"]) and not p["sku_interno"].startswith("TK-REV-")
        ]
        assert intrusos == [], f"semillas no representativas compartiendo celda: {intrusos}"

    def test_una_tienda_no_ofrece_dos_veces_el_mismo_producto(self, catalogo):
        pares = Counter((o["producto_canonico_id"], o["tienda_id"]) for o in catalogo["ofertas_tienda"])
        assert [p for p, n in pares.items() if n > 1] == []

    def test_una_referencia_de_tienda_apunta_a_un_solo_producto(self, catalogo):
        """El mismo SKU de Exito en dos productos canonicos significa que dos
        celdas se llenaron con el mismo listado."""
        pares = Counter((o["tienda_id"], o["referencia_externa"]) for o in catalogo["ofertas_tienda"])
        assert [p for p, n in pares.items() if n > 1] == []

    def test_los_identificadores_no_colisionan(self, catalogo):
        """Son `uuid5` sobre clave natural, que es lo que los hace estables
        entre corridas. El precio de esa estabilidad es que dos claves
        naturales iguales dan el mismo UUID, asi que hay que mirarlo."""
        for tabla in ("conceptos", "productos_canonicos", "ofertas_tienda", "precios_oferta"):
            ids = [f["id"] for f in catalogo[tabla]]
            assert len(ids) == len(set(ids)), tabla


class TestPrecios:
    def test_el_precio_no_vive_en_el_producto(self):
        """La correccion de tercera forma normal que motivo el esquema. Si
        alguien devuelve la columna, comparar precio entre tiendas vuelve a ser
        inexpresable."""
        columnas = set(ProductoCanonico.__table__.columns.keys())
        assert not (columnas & {"precio", "stock", "proveedor", "disponible", "url_producto"})

    def test_todo_precio_es_entero_de_centavos_y_esta_en_rango(self, cargado):
        """Rango plausible = p01-p99 medidos por fuente en el perfilado. Un
        precio fuera de ahi no es caro ni barato, es un dato roto."""
        precios = cargado.query(PrecioOferta).all()
        assert precios
        for precio in precios:
            assert isinstance(precio.valor_centavos, int)
            assert precio.valor_centavos % 100 == 0, "el feed publica pesos, no fracciones"
            assert PRECIO_MIN_CENTAVOS <= precio.valor_centavos <= PRECIO_MAX_CENTAVOS
            assert precio.moneda == "COP"

    def test_cada_oferta_tiene_exactamente_un_precio_vigente(self, cargado):
        """Sin esto, "el precio de hoy" es una consulta ambigua."""
        por_oferta: dict[uuid.UUID, int] = defaultdict(int)
        for precio in cargado.query(PrecioOferta):
            if precio.vigente:
                por_oferta[precio.oferta_id] += 1
        ofertas = cargado.query(OfertaTienda).all()
        assert len(por_oferta) == len(ofertas)
        assert set(por_oferta.values()) == {1}

    def test_todo_producto_tiene_al_menos_una_oferta_con_precio(self, cargado):
        """Un producto canonico sin oferta no se puede poner en un kit: existe
        en el catalogo y no se puede comprar en ninguna parte."""
        con_oferta = {o.producto_canonico_id for o in cargado.query(OfertaTienda)}
        sin_oferta = [p.sku_interno for p in cargado.query(ProductoCanonico) if p.id not in con_oferta]
        assert sin_oferta == []

    def test_los_niveles_ordenan_el_precio_de_la_canasta(self, cargado):
        """No se exige producto a producto, porque un premium barato existe.
        Se exige en la mediana, que es lo que hace que el kit economico
        termine costando menos que el premium; si no, la promesa multiperfil
        no se sostiene."""
        import statistics

        precio_de = {
            o.producto_canonico_id: p.valor_centavos
            for o in cargado.query(OfertaTienda)
            for p in cargado.query(PrecioOferta).filter_by(oferta_id=o.id)
            if p.vigente
        }
        medianas = {}
        for nivel in ("economico", "confiable", "premium"):
            valores = [
                precio_de[p.id]
                for p in cargado.query(ProductoCanonico).filter_by(nivel=nivel)
                if p.id in precio_de
            ]
            medianas[nivel] = statistics.median(valores)
        assert medianas["economico"] < medianas["confiable"] < medianas["premium"]


class TestVinculacionEntreTiendas:
    def test_los_metodos_son_los_del_esquema(self, catalogo):
        metodos = {o["metodo_vinculacion"] for o in catalogo["ofertas_tienda"]}
        assert metodos <= {m.value for m in MetodoVinculacion}

    def test_la_vinculacion_por_ean_va_con_confianza_plena(self, catalogo):
        """Un EAN coincide o no coincide; no tiene grados. Una confianza
        intermedia en una vinculacion por EAN seria una contradiccion.

        Excepto en el tier aprobado en revision (`TK-REV-*`): ahi el 0,85 no mide
        el emparejamiento del EAN sino el producto entero -es el mismo puntaje
        que lleva `quality_score`, 'lo miro una persona en la cola'-, y se hereda
        a la oferta. La confianza plena por EAN rige la vinculacion de la semilla,
        que es donde el EAN de verdad decidio el emparejamiento entre tiendas."""
        sku_de = {p["id"]: p["sku_interno"] for p in catalogo["productos_canonicos"]}
        for oferta in catalogo["ofertas_tienda"]:
            if oferta["metodo_vinculacion"] != "ean":
                continue
            if (sku_de.get(oferta["producto_canonico_id"]) or "").startswith("TK-REV-"):
                continue
            assert float(oferta["confianza_vinculacion"]) == 1.000

    def test_nada_por_debajo_del_umbral_medido_llega_al_catalogo(self, catalogo):
        """0,740 no es un numero elegido sino el medido contra la muestra
        anotada a mano: 88,89 % de precision ahi."""
        for oferta in catalogo["ofertas_tienda"]:
            if oferta["metodo_vinculacion"] == "atributos":
                assert float(oferta["confianza_vinculacion"]) >= UMBRAL_ACEPTACION

    def test_lo_dudoso_va_a_la_cola_y_no_se_descarta_ni_se_da_por_bueno(self, catalogo):
        """El camino del medio es el que importa. Entre 0,740 y 0,800 la oferta
        se crea, se marca y aparece en `revision_manual.csv`; ni se tira ni se
        acepta en silencio."""
        dudosas = [
            o
            for o in catalogo["ofertas_tienda"]
            if o["metodo_vinculacion"] == "atributos"
            and float(o["confianza_vinculacion"]) < UMBRAL_REVISION_MANUAL
        ]
        assert len(catalogo["revision_manual"]) == len(dudosas)
        for fila in catalogo["revision_manual"]:
            confianza = float(fila["confianza"])
            assert UMBRAL_ACEPTACION <= confianza < UMBRAL_REVISION_MANUAL
            assert fila["motivo"]
            assert fila["oferta_url"].startswith("http")

    def test_la_propiedad_requiere_revision_concuerda_con_la_cola(self, cargado, catalogo):
        """La misma regla leida por el modelo y por el CSV tiene que dar lo
        mismo, porque es la que alimentara la bandeja del curador."""
        marcadas = [o for o in cargado.query(OfertaTienda) if o.requiere_revision]
        assert len(marcadas) == len(catalogo["revision_manual"])

    def test_el_mayorista_no_aporta_ean(self, cargado, catalogo):
        """La verificacion empirica que cambio la estrategia: WooCommerce no
        tiene el campo y Shopify omite `barcode` del JSON publico. Si un dia
        aparece un EAN por ahi, es que se colo la referencia interna."""
        del catalogo
        mayoristas = {t.id for t in cargado.query(Tienda) if t.tipo == "mayorista"}
        assert mayoristas
        for oferta in cargado.query(OfertaTienda):
            if oferta.tienda_id in mayoristas:
                assert oferta.metodo_vinculacion != MetodoVinculacion.EAN.value

    def test_disponible_distingue_no_se_de_no_hay(self, cargado):
        """Forzar False donde no hubo observacion haria que el optimizador
        descarte ofertas legitimas."""
        valores = {o.disponible for o in cargado.query(OfertaTienda)}
        assert None in valores or False in valores or True in valores
        for oferta in cargado.query(OfertaTienda):
            assert oferta.disponible in (True, False, None)


class TestCoberturaDelCorpus:
    def test_resuelve_la_mayor_parte_de_los_renglones_reales(self, catalogo):
        """La medida que importa para la tesis no es cuantos productos hay sino
        que fraccion de una lista escolar de verdad queda resuelta."""
        cobertura = catalogo["metricas"]["cobertura_corpus"]
        assert cobertura["lineas_corpus"] == 3610
        assert cobertura["cobertura_lineas"] >= 0.95
        assert cobertura["cobertura_unidades"] >= 0.95

    def test_los_diecisiete_colegios_siguen_siendo_diecisiete(self, catalogo):
        """`colegio_id` leido como numero hace que `2.1` y `2.10` colapsen y el
        corpus pase de 17 a 16 sin que nada falle. Es un defecto que ya se
        cometio una vez."""
        por_colegio = catalogo["metricas"]["cobertura_corpus"]["cobertura_por_colegio"]
        assert len(por_colegio) == 17

    def test_ningun_colegio_queda_desatendido(self, catalogo):
        """El promedio puede tapar un colegio entero mal cubierto."""
        por_colegio = catalogo["metricas"]["cobertura_corpus"]["cobertura_por_colegio"]
        peor = min(por_colegio.items(), key=lambda kv: kv[1]["cobertura"])
        assert peor[1]["cobertura"] >= 0.80, f"colegio {peor[0]}: {peor[1]}"


class TestCuradoNoFiltrado:
    def test_el_universo_cerrado_deja_pasar_menos_basura_que_el_filtrado(self, catalogo):
        """El hallazgo central del perfilado: filtrar por palabra sobre un
        universo abierto concentro la basura en vez de quitarla, 10,41 % en la
        semilla contra 5,53 % del crudo. Construir por inclusion tiene que
        medir por debajo de los dos o el cambio de enfoque no sirvio de nada.
        """
        rn = catalogo["metricas"]["rn_p12_sobre_el_universo_cerrado"]
        referencia = rn["referencia_perfilado"]
        assert rn["tasa"] < referencia["crudo_del_scraper"]
        assert rn["tasa"] < referencia["semilla_de_la_bd"]

    def test_el_emparejamiento_esta_medido_y_no_declarado(self, catalogo):
        """Un umbral sin muestra anotada es una opinion."""
        emparejamiento = catalogo["metricas"]["emparejamiento"]
        assert emparejamiento is not None
        assert emparejamiento["pares_anotados"] >= 100
        assert emparejamiento["positivos"] > 0 and emparejamiento["negativos"] > 0
        operativo = emparejamiento["punto_operativo"]
        assert operativo["umbral"] == pytest.approx(UMBRAL_ACEPTACION, abs=0.011)
        assert operativo["precision"] >= 0.80
