# Informe técnico: intervención de calidad sobre Tukit (RCTCO)

Rama de trabajo: `refactor/limpieza-tukit` (desde `main` @ `11c3f10`). Sin commits, push ni merge.

## 1. Diagnóstico inicial

Monorepo con 6 servicios FastAPI (identidad, catalogo, inteligencia, comercio, operacion, gateway), `libs/py/tukit_comun`, `libs/ts/tukit-contrato` y 2 apps Next 16 (web, admin). Las fronteras entre servicios ya las hace cumplir `arquitectura/test_fronteras.py`.

Problemas confirmados:
- Módulos con varias responsabilidades: `inteligencia/trabajos.py` (3.471 líneas, con SQL propio), `inteligencia/optimizador.py` (1.792), `catalogo/enriquecer.py` (1.786) y `catalogo/descubrir.py` (1.564), `libs/ts/.../cliente-http.ts` (2.035).
- Duplicación: `_token_bearer` en 5 sitios (dos veces en `operacion/routers/operacion.py`, la segunda sobrescribía a la primera) y `_token_del_encabezado` en identidad.
- Capas invertidas: la ruta de consulta del catálogo (`consulta.py`) importaba de los CLI `descubrir` y `enriquecer`.
- Residuos: `docs/memoria/x5.py` (script desechable) y huecos en `.gitignore`.
- Deriva documental en el README (`apps/colegio`, `libs/go`, `servicios/ingesta` presentados como existentes).
- Sin código comentado ni TODOs.

## 2. Preparación e instalación

- Estado inicial: `main`, árbol limpio, sin stash. `origin/validacion/oe5` @ `6a89666` ya existía en el remoto; por indicación del usuario no se usó ni se modificó.
- Rama `refactor/limpieza-tukit` creada desde `main` y verificada activa.
- AI Slop Cleaner: copia manual del `SKILL.md` oficial en `.claude/skills/ai-slop-cleaner/SKILL.md` (159 líneas, `name: ai-slop-cleaner`, descargado de `Yeachan-Heo/oh-my-claudecode`, sin modificar). No se usó `npx skills add` porque habría creado `.agents/`, `skills-lock.json` y symlinks. Solo se instaló en el repositorio.
- Limitación: la sesión ya estaba iniciada al instalar, así que la skill no aparece en la lista de skills de Claude Code. La revisión se hizo con un subagente de solo lectura que leyó el `SKILL.md` y aplicó su modo `--review`.
- Entorno (solo local, sin tocar archivos del proyecto): `uv` con `pip --user`, `.venv` con Python 3.12, `uv sync --all-packages`, `npm ci`, y en el venv `tzdata`, `aiosqlite` y las extras `otel` de `tukit_comun`.

## 3. Limpieza

- Eliminado `docs/memoria/x5.py` (lee `/tmp/s6/...docx`, sin referencias).
- Eliminado el segundo `_token_bearer` de `operacion` (cuerpo idéntico al primero).
- Los dos helpers de token idénticos (comercio, inteligencia, operacion, identidad) pasan a `tukit_comun/autenticacion.py::token_bearer`, con test parametrizado. El del gateway se deja porque devuelve `or None`.
- `.gitignore` ampliado: coverage, htmlcov, `*.bak`, `*.orig`, `*.swp`, `Thumbs.db`, `.claude/settings.local.json`.
- Se corrigieron referencias obsoletas en comentarios y docs vivos.
- Comentarios: no se retiró ninguno por redundante; el repositorio no tenía comentarios de ruido detectables y los largos documentan decisiones, así que se conservaron.

## 4. Refactorización arquitectónica

- `catalogo/consulta.py` (ruta de servicio) ya no importa de los CLI: lee de `extraccion.py` y `clasificacion.py`, nuevos módulos puros. `transcripcion.py`, `cargador*.py`, `demanda_atributos.py` y `routers/admin.py` también.
- `tests` y `ensayos` que dependían de importaciones accidentales ahora importan de la fuente real (p. ej. `PerfilKit` desde `modelos`).

## 5. Modularización

| Antes | Después | Responsabilidad |
|---|---|---|
| `optimizador.py` | `optimizador/` | `tipos`, `candidatos` (filtros duros y heurística por perfil), `preferencias`, `frente` (enumeración exacta y NSGA-II), `lineas`, `recomendacion` (MAUT), `armado` |
| `trabajos.py` | `trabajos/` | `base`, `pipeline`, `lectura`, `solicitudes`, `revision`, `versiones`, `cambios`, más `formas` y `anclas` |
| `enriquecer.py` | `extraccion.py` + `enriquecer.py` | reglas puras frente a lote/CLI |
| `descubrir.py` | `clasificacion.py` + `descubrir.py` | reglas puras frente a revisión y alta |
| `cliente-http.ts` | `normalizar.ts` + `cliente-http.ts` | normalizadores puros frente a `ClienteApi` |

Los cortes salen de las secciones del código y de un grafo de dependencias sin ciclos. Los módulos se generaron con scripts que conservan los cuerpos y sus comentarios. Los paquetes reexportan su API, de modo que las importaciones existentes siguen funcionando. Las fórmulas, pesos, umbrales y semillas no se tocaron.

## 6. Validación

| Comprobación | Línea base | Final |
|---|---|---|
| `pytest arquitectura` | 75 OK, 1 skip | 75 OK, 1 skip |
| pytest (libs, servicios, ensayos) | 2.984 OK | 2.992 OK (+6 `token_bearer`, +2 fachadas) |
| `ruff check .` | 696 | 696 (ninguno nuevo) |
| `ruff format --check` | 68 sin formatear | 68 |
| `mypy tukit_comun` | OK | OK |
| TS: tests, `tsc`, `eslint` | 345 OK, 0 errores, 2 avisos | 345 OK, 0 errores, 2 avisos |
| Regresión del optimizador | 144 escenarios, SHA `9d07b149…` | mismo SHA, antes y después de cada cambio |

El golden usa kits, frente de Pareto, recomendación, filtros y consolidación sobre 144 escenarios con semilla fija. Cubre el camino NSGA-II. Vive solo en el scratchpad, no en el repositorio.

Errores preexistentes (idénticos a la línea base, no introducidos):
- `test_catalogo.py::test_un_precio_cerrado_no_bloquea_al_siguiente`: dependiente del reloj; pasa si se ejecuta solo.
- `ensayos/calibracion/test_acuerdo.py` y `test_aumentacion.py` (1 fallo + 3 errores): falta `ensayos/calibracion/datos/centroides.npz`.
- `npm run build:admin`: compila y pasa TypeScript, pero Next 16.4.3 aborta con `SecurityFatalError` por vulnerabilidad conocida. No se verificó sobre `main`. `build:web` OK.
- 696 avisos de ruff y 68 archivos sin formatear.
- `aiosqlite` y `tzdata` no están declarados como dependencias de desarrollo y hacen falta para correr pytest en Windows.

No validado: los tests `rabbitmq` y `redis` (sin servicios levantados), `nl2c_vivo` (Gemini), `make bd-deriva` y las migraciones (Postgres), y el comportamiento en ejecución de las apps.

Revisión independiente (AI Slop Cleaner `--review`, solo lectura). Verificó con AST que las definiciones se conservan: 73 en `optimizador`, 104 en `trabajos`, 53 en `enriquecer` y 50 en `descubrir`, todas una vez y con cuerpos idénticos, y no encontró ciclos. Hallazgos y resolución:
- Texto corrupto (UTF-8 doble codificado) en 7 comentarios, causado por mis scripts de corte: **corregido**.
- Reexportaciones de fachada sin uso (23 en `optimizador`, 39 en `trabajos`): **podadas**.
- `_token_del_encabezado` duplicado en identidad: **consolidado**.
- Test de resolución de fachadas: **añadido**.
- Finales de línea mezclados: **normalizados** a CRLF.
- Tests que importaban reglas puras desde `enriquecer`: **repuntados** a `extraccion`.

## 7. Pendientes

Conservado por incertidumbre:
- `tukit_comun/dependencias.py` (sin uso en producción; ADR 0019 lo describe).
- `catalogo/canonicos.py` (backfill sin referencias).
- `catalogo/admin_http.py` (shim usado por 4 tests y `api.py`).
- `catalogo/admin.py` (UI heredada con SQL crudo, pero enlazada desde `make bd-admin`).
- `docs/memoria/main.pdf` (ignorado pero versionado a propósito).
- Los PDF, imágenes y resultados en `docs/` y `ensayos/`.

Requiere revisión manual:
- Los parches de test sobre `trabajos.ver` y `ClienteIdentidad` solo afectan a los llamadores directos. Un test que llegue a `lectura.py` seguiría usando el cliente real. En producción no hay efecto.
- Dos copias de `logger` en `trabajos/anclas.py` y `lectura.py`: los nombres de logger cambiaron a `tukit_inteligencia.trabajos.<módulo>`. `caplog` por el padre sigue capturándolos.
- `.claude/` queda sin ignorar: la carpeta de la skill se commiteará. Confirmar que es lo deseado.
- La matriz de CI, el manifiesto y el README siguen nombrando `servicios/ingesta`, que no existe.
- Dependencia de Next vulnerable (bloquea `build:admin`).

Recomendaciones futuras, sin hacer en esta intervención por riesgo o falta de pruebas:
- Mover el SQL de `trabajos/` a `repositorios/trabajos.py`.
- Sacar `routers/nl2c.py:164` (SQL directo en el router) y `routers/comercio.py:558` (captura `httpx.HTTPError` en el router).
- Unificar el transporte de `nl2c._llamar_gemini` con `gemini.py`.
- Compartir `escuchar_cola`/`main` de los 4 `supresion.py` y el andamiaje de workers en `tukit_comun`.
- Partir `routers/admin.py` (2.417 líneas), `routers/inteligencia.py` (1.771), `FormularioEmpezar.tsx` y `VistaKits.tsx`, y dividir `ClienteApi` por dominio.
- Unificar los dos clientes Nominatim de `apps/web` y `apps/admin`.
- Normalizar quitar-tildes sobre `tukit_comun/texto.py` (17 copias; hay que comprobar NFD frente a NFKD caso por caso).
- Tests unitarios para `normalizar.ts`.

## 8. Estado final

- Rama: `refactor/limpieza-tukit`, con cambios sin commitear. 40 archivos modificados o eliminados respecto a `HEAD`, más 24 nuevos sin seguimiento. `main` y `origin/validacion/oe5` intactas.
- Cambios sin commit: `optimizador.py` y `trabajos.py` figuran como borrados en el índice.
- Funcionamiento: las suites ejecutables dan los mismos resultados que antes, salvo los preexistentes listados arriba. El comportamiento de los algoritmos se conserva según la comparación del optimizador.
