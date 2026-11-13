# Panel por hijo en la vista del kit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Con 2+ hijos, mostrar arriba del kit un resumen por hijo (tarjeta plegable con nombre, grado, personaje, total, productos y "falta") y una banda de lo compartido, dejando la lista por categoría de hoy intacta debajo.

**Architecture:** Un helper puro en `kit-vista.ts` arma, por hijo, un objeto `ResumenHijo` desde `kit.lineas` + `kit.consolidaciones` + `personajes_por_hijo` + `personaje_sin_encaje` + los mapas `nombresHijos`/`gradosHijos` que `VistaKits` ya calcula. Un componente nuevo `ResumenPorHijo` en `VistaKits.tsx` lo pinta antes de `SeccionesDeLineas`, solo cuando hay 2+ hijos. Sin cambios de backend ni de contrato (los campos ya existen tras la rama hermanos).

**Tech Stack:** Next.js 16 + TypeScript (web), `node --test`; lucide-react para iconos; CSS modules.

**Spec:** `docs/superpowers/specs/2026-11-13-panel-por-hijo-design.md`

## Global Constraints
- Ley 1581: el panel nombra al hijo solo con `nombresHijos` (apodo o "Hijo N"); nunca la referencia interna `linea.hijo` ni el apodo de otra fuente.
- No se recalcula aritmética: el total por hijo es la suma de `subtotal_linea` de sus líneas comprables (`entraAlTotal`), que ya refleja la consolidación (la línea del hermano consolidado va en 0).
- No se duplica el cálculo de lo compartido: se reutiliza `kit.consolidaciones` y el helper `textoDeConsolidacion` ya existente.
- Solo aparece con 2+ hijos distintos en las líneas del kit activo; con 1 hijo la vista no cambia.
- Aplica a cualquier perfil activo; la línea de personaje de una tarjeta solo si ese hijo pidió uno; la nota de "falta de personaje" (`personaje_sin_encaje`) solo trae datos en Fan.
- La tarjeta es de lectura: no repite carrusel ni controles de cambio (eso vive en la lista de abajo).

## Review Focus
- Hijo consolidado con otro (su línea en 0 unidades): no debe aparecer como producto propio duplicado ni inflar su total; el ítem compartido va en la banda, no dentro de las dos tarjetas. → test en Task 1.
- Hijo sin personaje junto a hermano con personaje: su tarjeta no muestra línea de personaje ni nota de falta, pero sí sus productos neutros. → test en Task 1.
- Una línea sin `hijo` (trabajos viejos / canónico de un solo hijo): no rompe el agrupamiento; con <2 hijos el resumen no se pinta. → test en Task 1 y Task 2.
- Un hijo cuyas líneas son todas abstenciones/informativas (sin nada comprable): total $0 bien formado y su "falta" lista esas líneas, sin tarjeta vacía sin sentido. → test en Task 1.
- Personaje normalizado distinto entre `personajes_por_hijo` y lo pedido ("Spider-Man" vs "spiderman"): el encabezado del hijo muestra el personaje una sola vez y correctamente. → test en Task 1.

---

### Task 1: Helper `resumenPorHijo` (lógica pura)

**Files:**
- Modify: `apps/web/src/lib/kit-vista.ts` (agregar `resumenPorHijo` y el tipo `ResumenHijo`)
- Test: `apps/web/test/kit-vista.test.ts`

**Interfaces:**
- Consumes: de `@tukit/contrato` — `LineaKit`, `Consolidacion`, `entraAlTotal`, `esAbstencion`; de este módulo — `textoDeConsolidacion`, `notaSinEncaje`.
- Produces:
  ```ts
  export interface ResumenHijo {
    hijo: string;              // referencia interna (clave), NO se pinta
    nombre: string;            // de nombresHijos; "Hijo N" si no hay
    grado: string | null;      // de gradosHijos
    personaje: string | null;  // de personajes_por_hijo (primero), o null
    total: number;             // suma de subtotal_linea de sus comprables
    productos: LineaKit[];     // sus líneas comprables NO consolidadas-en-cero
    comparten: number;         // nº de consolidaciones en que participa
    falta: string[];           // notas: abstenciones + personaje_sin_encaje
  }

  export function resumenPorHijo(
    kit: { lineas: LineaKit[]; consolidaciones: Consolidacion[]; personaje_sin_encaje?: { hijo: string; concepto: string; personaje: string }[] },
    nombres: ReadonlyMap<string, string>,
    grados: ReadonlyMap<string, string>,
    personajesPorHijo?: Record<string, string[]>,
  ): ResumenHijo[]
  ```
  Orden de los hijos: primera aparición en `kit.lineas`. `productos` excluye las líneas comprables cuyo `unidades_a_comprar === 0` (el hermano consolidado) para no duplicar el ítem compartido; `total` sí las incluye (suman 0, así el total por hijo cuadra con el del kit). `comparten` cuenta las `consolidaciones` cuyo `hijos` incluye a ese hijo. `falta` = `notaSinEncaje` de cada entrada de `personaje_sin_encaje` de ese hijo, más una línea corta por cada abstención (`esAbstencion`) usando su `descripcion`.

- [ ] **Step 1: Write the failing tests** en `apps/web/test/kit-vista.test.ts` (importar `resumenPorHijo`). Usar un helper local `linea(hijo, extra)` que arme un `LineaKit` comprable con `subtotal_linea` y `unidades_a_comprar` dados.
  - `resumen agrupa por hijo en orden de aparicion y pone nombre, grado y personaje`: líneas de "a" (grado Séptimo) y "b" (grado Jardín); `nombres={a:"Ana",b:"Luis"}`, `grados={a:"Séptimo",b:"Jardín"}`, `personajesPorHijo={a:["Spider-Man"],b:["Minnie"]}`. Assert: dos resúmenes `["a","b"]`; `[nombre,grado,personaje]` de a = `["Ana","Séptimo","Spider-Man"]`.
  - `el total suma los subtotales y el consolidado-en-cero no se duplica como producto`: a y b con el mismo ítem compartido, b con `unidades_a_comprar:0, subtotal_linea:0`, y `consolidaciones=[{...,hijos:["a","b"]}]`. Assert: `productos` de b no incluye ese ítem; `comparten` de a y b = 1; `total` de b suma solo sus otras líneas.
  - `hijo sin personaje no trae personaje ni nota de falta`: b sin entrada en `personajesPorHijo` ni en `personaje_sin_encaje`. Assert: `personaje` de b es `null` y `falta` de b es `[]`.
  - `falta lista personaje_sin_encaje y abstenciones`: a con `personaje_sin_encaje=[{hijo:"a",concepto:"C001",personaje:"spiderman"}]` y una línea de a en estado `HUECO_CATALOGO`. Assert: `falta` de a tiene la nota de `notaSinEncaje` y una línea con la descripción del hueco.
  - `con un solo hijo devuelve un solo resumen` (el gate de 2+ vive en el componente, no aquí).
- [ ] **Step 2: Run tests to verify they fail.** Run: `cd apps/web && node --test test/kit-vista.test.ts`. Expected: FAIL (`resumenPorHijo` no existe).
- [ ] **Step 3: Implement `resumenPorHijo` y `ResumenHijo`** en `apps/web/src/lib/kit-vista.ts`. Una sola pasada por `kit.lineas` para agrupar; `comparten` desde `consolidaciones`; `falta` combinando `notaSinEncaje` y las abstenciones. Reusar `entraAlTotal`/`esAbstencion` del contrato.
- [ ] **Step 4: Run tests to verify they pass.** Run: `cd apps/web && node --test test/kit-vista.test.ts`. Expected: PASS. Luego `cd apps/web && npx tsc --noEmit -p .` limpio.
- [ ] **Step 5: Commit** `git commit -m "Resumen por hijo: helper puro del kit por hijo con compartido y falta"`

### Task 2: Componente `ResumenPorHijo` en la vista del kit

**Files:**
- Modify: `apps/web/src/app/kits/[trabajo_id]/VistaKits.tsx` (nuevo componente + montaje antes de `SeccionesDeLineas`)
- Modify: `apps/web/src/app/kits/[trabajo_id]/Kits.module.css` (estilos de tarjetas plegables y banda)

**Interfaces:**
- Consumes: `resumenPorHijo`, `ResumenHijo`, `textoDeConsolidacion` de `@/lib/kit-vista`; `nombresHijos` y `gradosHijos` (ya calculados en `VistaKits` con `useMemo`); `ICONO_CATEGORIA` y `categoriaDeLinea` (ya existen tras Task 3 de hermanos). Estado de plegado: `useState` local (`Set<string>` de hijos colapsados; por omisión vacío = todos expandidos).
- Produces: el componente `ResumenPorHijo` (no exportado; vive en el mismo archivo), montado así:
  ```tsx
  {resumenPorHijo(kit, nombresHijos, gradosHijos, trabajo.personajes_por_hijo).length > 1 && (
    <ResumenPorHijo kit={kit} nombresHijos={nombresHijos} gradosHijos={gradosHijos}
      pedidos={trabajo.personajes_por_hijo} />
  )}
  ```
  justo antes de `<SeccionesDeLineas .../>`. El montaje repite la llamada al helper solo para el gate de longitud; el componente la vuelve a hacer internamente (barato, lista en memoria).

- [ ] **Step 1: Verificación de render manual** — no hay test de componente en este repo (los tests web son de lógica pura con `node --test`). La prueba de esta tarea es: `cd apps/web && npx tsc --noEmit -p .` limpio y `npx eslint src/app/kits src/lib/kit-vista.ts` sin errores nuevos, más la verificación visual del Step 4. Declarar esto en el ledger (la cobertura de lógica vive en Task 1).
- [ ] **Step 2: Implement `ResumenPorHijo`.** Estructura:
  - **Banda compartido** arriba (si `kit.consolidaciones.length > 0`): reutiliza `textoDeConsolidacion` con `nombresHijos`, `gradosHijos`; una línea por consolidación (producto · para quiénes · ahorro). Es la misma info que la sección "Lo que juntamos"; aquí es un encabezado del resumen.
  - **Una tarjeta por `ResumenHijo`:** encabezado siempre visible con `nombre · grado · personaje · total` y una línea "N comparten · M faltan" (M = `falta.length`). Botón que colapsa/expande (toggle en el `Set` de colapsados; `aria-expanded`). Cuerpo (si expandido): lista de `productos` (nombre + categoría + foto o `ICONO_CATEGORIA[categoriaDeLinea(linea)]`, patrón de las tarjetas Fan) y, si `falta.length`, una lista de avisos con el icono de aviso de hoy (`CircleAlert`).
  - Microcopy: encabezado del bloque "Cada kit por hijo"; cuando `personaje` es null se omite ese trozo del título; el total usa `formatearPesos`.
- [ ] **Step 3: Montar** el bloque antes de `SeccionesDeLineas` con el gate de 2+ hijos. No tocar la sección "Lo que juntamos" ni `SeccionesDeLineas` (quedan debajo, intactas).
- [ ] **Step 4: Verificar.** `cd apps/web && npx tsc --noEmit -p .` y `npx eslint src/app/kits src/lib/kit-vista.ts` limpios (0 errores; la advertencia preexistente de `agruparPorClase` no cuenta). Correr el app o una captura con un trabajo de 2 hijos y confirmar: banda de compartido, una tarjeta por hijo que pliega/expande, "falta" por hijo, y la lista por categoría intacta debajo. (Si no se puede levantar el app, dejarlo anotado y basar la prueba en tsc+eslint+Task 1.)
- [ ] **Step 5: Commit** `git commit -m "Kit: resumen por hijo plegable con compartido y lo que falta (2+ hijos)"`

---

## Verificación de punta a punta
- Un trabajo con 2 hijos (Séptimo·Spiderman y Jardín·Minnie, mismo colegio): el kit Fan muestra arriba la banda de compartido y dos tarjetas (Ana·Séptimo·Spiderman·total, Luis·Jardín·Minnie·total), cada una con sus productos, su "falta" si la hay, y plegables. Debajo, la lista por categoría de hoy sin cambios.
- Un trabajo con 1 hijo: la vista queda idéntica a hoy (no se pinta el resumen).
- Un perfil sin personaje (Ahorrador) con 2 hijos: las tarjetas salen sin línea de personaje ni nota de falta, pero con sus productos y total.
