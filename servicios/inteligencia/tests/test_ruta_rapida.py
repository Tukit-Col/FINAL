"""La ruta rapida de INTELIGENCIA para listas ya verificadas (P3).

Cuando un trabajo apunta a una lista REVISADA (revisada_en != null), no hay
nada que volver a percibir, normalizar ni resolver: el catalogo ya tiene el
concepto de cada item y los productos candidatos curados. La ruta rapida salta
directo a optimizacion (NSGA-II) leyendo de un endpoint nuevo del catalogo
(`/v1/admin/listas/{id}/resueltos`) en vez de recomputar con `emparejar`.

Lo que estas pruebas defienden:

- La ruta rapida NUNCA llama a `emparejar` (spy con 0 llamadas): esa es la
  diferencia observable con la ruta lenta.
- Aun asi rellena ITEM+CANDIDATO+RESOLUCION+KIT+LINEA, para que el timeline de
  revision y las lecturas de abajo sigan coherentes.
- Las etapas percepcion/normalizacion/resolucion quedan OK con
  fuente='lista_verificada' (satisfechas por la lista, no saltadas).
- Si CUALQUIER hijo apunta a una lista sin revisar, se usa la ruta lenta
  (correccion sobre optimizacion) y `emparejar` SI se llama.

El anclaje de personaje (los 4 conceptos ancla del Fan) vive en
`test_anclas_personaje.py`.
"""

from __future__ import annotations

import uuid
from typing import Any

from _ayudas_inteligencia import (
    COLEGIO,
    CatalogoVerificado,
    candidato_dict,
    catalogo_verificado,
    crear_y_procesar,
    item_resuelto,
)
from conftest import opcion, reconocido, renglon
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoResolucion, EstadoTrabajo


class TestRutaRapidaVerificada:
    async def test_no_llama_emparejar_y_arma_ahorrador_y_premium(self, motor):
        catalogo = catalogo_verificado()
        trabajo_id, estado = await crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert "emparejar" not in catalogo.llamadas
        assert "resueltos" in catalogo.llamadas
        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        assert {k["perfil"] for k in vista["kits"]} == {"Ahorrador", "Premium"}

    async def test_escribe_item_kit_linea_con_referencia_valida(self, motor):
        from sqlalchemy import func, select

        catalogo = catalogo_verificado()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)

        async with motor.engine.begin() as conexion:
            items = list(
                await conexion.execute(
                    select(trabajos.ITEM.c.id).where(trabajos.ITEM.c.trabajo_id == trabajo_id)
                )
            )
            item_ids = {f.id for f in items}
            kits = await conexion.scalar(
                select(func.count()).select_from(trabajos.KIT).where(trabajos.KIT.c.trabajo_id == trabajo_id)
            )
            lineas = list(
                await conexion.execute(
                    select(trabajos.LINEA.c.item_crudo_id)
                    .select_from(
                        trabajos.LINEA.join(trabajos.KIT, trabajos.LINEA.c.kit_id == trabajos.KIT.c.id)
                    )
                    .where(trabajos.KIT.c.trabajo_id == trabajo_id)
                )
            )

        assert len(item_ids) == 4
        assert kits == 2
        assert lineas, "el kit debe tener lineas"
        for fila in lineas:
            assert fila.item_crudo_id in item_ids

    async def test_rellena_candidato_y_resolucion_resuelto_auto(self, motor):
        from sqlalchemy import func, select

        catalogo = catalogo_verificado()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)

        async with motor.engine.begin() as conexion:
            candidatos = await conexion.scalar(select(func.count()).select_from(trabajos.CANDIDATO))
            resoluciones = list(
                await conexion.execute(
                    select(trabajos.RESOLUCION)
                    .select_from(
                        trabajos.RESOLUCION.join(
                            trabajos.ITEM, trabajos.ITEM.c.id == trabajos.RESOLUCION.c.item_crudo_id
                        )
                    )
                    .where(trabajos.ITEM.c.trabajo_id == trabajo_id)
                )
            )

        # 2 candidatos cuaderno + 2 cartuchera + 1 colores.
        assert candidatos == 5
        surtibles = [r for r in resoluciones if r.concepto_codigo is not None]
        assert surtibles, "debe haber resoluciones con concepto"
        assert all(r.estado == EstadoResolucion.RESUELTO_AUTO.value for r in surtibles)
        assert {r.concepto_codigo for r in surtibles} == {"C001", "C009", "C004"}

    async def test_un_concepto_sin_productos_no_tumba_el_trabajo(self, motor):
        """Lo que paso con la lista de Jardin de CACS: "muda de ropa" (concepto
        no_comprar, sin productos) y un util de un concepto recien creado sin
        productos se resolvian RESUELTO_AUTO sin candidato, el CHECK lo rechazaba
        y el acudiente veia "Algo se rompio" en vez de su kit."""
        from sqlalchemy import select

        catalogo = catalogo_verificado()
        catalogo.items_resueltos += [
            item_resuelto(5, "Muda de ropa marcada", "C067", [], tipo_item="no_comprar"),
            item_resuelto(6, "1 pliego de papel bond", "C129", []),
        ]
        trabajo_id, estado = await crear_y_procesar(motor, catalogo)

        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        async with motor.engine.begin() as conexion:
            por_concepto = {
                r.concepto_codigo: r.estado
                for r in await conexion.execute(
                    select(trabajos.RESOLUCION.c.concepto_codigo, trabajos.RESOLUCION.c.estado)
                    .select_from(
                        trabajos.RESOLUCION.join(
                            trabajos.ITEM, trabajos.ITEM.c.id == trabajos.RESOLUCION.c.item_crudo_id
                        )
                    )
                    .where(trabajos.ITEM.c.trabajo_id == trabajo_id)
                )
            }
        # La muda no se busca en el catalogo: linea informativa, sin resolucion.
        assert "C067" not in por_concepto
        assert por_concepto["C129"] == EstadoResolucion.HUECO_CATALOGO.value
        lineas = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"][0]["lineas"]
        muda = next(linea for linea in lineas if linea["descripcion"].startswith("Muda"))
        assert muda["informativa"] is True

    async def test_la_resolucion_guarda_lo_exigido_y_explica_el_hueco(self, motor):
        """Un renglon cuyo atributo exigido no cumple ningun producto llega sin
        candidatos: es un hueco que dice que pidio, no un concepto vacio."""
        from sqlalchemy import select

        catalogo = catalogo_verificado()
        catalogo.items_resueltos[0]["atributos_impuestos"] = {"rayado": "cuadriculado"}
        catalogo.items_resueltos += [
            item_resuelto(
                5,
                "cuaderno ferrocarril",
                "C001",
                [],
                atributos_impuestos={"rayado": "ferrocarril"},
            ),
            item_resuelto(
                6,
                "cuaderno rayado o cuadriculado",
                "C001",
                [candidato_dict("TK-C001-ECO", "economico", 4500)],
                atributos_por_revisar=["rayado"],
            ),
        ]
        trabajo_id, estado = await crear_y_procesar(motor, catalogo)

        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        async with motor.engine.begin() as conexion:
            por_texto = {
                r.texto: r
                for r in await conexion.execute(
                    select(
                        trabajos.ITEM.c.texto,
                        trabajos.RESOLUCION.c.estado,
                        trabajos.RESOLUCION.c.atributos_impuestos,
                        trabajos.RESOLUCION.c.motivo,
                    )
                    .select_from(
                        trabajos.RESOLUCION.join(
                            trabajos.ITEM, trabajos.ITEM.c.id == trabajos.RESOLUCION.c.item_crudo_id
                        )
                    )
                    .where(trabajos.ITEM.c.trabajo_id == trabajo_id)
                )
            }
        cuadriculado = por_texto["cuaderno cuadriculado"]
        assert cuadriculado.estado == EstadoResolucion.RESUELTO_AUTO.value
        assert cuadriculado.atributos_impuestos == {"rayado": "cuadriculado"}

        ferrocarril = por_texto["cuaderno ferrocarril"]
        assert ferrocarril.estado == EstadoResolucion.HUECO_CATALOGO.value
        assert ferrocarril.atributos_impuestos == {"rayado": "ferrocarril"}
        assert "rayado=ferrocarril" in ferrocarril.motivo

        assert "revisar: rayado" in por_texto["cuaderno rayado o cuadriculado"].motivo

    async def test_una_herramienta_repetida_se_cobra_una_vez(self, motor):
        catalogo = catalogo_verificado()
        tijeras = [candidato_dict("TK-C013-ECO", "economico", 5800)]
        catalogo.items_resueltos += [
            item_resuelto(5, "Tijeras", "C013", tijeras, uno_por_estudiante=True),
            item_resuelto(6, "tijeras", "C013", tijeras, uno_por_estudiante=True, posible_repetido_de=None),
        ]
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)
        kit = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"][0]
        por_orden = {linea["orden"]: linea for linea in kit["lineas"]}
        assert por_orden[5]["unidades_a_comprar"] == 1
        assert por_orden[6]["unidades_a_comprar"] == 0
        assert "linea 5" in por_orden[6]["mensaje"]

    async def test_la_herramienta_repetida_no_viaja_en_cero_al_checkout(self, motor):
        # La linea repetida queda en el kit con 0 unidades para que el acudiente
        # la encuentre, pero Comercio exige cantidad > 0: si viajaba, el checkout
        # entero respondia 400 y el acudiente no podia pagar.
        catalogo = catalogo_verificado()
        tijeras = [candidato_dict("TK-C013-ECO", "economico", 5800)]
        catalogo.items_resueltos += [
            item_resuelto(5, "Tijeras", "C013", tijeras, uno_por_estudiante=True),
            item_resuelto(6, "tijeras", "C013", tijeras, uno_por_estudiante=True, posible_repetido_de=None),
        ]
        creado = await trabajos.crear(
            motor,
            hijos=[{"referencia": "canonico", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            preferencias={},
            origen=trabajos.ORIGEN_CANONICO,
        )
        await trabajos.procesar(motor, uuid.UUID(creado["trabajo_id"]), catalogo=catalogo)
        aplicado = await trabajos.aplicar_canonico(
            motor,
            colegio_id=COLEGIO,
            grado="Cuarto",
            anio_lectivo=2026,
            perfil="Ahorrador",
            usuario_id=(acudiente := uuid.uuid4()),
            catalogo=catalogo,
        )

        class ComercioFalso:
            orden: dict[str, Any] = {}

            async def crear_orden(self, cuerpo):
                self.orden = cuerpo
                return 201, {"pedido_id": "ped-1", "total": 0}

            async def iniciar_pago(self, pedido_id, cuerpo):
                return 201, {"pago_id": "pago-1", "url_redireccion": "https://pasarela/xy"}

        comercio = ComercioFalso()
        await trabajos.ordenar(
            motor,
            uuid.UUID(aplicado["trabajo_id"]),
            portador=acudiente,
            perfil="Ahorrador",
            entrega={"destinatario": "Ana", "direccion": "Calle 1", "ciudad": "Bogota"},
            correo="ana@example.com",
            comercio=comercio,
            catalogo=catalogo,
        )
        lineas = comercio.orden["lineas"]
        assert all(linea["cantidad"] > 0 for linea in lineas)
        assert [linea["cantidad"] for linea in lineas if linea["sku"] == "TK-C013-ECO"] == [1]

    async def test_etapas_ok_con_fuente_lista_verificada(self, motor):
        catalogo = catalogo_verificado()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        por_nombre = {e["nombre"]: e for e in vista["etapas"]}
        assert por_nombre["percepcion"]["estado"] == "ok"
        assert por_nombre["normalizacion"]["estado"] == "ok"
        assert por_nombre["resolucion"]["estado"] == "ok"
        assert por_nombre["optimizacion"]["estado"] == "ok"
        for nombre in ("percepcion", "normalizacion", "resolucion"):
            assert por_nombre[nombre]["detalle"].get("fuente") == "lista_verificada"

    async def test_linea_informativa_no_surtible_queda_visible(self, motor):
        catalogo = catalogo_verificado()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo)
        kits = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"]
        lineas = kits[0]["lineas"]

        licencia = next(linea for linea in lineas if linea["informativa"])
        assert licencia["subtotal_linea"] is None
        assert licencia["instruccion_colegio"] == "Se adquiere con QUOVIX."


class TestListaSinRevisarUsaRutaLenta:
    async def test_si_no_esta_revisada_se_llama_emparejar(self, motor):
        catalogo = CatalogoVerificado(
            revisada=False,
            renglones=[renglon(1, "2 cuadernos", cantidad=2)],
            respuestas={
                "2 cuadernos": reconocido("2 cuadernos", "C001", [opcion("TK-C001-ECO", "economico", 4500)])
            },
        )
        trabajo_id, estado = await crear_y_procesar(motor, catalogo)

        assert "emparejar" in catalogo.llamadas
        assert "resueltos" not in catalogo.llamadas
        assert estado == EstadoTrabajo.ESPERA_REVISION.value




