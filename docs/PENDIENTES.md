# Pendientes

Lo que quedó abierto, con lo necesario para retomarlo sin reconstruir el contexto. Cada entrada dice
qué falta, por qué importa y cómo se hace. Cuando algo se resuelve, se borra de aquí y queda en el
commit, el ADR o el documento que lo resolvió.

- **Última revisión:** 2026-10-08.

---

## 1. Documentación

### 1.1 Volver a medir el benchmark con el optimizador vigente

**Qué falta.** Las cifras del [informe del benchmark](informes/reporte-benchmark-laya-nsga.md), las de
la §8 del [documento de algoritmos](algoritmos/main.tex) y los archivos de
[`informes/benchmark-laya/`](informes/benchmark-laya/README.md) son del optimizador del 4 de octubre
de 2026 (v3). Desde entonces cambió cuatro veces: costo de línea, siembra con la escalera, mejor
marca que cabe (v4); kits a pedido y A tu Medida (v5); herramientas por hijo (v6); proyección sobre
lo surtible (v7, [ADR 0039](arquitectura/adr/0039-lo-que-no-tiene-precio-no-gana-por-barato.md)).

**Por qué importa.** La tesis presenta las cifras de v3 y, aparte, el efecto de v4 medido con la
semilla 0. Una medición completa con el optimizador vigente reemplazaría las dos cosas por una sola
tabla actual.

**Cómo.** Con el venv del proyecto, desde `ensayos/bench_laya/`. No hace falta GPU: las respuestas
de Laya (`laya_A.json` a `laya_D.json`) no dependen del optimizador y se reutilizan. Conviene
conservar `instancias.json.gz` tal cual, para medir sobre la misma foto del catálogo y que la
comparación con v3 sea directa.

```bash
cd ensayos/bench_laya
python correr_nsga.py --procesos 10      # el frente con el optimizador vigente, 5 semillas
python evaluar.py                        # escribe resumen.json y resultados.json.gz en docs/informes/benchmark-laya/
python graficas.py "2.14|Jardin"         # tablas.md, fig_optimo.png y la figura del frente
python tiempos.py nsga                   # opcional: tiempos con la máquina sola
python -m pytest test_comun.py           # el óptimo exacto sigue siendo el techo
```

**Después de correrlo:**

- Actualizar las tablas y la lectura del [informe](informes/reporte-benchmark-laya-nsga.md) y su
  sección «Lo que cambió después».
- Actualizar en el documento de algoritmos la tabla de resultados y la de antes/después
  (`secciones/08-evaluacion.tex`) y recompilar. La figura se toma sola de `informes/benchmark-laya/`.
- La fila «Modelo general» (Laya) no cambia, porque sus elecciones son las mismas; lo que cambia
  es contra qué frente se mide si está dominada.

### 1.2 Traer los documentos del repositorio externo `Arquitectura/`

**Qué falta.** El README raíz y varios documentos citan documentos de un repositorio `Arquitectura/`
que no está en esta máquina ni en la organización de GitHub: `ARQUITECTURA.md`, los ADR 0001 a 0026
(en particular el 0014, *monorepo con despliegue independiente*), `PERFILADO_PIPELINE.md`,
`PLAN_TUKIT_V2.md`, `ESQUEMA_OBJETIVO.md` y el SRS (`SRS_ISIS2610G19_v6.docx`). Los tres que el
README enlazaba quedaron como referencias de texto para no dejar enlaces rotos. Se buscaron el
2026-10-08 en el perfil de usuario completo, en los repositorios de `Documents/TESIS` con su
historial y en los repositorios de `Tukit-Col` en GitHub, sin resultado.

**Cómo.** Si aparecen, copiarlos a `docs/` según su tipo (los ADR a `arquitectura/adr/`, el
perfilado a `analisis/`, el plan a `diseno/planes/`, el SRS a `requisitos/`), agregarlos al
[índice](README.md) y volver a convertir en enlaces las referencias de texto del README raíz.

### 1.3 Portada del documento de algoritmos

Completar facultad, departamento, programa, director, ciudad y fecha al inicio de
[`algoritmos/main.tex`](algoritmos/main.tex) (las macros `\Facultad`, `\Departamento`,
`\Programa`, `\Director`, `\Lugar` y `\Fecha`).

---

## 2. Algoritmos

En orden de impacto. Los cuatro primeros salen del análisis del
[documento de algoritmos](algoritmos/main.tex) (§7.4 y §10).

### 2.1 Frente exacto por programación dinámica

Con la formulación vigente los cuatro objetivos se suman línea por línea, y el frente de Pareto
exacto se calcula por programación dinámica sobre (suma de niveles, líneas con precio, líneas con
personaje) en O(n⁴k). Para una lista típica son unos 10⁴ estados frente a unas 10⁷ operaciones del
NSGA-II, y el frente pasaría a ser exacto y no dependería de una semilla. La recurrencia está en el
teorema 7.10 y se verificó contra la enumeración en 300 instancias. Puede reemplazar al NSGA-II o
quedarse como verificación.

### 2.2 Pesos por omisión distintos de los de la encuesta

`PESOS_POR_OMISION` en `servicios/inteligencia/tukit_inteligencia/modelos/base.py` vale
precio 0,35 · marca exigida 0,30 · calidad 0,25 · personaje 0,10. La pregunta de prioridades de la
encuesta, normalizada, da 0,285 · 0,273 · 0,255 · 0,187: los del código exageran la separación y le
quitan al personaje casi la mitad de su peso. Cambiarlos es una línea, pero puede cambiar qué kit se
recomienda (la condición «calidad primero» de `recomendar`), así que va con su prueba y con la
decisión registrada.

### 2.3 Un rescate semántico con coseno ≥ 0,93 se acepta sin revisión

Abierto en el [ADR 0039](arquitectura/adr/0039-lo-que-no-tiene-precio-no-gana-por-barato.md). El
arreglo correcto es que `/v1/catalogo/emparejar` diga que el concepto vino de un rescate y que
`estado_desde_emparejamiento` lo mande siempre a revisión. Cambia el contrato de la API. Impacto
medido bajo: ningún producto alcanzó 0,93 contra un concepto ajeno.

### 2.4 Acoplamiento en el objetivo

Mientras la consolidación entre hermanos y la agrupación de herramientas se apliquen después de
elegir, el optimizador resuelve un problema separable. Llevar la consolidación dentro del costo (y,
eventualmente, un costo fijo por tienda) acopla las líneas y vuelve a justificar una metaheurística.
En ese caso: cambiar SBX y PM por operadores categóricos (cruce uniforme, mutación por reemplazo del
índice), medir con hipervolumen contra el frente exacto en instancias chicas, y correr la prueba de
falsación que preveía el diseño (sin acoplamiento, heurística y NSGA-II deben empatar).

### 2.5 Resolución: grafo de sustituibilidad y reordenador

La tabla `sustituibilidad_concepto` existe y está vacía; el reordenador no está implementado. La
evaluación tiene que separar «no lo tenemos» de «no lo encontramos» y medir el *recall* antes que el
ordenamiento.

### 2.6 Calibrar τ

El umbral de autoaceptación (`TUKIT_TAU`, 0,75) se fijó a mano. Calibrarlo contra las correcciones
que hacen los revisores en la cola.

### 2.7 Percepción en paralelo

Las páginas se leen una tras otra; son independientes. Leerlas en paralelo, respetando la cuota del
proveedor, baja la primera lectura de la suma de las páginas a la más lenta.

### 2.8 Evaluar hogares de varios hijos

El benchmark usa un hijo por lista, así que la consolidación entre hermanos nunca entra en juego.
Armar hogares sintéticos de 2 a 4 hijos combinando listas de un mismo colegio.

---

### 2.9 El personaje se escribe de dos formas

La tabla de personajes de `enriquecer.py` (`PERSONAJES`) produce el nombre con mayúsculas
(`Frozen`, `Mickey Mouse`), y es la que usa la aprobación de la cola; las semillas del corpus están
en minúsculas (`frozen`). El kit Fan compara sin distinguir mayúsculas, pero la nivelación agrupa
por el texto exacto, así que `Frozen` y `frozen` quedan en escaleras distintas, y el SKU semilla
cambia. Hoy 24 de los 76 productos activos con personaje tienen mayúsculas. Arreglo: normalizar a
minúsculas al escribir (salida de `extraer_personaje` y guardado del editor), y una pasada única
sobre `productos_canonicos.csv`. La [guía de curaduría](guias/GUIA_CONCEPTOS_Y_PRODUCTOS.md) fija
la forma en minúsculas mientras tanto.

---

## 3. Ramas e integración

- **Nada está publicado.** `docs/documentacion` sale de `feature/atributos-catalogo`, que va
  218 commits por delante de `main`. Integrar primero atributos y después documentación; al revés,
  la de documentación arrastra los commits de atributos.
- **El trabajo `ensayos` de la CI** se verificó solo localmente. Confirmar que pasa en GitHub al
  publicar la rama.

---

## 4. Menores

- `ensayos/curaduria_huecos.py` usa rutas `/tmp/...` (cachés de percepción); en Windows apuntan a
  `C:\tmp`. Pasarlas a una carpeta del repositorio ignorada por git o a una variable de entorno.
- `ensayos/fase1.py` fuera de `make fase1` no carga `.env` y falla al conectarse a la base. Cargar
  `.env` al arrancar, como hacen los servicios.
