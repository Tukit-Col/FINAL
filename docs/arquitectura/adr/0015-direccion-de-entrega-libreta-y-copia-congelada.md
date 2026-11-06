# ADR 0015. Dirección de entrega: libreta en Identidad y copia congelada en el envío

- **Estado:** aceptada (sesión de aprobación del OE2, 2026-09-21; ver `ACTA_APROBACION_OE2.md`)
- **Fecha:** 2026-09-21
- **Decide:** equipo ISIS2610-G19
- **Relacionada con:** ADR 0012 (costura Comercio/Catálogo), ADR 0013 (matrícula y roles con ámbito)

> **Historia de estado.** Esta decisión estuvo primero en «propuesta» porque se apoya en los
> ADR 0012 y 0013, y no podía estar aceptada mientras su premisa no lo estuviera. Los cuatro
> (0012 a 0015), junto con 0016 y 0017, se decidieron **juntos** en la sesión de aprobación
> del OE2 del 2026-09-21, de modo que la premisa quedó aceptada en el mismo acto.

## Contexto

No existía **ninguna** dirección de entrega en todo el sistema, en un negocio cuya
propuesta de valor es entregar el kit escolar en la casa. La búsqueda por los siete
servicios no encontró ni tabla, ni columna, ni campo de formulario.

El hueco no era solo de implementación: `ESQUEMA_OBJETIVO.md` tampoco la modela, así que
se arrastraba del código al diseño y de ahí a las 67 tablas del esquema objetivo. Un
defecto de omisión sobrevive más que uno de comisión, porque nada lo señala.

El dato es sensible de forma poco habitual. No es solo información de contacto: es la
ubicación física del hogar de una familia con menores de edad, cruzada con el colegio al
que asisten y con el horario en el que alguien estará en casa para recibir. Bajo la Ley
1581 de 2012 eso obliga a tratarlo con el mismo cuidado que el resto de los datos de
menores del sistema.

## Fuerzas en tensión

1. **La supresión tiene que alcanzarla.** Si la dirección vive fuera de la frontera de
   cumplimiento, el derecho al olvido vuelve a quedar a medias, que es exactamente el
   defecto que el Anexo M documentó en las otras rutas de datos personales.
2. **El historial de entregas no se puede reescribir.** Si el envío apunta a la libreta
   con una llave foránea, corregir un número de apartamento cambia retroactivamente a
   dónde se entregó un pedido de hace seis meses, y deja sin sustento cualquier reclamo o
   disputa.
3. **Repartir una ruta no necesita el apartamento.** Asignar zona, agrupar entregas y
   estimar costo dependen de la ciudad y la localidad. La calle y el número solo hacen
   falta en el último tramo.
4. **Comercio no puede depender de Identidad para despachar.** Si el operador logístico
   necesita una llamada a otro servicio para saber a dónde va el paquete, una caída de
   Identidad detiene la operación física.

## Alternativas consideradas

### A. Todo en Comercio

La dirección como tabla de Comercio, junto al pedido y al envío.

Resuelve 2, 3 y 4 sin esfuerzo. **Se rechaza por 1:** mete dato personal de familias con
menores en la base transaccional, fuera de la frontera de cumplimiento, y obliga a que la
supresión cruce servicios para algo que es puramente personal. Es repetir la decisión que
produjo el problema de supresión actual.

### B. Todo en Identidad, con llave foránea desde el envío

Una sola tabla, referenciada desde Comercio.

Resuelve 1. **Se rechaza por 2 y 4:** la referencia hace que editar la dirección reescriba
el historial, y la llave foránea cruza bases, que es justo lo que el manifiesto de
arquitectura prohíbe.

### C. Libreta en Identidad, copia congelada en el envío — **elegida**

Dos cosas que se parecen y no son la misma:

- **`identidad.direccion`** es la *libreta* del acudiente: direcciones reutilizables, que
  él edita y archiva, sujetas a supresión.
- **El envío en Comercio** guarda una *copia congelada* de la dirección tal como estaba al
  confirmar el pedido. No es una referencia: son columnas propias del envío.

Es el mismo razonamiento por el que el precio se congela en la línea del pedido en vez de
leerse del catálogo al consultar. Un hecho histórico y un dato editable son cosas
distintas aunque se escriban igual.

## Decisión

Se adopta la alternativa C, con tres reglas:

1. **Minimización por columna.** `ciudad` y `localidad` quedan en claro, porque de ellas
   depende la asignación de zona. La calle, el número, el apartamento y el punto de
   referencia van en `linea_cifrada`, y el teléfono en `contacto_cifrado`. La distinción
   no es estética: permite que el motor de rutas opere sin descifrar nada.

2. **Baja lógica, no borrado.** `archivada_en` en vez de `DELETE`. Un envío en curso
   necesita que la dirección exista mientras se entrega. Un índice único parcial garantiza
   una sola predeterminada activa por usuario, y archivar libera el lugar sin borrar.

3. **La copia congelada sobrevive a la supresión de la libreta.** Cuando el titular ejerce
   supresión, se borra la libreta; la copia del envío se conserva mientras dure la
   obligación contable y comercial, y se anonimiza al vencer. Esto se declara en el
   registro de tratamiento como conservación por obligación legal, no como olvido de
   borrar.

El conteo del esquema objetivo pasa de 67 a **68 tablas**: una nueva en Identidad. Comercio
no suma tabla porque la copia son columnas de `envio`.

## Consecuencias

**A favor.** La supresión alcanza el dato personal sin tocar el registro contable. El
historial de entregas es inmutable. Comercio despacha sin llamar a Identidad. El motor de
rutas nunca ve una dirección completa en claro.

**En contra.** Hay duplicación deliberada, y con ella la pregunta legítima de "¿cuál es la
buena?". La respuesta es que las dos lo son, para preguntas distintas: la libreta responde
"¿a dónde envío el próximo pedido?" y la copia responde "¿a dónde envié este?". Queda
anotado que esta duplicación **no** es del tipo que las funciones de aptitud prohíben: no
hay dos maestros del mismo hecho, hay dos hechos distintos.

**Deuda que abre.** El cifrado de `linea_cifrada` depende del mismo mecanismo de llaves que
hoy es una sola frase de paso de pgcrypto, sin separación por clasificación y sin rotación.
Esta decisión no lo arregla; lo hace más urgente.

## Verificación

Cuatro pruebas en `tukit/servicios/identidad/tests/test_privacidad.py` fijan los
invariantes: una sola predeterminada activa por usuario, que archivar libera el lugar, que
la ciudad queda en claro y la calle no, y que no existe ninguna columna de dirección en
texto plano al lado de la cifrada.
