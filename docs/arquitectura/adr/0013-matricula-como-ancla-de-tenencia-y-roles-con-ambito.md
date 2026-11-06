# ADR 0013 — La matrícula como ancla de multi-tenencia, y roles con ámbito

- **Estado:** aceptada (sesión de aprobación del OE2, 2026-09-21; ver `ACTA_APROBACION_OE2.md`)
- **Objetivos afectados:** OE1 (Anexo M y diccionario de datos), OE2 (diseño), OE4 (ejecución)
- **Relación con el WBS:** habilita el paquete F1-3.6 de datos personales y condiciona todo
  el modelo de autorización de la fase 4
- **Relación con otras decisiones:** prerrequisito del ADR 0012; el ámbito solo se puede
  definir una vez existe el ancla

## Contexto

Tukit es un negocio B2B2C cuyo eje de crecimiento es **agregar colegios**. No crece por
tráfico: crece por inquilinos. El modelo de datos actual no refleja eso.

Tres hechos verificados en el código:

**No existe ancla de tenencia.** La columna `institucion_id` aparece diez veces en los
modelos de MS-Instituciones, una vez en MS-Busqueda y **cero veces en MS-Comercio y
MS-Cuentas**. Los pedidos y los usuarios no saben a qué colegio pertenecen. Cualquier
consulta que deba restringirse a un colegio tiene que reconstruir esa relación a mano.

**El rol es una cadena plana.** En `MS-Cuentas/app/models/__init__.py` está declarado como
`rol: Mapped[str] = mapped_column(String(50), nullable=False)`. Un solo valor, sin
estructura.

**La verificación no tiene ámbito.** En `Tukit-Auth/tukit_auth/deps.py`, la función
`require_rol` hace literalmente `if user.get("rol") not in roles`. Eso significa que un
administrador del colegio A y uno del colegio B **pasan exactamente el mismo control**. La
única defensa es que cada endpoint se acuerde de comparar el colegio del token contra el
del recurso. Con decenas de endpoints, alguno no se va a acordar, y en un sistema que
maneja datos de menores de edad esa omisión es una fuga.

Hay además una restricción de negocio que descarta la solución obvia. Poner `colegio_id` en
el usuario **es incorrecto**, porque un acudiente puede tener hijos en colegios distintos.
La tenencia no está en la persona.

Retrofitear multi-tenencia después de tener datos de producción es una de las causas
clásicas de estancamiento en startups B2B, porque obliga a rellenar datos históricos cuya
pertenencia ya nadie recuerda. Hacerlo ahora, con diecisiete colegios y sin operación real,
es barato.

## Decisión

**El ancla de tenencia es la matrícula, y la autorización pasa de rol plano a asignaciones
de rol con ámbito.**

### La matrícula

```
Matricula
    estudiante_id      datos de menor, clasificados
    sede_id            y por transitividad el colegio
    grado
    anio_lectivo
    acudientes[]       relación N:M, un estudiante puede tener varios
```

Todo lo específico de un colegio cuelga de ahí. Un kit es para una matrícula. Un pedido
agrupa líneas de una o varias matrículas, lo que modela el caso real de **dos hermanos en
una sola compra** que hoy no existe en el esquema. La lista oficial aplica a la terna sede,
grado y año, que encaja exactamente con la matrícula.

Incluir `anio_lectivo` en el ancla resuelve algo que la estacionalidad del negocio exige y
que hoy falta: el histórico. Un colegio quiere ver qué se pidió el año pasado, y una
matrícula vieja no debe aparecer como activa.

Las políticas de seguridad a nivel de fila se escriben entonces contra **el conjunto de
matrículas visibles para quien llama**, y se derivan una vez en lugar de repetirse endpoint
por endpoint.

Esas políticas quedan deliberadamente **asimétricas entre lectura y escritura**. Para leer
un pedido basta que toque alguna matrícula visible, porque un pedido de dos hermanos es
legítimamente visible para el acudiente de ambos. Para escribir se exige que **todas** las
matrículas de las líneas estén contenidas en el conjunto del llamante, que es lo que impide
que alguien inserte en su pedido la matrícula del hijo de otro. La asimetría no es un
descuido: sin ella, el mismo modelo que habilita el caso de los hermanos abre un vector de
inyección de matrículas ajenas.

Una precondición que hay que ejecutar antes: las políticas actuales **fallan abiertas**, así
que construir tenencia encima de ellas sin corregirlas primero produce una falsa sensación
de aislamiento, que es peor que no tener ninguno porque nadie lo audita después.

### Roles con ámbito

```
rol              codigo, nombre                                   catálogo, no enumeración
permiso          codigo, recurso, accion, campo (opcional)        el campo da seguridad de campo
rol_permiso      rol -> permiso
asignacion_rol   usuario, rol, ambito_tipo, ambito_id, vigencia   la pieza clave
```

`ambito_tipo` toma valores de `global`, `colegio`, `sede` o `matricula`. Con eso se puede
expresar "María es administradora con ámbito `colegio:42`".

> **Corrección a la versión inicial de este ADR.** El texto original justificaba la
> decisión diciendo que esa frase era *literalmente inexpresable* hoy. Es falso.
> `MS-Instituciones/app/models/__init__.py:93` ya define `PertenenciaInstitucion`, cuya
> tripla `(usuario_id, institucion_id, rol)` expresa justamente eso, y nació resolviendo
> una referencia directa insegura real.
>
> Se corrige y no se borra porque un ADR que funda su decisión en una premisa falsa es
> peor que uno que no existe: quien lo lea después confiará en el diagnóstico sin volver a
> mirar el código.

La premisa correcta es más estrecha y más útil. Lo que falta no es la expresividad sino
cuatro propiedades que la tabla actual no tiene:

| Propiedad | Hoy en `PertenenciaInstitucion` | Con `asignacion_rol` |
|---|---|---|
| Alcance | 1 servicio de 7 | los 7 |
| Niveles de ámbito | solo `institucion` | `global`, `colegio`, `sede`, `matricula` |
| Roles por ámbito | 1, por la restricción única `(usuario_id, institucion_id)` | varios |
| Revocación | borrar la fila | cerrar la vigencia |

La cuarta es la que más pesa, porque la tabla actual se contradice a sí misma: su
comentario sostiene que el vínculo debe conservarse para «auditoría de quién tuvo acceso a
qué institución y cuándo», y describe así una auditoría que la tabla no puede sostener,
ya que la única manera de quitar el acceso destruye la evidencia de que existió.

Esto deja la decisión mejor parada, no peor: **generaliza un mecanismo que el equipo ya
validó contra un ataque real** en vez de introducir uno nuevo.

La verificación deja de ser `rol in roles` y pasa a ser `puede(usuario, "pedido:leer",
ambito)`.

Tres consecuencias que valen la pena hacer explícitas:

1. **La columna `campo` da seguridad a nivel de campo con el mismo modelo.**
   `estudiante:leer` y `estudiante:leer:nombre` son permisos distintos. El serializador
   filtra contra el conjunto efectivo de permisos en un solo lugar del código, en vez de
   confiar en que cada respuesta esté bien escrita.
2. **Agregar un rol deja de ser una migración y un despliegue.** Cuando entre el primer
   colegio que quiera un coordinador de primaria distinto de la rectoría, eso se configura.
3. **Las asignaciones no viajan completas dentro del token.** Un acudiente con varios hijos
   o un operador con varias zonas lo inflan y, peor, lo vuelven imposible de revocar. El
   token lleva el sujeto y una versión de permisos; el ámbito efectivo se resuelve contra
   Identidad con caché corto. Es un salto más, y es el que permite revocar un acceso en
   segundos, que es un requisito real cuando hay datos de menores de por medio.

## Consecuencias

### Positivas

- Cierra un hueco de autorización real en un sistema multi-inquilino, no hipotético.
- La seguridad a nivel de fila y la de campo se derivan de un mismo modelo, en lugar de ser
  dos mecanismos que hay que mantener sincronizados.
- Habilita el histórico por año lectivo, que el negocio necesita y hoy no existe.
- Modela hermanos en un mismo pedido, que es el caso común y hoy no se puede representar.
- El catálogo de campos clasificados que esto exige **es el Anexo M** que pide el paquete
  F1-3.6. Un mismo trabajo cierra un requisito legal y un entregable académico.
- Permite revocación rápida de accesos, que es una obligación práctica bajo la Ley 1581.

### Negativas, y las asumimos

- **Una consulta más en el camino de autorización.** Se mitiga con caché corto por sujeto y
  con la versión de permisos en el token para invalidarlo.
- **Migración de datos delicada.** Hay que inferir matrículas a partir de datos que hoy no
  las tienen, y va a haber filas cuya pertenencia no se pueda determinar sin intervención.
- **Más tablas y más conceptos** que un enumerado de roles. Es complejidad real, y se
  justifica porque el mecanismo que hoy sí expresa el ámbito cubre un servicio de siete,
  un solo nivel de jerarquía y no conserva historia; no porque quede más elegante.
- **Hay que auditar los siete servicios** endpoint por endpoint para saber dónde falta hoy
  el chequeo de ámbito antes de poder migrar con confianza.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| `colegio_id` en el usuario | Incorrecto: un acudiente puede tener hijos en colegios distintos. La tenencia no está en la persona |
| Ampliar el enumerado de roles, sin ámbito | No resuelve nada: el problema no es que falten roles, es que ninguno puede decir *de qué* colegio |
| Meter las asignaciones completas en el token | Infla el token y, sobre todo, vuelve la revocación imposible hasta que expire |
| Una base de datos por colegio | Aislamiento perfecto, y operativamente inviable para un equipo de tres personas que además quiere escalar a cientos de colegios |
| Solo seguridad a nivel de fila, sin permisos de campo | Resuelve qué filas se ven, no qué columnas. No basta cuando hay datos de menores en la misma fila que datos públicos |
| Dejarlo para después | Es la alternativa más cara. Retrofitear tenencia con datos de producción encima es un proyecto, no una migración |

## Evidencia

- `institucion_id` con cero apariciones en los modelos de MS-Comercio y MS-Cuentas,
  verificado por inspección.
- `rol: Mapped[str] = mapped_column(String(50), nullable=False)` en
  `MS-Cuentas/app/models/__init__.py`.
- `if user.get("rol") not in roles` en `Tukit-Auth/tukit_auth/deps.py`.
- Variables de sesión `app.current_user_id` y `app.current_user_rol` fijadas por la librería
  compartida, sin ninguna variable de ámbito de inquilino.
- Migración `0004_row_level_security.py` en MS-Plataforma, único uso de seguridad a nivel de
  fila en todo el sistema. Cubre tres tablas de un solo servicio, filtra por `usuario_id` y
  por tanto aísla usuarios y no inquilinos, y sobre todo **falla abierta**: su condición base
  empieza con `current_setting('app.current_user_id', true) IS NULL`, de modo que toda
  conexión sin contexto de sesión ve la tabla completa.
