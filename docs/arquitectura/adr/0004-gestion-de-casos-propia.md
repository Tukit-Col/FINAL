# ADR 0004 — Gestión de casos de primera parte en MS-Plataforma

- **Estado:** aceptada
- **Objetivos afectados:** OE2, OE4

## Contexto

Hoy MS-Plataforma tiene una entidad de peticiones, quejas, reclamos y sugerencias que
cumple el plazo legal, pero que **solo se crea cuando un humano la abre**. Cuando el
sistema falla por su cuenta, lo que ocurre es que se dispara una alarma técnica: nadie le
responde al padre y no queda rastro consultable de que su compra se rompió.

Esto es el hueco de los caminos infelices. El padre subió la lista, algo falló, y desde su
lado el sistema simplemente no funcionó.

Se evaluó usar Salesforce Service Cloud, cuyo modelo de Caso es el estándar de la
industria y el que inspira este diseño.

## Decisión

**Se implementa un dominio de Casos propio dentro de MS-Plataforma**, con esquema
inspirado en el objeto Case de Salesforce pero sin licencia ni dependencia externa.

Campos: número de caso, asunto, descripción, estado (nuevo, en curso, escalado, cerrado),
origen (web, sistema, administrador), prioridad, tipo, contacto, cuenta, tipo y
referencia de la entidad relacionada, responsable, caso padre, razón de cierre y sellos de
tiempo. Los cambios de estado se registran en un histórico de solo adición mediante
`Tukit-Auditoria`.

Lo que cambia respecto a hoy es la regla de oro: **cada camino infeliz del flujo crea un
Caso con origen `sistema`**, y el padre ve una explicación y un siguiente paso, nunca una
pantalla muerta.

| Etapa | Falla | Tipo de caso | Qué ve el padre |
| --- | --- | --- | --- |
| Autenticación | Segundo factor perdido, cuenta bloqueada | AuthFailure | Recuperación asistida |
| Percepción | Documento ilegible, modelo caído | MappingFailure | Captura manual asistida con lo ya leído |
| Normalización | Confianza baja o sin coincidencia | MappingFailure | Ítem marcado en revisión, el resto del kit avanza |
| Optimización | Excede el presupuesto de tiempo | SystemError | Resultado parcial, primero el kit Ahorrador |
| Pago | Notificación perdida o rechazo | PaymentFailure | Orden pendiente con explicación y reintento |
| Inventario | Agotado al momento de pagar | StockFailure | Sustituto del mismo pipeline, con aviso explícito |
| Entrega | No entregado, dirección errada | DeliveryFailure | Reagendamiento más notificación |

## Consecuencias

### Positivas

- Los caminos infelices pasan de ser alarmas invisibles a ser compromisos con el usuario
  que se pueden medir, con plazo y con responsable.
- El mismo dominio sirve para las peticiones legales de la Ley 1581, que ya existían, sin
  duplicar modelo.
- Da materia medible a la sustentación: número de casos por tipo y tiempo de cierre son
  evidencia de que la arquitectura maneja el fallo, no solo el éxito.

### Negativas, y las asumimos

- **Hay que construir lo que Salesforce da hecho:** escalamiento, asignación de
  responsable, plazos, cola de trabajo. Se construye la versión mínima, no la completa.
- **Riesgo de inundación de casos.** Un fallo sistémico podría generar miles de casos
  idénticos. Mitigación: agrupar por huella del error y crear un caso padre con casos hijo,
  que es justamente para lo que sirve el campo de caso padre.
- **Sin licencia no hay consola de agente.** El panel de administración tiene que
  proveerla, y eso es trabajo de interfaz que no existía.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Salesforce Service Cloud | Costo de licencia por agente insostenible antes de facturar, y una dependencia externa en el camino de atención de un piloto escolar |
| Seguir solo con alarmas técnicas | Es el estado actual y es precisamente el problema: nadie le responde al usuario |
| Usar un sistema de tiquetes de código abierto de terceros | Un despliegue más que operar, y el modelo de datos no se integra con las entidades del dominio, que es lo que da valor al campo de entidad relacionada |
