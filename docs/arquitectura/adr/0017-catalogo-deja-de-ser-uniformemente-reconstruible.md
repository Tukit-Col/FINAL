# ADR 0017. Catálogo deja de ser uniformemente reconstruible

- **Estado:** aceptada (sesión de aprobación del OE2, 2026-09-21; ver `ACTA_APROBACION_OE2.md`)
- **Fecha:** 2026-09-21
- **Decide:** equipo ISIS2610-G19
- **Relacionada con:** ADR 0012 (costura Comercio/Catálogo y recuperabilidad asimétrica)

## Contexto

El ADR 0012 separó Catálogo de Comercio con un argumento que era su mejor aporte: los dos
almacenes no pueden compartir base **porque no pueden compartir política de respaldo**. Si
se pierde Catálogo entero se vuelve a correr el raspado y en horas está de vuelta; un
pedido no. De ahí salió el objetivo de punto de recuperación de horas para Catálogo y de
cero para Comercio.

Ese argumento era correcto cuando Catálogo contenía únicamente productos raspados. Al
traer el módulo editorial a la primera versión, dejó de serlo. Cuatro de sus diecisiete
tablas guardan **registros de decisión institucional con aprobador nombrado y fecha**:

| Tabla | Qué guarda | ¿Se reconstruye raspando? |
|---|---|---|
| `propuesta_version` | quién aprobó qué edición y cuándo | **no** |
| `version_vigente` | qué edición usó cada colegio cada año | **no** |
| `configuracion_colegio_editorial` | la política que el colegio fijó | **no** |
| `version_lista_oficial` | qué publicó el colegio y quién | **no** |

El requisito que sostiene la primera de ellas dice explícitamente que existe para poder
responder ante una auditoría. Un registro nominal de decisión institucional con un objetivo
de punto de recuperación en horas es, en pequeño, **el mismo error de asimetría que el
ADR 0012 fue creado para corregir**: mezclar en una política de respaldo barata un dato que
no se puede volver a producir.

La tentación es declarar una excepción por tabla. No funciona, y la razón es técnica y no
de criterio: **la recuperación a un punto en el tiempo es por agrupación de bases, no por
tabla.** No se puede restaurar media base a un instante y la otra media a otro. Basta una
tabla que no se pueda perder para que el objetivo de punto de recuperación de toda la
agrupación sea el de esa tabla.

## Decisión

**Catálogo pasa a objetivo de punto de recuperación cero**, igual que Comercio. Se corrige
el ADR 0012 en ese punto en vez de sostener una clasificación que dejó de ser cierta.

Se rechaza mover las cuatro tablas a un servicio que ya tenga recuperación estricta. Se
evaluó mandar el registro de decisión a la bitácora de auditoría de Operación y dejar en
Catálogo solo una copia de trabajo reconstruible desde ella, que es elegante y **casi
funciona**. El defecto aparece al pensar el orden de restauración: Operación referencia a
Catálogo, así que Catálogo tendría que restaurarse primero; pero Catálogo necesitaría la
bitácora de Operación para reconstruir sus decisiones, así que Operación tendría que ir
primero. Es un ciclo en el orden de restauración, que es exactamente la propiedad que la
función de aptitud de aciclicidad existe para proteger. Vale la pena registrarlo porque la
alternativa parecía la más limpia de las tres hasta que se le pidió un orden concreto.

## Consecuencias

**La justificación principal del ADR 0012 se debilita, y hay que decirlo en la
sustentación.** Si Catálogo y Comercio tienen ahora el mismo objetivo de recuperación, la
recuperabilidad asimétrica ya no separa a esos dos en particular. La separación sigue en
pie por los otros motivos, que no cambiaron: Catálogo necesita `pgvector`, réplicas de
lectura y tolera ráfagas de escritura del raspador, mientras Comercio necesita
transaccionalidad estricta y disponibilidad constante. Pero el argumento que encabezaba el
ADR 0012 pasa a segundo lugar detrás del perfil de recurso.

Conviene no maquillar esto. Una decisión de arquitectura cuya justificación principal se
cae por un cambio de alcance es un hallazgo legítimo, y presentarlo así es más defendible
que reescribir la historia para que parezca que siempre se supo. La asimetría de
recuperabilidad **sigue siendo real** entre otros pares —Inteligencia sí es enteramente
reconstruible, y esa frontera se mantiene por ese motivo—, solo que ya no es la que separa
a Catálogo de Comercio.

**El costo sube.** Archivado continuo y retención sobre una base más, que es la más grande
del sistema por número de filas. Es el precio de haber metido un registro institucional en
ella, y conviene tenerlo presente si algún día se propone meter otro.

**Lo que este ADR enseña, y que vale más que la decisión.** La política de respaldo de un
almacén la fija **el dato menos reconstruible que contenga**, no el más común. Al añadir
una tabla a un servicio hay que preguntar si se puede volver a producir; si no, arrastra a
toda la agrupación a su nivel. Esa pregunta no estaba en ninguna lista de verificación
cuando se decidió traer el módulo editorial, y por eso el defecto entró.

## Alternativas consideradas

**Dejarlo como está y anotar la excepción.** Rechazada porque la recuperación a un punto
en el tiempo no distingue tablas: la excepción sería una declaración sin mecanismo que la
sostenga, que es la clase de afirmación que el barrido de coherencia encontró repetida por
todo el corpus documental.

**Sacar el módulo editorial de la primera versión.** Resolvería la contradicción quitando
la causa, pero reinstala el problema que motivó traerlo: los tres dolores mejor
documentados del colegio se quedan sin aliviador y el encaje del lienzo de valor vuelve a
quedar invertido. Se prefiere pagar el respaldo.

**Una base aparte solo para las cuatro tablas de decisión.** Correcta en teoría y
desproporcionada en la práctica: un octavo almacén, con su despliegue y su respaldo, para
cuatro tablas de bajo volumen, en un equipo de tres personas.
