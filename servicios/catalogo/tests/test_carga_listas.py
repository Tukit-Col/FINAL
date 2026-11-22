"""NFR-MAN-01: la siembra de listas oficiales decide que renglon entra, cual va a revision y que no se pisa.

`test_cargador_listas` fija las piezas puras y el armado feliz. Aqui se
caracteriza lo que alli no se mira:

- **Rechazos del armado.** Una fila sin colegio/grado/texto, un orden que no es
  numero, o un `colegios.csv` ausente BLOQUEAN y dicen en que fila estuvo el
  error, en vez de dejar que lo descubra una restriccion de Postgres a mitad de
  una carga de miles de filas.
- **Deduplicacion de trabajo y umbral.** El mismo texto repetido en varios
  grados se clasifica una sola vez, y el corte de 0,5 se aplica en el borde
  exacto: 0,5 resuelve, por debajo va a revision.
- **Escritura.** Se siembra contra un esquema SQLite real: orden de dependencias,
  bloques de INSERT, idempotencia (la segunda corrida actualiza, no duplica) y
  que un cambio en el CSV llega a la base.
- **Orquestacion.** Un bloqueo devuelve 1 sin escribir; `--solo-validar` lee el
  vocabulario pero no escribe; la carga completa deja versiones sin revisar.

Los CSV se escriben en `tmp_path`; la base es un fichero SQLite inyectado en
lugar de Postgres. Los datos son inventados.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from tukit_catalogo import cargador_listas
from tukit_catalogo.cargador_listas import (
    Cargador,
    Informe,
    Problema,
    _en_bloques,
    id_colegio,
    id_item,
    id_lista,
    id_sede,
    id_version,
    leer_conceptos,
)
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    ItemListaOficial,
    ListaOficial,
    VersionListaOficial,
)
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

COLUMNAS = (
    "colegio_codigo,grado,orden,texto_original,cantidad,tipo_item,"
    "modo_adquisicion,categoria,instruccion_colegio,url_externa"
)
COLEGIOS = "codigo,nombre,sede_nombre\n2.4,Colegio Ficticio Uno,Sede Norte Ficticia\n"

U_CUADERNO = uuid.UUID(int=0xA1)
U_LAPIZ = uuid.UUID(int=0xA2)
CONCEPTOS = [
    {"id": U_CUADERNO, "nombre": "Cuaderno cuadriculado", "sinonimos": ["cuaderno"]},
    {"id": U_LAPIZ, "nombre": "Lapiz negro", "sinonimos": []},
]

RENGLON_CUADERNO = "2.4,Cuarto,1,Cuaderno cuadriculado,2,util,mercado_abierto,Cuadernos,,"
RENGLON_RARO = "2.4,Cuarto,2,Punzon punta metalica,1,util,mercado_abierto,Otros,,"


def _datos(directorio: Path, filas: list[str], colegios: str | None = COLEGIOS) -> Path:
    if colegios is not None:
        (directorio / "colegios.csv").write_text(colegios, encoding="utf-8")
    (directorio / "items_lista.csv").write_text(
        COLUMNAS + "\n" + "".join(f"{f}\n" for f in filas), encoding="utf-8"
    )
    return directorio


def _armar(directorio: Path, conceptos=CONCEPTOS) -> tuple[Cargador, dict]:
    cargador = Cargador(directorio)
    return cargador, cargador.armar(conceptos)


# ---------------------------------------------------------------------------
# Armado: lo que se rechaza
# ---------------------------------------------------------------------------


class TestRechazosDelArmado:
    def test_sin_items_lista_csv_no_hay_nada_que_sembrar_y_se_bloquea(self, tmp_path):
        (tmp_path / "colegios.csv").write_text(COLEGIOS, encoding="utf-8")
        cargador, datos = _armar(tmp_path)
        assert datos == {"lista_oficial": [], "version_lista_oficial": [], "item_lista_oficial": []}
        assert [(p.bloqueante, p.clase) for p in cargador.problemas] == [(True, "datos")]
        assert "items_lista.csv" in cargador.problemas[0].detalle

    def test_sin_colegios_csv_se_dice_y_cada_fila_queda_sin_colegio(self, tmp_path):
        """Sin `colegios.csv` no hay `sede_id`: se denuncia el fichero y tambien cada fila afectada."""
        cargador, datos = _armar(_datos(tmp_path, [RENGLON_CUADERNO, RENGLON_RARO], colegios=None))
        assert datos["item_lista_oficial"] == []
        clases = [(p.bloqueante, p.clase) for p in cargador.problemas]
        assert clases == [(True, "datos"), (True, "colegio"), (True, "colegio")]
        assert "colegios.csv" in cargador.problemas[0].detalle

    @pytest.mark.parametrize(
        "fila",
        [
            ",Cuarto,1,Cuaderno,1,util,mercado_abierto,x,,",  # sin colegio
            "2.4,,1,Cuaderno,1,util,mercado_abierto,x,,",  # sin grado
            "2.4,Cuarto,1,   ,1,util,mercado_abierto,x,,",  # texto en blanco
        ],
    )
    def test_una_fila_sin_colegio_grado_o_texto_bloquea_con_su_numero(self, tmp_path, fila):
        cargador, datos = _armar(_datos(tmp_path, [RENGLON_CUADERNO.replace(",1,", ",9,", 1), fila]))
        assert len(datos["item_lista_oficial"]) == 1
        problema = next(p for p in cargador.problemas if p.clase == "fila")
        assert problema.bloqueante
        assert "fila 3" in problema.detalle  # la cabecera es la 1; la segunda de datos es la 3

    @pytest.mark.parametrize("orden", ["", "uno", "1.5x"])
    def test_un_orden_que_no_es_numero_bloquea_y_omite_el_renglon(self, tmp_path, orden):
        cargador, datos = _armar(_datos(tmp_path, [f"2.4,Cuarto,{orden},Cuaderno cuadriculado,1,util,x,c,,"]))
        assert datos["item_lista_oficial"] == []
        problema = next(p for p in cargador.problemas if p.clase == "orden")
        assert problema.bloqueante
        assert "orden no numerico" in problema.detalle

    def test_el_orden_repetido_se_denuncia_en_la_segunda_aparicion_y_esa_no_entra(self, tmp_path):
        """El primero manda: la segunda fila con el mismo (colegio, grado, orden) no sobrescribe."""
        cargador, datos = _armar(
            _datos(
                tmp_path,
                [
                    "2.4,Cuarto,1,Cuaderno cuadriculado,1,util,mercado_abierto,c,,",
                    "2.4,Cuarto,1,Lapiz negro,5,util,mercado_abierto,c,,",
                ],
            )
        )
        assert [i["texto_original"] for i in datos["item_lista_oficial"]] == ["Cuaderno cuadriculado"]
        problema = next(p for p in cargador.problemas if p.clase == "orden")
        assert "fila 3" in problema.detalle
        assert "repite el orden 1" in problema.detalle

    def test_el_mismo_orden_en_grados_distintos_no_es_un_choque(self, tmp_path):
        cargador, datos = _armar(
            _datos(
                tmp_path,
                [
                    "2.4,Cuarto,1,Cuaderno cuadriculado,1,util,mercado_abierto,c,,",
                    "2.4,Quinto,1,Cuaderno cuadriculado,1,util,mercado_abierto,c,,",
                ],
            )
        )
        assert len(datos["item_lista_oficial"]) == 2
        assert not cargador.problemas


# ---------------------------------------------------------------------------
# Armado: estructura y decisiones
# ---------------------------------------------------------------------------


class TestEstructuraDeLaSiembra:
    def test_una_lista_y_una_version_por_colegio_y_grado(self, tmp_path):
        _, datos = _armar(
            _datos(
                tmp_path,
                [
                    "2.4,Cuarto,1,Cuaderno cuadriculado,1,util,mercado_abierto,c,,",
                    "2.4,Cuarto,2,Lapiz negro,1,util,mercado_abierto,c,,",
                    "2.4,Quinto,1,Lapiz negro,1,util,mercado_abierto,c,,",
                ],
            )
        )
        assert sorted(x["grado"] for x in datos["lista_oficial"]) == ["Cuarto", "Quinto"]
        assert len(datos["version_lista_oficial"]) == 2
        lista = next(x for x in datos["lista_oficial"] if x["grado"] == "Cuarto")
        assert lista["id"] == id_lista("2.4", "Cuarto", 2026)
        assert lista["colegio_id"] == id_colegio("2.4")
        assert lista["sede_id"] == id_sede("2.4", "Sede Norte Ficticia")
        assert lista["anio_lectivo"] == 2026
        assert lista["activa"] is True
        version = next(v for v in datos["version_lista_oficial"] if v["lista_id"] == lista["id"])
        assert version["id"] == id_version("2.4", "Cuarto", 2026)
        # Los dos renglones de Cuarto cuelgan de la version de Cuarto, con id estable.
        cuarto = [i for i in datos["item_lista_oficial"] if i["version_id"] == version["id"]]
        assert sorted(i["id"] for i in cuarto) == sorted(
            [id_item("2.4", "Cuarto", 1), id_item("2.4", "Cuarto", 2)]
        )

    def test_el_anio_lectivo_se_toma_del_parametro(self, tmp_path):
        _datos(tmp_path, [RENGLON_CUADERNO])
        datos = Cargador(tmp_path, anio=2027).armar(CONCEPTOS)
        assert datos["lista_oficial"][0]["anio_lectivo"] == 2027
        assert datos["lista_oficial"][0]["id"] == id_lista("2.4", "Cuarto", 2027)

    def test_sin_nombre_de_sede_se_usa_sede_unica(self, tmp_path):
        colegios = "codigo,nombre,sede_nombre\n2.4,Colegio Ficticio Uno,\n"
        _, datos = _armar(_datos(tmp_path, [RENGLON_CUADERNO], colegios=colegios))
        assert datos["lista_oficial"][0]["sede_id"] == id_sede("2.4", "Sede unica")

    def test_el_renglon_conserva_lo_que_el_csv_dice_y_deja_nulo_lo_que_no_sabe(self, tmp_path):
        fila = "2.4,Cuarto,3,Plan lector Ficticio,0,licencia_digital,plataforma,  Plan lector ,,https://colegio.example.test/plan"
        _, datos = _armar(_datos(tmp_path, [fila]))
        renglon = datos["item_lista_oficial"][0]
        assert renglon["orden"] == 3
        assert renglon["cantidad"] == 1  # el cero del corpus se lee como uno
        assert renglon["unidad"] is None  # nunca se adivina del texto
        assert renglon["tipo_item"] == "licencia_digital"
        assert renglon["modo_adquisicion"] == "plataforma"
        assert renglon["instruccion_colegio"]  # rellenada porque Tukit no lo surte
        assert renglon["url_externa"] == "https://colegio.example.test/plan"
        assert renglon["atributos"] == {"categoria": "Plan lector"}

    def test_sin_categoria_ni_url_quedan_vacios_y_no_como_texto_en_blanco(self, tmp_path):
        _, datos = _armar(
            _datos(tmp_path, ["2.4,Cuarto,1,Cuaderno cuadriculado,1,util,mercado_abierto, ,,  "])
        )
        renglon = datos["item_lista_oficial"][0]
        assert renglon["atributos"] == {}
        assert renglon["url_externa"] is None
        assert renglon["instruccion_colegio"] is None  # lo surtible no lleva instruccion

    def test_el_contenido_crudo_de_la_lista_no_se_persiste(self, tmp_path):
        """`contenido_redactado` solo puede llevar texto que paso la redaccion de nombres de menores."""
        _, datos = _armar(_datos(tmp_path, [RENGLON_CUADERNO]))
        version = datos["version_lista_oficial"][0]
        assert version["contenido_redactado"] is None
        assert version["hash_origen"] is None
        assert version["revisada_en"] is None


class TestResolucionYCarencias:
    def test_el_mismo_texto_se_clasifica_una_sola_vez(self, tmp_path, monkeypatch):
        """'Borrador de Nata' aparece 40 veces en el corpus: clasificar compara contra todos los sinonimos."""
        llamadas: list[str] = []

        def clasificar_falso(texto, conceptos):
            llamadas.append(texto)
            return U_CUADERNO, "cuaderno", 0.9

        monkeypatch.setattr(cargador_listas, "clasificar", clasificar_falso)
        _, datos = _armar(
            _datos(
                tmp_path,
                [
                    "2.4,Cuarto,1,Borrador Ficticio,1,util,mercado_abierto,c,,",
                    "2.4,Cuarto,2,Borrador Ficticio,1,util,mercado_abierto,c,,",
                    "2.4,Quinto,1,Borrador Ficticio,1,util,mercado_abierto,c,,",
                    "2.4,Quinto,2,Otro Texto Ficticio,1,util,mercado_abierto,c,,",
                ],
            )
        )
        assert llamadas == ["Borrador Ficticio", "Otro Texto Ficticio"]
        assert len(datos["item_lista_oficial"]) == 4

    @pytest.mark.parametrize(
        ("parecido", "resuelto"),
        [(0.5, True), (0.9, True), (0.4999, False), (0.0, False)],
    )
    def test_el_corte_de_revision_es_cerrado_por_arriba(self, tmp_path, monkeypatch, parecido, resuelto):
        monkeypatch.setattr(
            cargador_listas, "clasificar", lambda texto, conceptos: (U_CUADERNO, "c", parecido)
        )
        _, datos = _armar(_datos(tmp_path, [RENGLON_CUADERNO]))
        renglon = datos["item_lista_oficial"][0]
        assert (renglon["concepto_id"] == U_CUADERNO) is resuelto
        assert renglon["requiere_revision"] is (not resuelto)
        assert renglon["confianza_normalizacion"] == round(parecido, 3)

    def test_la_confianza_se_redondea_a_tres_decimales(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            cargador_listas, "clasificar", lambda texto, conceptos: (U_CUADERNO, "c", 0.87654321)
        )
        _, datos = _armar(_datos(tmp_path, [RENGLON_CUADERNO]))
        assert datos["item_lista_oficial"][0]["confianza_normalizacion"] == 0.877

    def test_las_carencias_cuentan_lo_que_falta_y_el_vocabulario_que_nadie_pide(self, tmp_path):
        cargador, _ = _armar(
            _datos(
                tmp_path,
                [
                    RENGLON_CUADERNO,
                    RENGLON_RARO,
                    "2.4,Cuarto,3,Plan lector Ficticio,1,licencia_digital,plataforma,Otros,,",
                ],
            )
        )
        assert cargador.total_items == 3
        assert cargador.sin_concepto == 2
        assert cargador.carencias == {
            "renglones sin concepto resuelto": (2, 3),
            "renglones que Tukit no puede surtir": (1, 3),
            "renglones sin unidad declarada": (3, 3),
            "conceptos del catalogo que nadie pide": (1, 2),  # nadie pidio el lapiz
        }

    def test_sin_vocabulario_no_se_mide_cuanto_vocabulario_nadie_pide(self, tmp_path):
        cargador, _ = _armar(_datos(tmp_path, [RENGLON_CUADERNO]), conceptos=[])
        assert "conceptos del catalogo que nadie pide" not in cargador.carencias

    def test_si_no_entro_ningun_renglon_no_hay_carencias_que_medir(self, tmp_path):
        cargador, _ = _armar(_datos(tmp_path, ["9.9,Cuarto,1,Cuaderno,1,util,mercado_abierto,c,,"]))
        assert cargador.carencias == {}
        assert cargador.total_items == 0


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------


class TestInforme:
    def test_el_problema_dice_si_bloquea(self):
        assert str(Problema(True, "orden", "x")) == "[BLOQUEA] orden: x"
        assert str(Problema(False, "nota", "y")) == "[carencia] nota: y"

    def test_imprime_lo_sembrado_las_carencias_y_recorta_las_listas_largas(self, capsys):
        informe = Informe(
            escritos={"lista_oficial": 2, "item_lista_oficial": 40},
            problemas=[Problema(True, "fila", f"fila {i}") for i in range(22)]
            + [Problema(False, "nota", f"nota {i}") for i in range(16)],
            carencias={"renglones sin concepto resuelto": (1, 4), "otra": (0, 0)},
        )
        assert informe.bloqueado
        informe.imprimir()
        salida = capsys.readouterr().out
        assert "item_lista_oficial" in salida
        assert "22 problema(s) que BLOQUEAN" in salida
        assert "fila 19" in salida
        assert "fila 20" not in salida
        assert "... y 2 mas" in salida
        assert "16 carencia(s) con nombre propio" in salida
        assert "nota 14" in salida
        assert "nota 15" not in salida
        assert "(25%)" in salida
        assert "(0%)" in salida  # total cero: sin division por cero

    def test_sin_bloqueos_no_se_imprime_esa_seccion(self, capsys):
        informe = Informe(escritos={"lista_oficial": 1})
        assert not informe.bloqueado
        informe.imprimir()
        assert "BLOQUEAN" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Escritura contra SQLite
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


def _vocabulario(bd: Session) -> None:
    bd.add_all(
        [
            Concepto(
                id=U_CUADERNO,
                codigo="C001",
                nombre_canonico="Cuaderno cuadriculado",
                categoria="escritura",
                sinonimos=["cuaderno"],
            ),
            Concepto(
                id=U_LAPIZ,
                codigo="C002",
                nombre_canonico="Lapiz negro",
                categoria="escritura",
                sinonimos=None,
            ),
            Concepto(
                id=uuid.UUID(int=0xA3),
                codigo="C003",
                nombre_canonico="Concepto retirado",
                categoria="otro",
                activo=False,
            ),
        ]
    )
    bd.commit()


def _contar(bd: Session) -> dict[str, int]:
    bd.rollback()
    return {
        modelo.__tablename__: bd.scalar(select(func.count()).select_from(modelo))
        for modelo in (ListaOficial, VersionListaOficial, ItemListaOficial)
    }


class TestBloques:
    def test_parte_en_bloques_del_tamano_pedido_sin_perder_filas(self):
        filas = [{"n": i} for i in range(5)]
        assert [len(b) for b in _en_bloques(filas, 2)] == [2, 2, 1]
        assert [f["n"] for b in _en_bloques(filas, 2) for f in b] == [0, 1, 2, 3, 4]
        assert list(_en_bloques([], 400)) == []

    def test_el_limite_de_parametros_de_postgres_obliga_a_partir(self):
        """16 bits de parametros: 400 filas x 14 columnas = 5.600, con holgura sobre el limite de 32.767."""
        assert cargador_listas.FILAS_POR_BLOQUE * 14 < 32767


class TestEscribir:
    async def test_escribe_las_tres_capas_y_cuenta_lo_escrito(self, tmp_path, bd):
        _vocabulario(bd)
        cargador, datos = _armar(_datos(tmp_path, [RENGLON_CUADERNO, RENGLON_RARO]))
        escritos = await cargador.escribir(datos)
        assert escritos == {"lista_oficial": 1, "version_lista_oficial": 1, "item_lista_oficial": 2}
        assert _contar(bd) == {"lista_oficial": 1, "version_lista_oficial": 1, "item_lista_oficial": 2}
        version = bd.scalar(select(VersionListaOficial))
        assert version.revisada_en is None  # nacen abiertas: es lo que habilita el descubrimiento
        assert version.vigente is True
        cuaderno = bd.scalar(select(ItemListaOficial).where(ItemListaOficial.orden == 1))
        assert cuaderno.concepto_id == U_CUADERNO
        assert cuaderno.cantidad == 2
        raro = bd.scalar(select(ItemListaOficial).where(ItemListaOficial.orden == 2))
        assert raro.concepto_id is None
        assert raro.requiere_revision is True

    async def test_sin_filas_cada_tabla_cuenta_cero(self, tmp_path, bd):
        escritos = await Cargador(tmp_path).escribir({})
        assert escritos == {"lista_oficial": 0, "version_lista_oficial": 0, "item_lista_oficial": 0}

    async def test_escribir_en_varios_bloques_deja_todas_las_filas(self, tmp_path, bd, monkeypatch):
        monkeypatch.setattr(cargador_listas, "FILAS_POR_BLOQUE", 2)
        filas = [f"2.4,Cuarto,{i},Cuaderno cuadriculado,1,util,mercado_abierto,c,," for i in range(1, 6)]
        _vocabulario(bd)
        cargador, datos = _armar(_datos(tmp_path, filas))
        escritos = await cargador.escribir(datos)
        assert escritos["item_lista_oficial"] == 5
        assert _contar(bd)["item_lista_oficial"] == 5

    async def test_sembrar_dos_veces_no_duplica_y_actualiza_lo_que_cambio(self, tmp_path, bd):
        _vocabulario(bd)
        carpeta = _datos(tmp_path, [RENGLON_CUADERNO, RENGLON_RARO])
        primero, datos = _armar(carpeta)
        await primero.escribir(datos)
        ids = set(bd.scalars(select(ItemListaOficial.id)))

        _datos(
            tmp_path,
            [
                "2.4,Cuarto,1,Cuaderno cuadriculado,7,util,mercado_abierto,Cuadernos,,",
                RENGLON_RARO,
            ],
        )
        segundo, datos2 = _armar(carpeta)
        await segundo.escribir(datos2)

        assert _contar(bd) == {"lista_oficial": 1, "version_lista_oficial": 1, "item_lista_oficial": 2}
        assert set(bd.scalars(select(ItemListaOficial.id))) == ids
        bd.rollback()
        cuaderno = bd.scalar(select(ItemListaOficial).where(ItemListaOficial.orden == 1))
        assert cuaderno.cantidad == 7

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-10: volver a sembrar reabre (revisada_en=NULL) una version que el administrador "
            "ya cerro, contra la regla 'una vez revisada no se vuelve a abrir'"
        ),
    )
    async def test_volver_a_sembrar_no_reabre_una_version_ya_revisada(self, tmp_path, bd):
        """El modelo dice que una version revisada no se vuelve a abrir (modelos/listas.py).

        `descubrir --cerrar` la marca; si la siguiente corrida del cargador la
        devuelve a 'sin revisar', cada corrida volveria a consultar tiendas por
        listas ya resueltas. El upsert actualiza todas las columnas del primer
        bloque, y `revisada_en: None` esta entre ellas.
        """
        _vocabulario(bd)
        carpeta = _datos(tmp_path, [RENGLON_CUADERNO])
        primero, datos = _armar(carpeta)
        await primero.escribir(datos)
        revisada = datetime(2026, 9, 1, tzinfo=UTC)
        bd.execute(update(VersionListaOficial).values(revisada_en=revisada))
        bd.commit()

        segundo, datos2 = _armar(carpeta)
        await segundo.escribir(datos2)

        bd.rollback()
        assert bd.scalar(select(VersionListaOficial.revisada_en)) is not None


class TestLeerConceptos:
    async def test_devuelve_solo_los_activos_con_la_forma_que_usa_el_clasificador(self, bd):
        _vocabulario(bd)
        conceptos = await leer_conceptos()
        por_nombre = {c["nombre"]: c for c in conceptos}
        assert set(por_nombre) == {"Cuaderno cuadriculado", "Lapiz negro"}  # el retirado no entra
        assert por_nombre["Cuaderno cuadriculado"] == {
            "id": U_CUADERNO,
            "nombre": "Cuaderno cuadriculado",
            "sinonimos": ["cuaderno"],
        }
        assert por_nombre["Lapiz negro"]["sinonimos"] == []  # None -> lista vacia

    async def test_una_base_sin_conceptos_da_una_lista_vacia(self, bd):
        assert await leer_conceptos() == []


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------


class TestPrincipal:
    async def test_un_bloqueo_devuelve_1_y_no_escribe_nada(self, tmp_path, bd, capsys):
        _vocabulario(bd)
        carpeta = _datos(tmp_path, [RENGLON_CUADERNO, "9.9,Cuarto,1,Cuaderno,1,util,mercado_abierto,c,,"])

        assert await cargador_listas._principal(carpeta, 2026, solo_validar=False) == 1

        salida = capsys.readouterr().out
        assert "No se escribio nada" in salida
        assert "[BLOQUEA] colegio" in salida
        assert set(_contar(bd).values()) == {0}

    async def test_solo_validar_lee_el_vocabulario_pero_no_escribe(self, tmp_path, bd, capsys):
        _vocabulario(bd)
        carpeta = _datos(tmp_path, [RENGLON_CUADERNO, RENGLON_RARO])

        assert await cargador_listas._principal(carpeta, 2026, solo_validar=True) == 0

        salida = capsys.readouterr().out
        assert "Vocabulario activo del catalogo: 2 conceptos" in salida
        assert "Renglones sin concepto resuelto: 1/2 (50.0%)" in salida
        assert "(--solo-validar: no se escribio nada en la base)" in salida
        assert set(_contar(bd).values()) == {0}

    async def test_la_carga_completa_siembra_y_avisa_que_quedan_sin_revisar(self, tmp_path, bd, capsys):
        _vocabulario(bd)
        carpeta = _datos(tmp_path, [RENGLON_CUADERNO, RENGLON_RARO])

        assert await cargador_listas._principal(carpeta, 2026, solo_validar=False) == 0

        salida = capsys.readouterr().out
        assert "Las versiones quedan SIN revisar" in salida
        assert "--solo-validar" not in salida
        assert _contar(bd) == {"lista_oficial": 1, "version_lista_oficial": 1, "item_lista_oficial": 2}

    async def test_un_items_lista_vacio_bloquea_en_vez_de_sembrar_cero_renglones(self, tmp_path, bd, capsys):
        """Una siembra que "termina bien" con 0 renglones esconderia un CSV truncado."""
        carpeta = _datos(tmp_path, [])

        assert await cargador_listas._principal(carpeta, 2026, solo_validar=False) == 1

        salida = capsys.readouterr().out
        assert "No se escribio nada" in salida
        assert "items_lista.csv" in salida
        assert set(_contar(bd).values()) == {0}


class TestMain:
    def test_un_directorio_que_no_existe_sale_con_2(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["cargador_listas", "--datos", str(tmp_path / "no_existe")])
        assert cargador_listas.main() == 2
        assert "No existe el directorio de datos" in capsys.readouterr().out

    def test_el_anio_y_el_modo_llegan_a_la_orquestacion(self, tmp_path, bd, monkeypatch, capsys):
        _vocabulario(bd)
        carpeta = _datos(tmp_path, [RENGLON_CUADERNO])
        monkeypatch.setattr(
            "sys.argv", ["cargador_listas", "--datos", str(carpeta), "--anio", "2031", "--solo-validar"]
        )
        assert cargador_listas.main() == 0
        assert "--solo-validar" in capsys.readouterr().out
        assert set(_contar(bd).values()) == {0}

    def test_main_siembra_con_el_anio_pedido(self, tmp_path, bd, monkeypatch):
        _vocabulario(bd)
        carpeta = _datos(tmp_path, [RENGLON_CUADERNO])
        monkeypatch.setattr("sys.argv", ["cargador_listas", "--datos", str(carpeta), "--anio", "2031"])
        assert cargador_listas.main() == 0
        bd.rollback()
        assert bd.scalar(select(ListaOficial.anio_lectivo)) == 2031
