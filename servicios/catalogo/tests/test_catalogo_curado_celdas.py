"""Una respuesta por celda (concepto, nivel, personaje), con los tres niveles y sin duplicados."""

# Los fixtures `catalogo` y `cargado` llegan de `_ayudas_catalogo_curado`.
# ruff: noqa: F811

from __future__ import annotations

import uuid
from collections import Counter, defaultdict

from _ayudas_catalogo_curado import (  # noqa: F401  (los fixtures se reusan tal cual)
    _es_true,
    _precio_minimo_por_producto,
    _representantes,
    cargado,
    catalogo,
)
from sqlalchemy.orm import Session
from tukit_catalogo.modelos import (
    Concepto,
    Nivel,
    ProductoCanonico,
)

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
