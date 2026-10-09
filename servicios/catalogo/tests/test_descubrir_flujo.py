"""NFR-MAN-01: el descubrimiento propone, una persona decide, y la puerta a las tiendas no se reabre.

`test_descubrir` fija el vocabulario (singulares, cabeza de la frase, EAN) y que
la regla de la puerta este en la firma de las funciones. Aqui se ejercita el
flujo completo contra un esquema SQLite real y una tienda de mentira
(`tiendas.buscar` se sustituye; ninguna prueba toca la red):

- **Que se propone.** Un renglon que el catalogo ya cubre en sus tres niveles NO
  sale a ninguna tienda; el que esta a medias propone lo que falta, repartido
  barato/medio/caro; el que no se reconoce se propone como concepto NUEVO con
  puntaje bajo, no colgado del concepto mas parecido.
- **Idempotencia.** Volver a revisar la misma lista no re-propone lo ya decidido
  (aprobado, rechazado, pendiente u ofertado): rechazar sirve de algo.
- **Que decide una persona.** Aprobar crea producto + oferta + precio en una
  sola transaccion; rechazar con `--no-surtir` saca al concepto del catalogo
  comprable; aprobar sin concepto no crea nada; ni lo aprobado ni lo rechazado se
  resuelve dos veces.
- **La puerta.** Cerrar se niega si quedan pendientes; una lista cerrada ya no
  abre revision, y eso no depende de quien llame.
- **Altas a mano.** Libro con ISBN verificado y util elegido de una lista de
  candidatos pasan por la misma cola, con ids estables.
- **El score hibrido nunca resta.** Invariante documentada de `clasificar`.

La base es un fichero SQLite en `tmp_path` inyectado en lugar de Postgres; los
nombres, tiendas y precios son inventados.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from tukit_catalogo import descubrir
from tukit_catalogo.cargador import AGENTE_FIRECRAWL, _uuid_estable
from tukit_catalogo.descubrir import (
    PuertaCerrada,
    _parecido,
    _plano,
    abrir_revision,
    buscar_candidatos,
    cerrar,
    clasificar,
    crear_libro,
    crear_util,
    listar_listas,
    listar_pendientes,
    probar,
    proponer,
    resolver,
)
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    ItemListaOficial,
    ListaOficial,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    PropuestaProducto,
    Tienda,
    VersionListaOficial,
)
from tukit_catalogo.tiendas import Oferta
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

CURADOR = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
ISBN_VALIDO = "9789580714729"
ISBN_MALO = "9789580714728"


def _oferta(
    nombre: str,
    precio: int,
    *,
    tienda: str = "exito",
    sku: str | None = None,
    disponible: bool = True,
    imagen: str | None = "https://img.example.test/p.jpg",
    ean: str | None = None,
    marca: str | None = "Marca Ficticia",
    especificaciones: dict[str, str] | None = None,
) -> Oferta:
    return Oferta(
        tienda=tienda,
        nombre=nombre,
        precio_cop=precio,
        disponible=disponible,
        imagen_url=imagen,
        url=f"https://{tienda}.example.test/{sku or nombre}/p".replace(" ", "-"),
        sku=sku or f"SKU-{nombre}".replace(" ", "-"),
        ean=ean,
        marca=marca,
        especificaciones=especificaciones or {},
    )


class TiendaFalsa:
    """Sustituye a `tiendas.buscar`: responde por tienda, anota cada consulta."""

    def __init__(self, ofertas: dict[str, list[Oferta]] | None = None) -> None:
        self.ofertas = ofertas or {}
        self.consultas: list[tuple[str, str]] = []

    def __call__(self, tienda: str, consulta: str, cuantos: int = 24) -> list[Oferta]:
        self.consultas.append((tienda, consulta))
        return list(self.ofertas.get(tienda, []))


@pytest.fixture()
def tienda_falsa(monkeypatch: pytest.MonkeyPatch) -> TiendaFalsa:
    falsa = TiendaFalsa()
    monkeypatch.setattr(descubrir.tiendas, "buscar", falsa)
    return falsa


# ---------------------------------------------------------------------------
# Piezas puras
# ---------------------------------------------------------------------------


class TestParecidoYPlano:
    def test_plano_quita_tildes_mayusculas_y_espacios_repetidos(self):
        assert _plano("  LÁPIZ   de  Colóres ") == "lapiz de colores"

    def test_las_preposiciones_no_cuentan_como_parecido(self):
        """Compartir 'de' subia chaquiras/colores justo hasta el umbral y se colaban."""
        assert _parecido("chaquiras de colores", "colores de madera") == pytest.approx(1 / 3)

    def test_las_cantidades_y_los_plurales_no_estorban(self):
        assert _parecido("2 lapices negros", "lapiz negro") == 1.0

    def test_sin_palabras_significativas_no_hay_parecido(self):
        assert _parecido("de la", "cuaderno") == 0.0
        assert _parecido("cuaderno", "") == 0.0


CUADERNO = {"id": uuid.UUID(int=0xA1), "nombre": "cuaderno", "sinonimos": ["cuaderno cosido"]}


class TestClasificarHibrido:
    def test_sin_vector_el_resultado_es_el_lexico_de_siempre(self):
        solo_lexico = clasificar("cuaderno cuadriculado", [CUADERNO])
        con_vector_vacio = clasificar("cuaderno cuadriculado", [CUADERNO], embedding_renglon=[1.0, 0.0])
        # El concepto no trae embedding: el canal semantico no participa.
        assert solo_lexico == con_vector_vacio
        assert solo_lexico[0] == CUADERNO["id"]
        assert solo_lexico[2] == pytest.approx(0.8)

    def test_un_coseno_alto_suma_un_aporte_pequeno_a_quien_ya_acerto_la_cabeza(self):
        concepto = {**CUADERNO, "embedding": [1.0, 0.0]}
        sin = clasificar("cuaderno cuadriculado", [concepto])[2]
        con = clasificar("cuaderno cuadriculado", [concepto], embedding_renglon=[1.0, 0.0])[2]
        assert con == pytest.approx(sin + 0.15)

    def test_el_aporte_no_pasa_de_uno(self):
        concepto = {**CUADERNO, "embedding": [1.0, 0.0]}
        assert clasificar("cuaderno", [concepto], embedding_renglon=[1.0, 0.0])[2] == 1.0

    def test_un_coseno_muy_alto_rescata_un_sinonimo_que_no_esta_en_la_lista(self):
        """'estuche' responde a 'cartuchera' sin haberlo escrito antes, y entra a revision."""
        cartuchera = {
            "id": uuid.UUID(int=0xB1),
            "nombre": "cartuchera",
            "sinonimos": [],
            "embedding": [1.0, 0.0],
        }
        id_, nombre, puntaje = clasificar("estuche", [cartuchera], embedding_renglon=[1.0, 0.0])
        assert (id_, nombre) == (cartuchera["id"], "cartuchera")
        assert puntaje == pytest.approx(0.95)  # piso 0.55 + el tramo completo del umbral a 1.0

    def test_el_rescate_exige_el_umbral_alto(self):
        """Un parecido de tema (coseno mediano) no rescata nada: 'chaquiras' no es 'colores'."""
        cartuchera = {
            "id": uuid.UUID(int=0xB1),
            "nombre": "cartuchera",
            "sinonimos": [],
            "embedding": [1.0, 0.0],
        }
        # coseno = 0.8 < 0.86
        assert clasificar("estuche", [cartuchera], embedding_renglon=[0.8, 0.6]) == (None, "", 0.0)

    def test_el_rescate_en_el_borde_cae_justo_en_el_piso_de_revision(self):
        cartuchera = {
            "id": uuid.UUID(int=0xB1),
            "nombre": "cartuchera",
            "sinonimos": [],
            "embedding": [1.0, 0.0],
        }
        # coseno = 0.86 exacto
        _, _, puntaje = clasificar("estuche", [cartuchera], embedding_renglon=[0.86, (1 - 0.86**2) ** 0.5])
        assert puntaje == pytest.approx(0.55)

    def test_sin_conceptos_no_hay_clasificacion(self):
        assert clasificar("cuaderno", []) == (None, "", 0.0)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-11: un coseno negativo RESTA al puntaje lexico (descubrir.py:297 y :299 suman "
            "_APORTE_COSENO * cos sin piso en 0), contra el docstring de clasificar (l.259-261) 'Nunca resta'"
        ),
    )
    def test_el_canal_semantico_nunca_baja_el_puntaje_lexico(self):
        """El docstring de `clasificar` promete que el hibrido nunca da menos que el lexico solo."""
        sin_vector = clasificar("cuaderno cuadriculado", [CUADERNO])[2]
        opuesto = {**CUADERNO, "embedding": [-1.0, 0.0]}
        con_vector_opuesto = clasificar("cuaderno cuadriculado", [opuesto], embedding_renglon=[1.0, 0.0])[2]
        assert con_vector_opuesto >= sin_vector


class TestBuscarCandidatos:
    def test_descarta_lo_agotado_sin_foto_o_fuera_de_rango_de_precio(self, tienda_falsa):
        tienda_falsa.ofertas["exito"] = [
            _oferta("Tijeras Buenas", 8000, sku="ok"),
            _oferta("Tijeras Agotadas", 8000, sku="agotada", disponible=False),
            _oferta("Tijeras Sin Foto", 8000, sku="sin-foto", imagen=None),
            _oferta("Tijeras Regaladas", 999, sku="barata"),
            _oferta("Tijeras Institucionales", 400_001, sku="cara"),
            _oferta("Tijeras En El Borde Bajo", 1000, sku="borde-bajo"),
            _oferta("Tijeras En El Borde Alto", 400_000, sku="borde-alto"),
        ]
        encontrados = buscar_candidatos("tijeras", ancla="tijeras")
        assert sorted(o.sku for o in encontrados) == ["borde-alto", "borde-bajo", "ok"]

    def test_el_ancla_tumba_lo_que_no_se_llama_como_lo_pedido(self, tienda_falsa):
        """Exito devuelve velas y un trapero ante 'aserrin colores surtidos': ninguno se llama aserrin."""
        tienda_falsa.ofertas["exito"] = [
            _oferta("Vela Aromatica", 5000, sku="vela"),
            _oferta("Aserrin De Colores", 4000, sku="aserrin"),
        ]
        assert [o.sku for o in buscar_candidatos("aserrin colores surtidos", ancla="aserrin")] == ["aserrin"]

    def test_la_raiz_permite_que_el_plural_encuentre_el_singular(self, tienda_falsa):
        tienda_falsa.ofertas["exito"] = [_oferta("Pompon Gigante", 3000, sku="p")]
        assert [o.sku for o in buscar_candidatos("pompones", ancla="pompones")] == ["p"]

    def test_sin_ancla_la_primera_palabra_de_la_consulta_hace_de_ancla(self, tienda_falsa):
        tienda_falsa.ofertas["exito"] = [
            _oferta("Regla Plastica", 2000, sku="r"),
            _oferta("Otra Cosa", 2000, sku="o"),
        ]
        assert [o.sku for o in buscar_candidatos("regla plastica")] == ["r"]

    def test_consulta_a_las_tres_tiendas_del_cliente(self, tienda_falsa):
        buscar_candidatos("tijeras", ancla="tijeras")
        assert [t for t, _c in tienda_falsa.consultas] == ["exito", "panamericana", "grancentral"]

    def test_si_hay_pocos_se_devuelven_todos_del_mas_barato_al_mas_caro(self, tienda_falsa):
        tienda_falsa.ofertas["exito"] = [
            _oferta("Tijeras C", 9000, sku="c"),
            _oferta("Tijeras A", 3000, sku="a"),
        ]
        tienda_falsa.ofertas["panamericana"] = [_oferta("Tijeras B", 6000, sku="b", tienda="panamericana")]
        assert [o.sku for o in buscar_candidatos("tijeras", ancla="tijeras")] == ["a", "b", "c"]

    def test_si_hay_muchos_se_reparten_barato_medio_y_caro_sin_los_extremos(self, tienda_falsa):
        """El mas barato suele ser un accesorio suelto y el mas caro un empaque institucional."""
        tienda_falsa.ofertas["exito"] = [
            _oferta(f"Tijeras {n:02}", 1000 * (n + 1), sku=f"s{n:02}") for n in range(12)
        ]
        elegidos = buscar_candidatos("tijeras", ancla="tijeras")
        assert [o.precio_cop for o in elegidos] == [3000, 7000, 11000]  # posiciones 2, 6 y 10 de 12

    def test_sin_resultados_devuelve_vacio(self, tienda_falsa):
        assert buscar_candidatos("tijeras", ancla="tijeras") == []


# ---------------------------------------------------------------------------
# Esquema SQLite
# ---------------------------------------------------------------------------


def _activar_fk(conexion, _registro):  # noqa: ANN001
    conexion.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def bd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    archivo = tmp_path / "catalogo.db"
    sincrono = create_engine(f"sqlite:///{archivo}")
    event.listen(sincrono, "connect", _activar_fk)
    Base.metadata.create_all(sincrono)

    def fabricar(servicio: str, *, echo: bool = False) -> MotorServicio:
        motor = create_async_engine(f"sqlite+aiosqlite:///{archivo}")
        event.listen(motor.sync_engine, "connect", _activar_fk)
        return MotorServicio(servicio, motor, async_sessionmaker(motor, expire_on_commit=False))

    monkeypatch.setattr("tukit_comun.bd.crear_motor", fabricar)
    with Session(sincrono) as sesion:
        yield sesion
    sincrono.dispose()


def _sembrar(bd: Session, *, revisada: bool = False) -> SimpleNamespace:
    """Un catalogo pequeno y una lista de tres renglones.

    - `cuaderno` ya tiene los tres niveles: no sale a ninguna tienda.
    - `tijeras` solo tiene el economico.
    - El tercer renglon no corresponde a ningun concepto.
    """
    tiendas = {
        slug: Tienda(slug=slug, nombre=slug.title(), tipo="minorista")
        for slug in ("exito", "panamericana", "grancentral")
    }
    bd.add_all(tiendas.values())
    cuaderno = Concepto(
        codigo="C001",
        nombre_canonico="cuaderno",
        categoria="escritura",
        sinonimos=["cuaderno cosido"],
        atributos_discriminantes=["hojas"],
    )
    tijeras = Concepto(codigo="C002", nombre_canonico="tijeras", categoria="manualidades", sinonimos=[])
    bd.add_all([cuaderno, tijeras])
    bd.flush()
    for nivel in ("economico", "confiable", "premium"):
        bd.add(
            ProductoCanonico(
                concepto_id=cuaderno.id,
                sku_interno=f"TK-CUA-{nivel}",
                nombre=f"Cuaderno Ficticio {nivel}",
                nivel=nivel,
                curado_por=CURADOR,
            )
        )
    bd.add(
        ProductoCanonico(
            concepto_id=tijeras.id,
            sku_interno="TK-TIJ-eco",
            nombre="Tijeras Ficticias economicas",
            nivel="economico",
            curado_por=CURADOR,
        )
    )
    lista = ListaOficial(colegio_id=uuid.UUID(int=0xC0), sede_id=None, grado="Cuarto", anio_lectivo=2026)
    bd.add(lista)
    bd.flush()
    version = VersionListaOficial(
        lista_id=lista.id,
        numero=1,
        vigente=True,
        revisada_en=datetime(2026, 9, 1, tzinfo=UTC) if revisada else None,
    )
    bd.add(version)
    bd.flush()
    items = [
        ItemListaOficial(
            version_id=version.id, orden=orden, texto_original=texto, cantidad=1, requiere_revision=True
        )
        for orden, texto in enumerate(
            ["Cuaderno cosido 100 hojas", "Tijeras escolares", "Aserrin de colores x 3 bolsas"], start=1
        )
    ]
    bd.add_all(items)
    bd.commit()
    return SimpleNamespace(
        tiendas={s: t.id for s, t in tiendas.items()},
        cuaderno=cuaderno.id,
        tijeras=tijeras.id,
        version=version.id,
        corto=str(version.id)[:8],
        items={i.texto_original: i.id for i in items},
    )


def _tijeras_en_tienda(falsa: TiendaFalsa) -> None:
    falsa.ofertas["exito"] = [
        _oferta("Tijeras Escolares Ficticias 1", 3000, sku="T1"),
        _oferta("Tijeras Escolares Ficticias 2", 6000, sku="T2"),
        _oferta("Tijeras Escolares Ficticias 3", 9000, sku="T3"),
        _oferta("Tijeras Escolares Ficticias 4", 20000, sku="T4"),
    ]
    falsa.ofertas["panamericana"] = [
        _oferta("Aserrin De Colores Ficticio", 5000, sku="A1", tienda="panamericana"),
    ]


def _propuestas(bd: Session) -> list[PropuestaProducto]:
    bd.rollback()
    return list(bd.scalars(select(PropuestaProducto).order_by(PropuestaProducto.referencia_externa)))


def _contar(bd: Session, modelo) -> int:  # noqa: ANN001
    bd.rollback()
    return bd.scalar(select(func.count()).select_from(modelo))


def _propuesta(bd: Session, mundo, **kw) -> PropuestaProducto:
    datos = {
        "concepto_id": mundo.tijeras,
        "texto_origen": "Tijeras escolares",
        "tienda_id": mundo.tiendas["exito"],
        "referencia_externa": "REF-1",
        "url": "https://exito.example.test/tijeras/p",
        "nombre": "Tijeras Escolares Ficticias Caja x 12 Unidades",
        "marca": "Marca Ficticia",
        "ean": "7701234567890",
        "imagen_url": "https://img.example.test/t.jpg",
        "precio_centavos": 900000,
        "disponible": True,
        "especificaciones": {},
        "nivel_sugerido": "economico",
        "puntaje": 0.8,
        "version_lista_id": mundo.version,
    }
    datos.update(kw)
    p = PropuestaProducto(**datos)
    bd.add(p)
    bd.commit()
    return p


# ---------------------------------------------------------------------------
# La puerta
# ---------------------------------------------------------------------------


class TestAbrirRevision:
    async def test_devuelve_los_renglones_en_orden_con_los_datos_de_la_lista(self, bd):
        mundo = _sembrar(bd)
        revision = await abrir_revision(mundo.corto)
        assert revision.version_id == mundo.version
        assert revision.colegio == str(uuid.UUID(int=0xC0))[:8]
        assert (revision.grado, revision.anio) == ("Cuarto", 2026)
        assert [t for _i, t in revision.items] == [
            "Cuaderno cosido 100 hojas",
            "Tijeras escolares",
            "Aserrin de colores x 3 bolsas",
        ]

    async def test_una_version_que_no_existe_cierra_la_puerta(self, bd):
        _sembrar(bd)
        with pytest.raises(PuertaCerrada, match="No existe ninguna version"):
            await abrir_revision("ffffffff")

    async def test_una_version_revisada_cierra_la_puerta_con_su_fecha(self, bd):
        mundo = _sembrar(bd, revisada=True)
        with pytest.raises(PuertaCerrada, match="ya fue revisada el 2026-09-01"):
            await abrir_revision(mundo.corto)

    @pytest.mark.parametrize(
        "operacion",
        [
            lambda c: crear_libro(c, ISBN_VALIDO, "Libro Ficticio", 50000, "exito", None, None, None),
            lambda c: crear_util(c, "C002", "tijeras", None),
        ],
        ids=["crear_libro", "crear_util"],
    )
    async def test_ninguna_alta_a_mano_sale_a_una_tienda_si_la_lista_esta_revisada(
        self, bd, tienda_falsa, operacion
    ):
        mundo = _sembrar(bd, revisada=True)
        with pytest.raises(PuertaCerrada):
            await operacion(mundo.corto)
        assert tienda_falsa.consultas == []
        assert _contar(bd, PropuestaProducto) == 0


# ---------------------------------------------------------------------------
# proponer
# ---------------------------------------------------------------------------


class TestProponer:
    async def test_cada_renglon_recibe_el_tratamiento_que_le_corresponde(self, bd, tienda_falsa, capsys):
        mundo = _sembrar(bd)
        _tijeras_en_tienda(tienda_falsa)

        await proponer(await abrir_revision(mundo.corto))

        salida = capsys.readouterr().out
        assert "Revision de" in salida
        assert "YA LO TENEMOS" in salida
        assert "falta confiable, premium" in salida
        assert "CONCEPTO NUEVO: aserrin colores" in salida
        assert "resueltos con nuestro catalogo, sin salir  1/3" in salida
        assert "hubo que consultar una tienda              2/3" in salida
        assert "Encoladas para revision: 4" in salida
        assert f"--cerrar {mundo.corto}" in salida

        # El cuaderno, que ya tiene tres niveles, no consulto ninguna tienda.
        assert all("cuaderno" not in c for _t, c in tienda_falsa.consultas)
        pendientes = _propuestas(bd)
        assert [p.referencia_externa for p in pendientes] == ["A1", "T1", "T3", "T4"]

    async def test_lo_que_falta_se_propone_barato_medio_y_caro_con_su_trazabilidad(self, bd, tienda_falsa):
        mundo = _sembrar(bd)
        _tijeras_en_tienda(tienda_falsa)

        await proponer(await abrir_revision(mundo.corto))

        por_ref = {p.referencia_externa: p for p in _propuestas(bd)}
        assert [(r, por_ref[r].nivel_sugerido, por_ref[r].precio_centavos) for r in ("T1", "T3", "T4")] == [
            ("T1", "economico", 300000),
            ("T3", "confiable", 900000),
            ("T4", "premium", 2000000),
        ]
        tijera = por_ref["T1"]
        assert tijera.concepto_id == mundo.tijeras
        assert tijera.concepto_sugerido is None
        assert tijera.texto_origen == "Tijeras escolares"
        assert tijera.tienda_id == mundo.tiendas["exito"]
        assert tijera.estado == "pendiente"
        assert tijera.origen == "scraper"
        assert tijera.version_lista_id == mundo.version
        assert tijera.item_lista_id == mundo.items["Tijeras escolares"]
        assert float(tijera.puntaje) == pytest.approx(0.8)  # el parecido, con tope en 0.9
        assert tijera.id == _uuid_estable("propuesta", "exito", "T1")

    async def test_lo_que_no_se_reconoce_nace_como_concepto_nuevo_con_puntaje_bajo(self, bd, tienda_falsa):
        mundo = _sembrar(bd)
        _tijeras_en_tienda(tienda_falsa)

        await proponer(await abrir_revision(mundo.corto))

        nueva = next(p for p in _propuestas(bd) if p.referencia_externa == "A1")
        assert nueva.concepto_id is None
        assert nueva.concepto_sugerido == "aserrin colores"
        assert float(nueva.puntaje) == pytest.approx(0.3)
        assert nueva.tienda_id == mundo.tiendas["panamericana"]
        assert nueva.item_lista_id == mundo.items["Aserrin de colores x 3 bolsas"]

    async def test_el_puntaje_de_un_concepto_conocido_no_pasa_de_0_9(self, bd, tienda_falsa):
        mundo = _sembrar(bd)
        tienda_falsa.ofertas["exito"] = [_oferta("Tijeras Ficticias", 4000, sku="T1")]

        revision = await abrir_revision(mundo.corto)
        revision = type(revision)(
            version_id=revision.version_id,
            colegio=revision.colegio,
            grado=revision.grado,
            anio=revision.anio,
            items=((mundo.items["Tijeras escolares"], "Tijeras"),),
        )
        await proponer(revision)

        assert float(_propuestas(bd)[0].puntaje) == pytest.approx(0.9)

    async def test_volver_a_revisar_no_vuelve_a_proponer_lo_ya_decidido(self, bd, tienda_falsa, capsys):
        mundo = _sembrar(bd)
        _tijeras_en_tienda(tienda_falsa)
        await proponer(await abrir_revision(mundo.corto))
        capsys.readouterr()

        await proponer(await abrir_revision(mundo.corto))

        assert len(_propuestas(bd)) == 4
        assert "Encoladas para revision: 0" in capsys.readouterr().out

    async def test_lo_rechazado_tampoco_se_vuelve_a_proponer(self, bd, tienda_falsa):
        """Sin esto la persona que ya dijo que no tendria que decirlo cada semana."""
        mundo = _sembrar(bd)
        _tijeras_en_tienda(tienda_falsa)
        await proponer(await abrir_revision(mundo.corto))
        pendiente = next(p for p in _propuestas(bd) if p.referencia_externa == "T1")
        assert await resolver(str(pendiente.id)[:8], False, None, "es otra cosa") == 0

        await proponer(await abrir_revision(mundo.corto))

        assert [p.estado for p in _propuestas(bd) if p.referencia_externa == "T1"] == ["rechazada"]
        assert len(_propuestas(bd)) == 4

    async def test_lo_que_ya_esta_ofertado_en_el_catalogo_no_se_propone(self, bd, tienda_falsa):
        mundo = _sembrar(bd)
        _tijeras_en_tienda(tienda_falsa)
        producto = bd.scalar(select(ProductoCanonico).where(ProductoCanonico.sku_interno == "TK-TIJ-eco"))
        bd.add(
            OfertaTienda(
                producto_canonico_id=producto.id,
                tienda_id=mundo.tiendas["exito"],
                referencia_externa="T1",
                metodo_vinculacion="manual",
                confianza_vinculacion=1.0,
            )
        )
        bd.commit()

        await proponer(await abrir_revision(mundo.corto))

        assert "T1" not in {p.referencia_externa for p in _propuestas(bd)}

    async def test_sin_candidatos_en_ninguna_tienda_no_se_encola_nada(self, bd, tienda_falsa, capsys):
        mundo = _sembrar(bd)
        await proponer(await abrir_revision(mundo.corto))
        assert _propuestas(bd) == []
        assert "Encoladas para revision: 0" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# listar
# ---------------------------------------------------------------------------


class TestListados:
    async def test_pendientes_vacio(self, bd, capsys):
        _sembrar(bd)
        await listar_pendientes()
        assert "No hay nada pendiente de revisar." in capsys.readouterr().out

    async def test_pendientes_muestra_destino_precio_y_nivel_y_oculta_lo_resuelto(self, bd, capsys):
        mundo = _sembrar(bd)
        a_concepto = _propuesta(bd, mundo, referencia_externa="R1")
        nueva = _propuesta(
            bd,
            mundo,
            referencia_externa="R2",
            concepto_id=None,
            concepto_sugerido="aserrin colores",
            nombre="Aserrin Ficticio",
            nivel_sugerido=None,
            precio_centavos=550000,
        )
        rechazada = _propuesta(bd, mundo, referencia_externa="R3", estado="rechazada")

        await listar_pendientes()

        salida = capsys.readouterr().out
        assert "2 propuestas pendientes" in salida
        assert str(a_concepto.id)[:8] in salida
        assert "tijeras" in salida
        assert "nuevo: aserrin colores" in salida
        assert str(nueva.id)[:8] in salida
        assert "$   5500" in salida
        assert str(rechazada.id)[:8] not in salida  # lo ya decidido no vuelve a la cola
        assert salida.count("$") == 2

    async def test_listas_vacio(self, bd, capsys):
        await listar_listas()
        assert "No hay listas cargadas todavia." in capsys.readouterr().out

    async def test_listas_pone_primero_las_abiertas_y_cuenta_los_renglones(self, bd, capsys):
        mundo = _sembrar(bd)
        cerrada = ListaOficial(
            colegio_id=uuid.UUID(int=0xC1), sede_id=None, grado="Tercero", anio_lectivo=2026
        )
        bd.add(cerrada)
        bd.flush()
        bd.add(
            VersionListaOficial(
                lista_id=cerrada.id, numero=1, vigente=True, revisada_en=datetime(2026, 8, 15, tzinfo=UTC)
            )
        )
        bd.commit()

        await listar_listas()

        salida = capsys.readouterr().out
        assert "2 versiones de lista, 1 sin revisar" in salida
        lineas = [ln for ln in salida.splitlines() if "renglones" in ln]
        assert "SIN REVISAR" in lineas[0]
        assert str(mundo.version)[:8] in lineas[0]
        assert "  3 renglones" in lineas[0]
        assert "revisada 2026-08-15" in lineas[1]
        assert "  0 renglones" in lineas[1]


# ---------------------------------------------------------------------------
# probar
# ---------------------------------------------------------------------------


class TestProbar:
    async def test_dice_que_resuelve_el_catalogo_y_que_necesita_revision(self, bd, tienda_falsa, capsys):
        _sembrar(bd)
        bd.add(Concepto(codigo="C003", nombre_canonico="regla", categoria="escritura", sinonimos=[]))
        bd.commit()

        await probar(["Cuaderno cosido 100 hojas", "regla de 30 cm", "punzon metalico"])

        salida = capsys.readouterr().out
        assert "OK       Cuaderno cosido 100 hojas" in salida
        assert "[confiable, economico, premium]" in salida
        assert "SIN QUE  regla de 30 cm" in salida
        assert "concepto sin producto" in salida
        assert "NO       punzon metalico" in salida
        assert "resueltos con catalogo  1/3" in salida
        assert "necesita revision de un administrador" in salida
        assert tienda_falsa.consultas == []  # el match del acudiente jamas sale a una tienda

    async def test_si_todo_se_resuelve_no_pide_revision(self, bd, capsys):
        _sembrar(bd)
        await probar(["cuaderno"])
        salida = capsys.readouterr().out
        assert "resueltos con catalogo  1/1" in salida
        assert "necesita revision" not in salida


# ---------------------------------------------------------------------------
# resolver
# ---------------------------------------------------------------------------


class TestResolverRechazar:
    async def test_una_propuesta_que_no_existe(self, bd, capsys):
        _sembrar(bd)
        assert await resolver("ffffffff", False, None, None) == 1
        assert "No encuentro ninguna propuesta que empiece por ffffffff" in capsys.readouterr().out

    async def test_rechazar_guarda_el_motivo_y_la_hora_y_no_toca_el_concepto(self, bd, capsys):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo)

        assert await resolver(str(p.id)[:8], False, None, "es un corrector") == 0

        bd.rollback()
        bd.refresh(p)
        assert (p.estado, p.motivo) == ("rechazada", "es un corrector")
        assert p.resuelta_en is not None
        assert bd.get(Concepto, mundo.tijeras).tipo_item != "no_comprar"
        salida = capsys.readouterr().out
        assert "Rechazada:" in salida and "motivo: es un corrector" in salida

    async def test_rechazar_con_no_surtir_marca_el_concepto_entero(self, bd, capsys):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo)

        assert await resolver(str(p.id)[:8], False, None, "no lo surtimos", no_surtir=True) == 0

        bd.rollback()
        assert bd.get(Concepto, mundo.tijeras).tipo_item == "no_comprar"
        assert "concepto marcado 'no_comprar'" in capsys.readouterr().out

    async def test_no_surtir_sin_concepto_avisa_y_no_marca_nada(self, bd, capsys):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, concepto_id=None, concepto_sugerido="aserrin colores")

        assert await resolver(str(p.id)[:8], False, None, None, no_surtir=True) == 0

        assert "no se marco no_comprar" in capsys.readouterr().out
        bd.rollback()
        assert {c.tipo_item for c in bd.scalars(select(Concepto))} == {"util"}

    async def test_una_propuesta_ya_resuelta_no_se_resuelve_dos_veces(self, bd, capsys):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo)
        assert await resolver(str(p.id)[:8], False, None, "no") == 0

        assert await resolver(str(p.id)[:8], True, "premium", None) == 1

        assert "Esa propuesta ya esta rechazada." in capsys.readouterr().out
        assert _contar(bd, ProductoCanonico) == 4  # solo los sembrados


class TestResolverAprobar:
    async def test_aprobar_crea_producto_oferta_y_precio_y_marca_la_propuesta(self, bd, capsys):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo)

        assert await resolver(str(p.id)[:8], True, "premium", None) == 0

        bd.rollback()
        pid = _uuid_estable("aprobado", str(mundo.tiendas["exito"]), "REF-1")
        producto = bd.get(ProductoCanonico, pid)
        assert producto.concepto_id == mundo.tijeras
        assert producto.sku_interno == "TK-REV-REF-1"
        assert producto.nombre == "Tijeras Escolares Ficticias Caja x 12 Unidades"
        assert producto.marca == "Marca Ficticia"
        assert producto.ean == "7701234567890"
        assert producto.nivel == "premium"  # el que dijo la persona, no el sugerido
        assert producto.unidades_por_empaque == 12  # sacado del nombre
        assert producto.unidad_base == "unidad"
        assert float(producto.quality_score) == pytest.approx(0.85)
        assert producto.curado_por == AGENTE_FIRECRAWL
        assert producto.es_propio is False and producto.activo is True

        oferta = bd.scalar(select(OfertaTienda).where(OfertaTienda.producto_canonico_id == pid))
        assert oferta.tienda_id == mundo.tiendas["exito"]
        assert oferta.referencia_externa == "REF-1"
        assert oferta.metodo_vinculacion == "ean"  # trae EAN
        assert float(oferta.confianza_vinculacion) == pytest.approx(0.85)
        assert oferta.url == "https://exito.example.test/tijeras/p"
        precio = bd.scalar(select(PrecioOferta).where(PrecioOferta.oferta_id == oferta.id))
        assert (precio.valor_centavos, precio.moneda, precio.fuente) == (900000, "COP", "scraper")

        bd.refresh(p)
        assert p.estado == "aprobada"
        assert p.producto_canonico_id == pid
        assert p.resuelta_en is not None
        salida = capsys.readouterr().out
        assert "Aprobada y en catalogo" in salida
        assert "nivel premium  $9,000  empaque x12" in salida

    async def test_sin_nivel_manda_el_sugerido_y_sin_sugerido_el_confiable(self, bd):
        mundo = _sembrar(bd)
        con = _propuesta(bd, mundo, referencia_externa="R1", nivel_sugerido="economico", ean="7700000000011")
        sin = _propuesta(bd, mundo, referencia_externa="R2", nivel_sugerido=None, ean="7700000000028")

        await resolver(str(con.id)[:8], True, None, None)
        await resolver(str(sin.id)[:8], True, None, None)

        bd.rollback()
        niveles = {
            p.sku_interno: p.nivel
            for p in bd.scalars(select(ProductoCanonico))
            if p.sku_interno.startswith("TK-REV")
        }
        assert niveles == {"TK-REV-R1": "economico", "TK-REV-R2": "confiable"}

    async def test_sin_ean_la_oferta_queda_vinculada_a_mano(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, ean=None)
        await resolver(str(p.id)[:8], True, "economico", None)
        bd.rollback()
        assert bd.scalar(select(OfertaTienda.metodo_vinculacion)) == "manual"

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-12: aprobar una oferta cuyo EAN ya esta en el catalogo (otra tienda) revienta con "
            "FK en oferta_tienda: el INSERT del producto (descubrir.py:781-804) se descarta por "
            "ean UNIQUE y la oferta apunta al id que no se creo"
        ),
    )
    async def test_aprobar_un_ean_que_ya_esta_en_el_catalogo_cuelga_la_oferta_del_producto_existente(
        self, bd
    ):
        """Un producto, varias tiendas: el mismo EAN en dos tiendas es UN producto con DOS ofertas.

        Es el caso normal de un catalogo comparador. Hoy la segunda aprobacion no encuentra el
        producto que el EAN ya tiene y deja la oferta huerfana (la transaccion se deshace).
        """
        mundo = _sembrar(bd)
        en_exito = _propuesta(bd, mundo, referencia_externa="E-1", ean="7700000000035")
        en_panamericana = _propuesta(
            bd,
            mundo,
            referencia_externa="P-1",
            ean="7700000000035",
            tienda_id=mundo.tiendas["panamericana"],
        )
        await resolver(str(en_exito.id)[:8], True, "economico", None)

        await resolver(str(en_panamericana.id)[:8], True, "economico", None)

        bd.rollback()
        assert (
            bd.scalar(
                select(func.count())
                .select_from(ProductoCanonico)
                .where(ProductoCanonico.ean == "7700000000035")
            )
            == 1
        )
        assert _contar(bd, OfertaTienda) == 2
        assert bd.get(PropuestaProducto, en_panamericana.id).estado == "aprobada"

    async def test_aprobar_una_propuesta_sin_concepto_no_crea_nada(self, bd, capsys):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, concepto_id=None, concepto_sugerido="aserrin colores")

        assert await resolver(str(p.id)[:8], True, "economico", None) == 1

        salida = capsys.readouterr().out
        assert "no tiene concepto" in salida and "aserrin colores" in salida
        assert _contar(bd, ProductoCanonico) == 4
        assert _contar(bd, OfertaTienda) == 0
        bd.rollback()
        assert bd.get(PropuestaProducto, p.id).estado == "pendiente"

    async def test_las_correcciones_a_mano_pisan_lo_automatico_y_lo_demas_se_conserva(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, nombre="Tijeras Frozen Escolares")

        await resolver(
            str(p.id)[:8],
            True,
            "economico",
            None,
            overrides={
                "nombre": "  Tijeras Escolares Corregidas  ",
                "marca": "Marca Corregida",
                "imagen_url": "https://img.example.test/corregida.jpg",
                "personaje": None,
                "atributos": {"punta": "roma"},
            },
        )

        bd.rollback()
        producto = bd.scalar(select(ProductoCanonico).where(ProductoCanonico.sku_interno == "TK-REV-REF-1"))
        assert producto.nombre == "Tijeras Escolares Corregidas"
        assert producto.marca == "Marca Corregida"
        assert producto.imagen_url == "https://img.example.test/corregida.jpg"
        assert producto.personaje is None  # la persona quito el personaje que se habia deducido del nombre
        assert producto.atributos == {"punta": "roma"}  # reemplaza, no fusiona

    async def test_sin_correcciones_el_personaje_se_deduce_del_nombre(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, nombre="Tijeras Frozen Escolares")
        await resolver(str(p.id)[:8], True, "economico", None)
        bd.rollback()
        producto = bd.scalar(select(ProductoCanonico).where(ProductoCanonico.sku_interno == "TK-REV-REF-1"))
        assert producto.personaje == "Frozen"

    async def test_los_atributos_se_leen_del_nombre_segun_el_concepto(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(
            bd,
            mundo,
            concepto_id=mundo.cuaderno,
            nombre="Cuaderno Ficticio 100 Hojas Cosido",
            referencia_externa="C1",
        )
        await resolver(str(p.id)[:8], True, "economico", None)
        bd.rollback()
        producto = bd.scalar(select(ProductoCanonico).where(ProductoCanonico.sku_interno == "TK-REV-C1"))
        assert producto.atributos == {"hojas": 100}

    async def test_un_nombre_largo_se_trunca_al_limite_de_la_columna(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, nombre="Tijeras " + "x" * 400)
        await resolver(str(p.id)[:8], True, "economico", None)
        bd.rollback()
        producto = bd.scalar(select(ProductoCanonico).where(ProductoCanonico.sku_interno == "TK-REV-REF-1"))
        assert len(producto.nombre) == 255

    async def test_si_el_producto_ya_existia_no_se_duplica_nada(self, bd):
        """Un reintento tras una caida a mitad de camino no deja productos, ofertas ni precios dobles."""
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo)
        await resolver(str(p.id)[:8], True, "economico", None)
        bd.rollback()
        bd.execute(PropuestaProducto.__table__.update().values(estado="pendiente", producto_canonico_id=None))
        bd.commit()

        assert await resolver(str(p.id)[:8], True, "economico", None) == 0

        assert _contar(bd, ProductoCanonico) == 5
        assert _contar(bd, OfertaTienda) == 1
        assert _contar(bd, PrecioOferta) == 1
        bd.rollback()
        assert bd.get(PropuestaProducto, p.id).estado == "aprobada"


# ---------------------------------------------------------------------------
# crear_libro
# ---------------------------------------------------------------------------


class TestCrearLibro:
    async def test_encola_el_libro_con_su_isbn_como_referencia(self, bd, capsys):
        mundo = _sembrar(bd)

        codigo = await crear_libro(
            mundo.corto,
            "978-958-07-1472-9",
            "Libro Ficticio de Lectura",
            52000,
            "panamericana",
            "https://panamericana.example.test/libro",
            "https://img.example.test/libro.jpg",
            None,
        )

        assert codigo == 0
        (p,) = _propuestas(bd)
        assert p.id == _uuid_estable("propuesta", "panamericana", ISBN_VALIDO)
        assert p.referencia_externa == ISBN_VALIDO
        assert p.ean == ISBN_VALIDO
        assert p.nombre == "Libro Ficticio de Lectura"
        assert p.precio_centavos == 5200000
        assert p.tienda_id == mundo.tiendas["panamericana"]
        assert (p.origen, p.estado, p.nivel_sugerido) == ("manual", "pendiente", "confiable")
        assert float(p.puntaje) == pytest.approx(0.9)
        assert p.especificaciones == {"isbn": ISBN_VALIDO}
        assert p.concepto_id is None and p.concepto_sugerido == "Libro Ficticio de Lectura"
        assert p.version_lista_id == mundo.version
        assert "Encolado a mano" in capsys.readouterr().out

    async def test_con_concepto_cuelga_de_el_y_no_sugiere_uno_nuevo(self, bd):
        mundo = _sembrar(bd)
        assert await crear_libro(mundo.corto, ISBN_VALIDO, "Libro", 52000, "exito", None, None, "C002") == 0
        (p,) = _propuestas(bd)
        assert p.concepto_id == mundo.tijeras
        assert p.concepto_sugerido is None

    async def test_el_mismo_isbn_en_la_misma_tienda_se_propone_una_sola_vez(self, bd, capsys):
        mundo = _sembrar(bd)
        await crear_libro(mundo.corto, ISBN_VALIDO, "Libro", 52000, "exito", None, None, None)
        capsys.readouterr()

        assert (
            await crear_libro(mundo.corto, ISBN_VALIDO, "Libro Otra Vez", 60000, "exito", None, None, None)
            == 0
        )

        assert "Ese ISBN ya estaba propuesto para exito." in capsys.readouterr().out
        assert [p.nombre for p in _propuestas(bd)] == ["Libro"]

    @pytest.mark.parametrize(
        ("isbn", "tienda", "concepto", "mensaje"),
        [
            (ISBN_MALO, "exito", None, "no pasa el digito de control"),
            ("12345", "exito", None, "no pasa el digito de control"),
            (ISBN_VALIDO, "libreria-inexistente", None, "No conozco la tienda 'libreria-inexistente'"),
            (ISBN_VALIDO, "exito", "C999", "No existe el concepto 'C999'"),
        ],
    )
    async def test_los_datos_malos_se_rechazan_antes_de_encolar(
        self, bd, capsys, isbn, tienda, concepto, mensaje
    ):
        """Un ISBN mal copiado entra sin ruido y el dia de la compra resulta ser otra edicion."""
        mundo = _sembrar(bd)

        assert await crear_libro(mundo.corto, isbn, "Libro", 52000, tienda, None, None, concepto) == 1

        assert mensaje in capsys.readouterr().out
        assert _propuestas(bd) == []


# ---------------------------------------------------------------------------
# crear_util
# ---------------------------------------------------------------------------


class TestCrearUtil:
    async def test_un_concepto_inexistente_se_rechaza_antes_de_consultar_tiendas(
        self, bd, tienda_falsa, capsys
    ):
        mundo = _sembrar(bd)
        assert await crear_util(mundo.corto, "C999", "tijeras", None) == 1
        assert "No existe el concepto 'C999'" in capsys.readouterr().out
        assert tienda_falsa.consultas == []

    async def test_sin_candidatos_lo_dice_y_no_es_un_error(self, bd, tienda_falsa, capsys):
        mundo = _sembrar(bd)
        assert await crear_util(mundo.corto, "C002", "tijeras", None) == 0
        assert "Ninguna tienda devolvio algo que contenga 'tijeras'" in capsys.readouterr().out

    async def test_sin_elegir_lista_los_candidatos_validos_por_precio_y_no_escribe(
        self, bd, tienda_falsa, capsys
    ):
        mundo = _sembrar(bd)
        tienda_falsa.ofertas["exito"] = [
            _oferta("Tijeras Escolares Caras", 12000, sku="caras"),
            _oferta("Tijeras Escolares Agotadas", 3000, sku="agotadas", disponible=False),
            _oferta("Tijeras Escolares Regaladas", 0, sku="cero"),
            _oferta("Cuchillo De Cocina", 3000, sku="cuchillo"),  # no contiene todas las palabras
        ]
        tienda_falsa.ofertas["panamericana"] = [
            _oferta("Tijeras Escolares Baratas", 4000, sku="baratas", tienda="panamericana")
        ]

        assert await crear_util(mundo.corto, "C002", "tijeras escolares", None) == 0

        salida = capsys.readouterr().out
        assert "Candidatos para C002 (tijeras)" in salida
        filas = [ln for ln in salida.splitlines() if "Tijeras Escolares" in ln and "$" in ln]
        assert len(filas) == 2
        assert "Baratas" in filas[0] and "Caras" in filas[1]  # del mas barato al mas caro
        assert "2 candidatos" in salida
        assert "Cuchillo" not in salida and "Agotadas" not in salida and "Regaladas" not in salida
        assert _propuestas(bd) == []

    async def test_una_tienda_que_la_base_no_conoce_se_salta(self, bd, tienda_falsa, capsys):
        mundo = _sembrar(bd)
        bd.execute(Tienda.__table__.delete().where(Tienda.slug == "grancentral"))
        bd.commit()
        tienda_falsa.ofertas["grancentral"] = [
            _oferta("Tijeras Escolares Fantasma", 4000, tienda="grancentral")
        ]

        assert await crear_util(mundo.corto, "C002", "tijeras escolares", None) == 0

        assert "Ninguna tienda devolvio" in capsys.readouterr().out
        assert all(t != "grancentral" for t, _c in tienda_falsa.consultas)

    @pytest.mark.parametrize("indice", [2, -1, 99])
    async def test_un_indice_fuera_de_rango_se_rechaza(self, bd, tienda_falsa, capsys, indice):
        mundo = _sembrar(bd)
        tienda_falsa.ofertas["exito"] = [
            _oferta("Tijeras Escolares Uno", 4000, sku="u1"),
            _oferta("Tijeras Escolares Dos", 5000, sku="u2"),
        ]

        assert await crear_util(mundo.corto, "C002", "tijeras escolares", indice) == 1

        assert "hay 2 candidatos (0 a 1)" in capsys.readouterr().out
        assert _propuestas(bd) == []

    async def test_elegir_encola_ese_candidato_contra_el_concepto(self, bd, tienda_falsa, capsys):
        mundo = _sembrar(bd)
        tienda_falsa.ofertas["exito"] = [
            _oferta(
                "Tijeras Escolares Dos",
                5000,
                sku="u2",
                ean="7701234567890",
                especificaciones={"Punta": "Roma"},
            ),
            _oferta("Tijeras Escolares Uno", 4000, sku="u1", ean="no-es-un-ean"),
        ]

        assert await crear_util(mundo.corto, "C002", "tijeras escolares", 1) == 0

        (p,) = _propuestas(bd)
        assert p.referencia_externa == "u2"  # el indice 1 del orden por precio
        assert p.id == _uuid_estable("util", "exito", "u2")
        assert p.concepto_id == mundo.tijeras
        assert p.texto_origen == "tijeras"
        assert p.ean == "7701234567890"
        assert p.precio_centavos == 500000
        assert p.especificaciones == {"Punta": "Roma"}
        assert p.nivel_sugerido is None  # el nivel lo pone quien aprueba
        assert (p.origen, p.estado) == ("manual", "pendiente")
        assert float(p.puntaje) == pytest.approx(0.6)
        assert p.version_lista_id == mundo.version
        assert "Encolado para C002" in capsys.readouterr().out

    async def test_un_ean_que_no_lo_es_no_ensucia_la_propuesta(self, bd, tienda_falsa):
        mundo = _sembrar(bd)
        tienda_falsa.ofertas["exito"] = [_oferta("Tijeras Escolares Uno", 4000, sku="u1", ean="SKU-INTERNO")]
        await crear_util(mundo.corto, "C002", "tijeras escolares", 0)
        assert _propuestas(bd)[0].ean is None

    async def test_elegir_dos_veces_el_mismo_producto_no_duplica(self, bd, tienda_falsa, capsys):
        mundo = _sembrar(bd)
        tienda_falsa.ofertas["exito"] = [_oferta("Tijeras Escolares Uno", 4000, sku="u1")]
        await crear_util(mundo.corto, "C002", "tijeras escolares", 0)
        capsys.readouterr()

        assert await crear_util(mundo.corto, "C002", "tijeras escolares", 0) == 0

        assert "Ese producto de exito ya estaba propuesto." in capsys.readouterr().out
        assert len(_propuestas(bd)) == 1


# ---------------------------------------------------------------------------
# cerrar
# ---------------------------------------------------------------------------


class TestCerrar:
    async def test_una_version_que_no_existe(self, bd, capsys):
        _sembrar(bd)
        assert await cerrar("ffffffff") == 1
        assert "No existe ninguna version que empiece por ffffffff" in capsys.readouterr().out

    async def test_con_propuestas_pendientes_se_niega_y_la_deja_abierta(self, bd, capsys):
        mundo = _sembrar(bd)
        _propuesta(bd, mundo)

        assert await cerrar(mundo.corto) == 1

        salida = capsys.readouterr().out
        assert "Quedan 1 propuestas sin decidir" in salida
        bd.rollback()
        assert bd.get(VersionListaOficial, mundo.version).revisada_en is None

    async def test_sin_pendientes_la_cierra_y_la_puerta_ya_no_abre(self, bd, capsys):
        """Lo aprobado y lo rechazado no bloquean; las pendientes de OTRA lista tampoco."""
        mundo = _sembrar(bd)
        _propuesta(bd, mundo, referencia_externa="R1", estado="rechazada")
        otra = ListaOficial(colegio_id=uuid.UUID(int=0xC2), sede_id=None, grado="Quinto", anio_lectivo=2026)
        bd.add(otra)
        bd.flush()
        otra_version = VersionListaOficial(lista_id=otra.id, numero=1, vigente=True)
        bd.add(otra_version)
        bd.commit()
        _propuesta(bd, mundo, referencia_externa="R2", version_lista_id=otra_version.id)

        assert await cerrar(mundo.corto) == 0

        assert "Lista revisada." in capsys.readouterr().out
        bd.rollback()
        assert bd.get(VersionListaOficial, mundo.version).revisada_en is not None
        assert bd.get(VersionListaOficial, otra_version.id).revisada_en is None
        with pytest.raises(PuertaCerrada):
            await abrir_revision(mundo.corto)

    async def test_cerrar_dos_veces_no_mueve_la_fecha(self, bd, capsys):
        mundo = _sembrar(bd, revisada=True)
        assert await cerrar(mundo.corto) == 0
        assert "Ya estaba revisada el 2026-09-01." in capsys.readouterr().out
        bd.rollback()
        assert bd.get(VersionListaOficial, mundo.version).revisada_en.date().isoformat() == "2026-09-01"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _correr(monkeypatch, *argumentos: str) -> int:
    monkeypatch.setattr("sys.argv", ["descubrir", *argumentos])
    return descubrir.main()


class TestMain:
    def test_sin_argumentos_imprime_la_ayuda_y_sale_con_2(self, monkeypatch, capsys):
        assert _correr(monkeypatch) == 2
        assert "--revisar" in capsys.readouterr().out

    def test_listas_y_pendientes(self, bd, monkeypatch, capsys):
        mundo = _sembrar(bd)
        assert _correr(monkeypatch, "--listas") == 0
        assert mundo.corto in capsys.readouterr().out
        assert _correr(monkeypatch, "--pendientes") == 0
        assert "No hay nada pendiente" in capsys.readouterr().out

    def test_probar_un_renglon_y_un_archivo_de_renglones(self, bd, tmp_path, monkeypatch, capsys):
        _sembrar(bd)
        assert _correr(monkeypatch, "--probar", "cuaderno") == 0
        assert "resueltos con catalogo  1/1" in capsys.readouterr().out

        archivo = tmp_path / "renglones.txt"
        archivo.write_text("cuaderno\n\n   \npunzon metalico\n", encoding="utf-8")
        assert _correr(monkeypatch, "--desde-lista", str(archivo)) == 0
        assert "resueltos con catalogo  1/2" in capsys.readouterr().out  # las lineas en blanco no cuentan

    def test_revisar_propone_y_cerrar_se_niega_mientras_haya_pendientes(
        self, bd, tienda_falsa, monkeypatch, capsys
    ):
        mundo = _sembrar(bd)
        _tijeras_en_tienda(tienda_falsa)

        assert _correr(monkeypatch, "--revisar", mundo.corto) == 0
        assert "Encoladas para revision: 4" in capsys.readouterr().out
        assert _correr(monkeypatch, "--cerrar", mundo.corto) == 1

    def test_aprobar_y_rechazar_por_linea_de_comandos(self, bd, monkeypatch, capsys):
        mundo = _sembrar(bd)
        a = _propuesta(bd, mundo, referencia_externa="R1")
        r = _propuesta(bd, mundo, referencia_externa="R2")

        assert _correr(monkeypatch, "--aprobar", str(a.id)[:8], "--nivel", "premium") == 0
        assert _correr(monkeypatch, "--rechazar", str(r.id)[:8], "--motivo", "no sirve", "--no-surtir") == 0

        bd.rollback()
        assert bd.get(PropuestaProducto, a.id).estado == "aprobada"
        assert bd.get(PropuestaProducto, r.id).motivo == "no sirve"
        assert bd.get(Concepto, mundo.tijeras).tipo_item == "no_comprar"
        capsys.readouterr()

    def test_revisar_una_lista_cerrada_sale_con_1_y_lo_dice(self, bd, monkeypatch, capsys):
        mundo = _sembrar(bd, revisada=True)
        assert _correr(monkeypatch, "--revisar", mundo.corto) == 1
        assert "ya fue revisada" in capsys.readouterr().out

    @pytest.mark.parametrize("bandera", ["--crear-libro", "--crear-util"])
    def test_las_altas_a_mano_exigen_una_revision(self, monkeypatch, capsys, bandera):
        assert _correr(monkeypatch, bandera) == 2
        assert "agrega --revisar" in capsys.readouterr().out

    def test_crear_libro_dice_que_argumentos_faltan(self, monkeypatch, capsys):
        assert _correr(monkeypatch, "--crear-libro", "--revisar", "abcd1234", "--isbn", ISBN_VALIDO) == 2
        assert "--titulo, --precio, --tienda" in capsys.readouterr().out

    def test_crear_util_dice_que_argumentos_faltan(self, monkeypatch, capsys):
        assert _correr(monkeypatch, "--crear-util", "--revisar", "abcd1234", "--concepto", "C002") == 2
        assert "faltan: --consulta" in capsys.readouterr().out

    def test_crear_libro_por_linea_de_comandos(self, bd, monkeypatch):
        mundo = _sembrar(bd)
        argumentos = [
            "--crear-libro", "--revisar", mundo.corto, "--isbn", ISBN_VALIDO,
            "--titulo", "Libro Ficticio", "--precio", "40000", "--tienda", "exito",
        ]  # fmt: skip
        assert _correr(monkeypatch, *argumentos) == 0
        assert [p.referencia_externa for p in _propuestas(bd)] == [ISBN_VALIDO]

    def test_crear_libro_sobre_una_lista_cerrada_sale_con_1(self, bd, monkeypatch, capsys):
        mundo = _sembrar(bd, revisada=True)
        argumentos = [
            "--crear-libro", "--revisar", mundo.corto, "--isbn", ISBN_VALIDO,
            "--titulo", "Libro Ficticio", "--precio", "40000", "--tienda", "exito",
        ]  # fmt: skip
        assert _correr(monkeypatch, *argumentos) == 1
        assert "ya fue revisada" in capsys.readouterr().out

    def test_crear_util_por_linea_de_comandos(self, bd, tienda_falsa, monkeypatch, capsys):
        mundo = _sembrar(bd)
        tienda_falsa.ofertas["exito"] = [_oferta("Tijeras Escolares Uno", 4000, sku="u1")]
        base = [
            "--crear-util",
            "--revisar",
            mundo.corto,
            "--concepto",
            "C002",
            "--consulta",
            "tijeras escolares",
        ]

        assert _correr(monkeypatch, *base) == 0  # solo lista
        assert _propuestas(bd) == []
        assert _correr(monkeypatch, *base, "--elegir", "0") == 0
        assert [p.referencia_externa for p in _propuestas(bd)] == ["u1"]
        capsys.readouterr()

    def test_crear_util_sobre_una_lista_cerrada_sale_con_1(self, bd, monkeypatch, capsys):
        mundo = _sembrar(bd, revisada=True)
        argumentos = ["--crear-util", "--revisar", mundo.corto, "--concepto", "C002", "--consulta", "tijeras"]
        assert _correr(monkeypatch, *argumentos) == 1
        assert "ya fue revisada" in capsys.readouterr().out
