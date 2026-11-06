# ADR 0011 — Wompi como pasarela de pagos, con PSE como medio preferente

- **Estado:** aceptada
- **Objetivos afectados:** OE4 y viabilidad del modelo de negocio
- **Relación con el WBS:** el paquete F4-11.2 exige checkout **mock** como mínimo; esta
  decisión va más allá del mínimo exigido

## Contexto

Hoy no existe integración de pagos en ningún servicio. El estado de pedido pagado se
alcanza por transición manual, y el checkout de la aplicación de padres crea el pedido sin
cobrar.

Para la tesis eso basta: el criterio de aceptación del paquete F4-11.2 pide explícitamente
checkout mock, y el hito de OE4 pide MVP web funcional. **El pago real no es bloqueante
académico.**

Pero sí es bloqueante para operar como negocio, y el equipo decidió incorporarlo ahora.
Por eso esta decisión se toma con el criterio del negocio y no con el mínimo académico.

El dossier ya tiene el análisis de alternativas verificado:

| Pasarela | Tarjetas | PSE | Nota |
| --- | --- | --- | --- |
| Wompi, operada por Bancolombia | cerca de 2,99 % más tarifa fija | alrededor de 1,49 % | Respaldo bancario local |
| ePayco | entre 2,79 % y 3,50 % según volumen | — | Rango más amplio, depende de volumen que aún no existe |
| Stripe | — | — | **Descartada**: verificado en agosto de 2026 que no habilita cuentas para negocios registrados en Colombia |

Hay un dato del modelo financiero que convierte esto en una decisión arquitectónica y no
solo comercial. La contribución por kit se modeló con un costo de pasarela cercano a
2,65 %, mientras la tarifa de mercado en tarjetas es del orden de 2,99 %. La diferencia se
cubre **enrutando el pago por PSE**, que cuesta alrededor de la mitad. Es decir, la
estructura del checkout influye directamente en si la contribución unitaria se sostiene.

## Decisión

**Wompi es la pasarela de pagos de Tukit, y PSE es el medio de pago preferente en la
interfaz de checkout.**

Consecuencias de diseño que se derivan:

1. La integración se hace **detrás de un puerto** `PasarelaPagos`, con el adaptador de
   Wompi y un adaptador simulado. El adaptador simulado es el que corre en las pruebas y en
   la demostración académica, lo que preserva el checkout mock que el WBS exige.
2. El checkout presenta **PSE primero** y tarjeta como alternativa, porque de ese orden
   depende el margen. No es una preferencia estética.
3. La confirmación de pago se resuelve por **notificación web entrante idempotente**, no
   por la respuesta de la petición, porque la notificación puede llegar duplicada, fuera de
   orden o perderse.
4. Una notificación perdida o un rechazo **crea un Caso** de tipo `PaymentFailure`, según
   el ADR 0004, y el pedido queda en estado pendiente con explicación y reintento
   disponible, nunca en una pantalla muerta.

## Consecuencias

### Positivas

- Habilita cobrar, que es la diferencia entre un prototipo y un negocio.
- El puerto mantiene intacta la evidencia académica: las pruebas y la demostración siguen
  corriendo contra el adaptador simulado, sin claves ni dinero real.
- PSE primero protege la contribución unitaria que el dossier proyecta.
- El manejo idempotente de notificaciones y el Caso por fallo cubren el camino infeliz de
  pago, que era uno de los huecos señalados del flujo.

### Negativas, y las asumimos

- **Se añade una dependencia externa en el camino del dinero.** Mitigación: el estado del
  pedido nunca se deriva de la respuesta sincrónica, solo de la notificación verificada.
- **Hay obligaciones que no son de código**: constitución del comercio, cuenta bancaria,
  verificación de identidad ante Bancolombia. Son trámites con tiempos propios y hay que
  arrancarlos en paralelo al desarrollo.
- **Aparece manejo de datos financieros**, con su propia superficie de cumplimiento. Se
  mitiga no almacenando nunca datos de tarjeta: la captura ocurre del lado de Wompi.
- **Riesgo de que la integración desplace trabajo de la tesis.** Es real. Se acota con el
  puerto: si la integración se atrasa, el adaptador simulado sostiene la entrega académica
  sin cambiar una línea del resto del sistema.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Quedarse solo con checkout mock | Suficiente para la tesis, insuficiente para operar. El equipo decidió avanzar al negocio |
| ePayco | Rango de comisión más amplio y dependiente de volumen que todavía no existe; sin la ventaja de respaldo bancario local |
| Stripe | No habilita cuentas para negocios colombianos, verificado |
| Solo PSE, sin tarjeta | Más barato, pero excluye a quien no tiene cuenta bancaria habilitada, y en un producto de padres de familia eso es perder ventas |
| Pasarela propia | Absurdo para el volumen y expone a obligaciones de cumplimiento que ninguna startup temprana debería asumir |

## Evidencia

- Análisis de comisiones y descarte de Stripe en la sección de finanzas del dossier, con
  fuente verificada.
- Entradas `wompi_pricing` y `epayco_pricing` en la bibliografía del dossier, hasta ahora
  sin citar, que esta decisión pone en uso.
- Ausencia verificada de cualquier código de pasarela en los repositorios de comercio.
