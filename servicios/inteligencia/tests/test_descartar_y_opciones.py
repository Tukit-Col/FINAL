from __future__ import annotations

import uuid

import pytest
from _ayudas_inteligencia import COLEGIO, catalogo_simple, linea_del_kit, sembrar_canonico, total_del_kit
from conftest import CatalogoFalso, opcion, reconocido
from tukit_inteligencia import trabajos


def _catalogo_con_cuatro_cuadernos() -> CatalogoFalso:
    catalogo = catalogo_simple()
    catalogo.respuestas["2 cuadernos cuadriculados"] = reconocido(
        "2 cuadernos cuadriculados",
        "C001",
        [
            opcion("TK-C001-ECO", "economico", 4500),
            opcion("TK-C001-CON", "confiable", 7000),
            opcion("TK-C001-PRE", "premium", 12000),
            opcion("TK-C001-LUJ", "premium", 15000, marca="Norma"),
        ],
    )
    return catalogo


async def _publicado(motor, usuario_id=None) -> uuid.UUID:
    await sembrar_canonico(motor, _catalogo_con_cuatro_cuadernos())
    resultado = await trabajos.aplicar_canonico(
        motor,
        colegio_id=COLEGIO,
        grado="Cuarto",
        anio_lectivo=2026,
        perfil="Ahorrador",
        usuario_id=usuario_id,
        catalogo=_catalogo_con_cuatro_cuadernos(),
    )
    return uuid.UUID(resultado["trabajo_id"])


class ComercioFalso:
    def __init__(self) -> None:
        self.orden = None

    async def crear_orden(self, cuerpo):
        self.orden = cuerpo
        total = sum(ln["precio_unitario"] * ln["cantidad"] for ln in cuerpo["lineas"])
        return 201, {"pedido_id": "ped-1", "total": total}

    async def iniciar_pago(self, pedido_id, cuerpo):
        return 201, {"pago_id": "pago-1", "url_redireccion": "https://pasarela/xy"}


ENTREGA = {"destinatario": "Ana", "direccion": "Calle 1", "ciudad": "Bogota"}


async def test_descartar_una_linea_baja_el_total_y_se_puede_deshacer(motor):
    parent_id = await _publicado(motor)
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    cuaderno = linea_del_kit(vista, "Ahorrador", "2 cuadernos")
    total_antes = total_del_kit(vista, "Ahorrador")
    subtotal = cuaderno["subtotal_linea"]
    assert subtotal and subtotal > 0
    item = uuid.UUID(cuaderno["item_id"])

    await trabajos.descartar_linea_del_acudiente(
        motor, parent_id, "Ahorrador", item, descartar=True, usuario_id=None, catalogo=catalogo
    )
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    cuaderno = linea_del_kit(vista, "Ahorrador", "2 cuadernos")
    assert cuaderno["descartado"] is True
    assert cuaderno["subtotal_linea"] is None
    assert cuaderno["subtotal_descartado"] == subtotal
    assert total_del_kit(vista, "Ahorrador") == total_antes - subtotal
    assert "descartado" not in linea_del_kit(vista, "Premium", "2 cuadernos")

    await trabajos.descartar_linea_del_acudiente(
        motor, parent_id, "Ahorrador", item, descartar=False, usuario_id=None, catalogo=catalogo
    )
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    assert not linea_del_kit(vista, "Ahorrador", "2 cuadernos").get("descartado")
    assert total_del_kit(vista, "Ahorrador") == total_antes
    assert vista["cambios"] == {}


async def test_la_orden_no_cobra_lo_descartado_y_suma_lo_demas(motor):
    dueno = uuid.uuid4()
    parent_id = await _publicado(motor, usuario_id=dueno)
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])
    await trabajos.descartar_linea_del_acudiente(
        motor, parent_id, "Ahorrador", item, descartar=True, usuario_id=dueno, catalogo=catalogo
    )

    comercio = ComercioFalso()
    resultado = await trabajos.ordenar(
        motor,
        parent_id,
        portador=dueno,
        perfil="Ahorrador",
        entrega=ENTREGA,
        correo="ana@example.com",
        comercio=comercio,
        catalogo=catalogo,
    )
    skus = {ln["sku"] for ln in comercio.orden["lineas"]}
    assert "TK-C001-ECO" not in skus
    assert "TK-C004-CON" in skus
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    assert resultado["total"] == total_del_kit(vista, "Ahorrador")


async def test_descartar_y_cambiar_en_la_misma_linea_no_cobra_la_linea(motor):
    dueno = uuid.uuid4()
    parent_id = await _publicado(motor, usuario_id=dueno)
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])
    await trabajos.cambiar_producto_del_acudiente(
        motor, parent_id, "Ahorrador", item, "TK-C001-PRE", usuario_id=dueno, catalogo=catalogo
    )
    await trabajos.descartar_linea_del_acudiente(
        motor, parent_id, "Ahorrador", item, descartar=True, usuario_id=dueno, catalogo=catalogo
    )
    comercio = ComercioFalso()
    await trabajos.ordenar(
        motor,
        parent_id,
        portador=dueno,
        perfil="Ahorrador",
        entrega=ENTREGA,
        correo="ana@example.com",
        comercio=comercio,
        catalogo=catalogo,
    )
    assert all(not ln["sku"].startswith("TK-C001") for ln in comercio.orden["lineas"])

    await trabajos.descartar_linea_del_acudiente(
        motor, parent_id, "Ahorrador", item, descartar=False, usuario_id=dueno, catalogo=catalogo
    )
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    assert linea_del_kit(vista, "Ahorrador", "2 cuadernos")["producto_elegido"]["sku"] == "TK-C001-PRE"


async def test_si_se_descartan_todas_las_lineas_no_hay_orden(motor):
    dueno = uuid.uuid4()
    parent_id = await _publicado(motor, usuario_id=dueno)
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    kit = next(k for k in vista["kits"] if k["perfil"] == "Ahorrador")
    for linea in kit["lineas"]:
        if linea.get("producto_elegido") and not linea["informativa"]:
            await trabajos.descartar_linea_del_acudiente(
                motor,
                parent_id,
                "Ahorrador",
                uuid.UUID(linea["item_id"]),
                descartar=True,
                usuario_id=dueno,
                catalogo=catalogo,
            )
    assert total_del_kit(await trabajos.ver(motor, parent_id, catalogo=catalogo), "Ahorrador") == 0

    with pytest.raises(trabajos.CheckoutRechazado) as exc:
        await trabajos.ordenar(
            motor,
            parent_id,
            portador=dueno,
            perfil="Ahorrador",
            entrega=ENTREGA,
            correo="ana@example.com",
            comercio=ComercioFalso(),
            catalogo=catalogo,
        )
    assert exc.value.estado == 409


async def test_nadie_mas_descarta_la_linea_de_otro_acudiente(motor):
    dueno = uuid.uuid4()
    parent_id = await _publicado(motor, usuario_id=dueno)
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])
    with pytest.raises(trabajos.CambioNoPermitido) as error:
        await trabajos.descartar_linea_del_acudiente(
            motor, parent_id, "Ahorrador", item, descartar=True, usuario_id=uuid.uuid4(), catalogo=catalogo
        )
    assert error.value.codigo == "solicitud_ajena"
    assert error.value.estado == 403


async def test_descartar_no_toca_el_canonico_de_los_demas(motor):
    parent_id = await _publicado(motor)
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])
    total_antes = total_del_kit(vista, "Ahorrador")
    await trabajos.descartar_linea_del_acudiente(
        motor, parent_id, "Ahorrador", item, descartar=True, usuario_id=None, catalogo=catalogo
    )
    otro = uuid.UUID(
        (
            await trabajos.aplicar_canonico(
                motor,
                colegio_id=COLEGIO,
                grado="Cuarto",
                anio_lectivo=2026,
                perfil="Ahorrador",
                usuario_id=None,
                catalogo=catalogo,
            )
        )["trabajo_id"]
    )
    assert total_del_kit(await trabajos.ver(motor, otro, catalogo=catalogo), "Ahorrador") == total_antes


async def test_las_opciones_traen_todo_el_concepto_con_la_diferencia(motor):
    parent_id = await _publicado(motor)
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])

    cuerpo = await trabajos.opciones_de_la_linea(motor, parent_id, "Ahorrador", item, catalogo=catalogo)
    opciones = {o["sku"]: o for o in cuerpo["opciones"]}
    assert set(opciones) == {"TK-C001-ECO", "TK-C001-CON", "TK-C001-PRE", "TK-C001-LUJ"}
    assert cuerpo["opciones"][0]["sku"] == "TK-C001-ECO"
    assert opciones["TK-C001-ECO"]["en_kit"] and opciones["TK-C001-ECO"]["diferencia"] == 0
    assert opciones["TK-C001-LUJ"]["diferencia"] == 2 * (15000 - 4500)
    assert opciones["TK-C001-LUJ"]["marca"] == "Norma"
    assert "TK-C004-CON" not in opciones


async def test_se_puede_elegir_un_producto_del_mismo_concepto_fuera_de_las_alternativas(motor):
    parent_id = await _publicado(motor)
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    cuaderno = linea_del_kit(vista, "Ahorrador", "2 cuadernos")
    assert "TK-C001-LUJ" not in {a["sku"] for a in cuaderno["alternativas"]}
    item = uuid.UUID(cuaderno["item_id"])

    await trabajos.cambiar_producto_del_acudiente(
        motor, parent_id, "Ahorrador", item, "TK-C001-LUJ", usuario_id=None, catalogo=catalogo
    )
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    assert linea_del_kit(vista, "Ahorrador", "2 cuadernos")["producto_elegido"]["sku"] == "TK-C001-LUJ"

    with pytest.raises(trabajos.CambioNoPermitido) as error:
        await trabajos.cambiar_producto_del_acudiente(
            motor, parent_id, "Ahorrador", item, "TK-C004-CON", usuario_id=None, catalogo=catalogo
        )
    assert error.value.codigo == "producto_no_permitido"


async def _con_filtros(motor, trabajo_id, preferencias) -> None:
    from sqlalchemy import update
    from tukit_comun.cifrado import cifrador_desde_entorno

    TRABAJO = trabajos.TRABAJO

    async with motor.engine.begin() as conexion:
        await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id)
            .values(preferencias_cifradas=cifrador_desde_entorno().cifrar_json(preferencias))
        )


async def test_el_carrusel_no_ofrece_la_marca_que_el_acudiente_excluyo(motor):
    parent_id = await _publicado(motor)
    await _con_filtros(motor, parent_id, {"marcas_excluidas": ["Norma"]})
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])

    cuerpo = await trabajos.opciones_de_la_linea(motor, parent_id, "Ahorrador", item, catalogo=catalogo)
    assert {o["sku"] for o in cuerpo["opciones"]} == {"TK-C001-ECO", "TK-C001-CON", "TK-C001-PRE"}


async def test_no_se_puede_cambiar_a_la_marca_excluida_aunque_sea_del_concepto(motor):
    parent_id = await _publicado(motor)
    await _con_filtros(motor, parent_id, {"marcas_excluidas": ["Norma"]})
    catalogo = _catalogo_con_cuatro_cuadernos()
    vista = await trabajos.ver(motor, parent_id, catalogo=catalogo)
    item = uuid.UUID(linea_del_kit(vista, "Ahorrador", "2 cuadernos")["item_id"])

    with pytest.raises(trabajos.CambioNoPermitido) as error:
        await trabajos.cambiar_producto_del_acudiente(
            motor, parent_id, "Ahorrador", item, "TK-C001-LUJ", usuario_id=None, catalogo=catalogo
        )
    assert error.value.codigo == "producto_excluido"
