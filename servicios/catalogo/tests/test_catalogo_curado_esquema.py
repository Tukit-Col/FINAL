"""El catalogo curado entra en el esquema real: conceptos, curaduria y niveles.

La carga y su porque viven en `_ayudas_catalogo_curado`.
"""

# Los fixtures `catalogo` y `cargado` llegan de `_ayudas_catalogo_curado`.
# ruff: noqa: F811

from __future__ import annotations

import uuid

import pytest
from _ayudas_catalogo_curado import (  # noqa: F401  (los fixtures se reusan tal cual)
    cargado,
    catalogo,
    del_corpus,
)
from tukit_catalogo.cargador import CONCEPTOS_LIBRO
from tukit_catalogo.modelos import (
    CALIDAD_POR_NIVEL,
    Concepto,
    Nivel,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
)

# Los conceptos que admiten personaje: donde un nino de verdad pide Spiderman o
# Frozen. Arranco en 7 (CATALOGO_LIMPIO.md §2) y la curadora amplio la lista a 18
# desde el dashboard, admitiendo la personalizacion que el mercado si trae:
# lapiz/regla/esfero/pegante/resaltador/toallitas/delantal/rompecabezas/vaso/
# corrector/balon con personaje (Kiut, Barbie, Avengers, Hot Wheels, unicornio...).
# La BD manda sobre esta lista; el numero refleja lo que la curadora decidio.
CONCEPTOS_CON_PERSONAJE_ESPERADOS = 18


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
