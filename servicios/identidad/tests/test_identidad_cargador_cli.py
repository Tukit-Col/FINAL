"""NFR-MAN-01: la escritura, el informe y la linea de comandos de la siembra de colegios.

`test_cargador.py` fija el identificador derivado y el armado en memoria. Falta
lo que ocurre cuando el cargador de verdad toca la base y le habla a quien lo
corre, que es donde una siembra falla en silencio:

- `Cargador.escribir` hace `INSERT ... ON CONFLICT DO UPDATE` sobre colegio y
  sede: volver a sembrar actualiza las MISMAS filas (no duplica) y conserva
  `creado_en`; y es atomico, de modo que una sede rota no deja colegios sueltos;
- `_principal` NO escribe nada si hay codigos rotos o repetidos (devuelve 1) y
  con `--solo-validar` no toca la base (devuelve 0);
- `main` traduce la linea de comandos a esos dos caminos y a un codigo de salida
  (2 si el directorio de datos no existe);
- `Informe.imprimir` es la unica evidencia que ve el operador, asi que sus
  secciones, porcentajes y recortes ("... y N mas") se fijan por su salida.

La base es un archivo SQLite en un directorio temporal, elegido por la variable
`TUKIT_IDENTIDAD_DB_URL` que ya lee `crear_motor`; el `INSERT ... ON CONFLICT`
del dialecto de Postgres se compila tal cual en SQLite. No hay red ni Postgres.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from tukit_comun import derivar
from tukit_comun.bd import MotorServicio
from tukit_identidad import cargador
from tukit_identidad.cargador import Cargador, Informe, Problema, id_colegio, id_sede
from tukit_identidad.modelos import Base, Colegio, Sede

pytestmark = pytest.mark.nfr("NFR-MAN-01")

RAIZ = Path(__file__).resolve().parents[3]
DATOS_VERSIONADOS = RAIZ / "datos" / "listas"


def _csv(directorio: Path, filas: list[tuple[str, str, str]]) -> Path:
    contenido = "codigo,nombre,sede_nombre\n" + "".join(f"{c},{n},{s}\n" for c, n, s in filas)
    (directorio / "colegios.csv").write_text(contenido, encoding="utf-8")
    return directorio


@pytest.fixture
def bd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Una base SQLite en archivo con el esquema de Identidad, elegida por la
    misma variable de entorno que usa el servicio. Devuelve una funcion que
    ejecuta una consulta de lectura por una conexion sincrona aparte."""
    ruta = tmp_path / "identidad.db"
    monkeypatch.setenv("TUKIT_IDENTIDAD_DB_URL", f"sqlite+aiosqlite:///{ruta}")
    motor = create_engine(f"sqlite:///{ruta}")
    Base.metadata.create_all(motor)

    def consultar(consulta):
        with motor.connect() as conexion:
            return list(conexion.execute(consulta))

    yield consultar
    motor.dispose()


class TestInformeImprimir:
    def test_muestra_lo_escrito_las_carencias_con_porcentaje_y_las_carencias_con_nombre(
        self, capsys: pytest.CaptureFixture[str]
    ):
        informe = Informe(
            escritos={"colegio": 2, "sede": 2},
            problemas=[Problema(False, "sede", "`1.1` sin sede declarada")],
            carencias={"colegios sin NIT": (2, 2), "colegios sin nombre propio": (1, 2)},
        )

        informe.imprimir()
        salida = capsys.readouterr().out

        assert "=== sembrado ===" in salida
        assert "colegio" in salida and "sede" in salida
        assert "=== lo que falta para poder mostrarlo a un papa ===" in salida
        assert "(100%)" in salida and "(50%)" in salida
        assert "=== 1 carencia(s) con nombre propio ===" in salida
        assert "[carencia] sede: `1.1` sin sede declarada" in salida
        assert "BLOQUEAN" not in salida

    def test_los_problemas_bloqueantes_se_listan_y_se_recortan_a_veinte(
        self, capsys: pytest.CaptureFixture[str]
    ):
        problemas = [Problema(True, "codigo", f"fila {n} sin codigo") for n in range(25)]

        Informe(problemas=problemas).imprimir()
        salida = capsys.readouterr().out

        assert "=== 25 problema(s) que BLOQUEAN ===" in salida
        assert "[BLOQUEA] codigo: fila 19 sin codigo" in salida
        assert "fila 20 sin codigo" not in salida
        assert "... y 5 mas" in salida

    def test_las_carencias_con_nombre_se_recortan_a_quince(self, capsys: pytest.CaptureFixture[str]):
        problemas = [Problema(False, "sede", f"`{n}` sin sede") for n in range(20)]

        Informe(problemas=problemas).imprimir()
        salida = capsys.readouterr().out

        assert "=== 20 carencia(s) con nombre propio ===" in salida
        assert "`14` sin sede" in salida
        assert "`15` sin sede" not in salida
        assert "... y 5 mas" in salida

    def test_una_carencia_sobre_cero_colegios_imprime_0_por_ciento_sin_dividir_por_cero(
        self, capsys: pytest.CaptureFixture[str]
    ):
        Informe(carencias={"colegios sin NIT": (0, 0)}).imprimir()

        assert "(0%)" in capsys.readouterr().out

    def test_sin_problemas_ni_carencias_solo_imprime_lo_sembrado(self, capsys: pytest.CaptureFixture[str]):
        Informe(escritos={"colegio": 1}).imprimir()
        salida = capsys.readouterr().out

        assert "=== sembrado ===" in salida
        assert "falta" not in salida
        assert "carencia(s)" not in salida


class TestArmadoDeFilasRotas:
    def test_una_fila_sin_codigo_bloquea_pero_las_demas_se_arman(self, tmp_path: Path):
        directorio = _csv(
            tmp_path,
            [("2.4", "Colegio Ficticio Uno", "Sede unica"), ("", "Colegio Sin Codigo", "Sede unica")],
        )
        cargador_ = Cargador(directorio)

        datos = cargador_.armar()

        assert [c["nombre"] for c in datos["colegio"]] == ["Colegio Ficticio Uno"]
        [problema] = [p for p in cargador_.problemas if p.bloqueante]
        # La fila 1 es la cabecera: la primera de datos se numera como la 2.
        assert problema.clase == "codigo"
        assert "fila 3 sin codigo" in problema.detalle
        assert Informe(problemas=cargador_.problemas).bloqueado

    def test_si_ninguna_fila_tiene_codigo_no_hay_colegios_ni_carencias_que_medir(self, tmp_path: Path):
        cargador_ = Cargador(_csv(tmp_path, [("", "Colegio Sin Codigo", "Sede unica")]))

        datos = cargador_.armar()

        assert datos == {"colegio": [], "sede": []}
        assert cargador_.carencias == {}

    def test_codigo_y_nombre_se_recortan_y_la_sede_toma_su_nombre_del_csv(self, tmp_path: Path):
        cargador_ = Cargador(_csv(tmp_path, [("  2.4  ", "  Colegio Ficticio Uno  ", "  Sede norte  ")]))

        datos = cargador_.armar()

        assert datos["colegio"][0]["id"] == id_colegio("2.4")
        assert datos["colegio"][0]["nombre"] == "Colegio Ficticio Uno"
        assert datos["sede"][0]["id"] == id_sede("2.4", "Sede norte")


class TestEscribir:
    async def test_siembra_colegios_y_sedes_con_los_ids_derivados(self, tmp_path: Path, bd):
        cargador_ = Cargador(
            _csv(
                tmp_path,
                [
                    ("2.4", "Colegio Ficticio Uno", "Sede unica"),
                    ("2.5", "Colegio Ficticio Dos", "Sede norte"),
                ],
            )
        )

        escritos = await cargador_.escribir(cargador_.armar())

        assert escritos == {"colegio": 2, "sede": 2}
        colegios = {fila.id: fila for fila in bd(select(Colegio.__table__))}
        assert set(colegios) == {derivar("colegio", "2.4"), derivar("colegio", "2.5")}
        assert colegios[derivar("colegio", "2.4")].nombre == "Colegio Ficticio Uno"
        assert colegios[derivar("colegio", "2.4")].activo is True
        sedes = {fila.id: fila for fila in bd(select(Sede.__table__))}
        assert sedes[derivar("sede", "2.5", "Sede norte")].colegio_id == derivar("colegio", "2.5")

    async def test_sembrar_dos_veces_actualiza_las_mismas_filas_y_conserva_creado_en(
        self, tmp_path: Path, bd
    ):
        primera = Cargador(_csv(tmp_path, [("2.4", "Nombre Viejo", "Sede unica")]))
        await primera.escribir(primera.armar())
        antes = bd(select(Colegio.__table__.c.creado_en))[0].creado_en

        segunda = Cargador(_csv(tmp_path, [("2.4", "Nombre Nuevo", "Sede unica")]))
        await segunda.escribir(segunda.armar())

        [colegio] = bd(select(Colegio.__table__))
        assert colegio.nombre == "Nombre Nuevo"
        assert colegio.creado_en == antes
        assert bd(select(func.count()).select_from(Colegio.__table__))[0][0] == 1
        assert bd(select(func.count()).select_from(Sede.__table__))[0][0] == 1

    async def test_una_tabla_sin_filas_cuenta_cero_y_no_escribe(self, bd):
        escritos = await Cargador(Path(".")).escribir({"colegio": [], "sede": []})

        assert escritos == {"colegio": 0, "sede": 0}
        assert bd(select(func.count()).select_from(Colegio.__table__))[0][0] == 0

    async def test_una_sede_rota_revierte_tambien_los_colegios_y_cierra_el_motor(
        self, bd, monkeypatch: pytest.MonkeyPatch
    ):
        """La siembra es UNA transaccion: si la sede falla, no queda ningun
        colegio sin sede. El motor se cierra aunque la escritura reviente."""
        cerrados: list[str] = []
        cerrar_original = MotorServicio.cerrar

        async def espia(self: MotorServicio) -> None:
            cerrados.append(self.servicio)
            await cerrar_original(self)

        monkeypatch.setattr(MotorServicio, "cerrar", espia)
        colegio_id = derivar("colegio", "2.4")
        datos = {
            "colegio": [{"id": colegio_id, "nombre": "Colegio Ficticio Uno", "nit": None, "activo": True}],
            "sede": [
                {"id": derivar("sede", "2.4", "x"), "colegio_id": colegio_id, "nombre": None, "activa": True}
            ],
        }

        with pytest.raises(IntegrityError):
            await Cargador(Path(".")).escribir(datos)

        assert bd(select(func.count()).select_from(Colegio.__table__))[0][0] == 0
        assert cerrados == ["identidad"]


class TestPrincipal:
    async def test_siembra_y_cuenta_lo_escrito_en_el_informe(
        self, tmp_path: Path, bd, capsys: pytest.CaptureFixture[str]
    ):
        directorio = _csv(tmp_path, [("2.4", "Colegio Ficticio Uno", "Sede unica")])

        codigo = await cargador._principal(directorio, solo_validar=False)
        salida = capsys.readouterr().out

        assert codigo == 0
        assert bd(select(func.count()).select_from(Colegio.__table__))[0][0] == 1
        assert "=== sembrado ===" in salida
        assert "Las listas de estos colegios las siembra Catalogo, contra los mismos UUID." in salida

    async def test_solo_validar_informa_pero_no_escribe_nada(
        self, tmp_path: Path, bd, capsys: pytest.CaptureFixture[str]
    ):
        directorio = _csv(tmp_path, [("2.4", "Colegio Ficticio Uno", "Sede unica")])

        codigo = await cargador._principal(directorio, solo_validar=True)
        salida = capsys.readouterr().out

        assert codigo == 0
        assert bd(select(func.count()).select_from(Colegio.__table__))[0][0] == 0
        assert "(--solo-validar: no se escribio nada en la base)" in salida
        assert "siembra Catalogo" not in salida

    async def test_un_codigo_repetido_devuelve_1_y_no_escribe_ni_siquiera_el_colegio_bueno(
        self, tmp_path: Path, bd, capsys: pytest.CaptureFixture[str]
    ):
        directorio = _csv(
            tmp_path,
            [
                ("2.4", "Colegio Ficticio Uno", "Sede unica"),
                ("2.5", "Colegio Ficticio Dos", "Sede unica"),
                ("2.4", "Colegio Repetido", "Sede unica"),
            ],
        )

        codigo = await cargador._principal(directorio, solo_validar=False)
        salida = capsys.readouterr().out

        assert codigo == 1
        assert bd(select(func.count()).select_from(Colegio.__table__))[0][0] == 0
        assert "No se escribio nada: hay codigos de colegio rotos o repetidos." in salida
        assert "`2.4` repetido en las filas 2 y 4" in salida

    async def test_el_corpus_versionado_pasa_la_validacion_sin_bloqueos(
        self, capsys: pytest.CaptureFixture[str]
    ):
        """Guardia de datos: si alguien rompe `datos/listas/colegios.csv` (codigo
        repetido o vacio), esto lo dice antes de que la siembra llegue a la base."""
        codigo = await cargador._principal(DATOS_VERSIONADOS, solo_validar=True)

        assert codigo == 0
        assert "BLOQUEAN" not in capsys.readouterr().out


class TestMain:
    """`main` lee `sys.argv`; es sincrono por fuera (`asyncio.run`), asi que estas
    pruebas son sincronas."""

    def test_un_directorio_inexistente_devuelve_2_y_lo_nombra(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        faltante = tmp_path / "no-existe"
        monkeypatch.setattr(sys, "argv", ["cargador", "--datos", str(faltante)])

        assert cargador.main() == 2
        assert f"No existe el directorio de datos: {faltante}" in capsys.readouterr().out

    def test_con_datos_y_sin_banderas_siembra_la_base(
        self, tmp_path: Path, bd, monkeypatch: pytest.MonkeyPatch
    ):
        directorio = _csv(tmp_path, [("2.4", "Colegio Ficticio Uno", "Sede unica")])
        monkeypatch.setattr(sys, "argv", ["cargador", "--datos", str(directorio)])

        assert cargador.main() == 0
        assert [fila.nombre for fila in bd(select(Colegio.__table__))] == ["Colegio Ficticio Uno"]

    def test_solo_validar_no_toca_la_base(self, tmp_path: Path, bd, monkeypatch: pytest.MonkeyPatch):
        directorio = _csv(tmp_path, [("2.4", "Colegio Ficticio Uno", "Sede unica")])
        monkeypatch.setattr(sys, "argv", ["cargador", "--datos", str(directorio), "--solo-validar"])

        assert cargador.main() == 0
        assert bd(select(func.count()).select_from(Colegio.__table__))[0][0] == 0

    def test_ejecutado_como_script_sale_con_el_codigo_de_main(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        directorio = _csv(tmp_path, [("2.4", "Colegio Ficticio Uno", "Sede unica")])
        monkeypatch.delitem(sys.modules, "tukit_identidad.cargador")
        monkeypatch.setattr(sys, "argv", ["cargador", "--datos", str(directorio), "--solo-validar"])

        with pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_identidad.cargador", run_name="__main__")

        assert salida.value.code == 0
        assert "(--solo-validar" in capsys.readouterr().out
