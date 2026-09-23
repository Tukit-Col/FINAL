"""Pruebas de la siembra de listas oficiales.

Las tres cosas que este cargador puede hacer mal no son fallos ruidosos:

1. Cerrar la puerta. Sembrar las versiones ya revisadas dejaria 175 listas que
   nunca podrian salir a dar de alta lo que el catalogo no tiene, y el
   sintoma seria un catalogo que deja de crecer, meses despues.
2. Forzar renglones a un concepto parecido. Sube la cobertura en el informe y
   le ofrece plastilina a quien pidio pompones.
3. Romper una restriccion a mitad de camino. Un CHECK que salta en la fila
   3.000 deja la siembra a medias y el mensaje habla de un nombre de
   restriccion, no de la fila del CSV.

De ahi la forma de estas pruebas: casi todas son sobre el armado en memoria,
que es donde estan las decisiones, y la ultima mete las filas armadas en el
esquema de verdad -SQLite con el mismo `Base.metadata`- para comprobar que
las restricciones que el modelo declara las cumple el cargador y no la suerte.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tukit_catalogo.cargador_listas import (
    INSTRUCCION_POR_MODO,
    UMBRAL_CONCEPTO,
    Cargador,
    cantidad_valida,
    id_colegio,
    id_item,
    id_sede,
    instruccion_para,
    normalizar_modo,
    normalizar_tipo,
)
from tukit_catalogo.modelos import Base
from tukit_catalogo.modelos.base import MODOS_SURTIBLES, ModoAdquisicion
from tukit_comun import derivar

RAIZ = Path(__file__).resolve().parents[3]
DATOS = RAIZ / "datos" / "listas"

COLUMNAS = (
    "colegio_codigo,grado,orden,texto_original,cantidad,tipo_item,"
    "modo_adquisicion,categoria,instruccion_colegio,url_externa"
)

CONCEPTO_CUADERNO = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
CONCEPTOS = [{"id": CONCEPTO_CUADERNO, "nombre": "Cuaderno cuadriculado", "sinonimos": ["cuaderno"]}]


def escribir_datos(directorio: Path, filas: list[str], colegios: str | None = None) -> Path:
    (directorio / "colegios.csv").write_text(
        colegios or "codigo,nombre,sede_nombre\n2.4,Colegio San Pedro,Sede unica\n", encoding="utf-8"
    )
    (directorio / "items_lista.csv").write_text(
        COLUMNAS + "\n" + "".join(f"{f}\n" for f in filas), encoding="utf-8"
    )
    return directorio


def item(directorio: Path, *, conceptos=CONCEPTOS) -> dict:
    return Cargador(directorio).armar(conceptos)["item_lista_oficial"][0]


class TestModoAdquisicion:
    """`desconocido` son 736 renglones del corpus y no es un valor del enum.

    La restriccion `item_modo_adquisicion_valido` los rechazaria uno a uno.
    """

    def test_desconocido_cae_en_mercado_abierto(self):
        assert normalizar_modo("desconocido") == ModoAdquisicion.MERCADO_ABIERTO.value

    def test_un_modo_vacio_tambien(self):
        assert normalizar_modo("") == ModoAdquisicion.MERCADO_ABIERTO.value
        assert normalizar_modo(None) == ModoAdquisicion.MERCADO_ABIERTO.value

    @pytest.mark.parametrize("modo", [m.value for m in ModoAdquisicion])
    def test_los_modos_de_verdad_se_respetan(self, modo):
        """Lo que el colegio si declaro no se toca. Convertir una edicion
        exclusiva en mercado abierto seria prometer surtir algo que el colegio
        cerro, que es el modo de falla mas caro del negocio."""
        assert normalizar_modo(modo) == modo


class TestInstruccionColegio:
    """`item_no_surtible_explica_como_conseguirlo` no admite un renglon que
    Tukit no surte sin decir como se consigue.

    La regla no es burocracia: una linea que dice "esto no te lo vendemos" y
    no dice donde comprarlo deja al acudiente peor que antes de abrir Tukit.
    """

    @pytest.mark.parametrize("modo", [m.value for m in ModoAdquisicion if m not in MODOS_SURTIBLES])
    def test_todo_modo_no_surtible_recibe_una_instruccion(self, modo):
        texto = instruccion_para(modo, None)
        assert texto and texto.strip()

    @pytest.mark.parametrize("modo", [m.value for m in MODOS_SURTIBLES])
    def test_lo_surtible_no_lleva_instruccion(self, modo):
        """Llenar la columna siempre convertiria el aviso en ruido."""
        assert instruccion_para(modo, None) is None

    def test_lo_que_el_colegio_dijo_manda_sobre_el_texto_generico(self):
        dicho = "Se paga en la plataforma del colegio antes del 30 de enero."
        assert instruccion_para("plataforma", dicho) == dicho

    def test_la_instruccion_habla_del_canal_concreto(self):
        assert "plataforma" in INSTRUCCION_POR_MODO["plataforma"].lower()
        assert "editorial" in INSTRUCCION_POR_MODO["venta_directa_editorial"].lower()

    def test_un_modo_no_surtible_sin_texto_en_el_csv_se_rellena(self, tmp_path: Path):
        """El CSV ya los trae, pero el cargador no puede darlo por hecho: la
        invariante la impone la base, y un CHECK que salta en la fila 3.000
        deja la siembra a medias."""
        fila = item(
            escribir_datos(tmp_path, ["2.4,Cuarto,1,Plan lector RAZ,1,licencia_digital,plataforma,Otros,,"])
        )

        assert fila["modo_adquisicion"] == "plataforma"
        assert fila["instruccion_colegio"]


class TestCantidad:
    """`item_cantidad_positiva` no admite cero."""

    def test_un_cero_del_corpus_se_lee_como_uno(self):
        """Cero no significa que el colegio no lo pida: significa que la
        transcripcion no encontro el numero en el PDF."""
        assert cantidad_valida("0") == 1
        assert cantidad_valida("") == 1
        assert cantidad_valida(None) == 1
        assert cantidad_valida("-3") == 1

    def test_una_cantidad_de_verdad_se_respeta(self):
        assert cantidad_valida("12") == 12
        assert cantidad_valida("3") == 3


class TestTipoItem:
    def test_un_tipo_desconocido_queda_nulo_y_no_en_util(self):
        """Nulo significa "lo que diga el concepto". Caer en `util` haria que
        el renglon afirmara por su cuenta que es papeleria, y el pipeline le
        buscaria papeleria a una biblia."""
        assert normalizar_tipo("chuchuwa") is None
        assert normalizar_tipo("") is None

    def test_los_tipos_del_corpus_pasan(self):
        assert normalizar_tipo("texto") == "texto"
        assert normalizar_tipo("licencia_digital") == "licencia_digital"


class TestOrdenYVersion:
    def test_el_orden_es_consecutivo_dentro_de_cada_lista(self, tmp_path: Path):
        datos = Cargador(
            escribir_datos(
                tmp_path,
                [
                    "2.4,Cuarto,1,Cuaderno cuadriculado,1,util,mercado_abierto,Cuadernos,,",
                    "2.4,Cuarto,2,Borrador de nata,2,util,mercado_abierto,Borradores,,",
                    "2.4,Quinto,1,Cuaderno cuadriculado,1,util,mercado_abierto,Cuadernos,,",
                ],
            )
        ).armar(CONCEPTOS)

        assert len(datos["lista_oficial"]) == 2
        assert [i["orden"] for i in datos["item_lista_oficial"]] == [1, 2, 1]
        # Dos grados son dos listas y dos versiones, no una con cinco
        # renglones: `uq_lista_oficial` va por colegio, sede, grado y anio.
        assert len({i["version_id"] for i in datos["item_lista_oficial"]}) == 2

    def test_un_orden_repetido_en_la_misma_lista_bloquea(self, tmp_path: Path):
        """`uq_item_version_orden` lo impondria la base abortando la
        transaccion entera, sin decir que dos filas del CSV chocaron."""
        cargador = Cargador(
            escribir_datos(
                tmp_path,
                [
                    "2.4,Cuarto,1,Cuaderno,1,util,mercado_abierto,Cuadernos,,",
                    "2.4,Cuarto,1,Borrador,1,util,mercado_abierto,Borradores,,",
                ],
            )
        )
        datos = cargador.armar(CONCEPTOS)

        assert len(datos["item_lista_oficial"]) == 1
        assert any(p.bloqueante for p in cargador.problemas)

    def test_la_version_nace_sin_revisar_y_vigente(self, tmp_path: Path):
        """La decision de fondo del cargador. El modelo documenta que solo una
        version SIN revisar habilita el descubrimiento, y que una vez revisada
        no se vuelve a abrir: sembrarlas cerradas seria sembrarlas muertas."""
        datos = Cargador(
            escribir_datos(tmp_path, ["2.4,Cuarto,1,Cuaderno,1,util,mercado_abierto,Cuadernos,,"])
        ).armar(CONCEPTOS)

        version = datos["version_lista_oficial"][0]
        assert version["revisada_en"] is None
        assert version["vigente"] is True
        assert version["numero"] == 1

    def test_un_colegio_que_no_esta_en_colegios_csv_bloquea(self, tmp_path: Path):
        """Sin el, la lista quedaria con un `sede_id` derivado de un nombre
        que nadie sembro, apuntando a una sede que no existe."""
        cargador = Cargador(
            escribir_datos(tmp_path, ["9.9,Cuarto,1,Cuaderno,1,util,mercado_abierto,Cuadernos,,"])
        )
        datos = cargador.armar(CONCEPTOS)

        assert datos["item_lista_oficial"] == []
        assert any(p.bloqueante and "9.9" in p.detalle for p in cargador.problemas)


class TestResolucionDeConcepto:
    def test_un_renglon_reconocido_cuelga_de_su_concepto(self, tmp_path: Path):
        fila = item(
            escribir_datos(
                tmp_path, ["2.4,Cuarto,1,Cuaderno cuadriculado,1,util,mercado_abierto,Cuadernos,,"]
            )
        )

        assert fila["concepto_id"] == CONCEPTO_CUADERNO
        assert fila["requiere_revision"] is False
        assert fila["confianza_normalizacion"] >= UMBRAL_CONCEPTO

    def test_un_renglon_que_no_reconocemos_va_a_revision_y_no_al_concepto_mas_parecido(self, tmp_path: Path):
        """`item_sin_concepto_va_a_revision` lo exige, y con razon: un renglon
        que nadie resolvio y que ademas nadie tiene que mirar desaparece del
        kit sin que el papa se entere de que le falta algo."""
        fila = item(
            escribir_datos(tmp_path, ["2.4,Cuarto,1,Punzon punta metalica,1,util,mercado_abierto,Otros,,"])
        )

        assert fila["concepto_id"] is None
        assert fila["requiere_revision"] is True
        assert fila["confianza_normalizacion"] < UMBRAL_CONCEPTO

    def test_sin_vocabulario_no_se_resuelve_nada_y_se_dice(self, tmp_path: Path):
        cargador = Cargador(
            escribir_datos(
                tmp_path, ["2.4,Cuarto,1,Cuaderno cuadriculado,1,util,mercado_abierto,Cuadernos,,"]
            )
        )
        cargador.armar([])

        assert cargador.sin_concepto == cargador.total_items == 1
        assert cargador.carencias["renglones sin concepto resuelto"] == (1, 1)


class TestIdentificadores:
    """La otra mitad de la referencia que cruza a Identidad.

    No se compara contra el cargador de Identidad porque un servicio no
    importa codigo de otro: se comparan los dos contra `tukit_comun.derivar`,
    que es el contrato que ambos firman. Si esta prueba y su gemela en
    Identidad pasan, los dos lados llegan al mismo UUID.
    """

    def test_el_colegio_se_deriva_igual_que_en_identidad(self):
        assert id_colegio("2.4") == derivar("colegio", "2.4")
        assert id_sede("2.4", "Sede unica") == derivar("sede", "2.4", "Sede unica")

    def test_la_lista_apunta_al_colegio_derivado(self, tmp_path: Path):
        datos = Cargador(
            escribir_datos(tmp_path, ["2.4,Cuarto,1,Cuaderno,1,util,mercado_abierto,Cuadernos,,"])
        ).armar(CONCEPTOS)

        lista = datos["lista_oficial"][0]
        assert lista["colegio_id"] == derivar("colegio", "2.4")
        assert lista["sede_id"] == derivar("sede", "2.4", "Sede unica")
        assert lista["anio_lectivo"] == 2026

    def test_el_anio_cambia_la_lista_pero_no_el_colegio(self, tmp_path: Path):
        directorio = escribir_datos(tmp_path, ["2.4,Cuarto,1,Cuaderno,1,util,mercado_abierto,Cuadernos,,"])
        de_2026 = Cargador(directorio, 2026).armar(CONCEPTOS)["lista_oficial"][0]
        de_2027 = Cargador(directorio, 2027).armar(CONCEPTOS)["lista_oficial"][0]

        assert de_2026["id"] != de_2027["id"]
        assert de_2026["colegio_id"] == de_2027["colegio_id"]

    def test_dos_renglones_distintos_no_comparten_identificador(self):
        assert id_item("2.4", "Cuarto", 1) != id_item("2.4", "Cuarto", 2)
        assert id_item("2.4", "Cuarto", 1) != id_item("2.4", "Quinto", 1)


class TestCsvVersionado:
    """El CSV que el monorepo versiona, no uno de mentira.

    Es la prueba de que la siembra no depende del corpus, que vive fuera del
    repositorio: si `datos/listas/items_lista.csv` desapareciera, esto falla
    aqui y no en un despliegue con la base vacia.
    """

    def test_el_corpus_entero_se_arma_sin_bloqueos(self):
        cargador = Cargador(DATOS)
        datos = cargador.armar([])

        assert not [p for p in cargador.problemas if p.bloqueante]
        assert len(datos["lista_oficial"]) == len(datos["version_lista_oficial"]) == 175
        assert len(datos["item_lista_oficial"]) == 4719

    def test_ningun_renglon_del_corpus_rompe_la_regla_de_lo_no_surtible(self):
        datos = Cargador(DATOS).armar([])

        sin_explicar = [
            i
            for i in datos["item_lista_oficial"]
            if i["modo_adquisicion"] not in {m.value for m in MODOS_SURTIBLES}
            and not i["instruccion_colegio"]
        ]
        assert sin_explicar == []


class TestContraElEsquema:
    """Las filas armadas entran en las tablas de verdad.

    SQLite con el mismo `Base.metadata` que Postgres, y con las restricciones
    CHECK activas. No prueba el upsert -eso es de Postgres- sino que lo que el
    cargador arma cumple lo que el modelo exige, que es lo que de otro modo
    solo se descubre a mitad de una carga de 4.719 filas.
    """

    def _sembrar(self, sesion: Session, datos: dict) -> None:
        for tabla in ("lista_oficial", "version_lista_oficial", "item_lista_oficial"):
            sesion.execute(insert(Base.metadata.tables[tabla]), datos[tabla])
        sesion.flush()

    def test_las_filas_armadas_se_insertan_tal_cual(self, sesion: Session, tmp_path: Path):
        datos = Cargador(
            escribir_datos(
                tmp_path,
                [
                    "2.4,Cuarto,1,Punzon punta metalica,1,util,mercado_abierto,Otros,,",
                    "2.4,Cuarto,2,Plan lector RAZ,1,licencia_digital,plataforma,Otros,,https://pagoslearning.com/",
                    "2.4,Quinto,1,Texto de ingles,0,texto,edicion_exclusiva,Textos,,",
                ],
            )
        ).armar([])

        self._sembrar(sesion, datos)

        item_tabla = Base.metadata.tables["item_lista_oficial"]
        assert sesion.execute(select(func.count()).select_from(item_tabla)).scalar_one() == 3
        # La cantidad cero del corpus entro como uno: es lo unico que
        # `item_cantidad_positiva` acepta.
        cantidades = sesion.execute(select(item_tabla.c.cantidad)).scalars().all()
        assert min(cantidades) == 1

    def test_un_renglon_no_surtible_sin_instruccion_lo_rechaza_la_base(self, sesion: Session, tmp_path: Path):
        """Control negativo. Sin el, la prueba de arriba pasaria igual si la
        restriccion no existiera, y lo que se estaria comprobando es que
        SQLite deja insertar cualquier cosa.
        """
        datos = Cargador(
            escribir_datos(tmp_path, ["2.4,Cuarto,1,Plan lector RAZ,1,licencia_digital,plataforma,Otros,,"])
        ).armar([])
        datos["item_lista_oficial"][0]["instruccion_colegio"] = None

        with pytest.raises(IntegrityError):
            self._sembrar(sesion, datos)
