"""Pruebas de la siembra de colegios y sedes.

Lo que hay que fijar aqui no es que el INSERT corra. Es el identificador.

El colegio vive en esta base y su lista de utiles vive en la de Catalogo, y
entre las dos no hay llave foranea: la referencia es logica y nadie la impone.
Eso deja un modo de falla silencioso y muy caro: si esta siembra derivara el
UUID de otra forma que la del otro cargador, todo pasaria -las pruebas de
arquitectura tambien, porque comprueban que la referencia este declarada, no
que resuelva- y el sistema quedaria con 17 colegios y 175 listas que no
apuntan a ninguno de ellos.

Por eso las pruebas van contra `tukit_comun.derivar`, que es el contrato
compartido, y no contra un UUID copiado a mano.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from tukit_comun import derivar
from tukit_identidad.cargador import (
    SEDE_POR_OMISION,
    Cargador,
    Informe,
    Problema,
    es_nombre_de_relleno,
    id_colegio,
    id_sede,
)
from tukit_identidad.modelos import Base

RAIZ = Path(__file__).resolve().parents[3]
DATOS = RAIZ / "datos" / "listas"


def escribir_colegios(directorio: Path, filas: list[tuple[str, str, str]]) -> Path:
    contenido = "codigo,nombre,sede_nombre\n" + "".join(f"{c},{n},{s}\n" for c, n, s in filas)
    (directorio / "colegios.csv").write_text(contenido, encoding="utf-8")
    return directorio


class TestIdentificadores:
    """La mitad de Identidad de una referencia que cruza dos bases."""

    def test_el_id_del_colegio_sale_del_codigo_y_de_nada_mas(self):
        assert id_colegio("2.4") == derivar("colegio", "2.4")

    def test_dos_colegios_distintos_no_pueden_colisionar(self):
        assert id_colegio("2.4") != id_colegio("2.14")

    def test_el_mismo_codigo_da_el_mismo_uuid_en_cada_corrida(self):
        """Es lo que hace idempotente la siembra: con un UUID aleatorio, la
        segunda corrida duplicaria los 17 colegios en vez de actualizarlos."""
        assert id_colegio("2.4") == id_colegio("2.4")

    def test_la_sede_necesita_el_nombre_ademas_del_codigo(self):
        """Un colegio puede tener varias sedes, y el codigo solo no las
        distinguiria: las dos derivarian el mismo identificador."""
        assert id_sede("2.4", "Sede unica") == derivar("sede", "2.4", "Sede unica")
        assert id_sede("2.4", "Sede norte") != id_sede("2.4", "Sede sur")


class TestArmado:
    def test_arma_un_colegio_con_su_sede(self, tmp_path: Path):
        cargador = Cargador(escribir_colegios(tmp_path, [("2.4", "Colegio San Pedro", "Sede unica")]))
        datos = cargador.armar()

        assert len(datos["colegio"]) == 1
        assert len(datos["sede"]) == 1
        colegio, sede = datos["colegio"][0], datos["sede"][0]
        assert colegio["nombre"] == "Colegio San Pedro"
        assert colegio["activo"] is True
        # La sede cuelga del colegio por una llave foranea de verdad: esta es
        # la unica de las dos referencias que Postgres si puede imponer.
        assert sede["colegio_id"] == colegio["id"] == derivar("colegio", "2.4")
        assert sede["nombre"] == "Sede unica"

    def test_un_codigo_repetido_bloquea_en_vez_de_pisar_al_primero(self, tmp_path: Path):
        """Los dos derivarian el MISMO UUID, asi que el upsert no duplicaria
        nada: el segundo se comeria al primero y el informe diria que sembro
        dos colegios. Un colegio perdido sin un solo mensaje es peor que un
        fallo ruidoso."""
        cargador = Cargador(
            escribir_colegios(
                tmp_path, [("2.4", "Colegio San Pedro", "Sede unica"), ("2.4", "Otro", "Sede unica")]
            )
        )
        datos = cargador.armar()

        assert len(datos["colegio"]) == 1
        assert any(p.bloqueante and "2.4" in p.detalle for p in cargador.problemas)
        assert Informe(problemas=cargador.problemas).bloqueado

    def test_un_colegio_sin_sede_declarada_se_siembra_con_la_unica(self, tmp_path: Path):
        """Sin sede no habria donde matricular a nadie, porque `matricula`
        cuelga de la sede y no del colegio. Se asume una y se dice."""
        cargador = Cargador(escribir_colegios(tmp_path, [("1.1", "Colegio 1.1", "")]))
        datos = cargador.armar()

        assert datos["sede"][0]["nombre"] == SEDE_POR_OMISION
        assert any(not p.bloqueante and "1.1" in p.detalle for p in cargador.problemas)

    def test_sin_fichero_no_inventa_nada_y_bloquea(self, tmp_path: Path):
        cargador = Cargador(tmp_path)
        datos = cargador.armar()

        assert datos == {"colegio": [], "sede": []}
        assert Informe(problemas=cargador.problemas).bloqueado


class TestCarencias:
    """Lo que el informe tiene que decir aunque la siembra salga bien."""

    def test_cuenta_los_colegios_que_el_papa_ve_como_un_codigo(self, tmp_path: Path):
        cargador = Cargador(
            escribir_colegios(
                tmp_path,
                [("1.1", "Colegio 1.1", "Sede unica"), ("2.4", "Colegio San Pedro", "Sede unica")],
            )
        )
        cargador.armar()

        assert cargador.carencias["colegios sin nombre propio"] == (1, 2)

    def test_un_nombre_de_relleno_es_el_codigo_disfrazado(self):
        assert es_nombre_de_relleno("2.5", "Colegio 2.5")
        assert not es_nombre_de_relleno("2.4", "Colegio San Pedro")

    def test_ningun_colegio_del_corpus_trae_nit(self, tmp_path: Path):
        """El corpus esta anonimizado y el NIT identificaria al colegio, que es
        justo lo que la anonimizacion evito. Se reporta vacio en vez de
        inventar uno: la columna es unica y un NIT falso es peor que ninguno."""
        cargador = Cargador(escribir_colegios(tmp_path, [("2.4", "Colegio San Pedro", "Sede unica")]))
        datos = cargador.armar()

        assert datos["colegio"][0]["nit"] is None
        assert cargador.carencias["colegios sin NIT"] == (1, 1)


class TestElProblemaSeLee:
    def test_un_problema_se_entiende_sin_abrir_el_codigo(self):
        texto = str(Problema(bloqueante=True, clase="codigo", detalle="`2.4` repetido"))
        assert "BLOQUEA" in texto
        assert "2.4" in texto


class TestCsvVersionado:
    """El CSV que el monorepo versiona, no uno de mentira.

    Es la prueba de que la siembra no depende de una ruta fuera del
    repositorio: si `datos/listas/colegios.csv` desapareciera, esto falla aqui
    y no en un despliegue con la base vacia.
    """

    def test_el_corpus_aporta_los_17_colegios(self):
        cargador = Cargador(DATOS)
        datos = cargador.armar()

        assert len(datos["colegio"]) == 17
        assert len(datos["sede"]) == 17
        assert not [p for p in cargador.problemas if p.bloqueante]

    def test_los_17_identificadores_son_distintos(self):
        datos = Cargador(DATOS).armar()

        assert len({c["id"] for c in datos["colegio"]}) == 17
        assert len({s["id"] for s in datos["sede"]}) == 17


class TestContraElEsquema:
    """Las filas armadas entran en las tablas de verdad, no en un diccionario.

    Corre contra SQLite en memoria con el mismo `Base.metadata` que Postgres.
    No prueba el upsert -eso es de Postgres- sino que ninguna columna que el
    armado deja fuera sea obligatoria, que es el error que solo aparece al
    escribir de verdad.
    """

    @pytest.mark.asyncio
    async def test_las_filas_armadas_se_insertan_tal_cual(self, db: AsyncSession, tmp_path: Path):
        datos = Cargador(
            escribir_colegios(
                tmp_path,
                [("2.4", "Colegio San Pedro", "Sede unica"), ("2.9", "Colegio Modelia", "Sede unica")],
            )
        ).armar()

        await db.execute(insert(Base.metadata.tables["colegio"]), datos["colegio"])
        await db.execute(insert(Base.metadata.tables["sede"]), datos["sede"])
        await db.flush()

        sedes = await db.execute(
            select(func.count())
            .select_from(Base.metadata.tables["sede"])
            .where(Base.metadata.tables["sede"].c.colegio_id == derivar("colegio", "2.4"))
        )
        assert sedes.scalar_one() == 1
