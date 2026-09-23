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
    async def test_no_llama_emparejar_y_arma_tres_kits(self, motor):
        catalogo = _catalogo_verificado()
        trabajo_id, estado = await _crear_y_procesar(motor, catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert "emparejar" not in catalogo.llamadas
        assert "resueltos" in catalogo.llamadas
        assert estado == EstadoTrabajo.ESPERA_REVISION.value
        assert {k["perfil"] for k in vista["kits"]} == {"Ahorrador", "Fan", "Premium"}

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
                select(func.count()).select_from(trabajos.KIT).where(
                    trabajos.KIT.c.trabajo_id == trabajo_id
                )
            )
            lineas = list(
                await conexion.execute(
                    select(trabajos.LINEA.c.item_crudo_id).select_from(
                        trabajos.LINEA.join(trabajos.KIT, trabajos.LINEA.c.kit_id == trabajos.KIT.c.id)
                    ).where(trabajos.KIT.c.trabajo_id == trabajo_id)
                )
            )

        assert len(item_ids) == 4
        assert kits == 3
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
                "2 cuadernos": reconocido(
                    "2 cuadernos", "C001", [opcion("TK-C001-ECO", "economico", 4500)]
                )
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
