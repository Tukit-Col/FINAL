## Fase 2 — Tubería + Web (Tasks 26–29)

Cierra el lazo del alta: la tubería de inteligencia deja de re-registrar
contacto cuando ya hay un `usuario_id` de sesión, el contrato TypeScript
aprende `crearCuenta`, un Route Handler pone la cookie httpOnly, y `/empezar`
arranca por la cuenta (paso 1) con un interruptor "Ya tengo cuenta".

**Precondición:** las Tasks 20–25 (Fase 2 backend) están en verde. El endpoint
`POST /v1/cuenta` ya existe y devuelve `{sesion, token}`.

---

### Task 26 — La tubería confía en el `usuario_id` de la sesión

**Contexto.** `subir_listas` (`servicios/inteligencia/tukit_inteligencia/api.py`,
def en :499) re-registra el contacto SIEMPRE, aunque el acudiente ya venga
autenticado. El defecto está en :632–636:

```python
contacto_referencia: str | None = None
if contacto and contacto.correo:
    contacto_referencia = await _identidad().registrar_contacto(contacto.correo, contacto.celular)
```

`trabajos.crear` (`trabajos.py:137`) ya trae el patrón correcto — el guard de
:160 es `if usuario_id is None and contacto and contacto.get("correo"):`. La
tubería debe mirar primero el `usuario_id` que viaja en la sesión y solo caer
al registro-por-contacto cuando no hay sesión (el flujo anónimo heredado sigue
vivo hasta que toda la web migre).

No hay lector de token en `api.py` de inteligencia hoy. El `usuario_id` llega
por cabecera `Authorization: Bearer <token>` desde el Route Handler; el propio
servicio de inteligencia no valida el token (no tiene la clave HMAC) — se lo
pasa a Identidad, que ya expone `GET /v1/sesion` (`usuario_del_token`). Para no
sostener un await de red dentro de la sesión de base (mismo cuidado que
`operacion/routers/operacion.py:186`), el `usuario_id` se resuelve ANTES de
abrir cualquier trabajo.

**26.1 — Test RED: `subir_listas` con sesión no vuelve a registrar contacto**

Añadir a `servicios/inteligencia/tests/test_api_inteligencia.py` (usa el mismo
doble de Identidad que las pruebas existentes — un `ClienteIdentidad` falso
colgado de `app.state.identidad`). El doble cuenta las llamadas a
`registrar_contacto` y expone `usuario_del_token`:

```python
async def test_subir_listas_con_sesion_no_reregistra_contacto(cliente, identidad_doble):
    identidad_doble.usuario_por_token["tok-acudiente"] = "11111111-1111-1111-1111-111111111111"
    respuesta = await cliente.post(
        "/v1/listas",
        headers={"Authorization": "Bearer tok-acudiente"},
        files=_archivo_lista_valido(),
        data={"colegio_id": COLEGIO_PILOTO, "grado": "5"},
    )
    assert respuesta.status_code == 202
    assert identidad_doble.registros == 0  # ya venía autenticado: no re-registra
```

Correr y ver **FAIL** (hoy siempre llama a `registrar_contacto`, o `usuario_por_token`
no existe en el doble).

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia/tests/test_api_inteligencia.py -k con_sesion_no_reregistra -x
```

**26.2 — Ampliar el doble de Identidad y añadir el lector de token**

En el doble de pruebas (donde vive el `ClienteIdentidad` falso), añadir:

```python
self.usuario_por_token: dict[str, str] = {}
self.registros = 0


async def usuario_del_token(self, token: str) -> str | None:
    return self.usuario_por_token.get(token)


async def registrar_contacto(self, correo, celular=None):
    self.registros += 1
    return "22222222-2222-2222-2222-222222222222"
```

Y en `remoto.py` (`ClienteIdentidad`, junto a `registrar_contacto` :212) el
método real:

```python
async def usuario_del_token(self, token: str) -> str | None:
    """Resuelve el Bearer a un usuario_id contra Identidad. None si no vale."""
    try:
        r = await self._cliente.get("/v1/sesion", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()["sesion"]["usuario"]["id"]
    except httpx.HTTPError:
        return None
```

**26.3 — Impl mínima en `subir_listas`**

Leer el Bearer al inicio del handler (helper local, no hace falta uno global
para un solo uso), resolverlo a `usuario_id` ANTES de la sesión de base, y
pasar `usuario_id` a `trabajos.crear` — que ya sabe no registrar contacto
cuando lo recibe. El bloque :632–636 se colapsa: `contacto_referencia` solo se
calcula en la rama sin sesión.

```python
# cerca del inicio de subir_listas, tras parsear la forma
autorizacion = request.headers.get("Authorization", "")
token = autorizacion[7:] if autorizacion.startswith("Bearer ") else None
usuario_id = await _identidad().usuario_del_token(token) if token else None
```

Y en el punto donde hoy está :632–636, reemplazar por el guard que refleja
`trabajos.py:160`:

```python
contacto_referencia: str | None = None
if usuario_id is None and contacto and contacto.correo:
    contacto_referencia = await _identidad().registrar_contacto(contacto.correo, contacto.celular)
```

Pasar `usuario_id=usuario_id` a la llamada de `trabajos.crear` dentro de
`subir_listas` (hoy no lo pasa; `crear` ya acepta el kwarg, :137).

**26.4 — Test GREEN + no-regresión del flujo anónimo**

Correr el test nuevo y el que ya cubre el alta anónima (sin cabecera → sí
registra contacto, `registros == 1`):

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia/tests/test_api_inteligencia.py -x
```

Ver **PASS**. El flujo anónimo sigue registrando; el autenticado ya no.

**26.5 — Commit**

```bash
git add servicios/inteligencia/
git commit -m "inteligencia: subir_listas confía en el usuario_id de la sesión

Cuando el acudiente ya viene autenticado (Bearer), resolver el usuario_id
contra Identidad y no re-registrar el contacto. El flujo anónimo heredado
sigue registrando por contacto. Refleja el guard de trabajos.crear (ADR-0013).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 27 — El contrato TypeScript aprende `crearCuenta`

**Contexto.** `libs/ts/tukit-contrato/src/origen.ts` define `Credenciales`
(:100) y la interfaz `OrigenDatos` (:100–159) — tiene `iniciarSesion` pero no
`crearCuenta`. `cliente-http.ts` (:160–214) implementa `iniciarSesion` con
`this.pedir<{sesion; token}>("/v1/sesiones", …)`. El paquete SÍ tiene runner de
pruebas (`package.json`: `node --test "test/**/*.test.ts"`; existe
`test/atributos.test.ts`).

**27.1 — Test RED: el doble de `OrigenDatos` cumple `crearCuenta`**

Crear `libs/ts/tukit-contrato/test/cuenta.test.ts`. Primero un doble mínimo que
implemente `OrigenDatos` con `crearCuenta`, y una aserción de forma sobre lo que
devuelve (`{sesion, token}`). Esto es el "primer test double de OrigenDatos"
que el spec pide: fija el contrato antes que la impl HTTP.

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import type { OrigenDatos, NuevaCuenta } from "../src/origen.ts";

test("crearCuenta devuelve sesión y token", async () => {
  const origen = new OrigenFalso();
  const nueva: NuevaCuenta = { correo: "ana@ej.com", clave: "clave-fuerte", celular: "+57 300 000 0000" };
  const { sesion, token } = await origen.crearCuenta(nueva);
  assert.equal(sesion.usuario.correo, "ana@ej.com");
  assert.ok(token.length > 0);
});
```

Correr y ver **FAIL** (no compila: `NuevaCuenta`/`crearCuenta` no existen).

```bash
cd libs/ts/tukit-contrato && npm test
```

**27.2 — Impl: tipo + método en la interfaz + impl HTTP**

En `origen.ts`, junto a `Credenciales`:

```ts
export interface NuevaCuenta extends Credenciales {
  celular?: string;
}
```

En la interfaz `OrigenDatos`, junto a `iniciarSesion`:

```ts
crearCuenta(cuenta: NuevaCuenta): Promise<{ sesion: Sesion; token: string }>;
```

En `cliente-http.ts` (`ClienteApi`), reflejando `iniciarSesion`:

```ts
crearCuenta(cuenta: NuevaCuenta): Promise<{ sesion: Sesion; token: string }> {
  return this.pedir<{ sesion: Sesion; token: string }>("/v1/cuenta", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuenta),
  });
}
```

Completar el `OrigenFalso` del test con las demás firmas de `OrigenDatos` que
haga falta para compilar (mínimo: las que ya usan otros dobles; si no hay, dejar
`throw new Error("no usado")` en los métodos que el test no ejerce —
`ponytail:` doble de prueba, solo `crearCuenta` se ejerce aquí).

**27.3 — Test GREEN + typecheck del paquete**

```bash
cd libs/ts/tukit-contrato && npm test && npm run build
```

Ver **PASS** y build limpio.

**27.4 — Commit**

```bash
git add libs/ts/tukit-contrato/
git commit -m "contrato: crearCuenta en OrigenDatos + ClienteApi

Tipo NuevaCuenta (Credenciales + celular opcional), método crearCuenta en la
interfaz y su impl HTTP contra POST /v1/cuenta. Primer test double de
OrigenDatos fija la forma {sesion, token}.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 28 — Route Handler: `POST /empezar/api/cuenta` pone la cookie

**Contexto.** `apps/web/src/app/api/sesion/route.ts` es el molde: llama a
`origenDeDatos().iniciarSesion(cred)`, y hace
`respuesta.cookies.set(COOKIE_SESION, token, {httpOnly:true, sameSite:"lax",
secure: prod, path:"/", maxAge: 60*60*8})`. Usa `destinoDe`, `respuestaDeError`,
`urlAdmin`, `export const dynamic = "force-dynamic"`. `apps/web` NO tiene runner
de pruebas — este handler se verifica por `tsc --noEmit` (script `typecheck`) y
por el e2e manual del formulario.

**28.1 — Escribir el handler**

Crear `apps/web/src/app/empezar/api/cuenta/route.ts`, calcado de
`api/sesion/route.ts` pero llamando a `crearCuenta`:

```ts
import { NextResponse } from "next/server";
import { origenDeDatos } from "@/lib/origen";
import { COOKIE_SESION, respuestaDeError } from "@/lib/sesion"; // mismos imports que api/sesion
import type { NuevaCuenta } from "@tukit/contrato";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request) {
  try {
    const cuerpo = (await peticion.json()) as NuevaCuenta;
    const { sesion, token } = await origenDeDatos().crearCuenta(cuerpo);
    const respuesta = NextResponse.json({ sesion });
    respuesta.cookies.set(COOKIE_SESION, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 8,
    });
    return respuesta;
  } catch (e) {
    return respuestaDeError(e);
  }
}
```

Reutilizar EXACTAMENTE los helpers/constantes que `api/sesion/route.ts`
importa (leerlo primero y copiar los mismos nombres de import — `COOKIE_SESION`,
`respuestaDeError`, `origenDeDatos`). No inventar nuevos.

**28.2 — Typecheck**

```bash
cd apps/web && npm run typecheck
```

Ver salida limpia.

**28.3 — Commit**

```bash
git add apps/web/src/app/empezar/api/cuenta/
git commit -m "web: Route Handler POST /empezar/api/cuenta

Crea la cuenta contra el gateway y pone el token en cookie httpOnly (mismo
patrón que /api/sesion). El navegador nunca ve el token.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 29 — `/empezar` arranca por la cuenta (paso 1) + "Ya tengo cuenta"

**Contexto.** `FormularioEmpezar.tsx` ('use client') tiene `correo`/`celular`
useState (:362–363), el gate `listo` (:395–398), el `contacto` que se arma
(:419), y la sección "A dónde te avisamos" numerada como paso 2 (:741–775). El
spec fija: **contraseña en el paso 1**, cuentas reales desde el minuto uno.
Antes de armar el kit, hay una cuenta.

El cambio se verifica por `tsc` (no hay runner en `apps/web`) + el e2e manual.

**29.1 — Añadir estado de cuenta y el interruptor**

Junto a los useState de `correo`/`celular`, añadir:

```ts
const [clave, setClave] = useState("");
const [yaTengoCuenta, setYaTengoCuenta] = useState(false);
const [sesionLista, setSesionLista] = useState(false);
```

`sesionLista` marca que el paso 1 quedó resuelto (cuenta creada o sesión
iniciada) antes de habilitar el envío del kit.

**29.2 — Reescribir la sección de contacto como paso 1 "Tu cuenta"**

Reemplazar la sección `~741–775` (hoy "paso 2 · A dónde te avisamos") por el
paso 1 con correo + celular + **contraseña**, más el enlace "Ya tengo cuenta"
que alterna a modo inicio-de-sesión (sin celular). Renumerar los pasos que
siguen (preferencias pasa de 3 a 2, etc. — buscar los `<span className={styles.paso}>`
y correr la numeración).

Copy del bloque (respetando el tono existente — frases cortas, tú):

```tsx
<section className={styles.bloque} aria-labelledby={`${idBase}-cuenta`}>
  <h2 id={`${idBase}-cuenta`} className={styles.tituloBloque}>
    <span className={styles.paso}>1</span> Tu cuenta
  </h2>
  <p className={styles.explicacion}>
    Creas tu cuenta primero. Así guardamos tus kits y te escribimos cuando estén
    listos — armar el kit toma minutos, no segundos.
  </p>
  {/* correo, celular (solo si !yaTengoCuenta), clave */}
  {/* botón crear cuenta / iniciar sesión → llama al handler y setSesionLista(true) */}
  <button type="button" className={styles.enlaceSecundario}
          onClick={() => setYaTengoCuenta(v => !v)}>
    {yaTengoCuenta ? "Quiero crear una cuenta" : "Ya tengo cuenta"}
  </button>
</section>
```

**29.3 — Conectar el paso 1 a los handlers**

Un handler local `resolverCuenta()` que:
- si `yaTengoCuenta`: `POST /api/sesion` con `{correo, clave}`.
- si no: `POST /empezar/api/cuenta` con `{correo, clave, celular}`.
- en éxito: `setSesionLista(true)` (la cookie ya quedó puesta por el Route
  Handler; el formulario no toca el token).
- en 409 (`correo_ya_registrado`): mensaje "Ese correo ya tiene cuenta — inicia
  sesión" y `setYaTengoCuenta(true)`.

**29.4 — El gate `listo` exige la sesión; quitar `contacto` del envío del kit**

Actualizar el gate `listo` (:395) para pedir `sesionLista` en vez de validar
`correo`/`celular` sueltos:

```ts
const listo = sesionLista && hijos.every(hijoListo);
```

En las tres ramas de envío (`aplicarCanonico` :455, `crearTrabajo` :478,
`subirListas` :494) dejar de mandar `contacto` — el kit ya viaja autenticado por
la cookie; la tubería resuelve el `usuario_id` de la sesión (Task 26). Quitar la
construcción de `contacto` (:419). Si `crearTrabajo`/`subirListas` en el
contrato aún exigen `contacto`, hacerlo opcional en ese lado (mínimo cambio de
firma) — pero preferir no tocar el contrato si ya lo acepta ausente.

**29.5 — Typecheck + build**

```bash
cd apps/web && npm run typecheck && npm run build
```

Ver salida limpia.

**29.6 — Verificación e2e manual (documentar, no automatizar)**

Con el backend arriba (`make reanudar`): abrir `/empezar`, crear cuenta en el
paso 1, subir una lista, y confirmar en el panel de cola que el trabajo queda
atado al `usuario_id` de esa cuenta (no a un contacto anónimo). Registrar el
resultado en el PR.

**29.7 — Commit**

```bash
git add apps/web/src/app/empezar/
git commit -m "web: /empezar arranca por la cuenta (paso 1) + Ya tengo cuenta

Contraseña en el paso 1 — cuentas reales desde el minuto uno (spec). Correo +
celular + clave crean la cuenta contra /empezar/api/cuenta; interruptor a
inicio de sesión. El kit ya no manda contacto: viaja autenticado por cookie y
la tubería resuelve el usuario_id de la sesión.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
