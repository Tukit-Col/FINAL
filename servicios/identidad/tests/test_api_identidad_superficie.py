"""La superficie minima de Identidad, y sobre todo lo que NO expone.

La prueba mas util de este archivo es la ultima: comprueba que ninguna ruta
devuelva un estudiante, un nombre de menor ni una matricula. Identidad es la
frontera de cumplimiento del sistema, asi que abrir esa superficie sin
autenticacion ni control por clasificacion de dato seria justo el defecto que
el Anexo M documenta. Que hoy no exista es una decision, y una decision hay
que poder verificarla.
"""

from __future__ import annotations

import pytest
from tukit_identidad.api import app


def test_las_rutas_vienen_de_un_router_incluido(cliente):
    # ADR 0019: api.py es solo ensamblador; las rutas viven en routers/identidad.py.
    from tukit_identidad.routers import router

    montadas = {r.path for r in router.routes}
    assert "/v1/colegios" in montadas
    assert "/v1/sesiones" in montadas
    assert "/v1/cuenta/direcciones/{direccion_id}" in montadas


class TestLaSuperficieDeMenoresNoEstaAbierta:
    @pytest.mark.parametrize(
        "ruta",
        ["/v1/estudiantes", "/v1/matriculas", "/v1/usuarios", "/v1/colegios/2.4/estudiantes"],
    )
    async def test_no_hay_ruta_que_devuelva_datos_de_menores(self, cliente, ruta):
        assert (await cliente.get(ruta)).status_code in {404, 422}

    def test_el_esquema_publicado_no_anuncia_ninguna(self):
        """Se mira el OpenAPI y no solo las respuestas: una ruta que existe
        y hoy nadie llama es una ruta que alguien llama manana."""
        rutas = set(app.openapi()["paths"])
        assert rutas == {
            "/salud",
            # Liveness/readiness (ADR 0021): sondas sin PII, abiertas a proposito.
            "/health/live",
            "/health/ready",
            "/v1/colegios",
            "/v1/colegios/{colegio_id}",
            "/v1/grados",
            "/v1/contactos",
            # Resuelve un id a su contacto para ENVIAR (el repartidor de
            # Operacion), sin devolver menor ni matricula: la contraparte de
            # POST /v1/contactos. Efimera, nadie la persiste.
            "/v1/contactos/{usuario_id}",
            "/v1/contactos/{usuario_id}/credencial",
            # Datos DUEB de un colegio del directorio de Bogota (direccion,
            # contacto, sitio) para pre-llenar el perfil de un colegio nuevo. Es
            # el registro publico de establecimientos: no toca menores ni
            # matriculas, no abre la superficie sensible.
            "/v1/directorio/{dane}",
            # Nombres de acudientes ADULTOS por id, para el panel del back-office.
            # Es PII PERSONAL (no menor): exige `usuario:leer:nombre` (solo admin
            # y operador) y solo lee la tabla `usuario`, jamas `estudiante`. No
            # abre la superficie sensible de menores.
            "/v1/usuarios/nombres",
            # Autenticacion (seccion 12.4). Devuelven quien es el portador y sus
            # ROLES, nunca un estudiante ni un nombre de menor: la superficie
            # sensible sigue cerrada, es lo que fija la prueba de arriba.
            "/v1/sesiones",
            "/v1/sesiones/actual",
            "/v1/sesiones/cierre",
            # "Mi cuenta": quien soy y mi libreta de direcciones. Todo exige el
            # token y solo devuelve lo propio del portador; no abre menores.
            "/v1/cuenta",
            "/v1/cuenta/direcciones",
            "/v1/cuenta/direcciones/{direccion_id}",
            # "Mis hijos": apodos del portador, nunca nombres reales de menor.
            # Exige token y solo devuelve lo propio (Ley 1581 / Anexo M).
            "/v1/cuenta/hijos",
            # La tenencia del PROPIO portador. Este path tiene GET y POST y
            # se ABRE deliberadamente sobre dato de menor, pero acotado: exige token
            # y filtra por usuario_id (no por rol), asi que un padre solo alcanza a
            # SUS hijos. El GET devuelve el apodo del portador (descifrado, para
            # precargar `/empezar`) y el POST agrega matriculas del portador; ambos
            # siguen sin exponer nombre legal, documento ni estudiante_id. Nota: GET
            # y POST comparten esta clave de path, asi que el `set` no gana una
            # entrada nueva —no hay "lista" que ampliar, solo esta documentacion—.
            "/v1/cuenta/matriculas",
            # Quitar (DELETE) o cambiar de colegio (PUT) a UN hijo del portador.
            # Misma regla: exige token, solo alcanza matriculas con vinculo del
            # portador (404 si no es suya) y no devuelve dato de menor. Quitar no
            # borra: cierra el vinculo y retira la matricula (ADR 0031).
            "/v1/cuenta/matriculas/{matricula_id}",
            # El panel de privacidad (Ley 1581): consulta, copia, revocacion y
            # supresion del PROPIO portador. Exigen token y no tienen id en la
            # ruta, asi que no alcanzan datos de otro titular. Los apodos que
            # devuelven son los mismos de `/v1/cuenta/matriculas`.
            "/v1/cuenta/mis-datos",
            "/v1/cuenta/mis-datos/exportar",
            "/v1/cuenta/consentimientos/revocar",
            "/v1/cuenta/supresion",
            # El registro de verdad. Solo ESCRIBE (credencial + matriculas) y
            # nunca devuelve datos de menor: su respuesta es {usuario_id, creado}.
            "/v1/registro",
            # El padron de acudientes para el equipo interno. UNICA ruta que
            # expone dato de menor (el apodo) por la superficie publica, y por
            # eso GATEADA: 401 sin token, 403 sin rol admin/operador. Devuelve
            # solo familias registradas (credencial real, sin rol interno);
            # nunca clave, documento, fecha de nacimiento ni nombre legal. La
            # justifica el test del gate (TestElPadronDeAcudientes).
            "/v1/admin/acudientes",
        }
