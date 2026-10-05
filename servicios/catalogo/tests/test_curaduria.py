"""Pruebas de la curaduria que viaja por git.

Lo que puede salir mal aqui no se ve en el momento, se ve en la maquina de
otro: una lista que llega sin su concepto, una importacion que duplica la
version en cada `git pull`, o una exportacion que ensucia `conceptos.csv` con
cambios que nadie hizo y entierra en el diff los que si.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from conftest import crear_concepto
from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.orm import Session
from tukit_catalogo.curaduria import (
    ITEM,
    LISTA,
    VERSION,
    agrupar,
    filas_de_listas,
    fusionar_conceptos,
    importar_listas,
)
from tukit_catalogo.modelos import Base

COLEGIO = uuid.UUID("00000000-0000-0000-0000-00000000c01e")
REVISADA = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def base_nueva() -> Session:
    motor = create_engine("sqlite://")

    @event.listens_for(motor, "connect")
    def _activar_fk(conexion, _registro):  # noqa: ANN001
        conexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(motor)
    return Session(motor)


def sembrar_lista(sesion: Session, concepto_id: uuid.UUID | None, *, revisada: bool = True) -> uuid.UUID:
    lista_id, version_id = uuid.uuid4(), uuid.uuid4()
    sesion.execute(
        LISTA.insert().values(id=lista_id, colegio_id=COLEGIO, grado="Cuarto", anio_lectivo=2026, activa=True)
    )
    sesion.execute(
        VERSION.insert().values(
            id=version_id,
            lista_id=lista_id,
            numero=1,
            vigente=True,
            revisada_en=REVISADA if revisada else None,
        )
    )
    sesion.execute(
        ITEM.insert(),
        [
            {
                "id": uuid.uuid4(),
                "version_id": version_id,
                "orden": 1,
                "texto_original": "Cuaderno cuadriculado 100 hojas",
                "concepto_id": concepto_id,
                "cantidad": 3,
                "atributos": {"rayado": "cuadriculado"},
                "requiere_revision": concepto_id is None,
                "modo_adquisicion": "mercado_abierto",
                "instruccion_colegio": None,
            },
            {
                "id": uuid.uuid4(),
                "version_id": version_id,
                "orden": 2,
                "texto_original": "Plan lector RAZ",
                "concepto_id": None,
                "cantidad": 1,
                "atributos": {},
                "requiere_revision": True,
                "modo_adquisicion": "plataforma",
                "instruccion_colegio": "Se paga en la plataforma del colegio",
            },
        ],
    )
    sesion.flush()
    return lista_id


def importar(sesion: Session, filas: list[dict[str, str]]):
    return importar_listas(sesion.connection(), agrupar(filas))


class TestExportar:
    def test_exporta_el_concepto_por_codigo(self, sesion: Session):
        concepto = crear_concepto(sesion, "C001")
        sembrar_lista(sesion, concepto.id)

        filas = filas_de_listas(sesion.connection())

        assert [f["concepto"] for f in filas] == ["C001", ""]
        assert filas[0]["atributos"] == '{"rayado": "cuadriculado"}'

    def test_una_version_sin_revisar_no_se_exporta(self, sesion: Session):
        """Lo que no se ha curado no es curaduria: exportarlo mandaria a los
        compañeros una lista a medias como si estuviera resuelta."""
        sembrar_lista(sesion, None, revisada=False)

        assert filas_de_listas(sesion.connection()) == []

    def test_volver_a_subir_la_lista_no_borra_la_curada(self, sesion: Session):
        """Subir otra vez la lista deja vigente una version sin revisar. La
        curada sigue siendo la ultima revisada y tiene que seguir viajando."""
        concepto = crear_concepto(sesion, "C001")
        lista_id = sembrar_lista(sesion, concepto.id)
        sesion.execute(update(VERSION).where(VERSION.c.lista_id == lista_id).values(vigente=False))
        sesion.execute(
            VERSION.insert().values(
                id=uuid.uuid4(), lista_id=lista_id, numero=2, vigente=True, revisada_en=None
            )
        )

        filas = filas_de_listas(sesion.connection())

        assert [f["concepto"] for f in filas] == ["C001", ""]


class TestImportar:
    def test_ida_y_vuelta_reproduce_la_lista(self, sesion: Session):
        concepto = crear_concepto(sesion, "C001")
        sembrar_lista(sesion, concepto.id)
        exportadas = filas_de_listas(sesion.connection())

        with base_nueva() as otra:
            crear_concepto(otra, "C001")
            resultado = importar(otra, exportadas)

            assert len(resultado.nuevas) == 1
            assert filas_de_listas(otra.connection()) == exportadas

    def test_importar_dos_veces_no_crea_otra_version(self, sesion: Session):
        """Cada `git pull` corre la importacion. Si no fuera idempotente, cada
        uno agregaria una version identica y el historial dejaria de decir
        cuando cambio la lista de verdad."""
        concepto = crear_concepto(sesion, "C001")
        sembrar_lista(sesion, concepto.id)
        exportadas = filas_de_listas(sesion.connection())

        with base_nueva() as otra:
            crear_concepto(otra, "C001")
            importar(otra, exportadas)
            segunda = importar(otra, exportadas)

            assert len(segunda.al_dia) == 1
            assert otra.execute(select(func.count()).select_from(VERSION)).scalar_one() == 1

    def test_reemplaza_un_borrador_sin_revisar_y_lo_conserva(self, sesion: Session):
        concepto = crear_concepto(sesion, "C001")
        sembrar_lista(sesion, concepto.id)
        exportadas = filas_de_listas(sesion.connection())

        with base_nueva() as otra:
            crear_concepto(otra, "C001")
            sembrar_lista(otra, None, revisada=False)
            resultado = importar(otra, exportadas)

            versiones = otra.execute(
                select(VERSION.c.numero, VERSION.c.vigente).order_by(VERSION.c.numero)
            ).all()
            assert len(resultado.actualizadas) == 1
            assert [tuple(v) for v in versiones] == [(1, False), (2, True)]
            assert filas_de_listas(otra.connection()) == exportadas

    def test_un_concepto_que_no_existe_no_importa_la_lista(self, sesion: Session):
        """El error barato es negarse y decir cual falta. El caro seria dejar
        el renglon sin concepto: pasaria como no resuelto y volveria a la cola."""
        concepto = crear_concepto(sesion, "C101")
        sembrar_lista(sesion, concepto.id)
        exportadas = filas_de_listas(sesion.connection())

        with base_nueva() as otra:
            resultado = importar(otra, exportadas)

            assert resultado.errores and "C101" in resultado.errores[0]
            assert otra.execute(select(func.count()).select_from(LISTA)).scalar_one() == 0


def fila_concepto(codigo: str, **cambios: str) -> dict[str, str]:
    return {
        "id": str(uuid.uuid4()),
        "codigo": codigo,
        "nombre_canonico": codigo.lower(),
        "sinonimos": "",
        "categoria": "Otros",
        "tipo_item": "util",
        "atributos_discriminantes": "",
        "atributos_descriptivos": "",
        "admite_personaje": "false",
        "frecuencia_demanda": "1",
        "activo": "true",
        **cambios,
    }


class TestFusionarConceptos:
    def test_agrega_el_concepto_creado_en_la_cola(self):
        en_csv = [fila_concepto("C001")]
        nuevo = fila_concepto("C101", nombre_canonico="plan lector")

        fusion, nuevos, cambiados = fusionar_conceptos(en_csv, [*en_csv, nuevo])

        assert (nuevos, cambiados) == (1, 0)
        assert fusion[-1] == nuevo

    def test_actualiza_sinonimos_pero_no_las_columnas_del_csv(self):
        en_csv = [fila_concepto("C001")]
        viva = {
            **en_csv[0],
            "sinonimos": "esfero|boligrafo",
            "admite_personaje": "true",
            "frecuencia_demanda": "9",
        }

        fusion, _, cambiados = fusionar_conceptos(en_csv, [viva])

        assert cambiados == 1
        assert fusion[0]["sinonimos"] == "esfero|boligrafo"
        assert (fusion[0]["admite_personaje"], fusion[0]["frecuencia_demanda"]) == ("false", "1")

    def test_los_conceptos_de_libros_no_se_tocan(self):
        """El cargador los reescribe en cada carga; si el volcado los siguiera,
        cada exportacion marcaria C034 cambiado sin que nadie lo tocara."""
        en_csv = [fila_concepto("C034")]
        viva = {**en_csv[0], "tipo_item": "libro_libre"}

        fusion, nuevos, cambiados = fusionar_conceptos(en_csv, [viva, fila_concepto("dic-ingles")])

        assert (nuevos, cambiados) == (0, 0)
        assert fusion == en_csv
