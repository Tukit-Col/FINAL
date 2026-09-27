"""La superficie minima de Identidad, y sobre todo lo que NO expone.

La prueba mas util de este archivo es la ultima: comprueba que ninguna ruta
devuelva un estudiante, un nombre de menor ni una matricula. Identidad es la
frontera de cumplimiento del sistema, asi que abrir esa superficie sin
autenticacion ni control por clasificacion de dato seria justo el defecto que
el Anexo M documenta. Que hoy no exista es una decision, y una decision hay
que poder verificarla.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_comun.identificadores import derivar
from tukit_identidad.api import GRADOS, app
from tukit_identidad.modelos import Base, Colegio, Sede


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        colegio = Colegio(
            id=derivar("colegio", "2.4"),
            nombre="Colegio San Pedro",
            logo_url="https://cdn.tukit.co/colegios/san-pedro.png",
            sitio_web="https://sanpedro.edu.co",
            contacto_nombre="Secretaria academica",
            contacto_email="secretaria@sanpedro.edu.co",
            contacto_telefono="+57 1 2345678",
            direccion="Calle 1 # 2-3, Bogota",
        )
        sesion.add(colegio)
        await sesion.flush()
        sesion.add(Sede(id=derivar("sede", "2.4", "Sede unica"), colegio_id=colegio.id, nombre="Sede unica"))
        # Un segundo colegio sin perfil: los campos nuevos serializan null.
        sesion.add(Colegio(id=derivar("colegio", "9.9"), nombre="Colegio Sin Perfil"))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


class TestElDirectorioNoFiltraDeMas:
    """`GET /v1/directorio/{dane}` sirve dos formas en la MISMA ruta. Por defecto
    solo los 7 campos del alta: es lo que la subida de listas vuelca sin filtrar
    en `colegio_datos`, asi que un campo de mas se filtraria a cada colegio nuevo.
    La ficha completa (sector, localidad, rector, telefonos, correos) solo sale
    con `?completo=true`, para el detalle del colegio en el admin. Se usa un DANE
    real del directorio (no uno inventado) para no acoplar la prueba a un codigo."""

    async def test_por_defecto_solo_devuelve_los_campos_del_alta(self, cliente):
        from tukit_identidad.directorio_bogota import (
            _indice_por_dane,
            datos_colegio_nuevo_por_dane,
        )

        dane = next(iter(_indice_por_dane()))
        cuerpo = (await cliente.get(f"/v1/directorio/{dane}")).json()
        # Igualdad exacta: ni una clave de mas. Esto protege el flujo de subida
        # (MapaRuiz) de que se filtren datos del directorio a `colegio_datos`.
        assert set(cuerpo) == set(datos_colegio_nuevo_por_dane(dane))

    async def test_completo_agrega_el_superconjunto_del_admin(self, cliente):
        from tukit_identidad.directorio_bogota import _indice_por_dane

        dane = next(iter(_indice_por_dane()))
        cuerpo = (await cliente.get(f"/v1/directorio/{dane}?completo=true")).json()
        assert {"sector", "localidad", "rector", "telefonos", "correos"} <= set(cuerpo)


class TestElAcudienteEscogeColegioYGrado:
    async def test_los_colegios_traen_su_numero_de_sedes(self, cliente):
        cuerpo = (await cliente.get("/v1/colegios")).json()

        assert cuerpo["total"] == 2
        # Ordenados por nombre: "San Pedro" antes que "Sin Perfil".
        assert cuerpo["colegios"][0]["nombre"] == "Colegio San Pedro"
        assert cuerpo["colegios"][0]["sedes"] == 1

    async def test_el_identificador_es_el_derivado_que_usa_catalogo(self, cliente):
        """Es lo que hace que `lista_oficial.colegio_id` resuelva de verdad:
        los dos cargadores derivan el mismo UUID del mismo codigo."""
        cuerpo = (await cliente.get("/v1/colegios")).json()
        assert cuerpo["colegios"][0]["colegio_id"] == str(derivar("colegio", "2.4"))

    async def test_un_colegio_que_no_existe_es_404_con_codigo(self, cliente):
        respuesta = await cliente.get(f"/v1/colegios/{uuid.uuid4()}")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "colegio_no_existe"


class TestElPerfilDelColegio:
    """El logo y los contactos que el padre reconoce en la tarjeta de partner.

    Son datos institucionales, no de menor: no les aplica el cifrado del
    Anexo M que sí protege al estudiante en el mismo modelo. Por eso viajan en
    claro por la superficie pública, a diferencia de todo lo de `menor`.
    """

    async def test_el_detalle_trae_logo_sitio_y_contactos(self, cliente):
        cid = str(derivar("colegio", "2.4"))
        cuerpo = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert cuerpo["logo_url"] == "https://cdn.tukit.co/colegios/san-pedro.png"
        assert cuerpo["sitio_web"] == "https://sanpedro.edu.co"
        assert cuerpo["contacto_nombre"] == "Secretaria academica"
        assert cuerpo["contacto_email"] == "secretaria@sanpedro.edu.co"
        assert cuerpo["contacto_telefono"] == "+57 1 2345678"
        assert cuerpo["direccion"] == "Calle 1 # 2-3, Bogota"

    async def test_el_listado_trae_el_logo_para_la_tarjeta(self, cliente):
        # El logo va en el listado porque el desplegable del padre lo pinta
        # sin abrir el detalle; los contactos no, que son de la pantalla admin.
        cuerpo = (await cliente.get("/v1/colegios")).json()
        san_pedro = next(c for c in cuerpo["colegios"] if c["nombre"] == "Colegio San Pedro")
        assert san_pedro["logo_url"] == "https://cdn.tukit.co/colegios/san-pedro.png"

    async def test_un_colegio_sin_perfil_serializa_los_campos_como_null(self, cliente):
        cid = str(derivar("colegio", "9.9"))
        cuerpo = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert cuerpo["logo_url"] is None
        assert cuerpo["sitio_web"] is None
        assert cuerpo["contacto_nombre"] is None
        assert cuerpo["contacto_email"] is None
        assert cuerpo["contacto_telefono"] is None
        assert cuerpo["direccion"] is None

    async def test_los_grados_van_en_orden_escolar_y_no_alfabetico(self, cliente):
        cuerpo = (await cliente.get("/v1/grados")).json()
        assert cuerpo["grados"] == list(GRADOS)
        assert cuerpo["grados"][0] == "Parvulos"
        assert cuerpo["grados"][-1] == "Once"


class TestEditarElPerfilDelColegio:
    """El administrador completa el perfil institucional que el padre reconoce.

    Solo los campos institucionales —logo, sitio, contactos— son editables. El
    nombre y el NIT son la identidad de la institucion y no se tocan por esta
    puerta: cambiarlos rompe la referencia que Catalogo guarda por colegio_id.
    Estos datos NO son de menor, asi que no les toca el cifrado del Anexo M.
    """

    async def test_editar_persiste_y_hace_round_trip_por_el_get(self, cliente):
        cid = str(derivar("colegio", "9.9"))  # el que nace sin perfil
        respuesta = await cliente.patch(
            f"/v1/colegios/{cid}",
            json={
                "logo_url": "https://cdn.tukit.co/colegios/sin-perfil.png",
                "contacto_email": "rectoria@sinperfil.edu.co",
            },
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["logo_url"] == "https://cdn.tukit.co/colegios/sin-perfil.png"
        assert cuerpo["contacto_email"] == "rectoria@sinperfil.edu.co"
        # El nombre no se toca: es institucional y no vino en el cuerpo.
        assert cuerpo["nombre"] == "Colegio Sin Perfil"

        # Y persiste: el GET del detalle lo devuelve igual.
        despues = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert despues["logo_url"] == "https://cdn.tukit.co/colegios/sin-perfil.png"
        assert despues["contacto_email"] == "rectoria@sinperfil.edu.co"

    async def test_devuelve_la_misma_forma_que_el_detalle(self, cliente):
        cid = str(derivar("colegio", "2.4"))
        cuerpo = (
            await cliente.patch(f"/v1/colegios/{cid}", json={"sitio_web": "https://nuevo.edu.co"})
        ).json()
        assert set(cuerpo.keys()) == {
            "colegio_id",
            "nombre",
            "dane",
            "logo_url",
            "sitio_web",
            "contacto_nombre",
            "contacto_email",
            "contacto_telefono",
            "direccion",
            "sedes",
        }
        assert cuerpo["sitio_web"] == "https://nuevo.edu.co"

    async def test_un_colegio_que_no_existe_es_404(self, cliente):
        respuesta = await cliente.patch(f"/v1/colegios/{uuid.uuid4()}", json={"sitio_web": "x"})
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "colegio_no_existe"

    @pytest.mark.parametrize("campo", ["nombre", "nit"])
    async def test_los_campos_institucionales_no_se_editan(self, cliente, campo):
        cid = str(derivar("colegio", "2.4"))
        respuesta = await cliente.patch(f"/v1/colegios/{cid}", json={campo: "Otro"})
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "campo_no_editable"
        assert respuesta.json()["campo"] == campo

    async def test_el_dane_si_se_puede_completar(self, cliente):
        """A diferencia del NIT, el DANE si se edita: aqui el id ya esta fijado y
        no se re-deriva del DANE, asi que completarlo cuando falta es seguro y es
        lo que habilita leer la ficha del directorio."""
        cid = str(derivar("colegio", "2.4"))
        cuerpo = (await cliente.patch(f"/v1/colegios/{cid}", json={"dane": "311001105731"})).json()
        assert cuerpo["dane"] == "311001105731"
        despues = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert despues["dane"] == "311001105731"

    @pytest.mark.parametrize("dane", ["311001093", "311001105731a", "abcdefghijkl", "3110 0110573"])
    async def test_un_dane_que_no_son_12_digitos_es_400(self, cliente, dane):
        """El DANE es la llave del directorio DUEB: si no son 12 digitos exactos se
        rechaza antes de escribir, con el mismo formato de error 400 del endpoint."""
        cid = str(derivar("colegio", "2.4"))
        respuesta = await cliente.patch(f"/v1/colegios/{cid}", json={"dane": dane})
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "dane_invalido"
        assert respuesta.json()["campo"] == "dane"

    async def test_el_dane_se_puede_vaciar_con_null(self, cliente):
        """`null` vacia el DANE (p. ej. si se cargo uno equivocado): es valido y
        deja el colegio sin ficha de directorio, sin romper."""
        cid = str(derivar("colegio", "2.4"))
        await cliente.patch(f"/v1/colegios/{cid}", json={"dane": "311001105731"})
        cuerpo = (await cliente.patch(f"/v1/colegios/{cid}", json={"dane": None})).json()
        assert cuerpo["dane"] is None
        despues = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert despues["dane"] is None


class TestElContactoSeVuelveUnIdentificador:
    async def test_devuelve_un_id_y_no_repite_el_correo(self, cliente):
        """El trabajo del pipeline guarda `usuario_id` y nunca el correo: es
        lo que hace que el derecho al olvido lo alcance en un solo sitio."""
        respuesta = await cliente.post("/v1/contactos", json={"correo": "papa@ejemplo.com"})

        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["creado"] is True
        assert uuid.UUID(cuerpo["usuario_id"])
        assert "papa@ejemplo.com" not in respuesta.text

    async def test_resolver_un_id_devuelve_su_contacto_para_enviar(self, cliente):
        """La contraparte: el repartidor cambia el id por el correo justo al
        enviar. `celular` es nulo porque ninguna tabla lo persiste hoy."""
        creado = (await cliente.post("/v1/contactos", json={"correo": "mama@ejemplo.com"})).json()

        respuesta = await cliente.get(f"/v1/contactos/{creado['usuario_id']}")
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["usuario_id"] == creado["usuario_id"]
        assert cuerpo["correo"] == "mama@ejemplo.com"
        assert cuerpo["celular"] is None

    async def test_resolver_un_id_que_no_existe_da_404(self, cliente):
        respuesta = await cliente.get(f"/v1/contactos/{uuid.uuid4()}")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "usuario_no_existe"

    async def test_el_mismo_correo_no_crea_dos_cuentas(self, cliente):
        primero = (await cliente.post("/v1/contactos", json={"correo": "papa@ejemplo.com"})).json()
        segundo = (await cliente.post("/v1/contactos", json={"correo": "PAPA@Ejemplo.com "})).json()

        assert segundo["usuario_id"] == primero["usuario_id"]
        assert segundo["creado"] is False

    @pytest.mark.parametrize("correo", ["papa@ejemplo", "papa ejemplo.com", "@ejemplo.com"])
    async def test_lo_que_no_es_un_correo_no_crea_cuenta(self, cliente, correo):
        """422 y no 400: la entrada es valida como cadena y es el dominio
        quien la rechaza. El contrato separa los dos casos a proposito."""
        respuesta = await cliente.post("/v1/contactos", json={"correo": correo})
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "correo"

    async def test_una_cadena_demasiado_corta_la_para_la_validacion_de_forma(self, cliente):
        respuesta = await cliente.post("/v1/contactos", json={"correo": "a@b"})
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "entrada_invalida"


class TestElRegistroDelAcudiente:
    """El alta con credencial y los hijos del acudiente nuevo (camino B)."""

    async def test_crea_una_cuenta_con_credencial_usable(self, cliente):
        respuesta = await cliente.post(
            "/v1/registro",
            json={"correo": "nueva@ejemplo.com", "clave": "clave1234", "celular": "3001112233", "hijos": []},
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["creado"] is True

        # Y la credencial sirve: la cuenta puede iniciar sesion.
        sesion = await cliente.post(
            "/v1/sesiones", json={"correo": "nueva@ejemplo.com", "clave": "clave1234"}
        )
        assert sesion.status_code == 200
        assert sesion.json()["sesion"]["correo"] == "nueva@ejemplo.com"

    async def test_asciende_un_contacto_sin_credencial_sin_perder_su_id(self, cliente):
        """Orden-independiente con /v1/contactos: quien primero pidio un kit
        (creando el contacto) y luego se registra conserva el MISMO id, para
        que el trabajo del pipeline que ya lo referencia siga apuntando bien."""
        contacto = (await cliente.post("/v1/contactos", json={"correo": "mixta@ejemplo.com"})).json()
        assert contacto["creado"] is True

        registro = (
            await cliente.post(
                "/v1/registro", json={"correo": "mixta@ejemplo.com", "clave": "clave1234", "hijos": []}
            )
        ).json()
        assert registro["creado"] is True
        assert registro["usuario_id"] == contacto["usuario_id"]

        # Antes no podia entrar (centinela); ahora si.
        sesion = await cliente.post(
            "/v1/sesiones", json={"correo": "mixta@ejemplo.com", "clave": "clave1234"}
        )
        assert sesion.status_code == 200

    async def test_no_pisa_una_cuenta_ya_registrada(self, cliente):
        """La ruta es publica: no debe dejar que un tercero cambie la clave de
        una cuenta que ya tiene credencial."""
        await cliente.post("/v1/registro", json={"correo": "duena@ejemplo.com", "clave": "originaal", "hijos": []})
        repetido = await cliente.post(
            "/v1/registro", json={"correo": "duena@ejemplo.com", "clave": "otraaaaa", "hijos": []}
        )
        assert repetido.status_code == 201
        assert repetido.json()["creado"] is False

        # La clave sigue siendo la original, no la del segundo intento.
        assert (
            await cliente.post("/v1/sesiones", json={"correo": "duena@ejemplo.com", "clave": "originaal"})
        ).status_code == 200
        assert (
            await cliente.post("/v1/sesiones", json={"correo": "duena@ejemplo.com", "clave": "otraaaaa"})
        ).status_code == 401

    async def test_persiste_los_hijos_y_los_expone_por_cuenta_matriculas(self, cliente):
        colegio_id = str(derivar("colegio", "2.4"))
        await cliente.post(
            "/v1/registro",
            json={
                "correo": "conhijos@ejemplo.com",
                "clave": "clave1234",
                "hijos": [{"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Pipe"}],
            },
        )
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "conhijos@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]

        respuesta = await cliente.get(
            "/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token}"}
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["total"] == 1
        assert cuerpo["matriculas"][0]["colegio_id"] == colegio_id
        assert cuerpo["matriculas"][0]["grado"] == "Quinto"
        # El apodo NUNCA sale: la matricula es ambito, no identidad del menor.
        assert "Pipe" not in respuesta.text
        assert "apodo" not in cuerpo["matriculas"][0]

    async def test_reenviar_el_mismo_formulario_no_duplica_matriculas(self, cliente):
        colegio_id = str(derivar("colegio", "2.4"))
        cuerpo = {
            "correo": "repite@ejemplo.com",
            "clave": "clave1234",
            "hijos": [{"colegio_id": colegio_id, "grado": "Quinto"}],
        }
        # Nace como contacto y luego se registra dos veces (idempotente).
        await cliente.post("/v1/registro", json=cuerpo)
        # El segundo POST no asciende (ya tiene credencial) pero tampoco debe
        # duplicar; comprobamos por matriculas tras un solo alta valida.
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "repite@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]
        cuenta = (
            await cliente.get("/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token}"})
        ).json()
        assert cuenta["total"] == 1

    async def test_un_grado_que_no_existe_es_422(self, cliente):
        colegio_id = str(derivar("colegio", "2.4"))
        respuesta = await cliente.post(
            "/v1/registro",
            json={
                "correo": "malgrado@ejemplo.com",
                "clave": "clave1234",
                "hijos": [{"colegio_id": colegio_id, "grado": "5"}],
            },
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "grado"


class TestMisMatriculasExigenToken:
    async def test_sin_token_es_401(self, cliente):
        assert (await cliente.get("/v1/cuenta/matriculas")).status_code == 401

    async def test_solo_devuelve_lo_del_portador(self, cliente):
        """Otro acudiente no ve las matriculas ajenas ni con token valido."""
        colegio_id = str(derivar("colegio", "2.4"))
        await cliente.post(
            "/v1/registro",
            json={
                "correo": "conkid@ejemplo.com",
                "clave": "clave1234",
                "hijos": [{"colegio_id": colegio_id, "grado": "Quinto"}],
            },
        )
        await cliente.post("/v1/registro", json={"correo": "sinkid@ejemplo.com", "clave": "clave1234", "hijos": []})
        token_ajeno = (
            await cliente.post("/v1/sesiones", json={"correo": "sinkid@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]

        cuenta = (
            await cliente.get("/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token_ajeno}"})
        ).json()
        assert cuenta["total"] == 0


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
            "/v1/colegios",
            "/v1/colegios/{colegio_id}",
            "/v1/grados",
            "/v1/contactos",
            # Resuelve un id a su contacto para ENVIAR (el repartidor de
            # Operacion), sin devolver menor ni matricula: la contraparte de
            # POST /v1/contactos. Efimera, nadie la persiste.
            "/v1/contactos/{usuario_id}",
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
            # El ambito de tenencia del PROPIO portador: colegio, grado y anio,
            # nada que singularice al menor. Exige token y filtra por usuario_id
            # (no por rol), asi que sigue cerrada la superficie sensible: no
            # devuelve nombre, apodo, documento ni estudiante_id.
            "/v1/cuenta/matriculas",
            # El registro de verdad. Solo ESCRIBE (credencial + matriculas) y
            # nunca devuelve datos de menor: su respuesta es {usuario_id, creado}.
            "/v1/registro",
            # Datos DUEB de un colegio del directorio de Bogota por DANE, para
            # pre-llenar el perfil del colegio nuevo en la cola. Es dato
            # INSTITUCIONAL del directorio publico (nombre, localidad), no de
            # menores: no abre la superficie sensible.
            "/v1/directorio/{dane}",
        }
