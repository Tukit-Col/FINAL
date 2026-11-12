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
- El anclaje de personaje sube los 4 conceptos ancla al tope sin tocar totales.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoResolucion, EstadoTrabajo
from tukit_inteligencia.optimizador import (
    Candidato,
    KitArmado,
    LineaKit,
    anclar_personaje,
)

COLEGIO = "11111111-1111-5111-8111-111111111111"


# --------------------------------------------------------------------------
# Doble del catalogo con el endpoint nuevo /resueltos
# --------------------------------------------------------------------------


def _candidato_dict(sku: str, nivel: str, precio: int | None, **kw: Any) -> dict[str, Any]:
    base = opcion(sku, nivel, precio, **kw)
    base["producto_id"] = kw.get("producto_id") or str(uuid.uuid4())
    return base


def _item_resuelto(
    orden: int,
    texto: str,
    concepto_codigo: str | None,
    candidatos: list[dict[str, Any]],
    **kw: Any,
) -> dict[str, Any]:
    return {
        "item_id": str(uuid.uuid4()),
        "orden": orden,
        "texto_original": texto,
        "cantidad": kw.get("cantidad", 1),
        "tipo_item": kw.get("tipo_item", "util"),
        "modo_adquisicion": kw.get("modo_adquisicion", "mercado_abierto"),
        "concepto_codigo": concepto_codigo,
        "concepto_nombre": kw.get("concepto_nombre", (concepto_codigo or "").lower()),
        "instruccion_colegio": kw.get("instruccion_colegio"),
        "url_externa": kw.get("url_externa"),
        "candidatos": candidatos,
        "atributos_impuestos": kw.get("atributos_impuestos", {}),
        "atributos_por_revisar": kw.get("atributos_por_revisar", []),
        "uno_por_estudiante": kw.get("uno_por_estudiante", False),
        "posible_repetido_de": kw.get("posible_repetido_de"),
    }


@dataclass
class CatalogoVerificado(CatalogoFalso):
    """Catalogo con la lista marcada como revisada y el endpoint /resueltos."""

    revisada: bool = True
    items_resueltos: list[dict[str, Any]] = field(default_factory=list)

    async def listas(self, *, colegio_id: str, grado: str, anio_lectivo: int | None = None) -> list[dict]:
        self.llamadas.append("listas")
        if grado != self.grado:
            return []
        return [
            {
                "lista_id": "lista-1",
                "version_id": "ver-1",
                "grado": grado,
                "anio_lectivo": anio_lectivo or 2026,
                "revisada": self.revisada,
            }
        ]

    async def lista(self, lista_id: str) -> dict[str, Any]:
        self.llamadas.append("lista")
        return {
            "lista_id": lista_id,
            "version_id": "ver-1",
            "grado": self.grado,
            "revisada": self.revisada,
            "total_items": len(self.items_resueltos or self.renglones),
            "items": self.renglones,
        }

    async def revision(self, version_id: str) -> dict[str, Any]:
        # Misma forma que `lista()` pero por `version_id` explicito: es el camino
        # que toma el pipeline cuando el poller estampa el `version_id` del evento
        # en el hijo (para unir la lista aprobada con su trabajo en "Mis
        # solicitudes"). El fake devuelve la version pedida, revisada, con items.
        self.llamadas.append("revision")
        return {
            "lista_id": "lista-1",
            "version_id": version_id,
            "grado": self.grado,
            "revisada": self.revisada,
            "total_items": len(self.items_resueltos or self.renglones),
            "items": self.renglones,
        }

    async def resueltos(self, version_id: str) -> dict[str, Any]:
        self.llamadas.append("resueltos")
        return {
            "version_id": version_id,
            "revisada": True,
            "colegio_id": COLEGIO,
            "grado": self.grado,
            "anio_lectivo": 2026,
            "items": self.items_resueltos,
        }


def _catalogo_verificado(personaje: str | None = None) -> CatalogoVerificado:
    p = personaje
    return CatalogoVerificado(
        revisada=True,
        items_resueltos=[
            _item_resuelto(
                1,
                "cuaderno cuadriculado",
                "C001",
                [
                    _candidato_dict("TK-C001-ECO", "economico", 4500),
                    _candidato_dict("TK-C001-FAN", "confiable", 6000, personaje=p),
                ],
                cantidad=2,
            ),
            _item_resuelto(
                2,
                "cartuchera",
                "C009",
                [
                    _candidato_dict("TK-C009-ECO", "economico", 8000),
                    _candidato_dict("TK-C009-FAN", "confiable", 15000, personaje=p),
                ],
            ),
            _item_resuelto(
                3,
                "caja de colores",
                "C004",
                [_candidato_dict("TK-C004-CON", "confiable", 24900)],
            ),
            _item_resuelto(
                4,
                "Plan lector RAZ",
                None,
                [],
                tipo_item="licencia_digital",
                modo_adquisicion="plataforma",
                instruccion_colegio="Se adquiere con QUOVIX.",
            ),
        ],
    )


async def _crear_y_procesar(motor, catalogo, preferencias=None):
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias=preferencias or {},
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    estado = await trabajos.procesar(motor, trabajo_id, catalogo=catalogo)
    return trabajo_id, estado


# --------------------------------------------------------------------------
# La ruta rapida
# --------------------------------------------------------------------------


class TestRutaRapidaVerificada:
    async def test_no_llama_emparejar_y_arma_ahorrador_y_premium(self, motor):
        catalogo = _catalogo_verificado()
        trabajo_id, estado = await _crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert "emparejar" not in catalogo.llamadas
        assert "resueltos" in catalogo.llamadas
        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        assert {k["perfil"] for k in vista["kits"]} == {"Ahorrador", "Premium"}

    async def test_escribe_item_kit_linea_con_referencia_valida(self, motor):
        from sqlalchemy import func, select

        catalogo = _catalogo_verificado()
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)

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

        catalogo = _catalogo_verificado()
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)

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

        catalogo = _catalogo_verificado()
        catalogo.items_resueltos += [
            _item_resuelto(5, "Muda de ropa marcada", "C067", [], tipo_item="no_comprar"),
            _item_resuelto(6, "1 pliego de papel bond", "C129", []),
        ]
        trabajo_id, estado = await _crear_y_procesar(motor, catalogo)

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

        catalogo = _catalogo_verificado()
        catalogo.items_resueltos[0]["atributos_impuestos"] = {"rayado": "cuadriculado"}
        catalogo.items_resueltos += [
            _item_resuelto(
                5,
                "cuaderno ferrocarril",
                "C001",
                [],
                atributos_impuestos={"rayado": "ferrocarril"},
            ),
            _item_resuelto(
                6,
                "cuaderno rayado o cuadriculado",
                "C001",
                [_candidato_dict("TK-C001-ECO", "economico", 4500)],
                atributos_por_revisar=["rayado"],
            ),
        ]
        trabajo_id, estado = await _crear_y_procesar(motor, catalogo)

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
        catalogo = _catalogo_verificado()
        tijeras = [_candidato_dict("TK-C013-ECO", "economico", 5800)]
        catalogo.items_resueltos += [
            _item_resuelto(5, "Tijeras", "C013", tijeras, uno_por_estudiante=True),
            _item_resuelto(6, "tijeras", "C013", tijeras, uno_por_estudiante=True, posible_repetido_de=None),
        ]
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)
        kit = (await trabajos.ver(motor, trabajo_id, incluir_kits=True))["kits"][0]
        por_orden = {linea["orden"]: linea for linea in kit["lineas"]}
        assert por_orden[5]["unidades_a_comprar"] == 1
        assert por_orden[6]["unidades_a_comprar"] == 0
        assert "linea 5" in por_orden[6]["mensaje"]

    async def test_la_herramienta_repetida_no_viaja_en_cero_al_checkout(self, motor):
        # La linea repetida queda en el kit con 0 unidades para que el acudiente
        # la encuentre, pero Comercio exige cantidad > 0: si viajaba, el checkout
        # entero respondia 400 y el acudiente no podia pagar.
        catalogo = _catalogo_verificado()
        tijeras = [_candidato_dict("TK-C013-ECO", "economico", 5800)]
        catalogo.items_resueltos += [
            _item_resuelto(5, "Tijeras", "C013", tijeras, uno_por_estudiante=True),
            _item_resuelto(6, "tijeras", "C013", tijeras, uno_por_estudiante=True, posible_repetido_de=None),
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
        catalogo = _catalogo_verificado()
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        por_nombre = {e["nombre"]: e for e in vista["etapas"]}
        assert por_nombre["percepcion"]["estado"] == "ok"
        assert por_nombre["normalizacion"]["estado"] == "ok"
        assert por_nombre["resolucion"]["estado"] == "ok"
        assert por_nombre["optimizacion"]["estado"] == "ok"
        for nombre in ("percepcion", "normalizacion", "resolucion"):
            assert por_nombre[nombre]["detalle"].get("fuente") == "lista_verificada"

    async def test_linea_informativa_no_surtible_queda_visible(self, motor):
        catalogo = _catalogo_verificado()
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo)
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
        trabajo_id, estado = await _crear_y_procesar(motor, catalogo)

        assert "emparejar" in catalogo.llamadas
        assert "resueltos" not in catalogo.llamadas
        assert estado == EstadoTrabajo.ESPERA_REVISION.value


# --------------------------------------------------------------------------
# Anclaje de personaje (post-proceso puro sobre el kit)
# --------------------------------------------------------------------------


def _linea(orden: int, concepto: str | None, personaje: str | None, precio: int) -> LineaKit:
    elegido = Candidato(
        sku=f"SKU-{orden}",
        nombre=f"Producto {orden}",
        nivel="confiable",
        precio_cop=precio,
        personaje=personaje,
    )
    return LineaKit(
        hijo="hijo-1",
        orden=orden,
        descripcion=f"item {orden}",
        tipo="util",
        estado_resolucion=EstadoResolucion.RESUELTO_AUTO.value,
        cantidad_pedida=1,
        unidad_base="unidad",
        unidades_por_empaque=1,
        unidades_a_comprar=1,
        informativa=False,
        elegido=elegido,
        precio_unitario_cop=precio,
        subtotal_cop=precio,
        concepto_codigo=concepto,
    )


def _kit_con_conceptos() -> KitArmado:
    # Orden mezclado a proposito: los anclas no estan al frente ni en orden ancla.
    lineas = (
        _linea(1, "C005", "pikachu", 1000),  # no ancla
        _linea(2, "C086", "pikachu", 40000),  # maleta (ancla)
        _linea(3, "C020", None, 500),  # no ancla
        _linea(4, "C001", "pikachu", 6000),  # cuaderno (ancla)
        _linea(5, "C011", "pikachu", 9000),  # carpeta (ancla)
        _linea(6, "C009", "pikachu", 15000),  # cartuchera (ancla)
    )
    total = sum(x.subtotal_cop or 0 for x in lineas)
    return KitArmado(
        perfil="Fan",
        total_cop=total,
        objetivos={"costo": total, "fidelidad": 1.0, "disponibilidad": 1.0},
        lineas=lineas,
        consolidaciones=(),
    )


class TestAnclarPersonaje:
    def _conceptos(self, lineas: tuple[LineaKit, ...]) -> list[str | None]:
        return [linea.orden for linea in lineas]

    def test_sube_los_cuatro_anclas_al_tope_en_orden_canonico(self):
        kit = _kit_con_conceptos()
        anclado = anclar_personaje(kit, "pikachu")

        # Mapeo orden->concepto: 4=C001, 6=C009, 5=C011, 2=C086.
        primeros_cuatro = [linea.orden for linea in anclado.lineas[:4]]
        assert primeros_cuatro == [4, 6, 5, 2]
        # El resto conserva su orden relativo original: 1 y 3.
        assert [linea.orden for linea in anclado.lineas[4:]] == [1, 3]

    def test_no_cambia_totales_ni_consolidaciones(self):
        kit = _kit_con_conceptos()
        anclado = anclar_personaje(kit, "pikachu")

        assert anclado.total_cop == kit.total_cop
        assert anclado.consolidaciones == kit.consolidaciones
        assert len(anclado.lineas) == len(kit.lineas)
        assert {linea.orden for linea in anclado.lineas} == {linea.orden for linea in kit.lineas}

    def test_personaje_none_no_toca_el_kit(self):
        kit = _kit_con_conceptos()
        anclado = anclar_personaje(kit, None)
        assert anclado is kit

    def test_sin_ancla_del_personaje_pedido_devuelve_igual(self):
        kit = _kit_con_conceptos()
        anclado = anclar_personaje(kit, "batman")
        assert [linea.orden for linea in anclado.lineas] == [linea.orden for linea in kit.lineas]


# --------------------------------------------------------------------------
# El personaje llega al kit Fan end-to-end (regresion del bug de las 4 cards)
# --------------------------------------------------------------------------


@dataclass
class CatalogoRealista(CatalogoVerificado):
    """Modela el catalogo REAL: /resueltos NO trae la variante de personaje.

    El bug que esto defiende: `_elegir_por_nivel` del catalogo colapsa a una
    opcion por nivel y deja fuera la de personaje (es una via aparte, curada),
    asi que `/resueltos` nunca la entrega. El interruptor del Fan la pide por
    separado con `producto_de_personaje`. La fixture vieja horneaba el personaje
    dentro de los candidatos de /resueltos —ficcion que el catalogo real no
    produce— y por eso el bug pasaba verde.
    """

    async def producto_de_personaje(self, concepto: str, personaje: str) -> dict[str, Any] | None:
        self.llamadas.append("producto_de_personaje")
        if personaje.lower() != "spiderman":
            return None
        # El catalogo surte las cuatro anclas con spiderman (precio_desde, como
        # el endpoint publico de productos). La maleta (C086) no esta en la lista
        # de esta prueba, asi que solo C001/C009 caen en anclas presentes.
        return {
            "sku": f"SPIDEY-{concepto}",
            "nombre": f"{concepto} Spiderman",
            "marca": "Marvel",
            "nivel": "confiable",
            "personaje": "spiderman",
            "precio_desde": 20000,
            "unidades_por_empaque": 1,
        }


def _catalogo_realista() -> CatalogoRealista:
    # Mismos items que _catalogo_verificado pero SIN personaje en /resueltos:
    # es lo que el catalogo real entrega tras _elegir_por_nivel.
    base = _catalogo_verificado(personaje=None)
    return CatalogoRealista(revisada=True, items_resueltos=base.items_resueltos)


class TestPersonajeLlegaAlFan:
    async def test_el_fan_trae_spiderman_en_sus_anclas_aunque_resueltos_no_lo_tenga(self, motor):
        catalogo = _catalogo_realista()
        prefs = {"personaje_por_hijo": {"hijo-1": ["spiderman"]}, "pesos": {"personaje": 1}}
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo, preferencias=prefs)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        # El interruptor pidio el personaje por separado (no salio de /resueltos).
        assert "producto_de_personaje" in catalogo.llamadas
        fan = next(k for k in vista["kits"] if k["perfil"] == "Fan")

        # Las anclas surtidas de este set (C001 cuaderno, C009 cartuchera) traen
        # spiderman en el kit Fan; ese `personaje` es lo que pinta las cards.
        anclas = {
            li["concepto"]: li["producto_elegido"]
            for li in fan["lineas"]
            if li.get("concepto") in {"C001", "C009"} and li.get("producto_elegido")
        }
        assert anclas, "el Fan debe tener las anclas con producto elegido"
        assert all(p["personaje"] == "spiderman" for p in anclas.values())
        assert all(p["sku"].startswith("SPIDEY-") for p in anclas.values())

        # Los otros perfiles NO llevan el personaje (es una via del Fan).
        ahorrador = next(k for k in vista["kits"] if k["perfil"] == "Ahorrador")
        assert all((li.get("producto_elegido") or {}).get("personaje") is None for li in ahorrador["lineas"])

    async def test_sin_personaje_pedido_no_hay_fan_ni_se_pide_personaje(self, motor):
        # ADR 0030: el Fan solo se arma si el acudiente pidio un personaje.
        catalogo = _catalogo_realista()
        trabajo_id, _ = await _crear_y_procesar(motor, catalogo, preferencias={})
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert "producto_de_personaje" not in catalogo.llamadas
        assert all(k["perfil"] != "Fan" for k in vista["kits"])


@dataclass
class CatalogoDosPersonajes(CatalogoRealista):
    """Surte spiderman y frozen en las cuatro anclas; el resto no lo surte."""

    async def producto_de_personaje(self, concepto: str, personaje: str) -> dict[str, Any] | None:
        self.llamadas.append("producto_de_personaje")
        if personaje.lower() not in {"spiderman", "frozen"}:
            return None
        return {
            "sku": f"{personaje.upper()}-{concepto}",
            "nombre": f"{concepto} {personaje}",
            "nivel": "confiable",
            "personaje": personaje.lower(),
            "precio_desde": 20000,
            "unidades_por_empaque": 1,
        }


@pytest.fixture(autouse=True)
def _avisos_de_ancla_limpios():
    """El aviso de ancla no surtida sale una vez por proceso: cada test arranca en limpio."""
    trabajos._ANCLAS_AVISADAS.clear()
    yield
    trabajos._ANCLAS_AVISADAS.clear()


class TestAnclasPorHijo:
    async def test_un_hijo_cuatro_anclas_estables(self):
        from tukit_inteligencia.optimizador import CONCEPTOS_ANCLA

        primera = await trabajos.anclas_por_hijo(_catalogo_realista(), {"hijo-1": "spiderman"})
        segunda = await trabajos.anclas_por_hijo(_catalogo_realista(), {"hijo-1": "spiderman"})
        skus = {c: p["sku"] for c, p in primera["hijo-1"].items()}
        assert set(skus) == set(CONCEPTOS_ANCLA)
        assert skus == {c: p["sku"] for c, p in segunda["hijo-1"].items()}

    async def test_ancla_no_surtida_se_registra(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="tukit_inteligencia.trabajos"):
            r = await trabajos.anclas_por_hijo(_catalogo_realista(), {"hijo-1": "batman"})
        assert r == {}
        assert "batman" in caplog.text
        assert "C001" in caplog.text

    async def test_mismo_personaje_se_consulta_una_vez(self):
        catalogo = _catalogo_realista()
        r = await trabajos.anclas_por_hijo(catalogo, {"hijo-1": "spiderman", "hijo-2": "Spiderman"})
        assert catalogo.llamadas.count("producto_de_personaje") == 4
        assert r["hijo-1"] is r["hijo-2"]


class TestDosHijosEndToEnd:
    async def test_cada_hijo_recibe_su_personaje_en_el_fan(self, motor):
        base = _catalogo_verificado(personaje=None)
        catalogo = CatalogoDosPersonajes(revisada=True, items_resueltos=base.items_resueltos)
        prefs = {
            "personaje_por_hijo": {"hijo-1": ["spiderman"], "hijo-2": ["frozen"]},
            "pesos": {"personaje": 1},
        }
        respuesta = await trabajos.crear(
            motor,
            hijos=[
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Cuarto"},
            ],
            preferencias=prefs,
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
        fan = next(k for k in vista["kits"] if k["perfil"] == "Fan")

        personajes = {
            (li["hijo"], (li.get("producto_elegido") or {}).get("personaje"))
            for li in fan["lineas"]
            if li.get("concepto") in {"C001", "C009"}
        }
        assert ("hijo-1", "spiderman") in personajes
        assert ("hijo-2", "frozen") in personajes
        assert ("hijo-1", "frozen") not in personajes
        assert ("hijo-2", "spiderman") not in personajes


class TestElegirProductoDePersonaje:
    """La eleccion no depende del orden en que el catalogo entregue los candidatos."""

    def test_elegir_producto_de_personaje_es_determinista(self):
        from tukit_inteligencia.remoto import elegir_producto_de_personaje

        a = {"sku": "B", "nivel": "confiable", "precio_desde": 100}
        b = {"sku": "A", "nivel": "confiable", "precio_desde": 100}
        assert elegir_producto_de_personaje([a, b])["sku"] == "A"
        assert elegir_producto_de_personaje([b, a])["sku"] == "A"
        assert elegir_producto_de_personaje([]) is None

    def test_prefiere_con_precio_y_confiable(self):
        from tukit_inteligencia.remoto import elegir_producto_de_personaje

        sin_precio = {"sku": "A", "nivel": "confiable", "precio_desde": None}
        premium = {"sku": "B", "nivel": "premium", "precio_desde": 10}
        economico = {"sku": "C", "nivel": "economico", "precio_desde": 5}
        confiable_caro = {"sku": "D", "nivel": "confiable", "precio_desde": 900}
        confiable_barato = {"sku": "E", "nivel": "confiable", "precio_desde": 800}
        assert elegir_producto_de_personaje([sin_precio, premium])["sku"] == "B"
        assert elegir_producto_de_personaje([premium, economico])["sku"] == "C"
        assert elegir_producto_de_personaje([economico, confiable_caro])["sku"] == "D"
        assert elegir_producto_de_personaje([confiable_caro, confiable_barato])["sku"] == "E"
