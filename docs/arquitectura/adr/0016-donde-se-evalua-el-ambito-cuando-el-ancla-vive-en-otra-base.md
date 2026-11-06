# ADR 0016. Dónde se evalúa el ámbito cuando el ancla de tenencia vive en otra base

- **Estado:** aceptada (sesión de aprobación del OE2, 2026-09-21; ver `ACTA_APROBACION_OE2.md`)
- **Fecha:** 2026-09-21
- **Decide:** equipo ISIS2610-G19
- **Relacionada con:** ADR 0013 (matrícula como ancla y roles con ámbito), ADR 0012 (una base por servicio)

## Contexto

Este ADR existe porque los ADR 0012 y 0013 se contradicen, y la contradicción no se
detectó al escribirlos sino al intentar redactar el criterio de aceptación de un requisito.
Ese es el dato que conviene retener: **dos decisiones correctas por separado produjeron un
mecanismo inejecutable al combinarse**, y solo se vio cuando alguien tuvo que decir dónde
se ejecutaba.

El ADR 0013 promete que las políticas de seguridad a nivel de fila se escriben «contra el
conjunto de matrículas visibles» y que con eso el ámbito **se deriva una vez** en lugar de
repetirse punto de entrada por punto de entrada. Ese es su argumento principal, porque la
auditoría había encontrado 22 de 152 puntos de entrada donde la comparación faltaba, y el
atractivo de la propuesta era justamente eliminar la posibilidad de olvidarla.

El ADR 0012 establece una base de datos por servicio. `matricula` vive en Identidad, y el
manifiesto declara `comercio.linea_pedido.matricula_id` como referencia lógica entre bases,
no como llave foránea física.

El problema es que **una política de fila de Postgres no puede unirse contra otra base de
datos.** Se evalúa dentro del motor, en la sesión actual, sobre tablas locales. Por tanto:

| Servicio | ¿El ancla es local? | ¿La política del ADR 0013 funciona? |
|---|---|---|
| Identidad | sí, `matricula` vive aquí | sí |
| Comercio | no | **no** |
| Inteligencia | no | **no** |
| Catálogo | no | **no** |

El mecanismo funciona en el único almacén donde el ancla es local, y no funciona en los
tres donde están los datos que hay que aislar: los pedidos, los kits y las listas. Dicho de
otro modo, el ADR 0013 resuelve el problema exactamente donde no lo había.

## Decisión

**Se denormaliza la clave de ámbito, no la lista de matrículas**, y la política se evalúa
localmente en cada base contra un contexto de sesión pequeño.

Toda tabla de otro servicio que hoy referencia `matricula_id` lleva además las claves de
ámbito que la contienen, `colegio_id` y `sede_id`, copiadas al momento de crear la fila y
nunca actualizadas después. La política de fila se escribe contra esas columnas locales:

```sql
-- En Comercio, sobre linea_pedido. Ninguna unión con otra base.
CREATE POLICY lectura_por_ambito ON linea_pedido FOR SELECT
    USING (colegio_id = ANY (ambito_colegios()));
```

donde `ambito_colegios()` lee un contexto de sesión que la aplicación fija al abrir la
transacción, con los colegios que el sujeto alcanza. **La condición base deniega**: si el
contexto no está fijado, la función devuelve el conjunto vacío y no se ve nada. Esto es lo
contrario de lo que hacen hoy las políticas vigentes, que empiezan con
`current_setting(...) IS NULL` y por tanto **abren la tabla entera** a cualquier conexión
sin contexto.

La asimetría entre lectura y escritura del ADR 0013 se conserva y se vuelve expresable:
se **lee** si la fila cae en algún ámbito alcanzado, y se **escribe** solo si todas las
filas afectadas caen dentro. Un pedido con dos hermanos, uno visible y otro no, se puede
consultar pero no modificar.

### Por qué la clave de ámbito y no la lista de matrículas

La alternativa obvia era pasar el conjunto de matrículas visibles en el contexto de sesión
y comparar contra él. Se rechaza porque **no acota**. Un acudiente tiene dos o tres
matrículas y funcionaría bien; un rector de un colegio de mil estudiantes necesitaría mil
identificadores en cada transacción, y un administrador de Tukit, todos. El tamaño del
contexto crecería con el tamaño del inquilino, que es justo la dimensión en la que el
negocio pretende crecer.

La clave de ámbito no tiene ese problema: **el número de colegios que un sujeto alcanza es
pequeño para todos los roles**, porque esa es la forma de la autoridad en este dominio. Un
acudiente alcanza uno o dos; un rector, uno; un administrador de Tukit es el único caso sin
cota, y para él la política se escribe aparte con un permiso global explícito en vez de
enumerar.

### Por qué copiar y no consultar

Copiar `colegio_id` y `sede_id` es duplicación, y conviene decir por qué se acepta aquí
cuando el ADR 0012 se escribió justamente para eliminar una duplicación.

Son dos casos distintos. La duplicación que el ADR 0012 corrige era **un maestro con una
réplica que divergía**: dos tablas de producto con dos escritores no coordinados, donde la
pregunta «cuál es el precio» tenía dos respuestas. Aquí lo que se copia es un hecho
**inmutable en el momento en que se copia**: a qué colegio pertenecía esa matrícula cuando
se creó la línea del pedido. Si el estudiante se traslada de colegio el año siguiente, la
línea del pedido del año pasado **debe seguir apuntando al colegio donde estudiaba
entonces**, porque de eso depende que el histórico del colegio anterior siga siendo
correcto. La copia no es una réplica que puede quedar desactualizada; es la misma clase de
dato que el precio congelado en la línea o la dirección congelada en el envío.

Esto hace además que la denormalización sea **verificable en vez de confiable**: una
prueba puede comprobar que la copia solo se escribe en la creación y nunca se actualiza.

## Consecuencias

**A favor.** La promesa central del ADR 0013 se recupera en los tres servicios donde
importaba: el ámbito deja de depender de que cada punto de entrada recuerde compararlo. La
política es local a cada base, así que no introduce ninguna llamada de red en el camino
caliente ni acopla la autorización a que Identidad esté arriba. Y el modo de falla se
invierte: hoy una conexión sin contexto ve todo, y con esto no ve nada.

**En contra.** Hay tres columnas más por tabla protegida, y la lista de tablas es larga.
Cada punto de creación tiene que resolver el ámbito en ese instante, lo que sí exige
consultar a Identidad una vez, en la escritura y no en la lectura. Ese reparto es
deliberado: se paga en la operación menos frecuente y se cobra en la más frecuente.

**Lo que este ADR no resuelve, y hay que decirlo.** La seguridad a nivel de fila sigue
siendo una segunda línea de defensa y no la primera. La autorización de negocio
—«¿este usuario puede anular este pedido?»— se decide en la aplicación con
`puede(usuario, permiso, ámbito)`, porque depende de la acción y no solo de la fila. Lo que
la política garantiza es más estrecho y más valioso: que un punto de entrada que **olvide**
filtrar no devuelva datos de otro inquilino. Nadie debería leer este ADR como si la
autorización quedara resuelta en la base.

**Deuda que este ADR crea.** Las políticas vigentes fallan abiertas en 16 tablas de cinco
servicios, por seis migraciones con el defecto copiado idéntico. Este diseño no sirve de
nada mientras esa condición base siga invertida, así que **corregirla va antes**, no
después. Que el defecto sea idéntico en las seis ayuda: la corrección se hace y se verifica
de una sola forma.

## Alternativas consideradas

**Evaluar el ámbito solo en la aplicación, sin políticas de fila.** Es lo que el sistema
hace hoy, y la auditoría encontró 22 de 152 puntos de entrada sin la comparación. El
argumento en contra no es que los desarrolladores sean descuidados, sino que el mecanismo
depende de recordar algo en cada punto nuevo, y el número de puntos crece.

**Replicar la tabla `matricula` completa en cada servicio.** Resolvería la unión, pero crea
exactamente la clase de réplica que el ADR 0012 corrigió: un maestro y varias copias que
divergen, con la diferencia agravante de que aquí la copia gobierna un control de acceso.
Una política de seguridad evaluada sobre datos rezagados es peor que no tenerla, porque se
cree vigente.

**Una sola base compartida.** Elimina el problema por completo y reabre todos los que el
ADR 0012 cerró: obliga a una sola política de respaldo para datos con recuperabilidad
incompatible, y pone los datos de menores en la misma base que el catálogo raspado.

**Un servidor de decisiones de autorización externo.** Centraliza bien la política, pero
mete una llamada de red sincrónica en el camino de lectura y una dependencia más que tiene
que estar arriba para que el sistema responda. Para tres personas y este volumen, el costo
operativo no se justifica; queda anotado como camino de crecimiento si el número de
servicios sube.
