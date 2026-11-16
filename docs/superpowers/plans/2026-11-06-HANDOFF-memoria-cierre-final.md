# Handoff: cierre final de la memoria (copiar y pegar en una sesión nueva)

Abrir `claude` en `/Users/mariapaula.rodriguez/Documents/university/TUKIT/tukit` (rama `validacion/oe5`, base `6a89666`) y pegar lo que va entre las líneas:

---

Ejecuta el plan `docs/superpowers/plans/2026-11-06-memoria-cierre-final.md` con superpowers:subagent-driven-development. Ultracode está activo, así que cada tarea con más de un archivo corre como Workflow, con editoras opus y verificadoras adversariales. Léelo completo antes de empezar. Este es el último pase de la memoria de grado (`docs/memoria`) antes de entregarla.

**Qué piden y quién lo pide:**
1. **Rey (equipo):** sus pruebas unitarias, de integración, funcionales, adversariales de IA, de degradación, de carga y de telemetría tienen que estar en la memoria.
   - La fuente es `\subsection{Verificación de la versión evaluada}` en `sections/resultados.tex` de `~/Downloads/memoria_actualizada.zip`.
   - Está extraída en `/tmp/rey_zip.4smu`. Si no existe, se vuelve a extraer en un directorio nuevo y vacío, y se lee con `python3 -I`.
   - El código y las evidencias **no están en la memoria**. Están en las ramas `origin/a/fases-2-6-oe5`, `origin/a/fases-2-6-integracion` y `origin/qa` del repo FINAL (se leen con `git show`, sin merge), y en el repo `Tukit-Col/Tukit-QA`, al que esta cuenta no tiene acceso.
   - Ver «Dónde viven las pruebas de Rey» en el plan. Si para entonces la usuaria no consiguió acceso o un zip de Tukit-QA, pídeselo antes de la Tarea 2.
2. **Daniel (equipo):** el negocio, con al menos su `Validación financiera` (`sec:viabilidad`, el mismo zip).
   - Sus cifras ($180.000 por kit, 770 kits) chocan con las vigentes ($29.353, 41 kits, `docs/negocio/PUNTO_EQUILIBRIO.md`).
   - **Pregúntale a la usuaria** cuál escenario va antes de escribir (Tarea 2, paso 3).
3. **El desarrollo y el diseño del equipo:** se traen su recorrido pantalla a pantalla y sus vistas (lógica, de ejecución, de datos y física), dentro del tope de 60 páginas.
4. **Las 18 notas del jurado (J1-J18):** están transcritas en la tabla del plan.
5. **La usuaria:**
   - El documento es **autocontenido**: se lee solo, sin ADR, repositorios, rutas ni remisiones al anexo para entender, y guía a un lector que no tiene ningún contexto.
   - Hay que verificar **cada referencia** con Firecrawl. Binario: `/Users/mariapaula.rodriguez/.devbar/pkgs/node/22.23.4/node-v22.23.4-darwin-arm64/bin/firecrawl`. Nunca se imprime la API key.
   - Las gráficas tienen que ser legibles para una persona.
   - La redacción sigue la del equipo donde corrigió.
   - Nada de datos basura.

**Turnitin y humanizadores (ya investigado; no repetirlo):** Turnitin detecta texto de IA aunque se haya pasado por parafraseadores o «bypassers», y desde ago-2026 lo cuenta como IA generada. **No se usa ninguna herramienta humanizadora.** El trabajo es estructural y a mano, con la voz del equipo:
- largo de oración variado;
- párrafos fuera del molde tema → tres apoyos → transición;
- conectores sin repetir;
- detalle concreto propio.

`/humanizer` se usa solo en modo embebido sobre los párrafos que `ritmo.py` marque (Tarea 6). Los 15 peores se le entregan a la usuaria para que el equipo los reescriba con sus palabras.

**Faro:** ya está confirmado. En las transcripciones del OE5, los acudientes lo nombran como una papelería barata donde compran, así que la glosa de `oe5.tex` es correcta. No se vuelve a investigar.

**Reglas que no se negocian:**
- Cuerpo ≤ 60 páginas (REFERENCIAS ≤ 61 en `main.toc`), con 0 errores y 0 indefinidas.
- No se agrega ni se cambia ninguna cifra, nombre ni cita sin fuente. Cuando hay conflicto, gana la cifra vigente y se anota en `revision/conflictos-equipo.md`.
- Los OE se quedan literales y «Cumplido».
- Las citas van con ACU-0x, sin nombres de acudientes, y no se vuelve a contactar a los padres.
- Las ediciones se hacen con Python (reemplazo que ocurre exactamente una vez) o con Edit; nunca con `sd`. No se lee `.env`.
- Commits como `git -c user.name=MapaRuiz -c user.email=rodriguezr.mp@javeriana.edu.co`, sin atribución de IA. El PDF va con `git add -f`.
  - No se incluyen `apps/admin/AGENTS.md` ni `docs/validacion/oe5/oe5_ronda2/CHECKLIST_LLAMADAS_HOY.md`.
  - Se pregunta antes de cada push.
- Después de cada tarea se sincroniza `../memoria-final/`.
- Al final de cada tarea se muestra el resultado, y los `.md` para la usuaria se abren con `open -a MarkdownLyt`.

**Cómo empezar:** con la Tarea 1 (inventario y presupuesto de páginas, solo lectura). Al terminarla, muéstrale `revision/cierre-final/inventario.md` a la usuaria y espera su visto bueno antes de editar.

---
