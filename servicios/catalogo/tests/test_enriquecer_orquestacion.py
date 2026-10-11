"""NFR-MAN-01: el enriquecedor escribe lo que el nombre y la ficha dicen, y nada mas.

`test_enriquecer` fija los extractores puros (empaque, atributos, personaje).
Aqui se fija lo que decide que se ESCRIBE en el catalogo, contra un esquema
SQLite real y sin salir a ninguna parte:

- **Lo curado a mano no se pisa.** Una persona que reviso un producto vale mas
  que una expresion regular: atributos, imagen y personaje ya puestos sobreviven.
- **El nombre manda sobre la ficha.** La ficha de la tienda solo rellena lo que
  el nombre no dijo; si hablan de lo mismo, gana lo que el papa va a leer.
- **Idempotencia.** Correr dos veces deja el mismo catalogo y no recalcula
  vectores que no cambiaron (cada llamada al proveedor cuesta).
- **`--solo-validar` no escribe**, ni siquiera los vectores.
- **El canal semantico es opcional.** Sin embeder, el nombre se enriquece igual y
  se avisa; con `--sin-embeddings` ni se pregunta por el embeder.
- **`admite_personaje` se deduce de los datos**, no se mantiene a mano.

Los extractores que `test_enriquecer` no alcanza (medidas, piezas, conteos
sueltos) se fijan al final. La tienda se sustituye en `tiendas.ficha` (jamas red)
y el embeder es el falso de trigramas: la rama que lee la clave del proveedor
real queda fuera de estas pruebas a proposito.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from tukit_catalogo import enriquecer
from tukit_catalogo.embeddings import MODELO_FALSO, embeder_falso
from tukit_catalogo.enriquecer import (
    Empaque,
    _guardar_embeddings,
    _unidad_corta,
    extraer_atributos,
    extraer_empaque,
    imagen_desde_ficha,
)
from tukit_catalogo.modelos import Base, Concepto, OfertaTienda, ProductoCanonico, Tienda
from tukit_catalogo.tiendas import Oferta
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

CURADOR = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
IMAGEN_CURADA = "https://img.example.test/curada.jpg"


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


def _producto(concepto: Concepto, sku: str, nombre: str, **kw) -> ProductoCanonico:
    return ProductoCanonico(
        concepto_id=concepto.id, sku_interno=sku, nombre=nombre, nivel="economico", curado_por=CURADOR, **kw
    )


def _sembrar(bd: Session) -> dict[str, Concepto]:
    """Cuatro conceptos y seis productos; cada uno ejercita una decision distinta."""
    cuaderno = Concepto(
        codigo="C001",
        nombre_canonico="cuaderno",
        categoria="escritura",
        sinonimos=[],
        atributos_discriminantes=["hojas"],
        atributos_descriptivos=["material"],
    )
    tijeras = Concepto(
        codigo="C002",
        nombre_canonico="tijeras",
        categoria="manualidades",
        sinonimos=[],
        atributos_discriminantes=[],
    )
    regla = Concepto(
        codigo="C003",
        nombre_canonico="regla",
        categoria="escritura",
        sinonimos=[],
        atributos_discriminantes=["longitud"],
    )
    bd.add_all([cuaderno, tijeras, regla])
    bd.flush()
    exito = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    bd.add(exito)
    bd.flush()

    productos = [
        # Nombre con hojas y sin nada curado.
        _producto(cuaderno, "SKU-1", "Cuaderno Ficticio 100 Hojas Cosido"),
        # Empaque y personaje salen del nombre.
        _producto(tijeras, "SKU-2", "Tijeras Frozen Ficticias Caja x 12 Unidades"),
        # Curado a mano: nada de esto debe cambiar aunque el nombre diga otra cosa.
        _producto(
            cuaderno,
            "SKU-3",
            "Cuaderno Curado 50 Hojas",
            atributos={"hojas": 80},
            imagen_url=IMAGEN_CURADA,
            personaje="Personaje Curado",
        ),
        # El nombre no dice las hojas: solo la ficha de la tienda las sabe.
        _producto(cuaderno, "SKU-4", "Cuaderno Ficticio Argollado"),
        _producto(regla, "SKU-5", "Regla Plastica Ficticia 30 cm"),
        # Sin oferta y sin nada que leer.
        _producto(tijeras, "SKU-6", "Tijeras Ficticias Punta Roma"),
    ]
    bd.add_all(productos)
    bd.flush()
    for producto, url in (
        (productos[0], "https://exito.example.test/p1"),
        (productos[3], "https://exito.example.test/p4"),
    ):
        bd.add(
            OfertaTienda(
                producto_canonico_id=producto.id,
                tienda_id=exito.id,
                referencia_externa=producto.sku_interno,
                url=url,
                metodo_vinculacion="manual",
                confianza_vinculacion=1.0,
            )
        )
    # Una oferta sin direccion: no hay ficha que leer.
    bd.add(
        OfertaTienda(
            producto_canonico_id=productos[5].id,
            tienda_id=exito.id,
            referencia_externa="SKU-6",
            url=None,
            metodo_vinculacion="manual",
            confianza_vinculacion=1.0,
        )
    )
    bd.commit()
    return {"cuaderno": cuaderno, "tijeras": tijeras, "regla": regla}


def _fila(bd: Session, sku: str) -> ProductoCanonico:
    bd.rollback()
    bd.expire_all()
    return bd.scalar(select(ProductoCanonico).where(ProductoCanonico.sku_interno == sku))


def _instantanea(bd: Session) -> dict[str, tuple]:
    bd.rollback()
    bd.expire_all()
    return {
        p.sku_interno: (
            p.unidades_por_empaque,
            p.unidad_base,
            dict(p.atributos or {}),
            p.imagen_url,
            p.personaje,
            p.embedding_model,
            p.texto_embedding,
        )
        for p in bd.scalars(select(ProductoCanonico))
    }


def _ficha(
    nombre: str, *, imagen: str | None = None, especificaciones: dict[str, str] | None = None
) -> Oferta:
    return Oferta(
        tienda="exito",
        nombre=nombre,
        precio_cop=5000,
        disponible=True,
        imagen_url=imagen,
        url="https://exito.example.test/x",
        sku="X",
        ean=None,
        marca=None,
        especificaciones=especificaciones or {},
    )


class FichasFalsas:
    """Sustituye a `tiendas.ficha`: responde por direccion y anota cada lectura."""

    def __init__(self, fichas: dict[str, Oferta]) -> None:
        self.fichas = fichas
        self.leidas: list[str] = []

    def __call__(self, direccion: str) -> Oferta | None:
        self.leidas.append(direccion)
        return self.fichas.get(direccion)


class EmbederEspia:
    """Embeder falso (trigramas) que anota cuantos textos le pidieron."""

    modelo = MODELO_FALSO

    def __init__(self) -> None:
        self.pedidos: list[list[str]] = []

    def __call__(self, textos):  # noqa: ANN001, ANN204
        self.pedidos.append(list(textos))
        return embeder_falso(textos)


@pytest.fixture()
def embeder(monkeypatch: pytest.MonkeyPatch) -> EmbederEspia:
    espia = EmbederEspia()
    monkeypatch.setattr(enriquecer, "_embeder_por_entorno", lambda: espia)
    return espia


@pytest.fixture()
def sin_embeder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(enriquecer, "_embeder_por_entorno", lambda: None)


# ---------------------------------------------------------------------------
# Lectura del contexto
# ---------------------------------------------------------------------------


class TestCargarContexto:
    async def test_junta_productos_atributos_requeridos_direcciones_y_nombres(self, bd):
        conceptos = _sembrar(bd)

        # Desde a50c334 el contexto trae tambien el codigo de cada concepto
        # (enriquecer.py:1251, :1259).
        productos, requeridos, urls, nombres, codigos = await enriquecer._cargar_contexto()

        assert {p["nombre"] for p in productos} >= {
            "Cuaderno Curado 50 Hojas",
            "Regla Plastica Ficticia 30 cm",
        }
        assert len(productos) == 6
        curado = next(p for p in productos if p["nombre"] == "Cuaderno Curado 50 Hojas")
        assert curado["atributos"] == {"hojas": 80}
        assert curado["personaje"] == "Personaje Curado"
        assert curado["texto_embedding"] is None and curado["embedding_model"] is None
        # Discriminantes y descriptivos, en ese orden: el enriquecedor lee TODO lo que pueda.
        assert requeridos[str(conceptos["cuaderno"].id)] == ("hojas", "material")
        assert requeridos[str(conceptos["tijeras"].id)] == ()
        assert nombres[str(conceptos["regla"].id)] == "regla"
        assert codigos[str(conceptos["regla"].id)] == "C003"

    async def test_solo_cuentan_las_ofertas_con_direccion(self, bd):
        _sembrar(bd)
        productos, _req, urls, _nombres, _codigos = await enriquecer._cargar_contexto()
        por_nombre = {p["nombre"]: str(p["id"]) for p in productos}
        assert urls[por_nombre["Cuaderno Ficticio 100 Hojas Cosido"]] == ["https://exito.example.test/p1"]
        assert (
            str(next(p["id"] for p in productos if p["nombre"] == "Tijeras Ficticias Punta Roma")) not in urls
        )
        assert len(urls) == 2


# ---------------------------------------------------------------------------
# Lo que se escribe a partir del nombre
# ---------------------------------------------------------------------------


class TestEscrituraDesdeElNombre:
    async def test_escribe_empaque_atributos_y_personaje_leidos_del_nombre(self, bd, sin_embeder, capsys):
        _sembrar(bd)

        assert await enriquecer._principal(False, False, False) == 0

        cuaderno = _fila(bd, "SKU-1")
        assert (cuaderno.unidades_por_empaque, cuaderno.atributos) == (1, {"hojas": 100})
        tijeras = _fila(bd, "SKU-2")
        assert (tijeras.unidades_por_empaque, tijeras.unidad_base, tijeras.personaje) == (
            12,
            "unidad",
            "Frozen",
        )
        assert _fila(bd, "SKU-5").atributos == {"longitud": "30 cm"}
        salida = capsys.readouterr().out
        assert "empaque corregido (ya no es 1)         1/6" in salida
        assert "Escrito." in salida

    async def test_lo_curado_a_mano_no_se_pisa(self, bd, sin_embeder):
        """El nombre dice 50 hojas; la persona dejo 80. Gana la persona, y su imagen y personaje."""
        _sembrar(bd)

        await enriquecer._principal(False, False, False)

        curado = _fila(bd, "SKU-3")
        assert curado.atributos == {"hojas": 80}
        assert curado.imagen_url == IMAGEN_CURADA
        assert curado.personaje == "Personaje Curado"

    async def test_lo_curado_se_conserva_y_lo_nuevo_se_suma(self, bd, sin_embeder):
        conceptos = _sembrar(bd)
        bd.add(
            _producto(
                conceptos["cuaderno"], "SKU-7", "Cuaderno Mixto 100 Hojas", atributos={"material": "papel"}
            )
        )
        bd.commit()

        await enriquecer._principal(False, False, False)

        assert _fila(bd, "SKU-7").atributos == {"hojas": 100, "material": "papel"}

    async def test_correr_dos_veces_deja_el_mismo_catalogo(self, bd, sin_embeder):
        _sembrar(bd)
        await enriquecer._principal(False, False, False)
        primera = _instantanea(bd)

        await enriquecer._principal(False, False, False)

        assert _instantanea(bd) == primera

    async def test_un_concepto_admite_personaje_si_alguno_de_sus_productos_lo_tiene(self, bd, sin_embeder):
        """Se deduce de los datos: la bandera a mano decia siete conceptos y habia mas."""
        conceptos = _sembrar(bd)

        await enriquecer._principal(False, False, False)

        bd.rollback()
        bd.expire_all()
        assert bd.get(Concepto, conceptos["tijeras"].id).admite_personaje is True  # Frozen
        assert bd.get(Concepto, conceptos["cuaderno"].id).admite_personaje is True  # personaje curado
        assert bd.get(Concepto, conceptos["regla"].id).admite_personaje is False  # nadie tiene personaje

    async def test_solo_validar_cuenta_pero_no_escribe(self, bd, embeder, capsys):
        _sembrar(bd)
        antes = _instantanea(bd)

        assert await enriquecer._principal(False, True, True) == 0

        assert _instantanea(bd) == antes
        salida = capsys.readouterr().out
        assert "(--solo-validar: no se escribio nada)" in salida
        assert "embeddings a (re)calcular              6/6" in salida  # lo cuenta, pero no lo guarda
        assert "Escrito." not in salida


# ---------------------------------------------------------------------------
# La ficha de la tienda
# ---------------------------------------------------------------------------


class TestFichaDeLaTienda:
    @pytest.fixture()
    def fichas(self, monkeypatch: pytest.MonkeyPatch) -> FichasFalsas:
        falsas = FichasFalsas(
            {
                "https://exito.example.test/p1": _ficha(
                    "Cuaderno Ficticio",
                    imagen="https://img.example.test/p1.jpg",
                    especificaciones={"Número de hojas": "50"},
                ),
                "https://exito.example.test/p4": _ficha(
                    "Cuaderno Ficticio Argollado",
                    imagen=None,
                    especificaciones={"Número de hojas": "80", "Personaje": "Frozen"},
                ),
            }
        )
        monkeypatch.setattr(enriquecer.tiendas, "ficha", falsas)
        return falsas

    async def test_la_portada_de_la_ficha_llena_la_imagen_que_faltaba(self, bd, sin_embeder, fichas, capsys):
        _sembrar(bd)

        await enriquecer._principal(True, False, False)

        assert _fila(bd, "SKU-1").imagen_url == "https://img.example.test/p1.jpg"
        assert _fila(bd, "SKU-4").imagen_url is None  # la ficha no traia portada: no se inventa
        assert "fichas leidas: 2/2   con portada: 1" in capsys.readouterr().out

    async def test_solo_se_leen_las_fichas_de_productos_a_los_que_les_falta_algo_y_tienen_direccion(
        self, bd, sin_embeder, fichas
    ):
        _sembrar(bd)

        await enriquecer._principal(True, False, False)

        # SKU-3 ya tiene imagen y atributos; SKU-6 tiene la oferta sin direccion.
        assert sorted(fichas.leidas) == ["https://exito.example.test/p1", "https://exito.example.test/p4"]

    async def test_el_nombre_manda_sobre_la_ficha_y_la_ficha_rellena_lo_que_el_nombre_calla(
        self, bd, sin_embeder, fichas
    ):
        _sembrar(bd)

        await enriquecer._principal(True, False, False)

        assert _fila(bd, "SKU-1").atributos == {"hojas": 100}  # el nombre dice 100, la ficha 50
        assert _fila(bd, "SKU-4").atributos == {"hojas": 80}  # el nombre no decia nada

    async def test_el_personaje_que_declara_la_tienda_se_usa_si_el_nombre_no_lo_dice(
        self, bd, sin_embeder, fichas
    ):
        _sembrar(bd)
        await enriquecer._principal(True, False, False)
        assert _fila(bd, "SKU-4").personaje == "Frozen"
        assert _fila(bd, "SKU-1").personaje is None

    async def test_sin_la_bandera_de_imagenes_no_se_lee_ninguna_ficha(self, bd, sin_embeder, fichas):
        _sembrar(bd)
        await enriquecer._principal(False, False, False)
        assert fichas.leidas == []
        assert _fila(bd, "SKU-4").atributos == {}

    async def test_si_la_primera_direccion_no_responde_se_prueba_la_siguiente(
        self, bd, sin_embeder, monkeypatch
    ):
        """Un mismo producto en dos tiendas: si la ficha de la primera cayo, sirve la de la segunda."""
        _sembrar(bd)
        producto = _fila(bd, "SKU-6")
        bd.execute(OfertaTienda.__table__.delete().where(OfertaTienda.referencia_externa == "SKU-6"))
        bd.commit()
        exito = bd.scalar(select(Tienda).where(Tienda.slug == "exito"))
        otra = Tienda(slug="panamericana", nombre="Panamericana", tipo="minorista")
        bd.add(otra)
        bd.flush()
        for tienda, referencia, url in (
            (exito, "SKU-6B", "https://exito.example.test/p6-caido"),
            (otra, "SKU-6C", "https://panamericana.example.test/p6-vivo"),
        ):
            bd.add(
                OfertaTienda(
                    producto_canonico_id=producto.id,
                    tienda_id=tienda.id,
                    referencia_externa=referencia,
                    url=url,
                    metodo_vinculacion="manual",
                    confianza_vinculacion=1.0,
                )
            )
        bd.commit()
        falsas = FichasFalsas(
            {
                "https://panamericana.example.test/p6-vivo": _ficha(
                    "Tijeras", imagen="https://img.example.test/6.jpg"
                )
            }
        )
        monkeypatch.setattr(enriquecer.tiendas, "ficha", falsas)

        await enriquecer._principal(True, False, False)

        assert _fila(bd, "SKU-6").imagen_url == "https://img.example.test/6.jpg"
        assert (
            falsas.leidas.count("https://exito.example.test/p6-caido") == 1
        )  # se intento y se paso a la siguiente


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class TestCanalSemantico:
    async def test_calcula_y_guarda_un_vector_por_producto_con_la_huella_del_texto(self, bd, embeder, capsys):
        _sembrar(bd)

        await enriquecer._principal(False, False, True)

        assert len(embeder.pedidos) == 1  # una sola peticion con todos los textos
        assert len(embeder.pedidos[0]) == 6
        cuaderno = _fila(bd, "SKU-1")
        assert len(cuaderno.embedding) == 1024
        assert cuaderno.embedding_model == MODELO_FALSO
        # El texto se arma de lo ya enriquecido: nombre + concepto + atributos finales.
        assert "cuaderno" in cuaderno.texto_embedding.lower()
        assert "100" in cuaderno.texto_embedding
        assert "embeddings a (re)calcular              6/6" in capsys.readouterr().out

    async def test_la_segunda_pasada_no_vuelve_a_llamar_al_proveedor(self, bd, embeder):
        _sembrar(bd)
        await enriquecer._principal(False, False, True)
        embeder.pedidos.clear()

        await enriquecer._principal(False, False, True)

        assert embeder.pedidos == []

    async def test_solo_se_recalcula_el_producto_cuyo_texto_cambio(self, bd, embeder):
        _sembrar(bd)
        await enriquecer._principal(False, False, True)
        embeder.pedidos.clear()
        producto = _fila(bd, "SKU-6")
        producto.nombre = "Tijeras Ficticias Punta Redonda"
        bd.commit()

        await enriquecer._principal(False, False, True)

        assert len(embeder.pedidos) == 1 and len(embeder.pedidos[0]) == 1
        assert "redonda" in embeder.pedidos[0][0].lower()

    async def test_sin_embeder_se_enriquece_el_nombre_y_se_avisa(self, bd, sin_embeder, capsys):
        _sembrar(bd)

        await enriquecer._principal(False, False, True)

        assert _fila(bd, "SKU-2").unidades_por_empaque == 12
        assert _fila(bd, "SKU-2").embedding is None
        assert "sin GEMINI_API_KEY: no se calculan embeddings" in capsys.readouterr().out

    async def test_sin_embeddings_ni_se_pregunta_por_el_embeder(self, bd, monkeypatch):
        _sembrar(bd)

        def no_debe_llamarse():
            raise AssertionError("--sin-embeddings no debe consultar el entorno")

        monkeypatch.setattr(enriquecer, "_embeder_por_entorno", no_debe_llamarse)

        assert await enriquecer._principal(False, False, False) == 0

    async def test_guardar_una_lista_vacia_ni_abre_la_base(self, monkeypatch):
        def no_debe_abrirse(*_a, **_k):
            raise AssertionError("sin cambios no hay por que abrir un motor")

        monkeypatch.setattr("tukit_comun.bd.crear_motor", no_debe_abrirse)
        await _guardar_embeddings([])


# ---------------------------------------------------------------------------
# Imagen desde la ficha y main
# ---------------------------------------------------------------------------


class TestImagenDesdeFicha:
    def test_devuelve_la_portada_de_la_ficha(self, monkeypatch):
        monkeypatch.setattr(
            enriquecer.tiendas, "ficha", lambda _d: _ficha("X", imagen="https://img.example.test/a.jpg")
        )
        assert imagen_desde_ficha("https://exito.example.test/x") == "https://img.example.test/a.jpg"

    def test_si_la_ficha_no_existe_no_hay_imagen(self, monkeypatch):
        """Ponerle a un producto la foto de otro es peor que dejarlo sin foto."""
        monkeypatch.setattr(enriquecer.tiendas, "ficha", lambda _d: None)
        assert imagen_desde_ficha("https://exito.example.test/x") is None


class TestMain:
    """Desde a50c334 `main` tambien pasa `--reextraer`, `--informe` y `--fichas` (enriquecer.py:1563-1585)."""

    @pytest.fixture()
    def principal(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
        llamadas: list[tuple[Any, ...]] = []

        async def falso(
            con_imagenes: bool,
            solo_validar: bool,
            con_embeddings: bool = True,
            reextraer: dict[str, frozenset[str]] | None = None,
            informe: str | None = None,
            con_fichas: bool = False,
        ) -> int:
            llamadas.append((con_imagenes, solo_validar, con_embeddings, reextraer, informe, con_fichas))
            return 7

        monkeypatch.setattr(enriquecer, "_principal", falso)
        return llamadas

    def test_por_omision_no_va_a_la_red_pero_si_calcula_embeddings(self, monkeypatch, principal):
        """Ni portadas ni fichas (las dos van a la red de la tienda) sin pedirlas."""
        monkeypatch.setattr("sys.argv", ["enriquecer"])
        assert enriquecer.main() == 7
        assert principal == [(False, False, True, {}, None, False)]

    def test_cada_bandera_cambia_su_parametro(self, monkeypatch, principal):
        monkeypatch.setattr(
            "sys.argv",
            [
                "enriquecer",
                "--imagenes",
                "--solo-validar",
                "--sin-embeddings",
                "--reextraer",
                "C006:tipo,punta",
                "--reextraer",
                "C006:color",
                "--informe",
                "informe-ficticio.csv",
                "--fichas",
            ],
        )
        enriquecer.main()
        assert principal == [
            (True, True, False, {"C006": frozenset({"tipo", "punta", "color"})}, "informe-ficticio.csv", True)
        ]


# ---------------------------------------------------------------------------
# Extractores que test_enriquecer no alcanza
# ---------------------------------------------------------------------------


class TestEmpaqueBordes:
    def test_un_x0_no_cuenta_empaques(self):
        assert extraer_empaque("Cuaderno Ficticio x0") == Empaque(1, "unidad")

    def test_un_x_seguido_de_una_palabra_que_no_cuenta_ni_mide_sigue_siendo_conteo(self):
        assert extraer_empaque("Pelotas Ficticias x100 Gigante") == Empaque(100, "unidad")

    def test_un_conteo_suelto_sin_x_tambien_es_empaque(self):
        assert extraer_empaque("Block cuadriculado de 50 hojas") == Empaque(50, "hoja")
        assert extraer_empaque("Papel crepe ficticio 20 pliegos") == Empaque(20, "pliego")

    def test_pero_si_el_concepto_dice_que_las_hojas_describen_no_cuentan(self):
        assert extraer_empaque("Block cuadriculado de 50 hojas", ("hojas",)) == Empaque(1, "unidad")

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-13: extraer_empaque devuelve unidades=0 con 'caja de 0' o '0 unidades' "
            "(enriquecer.py:472-474 y :482-484 sin la guarda cantidad<1 de :464-465), que viola "
            "producto_empaque_positivo (modelos/catalogo.py:290)"
        ),
    )
    def test_un_empaque_nunca_es_menor_que_uno(self):
        """`unidades_por_empaque > 0` es CHECK de la tabla y divisor de `unidades_a_comprar`.

        Un cero que sale de un nombre raro tumbaria el UPDATE en lote de `_guardar`: una fila mala
        deja sin enriquecer a todo el catalogo.
        """
        for nombre in ("Cuaderno Ficticio x 0 unidades", "Caja de 0", "Lapiz Ficticio 0 unidades"):
            assert extraer_empaque(nombre).unidades >= 1, nombre


class TestAtributosBordes:
    def test_unidades_solo_si_el_empaque_es_mayor_que_uno(self):
        assert extraer_atributos("Tijeras Ficticias x 12 unidades", ("unidades",)) == {"unidades": 12}
        assert extraer_atributos("Tijeras Ficticias", ("unidades",)) == {}

    def test_piezas_acepta_fichas_como_sinonimo(self):
        assert extraer_atributos("Rompecabezas Ficticio 120 piezas", ("piezas",)) == {"piezas": 120}
        assert extraer_atributos("Rompecabezas Ficticio 120 fichas", ("piezas",)) == {"piezas": 120}

    @pytest.mark.parametrize(
        ("nombre", "esperado"),
        [
            ("Cinta Ficticia 10 cm", "10 cm"),
            ("Cinta Ficticia 3 centimetros", "3 cm"),
            ("Cuerda Ficticia 2 metros", "2 m"),
            ("Cinta Ficticia 3 m", "3 m"),
            ("Cinta Ficticia 2.5 milimetros", "2.5 mm"),
            ("Cinta Ficticia 2.0 mm", "2 mm"),
        ],
    )
    def test_la_longitud_se_normaliza_a_mm_cm_o_m(self, nombre, esperado):
        assert extraer_atributos(nombre, ("longitud",)) == {"longitud": esperado}

    def test_el_calibre_se_lee_como_una_medida(self):
        assert extraer_atributos("Alambre Ficticio 2.5 milimetros", ("calibre",)) == {"calibre": "2.5 mm"}

    def test_si_el_nombre_no_trae_la_medida_la_clave_no_aparece(self):
        """Nunca `desconocido`: un atributo inventado es peor que uno ausente."""
        assert extraer_atributos("Cinta Ficticia", ("longitud", "piezas", "unidades")) == {}

    @pytest.mark.parametrize(
        ("palabra", "corta"),
        [
            ("milimetros", "mm"),
            ("mm", "mm"),
            ("centimetros", "cm"),
            ("cm", "cm"),
            ("metros", "m"),
            ("m", "m"),
        ],
    )
    def test_unidad_corta(self, palabra, corta):
        assert _unidad_corta(palabra) == corta
