"""Llena los huecos del catalogo: conceptos sin producto y niveles sin opcion.

Un hueco es un renglon de la lista que el kit no puede responder. Diecisiete
conceptos no tenian NINGUN producto, asi que diecisiete cosas que los colegios
piden simplemente no aparecian en el carrito. Otros cuarenta y seis tenian uno
o dos niveles: con un solo producto no hay kit Ahorrador ni kit Premium, hay
el mismo kit tres veces.

Los productos salen de la API de catalogo de VTEX, que Exito y Panamericana
publican y que devuelve nombre, precio, existencias, EAN e imagen de una sola
consulta. No hace falta raspar HTML.

Lo dificil no es traer productos sino traer los CORRECTOS. Preguntarle `gel
antibacterial` a Exito devuelve primero una garrafa de veinte litros a 172.000
pesos, y `rompecabezas` a Panamericana devuelve uno de mil piezas. Los dos son
gel antibacterial y rompecabezas de verdad, y los dos son una respuesta
absurda para una lista de primaria. Por eso cada concepto trae su consulta y
su rango de precio escritos a mano: es la curaduria que separa un catalogo
utilizable de seiscientos tipos de block.

Lo que se cargue aqui entra con `quality_score` bajo a proposito. Son
sugerencias de una maquina, no decisiones de una persona, y el administrador
tiene que poder distinguirlas en la cola de revision.

Esto es CURADURIA y no parte de responderle a un papa. Corre aparte, antes de
que exista alguien preguntando, y por eso puede salir a la red sin la puerta
de `descubrir.exigir_sin_revisar`. La regla del sistema no cambia: el match
del acudiente corre siempre contra nuestra base, y si algo no esta, se agrega
por aqui y se revisa ANTES de que un papa lo vea. Un test en
`test_descubrir.py` impide que el modulo del acudiente importe este.

Hay dos modos. El de por defecto tapa HUECOS: recorre los conceptos, y para el
que le falta un nivel encola a lo sumo tres productos, uno por nivel. El de
`--surtir CODIGO[,CODIGO...]` ENSANCHA: para conceptos que ya estan llenos encola
el abanico completo -tipos, marcas, paquetes- con el nivel sin asignar, para que
la curadora lo reparta en la cola. Es como se traen los paquetes de cartulina,
las temperas surtidas o las variantes de cuaderno que el llenado de huecos nunca
mira por estar ya completos.

Uso:

    python -m tukit_catalogo.completar --solo-validar
    python -m tukit_catalogo.completar
    python -m tukit_catalogo.completar --surtir C010,C051,C029 --solo-validar
    python -m tukit_catalogo.completar --surtir C003,C006,C010,C014,C020,C022
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from .cargador import _uuid_estable

# Cuanto puede costar razonablemente cada cosa en una lista escolar, en pesos.
# El tope no es un detalle de afinacion: es lo que impide que el catalogo
# ofrezca la garrafa industrial cuando el colegio pidio un frasco.
#
# (consulta, minimo, maximo)
CONSULTAS: dict[str, tuple[str, int, int]] = {
    "C024": ("bata laboratorio escolar", 20000, 120000),
    "C025": ("tabla periodica escolar", 1000, 30000),
    "C026": ("calculadora cientifica escolar", 15000, 150000),
    "C032": ("resma papel carta", 8000, 60000),
    "C033": ("palitos de paleta manualidades", 1500, 25000),
    "C038": ("lana madeja ovillo", 2000, 30000),
    "C040": ("toallas humedas panitos", 3000, 30000),
    # `tabla picado` en Grancentral trae la que el colegio pide con su nombre
    # exacto: "Tabla Picado Con Tablero Acrilico Octavo Motivo Para Ninos" a
    # $9.500, que es la de doble uso del corpus. El tope de 20.000 deja fuera
    # las tablas de COCINA de las minoristas, que en Colombia tambien se
    # llaman tabla de picado y cuestan $21.630 y $36.979. Por eso no separaba
    # el rango de 40.000 que tenia antes.
    "C046": ("tabla picado", 3000, 20000),
    # El corpus pide "1 metro de lentejuelas de colores" y Grancentral lo
    # vende literalmente asi: "Paquete Lentejuelas x9 Colores (Metro por
    # Color)" a $5.750. Las minoristas no lo tienen; lo que devuelven ante
    # `lentejuelas` son renos y cascanueces con traje de lentejuelas.
    "C043": ("lentejuelas", 2000, 20000),
    # `refuerzo hojas` en vez de `reforzadores`. Con dos palabras cae en
    # "Paquete De Refuerzo Para Hojas Perforadas X350 Stickers" a $4.500, que
    # es la cosa, y no en las carpetas de yute con refuerzo en tela, que
    # comparten la palabra y son otro producto.
    "C055": ("refuerzo hojas", 1000, 15000),
    "C047": ("algodon", 1500, 25000),
    # `punzon` a secas devuelve los tres punzones escolares de verdad, y el
    # tope de 6.000 deja fuera lo que comparte la palabra sin ser la cosa: un
    # termometro de cocina con punzon de temperatura ($20.990) y un kit de
    # auriculoterapia ($39.999). La consulta que fallaba era `punzon punta
    # metalica`, que no devuelve nada en ninguna de las dos tiendas.
    "C073": ("punzon", 1000, 6000),
    # El corpus dice "regleta del mapa de Colombia", y con esa redaccion las
    # tres opciones aparecen: la plantilla acrilica, el mapa troquelado y el
    # foamy educativo. El tope de 10.000 descarta las gorras de la seleccion,
    # que es lo que trae `mapa colombia` sin acotar.
    "C099": ("plantilla mapa colombia", 1500, 10000),
    # El corpus dice "espumas para lavar loza", no "esponja". Con esa redaccion
    # aparece la esponja doble uso, que es la cosa. El tope de 12.000 descarta
    # los dispensadores de jabon con portaesponja, que cuestan el doble y son
    # otro producto. `esponjilla` traeria lana de acero, que sirve para lo
    # mismo pero no es lo que el colegio escribio.
    "C097": ("esponja lavar loza", 2000, 12000),
    "C048": ("biblia catolica letra grande", 60000, 400000),
    "C054": ("juego didactico educativo ninos", 10000, 90000),
    "C056": ("rompecabezas infantil 100 piezas", 8000, 70000),
    "C057": ("vaso plastico", 3000, 40000),
    "C060": ("curvigrafo", 3000, 45000),
    "C062": ("guantes desechables caja", 5000, 50000),
    "C063": ("gafas natacion", 8000, 95000),
    "C066": ("flauta dulce soprano", 15000, 90000),
    "C068": ("ojos moviles manualidades", 1500, 20000),
    # Redefinidos: "kit de artes" es temperas+pinceles, no los cuadros de
    # pintar por numeros que tenia; "kit de tecnologia" es electronica/arduino,
    # no las USB. El quinto filtro (`_coincide`) exige TODAS las palabras en el
    # nombre, y con tres ("kit tempera pincel") casi nada casa aunque las
    # tiendas tengan decenas de sets de arte; con dos ("set arte") entran los
    # kits de temperas/pinceles reales. Igual "protoboard" a secas trae los
    # kits de electronica/arduino, no las USB que se acaban de sacar.
    "C070": ("set arte", 8000, 90000),
    "C071": ("protoboard", 8000, 150000),
    "C072": ("lazo saltar cuerda", 5000, 45000),
    "C074": ("balon futbol", 20000, 120000),
    "C075": ("bolsa basura rollo", 3000, 35000),
    "C077": ("cojin infantil", 15000, 90000),
    "C078": ("fichas bibliograficas", 2000, 25000),
    "C079": ("pandereta instrumento percusion", 10000, 90000),
    "C080": ("jabon liquido manos", 3000, 35000),
    "C081": ("abaco escolar", 8000, 70000),
    "C084": ("gel antibacterial 500 ml", 3000, 35000),
    "C087": ("pilas alcalinas AA", 4000, 45000),
    "C088": ("pintura facial", 5000, 50000),
    "C089": ("pompones manualidades", 2000, 25000),
    "C090": ("separadores hojas indice", 2000, 25000),
    "C092": ("tablero de dibujo tecnico", 15000, 120000),
    "C093": ("tinta china dibujo", 5000, 50000),
    "C095": ("arena decorativa manualidades", 2000, 25000),
    "C096": ("copitos algodon", 2000, 20000),
    "C098": ("plastico burbuja rollo", 5000, 60000),
    # --- Conceptos con genericos en solo uno o dos niveles ---------------
    # Muchos de estos tenian el nivel "tapado" por productos de personaje
    # (una cartuchera de Frozen no es el generico economico), que ahora no
    # cuentan para cubrir el nivel. Las consultas apuntan al articulo neutro,
    # y el rango deja fuera la basura que se colo antes: en pincel, el
    # "limpiador para pinceles" y el oleo; en regla, la de tablero gigante.
    # Consultas CORTAS a proposito: el quinto filtro (`_coincide`) exige que
    # TODAS las palabras esten en el nombre, asi que "cartuchera escolar dos
    # cierres" da cero y "cartuchera" da seis. Se calibro cada una probando
    # cuantos candidatos reales devuelve antes de fijarla.
    "C002": ("lapiz negro", 500, 20000),
    "C008": ("regla", 1000, 15000),
    "C009": ("cartuchera", 5000, 60000),
    "C012": ("esfero", 500, 20000),
    "C016": ("pegante barra", 1500, 20000),
    "C021": ("pincel", 1500, 25000),
    "C027": ("tempera", 2000, 40000),
    "C030": ("acetato", 1000, 25000),
    "C039": ("resaltador", 1500, 25000),
    "C049": ("delantal", 10000, 60000),
    "C050": ("lienzo", 5000, 70000),
    "C059": ("corrector", 1500, 20000),
    "C061": ("aserrin", 1500, 20000),
    "C091": ("sobre manila", 500, 15000),
    # Morral ESCOLAR, no universitario: el generico que habia eran morrales de
    # PC 14"/15". `morral escolar` acota al de nino y el tope de 90.000 deja
    # fuera los porta-laptop. Los morrales de personaje (Minnie, Spiderman) ya
    # cubren la personalizacion y no se tocan.
    "C086": ("morral escolar", 20000, 90000),
}

# --- Ensanchamiento (`--surtir`) -------------------------------------------
#
# `CONSULTAS` tapa HUECOS: una consulta por concepto, y solo si le falta un
# nivel. Eso deja el catalogo con tres opciones por concepto y ni una mas.
# `SURTIDO` es lo contrario: para un concepto que YA esta lleno, trae el abanico
# -tipos, marcas, presentaciones- para que la curadora escoja en la cola. Varias
# consultas por concepto, cada una calibrada (1-2 palabras, porque el quinto
# filtro exige que TODAS esten en el nombre) y sondeada contra la API real antes
# de fijarla. Se surten las tres tiendas (Exito y Panamericana por VTEX,
# Grancentral por Shopify).
SURTIDO: dict[str, list[tuple[str, int, int]]] = {
    # Consumibles que el papa compra por PAQUETE (ver CONCEPTOS_PAQUETE): la
    # consulta trae sueltos y paquetes mezclados y el filtro de empaque prefiere
    # el paquete.
    "C003": [("block iris", 2000, 20000), ("block cuadriculado", 3000, 40000)],  # block
    "C006": [
        ("marcador borrable", 3000, 30000),
        ("marcador permanente", 2000, 30000),
        ("marcador sharpie", 3000, 40000),
        ("marcador pelikan", 2000, 30000),
    ],  # marcador (mas marcas: Sharpie, Pelikan)
    "C012": [
        ("esfero bic", 500, 20000),
        ("esfero kilometrico", 500, 20000),
        ("esfero gel", 1000, 25000),
        ("esfero paper mate", 1000, 25000),
    ],  # esfero (mas marcas: BIC, Kilometrico, gel, Paper Mate)
    "C004": [
        ("colores prismacolor", 8000, 90000),
        ("colores norma", 5000, 60000),
        ("crayones crayola", 3000, 40000),
        ("colores faber", 8000, 90000),
    ],  # colores/crayones (mas marcas: Prismacolor, Norma, Crayola, Faber)
    "C010": [("cartulina escolar", 2000, 20000)],  # cartulina (pliego da 0; escolar x10/x20 si)
    "C014": [
        ("papel seda", 1000, 20000),
        ("papel crepe", 1000, 20000),
        ("papel silueta", 1000, 20000),
        ("papel kraft", 1000, 25000),
    ],  # papel
    "C020": [("vinilo acrilico", 2000, 40000), ("vinilo escolar", 3000, 40000)],  # vinilo
    "C022": [("plastilina pelikan", 3000, 30000), ("plastilina barra", 2000, 30000)],  # plastilina
    "C027": [("pintura oleo", 5000, 60000), ("oleo", 5000, 60000)],  # pintura (repone oleo premium)
    "C029": [("foamy", 3000, 40000)],  # foamy (escarchado/octavo/carta, x10)
    "C038": [("lana madeja", 2000, 30000)],  # lana
    "C051": [("tempera", 3000, 60000)],  # tempera (Bozetto/Pelikan/Art Rangers)
    # No-consumibles: variedad por tipo/marca, sin preferencia de paquete.
    "C001": [("cuaderno cosido", 5000, 30000), ("cuaderno argollado", 8000, 45000)],  # cuaderno
    "C039": [("resaltador kiut", 5000, 30000), ("resaltador pastel", 3000, 30000)],  # resaltador
    # `morral infantil` repone el generico (porta-PC borrados); `morral disney`
    # es para PERSONALIZACION: Disney es la unica franquicia recuperable a las 4
    # anclas (cuaderno/cartuchera/carpeta/maleta) -- solo le faltaba la maleta y
    # el mercado si la tiene (Moana, Princess). Las demas franquicias
    # incompletas (lego/minecraft/jurassic/snoopy/halo) NO se surten: el mercado
    # no tiene sus carpetas ni maletas, y sin las 4 anclas no entran a
    # personalizacion.
    "C086": [("morral infantil", 30000, 130000), ("morral disney", 25000, 150000)],  # maleta
    # Kit de tecnologia: Exito es la que surte electronica de verdad (en
    # Panamericana "arduino" es un libro). VTEX consulta ambas igual; el rango
    # deja pasar kits reales.
    "C071": [("kit electronica", 20000, 150000), ("protoboard", 5000, 150000), ("arduino", 15000, 400000)],
}

# Conceptos cuyo generico honesto es un PAQUETE, no una unidad suelta. El papa no
# compra "una cartulina": compra el paquete x10. Cuando una consulta trae sueltos
# y paquetes mezclados, para estos conceptos se prefiere el paquete (unidades>1).
# Se apoya en `extraccion.extraer_empaque`, que ya sabe leer "x12 unidades" como
# conteo y "100 hojas"/"250 g" como medida, y es consciente del concepto.
CONCEPTOS_PAQUETE = frozenset({"C010", "C051", "C020", "C029", "C022", "C038", "C014"})

# Lo que Tukit NO deberia intentar vender aunque la lista lo pida.
#
# `muda de ropa` aparece cinco veces en el corpus y el impulso es buscarle
# producto. Es un error: el colegio pide que el nino traiga una muda suya, no
# que los papas compren una. Ofrecer una camiseta es no haber entendido el
# renglon. Va como linea informativa, con la instruccion del colegio y sin
# precio.
# Conceptos que ninguna consulta razonable resuelve, y que por eso NO se
# automatizan. Se dejan como hueco declarado en vez de llenarlos con lo
# primero que devuelva la tienda:
#
# - C055 reforzadores: ni `refuerzos adhesivos` ni `reforzador hojas`
#   devuelven nada en ninguna de las dos tiendas.
# - C043 lentejuelas: las dos tiendas solo venden cosas DECORADAS con
#   lentejuelas (vestido, morral, cojin, peluche) y mostacillas, que son otra
#   manualidad. Las lentejuelas por metro que pide la lista no estan.
# - C035 material singapur: cero resultados con `cubos conectores`,
#   `base ten blocks`, `counters matematicas` y `fichas fraccion`. Es material
#   didactico especializado que estas dos tiendas no manejan.
# - C069 plantilla de borrar: solo reglas de escala y una tableta magica de
#   juguete. El escudo de borrar de dibujo tecnico no aparece.
# - C046 tabla de picado: los dos productos correctos existen, la tabla de
#   picado y punzado a $14.490 y el tablero acrilico con tabla a $50.800, pero
#   ENTRE esos dos precios las tiendas venden tablas de COCINA: picadora a
#   $21.630 y acero inoxidable a $36.979. En Colombia una tabla de cocina
#   tambien se llama "tabla de picado", asi que ni el rango ni la palabra
#   separan. Necesita que una persona escoja las dos referencias a mano.
#
# C083 "frasco" salio de esta lista: se fusiono con C057 "vaso o plato" (los
# frascos que la lista pide son vasitos para mezclar pintura), asi que ya no es
# un hueco propio.
SIN_CONSULTA_FIABLE = ("C035", "C069")

# Esta lista tenia el doble de entradas y se acorto por una razon que conviene
# dejar escrita, porque el defecto era nuestro y no del mercado.
#
# C073 punzon y C099 regleta salieron al sondear con la redaccion exacta del
# corpus en vez del nombre canonico: `punzon` a secas y `plantilla mapa
# colombia` devuelven los tres niveles reales cada uno.
#
# C043 lentejuelas, C055 reforzadores y C046 tabla de picado salieron al
# agregar a Grancentral, que llevaba meses en la base como "dominio caido"
# cuando lo caido era la URL que teniamos guardada. Mientras estuvo mal, esto
# consulto dos tiendas creyendo que consultaba tres, las dos minoristas, y
# ninguna surte papeleria de manualidad al detal. Dimos por inexistente lo que
# no habiamos preguntado. Los tres estan en Grancentral con el nombre que usa
# el colegio, entre $4.500 y $9.500.
#
# Queda de esa tanda una leccion sobre el metodo, no sobre el surtido: un
# sondeo que pide seis resultados y mira cinco no distingue "no lo tiene" de
# "no lo alcance a ver".

# Los tres que quedan salieron despues de MIRAR lo que la consulta proponia, y
# son un buen retrato de como falla una busqueda por texto:
#
# - C083 frasco   -> `frasco para pintura` trajo brochas: van juntos en la
#                    misma estanteria y no son lo mismo.
# - C069 plantilla-> una tableta de dibujo magica de juguete. Grancentral tiene
#                    plantillas de ovulos y de circulos para dibujo tecnico a
#                    $6.200, pero el corpus pide la de BORRAR, que es un
#                    escudo metalico y es otra cosa; ponerla seria hacer pasar
#                    una por la otra.
# - C035 singapur -> un cuaderno de actividades de Minecraft. Es material
#                    didactico de una editorial y no papeleria.
#
# Ninguno lo habria detectado un filtro de precio ni un umbral de similitud:
# todos son productos reales, con foto y con existencias, dentro del rango. Lo
# que falla es el significado, y por eso estos van a curaduria humana en vez
# de entrar con puntaje bajo.

NO_SE_SURTE = {
    "C067": "El colegio pide una muda de ropa del nino. No hay que comprarla: se manda una que ya tenga.",
}

# El filtro de palabras vive en `tiendas` porque lo necesitan las dos
# plataformas: Shopify lo usa como su unica busqueda, al no tener endpoint de
# relevancia, y VTEX lo usa para corregir el suyo.
from .tiendas import _coincide  # noqa: E402

_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

TIENDAS = (("exito", "www.exito.com"), ("panamericana", "www.panamericana.com.co"))


@dataclass(frozen=True)
class Candidato:
    tienda: str
    nombre: str
    precio_cop: int
    imagen_url: str
    url: str
    ean: str | None
    sku: str
    marca: str | None


def buscar(host: str, consulta: str, cuantos: int = 24, intentos: int = 3) -> list[dict[str, Any]]:
    """Consulta el catalogo de una tienda, con reintento.

    El reintento no es precaucion de manual: la primera version lanzaba seis
    consultas a la vez y las tiendas devolvian vacio a casi todas. Parecia que
    no tenian el producto, y lo que pasaba es que estaban limitando el ritmo.
    `pilas alcalinas AA` daba cero en paralelo y veinticinco candidatos en
    serie. Un vacio silencioso por exceso de prisa se confunde con un hueco
    real del catalogo, que es el peor modo de fallar para esta herramienta.
    """
    direccion = (
        f"https://{host}/api/catalog_system/pub/products/search"
        f"?ft={urllib.parse.quote(consulta)}&_from=0&_to={cuantos - 1}"
    )
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(direccion, headers=_NAVEGADOR), timeout=25
            ) as respuesta:
                datos = json.loads(respuesta.read())
            if isinstance(datos, list) and datos:
                return datos
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass
        if intento < intentos - 1:
            time.sleep(1.5 * (intento + 1))
    return []


def a_candidatos(
    slug: str,
    crudos: list[dict[str, Any]],
    minimo: int,
    maximo: int,
    consulta: str = "",
) -> list[Candidato]:
    """Filtra lo que no sirve antes de que llegue al catalogo.

    Las cinco condiciones son las que distinguen un producto ofrecible de uno
    que solo llena una casilla:

    - CON EXISTENCIAS, porque un kit que contiene algo agotado no es un kit.
    - CON IMAGEN, porque el papa reconoce el producto por la foto.
    - DENTRO DEL RANGO, que es la curaduria de verdad: descarta la garrafa de
      veinte litros sin tener que enumerar cada caso.
    - PRECIO POSITIVO, porque VTEX devuelve cero cuando el articulo no se
      vende en linea, y un cero se propaga al total del kit como si fuera
      gratis.
    - CON TODAS LAS PALABRAS DE LA CONSULTA en el nombre. Esta es la ultima y
      se agrego tarde, con las cuatro anteriores puestas y pasando: ante
      `tabla picado` entro un cuchillo de cocina a $11.057, y ante `esponja
      lavar loza` entraron un lavaloza AXION y un tapete para grifo. Los tres
      tienen existencias, foto, precio en rango y son productos reales; lo que
      no tienen es la palabra. El ranking de la tienda premia el parecido
      parcial porque su negocio es que compres algo, no exactamente eso.
    """
    salida = []
    for crudo in crudos:
        if consulta and not _coincide(crudo.get("productName") or "", consulta):
            continue
        for articulo in crudo.get("items", []):
            vendedores = articulo.get("sellers") or []
            if not vendedores:
                continue
            oferta = vendedores[0].get("commertialOffer") or {}
            precio = int(oferta.get("Price") or 0)
            if precio <= 0 or not (minimo <= precio <= maximo):
                continue
            if (oferta.get("AvailableQuantity") or 0) <= 0:
                continue
            imagenes = articulo.get("images") or []
            if not imagenes:
                continue
            salida.append(
                Candidato(
                    tienda=slug,
                    nombre=crudo.get("productName") or articulo.get("name") or "",
                    precio_cop=precio,
                    imagen_url=imagenes[0].get("imageUrl", ""),
                    url=crudo.get("link") or "",
                    ean=(articulo.get("ean") or None),
                    sku=str(articulo.get("itemId") or ""),
                    marca=crudo.get("brand") or None,
                )
            )
            break  # un articulo por producto: las variantes de color no son opciones distintas
    return salida


def candidatos_shopify(slug: str, consulta: str, minimo: int, maximo: int) -> list[Candidato]:
    """Lo mismo que `buscar` + `a_candidatos`, para las tiendas de Shopify.

    Grancentral no es VTEX y no tiene el endpoint de busqueda, asi que su
    consulta vive en `tiendas`, que baja el catalogo entero y filtra en casa.
    Aqui solo se vuelven a aplicar las cuatro condiciones de arriba, que son de
    negocio y no de plataforma: con existencias, con imagen, dentro del rango y
    con precio positivo.
    """
    from .tiendas import buscar as buscar_tienda

    salida = []
    for oferta in buscar_tienda(slug, consulta):
        if oferta.precio_cop <= 0 or not (minimo <= oferta.precio_cop <= maximo):
            continue
        if not oferta.disponible or not oferta.imagen_url:
            continue
        salida.append(
            Candidato(
                tienda=slug,
                nombre=oferta.nombre,
                precio_cop=oferta.precio_cop,
                imagen_url=oferta.imagen_url,
                url=oferta.url,
                ean=oferta.ean,
                sku=oferta.sku,
                marca=oferta.marca,
            )
        )
    return salida


def repartir_en_niveles(candidatos: list[Candidato], faltan: set[str]) -> dict[str, Candidato]:
    """Escoge un producto por cada nivel que falte, separandolos por precio.

    Se ordena por precio y se toman los cuantiles, no los extremos. El mas
    barato de una busqueda suele ser un accesorio suelto y el mas caro un
    empaque institucional; los dos desvirtuan el abanico que el papa ve.

    Tambien se exige que los elegidos sean distintos entre si: tres niveles
    con el mismo producto a tres precios no es una eleccion, es ruido.
    """
    if not candidatos:
        return {}
    ordenados = sorted(candidatos, key=lambda c: c.precio_cop)
    posicion = {
        "economico": ordenados[len(ordenados) // 6],
        "confiable": ordenados[len(ordenados) // 2],
        "premium": ordenados[min(len(ordenados) - 1, (5 * len(ordenados)) // 6)],
    }
    elegidos: dict[str, Candidato] = {}
    usados: set[str] = set()
    precios_usados: set[int] = set()
    for nivel in ("economico", "confiable", "premium"):
        if nivel not in faltan:
            continue
        preferido = posicion[nivel]
        if preferido.nombre in usados:
            alternativa = next((c for c in ordenados if c.nombre not in usados), None)
            if alternativa is None:
                continue
            preferido = alternativa
        # Dos lanas del mismo precio en distinto color no son dos niveles: son
        # la misma opcion pintada de otro modo. Llamar premium a algo que
        # cuesta igual que el confiable le miente al papa sobre para que sirve
        # elegir, y le quita sentido al abanico entero.
        if preferido.precio_cop in precios_usados:
            continue
        elegidos[nivel] = preferido
        usados.add(preferido.nombre)
        precios_usados.add(preferido.precio_cop)
    return elegidos


def consultar_tiendas(
    consulta: str,
    minimo: int,
    maximo: int,
    tiendas: dict[str, uuid.UUID],
    ya_ofrecidos: set[tuple[str, str]],
) -> list[Candidato]:
    """Trae candidatos de las tres tiendas para una consulta, ya filtrados.

    Los conceptos van de uno en uno y las tiendas en paralelo. Repartir los
    conceptos entre varios hilos parecia mas rapido y salia peor: las tiendas
    limitaban el ritmo y respondian vacio, que aqui se lee igual que "no existe
    el producto". Se consultan las dos VTEX (Exito, Panamericana) y Grancentral
    (Shopify) a la vez, y se descarta lo que ya esta en el catalogo por
    (tienda, referencia).
    """
    with ThreadPoolExecutor(max_workers=3) as par:
        vtex = par.map(
            lambda t: a_candidatos(t[0], buscar(t[1], consulta), minimo, maximo, consulta),
            TIENDAS,
        )
        # Grancentral es mayorista y es la que tiene lo que las dos minoristas
        # no: lentejuelas por metro, reforzadores para hojas perforadas, la
        # tabla de picado con acrilico. Se consulta aparte porque es Shopify, no
        # porque valga menos.
        shopify = par.submit(candidatos_shopify, "grancentral", consulta, minimo, maximo)
        por_tienda = [*vtex, shopify.result()]
    # Una referencia de tienda que ya esta en el catalogo no se vuelve a traer.
    # La base lo impide con un indice unico sobre (tienda, referencia), y con
    # razon: el mismo articulo de la misma tienda no es una opcion nueva. Suele
    # pasar cuando dos conceptos vecinos comparten resultados de busqueda.
    return [
        c
        for grupo_tienda in por_tienda
        for c in grupo_tienda
        if (str(tiendas[c.tienda]), c.sku) not in ya_ofrecidos
    ]


def _a_propuesta(
    codigo: str,
    info: dict[str, Any],
    c: Candidato,
    tiendas: dict[str, uuid.UUID],
    nivel: str | None,
) -> dict[str, Any]:
    """Arma la fila de `propuesta_producto` a partir de un candidato.

    Un candidato NO es un producto: es una propuesta que espera a que una
    persona la mire. Antes se insertaba directo en el catalogo con calidad 0,4,
    y el efecto era el que el quinto filtro no atrapa: una poinsettia entraba
    como lentejuela y un lavaloza como esponja, sin que nadie lo viera, y el papa
    lo recibia como parte del kit. La cola de revision es donde el administrador
    aprueba lo bueno -y ahi nace el producto curado- o lo descarta.

    `nivel` es el nivel_sugerido. En el llenado de huecos viene fijo (el reparto
    ya decidio economico/confiable/premium); al ENSANCHAR viene None, porque el
    abanico se le muestra a la curadora para que ella asigne el nivel al aprobar
    -- `resolver` lo resuelve a "confiable" si sigue vacio.
    """
    return {
        "id": _uuid_estable("sugerido", codigo, c.tienda, c.sku),
        "concepto_id": info["id"],
        "concepto_sugerido": None,
        # El renglon contra el que se compara en la pantalla de revision. Aqui no
        # hay una lista de colegio detras -esto es curaduria adelantada-, asi que
        # el "pedido" es el propio concepto que se esta surtiendo.
        "texto_origen": info["nombre"],
        "tienda_id": tiendas[c.tienda],
        "referencia_externa": c.sku,
        "url": c.url or None,
        "nombre": c.nombre[:512],
        "marca": c.marca,
        "ean": c.ean if (c.ean or "").isdigit() and len(c.ean or "") in (8, 12, 13) else None,
        "imagen_url": c.imagen_url,
        "precio_centavos": c.precio_cop * 100,
        "disponible": True,
        # La ficha cruda no la traemos del listado, pero el nombre basta: al
        # aprobar, `resolver` saca empaque y atributos del nombre igual que lo
        # hacia esta funcion.
        "especificaciones": {},
        "nivel_sugerido": nivel,
        # Bajo a proposito. Lo eligio una consulta con un rango de precio, no una
        # persona que miro la lista del colegio. El administrador ordena su cola
        # por esto y los ve primero.
        "puntaje": 0.4,
        "estado": "pendiente",
        "origen": "scraper",
        "version_lista_id": None,
        "item_lista_id": None,
    }


def _preferir_paquetes(candidatos: list[Candidato], attrs: tuple[str, ...]) -> list[Candidato]:
    """Deja primero los PAQUETES cuando el papa compra por paquete.

    Para consumibles (`CONCEPTOS_PAQUETE`) el generico honesto es el paquete
    x10/x12, no la unidad suelta: nadie compra "una cartulina". Se lee cuantas
    unidades trae el nombre con `extraer_empaque` -que es consciente del concepto
    y sabe que "100 hojas" describe pero "x10 unds" cuenta- y, si hay candidatos
    con unidades>1, se descartan los sueltos. Si TODOS son sueltos, se dejan:
    mejor mostrar una unidad que dejar el renglon vacio. Orden final: paquete mas
    grande primero, y a igual tamano el mas barato.
    """
    from .extraccion import extraer_empaque

    con_empaque = [(extraer_empaque(c.nombre, attrs).unidades, c) for c in candidatos]
    paquetes = [par for par in con_empaque if par[0] > 1]
    escogidos = paquetes or con_empaque
    escogidos.sort(key=lambda par: (-par[0], par[1].precio_cop))
    return [c for _, c in escogidos]


async def _estado() -> tuple[
    dict[str, dict[str, Any]], dict[str, set[str]], dict[str, uuid.UUID], set[tuple[str, str]]
]:
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    producto = Base.metadata.tables["producto_canonico"]
    tienda = Base.metadata.tables["tienda"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            conceptos = {
                f.codigo: {
                    "id": f.id,
                    "nombre": f.nombre_canonico,
                    "attrs": tuple(f.atributos_discriminantes or ()) + tuple(f.atributos_descriptivos or ()),
                }
                for f in await conexion.execute(
                    select(
                        concepto.c.codigo,
                        concepto.c.id,
                        concepto.c.nombre_canonico,
                        concepto.c.atributos_discriminantes,
                        concepto.c.atributos_descriptivos,
                    )
                )
            }
            # Solo los GENERICOS cuentan para "este nivel ya esta cubierto". Un
            # producto de personaje (Spiderman, Frozen) es una opcion de
            # personalizacion, no el kit base: si una cartuchera tiene 13
            # personajes en economico pero ningun generico, el nivel economico
            # sigue vacio para el papa que no personaliza. Contarlos taparia el
            # hueco y dejaria conceptos sin kit base de tres niveles.
            niveles: dict[str, set[str]] = {}
            for f in await conexion.execute(
                select(producto.c.concepto_id, producto.c.nivel).where(producto.c.personaje.is_(None))
            ):
                niveles.setdefault(str(f.concepto_id), set()).add(f.nivel)
            tiendas = {f.slug: f.id for f in await conexion.execute(select(tienda.c.slug, tienda.c.id))}
            oferta = Base.metadata.tables["oferta_tienda"]
            ya_ofrecidos = {
                (str(f.tienda_id), f.referencia_externa)
                for f in await conexion.execute(select(oferta.c.tienda_id, oferta.c.referencia_externa))
            }
    finally:
        await motor.cerrar()
    return conceptos, niveles, tiendas, ya_ofrecidos


async def _encolar_candidatos(propuestas: list[dict[str, Any]], tipos_item) -> int:
    """Deja los candidatos en la cola de revision, no en el catalogo.

    Este es el cambio de fondo. Antes esta funcion escribia en las tres capas
    del catalogo (`producto_canonico`, `oferta_tienda`, `precio_oferta`) y una
    sugerencia de maquina quedaba, de hecho, como producto ofrecible: el papa
    podia recibirla sin que nadie la mirara. Ahora escribe en
    `propuesta_producto`, que es la cola que `descubrir --pendientes` lista y
    `descubrir --aprobar` resuelve. Un candidato solo se vuelve producto cuando
    una persona lo aprueba, y ahi nace curado (calidad 0,85, SKU `TK-REV-`).

    El `no_comprar` se marca igual que antes: es una decision de curaduria
    sobre el concepto, no un candidato, asi que va sobre `concepto` directamente.
    """
    from sqlalchemy import bindparam, update
    from sqlalchemy.dialects.postgresql import insert
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    motor = crear_motor("catalogo")
    encoladas = 0
    try:
        async with motor.engine.begin() as conexion:
            if propuestas:
                tabla = Base.metadata.tables["propuesta_producto"]
                # `on_conflict_do_nothing` sobre la llave (tienda, referencia):
                # correr `completar` dos veces no vuelve a proponer lo mismo, y
                # -mas importante- no resucita algo que ya se rechazo. La
                # decision del administrador manda sobre la corrida siguiente.
                resultado = await conexion.execute(
                    insert(tabla)
                    .values(propuestas)
                    .on_conflict_do_nothing(constraint="uq_propuesta_referencia")
                )
                encoladas = resultado.rowcount or 0
            if tipos_item:
                concepto = Base.metadata.tables["concepto"]
                await conexion.execute(
                    update(concepto)
                    .where(concepto.c.codigo == bindparam("cod"))
                    .values(tipo_item=bindparam("tipo")),
                    tipos_item,
                )
    finally:
        await motor.cerrar()
    return encoladas


async def _principal(solo_validar: bool) -> int:
    conceptos, niveles, tiendas, ya_ofrecidos = await _estado()

    pendientes = []
    for codigo, (consulta, minimo, maximo) in CONSULTAS.items():
        info = conceptos.get(codigo)
        if info is None:
            print(f"  aviso: el concepto {codigo} ya no existe, se omite")
            continue
        faltan = {"economico", "confiable", "premium"} - niveles.get(str(info["id"]), set())
        if faltan:
            pendientes.append((codigo, info, consulta, minimo, maximo, faltan))

    print(f"Conceptos con huecos: {len(pendientes)}. Consultando las tres tiendas...")

    def todas_las_tiendas(consulta: str, minimo: int, maximo: int) -> list[Candidato]:
        return consultar_tiendas(consulta, minimo, maximo, tiendas, ya_ofrecidos)

    resultados = []
    for indice, (codigo, info, consulta, minimo, maximo, faltan) in enumerate(pendientes, 1):
        candidatos = todas_las_tiendas(consulta, minimo, maximo)
        resultados.append((codigo, info, faltan, repartir_en_niveles(candidatos, faltan), len(candidatos)))
        avance = f"[{indice:2}/{len(pendientes)}]"
        print(f"  {avance} {codigo} {info['nombre'][:22]:24} {len(candidatos):3} candidatos")
        time.sleep(0.4)

    propuestas = []
    cerrados = parciales = vacios = 0

    for codigo, info, faltan, elegidos, cuantos in resultados:
        if not elegidos:
            vacios += 1
            print(f"  {codigo:6} {info['nombre'][:24]:26} SIN CANDIDATOS ({cuantos} vistos, fuera de rango)")
            continue
        if len(elegidos) == len(faltan):
            cerrados += 1
        else:
            parciales += 1

        for nivel, c in elegidos.items():
            print(f"      {nivel:10} ${c.precio_cop:>7}  {c.nombre[:52]}")
            propuestas.append(_a_propuesta(codigo, info, c, tiendas, nivel))

    tipos = [{"cod": c, "tipo": "no_comprar"} for c in NO_SE_SURTE if c in conceptos]

    print("\n=== huecos ===")
    print(f"  conceptos con candidatos para los 3 niveles  {cerrados}")
    print(f"  con candidatos a medias                      {parciales}")
    print(f"  sin ningun candidato aceptable               {vacios}")
    print(f"  candidatos encolados para revision           {len(propuestas)}")
    print(f"  conceptos marcados como no surtibles         {len(tipos)}")

    if solo_validar:
        print("\n(--solo-validar: no se escribio nada)")
        return 0

    encoladas = await _encolar_candidatos(propuestas, tipos)
    print(f"\nEncolado. {encoladas} candidatos nuevos en la cola de revision.")
    print("Revisalos con  make bd-revisar  /  python -m tukit_catalogo.descubrir --pendientes")
    return 0


async def _surtir(codigos: list[str], tope: int, solo_validar: bool) -> int:
    """Ensancha conceptos que YA estan llenos: encola el ABANICO, no 3 picks.

    `_principal` tapa huecos -salta el concepto lleno y encola a lo sumo tres
    productos, uno por nivel-. Eso deja el catalogo correcto pero angosto: una
    cartulina, una tempera, un cuaderno. Aqui es al reves: para los codigos
    dados se ignora si ya tiene los tres niveles y se encola TODO lo que pasa el
    rango y el quinto filtro, con `nivel_sugerido=None` para que la curadora
    asigne el nivel al aprobar. Asi la cola le muestra la variedad -tipos,
    marcas, presentaciones- y ella arma el abanico a mano.

    Para los consumibles (`CONCEPTOS_PAQUETE`) se prefieren los PAQUETES sobre
    las unidades sueltas. `tope` corta cuantos candidatos se encolan por consulta
    para no inundar la cola.
    """
    conceptos, _niveles, tiendas, ya_ofrecidos = await _estado()

    codigos = [c.upper() for c in codigos]
    desconocidos = [c for c in codigos if c not in SURTIDO]
    if desconocidos:
        print(f"  aviso: sin consultas de surtido para {', '.join(desconocidos)}; se omiten")
    a_surtir = [c for c in codigos if c in SURTIDO]
    if not a_surtir:
        print("Nada que surtir: ninguno de los codigos tiene consultas en SURTIDO.")
        return 1

    print(f"Ensanchando {len(a_surtir)} conceptos. Consultando las tres tiendas...")

    propuestas: dict[Any, dict[str, Any]] = {}
    for codigo in a_surtir:
        info = conceptos.get(codigo)
        if info is None:
            print(f"  aviso: el concepto {codigo} ya no existe, se omite")
            continue
        for consulta, minimo, maximo in SURTIDO[codigo]:
            candidatos = consultar_tiendas(consulta, minimo, maximo, tiendas, ya_ofrecidos)
            if codigo in CONCEPTOS_PAQUETE:
                candidatos = _preferir_paquetes(candidatos, info["attrs"])
            else:
                candidatos = sorted(candidatos, key=lambda c: c.precio_cop)
            recortados = candidatos[:tope]
            print(
                f"  {codigo:6} {info['nombre'][:20]:22} '{consulta}': "
                f"{len(candidatos):3} candidatos, encolo {len(recortados)}"
            )
            for c in recortados:
                # Un mismo SKU puede aparecer en dos consultas del concepto (p.ej.
                # 'vinilo acrilico' y 'vinilo escolar'). Se deduplica por id
                # estable para no encolarlo dos veces en esta corrida; la BD ya
                # frena repeticiones entre corridas via `on_conflict_do_nothing`.
                fila = _a_propuesta(codigo, info, c, tiendas, None)
                propuestas.setdefault(fila["id"], fila)
            time.sleep(0.4)

    filas = list(propuestas.values())
    print(f"\n=== ensanchamiento ===\n  candidatos unicos encolables  {len(filas)}")

    if solo_validar:
        print("\n(--solo-validar: no se escribio nada)")
        return 0

    encoladas = await _encolar_candidatos(filas, [])
    print(f"\nEncolado. {encoladas} candidatos nuevos en la cola de revision.")
    print("Revisalos con  make bd-revisar  /  python -m tukit_catalogo.descubrir --pendientes")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--solo-validar", action="store_true")
    analizador.add_argument(
        "--surtir",
        metavar="CODIGO[,CODIGO...]",
        help="Ensancha los conceptos dados: encola el abanico completo, no solo los niveles faltantes.",
    )
    analizador.add_argument(
        "--tope",
        type=int,
        default=15,
        help="Maximo de candidatos a encolar por consulta en --surtir (por defecto 15).",
    )
    args = analizador.parse_args()
    if args.surtir:
        codigos = [c.strip() for c in args.surtir.split(",") if c.strip()]
        return asyncio.run(_surtir(codigos, args.tope, args.solo_validar))
    return asyncio.run(_principal(args.solo_validar))


if __name__ == "__main__":
    sys.exit(main())
