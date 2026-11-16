# Cierre final de la memoria: contenido del equipo, notas del jurado, autocontenido y redacción propia

> **Para agentes:** SUB-SKILL REQUERIDA: superpowers:subagent-driven-development (recomendada) o superpowers:executing-plans. Los pasos usan casillas (`- [ ]`). Ultracode está activo: cada tarea con más de un archivo corre como Workflow.

**Objetivo:** dejar la memoria (`tukit/docs/memoria`, rama `validacion/oe5`, base `6a89666`) lista para entregar.
- Integra el contenido del equipo que falta: las pruebas de Rey, el negocio de Daniel y el desarrollo y el diseño de Juan y Dani.
- Atiende cada nota del jurado.
- Se lee sola, sin ADR, rutas ni repositorios.
- Tiene referencias verificadas, gráficas legibles y redacción con la voz del equipo.

**Arquitectura:** seis tareas en secuencia, y la usuaria ve el resultado de cada una antes de pasar a la siguiente.
1. Inventario.
2. Contenido del equipo.
3. Notas del jurado.
4. Autocontenido.
5. Referencias y gráficas.
6. Redacción y cierre.

Cada tarea de edición corre como un Workflow con una editora por archivo y una verificadora adversarial. Después se compila y se miden las páginas.

**Stack:** LaTeX (`bash compilar.sh` dentro de `docs/memoria`, con `timeout 300`), Workflow (opus para editar y verificar, sonnet para contar), Python para las ediciones, Firecrawl CLI para las referencias y `uv run --with openpyxl` para la encuesta.

**Spec:** se arma con estas fuentes:
- El mensaje de la usuaria del 6-nov-2026, 13:08, con sus citas de Rey y Daniel.
- La foto de las notas del jurado (transcrita abajo).
- La versión del equipo en `~/Downloads/memoria_actualizada.zip`, que es idéntica a `memoria_actualizada (1).zip`.
- El informe `docs/memoria/revision/diff-equipo-2026-11-06.md`.
- La rúbrica `~/Downloads/Formato-evaluación-TG-ISIST-v4(Sustentación) (1).csv` (latin-1).

## Restricciones globales
- **Tope duro:** cuerpo ≤ 60 páginas. Se mide como la página de REFERENCIAS en `main.toc` menos 1, así que REFERENCIAS tiene que quedar en 61 o menos. Hoy está en 61.
- **Medición del cuerpo:**
  - `python3 -c "import re;t=open('main.toc',encoding='latin-1').read();print(re.findall(r'REFERENCIAS\}\{(\d+)',t)); l=open('main.log','rb').read().decode('latin-1');print(l.count('\n! '),l.count('Overfull'),l.count('undefined'))"`
  - Lo esperado es `['≤61']`, con 0 errores y 0 indefinidas. El Overfull que ya existe se puede quedar.
- **Páginas:** página del PDF = página del cuerpo + 12. Una página con poco texto se detecta con `pdftotext -f N -l N -layout main.pdf - | rg -c '\S'` (menos de 30 líneas).
- **Cifras:** no se inventa ninguna cifra, nombre, fecha ni cita. Las cifras vigentes vienen de tres fuentes:
  - `sections/cifras_calibracion.tex` (generado; no se edita a mano);
  - `docs/entrega/HECHOS_CANONICOS_DOCS.md`;
  - `docs/negocio/PUNTO_EQUILIBRIO.md`.
- **Conflicto entre fuentes:** si una cifra del equipo choca con la vigente, gana la vigente y la discrepancia va a `revision/conflictos-equipo.md`.
- **Objetivos:** los OE se quedan literales a la VFP v4 y los cinco quedan «Cumplido». La metodología de cada OE se sigue nombrando al inicio de su bloque:
  - OE1: Design Thinking + IEEE 830.
  - OE2: RUP + IEEE 1016 + ATAM.
  - OE3 y OE4: SCRUM + CRISP-DM.
  - OE5: ISO/IEC 25010 + protocolo preregistrado.
- **Autocontenido:** en el cuerpo no quedan:
  - ADR (`ADR 00xx`);
  - rutas (`\path{}`, `docs/…`, `.md`, `.py`);
  - commits (`b6b6fe7`);
  - comandos (`make arriba`);
  - las palabras «repositorio» o «monorrepositorio» como referencia;
  - remisiones al anexo que el lector necesite para entender.

  La decisión se explica en una frase en el lugar donde se usa. En el anexo solo queda material de consulta.
- **Privacidad:** sin nombres de acudientes, direcciones ni teléfonos. Las citas se identifican con ACU-0x. No se vuelve a contactar a los padres.
- **Edición:** con Python (reemplazo que ocurra exactamente una vez) o con Edit; nunca con `sd`, que daña las barras invertidas.
- **Git:**
  - Commits como `git -c user.name=MapaRuiz -c user.email=rodriguezr.mp@javeriana.edu.co`, sin atribución de IA.
  - `git add -f docs/memoria/main.pdf`.
  - No se incluyen `apps/admin/AGENTS.md` ni `docs/validacion/oe5/oe5_ronda2/CHECKLIST_LLAMADAS_HOY.md`, que no son de este trabajo.
  - Se pregunta antes de cada push.
- **Sincronizar** al terminar cada tarea: `rsync -a --exclude council/ --exclude '*.aux' --exclude '*.log' tukit/docs/memoria/ memoria-final/` (desde la raíz TUKIT).
- **Estilo:** primero la redacción del equipo donde corrigió, después las reglas de la memoria `team-writing-style-rules`, y por último `thesis-writing-style-dani` (el modelo es `sections/analisisProblema.tex`). No se usan los documentos secundarios (SDD, ATAM, SRS, ADR) como guía de estilo.

## Notas del jurado (foto del 6-nov, transcrita; las páginas son del PDF que leyó el jurado, así que se ubican por contenido)
| # | Nota (literal o casi) | Pág. | Qué pide |
|---|---|---|---|
| J1 | «Umbral no calibrado → decide si va al humano» | — | Explicar claramente que τ sí se calibró (405 pares, \calTauP{}) y cómo decide qué renglón va a revisión humana |
| J2 | «sin calibrar» | 37 | Encontrar y corregir toda frase que diga o insinúe «sin calibrar» |
| J3 | «microservicios vs auditoría» | — | Separar el diseño final de la auditoría de la versión anterior; no mezclar «defectos de los microservicios anteriores» con el sistema construido |
| J4 | «diseño del NSGA: crudo, malo, vacío(?)» | — | Describir el diseño de NSGA-II: codificación del individuo, operadores, población, generaciones, criterio de parada y cómo se eligen los 2–4 kits del frente |
| J5 | «demasiado sincero: "faltan temas", "no se hizo", "pendiente"» | — | Sacar del cuerpo el tono de pendiente. Los límites se dicen una vez, como alcance, en Limitaciones (VIII); se quitan del cuerpo los `\pendienteEvidencia{}` y los «queda pendiente» |
| J6 | «viajan datos a Google» | — | Explicar qué datos van a Gemini, por qué (lectura de la lista), con qué protección (minimización, sin nombre legal, el apodo cifrado) y qué falta (depurar el nombre en el documento), en un solo lugar |
| J7 | «Conclusiones = caracterización de 17 colegios… 25 conceptos ¿es aporte?» | 10/4 | Las conclusiones dicen el aporte, no repiten la caracterización |
| J8 | «Redacción atemporal» | 11 | Tiempos verbales coherentes; sin «hoy», «ya», «a la fecha» ni fechas de trabajo innecesarias |
| J9 | «histórico exagerado» / «Estilo del TG: no describe el histórico» | 13 | Recortar la historia v0 (14→7→6 servicios) a lo mínimo; el TG describe el sistema final. Esto **reemplaza** la memoria `v0-architecture-is-method-narrative`, que habrá que actualizar |
| J10 | «Dicen que Objetivo General no se cumple → OE5» | 41 | Argumentar en VII.6 y VIII, con la evidencia, por qué se cumple el OG (seis acudientes llegaron a un pedido pagado; C1 y C2), sin cambiar cifras |
| J11 | «Cómo se modela "personaje" matemáticamente — revisar modelos» | 44, 14 | Dar la fórmula del objetivo de personaje, la de los demás objetivos y la de MAUT, con símbolos definidos |
| J12 | «diagrama de componentes / diagrama de despliegue» | 33 | Un diagrama de componentes distinto del de despliegue; los dos legibles |
| J13 | «Kappa Cohen» | 35/36 | Explicar en lenguaje llano qué mide el kappa, entre quiénes se comparó y cómo se lee 0,7331 |
| J14 | «11 de 12 fallaron…» | 42 | Ubicar la frase y explicarla o reformularla para que no se lea como un fracaso sin contexto |
| J15 | «ladrillo total» | — | Bloques de texto densos: partir párrafos, poner figuras o tablas resumen y guiar al lector |
| J16 | «Cap 4 = demasiadas cifras sueltas, poner una tabla de referencia» | — | El capítulo IV junta sus cifras en una tabla y el texto la cita |
| J17 | «Corpus crudo – filtrado – curado» | — | Una figura o tabla del embudo del corpus: crudo (3.610) → analizable (3.608) → formas (1.451) → conceptos (99 → 149, 145 activos) → corpus final (4.719 con 1.109 libros, licencias y uniformes) |
| J18 | «documento no es autocontenido, parece doc de auditoría; ejemplo…» | — | Ver Tarea 4; agregar un ejemplo trabajado de una lista real (anonimizada) que recorra las etapas |

## Hechos ya verificados el 6-nov (no volver a buscar)
- **Faro:** está confirmado.
  - En las transcripciones `/tmp/tukit-oe5/v1.txt` [01:40] y [13:17] y `/tmp/tukit-oe5/v2.txt` [08:23] y [11:46–12:15], los acudientes nombran «el Faro» como papelería barata junto a Panamericana, Éxito, Comercial Papelera y San Victorino; «los compro en el Faro».
  - La glosa de `oe5.tex` («el comercio con el que esa acudiente compara precios») está bien. Si se quiere más precisa: «una papelería de precios bajos donde esa acudiente suele comprar».
  - `/tmp` puede haberse borrado; si pasó, la glosa actual se deja.
- **Zips:** `memoria_actualizada.zip` y `memoria_actualizada (1).zip` son idénticos (`cmp`). La versión del equipo está extraída en `/tmp/rey_zip.4smu`; si no existe, se vuelve a extraer en un directorio nuevo.
- **Pruebas de Rey:** su sección es `\subsection{Verificación de la versión evaluada}` en `sections/resultados.tex` del zip, líneas ~220-286, con la auditoría de seguridad en ~287-355. Usa cifras más viejas que las vigentes:

  | Dato | Versión de Rey | Vigente (`calidad.tex`, HECHOS) |
  |---|---|---|
  | Pruebas | 1.647 | 2.542 |
  | Cobertura | 72,43 % | 54 % catálogo / 98 % puerta |
  | Hallazgos | 78 (14 altos) | 85 (16 altos) |

  - Lo que hay que traer de Rey es la **estructura y la explicación**:
    - el plan de diez fases y cada nivel de prueba (unitarias, integración, funcionales con oro, adversariales de IA, resiliencia, degradación, carga, telemetría);
    - la matriz de 60 metas;
    - el disyuntor (26,3 s frente a 30 s de ESC-R2);
    - las tres caídas que fallaron y cómo se corrigieron.
  - Cada cifra se toma de la fuente vigente si existe. Si solo existe la de Rey, se usa con su fecha y su versión.
- **Dónde viven las pruebas de Rey (buscado el 6-nov):** el texto del zip es solo la narración. El material de verdad está fuera de la memoria:
  - Rama `origin/a/fases-2-6-oe5` del repo FINAL, con commits de Juan Enrique Rozo Tarache hasta el 4-nov:
    - 194 archivos y 102 de prueba (`test_*`, `*.spec.mjs`);
    - `ensayos/adversariales` (ADV-01…14, incluidos los de NL2C), `ensayos/integracion` y `ensayos/e2e`;
    - los conjuntos de oro `datos/golden/` (G01-G10, con su `README.md` y `oracle.json`);
    - las e2e de Playwright en `apps/{web,admin}/e2e/`;
    - la CI en `.github/workflows/ci.yml`.
  - Rama `origin/a/fases-2-6-integracion`, del 11-oct, que es la corrida de las fases 2-6 sobre la integración del 8-oct, y rama `origin/qa`, que trae el fake-gemini.
  - Hay que leerlas con `git show <rama>:<ruta>`, sin hacer checkout ni merge.
  - El repo `github.com/Tukit-Col/Tukit-QA` existe, pero la cuenta de esta máquina no tiene acceso. Probablemente es el `./qa` con el catálogo de ensayos, la matriz de caos, las fases 7-9 de Daniel y el «informe de pruebas de la entrega». **Hay que pedirle acceso a Rey**, o un zip.
  - En disco hay tres fuentes más:
    - `~/Downloads/pruebas-qa-tukit.html`: el tablero de fases, hechas y por hacer;
    - `docs/informes/calidad/hallazgos_qa_oficial.csv` y `carga_mac_2026-11-05/`;
    - `../_archivo/2026-11-05/borradores_arquitectura/Arquitectura/QA_Tukit.tex`: el plan de atributos de calidad (8.375 palabras).
  - Para cada cifra de Rey hay que contar en esas fuentes: pruebas con `pytest --collect-only -q` sobre la rama, sin red; gold sets; casos ADV; hallazgos en el CSV.
  - La `calidad.tex` actual ya cubre los niveles de prueba en un párrafo. Lo que falta, y lo que Rey reclama, es la profundidad:
    - una tabla por nivel (qué se probó, con qué datos, cuántas pruebas y cuál fue el resultado);
    - los conjuntos de oro;
    - los ataques adversariales a la IA;
    - la matriz de requisitos no funcionales;
    - las fases 7-9.
- **Negocio de Daniel:** es `\subsection{Validación financiera}` (`\label{sec:viabilidad}`) en `resultados.tex` del zip, líneas ~388+, con la tabla `tab:proyeccion` a tres años.
  - Usa estos supuestos: $180.000 por kit, 15 %, contribución de $19.500, equilibrio en 770 kits y kits de 1.500 / 8.000 / 25.000 por año.
  - La memoria vigente dice $29.353 por kit Ahorrador y 41 kits con la infraestructura del piloto, de `docs/negocio/PUNTO_EQUILIBRIO.md` y `Nestle/scripts/flujo_caja.py`.
  - Primero hay que leer `PUNTO_EQUILIBRIO.md` y decidir con la usuaria cuál se queda (Tarea 2, paso 3).
- **Imágenes del equipo:** están en `/tmp/rey_zip.4smu/img/{arquitectura,desarrollo,graficas,modelo,negocio}`; las de negocio ya están copiadas en `docs/memoria/img/negocio/`.
- **Turnitin** (guías oficiales, consultadas con Firecrawl el 6-nov):
  - El modelo solo evalúa «texto que califica», es decir, oraciones de prosa en formato largo; las tablas, las listas y el código no cuentan.
  - Desde ago-2025 detecta texto de IA modificado por un «AI bypasser».
  - Desde ago-2026 junta «IA parafraseada» con «IA generada» en una sola categoría.
  - El 18-ago-2026 reentrenó el modelo de inglés con texto ya pasado por humanizadores.
  - **Conclusión:** los humanizadores automáticos (QuillBot, StealthGPT, Undetectable, etc.) cambian palabras por sinónimos, y Turnitin los marca. Además, usarlos es un problema de integridad.
  - Lo que distingue un texto humano es estructural:
    - largo de oración variable;
    - párrafos que no siguen el molde tema → tres apoyos → transición;
    - conectores no repetidos;
    - detalle concreto propio, como cifras, nombres de colegios u observaciones de las sesiones;
    - la voz del autor.
  - Fuentes: https://guides.turnitin.com/hc/en-us/articles/22774058814093 , https://guides.turnitin.com/hc/en-us/articles/27251688507533
  - La memoria está en español, y Turnitin documenta el soporte de idioma de su detector. Hay que verificar en la guía si cubre español antes de afirmar nada.

## Foco de revisión (lo más probable que falle)
1. **Superar las 60 páginas** al traer el desarrollo del equipo (~10.900 palabras frente a ~8.800 de VI + optimización + NL2C). Cada capítulo tiene un presupuesto (Tarea 1) que se respeta.
2. **Una cifra vieja del equipo** que reemplaza a una vigente: 1.647 pruebas, 78 hallazgos, 770 kits, AUC 0,961, «diez tiendas», «340 %». `cifras.py diff` y la verificadora lo atrapan.
3. **Quitar los ADR y las rutas sin dejar la razón de la decisión.** Cada ADR quitado se reemplaza por media frase con el porqué.
4. **Un «humanizado» que cambie un alcance**, por ejemplo «en 40 listas» frente a «en 32», o que borre un límite de un OE.
5. **Una referencia que no existe o que no dice lo que se le atribuye**, por ejemplo `sun_product-aware_2024`, que ya se quitó; Gray está verificada; Ley 1269 está verificada.

---

### Tarea 1: Inventario y presupuesto de páginas (solo lectura, Workflow con sonnet)

**Archivos:** solo se leen `sections/*.tex`, `/tmp/rey_zip.4smu/sections/*.tex` y `main.pdf`. **Salida:** `docs/memoria/revision/cierre-final/inventario.md`.

- [ ] **Paso 1:** contar en el cuerpo, por archivo:
  - ADR: `rg -c "ADR"`;
  - rutas: `rg -c '\\path\{|docs/|\.md|\.py|make '`;
  - remisiones al anexo: `rg -c -i "anexo"`;
  - `\pendienteEvidencia`;
  - las frases de J5: `rg -n -i "pendiente|no se hizo|no se midió|no se ejecutó|faltan?"`.
- [ ] **Paso 2:** ubicar cada nota J1–J18 en el PDF actual (página del cuerpo y archivo:línea) con `rg` de una frase clave. Si una nota ya está atendida, se marca «ya resuelta» con la cita.
- [ ] **Paso 3:** alinear las secciones del equipo con las actuales en una tabla: desarrollo/diseño del zip → `desarrolloSolucion.tex`, `optimizacion.tex`, `nl2c.tex`, `disenoSolucion.tex`.
  - Para cada subsección, una de tres acciones: «traer redacción», «traer estructura» o «ya está».
  - Se toma como base el informe `revision/diff-equipo-2026-11-06.md`.
- [ ] **Paso 4: presupuesto de páginas (total 60).** Punto de partida: I 1-2, II 3-9, III 10-14, IV 15-20, V 21-30, VI 31-46, VII 47-56, VIII 57-60.
  - Propuesta:

    | Capítulo | Páginas |
    |---|---|
    | I | 2 |
    | II | 6 |
    | III | 5 |
    | IV | 6 |
    | V | 10 |
    | VI | 16 |
    | VII | 11 |
    | VIII | 4 |

  - Lo que se agrega (pruebas de Rey, negocio y fórmulas) se paga con lo que se quita: historia v0, auditoría, cifras sueltas, ADR y frases de pendiente.
- [ ] **Paso 5:** abrir `inventario.md` en MarkdownLyt y mostrárselo a la usuaria.

### Tarea 2: Contenido del equipo (Workflow: una editora por archivo, opus; verificadora adversarial)

**Archivos:** se modifican `sections/{calidad,resultados,desarrolloSolucion,disenoSolucion,optimizacion,descripcionGeneral}.tex` y `bib/tukit.bib`, y se crea `revision/conflictos-equipo.md`.

- [ ] **Paso 1: foto de cifras antes de editar.** Se usa `python3 revision/e2e-2026-11-06/cifras.py snapshot > revision/cierre-final/antes.json`. Si el script no existe, se escribe uno que extraiga el multiconjunto de números `\d+([.,]\d+)*`, macros `\cal*` y claves `\cite`/`\ref`, por archivo.
- [ ] **Paso 2: pruebas de Rey en `calidad.tex`.** Se reescribe `\subsection{Verificación del sistema integrado}` con la estructura de Rey. Se mantiene el molde Pregunta/Método/Métrica/Resultado/Lectura, pero con párrafos más cortos (J15).
  - Contenido:
    - una tabla de los niveles de prueba: nivel, qué verifica, cuántas pruebas, resultado;
    - la carga;
    - la degradación con el disyuntor;
    - las tres caídas corregidas, contadas en presente;
    - la seguridad.
  - Cifras vigentes donde existan.
  - El estado se explica sin «pendiente» (J5): lo que no se corrió va una vez en VIII Limitaciones.
- [ ] **Paso 3: negocio de Daniel.** Antes de editar, se le pregunta a la usuaria (AskUserQuestion) qué cifras se usan. Opciones:
  - (a) las vigentes de `PUNTO_EQUILIBRIO.md` ($29.353, 41 kits), con la tabla a tres años **recalculada** con el script;
  - (b) la proyección de Daniel tal cual, declarada como escenario del equipo y reconciliada en una frase con la vigente;
  - (c) las dos, como escenario piloto y escenario a escala.

  Con la respuesta se agrega `\subsection{Validación financiera}` en VII, con la `\label{sec:viabilidad}` que hoy está en II; se mueve el label y se quita el duplicado. La tabla tiene como mucho 8 filas.
- [ ] **Paso 4: desarrollo y diseño de Juan y Dani.**
  - Para cada fila «traer redacción» del inventario, se reemplaza el párrafo actual por el del equipo, corregido con las cifras vigentes.
  - Para «traer estructura», se reordenan las subsecciones de VI siguiendo el recorrido del acudiente del equipo (registro → carga → procesamiento → kits → asistente → pago → seguimiento → privacidad → revisión → catálogo → logística).
  - En V se traen las vistas lógica, de tiempo de ejecución, de datos y física del equipo, con sus figuras de `/tmp/rey_zip.4smu/img/` copiadas a `docs/memoria/img/`.
  - En ningún caso se trae «Comparación de alternativas» completa, porque ya está en VII.
- [ ] **Paso 5: verificadora adversarial (opus).** Lee `git diff` por archivo y marca:
  - cifras que cambiaron sin fuente;
  - métodos o límites de un OE que se perdieron;
  - ADR o rutas nuevas.

  Lo marcado se corrige.
- [ ] **Paso 6: compilar y medir.** Para pasar: REFERENCIAS ≤ 61, 0 errores y 0 indefinidas. Si se pasa de 61, se recorta según el presupuesto de la Tarea 1, nunca un método ni un límite.
- [ ] **Paso 7: commit.** Mensaje: `Memoria: pruebas de integración y unitarias (Rey), validación financiera (Daniel) y desarrollo/diseño del equipo`. Después, sincronizar.

### Tarea 3: Notas del jurado J1–J18 (Workflow: editora por archivo, opus; verificadora por nota)

**Archivos:** los que ubicó la Tarea 1, paso 2.

- [ ] **Paso 1: aplicar cada nota con la acción de la tabla.** Además:
  - **J11:** se escribe en `optimizacion.tex` la definición formal con símbolos y se explica cada uno en la misma frase.
    - Para cada renglón $i$ y producto $p$: costo $c_p$, fidelidad de marca $f_{ip}$, disponibilidad $d_p$ y personaje $\phi_p = 1$ si el producto tiene el personaje pedido.
    - La función MAUT es $U = \sum_k w_k\,u_k$, con los pesos de la P21.
    - Se toma de `optimizacion.tex` y del código `servicios/inteligencia/` (`rg -n "personaje" servicios/inteligencia | head`). **No se inventa la fórmula:** si el código usa otra, se escribe la del código.
  - **J4:** los parámetros reales de NSGA-II se leen del código (`rg -n "pop_size|n_gen|NSGA2|crossover|mutation" servicios/inteligencia`).
  - **J12:** el diagrama de componentes se dibuja en TikZ con la paleta C4 de `img/arquitectura/c4-contenedores.tex`. Se renderiza a 300 dpi para revisar que ningún rótulo pise una línea.
  - **J17:** el embudo es una figura TikZ horizontal con 5 cajas y conteos.
  - **J16:** la tabla de referencia del cap. IV junta las cifras de la encuesta y del corpus, y el texto la cita en lugar de repetir cada cifra.
  - **J18:** el ejemplo trabajado se toma de una lista del corpus (anonimizada) y muestra 3 renglones a través de percepción → normalización → resolución → kit. Si no cabe en el cuerpo, va como figura compacta.
- [ ] **Paso 2: una verificadora por nota (sonnet).** Recibe la nota, la cita del antes y la del después, y responde `{resuelta: bool, por_que}`. Las que salgan `false` se vuelven a editar.
- [ ] **Paso 3: compilar, medir y hacer commit.** Mensaje: `Memoria: atender las notas del jurado`. Después, sincronizar.

### Tarea 4: Autocontenido (Workflow: editora por archivo)

- [ ] **Paso 1: quitar ADR, rutas, commits y comandos del cuerpo.**
  - Cada `(ADR 00xx)` se borra. Si la frase no dice el porqué de la decisión, se agrega media frase con la razón, tomada del ADR en `docs/arquitectura/adr/`.
  - La tabla de decisiones registradas de V se vuelve «Decisiones de diseño» sin números de ADR: decisión, alternativa descartada y por qué.
- [ ] **Paso 2: remisiones al anexo.** Lo que se necesita para entender vuelve al cuerpo en forma compacta, o se dice en una frase. Al anexo solo se remite material de consulta: el glosario, las constantes, los instrumentos del OE5 y el detalle de la calibración.
- [ ] **Paso 3: guiar al lector (J15, J18).**
  - Cada capítulo abre con 2-3 frases: lo que traíamos, lo que se hace aquí y lo que se encontró. Cierra con una frase que lleva al siguiente.
  - Cada término técnico se define en su primer uso: PE-04, ML-09, DP-03, CO-01, ESC-D4, hipervolumen, MAUT, RTLX, SUS, NPS, kappa, MRR, F1.
- [ ] **Paso 4: comprobar.**
  - `rg -c "ADR|\\\\path\{|docs/|b6b6fe7|make " sections/{introduccion,descripcionGeneral,contextoProyecto,analisisProblema,disenoSolucion,desarrolloSolucion,optimizacion,nl2c,resultados,calidad,oe5,conclusiones}.tex` debe dar 0 en todos.
  - `rg -c -i "anexo"` debe quedar en 10 o menos, solo de consulta.
  - Compilar, hacer commit y sincronizar.

### Tarea 5: Referencias y gráficas (Workflow: sonnet con Firecrawl, en lotes de 10)

- [ ] **Paso 1: listar las referencias citadas.** Con `rg -o '\\citep?\{[^}]+\}' sections | ...`, se separan las claves y se cruzan con `bib/tukit.bib`.
- [ ] **Paso 2: verificar cada referencia.** Una agente por lote verifica con `firecrawl search`/`scrape`: que exista, que coincidan autor, año, título y venue, que la URL o el DOI respondan y que **la frase de la memoria diga lo que la fuente dice** (cita y fuente lado a lado).
  - El binario: `/Users/mariapaula.rodriguez/.devbar/pkgs/node/22.23.4/node-v22.23.4-darwin-arm64/bin/firecrawl` (puede no estar en el PATH).
  - Salida: `revision/cierre-final/referencias.json` con `{clave, existe, metadatos_ok, afirmacion_ok, url, nota}`.
  - Se corrige el `.bib`. Una referencia que no se pueda verificar se quita junto con su frase, o se le pregunta a la usuaria.
- [ ] **Paso 3: gráficas humanas.**
  - Se revisa cada figura del cuerpo con un render a 300 dpi (`pdftoppm -r 300 -f N -l N`).
  - Se revisa que:
    - el texto de la figura se pueda leer al tamaño de impresión (≥ 7 pt);
    - haya un mensaje por figura;
    - el pie diga qué mirar;
    - se usen coma decimal y Latin Modern;
    - ningún rótulo pise otro.
  - Las de benchmarks se regeneran con `ensayos/calibracion/graficas.py`, y las TikZ se ajustan.
  - Se prefiere una figura a una tabla de cifras (memoria `memoria-e2e-council-decisions`).
- [ ] **Paso 4: compilar, hacer commit y sincronizar.**

### Tarea 6: Redacción con la voz del equipo y cierre

**Por qué no basta con pasar `/humanizer` a cada párrafo:** Turnitin detecta texto parafraseado por herramientas, y un pase automático tiende a dejar otro molde uniforme. Lo que funciona y además es honesto es que el texto sea de verdad del equipo: su redacción donde corrigió, su detalle concreto y su ritmo.

- [ ] **Paso 1: medir el molde.** Un script en `revision/cierre-final/ritmo.py` reporta, por párrafo de prosa:
  - el número de oraciones;
  - la desviación estándar del largo de oración en palabras (bandera si es < 6);
  - los conectores repetidos en el capítulo (bandera si uno aparece > 4 veces: «Además», «Por eso», «De modo que», «A partir de», «Para ello»);
  - las aperturas repetidas;
  - las marcas de la lista: `no solo|sino que|—|–|crucial|fundamental|robust|cabe destacar|es importante|en definitiva|pilar|potenciar|clave`;
  - el molde «X, no Y».

  Una prueba corta del script corre con un párrafo sintético de oraciones iguales y otro variado.
- [ ] **Paso 2: reescribir solo los párrafos con bandera (Workflow, opus, una editora por capítulo).** La prioridad es:
  1. usar la frase del equipo si existe en el zip;
  2. agregar detalle concreto ya presente en las fuentes (colegio, tarea, cita ACU-0x, cifra con su muestra);
  3. variar el largo de oración y la estructura del párrafo;
  4. aplicar las reglas del skill humanizer (§1-§8) en modo embebido.

  Ninguna editora agrega cifras.
- [ ] **Paso 3: lectura humana.** Se genera `revision/cierre-final/para-leer-en-voz-alta.md` con los 15 párrafos de mayor puntaje residual. **Le toca a la usuaria y al equipo** reescribirlos a mano con sus palabras, porque es la parte que ninguna herramienta debe hacer por ellos. Se abre en MarkdownLyt.
- [ ] **Paso 4: política de la Javeriana.** Se busca con Firecrawl la política de uso de IA generativa en trabajos de grado de la Facultad de Ingeniería. Si pide declarar el uso, se propone a la usuaria un párrafo de declaración para los preliminares; no se agrega sin su OK.
- [ ] **Paso 5: verificación final.**
  - `bash compilar.sh`:
    - REFERENCIAS ≤ 61;
    - 0 errores y 0 indefinidas;
    - páginas con menos de 30 líneas solo al final de capítulo.
  - `cifras.py diff revision/cierre-final/antes.json`: sin pérdidas. Las cifras nuevas son solo las del equipo, listadas con su fuente.
  - El conteo de marcas del paso 1 baja respecto de `6a89666`.
  - Autocontenido: 0 ADR, rutas y commits en el cuerpo.
- [ ] **Paso 6: cierre.**
  - Commit `Memoria: redacción final con la voz del equipo` y `git add -f docs/memoria/main.pdf`.
  - Sincronizar `memoria-final/`.
  - Preguntar antes del push a `validacion/oe5`.
  - Actualizar la memoria `v0-architecture-is-method-narrative` con la nota J9 del jurado, que pide recortar la historia.
  - Actualizar `revision/PREGUNTAS_SUSTENTACION.md` con preguntas derivadas de J1–J18.

## Verificación final
- Compila; el cuerpo tiene ≤ 60 páginas y hay 0 referencias rotas.
- Cada nota J1–J18 queda resuelta o explicada en `revision/cierre-final/jurado.md`.
- `referencias.json` sin `existe:false` ni `afirmacion_ok:false`.
- 0 ADR, rutas y commits en el cuerpo.
- `conflictos-equipo.md` revisado con la usuaria.
