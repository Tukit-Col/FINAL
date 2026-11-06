# ADR 0002 — Auditoría como librería compartida y no como servicio

- **Estado:** aceptada
- **Objetivo afectado:** OE2
- **Cierra:** el asunto abierto A-03 del SAD

## Contexto

El SAD lista MS-Auditoria como microservicio y deja abierto el asunto A-03 sobre cómo
garantizar que el registro de auditoría sea inmutable. En el código, la auditoría ya es
la librería `Tukit-Auditoria`, declarada como dependencia por los siete servicios.

Un servicio de auditoría separado tiene un problema de fondo: si el registro de auditoría
viaja por la red, el registro puede perderse justo cuando más importa, que es cuando el
sistema está fallando. Y si la escritura de auditoría es sincrónica contra otro servicio,
cada operación del negocio queda acoplada a la disponibilidad de ese servicio.

La librería resuelve esto con el patrón de bandeja de salida: la escritura de auditoría
ocurre **en la misma transacción** que el hecho auditado, sobre la base de datos local
del servicio, y un trabajador la propaga después.

## Decisión

**La auditoría es la librería compartida `Tukit-Auditoria`, con bandeja de salida local
por servicio.** No hay servicio de auditoría.

Sobre la inmutabilidad, que es lo que A-03 dejaba abierto: hoy el carácter de solo
adición está garantizado **por convención de código**, no por la base de datos. Se cierra
A-03 con una medida concreta y verificable: revocar los permisos de actualización y
borrado sobre las tablas de auditoría para el rol de la aplicación, dejando solo
inserción, y verificarlo con una prueba de integración que intente un borrado y espere
que falle.

## Consecuencias

### Positivas

- La auditoría no se pierde durante una falla, porque se escribe con el hecho.
- Cero latencia de red en el camino crítico.
- Un servicio menos que operar.

### Negativas, y las asumimos

- **El esquema de auditoría se versiona en muchos lugares.** Un cambio en el formato del
  registro obliga a actualizar la librería y redesplegar los siete servicios.
  Mitigación: versionar el contrato del evento y aceptar dos versiones a la vez durante
  las transiciones.
- **No hay un único lugar donde consultar todo.** La consulta transversal requiere
  agregar desde varias bases. Mitigación: MS-Plataforma consume las bandejas de salida y
  materializa la vista consolidada, que es para lectura y no fuente de verdad.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| MS-Auditoria como servicio, escritura sincrónica | Acopla cada operación del negocio a la disponibilidad del servicio de auditoría, y pierde registros exactamente cuando hay incidentes |
| Servicio de auditoría con escritura asíncrona directa | Sin bandeja de salida local no hay garantía de que el registro sobreviva a la caída del productor |
| Base de datos de solo adición dedicada | Añade un motor más al despliegue para un volumen que Postgres maneja sin esfuerzo |

## Evidencia

- `Tukit-Auditoria` declarada por los siete servicios en sus archivos de proyecto.
- Bandejas de salida implementadas, con trabajadores que consumen de RabbitMQ.
- Ausencia verificada de revocación de permisos en base de datos, que es justo lo que
  esta decisión ordena corregir.
