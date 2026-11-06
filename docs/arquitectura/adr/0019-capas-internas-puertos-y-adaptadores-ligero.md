# ADR 0019. Capas internas por servicio: puertos y adaptadores ligero, no MVC

- **Estado:** propuesta
- **Fecha:** 2026-09-25
- **Decide:** equipo ISIS2610-G19
- **Objetivos afectados:** OE2 (diseño interno de cada servicio), OE4 (mantenibilidad y prueba)
- **Relacionada con:** ADR 0014 (monorepo con funciones de aptitud sobre fronteras *entre*
  servicios; esta decisión gobierna las fronteras *dentro* de cada uno), ADR 0011 (el puerto
  `PasarelaPagos` es el patrón que aquí se generaliza)

## Contexto

Las fronteras **entre** servicios están sanas y demostradas: una base por servicio, ningún import
cruzado, referencias declaradas, todo verificado por `arquitectura/test_fronteras.py` (ADR 0014). La
deuda estructural real está **dentro** de cada servicio: los archivos de rutas están gordos porque
un solo manejador de FastAPI mezcla las tres capas —HTTP/validación, reglas de dominio y
persistencia (SQL crudo)— en la misma función. Se ve en el tamaño: `catalogo/admin_http.py` = 1.984
líneas, `inteligencia/trabajos.py` = 1.826, `catalogo/admin.py` = 1.656, `comercio/api.py` = 682.

El caso limpio es `comercio.crear_orden` (`api.py:357-457`): en ~100 líneas conviven el decorador y
la validación (a), la invariante FU-08 —"re-verifica el precio contra Catálogo y solo si coincide
congela"— (b), y cuatro `insert()` de SQLAlchemy Core con la estructura de tablas desplegada (c). La
consecuencia no es cosmética: la regla de negocio más cara del sistema —no cobrar a un precio que
cambió— hoy solo se puede probar levantando FastAPI y montando `app.state`, cuando es una función
pura que debería probarse con una lista y un diccionario.

Los servicios **ya tienen** parte de la separación hecha, y bien: `modelos/` (ORM partido por
sub-dominio) en todos, `remoto.py` (adaptador de salida HTTP) en comercio/inteligencia/operacion, y
los *workers* aparte (`pasarela.py`, `repartidor.py`, `poller.py`). Lo que falta no es "modelos" ni
"adaptadores de salida" —existen— sino la capa de **dominio** libre de framework y la de
**repositorio** de la propia base.

MVC no es el patrón. MVC tiene sentido con una Vista que el backend renderiza; la API de Tukit es
*headless* (devuelve JSON, Next.js pinta). Forzar Modelo-Vista-Controlador sobre un servicio JSON
deja el patrón sin su tercera pata y no dice dónde van las reglas.

## Decisión

**Cada servicio con base se estructura en arquitectura hexagonal ligera, con la regla de dependencia
apuntando hacia adentro**, apoyada en lo que ya existe:

```
servicios/<svc>/tukit_<svc>/
├── api.py            crear_app + include_router(...)   (queda delgado)
├── routers/          adaptador de entrada: parsea → llama al dominio → traduce al sobre de error. Sin reglas, sin SQL
├── dominio/          PURO: dataclasses + funciones. Sin FastAPI, sin SQLAlchemy, sin httpx. Declara los Protocol (puertos)
├── repositorios/     adaptador de salida a la propia base: el SQL, detrás del Protocol que el dominio pide
├── modelos/          (EXISTE) ORM declarativo — se reusa tal cual
└── remoto.py         (EXISTE) adaptador de salida HTTP a otros servicios
```

**Los puertos son `typing.Protocol`**, generalizando `comercio/tukit_comercio/pasarela.py:84`
(`class PasarelaPago(Protocol)`), que ya es puertos-y-adaptadores de libro. El `Protocol` vive en
`dominio/`; la implementación concreta con SQL en `repositorios/`. El dominio nunca importa
SQLAlchemy: recibe datos planos y devuelve datos planos.

**Inyección de dependencias en dos planos**, sin marco nuevo:
- **Singletons de proceso** (motor, clientes remotos, pasarela) siguen en `app.state` vía `_arrancar`
  (`comercio/api.py:74-80`), como hoy.
- **Repositorios por-petición** por `Depends`, con un ayudante compartido nuevo
  `tukit_comun/dependencias.py::repo_dep(construir)` que abre `MotorServicio.sesion()` —que ya hace
  commit/rollback (`bd.py:60-70`)— y construye el repo atado a esa conexión.

**El I/O asíncrono se resuelve en el router, no en el dominio.** El router hace los `await` (por
ejemplo, resuelve todos los SKU de la orden de una) y pasa al dominio una estructura ya materializada
(`resueltos.get`, un dict puro). El dominio queda síncrono y puro; se elimina de raíz cualquier
tentación de "correr una corrutina dentro de una función pura".

El adelgazamiento es **guiado por pruebas y sin pérdida de funcionalidad**: por servicio, se escriben
primero los tests de dominio puro (que fallan), se extrae el dominio (verde), se extrae el
repositorio (SQL fuera del handler, comportamiento intacto), se adelgaza el router, y se confirma que
la suite de integración HTTP+DB pre-existente sigue verde. Si un test de integración se pone rojo, la
extracción cambió comportamiento y se revierte. Orden: `comercio` (referencia) → `operacion` (valida
la plantilla barato) → `catalogo` → `identidad` → `inteligencia` (el más riesgoso, se de-riesga
aparte).

`gateway` **queda plano y sin capas**, y es correcto: el manifiesto lo declara "sin dominio y sin
base" y el código lo cumple. `ingesta` nace con esta forma cuando tenga código.

## Consecuencias

**A favor.** La invariante FU-08 —y toda regla de negocio— pasa a probarse con `assert` sobre datos,
sin red ni base: las pruebas más caras del sistema se vuelven las más rápidas. El SQL deja de estar
embebido en la lógica. Ninguna frontera *entre* servicios cambia; todo es interno. La estructura la
puede razonar completa un equipo de cuatro.

**En contra.** Son más archivos y una indirección más (el `Protocol`). Se acepta porque la
indirección es exactamente la costura que separa "qué decide el negocio" de "cómo se guarda", y esa
costura es la que hoy no existe.

**Deuda que se declara.** La migración de `inteligencia/trabajos.py` (1.826 líneas, orquestador con
estado) es la más riesgosa y no se hace de un tirón: primero se cosecha lo ya-puro a
`dominio/pipeline.py`, luego la máquina de estados a `dominio/maquina.py`, y solo entonces se toca
`procesar`, apoyándose en la ejecución durable de la ADR 0024.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| **Dejarlo como está** (handlers gordos) | El código gordo no falla ni es lento, pero hace inejecutable probar las invariantes sin FastAPI+Postgres. Para una tesis que afirma tener reglas de dominio verificadas, esa es la deuda que sí importa pagar. |
| **MVC clásico** | No hay Vista que separar en una API headless; el patrón queda cojo y no dice dónde van las reglas. |
| **Repositorio genérico único** (un `Repo[T]` para todo) | Una abstracción con una sola forma que termina filtrando SQLAlchemy al dominio. Un repositorio concreto por agregado es más código y menos magia. |
| **Framework de DI** (dependency-injector, wiring) | `Depends` + `app.state` ya cubren los dos planos que existen. Un contenedor de DI es infraestructura para un problema que el framework HTTP ya resuelve. |
| **Reescritura de golpe** | Rompe la red de regresión. La migración incremental guiada por pruebas mantiene el sistema verde en cada paso. |
