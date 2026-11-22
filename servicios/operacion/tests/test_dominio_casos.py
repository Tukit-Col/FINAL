from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tukit_operacion.dominio.casos import (
    CategoriaRechazada,
    admitir_categoria_acudiente,
    clave_orden,
    prioridad_inicial,
    vence_en,
)
from tukit_operacion.modelos import CategoriaCaso, Prioridad

AHORA = datetime(2026, 1, 1, tzinfo=UTC)


def test_admite_una_categoria_de_acudiente():
    assert admitir_categoria_acudiente("peticion") is CategoriaCaso.PETICION


def test_rechaza_categoria_de_saga_como_no_permitida():
    rechazo = admitir_categoria_acudiente("mapeo_lista")
    assert isinstance(rechazo, CategoriaRechazada)
    assert rechazo.razon == "categoria_no_permitida"
    assert rechazo.estado == 422


def test_rechaza_categoria_inexistente_como_invalida():
    rechazo = admitir_categoria_acudiente("inventada")
    assert isinstance(rechazo, CategoriaRechazada)
    assert rechazo.razon == "categoria_invalida"
    assert rechazo.estado == 422


def test_prioridad_inicial_por_categoria():
    assert prioridad_inicial(CategoriaCaso.PAGO) is Prioridad.URGENTE
    assert prioridad_inicial(CategoriaCaso.SUGERENCIA) is Prioridad.BAJA


def test_vence_en_pago_antes_que_peticion():
    pago = vence_en(CategoriaCaso.PAGO, AHORA)
    peticion = vence_en(CategoriaCaso.PETICION, AHORA)
    assert pago == AHORA + timedelta(hours=24)
    assert pago < peticion


def test_clave_orden_urgente_va_antes_que_media():
    assert clave_orden("urgente", AHORA) < clave_orden("media", AHORA)


def test_clave_orden_sin_vencimiento_va_al_final_de_su_grupo():
    assert clave_orden("alta", AHORA) < clave_orden("alta", None)


def test_clave_orden_prioridad_desconocida_va_al_fondo():
    assert clave_orden("inexistente", AHORA) > clave_orden("baja", AHORA)
