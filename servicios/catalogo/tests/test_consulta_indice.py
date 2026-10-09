"""NFR-MAN-01: el indice que lee `consulta` de la base y lo que sale de emparejar contra el.

`test_consulta` fija la decision pura (`emparejar` con listas a mano). Falta el
borde con la base y la CLI, que es donde se decide QUE catalogo ve el
acudiente:

  - `cargar_indice` solo trae conceptos activos y productos activos, con el
    precio vigente MAS BAJO de sus ofertas activas (una oferta apagada o un
    tramo cerrado no cuentan) y el vector del concepto como centro de los de sus
    productos;
  - restriccion dura del producto: ninguna opcion que devuelve `emparejar` puede
    ser un SKU que no exista en `producto_canonico` (ni uno retirado);
  - el canal semantico DEGRADA, no tumba: sin embeder, o con uno que falla, el
    renglon se empareja por lexico;
  - la CLI imprime lo que decidio y cierra su motor efimero aunque falle.

Se inyecta `embeder_falso` (trigramas, 1024 dims, sin red) donde hace falta un
vector; nada usa Gemini ni su clave. Datos ficticios.
"""

from __future__ import annotations

import json
import logging
import runpy
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo import consulta
from tukit_catalogo.consulta import (
    Emparejamiento,
    Opcion,
    _elegir_por_nivel,
    _embeder_por_entorno,
    _imprimir,
    calcular_vectores,
    cargar_indice,
    emparejar,
    emparejar_en_catalogo,
)
from tukit_catalogo.embeddings import MODELO_FALSO, coseno, embeder_falso, promedio, texto_de_producto
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

CURADOR = uuid.UUID("cccccccc-cccc-5ccc-8ccc-cccccccccccc")
_DESDE = datetime(2026, 2, 1, tzinfo=UTC)
_HASTA = datetime(2026, 3, 1, tzinfo=UTC)


def _siembra(sesion) -> None:
    """Block (con y sin vector, con y sin precio, con un Bluey y un retirado), colores, origami y un hueco."""
    block = Concepto(
        codigo="C003",
        nombre_canonico="block",
        categoria="Papel",
        sinonimos=["bloc", "block carta", "block oficio"],
        atributos_discriminantes=["tamano"],
    )
    colores = Concepto(
        codigo="C004", nombre_canonico="colores", categoria="Arte", sinonimos=["lapices de colores"]
    )
    origami = Concepto(
        codigo="C090",
        nombre_canonico="origami",
        categoria="Papel",
        sinonimos=["papel origami"],
        atributos_discriminantes=["tamano"],
    )
    tijeras = Concepto(codigo="C050", nombre_canonico="tijeras", categoria="Arte")
    compas = Concepto(codigo="C099", nombre_canonico="compas geometrico", categoria="Arte", activo=False)
    exito = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    pana = Tienda(slug="panamericana", nombre="Panamericana", tipo="minorista")
    cerrada = Tienda(slug="cerrada", nombre="Tienda Cerrada", tipo="minorista")
    sesion.add_all([block, colores, origami, tijeras, compas, exito, pana, cerrada])
    sesion.flush()

    def _producto(concepto, sku, nombre, nivel, *, atributos=None, vector=False, **extra):
        texto = texto_de_producto(nombre, concepto.nombre_canonico, atributos)
        producto = ProductoCanonico(
            concepto_id=concepto.id,
            sku_interno=sku,
            nombre=nombre,
            nivel=nivel,
            atributos=atributos or {},
            curado_por=CURADOR,
            embedding=embeder_falso([texto])[0] if vector else None,
            embedding_model=MODELO_FALSO if vector else None,
            texto_embedding=texto if vector else None,
            **extra,
        )
        sesion.add(producto)
        sesion.flush()
        return producto

    eco = _producto(
        block,
        "TK-C003-ECO",
        "Block cuadriculado carta",
        "economico",
        atributos={"tamano": "carta"},
        vector=True,
    )
    _producto(
        block, "TK-C003-CON", "Block iris oficio", "confiable", atributos={"tamano": "oficio"}, vector=True
    )
    pre = _producto(block, "TK-C003-PRE", "Block premium carta", "premium", atributos={"tamano": "carta"})
    _producto(
        block,
        "TK-C003-ECO-BLUEY",
        "Block carta Bluey",
        "economico",
        atributos={"tamano": "carta"},
        personaje="bluey",
    )
    _producto(block, "TK-C003-RET", "Block retirado", "premium", atributos={"tamano": "carta"}, activo=False)
    _producto(
        colores, "TK-C004-ECO", "Colores x12 economico", "economico", marca="Faber", unidades_por_empaque=12
    )
    _producto(origami, "TK-C090-ECO", "Bloc origami 15 x 15", "economico", atributos={"tamano": "15 x 15 cm"})
    _producto(compas, "TK-C099-ECO", "Compas escolar", "economico")

    def _oferta(producto, tienda, centavos, *, activo=True, historico=None):
        oferta = OfertaTienda(
            producto_canonico_id=producto.id,
            tienda_id=tienda.id,
            referencia_externa=f"{tienda.slug}-{producto.sku_interno}",
            url=f"https://{tienda.slug}.example.test/{producto.sku_interno}",
            metodo_vinculacion="manual",
            disponible=True,
            activo=activo,
        )
        sesion.add(oferta)
        sesion.flush()
        if historico is not None:
            sesion.add(
                PrecioOferta(
                    oferta_id=oferta.id,
                    valor_centavos=historico,
                    fuente="scraper",
                    vigente_desde=_DESDE,
                    vigente_hasta=_HASTA,
                )
            )
        sesion.add(
            PrecioOferta(oferta_id=oferta.id, valor_centavos=centavos, fuente="scraper", vigente_desde=_HASTA)
        )
        sesion.flush()

    # ECO: tres tiendas. Gana la de 4500; la oferta APAGADA (1000) y el tramo CERRADO (900)
    # son mas baratos y no cuentan.
    _oferta(eco, exito, 500000, historico=90000)
    _oferta(eco, pana, 450000)
    _oferta(eco, cerrada, 100000, activo=False)
    _oferta(pre, exito, 990000)
    sesion.flush()


@pytest.fixture()
async def base():
    """Un motor SQLite sembrado: devuelve `(engine, fabrica)`."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()
    yield engine, fabrica
    await engine.dispose()


@pytest.fixture()
async def indice(base):
    engine, _ = base
    async with engine.connect() as conexion:
        return await cargar_indice(conexion)


async def _skus_activos(fabrica) -> set[str]:
    async with fabrica() as sesion:
        filas = await sesion.execute(
            select(ProductoCanonico.sku_interno).where(ProductoCanonico.activo.is_(True))
        )
        return {sku for (sku,) in filas}


# --- cargar_indice -----------------------------------------------------------


async def test_el_indice_solo_trae_conceptos_activos_con_su_vocabulario(indice):
    """El concepto apagado (`C099`) no existe para el acudiente; los demas traen su vocabulario."""
    conceptos, _ = indice
    por_codigo = {c["codigo"]: c for c in conceptos}
    assert set(por_codigo) == {"C003", "C004", "C090", "C050"}
    assert por_codigo["C003"]["sinonimos"] == ["bloc", "block carta", "block oficio"]
    assert por_codigo["C003"]["discriminantes"] == ("tamano",)
    assert por_codigo["C050"]["sinonimos"] == []
    assert por_codigo["C050"]["discriminantes"] == ()


async def test_el_indice_solo_trae_productos_activos_con_el_precio_vigente_mas_bajo(indice):
    """El retirado no aparece; ECO cuesta 4500 aunque una oferta apagada y un tramo cerrado sean menores."""
    _, productos = indice
    por_sku = {p["sku"]: p for p in productos}
    assert "TK-C003-RET" not in por_sku
    assert por_sku["TK-C003-ECO"]["precio_cop"] == 4500
    assert por_sku["TK-C003-PRE"]["precio_cop"] == 9900
    assert por_sku["TK-C003-CON"]["precio_cop"] is None  # sin ofertas: se ofrece, "sin precio"
    colores = por_sku["TK-C004-ECO"]
    assert (colores["marca"], colores["unidad_base"], colores["unidades_por_empaque"]) == (
        "Faber",
        "unidad",
        12,
    )
    assert por_sku["TK-C003-ECO-BLUEY"]["personaje"] == "bluey"
    assert por_sku["TK-C003-CON"]["atributos"] == {"tamano": "oficio"}


async def test_el_vector_del_concepto_es_el_centro_de_los_de_sus_productos_y_no_viaja_el_del_producto(indice):
    """Block promedia los dos vectores que tiene (ECO y CON); colores, sin ninguno, queda sin vector."""
    conceptos, productos = indice
    por_codigo = {c["codigo"]: c for c in conceptos}
    esperado = promedio(
        embeder_falso(
            [
                texto_de_producto("Block cuadriculado carta", "block", {"tamano": "carta"}),
                texto_de_producto("Block iris oficio", "block", {"tamano": "oficio"}),
            ]
        )
    )
    assert por_codigo["C003"]["embedding"] == pytest.approx(esperado)
    assert por_codigo["C004"]["embedding"] is None
    assert por_codigo["C090"]["embedding"] is None
    assert all("embedding" not in p for p in productos)


async def test_un_indice_sin_vectores_no_falla_y_deja_los_conceptos_sin_embedding(base, caplog):
    """Sin ningun embedding poblado el indice carga igual (solo lexico) y lo deja en el log de depuracion."""
    engine, fabrica = base
    async with fabrica() as sesion:
        await sesion.execute(
            ProductoCanonico.__table__.update().values(
                embedding=None, embedding_model=None, texto_embedding=None
            )
        )
        await sesion.commit()
    with caplog.at_level(logging.DEBUG, logger="tukit_catalogo.consulta"):
        async with engine.connect() as conexion:
            conceptos, _ = await cargar_indice(conexion)
    assert all(c["embedding"] is None for c in conceptos)
    assert "indice sin embeddings poblados" in caplog.text


# --- emparejar contra el indice y la restriccion de SKU -----------------------


@pytest.mark.parametrize(
    "renglon",
    ["block oficio", "block", "block carta", "bloc origami", "lapices de colores x 12", "tijeras", "compas"],
)
async def test_ninguna_opcion_es_un_sku_que_no_exista_ni_uno_retirado(base, indice, renglon):
    """Restriccion dura: todo lo que se ofrece sale de `producto_canonico` y esta activo.

    Se prueba con renglones que reconocen un concepto, que lo reconocen con
    atributo, que caen en un hueco y que apuntan a un concepto apagado.
    """
    _, fabrica = base
    conceptos, productos = indice
    activos = await _skus_activos(fabrica)

    resultado = emparejar(renglon, conceptos, productos)

    assert {o.sku for o in resultado.opciones} <= activos
    assert "TK-C003-RET" not in {o.sku for o in resultado.opciones}
    assert all(o.producto_id is not None for o in resultado.opciones)


async def test_block_oficio_ofrece_solo_el_producto_que_declara_oficio(indice):
    """El atributo impuesto filtra: el de carta no se ofrece, y la opcion lleva su id canonico como texto."""
    conceptos, productos = indice
    resultado = emparejar("block oficio", conceptos, productos)
    assert resultado.estado == "reconocido"
    assert resultado.concepto_codigo == "C003"
    assert [o.sku for o in resultado.opciones] == ["TK-C003-CON"]
    (opcion,) = resultado.opciones
    esperado = next(p["id"] for p in productos if p["sku"] == "TK-C003-CON")
    assert opcion.producto_id == str(esperado)
    assert opcion.precio_cop is None
    assert opcion.cumple is True


async def test_sin_atributo_impuesto_hay_una_opcion_por_nivel_y_la_de_marca_gana_al_personaje(indice):
    """`block` pelado da economico, confiable y premium; en economico gana el de marca y no el Bluey."""
    conceptos, productos = indice
    resultado = emparejar("block", conceptos, productos)
    assert [(o.nivel, o.sku) for o in resultado.opciones] == [
        ("economico", "TK-C003-ECO"),
        ("confiable", "TK-C003-CON"),
        ("premium", "TK-C003-PRE"),
    ]
    assert [o.precio_cop for o in resultado.opciones] == [4500, None, 9900]


async def test_un_concepto_activo_sin_producto_es_hueco_de_catalogo(indice):
    """`tijeras` se entiende pero no hay que ofrecer: el estado lo dice para pedir curaduria, sin opciones."""
    conceptos, productos = indice
    resultado = emparejar("tijeras", conceptos, productos)
    assert resultado.estado == "hueco_catalogo"
    assert resultado.concepto_codigo == "C050"
    assert resultado.opciones == ()
    assert "no tiene producto" in resultado.motivo


async def test_un_renglon_que_no_se_reconoce_no_ofrece_nada(indice):
    """Por debajo del umbral de parecido el estado es `sin_match`: sin concepto, sin opciones, con motivo."""
    conceptos, productos = indice
    resultado = emparejar("zxqv wplk", conceptos, productos)
    assert resultado.estado == "sin_match"
    assert (resultado.concepto_codigo, resultado.concepto_nombre, resultado.opciones) == (None, None, ())
    assert resultado.parecido < 0.5
    assert resultado.motivo == "No reconocemos que pide este renglon."


async def test_un_concepto_apagado_nunca_se_empareja(indice):
    """`compas geometrico` esta apagado: no puede salir ni como concepto reconocido ni con su producto."""
    conceptos, productos = indice
    resultado = emparejar("compas geometrico", conceptos, productos)
    assert resultado.concepto_codigo != "C099"
    assert "TK-C099-ECO" not in {o.sku for o in resultado.opciones}


async def test_el_emparejamiento_cruza_a_json_con_todas_sus_opciones(indice):
    """`a_dict` viaja por HTTP a inteligencia: debe ser serializable y llevar las opciones como dicts."""
    conceptos, productos = indice
    datos = emparejar("block", conceptos, productos).a_dict()
    texto = json.dumps(datos)
    assert json.loads(texto)["opciones"][0]["sku"] == "TK-C003-ECO"
    assert set(datos) == {
        "texto",
        "texto_corregido",
        "estado",
        "concepto_codigo",
        "concepto_nombre",
        "parecido",
        "atributos_impuestos",
        "motivo",
        "opciones",
    }
    assert set(datos["opciones"][0]) >= {"sku", "nombre", "nivel", "precio_cop", "producto_id", "cumple"}


async def test_con_el_embeder_falso_el_vector_del_renglon_se_funde_sin_cambiar_lo_acertado(indice):
    """Inyectar `embeder_falso` no cambia un match que el lexico ya acertaba; el concepto tiene vector."""
    conceptos, productos = indice
    (vector,) = embeder_falso(["block oficio"])
    sin = emparejar("block oficio", conceptos, productos)
    con = emparejar("block oficio", conceptos, productos, embedding_renglon=vector)
    assert (con.concepto_codigo, [o.sku for o in con.opciones]) == (
        sin.concepto_codigo,
        [o.sku for o in sin.opciones],
    )
    assert con.parecido >= sin.parecido
    block = next(c for c in conceptos if c["codigo"] == "C003")
    assert coseno(vector, block["embedding"]) > 0.0


# --- _elegir_por_nivel --------------------------------------------------------


@pytest.mark.parametrize("invertir", [False, True], ids=["orden-directo", "orden-inverso"])
def test_en_un_nivel_gana_el_sin_personaje_y_a_igualdad_el_sku_menor(invertir):
    """La respuesta no depende del orden en que la base devolvio las filas.

    Hay tres economicos: un Bluey, uno de marca `-B` y uno de marca `-A`. Gana el
    de marca de sku menor, vengan como vengan.
    """
    productos = [
        {"nivel": "economico", "sku": "TK-X-ECO-BLUEY", "personaje": "bluey"},
        {"nivel": "economico", "sku": "TK-X-ECO-B", "personaje": None},
        {"nivel": "economico", "sku": "TK-X-ECO-A", "personaje": None},
        {"nivel": "premium", "sku": "TK-X-PRE", "personaje": None},
    ]
    if invertir:
        productos.reverse()
    elegidos = _elegir_por_nivel(productos)
    assert [(p["nivel"], p["sku"]) for p in elegidos] == [
        ("economico", "TK-X-ECO-A"),
        ("premium", "TK-X-PRE"),
    ]


def test_un_producto_de_nivel_desconocido_no_se_ofrece():
    """Solo hay tres niveles; uno fuera de la escala (o sin nivel) se descarta en vez de inventarle puesto."""
    elegidos = _elegir_por_nivel(
        [
            {"nivel": "lujo", "sku": "TK-X-LUJO"},
            {"nivel": None, "sku": "TK-X-NADA"},
            {"nivel": "confiable", "sku": "TK-X-CON"},
        ]
    )
    assert [p["sku"] for p in elegidos] == ["TK-X-CON"]


# --- calcular_vectores y el entorno -------------------------------------------


def test_sin_embeder_o_sin_renglones_no_hay_vectores():
    """Sin canal semantico cada renglon queda con `None`; una lista vacia da una lista vacia."""
    assert calcular_vectores(["a", "b"], None) == [None, None]
    assert calcular_vectores([], embeder_falso) == []


def test_los_vectores_se_piden_en_un_solo_lote():
    """Una peticion por lista, no una por renglon: es lo que mantiene la consulta barata."""
    pedidos: list[list[str]] = []

    def espia(textos):
        pedidos.append(list(textos))
        return embeder_falso(textos)

    vectores = calcular_vectores(["block", "colores", "tijeras"], espia)

    assert pedidos == [["block", "colores", "tijeras"]]
    assert len(vectores) == 3
    assert vectores[0] == embeder_falso(["block"])[0]


def test_si_el_embeder_falla_el_canal_degrada_a_lexico_y_deja_rastro(caplog):
    """Un proveedor caido no tumba la consulta: cada renglon queda en `None` y el fallo queda en el log."""

    def roto(textos):
        raise RuntimeError("proveedor ficticio caido")

    with caplog.at_level(logging.WARNING, logger="tukit_catalogo.consulta"):
        vectores = calcular_vectores(["block", "colores"], roto)

    assert vectores == [None, None]
    assert "canal semantico degradado a lexico" in caplog.text
    assert "proveedor ficticio caido" in caplog.text


def test_sin_clave_en_el_entorno_no_hay_embeder():
    """Sin `GEMINI_API_KEY` (el conftest la borra) la consulta no tiene canal semantico: devuelve `None`."""
    assert _embeder_por_entorno() is None


# --- emparejar_en_catalogo y el motor efimero de la CLI --------------------------


class _MotorEfimero:
    """El motor que crea la CLI: un engine real y un registro de si se cerro."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


@pytest.fixture()
def motor_efimero(base, monkeypatch):
    engine, _ = base
    motor = _MotorEfimero(engine)
    servicios: list[str] = []

    def crear(servicio):
        servicios.append(servicio)
        return motor

    monkeypatch.setattr("tukit_comun.bd.crear_motor", crear)
    motor.servicios = servicios
    return motor


async def test_la_cli_carga_el_indice_con_un_motor_propio_y_lo_cierra(motor_efimero):
    """`_cargar_indice_cli` abre el motor de `catalogo`, carga el indice y lo cierra al terminar."""
    conceptos, productos = await consulta._cargar_indice_cli()

    assert motor_efimero.servicios == ["catalogo"]
    assert motor_efimero.cerrado is True
    assert {c["codigo"] for c in conceptos} == {"C003", "C004", "C090", "C050"}
    assert len(productos) == 7


async def test_la_cli_cierra_su_motor_aunque_la_carga_falle(motor_efimero, monkeypatch):
    """Un error al cargar el indice se propaga, pero el motor efimero se cierra igual (sin pool abierto)."""

    async def falla(_conexion):
        raise RuntimeError("base ficticia caida")

    monkeypatch.setattr(consulta, "cargar_indice", falla)

    with pytest.raises(RuntimeError, match="base ficticia caida"):
        await consulta._cargar_indice_cli()

    assert motor_efimero.cerrado is True


async def test_emparejar_en_catalogo_con_embeder_inyectado_empareja_cada_renglon(motor_efimero):
    """Un lote de renglones sale en el mismo orden, con el embeder falso, y solo con SKU del catalogo."""
    resultados = await emparejar_en_catalogo(["block oficio", "tijeras", "zxqv"], embeder=embeder_falso)

    assert [r.estado for r in resultados] == ["reconocido", "hueco_catalogo", "sin_match"]
    assert [o.sku for o in resultados[0].opciones] == ["TK-C003-CON"]
    assert [r.texto for r in resultados] == ["block oficio", "tijeras", "zxqv"]


async def test_emparejar_en_catalogo_sin_embeder_ni_clave_sigue_con_lexico(motor_efimero):
    """Sin embeder inyectado y sin clave en el entorno el resultado es el lexico de siempre, sin fallar."""
    (resultado,) = await emparejar_en_catalogo(["block oficio"])
    assert resultado.estado == "reconocido"
    assert [o.sku for o in resultado.opciones] == ["TK-C003-CON"]


async def test_emparejar_en_catalogo_con_embeder_roto_degrada_en_vez_de_fallar(motor_efimero, caplog):
    """Si el proveedor de embeddings falla, la consulta responde igual por lexico y deja el aviso."""

    def roto(textos):
        raise RuntimeError("proveedor ficticio caido")

    with caplog.at_level(logging.WARNING, logger="tukit_catalogo.consulta"):
        (resultado,) = await emparejar_en_catalogo(["block oficio"], embeder=roto)

    assert resultado.estado == "reconocido"
    assert "canal semantico degradado a lexico" in caplog.text


# --- la CLI ---------------------------------------------------------------------


def _opcion(**cambios) -> Opcion:
    base = {
        "sku": "TK-C003-ECO",
        "nombre": "Block cuadriculado carta",
        "nivel": "economico",
        "personaje": None,
        "atributos": {"tamano": "carta"},
        "precio_cop": 4500,
        "cumple": True,
    }
    return Opcion(**{**base, **cambios})


def test_imprimir_muestra_la_correccion_el_concepto_el_pedido_y_cada_opcion(capsys):
    """La CLI dice que se leyo (si se corrigio), que concepto y atributos entendio y que ofrece."""
    resultado = Emparejamiento(
        texto="blok ofisio",
        texto_corregido="block oficio",
        estado="reconocido",
        concepto_codigo="C003",
        concepto_nombre="block",
        parecido=0.9,
        atributos_impuestos={"tamano": "oficio"},
        motivo="",
        opciones=(
            _opcion(),
            _opcion(nivel="premium", nombre="Block Bluey", precio_cop=None, personaje="bluey"),
        ),
    )

    _imprimir(resultado)

    salida = capsys.readouterr().out
    assert "  blok ofisio\n" in salida
    assert "  leido como block oficio\n" in salida
    assert "RECONOCIDO" in salida
    assert "-> block  [tamano=oficio]" in salida
    assert "economico" in salida
    assert "$4,500" in salida
    assert "sin precio" in salida
    assert "Block Bluey  bluey" in salida


def test_imprimir_un_renglon_que_no_se_reconoce_solo_dice_el_motivo(capsys):
    """Sin concepto no hay flecha ni opciones: queda el estado, el texto y el motivo."""
    _imprimir(
        Emparejamiento(
            texto="zxqv",
            texto_corregido="zxqv",
            estado="sin_match",
            concepto_codigo=None,
            concepto_nombre=None,
            parecido=0.1,
            atributos_impuestos={},
            motivo="No reconocemos que pide este renglon.",
            opciones=(),
        )
    )

    salida = capsys.readouterr().out
    assert salida.startswith("SIN_MATCH")
    assert "->" not in salida
    assert "leido como" not in salida
    assert "  No reconocemos que pide este renglon." in salida


def test_main_sin_renglones_pide_uno_y_sale_con_codigo_2(capsys):
    """La CLI sin argumentos no consulta nada: avisa por stderr y devuelve 2."""
    assert consulta.main([]) == 2
    capturado = capsys.readouterr()
    assert "Pasa al menos un renglon." in capturado.err
    assert capturado.out == ""


def test_main_empareja_los_renglones_e_imprime_cada_resultado(monkeypatch, capsys):
    """`main` pasa los renglones al emparejador y escribe un bloque por resultado (con linea en blanco)."""
    pedidos: list[list[str]] = []
    conceptos = [
        {"id": uuid.uuid4(), "codigo": "C050", "nombre": "tijeras", "sinonimos": [], "discriminantes": ()}
    ]

    async def falso(renglones):
        pedidos.append(list(renglones))
        return [emparejar(r, conceptos, []) for r in renglones]

    monkeypatch.setattr(consulta, "emparejar_en_catalogo", falso)

    assert consulta.main(["tijeras", "zxqv"]) == 0

    assert pedidos == [["tijeras", "zxqv"]]
    salida = capsys.readouterr().out
    assert "HUECO_CATALOGO" in salida
    assert "SIN_MATCH" in salida
    assert salida.count("\n\n") == 2


def test_main_sin_argv_toma_los_renglones_de_la_linea_de_comandos(monkeypatch, capsys):
    """`python -m tukit_catalogo.consulta "block"` usa `sys.argv[1:]` cuando no se le pasa lista."""
    pedidos: list[list[str]] = []

    async def falso(renglones):
        pedidos.append(list(renglones))
        return []

    monkeypatch.setattr(consulta, "emparejar_en_catalogo", falso)
    monkeypatch.setattr("sys.argv", ["consulta", "block oficio", "2 lapices negros"])

    assert consulta.main() == 0

    assert pedidos == [["block oficio", "2 lapices negros"]]
    assert capsys.readouterr().out == ""


def test_ejecutar_el_modulo_como_programa_sin_renglones_sale_con_2(monkeypatch, capsys):
    """`python -m tukit_catalogo.consulta` sin argumentos termina con `SystemExit(2)`."""
    monkeypatch.setattr("sys.argv", ["tukit_catalogo.consulta"])

    # runpy avisa que el modulo ya estaba importado: es justo lo que se esta ensayando.
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as salida:
        runpy.run_module("tukit_catalogo.consulta", run_name="__main__")

    assert salida.value.code == 2
    assert "Pasa al menos un renglon." in capsys.readouterr().err
