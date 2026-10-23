# Documentación de Tukit

Toda la documentación del repositorio vive aquí, clasificada por **qué tipo de documento es**,
no por el tema. El tema se busca en este índice; la carpeta dice cómo leer el documento: un
contrato manda, un ADR registra una decisión, un plan describe trabajo por hacer, un informe
reporta una medición.

| Carpeta | Qué contiene | Cómo leerlo |
|---|---|---|
| [`arquitectura/`](arquitectura/) | El contrato de la API, la revisión de arquitectura y los ADR | **Normativo.** Si el código y estos documentos no coinciden, uno de los dos tiene un defecto |
| [`algoritmos/`](algoritmos/) | El documento formal (LaTeX) de los algoritmos del núcleo | Referencia académica: definición, pseudocódigo, complejidad, propiedades y evolución |
| [`requisitos/`](requisitos/) | El trabajo sobre el SRS: consolidación, cierres de versión, adenda, trazabilidad, decisiones pendientes | Histórico de la especificación. El SRS vigente (`.docx`) vive en el repositorio externo `Arquitectura/` |
| [`diseno/specs/`](diseno/specs/) | Diseños de una funcionalidad antes de construirla | Qué se decidió construir y por qué |
| [`diseno/planes/`](diseno/planes/) | Planes de implementación paso a paso de esos diseños | Cómo se construyó; el estado al inicio de cada uno dice si se ejecutó |
| [`analisis/`](analisis/) | Análisis del sistema que no son diseño de una funcionalidad | Diagnósticos con su fecha: describen el estado en ese momento |
| [`guias/`](guias/) | Guías de procedimiento para operar el sistema | Cómo hacer algo bien, paso a paso. Normativas para quien opera |
| [`registros/`](registros/) | Registros de aplicación de un trabajo ya hecho, con las reglas para continuarlo | Qué se hizo y cómo seguir haciéndolo |
| [`informes/`](informes/) | Resultados de ensayos y auditorías, con sus cifras y los archivos de resultados | Mediciones fechadas. El código que las produce sigue en `ensayos/` y escribe aquí |

Lo que quedó abierto (mediciones por repetir, documentos externos por traer, mejoras de los
algoritmos, integración de ramas) está en [`PENDIENTES.md`](PENDIENTES.md).

## Índice

### Arquitectura (normativo)

- [Contrato de la API](arquitectura/CONTRATO_API.md) — la superficie HTTP del sistema, versionada. Fuente de verdad del frontend y de `libs/ts/tukit-contrato`.
- [Revisión de arquitectura](arquitectura/REVISION_ARQUITECTURA.md) — diagnóstico y diseño objetivo del backbone (resiliencia, eventos, observabilidad).
- [Decisiones de arquitectura (ADR)](arquitectura/adr/README.md) — 0027 a 0046, en formato Nygard, con su índice.

### Algoritmos

- [Algoritmos del núcleo de Tukit](algoritmos/main.tex) — percepción, normalización, resolución híbrida, catálogo y optimización multiobjetivo. Se compila con `latexmk -pdf main.tex` desde [`algoritmos/`](algoritmos/); el PDF no se versiona.

### Requisitos (SRS)

En orden cronológico:

1. [Consolidación del SRS en la línea base v4](requisitos/CONSOLIDACION_SRS_V4.md)
2. [Cierre v4 → v5](requisitos/CIERRE_V5.md) — el umbral `DP-04`, la norma de `E-21` y la Tabla 4.
3. [Cierre v5 → v6](requisitos/CIERRE_V6.md) — una sola taxonomía y el choque de `OP-03`.
4. [Adenda de requisitos](requisitos/ADENDA_REQUISITOS_SRS.md) — revisión del admin, artefacto reutilizable, aviso y factura (**ya incorporada**; no volver a aplicar).
5. [Correcciones de trazabilidad](requisitos/CORRECCIONES_TRAZABILIDAD.md) — códigos de requisito mal citados.
6. [`OP-03` frente a `NR-07`](requisitos/DECISION_OP03_NR07.md) — preparación de una decisión, con las opciones.
7. [Requisitos diferidos](requisitos/REQUISITOS_DIFERIDOS.md) — proveedores mayoristas y contenido editorial.

### Diseño: especificaciones y planes

Cada especificación tiene su plan con la misma fecha y el mismo nombre.

| Fecha | Tema | Especificación | Plan |
|---|---|---|---|
| 2026-09-22 | OE3 — Resolución híbrida con grafo | [spec](diseno/specs/2026-09-22-resolucion-hibrida-grafo-design.md) | [plan](diseno/planes/2026-09-22-resolucion-hibrida-grafo.md) |
| 2026-09-22 | OE4 — Optimizador NSGA-II + MAUT | [spec](diseno/specs/2026-09-22-optimizador-nsga2-maut-design.md) | [plan](diseno/planes/2026-09-22-optimizador-nsga2-maut.md) |
| 2026-09-23 | Curaduría del catálogo en la SPA | [spec](diseno/specs/2026-09-23-curaduria-catalogo-spa-design.md) | [plan](diseno/planes/2026-09-23-curaduria-catalogo-spa.md) |
| 2026-09-26 | Identidad y cuenta del acudiente | [spec](diseno/specs/2026-09-26-identidad-cuenta-acudiente-design.md) | [plan](diseno/planes/2026-09-26-identidad-cuenta-acudiente.md) (con sus secciones en `diseno/planes/.secciones-identidad-cuenta/`) |
| 2026-10-02 | Pagos de prueba con Wompi | [spec](diseno/specs/2026-10-02-pagos-wompi-sandbox-design.md) | [plan](diseno/planes/2026-10-02-pagos-wompi-sandbox.md) |
| 2026-10-11 | Afinar los kits del Agustiniano sin poblar el catálogo | — (la auditoría de huecos y el [ADR 0043](arquitectura/adr/0043-como-se-compara-cada-atributo.md)) | [plan](diseno/planes/2026-10-11-afinar-kits-agustiniano.md) |

Lo que se construyó puede diferir de la especificación. El documento de [algoritmos](algoritmos/main.tex) dice, para OE3 y OE4, qué se implementó y qué no.

### Análisis

- [Flujo de extremo a extremo por actor](analisis/FLUJO_EXTREMO_A_EXTREMO.md) — qué faltaba para cerrar el recorrido de cada actor (2026-09-22).
- [Hallazgos del recorrido manual por la UI](analisis/GAPS_UI.md) — ruta, persona, esperado, observado y causa.

### Guías

- [Curaduría: conceptos, productos y atributos](guias/GUIA_CONCEPTOS_Y_PRODUCTOS.md) — cuándo crear un concepto y cómo llenar cada campo, cómo asociarle productos, el vocabulario y el formato de cada atributo, qué hacer después de curar y qué valores del catálogo no cumplen la guía hoy.

### Registros

- [Curaduría del catálogo y los conceptos](registros/CURADURIA_CATALOGO.md) — cómo decide el emparejador, los criterios para curar y el registro de los conceptos creados.

### Informes

- [Benchmark: Laya contra el optimizador NSGA-II](informes/reporte-benchmark-laya-nsga.md) — sus resultados (métricas, detalle por lista, tablas, figuras, tiempos) están en [`informes/benchmark-laya/`](informes/benchmark-laya/README.md); el código y los datos de entrada, en [`ensayos/bench_laya/`](../ensayos/bench_laya/).
- [Auditoría de los kits canónicos de Séptimo](informes/auditoria-kits-agustiniano-septimo.md) (2026-10-07).
- [Auditorías de huecos del Agustiniano](informes/auditoria-huecos-agustiniano/README.md): las cuatro versiones (sobre `a565aeb`, `d4ea7cb`, `02d8f24` y `4dc3bc8`), con su índice.
- [Qué buscar con el scraper: huecos reales del Agustiniano](informes/surtido-huecos-agustiniano.md) (2026-10-12): los 69 renglones que siguen en hueco después del surtido aprobado en la cola.
- [Propuesta de atributos obligatorios para Séptimo](informes/atributos-septimo-propuesta.md), con su [hoja de revisión producto por producto](informes/propuestas-atributos-septimo.csv) (acción, atributo, valor propuesto, confianza y razón).

### Código de los ensayos

[`ensayos/`](../ensayos/) no tiene documentación: tiene el código que produce los informes y las herramientas de desarrollo. Sus pruebas corren con las del resto del repositorio.

| Qué | Para qué |
|---|---|
| `ensayos/bench_laya/` | Reproducir el benchmark: scripts, pruebas del óptimo exacto y datos de entrada (`.json.gz`, `escenarios.json`, `laya_*.json`) |
| `ensayos/curaduria_huecos.py` | Generar el informe de huecos del catálogo |
| `ensayos/fase1.py` | Parsear y emparejar renglones de punta a punta desde la consola (`make fase1`) |
| `ensayos/kits_offline.py` | Armar, desde `datos/` y sin base de datos, los kits Ahorrador y Premium de un colegio, para medir un cambio de curaduría o de código antes de cargarlo. Sus pruebas (`test_kits_offline.py`) fijan los renglones de la auditoría del Agustiniano |

## Lo que no está aquí, a propósito

| Documento | Dónde | Por qué se queda |
|---|---|---|
| `README.md` | raíz | Es la puerta de entrada del repositorio: cómo levantarlo y probarlo |
| `apps/web/README.md` | su app | Instrucciones de esa app |
| `apps/*/AGENTS.md`, `apps/admin/CLAUDE.md` | su app | Instrucciones para agentes de código; las herramientas las buscan en esa ruta |
| `arquitectura/` (raíz) | raíz | Ya no tiene documentos: son las funciones de aptitud (`test_fronteras.py`, `manifiesto.toml`, `verificar_deriva.py`, `humo.py`) que el `Makefile` ejecuta |
| ADR 0001–0026, `ARQUITECTURA.md`, el SRS | repositorio externo `Arquitectura/` | No forman parte de este repositorio; el código los cita por número |

## Convenciones para documentos nuevos

- Se ubica por tipo, según la tabla de arriba. Una especificación nueva va en `diseno/specs/AAAA-MM-DD-tema-design.md` y su plan en `diseno/planes/AAAA-MM-DD-tema.md`. Algunas herramientas de agentes escriben por omisión en `docs/superpowers/`; esos archivos se mueven aquí.
- Un ADR nuevo continúa la numeración en `arquitectura/adr/` y agrega su fila al índice de esa carpeta.
- Todo documento se agrega a este índice.
- Los enlaces entre documentos son relativos a la carpeta del archivo. Después de mover un documento hay que revisar los enlaces que salen de él y los que llegan a él.
