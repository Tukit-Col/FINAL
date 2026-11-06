# ADR 0001 — Consolidar los catorce servicios documentados a seis más gateway

- **Estado:** aceptada
- **Objetivo afectado:** OE2
- **Supersede:** el mapa de servicios del SAD vigente

## Contexto

El SAD documenta catorce microservicios: MS-APIGateway, MS-Analitica, MS-Auditoria,
MS-BFFAdmin, MS-Busqueda, MS-Catalogo, MS-Identidad, MS-Instituciones,
MS-Notificaciones, MS-Observabilidad, MS-PQRS, MS-Pedidos, MS-Privacidad y
MS-UltimaMilla.

El código implementa **siete desplegables**, porque el equipo ya había fusionado por
afinidad de dominio durante la Fase 1 sin actualizar el documento:

| Servicio real | Absorbe del SAD |
| --- | --- |
| MS-Cuentas | MS-Identidad, MS-Privacidad |
| MS-Comercio | MS-Catalogo, MS-Pedidos, MS-UltimaMilla |
| MS-Plataforma | MS-PQRS, MS-Analitica, MS-Observabilidad, MS-Notificaciones |
| MS-Busqueda | se mantiene |
| MS-Instituciones | se mantiene |
| MS-BFFAdmin | se mantiene |
| MS-APIGateway | se mantiene |

MS-Auditoria dejó de ser servicio y pasó a librería, lo que se documenta aparte en el
ADR 0002.

El problema no es que la fusión esté mal, es que la documentación describe un sistema
que nadie puede operar ni sustentar. Cada servicio adicional cuesta un contenedor, un
esquema de base de datos, un pipeline de integración continua, un conjunto de secretos,
un manual de operación y una frontera más que puede fallar. Con catorce servicios el
equipo mantiene infraestructura en vez de producto.

## Decisión

**El mapa canónico de Tukit es de seis servicios de dominio más un gateway.** El SAD, el
SDD y el documento maestro se reescriben a ese mapa. Los catorce nombres del SAD se
conservan únicamente como **módulos lógicos** dentro de su servicio contenedor, con
tabla de trazabilidad explícita, para no perder el rastro de los requisitos que los
mencionan.

La frontera que justifica cada servicio es la **razón de cambio**, no la entidad. Cuentas
cambia cuando cambia la ley de datos personales; Comercio cuando cambia la operación de
venta; Búsqueda cuando cambian los modelos; Instituciones cuando cambia la relación con
colegios; Plataforma cuando cambia la manera de atender y observar.

## Consecuencias

### Positivas

- Siete desplegables son operables por un equipo de cuatro personas y demostrables en
  un minikube local, que es lo que exige la sustentación.
- Las transacciones que antes cruzaban frontera ahora son locales. El caso más claro es
  pedido más inventario más entrega, que en el mapa de catorce eran tres servicios y una
  saga, y en Comercio es una transacción de base de datos.
- La documentación pasa a describir el sistema que existe, lo que elimina la clase
  entera de preguntas incómodas del tipo "¿dónde está MS-Notificaciones?".

### Negativas, y las asumimos

- **Menor independencia de despliegue.** Un cambio en notificaciones obliga a desplegar
  todo MS-Plataforma. Aceptable porque el equipo despliega en bloque de todas formas.
- **Menor granularidad de escalado.** No se puede escalar solo el catálogo sin escalar
  pedidos. Mitigación: el componente con perfil de recursos realmente distinto es el
  reranker, y ese sí se aísla, según el ADR 0005.
- **Riesgo de que los servicios fusionados se vuelvan monolitos internos.** Mitigación:
  frontera de módulo explícita dentro de cada servicio y prohibición de que un módulo
  lea tablas de otro, verificada en revisión de código.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Mantener los catorce del SAD | Ya se probó implícitamente y el equipo la abandonó en la práctica. Sostenerla en el papel solo produce documentación falsa |
| Monolito modular único | Habría sido defendible al inicio, pero hoy exige reescribir siete servicios que funcionan, con cobertura de pruebas entre 80 % y 90 %. El costo de la migración no compra ningún atributo de calidad que el mapa de seis no dé ya |
| Consolidar a tres servicios | Metería identidad y comercio en el mismo desplegable, mezclando el servicio con obligaciones legales de datos personales con el que maneja dinero. Mala frontera de riesgo |

## Evidencia

- Conteo de servicios del SAD: catorce nombres distintos en `Arquitectura/SAD_Tukit.tex`.
- Siete desplegables verificados en el inventario de repositorios, con sus migraciones,
  integración continua y superposiciones de Kubernetes.
- Cobertura de pruebas vigente: 90 % en Cuentas y Comercio, 84 % en Instituciones, 80 %
  en Búsqueda.
