from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tukit_identidad.curaduria import COLUMNAS_COLEGIOS, exportar, importar
from tukit_identidad.modelos import Colegio, Sede

COLEGIO = uuid.UUID("00000000-0000-0000-0000-00000000c01e")


async def sembrar(db: AsyncSession) -> None:
    db.add(
        Colegio(
            id=COLEGIO,
            nombre="Colegio San Pedro",
            dane="111001000001",
            contacto_nombre="Rectora",
            contacto_email="rectoria@sanpedro.edu.co",
        )
    )
    await db.flush()
    db.add(Sede(colegio_id=COLEGIO, nombre="Sede principal"))
    await db.flush()


class TestExportar:
    async def test_el_contacto_no_viaja(self, db: AsyncSession):
        await sembrar(db)

        colegios, sedes, faltantes = await exportar(db, {COLEGIO}, [])

        assert faltantes == []
        assert set(colegios[0]) == set(COLUMNAS_COLEGIOS)
        assert "rectoria@sanpedro.edu.co" not in str(colegios)
        assert sedes[0]["nombre"] == "Sede principal"

    async def test_un_colegio_ausente_conserva_la_fila_previa(self, db: AsyncSession):
        previo = {"id": str(COLEGIO), "nombre": "Colegio San Pedro", "nit": "", "dane": "", "logo_url": "",
                  "sitio_web": "", "direccion": ""}  # fmt: skip

        colegios, _, faltantes = await exportar(db, {COLEGIO}, [previo])

        assert colegios == [previo]
        assert faltantes == []

    async def test_un_colegio_ausente_sin_fila_previa_se_reporta(self, db: AsyncSession):
        _, _, faltantes = await exportar(db, {COLEGIO}, [])

        assert faltantes == [str(COLEGIO)]


class TestImportar:
    async def test_crea_el_colegio_con_su_identificador(self, db: AsyncSession):
        fila = {"id": str(COLEGIO), "nombre": "Colegio San Pedro", "dane": "111001000001"}
        sede = {"id": str(uuid.uuid4()), "colegio_id": str(COLEGIO), "nombre": "Sede principal"}

        creados, _, sedes = await importar(db, [fila], [sede])

        colegio = await db.get(Colegio, COLEGIO)
        assert (creados, sedes) == (1, 1)
        assert colegio is not None and colegio.dane == "111001000001"

    async def test_no_pisa_lo_que_ya_estaba_y_completa_lo_vacio(self, db: AsyncSession):
        await sembrar(db)
        fila = {"id": str(COLEGIO), "nombre": "Otro nombre", "dane": "999", "direccion": "Calle 1"}

        creados, completados, _ = await importar(db, [fila], [])

        colegio = (await db.execute(select(Colegio).where(Colegio.id == COLEGIO))).scalar_one()
        assert (creados, completados) == (0, 1)
        assert (colegio.nombre, colegio.dane, colegio.direccion) == (
            "Colegio San Pedro",
            "111001000001",
            "Calle 1",
        )
