# Revisión E2E de la memoria con council: hilo, conectores, estilo, repetición y nivel de maestría

> **Para agentes:** SUB-SKILL REQUERIDA: superpowers:subagent-driven-development o superpowers:executing-plans. Los pasos usan casillas (`- [ ]`).

**Objetivo:** que la memoria (`tukit/docs/memoria`, rama `validacion/oe5`, commit base `644dd5a`) cumpla cinco cosas:
- se lea de corrido, con conectores entre párrafos y un hilo de capítulo a capítulo;
- no repita información;
- no tenga marcas de texto de IA ni palabras rebuscadas;
- quede, comparada con tesis y artículos de arXiv del área, a la altura de una tesis de maestría;
- cubra los seis criterios del 38 % de la rúbrica oficial.

**Arquitectura:** tres workflows en secuencia. La usuaria ve el resultado de cada uno antes de lanzar el siguiente.
1. **Revisar** (solo lectura): lectores por capítulo, tres auditores transversales y un verificador adversarial por capítulo. Al final, una síntesis.
2. **Aplicar:** una editora por archivo, todas en paralelo porque cada una toca un archivo distinto. Después, compilación y una verificadora de cifras.
3. **Council final:** cinco jurados independientes leen el PDF nuevo, se revisan entre sí de forma anónima y dan un veredicto por criterio de la rúbrica y sobre el nivel de maestría.

**Stack:** LaTeX (`bash compilar.sh`), Workflow (agentes opus para leer y editar, sonnet para contar), python para verificar las cifras.

**Spec:** el mensaje de la usuaria del 6-nov, la página de TG de la Javeriana (60 páginas autocontenidas, sin contar referencias ni anexos) y la rúbrica `~/Downloads/Formato-evaluación-TG-ISIST-v4(Sustentación) (1).csv` (latin-1).

## Restricciones globales
- **Tope:** cuerpo ≤ 60 páginas, de la Introducción al final de las Conclusiones. Se mide como la página de REFERENCIAS en `main.toc` menos 1. Hoy es 59.
- **Cifras:** no se agrega ni se quita ninguna cifra, nombre, fecha ni cita.
  - Las cifras vienen de `cifras_calibracion.tex` (generado, no se edita a mano) y de `docs/entrega/HECHOS_CANONICOS_DOCS.md`.
- **Objetivos:** los OE se mantienen literales a la VFP v4, con la nota de prototipo funcional. Los cinco quedan "Cumplido".
- **Metodología:** la metodología de cada OE sigue nombrada al inicio de su bloque:
  - Design Thinking + IEEE 830 en el OE1;
  - RUP + IEEE 1016 + ATAM en el OE2;
  - SCRUM + CRISP-DM en el OE3 y el OE4;
  - ISO 25010 + protocolo preregistrado en el OE5.
- **Estilo:** el de Dani (memoria `thesis-writing-style-dani`; el modelo es `sections/analisisProblema.tex`):
  - cada sección abre diciendo qué cubre;
  - los términos se definen en la misma frase;
  - conectores explícitos (a partir de, de modo que, porque, a la vez, para ello);
  - vocabulario de estudiante de ingeniería.
- **Qué se evita** (humanizer, adaptado al español):
  - "no X sino Y" y "no solo… sino también";
  - cierres de una línea;
  - tríadas forzadas;
  - rayas (— –) como conector;
  - palabras infladas: clave, crucial, fundamental, robusto (figurado), sólido, integral, potenciar, destacar, cabe destacar, es importante señalar, en definitiva, en este sentido, pilar;
  - frases que describen el documento en lugar del tema.
- **Documento base:** los documentos secundarios (SDD, ATAM, SRS, ADR, QA) no son guía de estilo. Ver la memoria `memoria-es-documento-base`.
- **Privacidad:** sin nombres de acudientes, direcciones ni teléfonos.
- **Git:** `git -c user.name=MapaRuiz -c user.email=rodriguezr.mp@javeriana.edu.co`, sin atribución de IA. Se pregunta antes de hacer push.

## Foco de revisión (lo más probable que falle)
1. **Repetición entre capítulos.** 3.608/1.451, SUS 90, 0,9969, F1 0,948, 41/512 y τ aparecen en II, VI, VII y VIII y en el resumen. Regla: la cifra se explica una vez, donde se mide (VII). En el resto solo se nombra.
2. **Saltos sin puente** entre subsecciones de VI, que es el capítulo más largo (desarrollo + optimización + NL2C), y entre VII.5, VII.6 y VII.7 (calidad, OE5, amenazas).
3. **Un recorte para ganar espacio que borre el método o el límite** de un OE.
4. **Una frase reescrita que cambie una cifra o su alcance.** Por ejemplo, "en 40 listas" frente a "en 32".
5. **Jerga sin definir en su primer uso:** PE-04, ML-09, DP-03, CO-01, ESC-D4, hipervolumen, MAUT, RTLX, CGS-10, b6b6fe7.

---

### Tarea 1: Workflow «Revisar» (solo lectura)

**Archivos:** solo se leen `sections/{introduccion,descripcionGeneral,contextoProyecto,analisisProblema,disenoSolucion,desarrolloSolucion,optimizacion,resultados,calidad,oe5,conclusiones}.tex`, `covers/abstract_resumen.tex` y `main.pdf`.
**Salida:** `docs/memoria/revision/e2e-2026-11-06/` con `hallazgos-<cap>.json`, `repeticion.md`, `hilo.md`, `benchmark-maestria.md`, `rubrica.md` y `SINTESIS.md`.

**Esquema de hallazgo:** `{archivo, linea, tipo: conector|hilo|coherencia|ia|jerga|repeticion|rigor, severidad: alta|media|baja, cita_textual, problema, propuesta_reescritura}`.
- La propuesta reescribe la frase o el párrafo completo, con las mismas cifras.

- [ ] **Paso 1: Lectores por capítulo (6, opus, en pipeline con su verificador).**
  - **Grupos:**
    - I + II;
    - III + IV;
    - V;
    - VI (desarrollo + optimización);
    - VII (resultados + calidad + oe5);
    - VIII + resumen.
  - **Cada lector revisa, párrafo por párrafo:**
    - ¿El primer enunciado de este párrafo se apoya en el anterior? Si no, propone el conector o la frase puente.
    - ¿La sección abre diciendo qué cubre y cierra llevando a la siguiente?
    - Las marcas de IA de la lista de restricciones.
    - Términos sin definir.
    - Contradicciones internas.
    - Párrafos que dicen lo mismo dos veces.
- [ ] **Paso 2: Verificador adversarial por capítulo (6, opus).** Recibe los hallazgos de su capítulo y descarta los que se cumplan en cualquiera de estos casos:
  - la cita no existe;
  - la propuesta cambia una cifra o su alcance;
  - el "problema" es una preferencia sin efecto en la lectura;
  - la propuesta mete una marca de IA nueva.
- [ ] **Paso 3: Auditores transversales (3, en paralelo con el pipeline).**
  - **(a) Repetición (sonnet).**
    - Hace una matriz cifra/afirmación × capítulo, con las líneas.
    - Para cada repetición dice dónde se queda la explicación completa y dónde basta con nombrarla.
    - Estima cuántas líneas se ganan.
  - **(b) Hilo (opus).** Lee solo la apertura y el cierre de cada capítulo y subsección, más el resumen. Verifica dos cosas:
    - la cadena problema → objetivos → contexto → requisitos → diseño → construcción → resultados → conclusiones;
    - que cada OE se pueda seguir de su objetivo a su resultado y a su conclusión, con el método nombrado.
  - **(c) Benchmark de maestría (opus, con web).**
    - Busca 4-6 referencias comparables: tesis de maestría o artículos de arXiv sobre sistemas de recomendación multiobjetivo, emparejamiento de entidades o extracción de documentos con evaluación con usuarios, y alguna tesis de sistema o aplicación con arquitectura.
    - Extrae cómo estructuran el trabajo relacionado, la evaluación (líneas base, intervalos, ablación), las amenazas a la validez y la arquitectura.
    - Compara cada dimensión con la memoria y le pone una de tres marcas: a la altura, por debajo (qué falta, concreto) o por encima.
    - Mapea la memoria contra los seis criterios de la rúbrica (`rubrica.md`).
- [ ] **Paso 4: Síntesis (1, opus).**
  - Reúne lo que sobrevivió a la verificación y los tres auditores, y deduplica.
  - Ordena por severidad y estima el efecto en páginas.
  - Escribe `SINTESIS.md`:
    - top 10;
    - lista completa por archivo;
    - las brechas de maestría que se pueden cerrar sin datos nuevos y las que no (estas últimas solo se declaran).
- [ ] **Paso 5: Revisión de la usuaria.** Se abre `SINTESIS.md` en MarkdownLyt y la usuaria elige qué se aplica.

Son unos 16 agentes, por encima de la guía de 10, porque la usuaria pidió un council y la revisión completa.

### Tarea 2: Workflow «Aplicar»

**Archivos:** se modifican los `.tex` del cuerpo de la lista anterior y `covers/abstract_resumen.tex`. `cifras_calibracion.tex` no se toca.

- [ ] **Paso 1: Foto de las cifras antes de editar.**
  - `python3 revision/e2e-2026-11-06/cifras.py snapshot > antes.json`.
  - El script extrae, por archivo, el multiconjunto de números (`\d+([.,]\d+)*`), de macros `\cal*` y de claves de `\cite{}`/`\citep{}` y `\ref{}`.
- [ ] **Paso 2: Editoras (una por archivo, opus, en paralelo).**
  - Cada una aplica solo los hallazgos aprobados de su archivo.
  - Escribe con Python o Edit, nunca con `sd`, porque `sd` daña las barras invertidas.
- [ ] **Paso 3: Compilar.**
  - `bash compilar.sh`.
  - Para pasar: 0 errores, 0 `Overfull`, 0 referencias indefinidas y cuerpo ≤ 60 páginas.
  - El log se lee con `python3 -c "open('main.log','rb').read().decode('latin-1')"`.
- [ ] **Paso 4: Verificar las cifras.**
  - `python3 cifras.py diff antes.json` debe dar **0 diferencias en el total del cuerpo**. Mover una cifra de capítulo cuando se quita una repetición está permitido, y se lista.
  - Además, una verificadora adversarial (opus) lee `git diff` capítulo por capítulo y marca tres cosas:
    - cualquier cambio de alcance;
    - cualquier método o límite de un OE que se haya perdido;
    - cualquier marca de IA nueva.
- [ ] **Paso 5: Contar las marcas.** `rg -c -i "no solo|sino que|—|–|crucial|fundamental|robust|cabe destacar|es importante|en definitiva|pilar|potenciar" sections/*.tex`. Debe bajar respecto de la medición en 644dd5a, que se toma en el paso 1.
- [ ] **Paso 6: Commit y sincronización.**
  - Commit como MapaRuiz: `Memoria: revisión E2E de hilo, conectores, estilo y repetición`.
  - Sincronizar `memoria-final/`.
  - Preguntar antes del push.

### Tarea 3: Council final (llm-council sobre el PDF nuevo)

- [ ] **Paso 1: Cinco jurados independientes (opus).** Cada uno lee el cuerpo completo desde un rol:
  - jurado académico, que mira el rigor y el método;
  - jurado de ingeniería de software, que mira el diseño, el prototipo y el control de calidad;
  - editor de español académico;
  - lector lego, que solo mira el hilo;
  - jurado escéptico de las cifras y los límites.
- [ ] **Paso 2: Revisión cruzada anónima.** Cada jurado critica los veredictos de los otros sin saber de quién son.
- [ ] **Paso 3: Veredicto** en `revision/e2e-2026-11-06/COUNCIL.md`:
  - nota estimada en cada uno de los seis criterios de la rúbrica (Expresión escrita, Entorno y herramientas, Diseño, Prototipo funcional, Control de calidad, Análisis y conclusiones);
  - si está a la altura de una maestría y qué le falta;
  - lo que queda ALTO y se aplica antes del cierre.
- [ ] **Paso 4: Preguntas de la sustentación.** Con las 24 de R4 más las del council, generar `revision/PREGUNTAS_SUSTENTACION.md`, cada una con respuesta corta y página.

## Verificación final
- `bash compilar.sh`:
  - cuerpo ≤ 60 páginas;
  - 0 desbordes y 0 referencias rotas.
- `cifras.py diff` sin pérdidas.
- El conteo de marcas baja.
- `COUNCIL.md` sin hallazgos ALTOS abiertos.
