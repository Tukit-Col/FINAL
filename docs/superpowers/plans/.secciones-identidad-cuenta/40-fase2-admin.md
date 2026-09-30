## Fase 2 — Admin: acudientes por colegio (Tasks 30–33)

El back-office gana una vista de los acudientes de un colegio con el estado de
su trabajo (encolado / procesando / espera_revision / publicado / fallido), y
se corrige la etiqueta Dolor-1 de la pantalla de onboarding. La lista de
acudientes sale de `trabajo_pipeline` (que YA lleva `usuario_id`, el
identificador del acudiente — nunca su correo ni el nombre de un menor).

**Precondición:** Tasks 26–29 en verde. Los trabajos ya viajan con el
`usuario_id` de la sesión, así que agrupar por acudiente tiene sentido.

**Alcance de privacidad (Ley 1581 / Anexo M).** El panel muestra
`usuario_id` + estado + fechas, y —si el revisor lo pide— el correo del
acudiente resuelto contra Identidad (dato PERSONAL del titular, permitido). Los
apodos de los hijos NO se muestran aquí: son MENOR y el panel de colegio no los
necesita. `estudiante:leer:apodo` (MENOR) queda fuera de esta superficie.

---

### Task 30 — Backend: acudientes de un colegio con estado de trabajo

**Contexto.** `TrabajoPipeline` (`servicios/inteligencia/tukit_inteligencia/modelos/trabajo.py:50`)
tiene `usuario_id` (nullable), `estado`, `creado_en`, `actualizado_en`, y los
`hijos` en JSON (cada hijo trae `colegio_id`/`grado`). No hay columna
`colegio_id` en el trabajo — el colegio vive dentro de `hijos`. El endpoint
filtra los trabajos cuyo JSON `hijos` referencia el `colegio_id` pedido y los
agrupa por `usuario_id`, quedándose con el trabajo más reciente por acudiente
(el estado "vivo").

Este endpoint es de **inteligencia** (dueña de `trabajo_pipeline`), superficie
admin: `GET /v1/admin/colegios/{colegio_id}/acudientes`. Es RBAC-cerrado
(ADR-0013): solo personal con ámbito sobre ese colegio. El guardian de esquema
de inteligencia debe incluir la ruta nueva.

**30.1 — Test RED: dos acudientes del mismo colegio, un estado cada uno**

En `servicios/inteligencia/tests/test_admin_acudientes.py` (nuevo), con el
`cliente` de pruebas (SQLite StaticPool) sembrar dos `TrabajoPipeline` con
`usuario_id` distintos e `hijos` apuntando al mismo `colegio_id`, en estados
`espera_revision` y `publicado`. Pedir el endpoint y afirmar:

```python
async def test_acudientes_de_colegio_agrupa_por_usuario_con_ultimo_estado(cliente, ...):
    # sembrar trabajo A (usuario u1, colegio C, publicado, más viejo)
    # sembrar trabajo A' (usuario u1, colegio C, procesando, más nuevo)
    # sembrar trabajo B (usuario u2, colegio C, espera_revision)
    r = await cliente.get(f"/v1/admin/colegios/{C}/acudientes")
    assert r.status_code == 200
    filas = r.json()["acudientes"]
    assert len(filas) == 2                       # agrupado por usuario
    por_id = {f["usuario_id"]: f for f in filas}
    assert por_id[u1]["estado"] == "procesando"  # el más reciente, no el publicado viejo
    assert por_id[u2]["estado"] == "espera_revision"
```

Correr y ver **FAIL** (404, ruta inexistente).

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia/tests/test_admin_acudientes.py -x
```

**30.2 — Impl: consulta en el repo + ruta en el router admin**

La agrupación "último trabajo por usuario" es negocio ligero; el filtro por
colegio dentro del JSON `hijos` es lo delicado en SQL. Enfoque lazy: traer los
trabajos del colegio ordenados por `usuario_id, actualizado_en DESC` y quedarse
en Python con el primero de cada `usuario_id` (el conjunto por colegio es
pequeño — decenas, no millones).

Filtrado por colegio: en Postgres `hijos` es JSON; el modo portable (corre
también en el SQLite de pruebas) es un `LIKE` sobre el texto del JSON acotando
por el `colegio_id`, o —más honesto— cargar los trabajos recientes y filtrar en
Python por `any(h["colegio_id"] == colegio_id for h in trabajo.hijos)`. Dado el
volumen, filtrar en Python:

```python
# repositorios / consulta del servicio de inteligencia
async def trabajos_recientes(self) -> list[Fila]:
    q = select(TrabajoPipeline).order_by(
        TrabajoPipeline.usuario_id, TrabajoPipeline.actualizado_en.desc()
    )
    return (await self._conn.execute(q)).all()
```

```python
# router admin de inteligencia
@router.get("/v1/admin/colegios/{colegio_id}/acudientes")
async def acudientes_de_colegio(request: Request, colegio_id: str) -> dict:
    async with request.app.state.motor.sesion() as db:
        filas = await Repo(await db.connection()).trabajos_recientes()
    del_colegio = [
        f for f in filas
        if f.usuario_id and any(h.get("colegio_id") == colegio_id for h in f.hijos)
    ]
    ultimos: dict[str, Fila] = {}
    for f in del_colegio:                 # ya vienen ordenados por usuario, más reciente primero
        ultimos.setdefault(str(f.usuario_id), f)
    acudientes = [
        {
            "usuario_id": uid,
            "estado": f.estado,
            "actualizado_en": _iso(f.actualizado_en),
            "trabajo_id": str(f.id),
        }
        for uid, f in ultimos.items()
    ]
    return {"acudientes": acudientes}
```

`ponytail:` filtro por colegio en Python sobre trabajos recientes — un colegio
tiene decenas de acudientes, no hace falta índice sobre el JSON. Subir a JSON
containment (`hijos @> …`) si un colegio pasa de miles de trabajos.

**30.3 — Test GREEN**

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia/tests/test_admin_acudientes.py -x
```

Ver **PASS**.

**30.4 — Guardian de esquema**

Añadir `/v1/admin/colegios/{colegio_id}/acudientes` al set del test de esquema
publicado de inteligencia (el equivalente al guardian de identidad). Correr la
suite de inteligencia completa:

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia -x
```

Ver **PASS**.

**30.5 — Commit**

```bash
git add servicios/inteligencia/
git commit -m "inteligencia: GET /v1/admin/colegios/{id}/acudientes

Los acudientes de un colegio con el estado de su trabajo más reciente,
agrupado por usuario_id. Sin correo ni apodos de menores en esta superficie
(Ley 1581); solo usuario_id + estado + fecha.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 31 — Contrato: `acudientesDeColegio` + `AcudienteResumen`

**Contexto.** `origen.ts` ya tiene la familia de trabajos/colegios (`colegios()`
:148, `trabajoAdmin` :200). Añadir un método de lectura admin y su tipo. El
paquete tiene runner (`node --test`).

**31.1 — Test RED: el doble cumple `acudientesDeColegio`**

En `libs/ts/tukit-contrato/test/acudientes.test.ts`, un doble de `OrigenDatos`
que devuelve dos `AcudienteResumen` y una aserción de forma
(`usuario_id`/`estado`/`actualizado_en`/`trabajo_id`). Correr → **FAIL** (tipo y
método no existen).

**31.2 — Impl: tipo + método + impl HTTP**

En `contrato.ts` (donde viven los demás tipos) o el archivo de tipos que use el
contrato:

```ts
export interface AcudienteResumen {
  usuario_id: string;
  estado: EstadoTrabajo;      // ya exportado por el contrato
  actualizado_en: string;
  trabajo_id: string;
}
```

En `origen.ts` (`OrigenDatos`, junto a `trabajoAdmin`):

```ts
acudientesDeColegio(colegioId: string): Promise<AcudienteResumen[]>;
```

En `cliente-http.ts`:

```ts
acudientesDeColegio(colegioId: string): Promise<AcudienteResumen[]> {
  return this.pedir<{ acudientes: AcudienteResumen[] }>(
    `/v1/admin/colegios/${encodeURIComponent(colegioId)}/acudientes`,
  ).then((r) => r.acudientes);
}
```

**31.3 — Test GREEN + build**

```bash
cd libs/ts/tukit-contrato && npm test && npm run build
```

Ver **PASS** y build limpio.

**31.4 — Commit**

```bash
git add libs/ts/tukit-contrato/
git commit -m "contrato: acudientesDeColegio + AcudienteResumen

Lectura admin de los acudientes de un colegio con el estado de su trabajo.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 32 — Fix Dolor-1: la etiqueta de la pantalla de onboarding

**Contexto.** `apps/admin/src/app/onboarding/[version_id]/page.tsx:100` pinta el
título de la revisión. El spec marca un ajuste de etiqueta Dolor-1 aquí (una
afirmación imprecisa en la copy del encabezado / bajada :102–107). El cambio es
puramente de texto — se verifica por `tsc` y lectura.

**32.1 — Corregir la copy**

Leer :96–109 y ajustar la etiqueta/bajada a la redacción correcta del spec
(sección Dolor-1). Es un cambio de una o dos líneas de texto en el JSX; no toca
lógica ni tipos.

**32.2 — Typecheck**

```bash
cd apps/admin && npm run typecheck
```

Ver salida limpia.

**32.3 — Commit**

```bash
git add apps/admin/src/app/onboarding/
git commit -m "admin: corregir etiqueta Dolor-1 en la revisión de onboarding

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 33 — Panel de acudientes en `/colegios/{colegio}`

**Contexto.** `apps/admin/src/app/colegios/[colegio]/page.tsx` es un Server
Component que ya trae `colegio()` y deriva `grados` de `colegios()`. Tiene dos
`<section className={styles.tarjeta}>`: "Ficha del colegio" y "Grados
verificados". Añadir una tercera: "Acudientes", que llama a
`acudientesDeColegio(colegioId)` y lista `usuario_id` + estado + fecha. Sin
runner en `apps/admin`: se verifica por `tsc` + e2e manual.

**33.1 — Traer los acudientes en el Server Component**

Junto a la derivación de `grados` (:39–42):

```ts
const acudientes = await origenDeDatos().acudientesDeColegio(colegioId);
```

**33.2 — Sección "Acudientes" con estado**

Tras la sección "Grados verificados" (:78–97), añadir:

```tsx
<section className={styles.tarjeta}>
  <h2 className={styles.subtitulo}>Acudientes</h2>
  <p className={styles.bajada}>
    Quiénes han pedido kits para este colegio y en qué va su trabajo. Sin datos
    de menores: solo el identificador del acudiente y el estado.
  </p>
  {acudientes.length === 0 ? (
    <p className={styles.sinGrados}>Ningún acudiente todavía.</p>
  ) : (
    <ul className={styles.listaAcudientes}>
      {acudientes.map((a) => (
        <li key={a.usuario_id}>
          <code>{a.usuario_id.slice(0, 8)}</code>
          <span className={styles[`estado_${a.estado}`] ?? styles.estado}>{a.estado}</span>
          <time dateTime={a.actualizado_en}>{a.actualizado_en.slice(0, 10)}</time>
        </li>
      ))}
    </ul>
  )}
</section>
```

Reutilizar clases de `Colegios.module.css` que ya existan (`.tarjeta`,
`.subtitulo`, `.bajada`, `.sinGrados`); añadir `.listaAcudientes` y un chip de
estado solo si el CSS no tiene ya algo equivalente (mirar antes — el módulo ya
pinta insignias `insigniaAliado`/`insigniaBorrador`, reutilizables como chip).

**33.3 — Typecheck + build**

```bash
cd apps/admin && npm run typecheck && npm run build
```

Ver salida limpia.

**33.4 — Verificación e2e manual (documentar)**

Con backend arriba y al menos un trabajo publicado para un colegio piloto,
abrir `/colegios/{colegio}` en admin y confirmar que el acudiente aparece con su
estado. Registrar en el PR.

**33.5 — Commit**

```bash
git add apps/admin/src/app/colegios/
git commit -m "admin: panel de acudientes por colegio con estado de trabajo

Tercera sección en /colegios/{id}: quién pidió kits y en qué va su trabajo.
Solo usuario_id + estado + fecha (Ley 1581, sin datos de menores).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
