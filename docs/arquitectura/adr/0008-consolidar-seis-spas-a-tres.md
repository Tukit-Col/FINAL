# ADR 0008 — Consolidar las seis aplicaciones web a tres

- **Estado:** aceptada
- **Objetivos afectados:** OE2, OE4

## Contexto

`Tukit-Frontend` tiene seis aplicaciones de página única independientes: padres,
administración, colegio, proveedor, operador y editorial.

Cuatro de ellas, administración, proveedor, operador y editorial, son **paneles internos
para personal**, con el mismo patrón de interfaz: tablas, colas de trabajo, formularios de
aprobación. Lo único que las diferencia es el rol de quien entra y el subconjunto de
datos que ve.

Cada aplicación cuesta su propia configuración de construcción, su propio despliegue, su
propio manejo de sesión, su propia biblioteca de componentes que se duplica y su propia
entrada en el pipeline de integración continua. Ese costo se paga seis veces para un
producto que, en el piloto, tiene un puñado de usuarios internos.

## Decisión

**Tres aplicaciones web:**

| Aplicación | Quién entra | Qué absorbe |
| --- | --- | --- |
| Padres | Padres y madres de familia | La aplicación web progresiva actual, sin cambios de alcance |
| Colegio | Rector, coordinación, docentes | La aplicación de colegio actual |
| Personal | Administración de Tukit, proveedores, operadores logísticos, editoriales | Fusiona administración, proveedor, operador y editorial en una sola con navegación por rol |

La separación que se conserva es la que tiene razón de ser: **padres son público general,
colegio son aliados institucionales, y personal son usuarios internos con autenticación
reforzada.** Esas tres tienen perfiles de seguridad y de experiencia genuinamente
distintos. Las cuatro que se fusionan no.

## Consecuencias

### Positivas

- Se eliminan tres despliegues, tres configuraciones de construcción y tres duplicados de
  la biblioteca de componentes.
- El segundo factor obligatorio se aplica en un solo lugar para todo el personal, en vez de
  en cuatro.
- Los paneles internos comparten de verdad los componentes de tabla, cola y aprobación, en
  lugar de copiarlos.

### Negativas, y las asumimos

- **Un proveedor y un administrador de Tukit cargan la misma aplicación.** Hay que
  garantizar por autorización que el proveedor no vea nada que no le corresponde, y la
  autorización pasa a ser crítica en el cliente además del servidor. Mitigación: la
  autorización real vive en el servidor; el ocultamiento en el cliente es comodidad, no
  seguridad, y así debe documentarse.
- **El paquete de la aplicación de personal crece.** Mitigación: carga diferida por rol,
  de modo que nadie descargue las vistas que no puede usar.
- **Hay trabajo de migración de cuatro aplicaciones a una.** Es real, pero es trabajo de
  reorganización de rutas y no reescritura de lógica.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Mantener las seis | Seis veces el costo de mantenimiento para diferencias que son de rol, no de producto |
| Una sola aplicación para todo | Metería el público general y el personal interno en el mismo paquete y la misma frontera de sesión. Mal perfil de seguridad para el que maneja datos de menores |
| Dos aplicaciones, padres y todo lo demás | Colegio no es personal de Tukit: es un aliado externo con su propia identidad visual y su propio respaldo institucional, que es justamente el diferenciador del producto |
