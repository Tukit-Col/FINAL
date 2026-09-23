# Resolución híbrida con grafo — Plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para
> ejecutar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Spec:** `tukit/docs/specs/2026-09-22-resolucion-hibrida-grafo-design.md`

**Goal:** Que el emparejamiento deje de ser comparación de cadenas y pase a recuperar por tres
canales (léxico, denso y grafo), con la decisión tomada sobre una probabilidad calibrada en vez
de un puntaje crudo.

**Architecture:** `catalogo` **recupera y no decide**: un endpoint nuevo devuelve el pool de
candidatos con sus puntajes por canal. `inteligencia` reordena tras un puerto, calibra a
probabilidad y decide con τ/δ. El grafo de conceptos se construye una vez en memoria y se
cachea.

**Tech Stack:** Python 3.12, Postgres 16 con `pgvector` (HNSW coseno) y `pg_trgm` (GIN),
`multilingual-e5-large` (1024 dimensiones), scikit-learn para la regresión isotónica y la
logística de respaldo, FastAPI, pytest.

## Global Constraints

- **TDD obligatorio.** Ninguna línea de producción sin una prueba que haya fallado antes.
- **`ruff` limpio**, `line-length = 110`, reglas `E,F,I,UP,B,SIM`.
- Los cinco invariantes de `tukit/arquitectura/test_fronteras.py` siguen verdes.
- **`catalogo` es de solo lectura y no sale a la red en la ruta del acudiente.** Hay una prueba
  que lo vigila y no se puede romper. El único `POST` que existe no escribe nada.
- **`catalogo` recupera, `inteligencia` decide.** Si `catalogo` devuelve un estado de
  resolución, la frontera se movió y está mal.
- **`POST /v1/catalogo/emparejar` no se toca.** Está publicado en `CONTRATO_API.md` §12 y lo usa
  el CLI de administración.
- El modelo de embeddings es **`multilingual-e5-large`, 1024 dimensiones**, porque la columna ya
  es `vector(1024)` con índice coseno y porque es el que usó el prototipo. Cambiarlo invalida
  los AUC ya medidos.
- Estados de resolución: usar los que ya existen en `modelos.base.EstadoResolucion`
  (`RESUELTO_AUTO`, `AMBIGUO`, `SIN_MATCH`, `HUECO_CATALOGO`). **No inventar `clarify`**:
  `AMBIGUO` es ese estado.
- El dinero sale en **pesos enteros**, no en centavos.
- Suite completa antes de cada commit: `cd tukit && uv run pytest`.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `servicios/catalogo/tukit_catalogo/recuperacion/embebedor.py` | Puerto `Embebedor` y sus adaptadores |
| `servicios/catalogo/tukit_catalogo/recuperacion/lexico.py` | Canal de trigramas, `variantes_lexicas`, stopwords |
| `servicios/catalogo/tukit_catalogo/recuperacion/denso.py` | Canal de coseno sobre concepto y producto |
| `servicios/catalogo/tukit_catalogo/recuperacion/grafo.py` | Grafo en memoria: sustituibilidad, sinonimia, prior por grado |
| `servicios/catalogo/tukit_catalogo/recuperacion/pool.py` | Une los tres canales y arma la respuesta |
| `servicios/catalogo/tukit_catalogo/vectorizar.py` | Trabajo por lotes, idempotente |
| `servicios/catalogo/tukit_catalogo/proponer_sustitutos.py` | Deriva las ~120 aristas candidatas para revisión |
| `servicios/inteligencia/tukit_inteligencia/resolucion/reordenador.py` | Puerto `Reordenador` y respaldo logístico |
| `servicios/inteligencia/tukit_inteligencia/resolucion/calibrador.py` | Regresión isotónica versionada |
| `servicios/inteligencia/tukit_inteligencia/resolucion/decision.py` | τ/δ y los cuatro estados |

---

### Task 1: ADR 0019 (bloqueante)

El ADR 0005 dice textualmente que el reordenador «degrada al orden de la fusión recíproca».
Este plan lo contradice con evidencia. El `ARQUITECTURA.md` §11 exige que el cambio entre al
lock **antes** de bajar a código.

**Files:**
- Create: `Arquitectura/adr/0019-respaldo-aprendido-en-vez-de-rrf.md` (fuera del submódulo)
- Modify: `Arquitectura/ARQUITECTURA.md` tabla §4

- [ ] **Step 1: Escribir el ADR** en formato Nygard, siguiendo la forma de
  `Arquitectura/adr/0005-*.md`. Contenido obligatorio:
  - **Contexto:** medición sobre 2.710 pares — `lex` 0,728 · `vec` 0,825 · **`rrf` 0,753** ·
    `rerank` 0,879. RRF queda por debajo de su propio canal denso.
  - **Decisión:** el respaldo del puerto `Reordenador` pasa a ser una regresión logística sobre
    `[lex, vec, grafo, prior_grado]` entrenada con el gold. RRF se conserva solo como criterio
    de truncamiento del pool, nunca como puntaje.
  - **Alternativa rechazada:** mantener RRF como respaldo (es degradar por debajo de no
    fusionar nada).
  - **Consecuencias:** el ADR 0005 queda enmendado en su cláusula de degradación; el resto
    (GPU serverless en Modal, adaptador local en CPU) sigue vigente.

- [ ] **Step 2: Actualizar la tabla del §4** agregando la fila del 0019 y anotando en la del
  0005 que su cláusula de respaldo está enmendada por el 0019.

- [ ] **Step 3: Commit**

```bash
cd /Users/mariapaula.rodriguez/Documents/university/TUKIT
git add Arquitectura/adr/0019-respaldo-aprendido-en-vez-de-rrf.md Arquitectura/ARQUITECTURA.md
git commit -m "docs(adr): 0019 respaldo aprendido en vez de RRF

RRF midio 0,753 contra 0,825 del canal denso solo. Degradar a RRF es degradar
por debajo de no fusionar nada. Enmienda la clausula de degradacion del 0005."
```

---

### Task 2: Columna de embedding en `concepto`

La decisión del pipeline es *renglón → concepto*, y sin vector de concepto el canal denso no
participa en la etapa donde el match falla.

**Files:**
- Modify: `servicios/catalogo/tukit_catalogo/modelos/catalogo.py`
- Create: `servicios/catalogo/migraciones/versions/<hash>_embedding_en_concepto.py`
- Test: `servicios/catalogo/tests/test_concepto_vectorizable.py`

- [ ] **Step 1: Escribir la prueba que falla**

```python
# servicios/catalogo/tests/test_concepto_vectorizable.py
"""El concepto tiene que poder llevar vector: la decision del pipeline es
renglon -> concepto, y sin vector ahi el canal denso no participa."""

from tukit_catalogo.modelos import Concepto


def test_el_concepto_declara_las_tres_columnas_de_embedding():
    columnas = {c.name for c in Concepto.__table__.columns}

    assert "embedding" in columnas
    assert "embedding_model" in columnas
    assert "texto_embedding" in columnas


def test_el_vector_del_concepto_tiene_las_mismas_1024_dimensiones_que_el_producto():
    from tukit_catalogo.modelos import ProductoCanonico

    del_concepto = Concepto.__table__.c.embedding.type
    del_producto = ProductoCanonico.__table__.c.embedding.type

    assert del_concepto.dim == del_producto.dim == 1024
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_concepto_vectorizable.py -v`
Expected: FAIL con `AssertionError` sobre `embedding`.

- [ ] **Step 3: Agregar las columnas**

En `servicios/catalogo/tukit_catalogo/modelos/catalogo.py`, dentro de `class Concepto`, copiando
la forma exacta que ya tiene `ProductoCanonico`:

```python
    # Mismo patron que producto_canonico: el vector vive en la fila, con indice
    # HNSW coseno. El concepto lo necesita porque la decision que el pipeline
    # toma es renglon -> concepto, no renglon -> producto.
    embedding: Mapped[list[float] | None] = mapped_column(Embedding, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    texto_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Generar la migración y **agregarle a mano el índice HNSW**, que el autogenerador no emite:

```bash
cd tukit
uv run alembic -c servicios/catalogo/alembic.ini revision --autogenerate -m "embedding en concepto"
```

En el archivo generado, dentro de `upgrade()` y después de los `add_column`:

```python
op.execute("CREATE INDEX ix_concepto_embedding_hnsw ON concepto USING hnsw (embedding vector_cosine_ops)")
```

Y en `downgrade()`, antes de los `drop_column`:

```python
    op.execute("DROP INDEX IF EXISTS ix_concepto_embedding_hnsw")
```

- [ ] **Step 4: Correr y verificar que pasa**

```bash
cd tukit
uv run pytest servicios/catalogo/tests/test_concepto_vectorizable.py -v
make bd-migrar
make bd-deriva
psql -d tukit_catalogo -c "\d concepto" | grep -i embedding
```
Expected: pruebas verdes, sin deriva, y `embedding | vector(1024)` con su índice HNSW.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/catalogo/tukit_catalogo/modelos/catalogo.py servicios/catalogo/migraciones/versions/ servicios/catalogo/tests/test_concepto_vectorizable.py
git commit -m "feat(catalogo): embedding e indice HNSW en concepto"
```

---

### Task 3: Puerto `Embebedor` y vectorización por lotes

**Files:**
- Create: `servicios/catalogo/tukit_catalogo/recuperacion/__init__.py`
- Create: `servicios/catalogo/tukit_catalogo/recuperacion/embebedor.py`
- Create: `servicios/catalogo/tukit_catalogo/vectorizar.py`
- Modify: `servicios/catalogo/pyproject.toml`
- Test: `servicios/catalogo/tests/test_embebedor.py`, `servicios/catalogo/tests/test_vectorizar.py`

**Interfaces:**
- Produces:
  - `class Embebedor(Protocol)` con `modelo: str`, `dimensiones: int`,
    `embeber(textos: Sequence[str]) -> list[list[float]]`.
  - `class EmbebedorDeterminista` — adaptador de pruebas, sin modelo, reproducible por hash.
  - `class EmbebedorE5` — adaptador real, carga perezosa.
  - `obtener_embebedor() -> Embebedor | None`, que devuelve `None` si no hay ninguno
    configurado y lo anuncia.
  - `texto_de_concepto(fila) -> str`, `texto_de_producto(fila) -> str`.
  - `vectorizar(...)` idempotente.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/catalogo/tests/test_embebedor.py
"""El puerto, su adaptador de pruebas y la guardia de dimensiones."""

import pytest

from tukit_catalogo.recuperacion.embebedor import (
    EmbebedorDeterminista,
    texto_de_concepto,
    texto_de_producto,
    verificar_dimensiones,
)


def test_el_adaptador_determinista_devuelve_siempre_el_mismo_vector():
    uno = EmbebedorDeterminista()
    otro = EmbebedorDeterminista()

    assert uno.embeber(["cuaderno"]) == otro.embeber(["cuaderno"])


def test_el_vector_tiene_las_dimensiones_declaradas_y_esta_normalizado():
    embebedor = EmbebedorDeterminista()

    vector = embebedor.embeber(["cuaderno cuadriculado"])[0]

    assert len(vector) == embebedor.dimensiones == 1024
    norma = sum(v * v for v in vector) ** 0.5
    assert abs(norma - 1.0) < 1e-6


def test_textos_distintos_dan_vectores_distintos():
    embebedor = EmbebedorDeterminista()

    assert embebedor.embeber(["cuaderno"]) != embebedor.embeber(["tijera"])


def test_el_texto_del_concepto_junta_nombre_sinonimos_y_discriminantes():
    texto = texto_de_concepto(
        {
            "nombre_canonico": "cuaderno",
            "sinonimos": ["libreta", "cuadernillo"],
            "atributos_discriminantes": ["tipo", "tamano"],
        }
    )

    assert "cuaderno" in texto
    assert "libreta" in texto
    assert "tipo" in texto


def test_el_texto_del_producto_junta_nombre_marca_y_categoria():
    texto = texto_de_producto(
        {"nombre": "Cuaderno Cosido 100 Hojas", "marca": "Norma", "ruta_categoria": "Cuadernos"}
    )

    assert "Cuaderno Cosido 100 Hojas" in texto
    assert "Norma" in texto


def test_un_embebedor_de_otra_dimension_falla_ruidosamente():
    """Escribir 768 en una columna vector(1024) falla tarde y feo. Falla aqui."""

    class DeOtraDimension:
        modelo = "falso-768"
        dimensiones = 768

        def embeber(self, textos):
            return [[0.0] * 768 for _ in textos]

    with pytest.raises(ValueError, match="1024"):
        verificar_dimensiones(DeOtraDimension(), esperadas=1024)
```

```python
# servicios/catalogo/tests/test_vectorizar.py
"""Vectorizar es un trabajo por lotes y tiene que poder correrse dos veces."""

from tukit_catalogo.recuperacion.embebedor import EmbebedorDeterminista
from tukit_catalogo.vectorizar import filas_por_vectorizar


def test_solo_se_vectoriza_lo_que_no_tiene_vector():
    filas = [
        {"id": "1", "texto": "cuaderno", "texto_embedding": None, "embedding_model": None},
        {"id": "2", "texto": "tijera", "texto_embedding": "tijera", "embedding_model": "e5"},
    ]

    pendientes = filas_por_vectorizar(filas, modelo="e5")

    assert [f["id"] for f in pendientes] == ["1"]


def test_si_el_texto_cambio_se_vuelve_a_vectorizar():
    filas = [{"id": "1", "texto": "cuaderno grande", "texto_embedding": "cuaderno", "embedding_model": "e5"}]

    assert len(filas_por_vectorizar(filas, modelo="e5")) == 1


def test_si_el_modelo_cambio_se_vuelve_a_vectorizar_todo():
    filas = [{"id": "1", "texto": "cuaderno", "texto_embedding": "cuaderno", "embedding_model": "e5-viejo"}]

    assert len(filas_por_vectorizar(filas, modelo="e5-nuevo")) == 1


def test_correrlo_dos_veces_no_reescribe_nada():
    filas = [{"id": "1", "texto": "cuaderno", "texto_embedding": None, "embedding_model": None}]
    embebedor = EmbebedorDeterminista()

    pendientes = filas_por_vectorizar(filas, modelo=embebedor.modelo)
    for fila in pendientes:
        fila["texto_embedding"] = fila["texto"]
        fila["embedding_model"] = embebedor.modelo

    assert filas_por_vectorizar(filas, modelo=embebedor.modelo) == []
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_embebedor.py servicios/catalogo/tests/test_vectorizar.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tukit_catalogo.recuperacion'`

- [ ] **Step 3: Implementar**

En `servicios/catalogo/pyproject.toml`, agregar un extra opcional para que la imagen base no
cargue el modelo si se usa el adaptador remoto:

```toml
[project.optional-dependencies]
embeddings = ["sentence-transformers>=3.0"]
```

Crear `servicios/catalogo/tukit_catalogo/recuperacion/__init__.py`:

```python
"""Recuperacion de candidatos: lexico, denso y grafo.

Este paquete RECUPERA y no decide. Devolver un estado de resolucion desde aqui
seria mover la frontera que el ADR 0012 puso entre exhaustividad (catalogo) y
precision (inteligencia).
"""
```

Crear `servicios/catalogo/tukit_catalogo/recuperacion/embebedor.py`:

```python
"""El puerto de embeddings y sus adaptadores.

Es un puerto y no una llamada directa por la misma razon del ADR 0005 con el
reordenador: el modelo pesa ~2 GB, se necesita EN CADA CONSULTA (el renglon
entrante tambien hay que embeberlo, no solo el catalogo) y su perfil de recurso
no se parece al del resto del servicio.

El modelo es multilingual-e5-large y eso NO es una eleccion libre: la columna ya
es `vector(1024)` con indice coseno, que es exactamente e5-large, y es el que uso
el prototipo. Cambiarlo obliga a migrar la columna, reconstruir el HNSW y
re-medir el gold desde cero.
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
from collections.abc import Sequence
from typing import Any, Protocol

DIMENSIONES = 1024
MODELO_CANONICO = "intfloat/multilingual-e5-large"


class Embebedor(Protocol):
    modelo: str
    dimensiones: int

    def embeber(self, textos: Sequence[str]) -> list[list[float]]: ...


def verificar_dimensiones(embebedor: Any, *, esperadas: int = DIMENSIONES) -> None:
    """Falla al arrancar y no al escribir.

    Un embebedor de 768 contra una columna de 1024 falla en el `INSERT`, con un
    mensaje de Postgres sobre tipos y a mitad de un lote. Aqui falla antes, con
    los dos numeros en el mensaje.
    """
    if embebedor.dimensiones != esperadas:
        raise ValueError(
            f"El embebedor '{embebedor.modelo}' produce {embebedor.dimensiones} dimensiones "
            f"y la columna espera {esperadas}."
        )


class EmbebedorDeterminista:
    """Vectores reproducibles sin modelo, para pruebas y para desarrollo sin red.

    No pretende tener semantica: pretende ser estable. Sirve para probar el
    cableado (idempotencia, dimensiones, escritura) sin bajar dos gigas.
    """

    modelo = "determinista-1024"
    dimensiones = DIMENSIONES

    def embeber(self, textos: Sequence[str]) -> list[list[float]]:
        vectores = []
        for texto in textos:
            semilla = hashlib.sha256(texto.encode("utf-8")).digest()
            crudo = [
                struct.unpack("<f", hashlib.sha256(semilla + i.to_bytes(2, "little")).digest()[:4])[0]
                for i in range(self.dimensiones)
            ]
            # Se normaliza porque el indice es coseno: un vector sin normalizar
            # mide distinto segun su magnitud y no segun su direccion.
            norma = math.sqrt(sum(v * v for v in crudo)) or 1.0
            vectores.append([v / norma for v in crudo])
        return vectores


class EmbebedorE5:
    """El real. Carga perezosa: el modelo no entra a memoria hasta el primer uso."""

    modelo = MODELO_CANONICO
    dimensiones = DIMENSIONES

    def __init__(self) -> None:
        self._modelo = None

    def _cargar(self):
        if self._modelo is None:
            from sentence_transformers import SentenceTransformer

            self._modelo = SentenceTransformer(MODELO_CANONICO)
        return self._modelo

    def embeber(self, textos: Sequence[str]) -> list[list[float]]:
        # e5 exige el prefijo: fue entrenado con "query:" y "passage:" y sin el
        # los vectores quedan en otra region del espacio.
        con_prefijo = [f"query: {t}" for t in textos]
        return self._cargar().encode(con_prefijo, normalize_embeddings=True).tolist()


def obtener_embebedor() -> Embebedor | None:
    """El configurado, o None. Nunca revienta por no tener modelo.

    Sin embebedor el canal denso se apaga y la recuperacion sigue con lexico y
    grafo. Degradar, nunca tumbar.
    """
    cual = os.getenv("TUKIT_EMBEBEDOR", "").strip().lower()
    if cual == "determinista":
        return EmbebedorDeterminista()
    if cual in {"e5", "local"}:
        return EmbebedorE5()
    return None


def texto_de_concepto(fila: dict[str, Any]) -> str:
    """Lo que se embebe de un concepto, y queda escrito en `texto_embedding`.

    Se consideró enriquecerlo con renglones reales de las listas oficiales y se
    descarto: meteria la distribucion de la evaluacion dentro del indice y
    contaminaria la medicion.
    """
    partes = [str(fila.get("nombre_canonico") or "")]
    partes.extend(str(s) for s in (fila.get("sinonimos") or []))
    partes.extend(str(a) for a in (fila.get("atributos_discriminantes") or []))
    return ", ".join(p for p in partes if p)


def texto_de_producto(fila: dict[str, Any]) -> str:
    partes = [
        str(fila.get("nombre") or ""),
        str(fila.get("marca") or ""),
        str(fila.get("ruta_categoria") or ""),
    ]
    return ", ".join(p for p in partes if p)
```

Crear `servicios/catalogo/tukit_catalogo/vectorizar.py`:

```python
"""Trabajo por lotes: escribe los vectores del catalogo. Idempotente.

    TUKIT_EMBEBEDOR=e5 python -m tukit_catalogo.vectorizar
    TUKIT_EMBEBEDOR=determinista python -m tukit_catalogo.vectorizar --probar

Idempotente de verdad y no "casi": se recalcula solo si el texto cambio o si el
modelo cambio. `texto_embedding` existe justamente para poder responder esa
pregunta sin volver a embeber.
"""

from __future__ import annotations

from typing import Any


def filas_por_vectorizar(filas: list[dict[str, Any]], *, modelo: str) -> list[dict[str, Any]]:
    """Las que no tienen vector, o cuyo texto o modelo cambiaron."""
    return [
        fila
        for fila in filas
        if fila.get("texto_embedding") != fila.get("texto") or fila.get("embedding_model") != modelo
    ]
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_embebedor.py servicios/catalogo/tests/test_vectorizar.py -v`
Expected: PASS, 10 pruebas.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/catalogo/tukit_catalogo/recuperacion/ servicios/catalogo/tukit_catalogo/vectorizar.py servicios/catalogo/pyproject.toml servicios/catalogo/tests/test_embebedor.py servicios/catalogo/tests/test_vectorizar.py
git commit -m "feat(catalogo): puerto Embebedor y vectorizacion idempotente"
```

---

### Task 4: Canal léxico

Se porta desde `tukit-mvp-pipeline/pipeline/stage2_busqueda.py`, con las dos correcciones que
ese módulo ya pagó y documentó.

**Files:**
- Create: `servicios/catalogo/tukit_catalogo/recuperacion/lexico.py`
- Test: `servicios/catalogo/tests/test_canal_lexico.py`

**Interfaces:**
- Produces: `STOPWORDS_DOMINIO: frozenset[str]`, `SINONIMOS: dict[str, frozenset[str]]`,
  `variantes_lexicas(consulta: str) -> list[str]`, `consulta_para_trigramas(texto: str) -> str`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/catalogo/tests/test_canal_lexico.py
"""Las dos correcciones que el prototipo pago caro, como pruebas."""

from tukit_catalogo.recuperacion.lexico import (
    STOPWORDS_DOMINIO,
    consulta_para_trigramas,
    variantes_lexicas,
)


def test_cada_variante_es_una_frase_completa_y_no_una_palabra_suelta():
    """Una palabra suelta satura word_similarity en 1,0 contra cualquier
    producto que la contenga, y deja de discriminar."""
    variantes = variantes_lexicas("cuaderno cuadriculado 100 hojas")

    assert all(len(v.split()) > 1 for v in variantes)


def test_se_sustituye_un_sinonimo_por_variante_y_no_todos_a_la_vez():
    variantes = variantes_lexicas("esfero negro")

    assert "esfero negro" in variantes
    assert any("lapicero negro" == v for v in variantes)
    # Nunca una frase que apile todos los sinonimos.
    assert not any(v.count("negro") > 1 for v in variantes)


def test_el_sinonimo_se_sustituye_en_su_posicion_dejando_el_resto_igual():
    variantes = variantes_lexicas("caja de esfero x 12")

    assert any(v.startswith("caja de lapicero") for v in variantes)


def test_las_palabras_de_envase_salen_solo_del_canal_lexico():
    """El caso real: "caja de Plastilina Grande" empataba con "Caja organizador
    acrilico grande" por compartir caja/grande."""
    assert "caja" in STOPWORDS_DOMINIO
    assert "paquete" in STOPWORDS_DOMINIO

    assert consulta_para_trigramas("caja de plastilina") == "plastilina"


def test_grande_y_mediano_NO_son_stopwords():
    """Para cuadernos y mochilas el catalogo si diferencia tallas reales."""
    assert "grande" not in STOPWORDS_DOMINIO
    assert "mediano" not in STOPWORDS_DOMINIO


def test_una_consulta_que_solo_tiene_stopwords_no_queda_vacia():
    """Vaciarla haria que el canal lexico empate con todo el catalogo."""
    assert consulta_para_trigramas("caja paquete") != ""
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_canal_lexico.py -v`
Expected: FAIL con `ModuleNotFoundError: ...recuperacion.lexico`

- [ ] **Step 3: Implementar**

```python
# servicios/catalogo/tukit_catalogo/recuperacion/lexico.py
"""Canal de trigramas sobre el indice GIN que ya existe.

Portado de `tukit-mvp-pipeline/pipeline/stage2_busqueda.py`, con las dos
correcciones que ese modulo documenta y que costaron una validacion entera:

1. Una frase COMPLETA por sustitucion de sinonimo. Ni palabras sueltas (una
   palabra distintiva satura `word_similarity` en 1,000 contra cualquier producto
   que la contenga y deja de discriminar) ni todos los sinonimos apilados en una
   frase que no se parece a ningun nombre real.
2. Stopwords de envase SOLO en este canal. El canal denso recibe la frase
   completa sin filtrar, porque e5 se entreno sobre oraciones naturales.
"""

from __future__ import annotations

# Envase, cantidad y presentacion: aparecen en casi cualquier producto y no
# distinguen nada. NO incluir "grande"/"mediano"/"pequeno": para cuadernos y
# mochilas el catalogo si diferencia tallas reales con el mismo conteo de hojas.
STOPWORDS_DOMINIO = frozenset(
    {
        "caja",
        "cajas",
        "paquete",
        "paquetes",
        "bolsa",
        "bolsas",
        "set",
        "kit",
        "unidad",
        "unidades",
        "und",
        "pack",
        "x",
        "de",
        "del",
        "la",
        "el",
        "los",
        "las",
        "con",
        "para",
        "por",
    }
)

SINONIMOS: dict[str, frozenset[str]] = {
    "esfero": frozenset({"esfero", "esferos", "boligrafo", "bolígrafo", "lapicero", "lapiceros", "birome"}),
    "lapiz": frozenset({"lapiz", "lápiz", "lapices", "lápices", "portaminas"}),
    "marcador": frozenset({"marcador", "marcadores", "plumon", "plumón", "plumones", "rotulador"}),
    "cuaderno": frozenset({"cuaderno", "cuadernos", "cuadernillo", "libreta", "libretas"}),
    "pegamento": frozenset({"pegamento", "pegante", "pegantes", "silicona", "colbon", "colbón"}),
    "sacapuntas": frozenset({"sacapuntas", "sacapunta", "tajalapiz", "tajalápiz", "tajalapices"}),
    "borrador": frozenset({"borrador", "borradores", "goma de borrar"}),
    "cartuchera": frozenset({"cartuchera", "cartucheras", "estuche", "estuches"}),
    "mochila": frozenset({"mochila", "morral", "morrales", "maleta", "maletas", "maletin", "maletín"}),
    "octavo": frozenset({"octavo", "octavos", "1/8"}),
}

# "goma" queda fuera de `pegamento` a proposito: en `SINONIMOS` del prototipo
# entra porque ahi se sustituye la FRASE "goma de borrar", pero suelta es
# ambigua entre pegamento y borrador.

_VARIANTE_A_CANONICO: dict[str, str] = {
    variante: canonico for canonico, variantes in SINONIMOS.items() for variante in variantes
}


def consulta_para_trigramas(texto: str) -> str:
    """Quita las palabras de envase. Si no queda nada, devuelve el original.

    Vaciar la consulta seria peor que no filtrar: `word_similarity` contra una
    cadena vacia empata con todo el catalogo.
    """
    palabras = [p for p in texto.lower().split() if p not in STOPWORDS_DOMINIO]
    return " ".join(palabras) if palabras else texto.lower()


def variantes_lexicas(consulta: str) -> list[str]:
    """Una frase completa por sustitucion, con el resto de la frase intacto."""
    palabras = consulta.lower().split()
    variantes = [consulta.lower()]

    for posicion, palabra in enumerate(palabras):
        canonico = _VARIANTE_A_CANONICO.get(palabra)
        if canonico is None:
            continue
        for alternativa in sorted(SINONIMOS[canonico]):
            if alternativa == palabra:
                continue
            copia = list(palabras)
            copia[posicion] = alternativa
            frase = " ".join(copia)
            if frase not in variantes:
                variantes.append(frase)
    return variantes
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_canal_lexico.py -v`
Expected: PASS, 6 pruebas.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/catalogo/tukit_catalogo/recuperacion/lexico.py servicios/catalogo/tests/test_canal_lexico.py
git commit -m "feat(catalogo): canal lexico con variantes por sinonimo y stopwords de envase"
```

---

### Task 5: Grafo de conceptos y propuesta de sustitutos

**Files:**
- Create: `servicios/catalogo/tukit_catalogo/recuperacion/grafo.py`
- Create: `servicios/catalogo/tukit_catalogo/proponer_sustitutos.py`
- Test: `servicios/catalogo/tests/test_grafo_conceptos.py`, `servicios/catalogo/tests/test_proponer_sustitutos.py`

**Interfaces:**
- Produces:
  - `class GrafoConceptos` con `construir(conceptos, aristas, renglones)`,
    `vecinos(concepto_id) -> list[tuple[str, float]]`, `prior(concepto_id, grado) -> float`.
  - `proponer_aristas(conceptos) -> list[dict]` con `origen`, `sustituto`, `motivo`.
  - `CATEGORIAS_EXCLUIDAS`, `MAX_CONCEPTOS_POR_CATEGORIA = 6`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/catalogo/tests/test_grafo_conceptos.py
"""El grafo hace dos trabajos distintos y no hay que confundirlos."""

from tukit_catalogo.recuperacion.grafo import GrafoConceptos


def _grafo() -> GrafoConceptos:
    conceptos = [
        {"id": "c1", "codigo": "C001", "nombre_canonico": "cuaderno"},
        {"id": "c2", "codigo": "C002", "nombre_canonico": "block"},
        {"id": "c3", "codigo": "C003", "nombre_canonico": "biblia"},
    ]
    aristas = [{"origen": "c2", "sustituto": "c1", "grado": 0.6}]
    renglones = [
        {"concepto_id": "c1", "grado": "Parvulos"},
        {"concepto_id": "c1", "grado": "Parvulos"},
        {"concepto_id": "c3", "grado": "Once"},
    ]
    return GrafoConceptos.construir(conceptos, aristas, renglones)


def test_la_sustituibilidad_es_dirigida():
    """Que un block de dibujo sirva de origami no implica lo contrario."""
    grafo = _grafo()

    assert ("c1", 0.6) in grafo.vecinos("c2")
    assert grafo.vecinos("c1") == []


def test_el_prior_depende_del_grado():
    """Un block en Parvulos no es un block en Once."""
    grafo = _grafo()

    assert grafo.prior("c1", "Parvulos") > grafo.prior("c1", "Once")


def test_un_renglon_sin_grado_recibe_el_marginal_y_no_cero():
    """Castigar la ausencia de grado convertiria un dato faltante en evidencia
    en contra."""
    grafo = _grafo()

    assert grafo.prior("c1", None) > 0.0


def test_un_concepto_nunca_visto_en_un_grado_no_da_probabilidad_cero():
    """Suavizado de Laplace: cero seria una afirmacion que 175 listas no sostienen."""
    grafo = _grafo()

    assert grafo.prior("c2", "Parvulos") > 0.0


def test_el_grafo_se_construye_una_vez_y_se_reutiliza():
    """El perfilado atribuyo el 95,3 % de la latencia a reconstruirlo por item."""
    grafo = _grafo()

    assert grafo.vecinos("c2") is grafo.vecinos("c2")
```

```python
# servicios/catalogo/tests/test_proponer_sustitutos.py
"""Las aristas se PROPONEN automaticamente y las confirma una persona."""

from tukit_catalogo.proponer_sustitutos import proponer_aristas


def test_los_conceptos_de_una_misma_categoria_se_proponen_como_pares_dirigidos():
    conceptos = [
        {"id": "c1", "nombre_canonico": "colbon", "categoria": "Colbón / Pegante líquido / Pegastic"},
        {"id": "c2", "nombre_canonico": "pegastic", "categoria": "Colbón / Pegante líquido / Pegastic"},
    ]

    propuestas = proponer_aristas(conceptos)

    assert len(propuestas) == 2  # dirigida: c1->c2 y c2->c1
    assert all(p["motivo"] for p in propuestas)


def test_el_cajon_de_sastre_no_propone_nada():
    """ "Otros / Varios" junta 12 conceptos que no se parecen en nada."""
    conceptos = [
        {"id": f"c{i}", "nombre_canonico": f"cosa{i}", "categoria": "Otros / Varios"} for i in range(5)
    ]

    assert proponer_aristas(conceptos) == []


def test_una_categoria_con_demasiados_conceptos_tampoco_propone():
    conceptos = [
        {"id": f"c{i}", "nombre_canonico": f"cosa{i}", "categoria": "Lana, algodón, aserrín"}
        for i in range(11)
    ]

    assert proponer_aristas(conceptos) == []


def test_una_categoria_de_un_solo_concepto_no_propone_nada():
    conceptos = [{"id": "c1", "nombre_canonico": "cartulina", "categoria": "Cartulina"}]

    assert proponer_aristas(conceptos) == []


def test_el_motivo_nombra_la_categoria_para_que_sea_revisable():
    conceptos = [
        {"id": "c1", "nombre_canonico": "compas", "categoria": "Compás / Estuche de geometría"},
        {"id": "c2", "nombre_canonico": "estuche", "categoria": "Compás / Estuche de geometría"},
    ]

    assert "Compás / Estuche de geometría" in proponer_aristas(conceptos)[0]["motivo"]
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_grafo_conceptos.py servicios/catalogo/tests/test_proponer_sustitutos.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
# servicios/catalogo/tukit_catalogo/recuperacion/grafo.py
"""El grafo de conceptos, en memoria y construido una sola vez.

En memoria y no en una base de grafos porque el ADR 0006 elimino Neo4j al medir
que el grafo cabia: son 100 nodos. Y construido una vez porque el
`PERFILADO_PIPELINE.md` atribuyo el 95,3 % de la latencia del pipeline a
reconstruirlo por item: 1.673 ms construir contra 0,137 ms consultar, y cachearlo
bajo 20 items de 35,1 s a 1,7 s.

Hace DOS trabajos que no se deben confundir:

1. Expansion de recall, por sustituibilidad curada y dirigida.
2. Prior condicionado al grado, por co-ocurrencia en las listas oficiales.

Y una trampa que el codigo no puede cruzar: que dos conceptos aparezcan JUNTOS en
una lista es evidencia de que son COMPLEMENTARIOS, no sustitutos. Si el colegio
pide cuaderno y block, se necesitan los dos. Por eso la co-ocurrencia alimenta
solo el prior y nunca las aristas de sustitucion.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class GrafoConceptos:
    def __init__(
        self,
        vecinos: dict[str, list[tuple[str, float]]],
        conteo: dict[tuple[str, str], int],
        por_grado: dict[str, int],
        marginal: dict[str, float],
        n_conceptos: int,
    ) -> None:
        self._vecinos = vecinos
        self._conteo = conteo
        self._por_grado = por_grado
        self._marginal = marginal
        self._n_conceptos = max(1, n_conceptos)

    @classmethod
    def construir(
        cls,
        conceptos: list[dict[str, Any]],
        aristas: list[dict[str, Any]],
        renglones: list[dict[str, Any]],
    ) -> GrafoConceptos:
        vecinos: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for arista in aristas:
            vecinos[str(arista["origen"])].append((str(arista["sustituto"]), float(arista["grado"])))
        for origen in vecinos:
            # Mejor sustituto primero: es el orden en que se ofrecen.
            vecinos[origen].sort(key=lambda par: -par[1])

        conteo: dict[tuple[str, str], int] = defaultdict(int)
        por_grado: dict[str, int] = defaultdict(int)
        total_por_concepto: dict[str, int] = defaultdict(int)
        total = 0
        for renglon in renglones:
            concepto_id = renglon.get("concepto_id")
            if not concepto_id:
                continue
            concepto_id = str(concepto_id)
            grado = str(renglon.get("grado") or "")
            if grado:
                conteo[(concepto_id, grado)] += 1
                por_grado[grado] += 1
            total_por_concepto[concepto_id] += 1
            total += 1

        marginal = {c: n / total for c, n in total_por_concepto.items()} if total else {}

        return cls(dict(vecinos), dict(conteo), dict(por_grado), marginal, len(conceptos))

    def vecinos(self, concepto_id: str) -> list[tuple[str, float]]:
        return self._vecinos.get(str(concepto_id), [])

    def prior(self, concepto_id: str, grado: str | None) -> float:
        """P(concepto | grado) con suavizado de Laplace.

        Sin grado se devuelve el marginal, no cero: un dato que falta no es
        evidencia en contra. Y con suavizado porque un concepto que no aparecio
        en un grado dentro de 175 listas es raro, no imposible.
        """
        concepto_id = str(concepto_id)
        if not grado:
            return self._marginal.get(concepto_id, 1.0 / self._n_conceptos)
        observado = self._conteo.get((concepto_id, grado), 0)
        del_grado = self._por_grado.get(grado, 0)
        return (observado + 1) / (del_grado + self._n_conceptos)
```

```python
# servicios/catalogo/tukit_catalogo/proponer_sustitutos.py
"""Propone aristas de sustituibilidad para que una persona las confirme.

La tabla exige `motivo` y `curado_por` no nulos a proposito: una arista que no
dice por que existe ni quien la puso no se puede revisar, y poder revisarla es
lo unico que la separa de un coseno. Eso obliga a que una persona CONFIRME cada
arista, no a que la REDACTE.

La curaduria ya ocurrio y esta en un sitio inesperado: los nombres de las 49
categorias son grupos de sustitucion escritos con alternativas separadas por
barra ("Colbón / Pegante líquido / Pegastic"). Alguien ya decidio que se parece
a que cuando las nombro.

    python -m tukit_catalogo.proponer_sustitutos           # imprime las propuestas
    python -m tukit_catalogo.proponer_sustitutos --escribir  # las deja en la cola
"""

from __future__ import annotations

import itertools
from typing import Any

# Cajones de sastre: juntan cosas que no se parecen, asi que sus pares son ruido.
CATEGORIAS_EXCLUIDAS = frozenset({"Otros / Varios"})

# Por encima de esto la categoria dejo de nombrar alternativas y paso a ser una
# bolsa. Medido: con 6 se conservan 120 pares utiles de los 362 totales.
MAX_CONCEPTOS_POR_CATEGORIA = 6


def proponer_aristas(conceptos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pares dirigidos entre conceptos que comparten una categoria util."""
    por_categoria: dict[str, list[dict[str, Any]]] = {}
    for concepto in conceptos:
        categoria = str(concepto.get("categoria") or "")
        if not categoria or categoria in CATEGORIAS_EXCLUIDAS:
            continue
        por_categoria.setdefault(categoria, []).append(concepto)

    propuestas: list[dict[str, Any]] = []
    for categoria, miembros in sorted(por_categoria.items()):
        if not 2 <= len(miembros) <= MAX_CONCEPTOS_POR_CATEGORIA:
            continue
        for origen, sustituto in itertools.permutations(miembros, 2):
            propuestas.append(
                {
                    "origen": origen["id"],
                    "sustituto": sustituto["id"],
                    "grado": 0.5,  # valor de arranque; la revision lo ajusta
                    "motivo": (
                        f"Comparten la categoria '{categoria}', que enumera alternativas. "
                        f"Propuesta automatica: confirmar que {sustituto['nombre_canonico']} "
                        f"sirve cuando se pide {origen['nombre_canonico']}."
                    ),
                }
            )
    return propuestas
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_grafo_conceptos.py servicios/catalogo/tests/test_proponer_sustitutos.py -v`
Expected: PASS, 10 pruebas.

- [ ] **Step 5: Verificar el volumen contra la base real**

```bash
cd tukit
uv run python -m tukit_catalogo.proponer_sustitutos | tail -5
```
Expected: alrededor de **120 propuestas**. Si salen 362, el filtro de cajones de sastre no se
está aplicando.

- [ ] **Step 6: Commit**

```bash
cd tukit
git add servicios/catalogo/tukit_catalogo/recuperacion/grafo.py servicios/catalogo/tukit_catalogo/proponer_sustitutos.py servicios/catalogo/tests/test_grafo_conceptos.py servicios/catalogo/tests/test_proponer_sustitutos.py
git commit -m "feat(catalogo): grafo de conceptos en memoria y propuesta de sustitutos

Las aristas se derivan de los nombres de categoria, que ya son grupos de
sustitucion curados. La persona confirma en vez de redactar. La co-ocurrencia
alimenta solo el prior de grado: aparecer juntos es ser complementarios, no
sustitutos."
```

---

### Task 6: Endpoint `POST /v1/catalogo/recuperar`

**Files:**
- Create: `servicios/catalogo/tukit_catalogo/recuperacion/pool.py`
- Modify: `servicios/catalogo/tukit_catalogo/api.py`
- Test: `servicios/catalogo/tests/test_recuperar.py`

**Interfaces:**
- Produces, dos funciones con responsabilidades separadas a propósito:
  - `armar_pool_desde(texto: str, candidatos_por_canal: dict[str, list[dict]]) -> list[dict]`
    — **pura**, sin base de datos. Es la que une los canales y la que se prueba.
  - `armar_pool(texto: str, grado: str | None, conceptos, productos, grafo, embebedor, k=20) -> dict`
    — la que consulta y llama a la anterior. Devuelve `texto`, `texto_corregido`,
    `atributos_impuestos` y `candidatos`.

  Cada candidato lleva `producto_id`, `sku`, `nombre`, `nivel`, `concepto_codigo`,
  `personaje`, `marca`, `oferta_id`, `tienda_id`, `tienda_slug`, `precio_cop`, `unidad_base`,
  `unidades_por_empaque`, `cumple`, `canales` y `via`.

  **`oferta_id`, `tienda_id`, `tienda_slug` y `precio_cop` son una fila por OFERTA**, no por
  producto: un producto con tres ofertas produce tres candidatos. Es requisito del plan del
  OE4, que decide en qué tienda comprar, y por eso aquí no se aplica `min(precio)`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/catalogo/tests/test_recuperar.py
"""catalogo RECUPERA y no decide. Esa es la prueba de diseno."""

import inspect

from tukit_catalogo.recuperacion import pool


def test_la_respuesta_no_trae_estado_de_resolucion():
    """Si catalogo devuelve un veredicto, la frontera del ADR 0012 se movio."""
    fuente = inspect.getsource(pool)

    for prohibido in ("RESUELTO_AUTO", "AMBIGUO", "SIN_MATCH", "HUECO_CATALOGO"):
        assert prohibido not in fuente


def test_cada_candidato_declara_por_que_canal_entro():
    resultado = pool.armar_pool_desde(
        texto="cuaderno",
        candidatos_por_canal={
            "lex": [{"producto_id": "p1", "puntaje": 0.8}],
            "vec": [{"producto_id": "p1", "puntaje": 0.9}, {"producto_id": "p2", "puntaje": 0.7}],
            "grafo": [{"producto_id": "p3", "puntaje": 0.6}],
        },
    )

    por_id = {c["producto_id"]: c for c in resultado}
    assert set(por_id["p1"]["via"]) == {"lex", "vec"}
    assert por_id["p2"]["via"] == ["vec"]
    assert por_id["p3"]["via"] == ["grafo"]


def test_el_pool_es_la_union_y_no_pierde_a_nadie():
    resultado = pool.armar_pool_desde(
        texto="x",
        candidatos_por_canal={
            "lex": [{"producto_id": "p1", "puntaje": 0.8}],
            "vec": [{"producto_id": "p2", "puntaje": 0.9}],
            "grafo": [{"producto_id": "p3", "puntaje": 0.6}],
        },
    )

    assert {c["producto_id"] for c in resultado} == {"p1", "p2", "p3"}


def test_un_candidato_que_no_entro_por_un_canal_tiene_ese_canal_en_cero():
    resultado = pool.armar_pool_desde(
        texto="x",
        candidatos_por_canal={"lex": [{"producto_id": "p1", "puntaje": 0.8}], "vec": [], "grafo": []},
    )

    assert resultado[0]["canales"]["vec"] == 0.0
    assert resultado[0]["canales"]["lex"] == 0.8


def test_rrf_no_aparece_como_puntaje_de_ningun_candidato():
    """Midio 0,753 contra 0,825 del canal denso solo. No puntua."""
    resultado = pool.armar_pool_desde(
        texto="x",
        candidatos_por_canal={"lex": [{"producto_id": "p1", "puntaje": 0.8}], "vec": [], "grafo": []},
    )

    assert "rrf" not in resultado[0]["canales"]
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_recuperar.py -v`
Expected: FAIL con `ModuleNotFoundError: ...recuperacion.pool`

- [ ] **Step 3: Implementar el pool y exponer el endpoint**

```python
# servicios/catalogo/tukit_catalogo/recuperacion/pool.py
"""Une los tres canales en un pool. Sin veredicto.

Union y no fusion de rangos. RRF quedaria disponible solo para truncar si la
union se pasa de un tope, y NUNCA para puntuar: midio AUC 0,753 contra 0,825 del
canal denso solo, asi que fusionar con el es peor que no fusionar.

Aqui no se decide nada. Quien decide es `inteligencia`, con el reordenador y
tau/delta. Si este modulo empezara a devolver estados de resolucion, habria
movido la frontera que el ADR 0012 puso entre exhaustividad y precision, y hay
una prueba que lee este archivo para impedirlo.
"""

from __future__ import annotations

from typing import Any

CANALES = ("lex", "vec", "grafo")


def armar_pool_desde(
    texto: str, candidatos_por_canal: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """La union, con el puntaje de cada canal y la lista de por cuales entro."""
    acumulado: dict[str, dict[str, Any]] = {}

    for canal in CANALES:
        for candidato in candidatos_por_canal.get(canal, []):
            clave = str(candidato["producto_id"])
            entrada = acumulado.setdefault(
                clave,
                {
                    "producto_id": clave,
                    "canales": dict.fromkeys(CANALES, 0.0),
                    "via": [],
                    **{k: v for k, v in candidato.items() if k not in {"producto_id", "puntaje"}},
                },
            )
            entrada["canales"][canal] = float(candidato.get("puntaje") or 0.0)
            if canal not in entrada["via"]:
                entrada["via"].append(canal)

    # Orden estable: el mejor puntaje de cualquier canal primero, y el
    # identificador para desempatar, para que la respuesta no dependa del orden
    # en que la base devolvio las filas.
    return sorted(
        acumulado.values(),
        key=lambda c: (-max(c["canales"].values()), c["producto_id"]),
    )
```

En `servicios/catalogo/tukit_catalogo/api.py`, junto a `emparejar_renglones`:

```python
@app.post(
    "/v1/catalogo/recuperar",
    tags=["catalogo"],
    summary="Pool de candidatos con puntajes por canal. No decide nada.",
)
async def recuperar_candidatos(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Recupera amplio y deja el veredicto a quien corresponde.

    `emparejar` devuelve una decision y se conserva porque el contrato ya la
    publica; esta ruta devuelve el pool con los puntajes crudos de cada canal,
    que es lo que `inteligencia` necesita para reordenar y decidir con tau/delta.
    """
```

Y el cuerpo, que reusa `cargar_indice` de `consulta.py` para no duplicar la consulta:

```python
    from .consulta import cargar_indice
    from .recuperacion.embebedor import obtener_embebedor
    from .recuperacion.pool import armar_pool

    renglones = cuerpo.get("renglones") or []
    if not renglones:
        raise ErrorDominio("renglones_vacios", "Pasa al menos un renglon.", 400)

    conceptos, productos = await cargar_indice()
    grafo = app.state.grafo_conceptos
    embebedor = obtener_embebedor()
    k = int(cuerpo.get("k") or 20)

    return {
        "resultados": [
            armar_pool(
                texto=str(renglon.get("texto") or ""),
                grado=renglon.get("grado"),
                conceptos=conceptos,
                productos=productos,
                grafo=grafo,
                embebedor=embebedor,
                k=k,
            )
            for renglon in renglones
        ]
    }
```

`app.state.grafo_conceptos` se construye **una vez** en el arranque, en la función `_arrancar`
que ya existe en `api.py`. Reconstruirlo por petición es exactamente el defecto que el
perfilado midió.

`armar_pool` corrige el texto y extrae atributos con `corregir` y `extraer_atributos`, que ya
existen y se reusan; consulta cada canal; y delega la unión en `armar_pool_desde`. Si
`embebedor` es `None`, el canal denso aporta lista vacía y los otros dos siguen: degradar,
nunca tumbar.

- [ ] **Step 4: Correr y verificar que pasa**

```bash
cd tukit
uv run pytest servicios/catalogo/tests/test_recuperar.py -v
uv run pytest servicios/catalogo -q
```
Expected: verde, y `test_api_catalogo.py` intacto porque `emparejar` no se tocó.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/catalogo/tukit_catalogo/recuperacion/pool.py servicios/catalogo/tukit_catalogo/api.py servicios/catalogo/tests/test_recuperar.py
git commit -m "feat(catalogo): POST /v1/catalogo/recuperar, pool sin veredicto

emparejar queda intacto porque el contrato ya lo publica. RRF no puntua."
```

---

### Task 7: Puerto `Reordenador` con respaldo aprendido

**Files:**
- Create: `servicios/inteligencia/tukit_inteligencia/resolucion/__init__.py`
- Create: `servicios/inteligencia/tukit_inteligencia/resolucion/reordenador.py`
- Modify: `servicios/inteligencia/pyproject.toml` (agregar `scikit-learn>=1.4`)
- Test: `servicios/inteligencia/tests/test_reordenador.py`

**Interfaces:**
- Produces: `class Reordenador(Protocol)` con `puntuar(consulta, candidatos) -> list[float]`;
  `ReordenadorLogistico` (respaldo); `obtener_reordenador() -> tuple[Reordenador, str]` que
  devuelve también el nombre del nivel usado (`gpu`, `local`, `respaldo`).

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/inteligencia/tests/test_reordenador.py
"""El puerto y su respaldo. Degradar, nunca tumbar."""

from tukit_inteligencia.resolucion.reordenador import (
    ReordenadorLogistico,
    obtener_reordenador,
)


def _candidato(lex, vec, grafo, prior):
    return {"canales": {"lex": lex, "vec": vec, "grafo": grafo}, "prior_grado": prior}


def test_el_respaldo_pondera_por_evidencia_y_no_por_rango():
    """Es lo que RRF no hace, y por eso RRF midio peor que su canal denso."""
    reordenador = ReordenadorLogistico()

    puntajes = reordenador.puntuar(
        "cuaderno", [_candidato(1.0, 0.1, 0.0, 0.01), _candidato(0.3, 0.95, 0.0, 0.4)]
    )

    # El segundo tiene evidencia densa fuerte y mejor prior; gana pese a que el
    # primero satura el canal lexico.
    assert puntajes[1] > puntajes[0]


def test_los_puntajes_estan_entre_cero_y_uno():
    puntajes = ReordenadorLogistico().puntuar("x", [_candidato(0.5, 0.5, 0.0, 0.1)])

    assert 0.0 <= puntajes[0] <= 1.0


def test_sin_candidatos_devuelve_lista_vacia_y_no_revienta():
    assert ReordenadorLogistico().puntuar("x", []) == []


def test_sin_adaptador_configurado_se_usa_el_respaldo_y_se_dice_cual_es():
    reordenador, nivel = obtener_reordenador()

    assert nivel == "respaldo"
    assert isinstance(reordenador, ReordenadorLogistico)


def test_el_orden_de_los_puntajes_corresponde_al_de_los_candidatos():
    candidatos = [_candidato(0.9, 0.9, 0.0, 0.5), _candidato(0.1, 0.1, 0.0, 0.01)]

    puntajes = ReordenadorLogistico().puntuar("x", candidatos)

    assert len(puntajes) == 2
    assert puntajes[0] > puntajes[1]
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_reordenador.py -v`
Expected: FAIL con `ModuleNotFoundError: ...resolucion.reordenador`

- [ ] **Step 3: Implementar**

```python
# servicios/inteligencia/tukit_inteligencia/resolucion/reordenador.py
"""El puerto de reordenamiento y su escalera de adaptadores.

El ADR 0005 fijo la escalera: GPU serverless (Modal) por el arranque en frio de
1,5-3,5 s, adaptador local en CPU para desarrollo y demostracion, y un respaldo
cuando ninguno esta.

El ADR 0005 decia que ese respaldo era "el orden de la fusion reciproca". El ADR
0019 lo enmienda con la medicion: RRF obtuvo AUC 0,753, POR DEBAJO de su propio
canal denso (0,825). Degradar a RRF es degradar por debajo de no fusionar nada.
El respaldo es una regresion logistica sobre los cuatro rasgos, que pondera por
evidencia en vez de por rango.
"""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from typing import Any, Protocol

RASGOS = ("lex", "vec", "grafo", "prior_grado")

# Coeficientes de arranque, coherentes con los AUC medidos: el canal denso pesa
# mas que el lexico porque midio mejor (0,825 contra 0,728). Se reemplazan por
# los ajustados sobre los 2.710 pares en cuanto el entrenamiento corra; hasta
# entonces son un punto de partida declarado y no un numero magico.
COEFICIENTES_INICIALES = {"lex": 1.4, "vec": 3.2, "grafo": 0.9, "prior_grado": 1.1}
SESGO_INICIAL = -2.5


class Reordenador(Protocol):
    def puntuar(self, consulta: str, candidatos: Sequence[dict[str, Any]]) -> list[float]: ...


class ReordenadorLogistico:
    """El respaldo. Sale calibrado de fabrica y no agrega modelo a la imagen."""

    def __init__(
        self,
        coeficientes: dict[str, float] | None = None,
        sesgo: float = SESGO_INICIAL,
    ) -> None:
        self.coeficientes = dict(coeficientes or COEFICIENTES_INICIALES)
        self.sesgo = sesgo

    def _rasgos_de(self, candidato: dict[str, Any]) -> dict[str, float]:
        canales = candidato.get("canales") or {}
        return {
            "lex": float(canales.get("lex") or 0.0),
            "vec": float(canales.get("vec") or 0.0),
            "grafo": float(canales.get("grafo") or 0.0),
            "prior_grado": float(candidato.get("prior_grado") or 0.0),
        }

    def puntuar(self, consulta: str, candidatos: Sequence[dict[str, Any]]) -> list[float]:
        puntajes = []
        for candidato in candidatos:
            rasgos = self._rasgos_de(candidato)
            z = self.sesgo + sum(self.coeficientes[r] * rasgos[r] for r in RASGOS)
            puntajes.append(1.0 / (1.0 + math.exp(-z)))
        return puntajes


def obtener_reordenador() -> tuple[Reordenador, str]:
    """El mejor disponible, y el nombre del nivel al que se degrado.

    Devolver el nivel es lo que permite marcar la etapa como DEGRADADA en vez de
    fingir que corrio completa.
    """
    if os.getenv("TUKIT_REORDENADOR_URL"):
        from .reordenador_remoto import ReordenadorRemoto

        return ReordenadorRemoto(os.environ["TUKIT_REORDENADOR_URL"]), "gpu"
    return ReordenadorLogistico(), "respaldo"
```

Crear también `servicios/inteligencia/tukit_inteligencia/resolucion/__init__.py` con un
docstring de una línea.

Nota: `reordenador_remoto.py` se importa de forma perezosa dentro de la función, así que no
hace falta crearlo para que las pruebas pasen. Se agrega cuando haya adaptador remoto.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_reordenador.py -v`
Expected: PASS, 5 pruebas.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/tukit_inteligencia/resolucion/ servicios/inteligencia/tests/test_reordenador.py servicios/inteligencia/pyproject.toml
git commit -m "feat(inteligencia): puerto Reordenador con respaldo logistico (ADR 0019)"
```

---

### Task 8: Calibración y decisión τ/δ

**Files:**
- Create: `servicios/inteligencia/tukit_inteligencia/resolucion/calibrador.py`
- Create: `servicios/inteligencia/tukit_inteligencia/resolucion/decision.py`
- Test: `servicios/inteligencia/tests/test_calibrador.py`, `servicios/inteligencia/tests/test_decision.py`

**Interfaces:**
- Produces:
  - `class Calibrador` con `ajustar(puntajes, etiquetas) -> Calibrador`,
    `probabilidad(puntajes) -> list[float]`, y metadatos `modelo`, `ajustado_en`, `hash_gold`.
  - `TAU = 0.70`, `DELTA = 0.15`, `decidir(probabilidades, hubo_concepto, atributo_incumplido) -> str`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# servicios/inteligencia/tests/test_calibrador.py
"""Un puntaje no es una probabilidad, y compararlo contra un umbral fijo fue el
defecto original."""

from tukit_inteligencia.resolucion.calibrador import Calibrador


def test_la_probabilidad_esta_en_cero_uno():
    calibrador = Calibrador.ajustar([0.1, 0.4, 0.6, 0.9], [0, 0, 1, 1])

    for p in calibrador.probabilidad([0.0, 0.5, 1.0]):
        assert 0.0 <= p <= 1.0


def test_es_monotona_respecto_del_puntaje_crudo():
    """La isotonica no puede invertir el orden: eso es lo que la hace defendible."""
    calibrador = Calibrador.ajustar([0.1, 0.3, 0.5, 0.7, 0.9], [0, 0, 1, 1, 1])

    probabilidades = calibrador.probabilidad([0.1, 0.3, 0.5, 0.7, 0.9])

    assert probabilidades == sorted(probabilidades)


def test_registra_de_donde_salio():
    """Un calibrador sin procedencia es un numero magico con otro nombre."""
    calibrador = Calibrador.ajustar([0.1, 0.9], [0, 1])

    assert calibrador.modelo
    assert calibrador.ajustado_en
    assert calibrador.hash_gold


def test_dos_ajustes_sobre_los_mismos_datos_dan_el_mismo_hash():
    uno = Calibrador.ajustar([0.1, 0.9], [0, 1])
    otro = Calibrador.ajustar([0.1, 0.9], [0, 1])

    assert uno.hash_gold == otro.hash_gold
```

```python
# servicios/inteligencia/tests/test_decision.py
"""Los cuatro estados que ya existen. No se inventa `clarify`: es AMBIGUO."""

from tukit_inteligencia.modelos import EstadoResolucion
from tukit_inteligencia.resolucion.decision import DELTA, TAU, decidir


def test_probabilidad_alta_y_margen_amplio_resuelve_solo():
    estado = decidir([0.95, 0.20], hubo_concepto=True)

    assert estado == EstadoResolucion.RESUELTO_AUTO.value


def test_probabilidad_alta_con_margen_estrecho_es_ambiguo():
    """El margen manda aunque p1 sea alta: dos candidatos igual de buenos es
    una duda, no una respuesta."""
    estado = decidir([0.95, 0.93], hubo_concepto=True)

    assert estado == EstadoResolucion.AMBIGUO.value


def test_probabilidad_baja_con_concepto_reconocido_es_hueco_de_catalogo():
    """ "Te entendi y no lo tengo" es distinto de "no te entendi"."""
    estado = decidir([0.10], hubo_concepto=True)

    assert estado == EstadoResolucion.HUECO_CATALOGO.value


def test_probabilidad_baja_sin_concepto_es_sin_match():
    estado = decidir([0.10], hubo_concepto=False)

    assert estado == EstadoResolucion.SIN_MATCH.value


def test_un_atributo_que_ningun_producto_declara_es_hueco_no_sin_match():
    """ "Block oficio" se entiende perfecto; lo que falta es el producto."""
    estado = decidir([0.99], hubo_concepto=True, atributo_incumplido=True)

    assert estado == EstadoResolucion.HUECO_CATALOGO.value


def test_sin_candidatos_es_sin_match():
    assert decidir([], hubo_concepto=False) == EstadoResolucion.SIN_MATCH.value


def test_un_solo_candidato_sobre_el_umbral_resuelve():
    """Sin segundo no hay margen que exigir."""
    assert decidir([0.99], hubo_concepto=True) == EstadoResolucion.RESUELTO_AUTO.value


def test_los_umbrales_estan_declarados_y_son_razonables():
    assert 0.0 < TAU < 1.0
    assert 0.0 < DELTA < 1.0
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_calibrador.py servicios/inteligencia/tests/test_decision.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
# servicios/inteligencia/tukit_inteligencia/resolucion/calibrador.py
"""Convierte el puntaje del reordenador en una probabilidad.

Comparar un puntaje crudo contra un umbral fijo fue el defecto original: el
puntaje de un cross-encoder no es una probabilidad y su escala se mueve con el
modelo. La isotonica es monotona por construccion, asi que no puede reordenar
candidatos: solo reescala. Eso es justamente lo que la hace defendible.

El calibrador se versiona con su modelo, su fecha y el hash del gold con que se
ajusto. Un calibrador sin procedencia es un numero magico con otro nombre.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Calibrador:
    puntos_x: tuple[float, ...]
    puntos_y: tuple[float, ...]
    modelo: str
    ajustado_en: str
    hash_gold: str

    @classmethod
    def ajustar(
        cls,
        puntajes: Sequence[float],
        etiquetas: Sequence[int],
        *,
        modelo: str = "isotonica",
    ) -> Calibrador:
        from sklearn.isotonic import IsotonicRegression

        modelo_iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        modelo_iso.fit(list(puntajes), list(etiquetas))

        crudo = ",".join(f"{p:.6f}:{e}" for p, e in zip(puntajes, etiquetas, strict=True))
        return cls(
            puntos_x=tuple(float(v) for v in modelo_iso.X_thresholds_),
            puntos_y=tuple(float(v) for v in modelo_iso.y_thresholds_),
            modelo=modelo,
            ajustado_en=datetime.now(UTC).isoformat(),
            hash_gold=hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:16],
        )

    def probabilidad(self, puntajes: Sequence[float]) -> list[float]:
        import numpy as np

        return [float(np.clip(np.interp(p, self.puntos_x, self.puntos_y), 0.0, 1.0)) for p in puntajes]
```

```python
# servicios/inteligencia/tukit_inteligencia/resolucion/decision.py
"""tau/delta sobre la probabilidad calibrada (ADR 0010).

Dos umbrales y no uno, porque son dos preguntas distintas: `tau` pregunta si el
mejor candidato es lo bastante bueno, y `delta` si es lo bastante MEJOR que el
segundo. Dos candidatos igual de buenos son una duda aunque los dos pasen `tau`,
y esa duda tiene nombre propio en el modelo.

Los cuatro estados ya existen en `modelos.base.EstadoResolucion` y no se inventa
ninguno. `AMBIGUO` es lo que en otras partes se llama "clarify".
"""

from __future__ import annotations

from collections.abc import Sequence

from ..modelos import EstadoResolucion

# Valores de arranque. Se fijan sobre la curva precision-cobertura del gold y no
# a ojo; hasta que esa curva se corra, quedan declarados aqui con esa advertencia.
TAU = 0.70
DELTA = 0.15


def decidir(
    probabilidades: Sequence[float],
    *,
    hubo_concepto: bool,
    atributo_incumplido: bool = False,
) -> str:
    """El estado del renglon, de la probabilidad calibrada y ordenada."""
    if atributo_incumplido:
        # "Block oficio" se entendio perfecto; lo que falta es el producto. Es
        # un hueco de catalogo y jamas un sin_match.
        return EstadoResolucion.HUECO_CATALOGO.value

    if not probabilidades:
        return EstadoResolucion.HUECO_CATALOGO.value if hubo_concepto else EstadoResolucion.SIN_MATCH.value

    ordenadas = sorted(probabilidades, reverse=True)
    primera = ordenadas[0]

    if primera < TAU:
        return EstadoResolucion.HUECO_CATALOGO.value if hubo_concepto else EstadoResolucion.SIN_MATCH.value

    if len(ordenadas) > 1 and (primera - ordenadas[1]) < DELTA:
        return EstadoResolucion.AMBIGUO.value

    return EstadoResolucion.RESUELTO_AUTO.value
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd tukit && uv run pytest servicios/inteligencia/tests/test_calibrador.py servicios/inteligencia/tests/test_decision.py -v`
Expected: PASS, 12 pruebas.

- [ ] **Step 5: Commit**

```bash
cd tukit
git add servicios/inteligencia/tukit_inteligencia/resolucion/ servicios/inteligencia/tests/test_calibrador.py servicios/inteligencia/tests/test_decision.py
git commit -m "feat(inteligencia): calibracion isotonica y decision tau/delta

AMBIGUO es el estado de duda y ya existia; no se inventa clarify."
```

---

### Task 9: Casos del corpus como pruebas de regresión

**Files:**
- Create: `servicios/catalogo/tests/test_casos_del_corpus.py`

- [ ] **Step 1: Escribir las pruebas**

```python
# servicios/catalogo/tests/test_casos_del_corpus.py
"""Los casos que el corpus ya probo que fallan. Son pruebas, no ejemplos.

Cada uno viene de un error observado y documentado. El canal denso es nuevo y no
puede reintroducir los que el canal lexico ya tenia corregidos.
"""

import pytest

from tukit_catalogo.consulta import emparejar
from tukit_catalogo.descubrir import clasificar


@pytest.fixture
def conceptos():
    return [
        {
            "id": "c-colores",
            "codigo": "C004",
            "nombre": "colores",
            "sinonimos": ["lapices de colores"],
            "discriminantes": (),
        },
        {"id": "c-pompones", "codigo": "C050", "nombre": "pompones", "sinonimos": [], "discriminantes": ()},
        {
            "id": "c-block",
            "codigo": "C003",
            "nombre": "block",
            "sinonimos": [],
            "discriminantes": ("tamano",),
        },
    ]


def test_pompones_de_colores_no_cae_en_el_concepto_colores(conceptos):
    """Ahi "colores" es un adjetivo, no lo pedido. Defecto ya corregido."""
    concepto_id, _, _ = clasificar("pompones de colores", conceptos)

    assert concepto_id == "c-pompones"


def test_chaquiras_de_colores_tampoco(conceptos):
    """Chaquiras no esta en el catalogo, y reconocerlo como concepto nuevo es
    la respuesta correcta."""
    concepto_id, _, _ = clasificar("chaquiras de colores", conceptos)

    assert concepto_id != "c-colores"


def test_block_oficio_se_abstiene_en_vez_de_ofrecer_origami(conceptos):
    productos = [
        {
            "concepto_id": "c-block",
            "sku": "TK-C003-ORI",
            "nombre": "Bloc origami x 50",
            "nivel": "economico",
            "personaje": None,
            "atributos": {"tipo": "origami"},
            "precio_cop": 5000,
        },
    ]

    resultado = emparejar("block oficio", conceptos, productos)

    assert resultado.estado == "abstencion"
    assert resultado.opciones == ()
    assert "oficio" in resultado.motivo.lower() or "tamano" in resultado.motivo.lower()
```

- [ ] **Step 2: Correr**

Run: `cd tukit && uv run pytest servicios/catalogo/tests/test_casos_del_corpus.py -v`
Expected: PASS. Si alguna falla, es una regresión real y hay que arreglar el código, no la
prueba.

- [ ] **Step 3: Commit**

```bash
cd tukit
git add servicios/catalogo/tests/test_casos_del_corpus.py
git commit -m "test(catalogo): casos del corpus como regresion"
```

---

### Task 10: Verificación final

- [ ] **Step 1: Suite completa**

```bash
cd tukit
uv run pytest
uv run ruff check .
make bd-deriva
uv run pytest arquitectura -q
```
Expected: todo verde, ruff limpio, sin deriva, cinco invariantes en pie.

- [ ] **Step 2: Vectorizar el catálogo de verdad**

```bash
cd tukit
TUKIT_EMBEBEDOR=e5 uv run python -m tukit_catalogo.vectorizar
psql -d tukit_catalogo -c "select count(*) total, count(embedding) con_vector from producto_canonico;"
psql -d tukit_catalogo -c "select count(*) total, count(embedding) con_vector from concepto;"
```
Expected: 375 de 375 y 100 de 100. Correrlo dos veces no debe reescribir nada.

- [ ] **Step 3: Humo**

```bash
cd tukit
make backend
make humo
curl -s -X POST http://127.0.0.1:8010/v1/catalogo/recuperar \
  -H 'content-type: application/json' \
  -d '{"renglones":[{"texto":"cuaderno cuadriculado de 100 hojas","grado":"Cuarto"}]}' | head -40
```
Expected: candidatos con `canales` y `via` poblados, y al menos uno que haya entrado por `vec`.

---

## Qué queda fuera de este plan

- La medición completa sobre los 2.710 pares (recall de catálogo, accuracy de concepto,
  precisión de selección, ablación). Es trabajo de evaluación con su propio guion.
- El ajuste real de τ y δ sobre la curva precisión-cobertura: los valores de este plan son de
  arranque y están declarados como tales.
- El entrenamiento de la logística de respaldo sobre el gold: los coeficientes iniciales son
  coherentes con los AUC medidos y se reemplazan cuando el entrenamiento corra.
- El adaptador remoto del reordenador (`reordenador_remoto.py`), que se importa de forma
  perezosa y no bloquea nada.
- Llenar los 102 huecos de catálogo.
- La revisión humana de las ~120 aristas propuestas, que es trabajo de curaduría.
