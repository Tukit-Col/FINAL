"""NFR-MAN-01: el SQL de `RepoAdmin` que arma la cola de revision y la de curaduria.

`test_api_admin` ejerce estos metodos de paso, por HTTP y con el filtro por
omision. Aqui se les pide cada filtro por separado contra una conexion SQLite,
porque un filtro que se ignora en silencio no rompe nada a la vista: la consola
de revision muestra TODAS las listas y el equipo cree que "sin revisar" esta
vacio cuando en realidad no se aplico.

Lo que se vigila:

  - la cola trae UNA fila por lista (su ultima version), no una por version;
  - lo sin revisar va primero y cada filtro (revisada, colegio, grado, ano) se
    suma a los demas;
  - la procedencia sale de la tarea de importacion MAS RECIENTE de la version;
  - la cola de propuestas solo trae lo pendiente y el filtro por concepto
    excluye lo rechazado y lo que aun no tiene concepto;
  - lo retirado o apagado no entra a los productos de la ruta rapida ni al
    vocabulario que consume el clasificador.

Datos ficticios. Siembra: 3 listas (una con dos versiones), 3 propuestas
pendientes + 1 rechazada y 3 productos (1 retirado).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    ItemListaOficial,
    ListaOficial,
    ProductoCanonico,
    PropuestaProducto,
    TareaImportacion,
    Tienda,
    VersionListaOficial,
)
from tukit_catalogo.repositorios.admin import RepoAdmin

pytestmark = pytest.mark.nfr("NFR-MAN-01")

COLEGIO = uuid.UUID("88888888-8888-5888-8888-888888888888")
OTRO_COLEGIO = uuid.UUID("99999999-9999-5999-8999-999999999999")
ACUDIENTE = uuid.UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")
CURADOR = uuid.UUID("bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")
AHORA = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _siembra(sesion) -> dict[str, uuid.UUID]:
    """Tres listas (A con dos versiones), cuatro propuestas, tres productos y dos tareas de importacion."""
    cuaderno = Concepto(
        codigo="C001", nombre_canonico="cuaderno", categoria="Cuadernos", sinonimos=["libreta"]
    )
    colores = Concepto(codigo="C002", nombre_canonico="colores", categoria="Arte")
    apagado = Concepto(codigo="C003", nombre_canonico="concepto apagado", categoria="Arte", activo=False)
    otro_prefijo = Concepto(codigo="L001", nombre_canonico="libro de lectura", categoria="Lectura")
    tienda = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    sesion.add_all([cuaderno, colores, apagado, otro_prefijo, tienda])
    sesion.flush()

    # --- productos (uno retirado) ---
    for sku, nombre, activo in (
        ("TK-C001-CON", "Cuaderno Norma", True),
        ("TK-C001-ECO", "Cuaderno retirado", False),
        ("TK-C002-CON", "Colores Faber", True),
    ):
        concepto = colores if sku.startswith("TK-C002") else cuaderno
        sesion.add(
            ProductoCanonico(
                concepto_id=concepto.id,
                sku_interno=sku,
                nombre=nombre,
                nivel="confiable" if sku.endswith("CON") else "economico",
                curado_por=CURADOR,
                activo=activo,
            )
        )

    # --- listas: A (Cuarto 2026, v1 y v2 revisada), B (Quinto 2025), C (otro colegio) ---
    def _lista(colegio, grado, anio):
        lista = ListaOficial(colegio_id=colegio, grado=grado, anio_lectivo=anio)
        sesion.add(lista)
        sesion.flush()
        return lista

    def _version(lista, numero, *, revisada=False, vigente=False):
        version = VersionListaOficial(
            lista_id=lista.id, numero=numero, vigente=vigente, revisada_en=AHORA if revisada else None
        )
        sesion.add(version)
        sesion.flush()
        return version

    def _renglon(version, orden, concepto=None):
        item = ItemListaOficial(
            version_id=version.id,
            orden=orden,
            texto_original=f"renglon {orden}",
            cantidad=1,
            concepto_id=concepto.id if concepto else None,
            requiere_revision=concepto is None,
        )
        sesion.add(item)
        sesion.flush()
        return item

    lista_a = _lista(COLEGIO, "Cuarto", 2026)
    a1 = _version(lista_a, 1)
    _renglon(a1, 1, cuaderno)
    a2 = _version(lista_a, 2, revisada=True, vigente=True)
    resuelto = _renglon(a2, 1, cuaderno)
    sin_concepto = _renglon(a2, 2)

    lista_b = _lista(COLEGIO, "Quinto", 2025)
    b1 = _version(lista_b, 1, vigente=True)

    lista_c = _lista(OTRO_COLEGIO, "Cuarto", 2026)
    c1 = _version(lista_c, 1, vigente=True)

    # --- tareas: B tiene dos y la procedencia sale de la mas reciente ---
    def _tarea(version, origen, creada, **extra):
        sesion.add(
            TareaImportacion(
                version_id=version.id, origen=origen, estado="completada", creada_en=creada, **extra
            )
        )

    _tarea(b1, "onboarding", AHORA - timedelta(days=2))
    _tarea(
        b1, "sugerencia_padre", AHORA - timedelta(days=1), contacto_referencia=ACUDIENTE, documento=b"%PDF-1"
    )
    # Una sugerencia sin version ni documento: aparece en la bandeja de sugerencias.
    sesion.add(
        TareaImportacion(
            origen="sugerencia_padre",
            estado="pendiente",
            colegio_id=COLEGIO,
            grado="Sexto",
            anio_lectivo=2026,
            creada_en=AHORA,
        )
    )
    # Una importacion de onboarding que NO es sugerencia.
    _tarea(c1, "onboarding", AHORA)

    # --- propuestas: tres pendientes en orden y una rechazada ---
    def _propuesta(ref, *, concepto=None, sugerido=None, estado="pendiente", dias=0, version=None, **extra):
        sesion.add(
            PropuestaProducto(
                concepto_id=concepto.id if concepto else None,
                concepto_sugerido=sugerido,
                texto_origen=f"texto {ref}",
                tienda_id=tienda.id,
                referencia_externa=ref,
                nombre=f"Producto {ref}",
                precio_centavos=550000,
                estado=estado,
                propuesta_en=AHORA + timedelta(days=dias),
                version_lista_id=version.id if version else None,
                **extra,
            )
        )

    _propuesta("EX-1", concepto=cuaderno, dias=0, version=a2)
    _propuesta("EX-2", sugerido="pegante", dias=1)
    _propuesta("EX-3", concepto=colores, dias=2)
    _propuesta("EX-4", concepto=cuaderno, estado="rechazada", dias=3, motivo="no aplica")
    sesion.flush()
    return {
        "a1": a1.id,
        "a2": a2.id,
        "b1": b1.id,
        "c1": c1.id,
        "resuelto": resuelto.id,
        "sin_concepto": sin_concepto.id,
        "cuaderno": cuaderno.id,
    }


@pytest.fixture()
async def ambiente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()
    async with engine.connect() as conexion:
        yield RepoAdmin(conexion), ids
    await engine.dispose()


async def _versiones(repo, **filtros):
    base = {"revisada": None, "colegio_id": None, "grado": None, "anio_lectivo": None}
    return await repo.listar_versiones(**{**base, **filtros})


def _clave(fila) -> tuple[str, int, int]:
    """(grado, anio, numero de version): identifica la lista sembrada sin depender de uuids."""
    return (fila.grado, fila.anio_lectivo, fila.numero)


async def test_la_cola_trae_una_fila_por_lista_con_su_ultima_version_y_lo_pendiente_primero(ambiente):
    """La lista A tiene dos versiones y solo sale la 2; lo sin revisar va antes y se ordena por grado."""
    repo, ids = ambiente
    filas = await _versiones(repo)
    assert [_clave(f) for f in filas] == [("Cuarto", 2026, 1), ("Quinto", 2025, 1), ("Cuarto", 2026, 2)]
    revisada = filas[-1]
    assert revisada.version_id == ids["a2"]
    assert revisada.revisada_en is not None
    assert revisada.renglones == 2  # los de la v2, no los de la v1 (que tiene uno)
    assert [f.renglones for f in filas[:2]] == [0, 0]


@pytest.mark.parametrize(
    ("filtro", "esperado"),
    [
        ({"revisada": True}, [("Cuarto", 2026, 2)]),
        ({"revisada": False}, [("Cuarto", 2026, 1), ("Quinto", 2025, 1)]),
        ({"anio_lectivo": 2025}, [("Quinto", 2025, 1)]),
        ({"anio_lectivo": 2026}, [("Cuarto", 2026, 1), ("Cuarto", 2026, 2)]),
        ({"grado": "Quinto"}, [("Quinto", 2025, 1)]),
        ({"grado": "Cuarto", "revisada": False}, [("Cuarto", 2026, 1)]),
        ({"anio_lectivo": 2031}, []),
    ],
)
async def test_cada_filtro_de_la_cola_de_listas_se_aplica(ambiente, filtro, esperado):
    """Revisada (si/no), ano y grado acotan la cola y se pueden combinar."""
    repo, _ = ambiente
    assert [_clave(f) for f in await _versiones(repo, **filtro)] == esperado


async def test_filtrar_por_colegio_deja_solo_las_listas_de_ese_colegio(ambiente):
    """El filtro por colegio separa las listas de un colegio de las de otro (aislamiento de la consola)."""
    repo, _ = ambiente
    filas = await _versiones(repo, colegio_id=OTRO_COLEGIO)
    assert [(f.colegio_id, f.grado) for f in filas] == [(OTRO_COLEGIO, "Cuarto")]
    assert {f.colegio_id for f in await _versiones(repo, colegio_id=COLEGIO)} == {COLEGIO}


async def test_la_procedencia_sale_de_la_tarea_mas_reciente_de_la_version(ambiente):
    """B tiene una importacion de onboarding y, un dia despues, una sugerencia de padre: gana la segunda.

    Importa porque la consola decide con eso si muestra el contacto del
    acudiente (solo su referencia, nunca su correo) y el documento original.
    """
    repo, _ = ambiente
    por_grado = {(f.grado, f.anio_lectivo): f for f in await _versiones(repo)}
    quinto = por_grado[("Quinto", 2025)]
    assert quinto.procedencia == "sugerencia_padre"
    assert quinto.contacto_referencia == ACUDIENTE
    # Una lista sin ninguna tarea de importacion no tiene procedencia (y tampoco contacto).
    cuarto = por_grado[("Cuarto", 2026)]
    assert (cuarto.procedencia, cuarto.contacto_referencia) == (None, None)


async def test_la_cola_de_propuestas_trae_lo_pendiente_en_orden_de_llegada(ambiente):
    """Sin filtro salen EX-1, EX-2 y EX-3 por antiguedad; la rechazada no sale."""
    repo, _ = ambiente
    filas = await repo.cola_propuestas(None)
    assert [f.nombre for f in filas] == ["Producto EX-1", "Producto EX-2", "Producto EX-3"]
    assert [f.concepto_codigo for f in filas] == ["C001", None, "C002"]
    assert filas[1].concepto_sugerido == "pegante"


@pytest.mark.parametrize(
    ("concepto", "esperado"),
    [("C001", ["Producto EX-1"]), ("C002", ["Producto EX-3"]), ("C999", [])],
)
async def test_filtrar_la_cola_por_concepto_excluye_lo_rechazado_y_lo_que_no_tiene_concepto(
    ambiente, concepto, esperado
):
    """`C001` tiene dos propuestas, pero la rechazada (EX-4) no cuenta; la sin concepto tampoco entra."""
    repo, _ = ambiente
    assert [f.nombre for f in await repo.cola_propuestas(concepto)] == esperado


async def test_las_propuestas_de_una_version_son_solo_las_pendientes_de_esa_version(ambiente):
    repo, ids = ambiente
    assert [f.nombre for f in await repo.propuestas_pendientes_de_version(ids["a2"])] == ["Producto EX-1"]
    assert await repo.propuestas_pendientes_de_version(ids["b1"]) == []


async def test_los_codigos_de_concepto_solo_traen_los_del_prefijo_c(ambiente):
    """El generador del siguiente codigo (`C###`) no debe tropezar con codigos de otra familia (`L001`)."""
    repo, _ = ambiente
    assert sorted(await repo.codigos_concepto()) == ["C001", "C002", "C003"]


async def test_el_vocabulario_del_clasificador_solo_tiene_conceptos_activos_con_sinonimos(ambiente):
    """El concepto apagado no se ofrece al clasificador y un concepto sin sinonimos da una lista vacia."""
    repo, _ = ambiente
    vocabulario = {c["nombre"]: c["sinonimos"] for c in await repo.cargar_conceptos()}
    assert vocabulario == {
        "cuaderno": ["libreta"],
        "colores": [],
        "libro de lectura": [],
    }


async def test_la_ruta_rapida_solo_toma_productos_activos_de_los_conceptos_pedidos(ambiente):
    """Pedir C001 trae el producto vigente y no el retirado; una lista vacia de conceptos no trae nada."""
    repo, _ = ambiente
    assert {f.sku_interno for f in await repo.productos_por_conceptos(["C001"])} == {"TK-C001-CON"}
    assert {f.sku_interno for f in await repo.productos_por_conceptos(["C001", "C002"])} == {
        "TK-C001-CON",
        "TK-C002-CON",
    }
    assert await repo.productos_por_conceptos([]) == []


async def test_los_renglones_resueltos_llevan_su_concepto_y_el_sin_concepto_va_con_nulos(ambiente):
    """El renglon que nadie resolvio sale igual (con codigo nulo): el kit tiene que saber que falta."""
    repo, ids = ambiente
    filas = await repo.items_resueltos(ids["a2"])
    assert [(f.orden, f.concepto_codigo) for f in filas] == [(1, "C001"), (2, None)]
    assert filas[0].id == ids["resuelto"]
    assert filas[1].id == ids["sin_concepto"]


async def test_la_bandeja_de_sugerencias_solo_trae_las_de_padres_y_marca_si_hay_documento(ambiente):
    """Las importaciones de onboarding no aparecen; la mas reciente va primero; el flag no entrega el PDF."""
    repo, _ = ambiente
    filas = await repo.listar_sugerencias()
    assert [(f.grado, f.tiene_documento) for f in filas] == [("Sexto", False), (None, True)]
    assert filas[1].contacto_referencia == ACUDIENTE
