"""La notificacion referencia al usuario por id y no guarda el dato de contacto.

Es la deuda que el manifiesto documenta: el servicio anterior persistia el
correo real dentro del contenido y el derecho al olvido no lo alcanzaba. Aqui
lo comprobamos a nivel de esquema: ninguna columna de `notificacion` ni de
`preferencia_notificacion` se llama como un dato de contacto.
"""

from __future__ import annotations

from tukit_operacion.modelos import Notificacion, PreferenciaNotificacion

PROHIBIDAS = {"correo", "email", "celular", "telefono", "phone"}


def test_notificacion_no_tiene_columnas_de_contacto():
    columnas = {c.name for c in Notificacion.__table__.columns}
    assert PROHIBIDAS.isdisjoint(columnas)
    # Referencia al destinatario por id, que es la forma correcta.
    assert "usuario_id" in columnas


def test_preferencia_no_tiene_columnas_de_contacto():
    columnas = {c.name for c in PreferenciaNotificacion.__table__.columns}
    assert PROHIBIDAS.isdisjoint(columnas)
    assert "usuario_id" in columnas
