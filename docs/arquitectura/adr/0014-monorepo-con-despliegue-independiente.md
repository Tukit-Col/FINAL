# ADR 0014 — Un monorepo con despliegue independiente, y cómo sostenerlo académicamente

- **Estado:** aceptada (sesión de aprobación del OE2, 2026-09-21; ver `ACTA_APROBACION_OE2.md`)
- **Objetivos afectados:** OE2 (diseño y su defensa), OE4 (ejecución del MVP)
- **Relación con el WBS:** condiciona el paquete F2-5.4 de aprobación y toda la fase 4
- **Relación con otras decisiones:** habilita la prueba de arquitectura que protege los
  ADR 0012 y 0013; sucede al ADR 0001, que redujo de catorce servicios a seis

## Contexto

Tukit tiene hoy **dieciséis repositorios para un equipo de tres personas**. La decisión de
construir la versión ordenada del sistema al lado, en código nuevo, obliga a elegir de
nuevo la topología de repositorios, y conviene no reproducir la actual por inercia.

El costo de la topología actual es medible y se pagó durante este mismo trabajo. Al mover
la función de redacción de nombres de menores a la librería compartida, hubo que **editar
siete archivos `pyproject.toml`** para subir la versión de `tukit-auditoria` de 0.6.0 a
0.7.0, y después nada instalaba porque el tag `v0.7.0` no existía todavía en el remoto. Un
cambio de una función exigió siete ediciones, un release y un tag. La verificación local
solo fue posible instalando las librerías desde clones locales, es decir, saltándose el
mecanismo que la topología impone.

Hay un costo mayor y menos visible. Los ADR 0012 y 0013 dependen de que los servicios **no
declaren modelos de dominios ajenos**: es la única defensa contra volver a tener dos
maestros de `productos_catalogo`. Esa defensa solo es automatizable si la integración
continua puede inspeccionar todo el árbol de código a la vez. Repartida en dieciséis
repositorios, ningún proceso ve el sistema completo, y la frontera queda sostenida
únicamente por la disciplina de quien escribe el código. La evidencia de que esa disciplina
no basta ya existe: el catálogo se duplicó exactamente así.

### La objeción académica, y por qué no aplica

La objeción previsible en la sustentación es que un monorepo contradice el estilo de
microservicios. No lo contradice, y el marco para decirlo con precisión ya es estándar.

La norma **ISO/IEC/IEEE 42010** describe una arquitectura mediante vistas separadas, cada
una dirigida a preocupaciones distintas. El **modelo 4+1 de Kruchten** distingue
explícitamente la *vista de desarrollo*, que describe cómo se organiza el código en módulos
y repositorios, de la *vista física*, que describe cómo se despliega. Son vistas
diferentes por definición. El modelo **C4 de Brown** hace la misma separación: un
*contenedor* es una unidad desplegable, y la propia notación advierte que un contenedor no
equivale a un repositorio.

Lo que define el estilo de microservicios, en la formulación de Lewis y Fowler y en la de
Newman, es la **desplegabilidad independiente** y la **propiedad descentralizada de los
datos**. Ninguna de las dos habla del número de repositorios. Un sistema con siete
desplegables, cinco bases de datos separadas y una regla de no compartir esquema es una
arquitectura de microservicios, esté el código en uno o en dieciséis árboles.

El argumento se puede dar vuelta y queda a favor del monorepo. Una **función de aptitud**
en el sentido de Ford, Parsons y Kua, que verifique de forma automática y continua que
ningún servicio importa el modelo de otro, es la diferencia entre *afirmar* que hay
contextos delimitados y *demostrarlo*. Esa función solo es mecanizable si la integración
continua ve todo el código. El monorepo, entonces, no debilita la afirmación arquitectónica:
es lo que la vuelve verificable.

## Decisión

Se adopta **un solo repositorio, `tukit`, con siete desplegables independientes y cinco
bases de datos separadas**.

```
tukit/
├── servicios/
│   ├── identidad/   catalogo/   inteligencia/   comercio/   operacion/   ingesta/   gateway/
├── apps/            web/   admin/
├── libs/            py/tukit_comun/   go/tukitgo/
├── datos/           corpus, conceptos, golden sets, semillas
├── docs/adr/        continuando esta numeración
└── infra/           minikube, compose, integración continua
```

Las reglas que hacen que esto siga siendo una arquitectura de microservicios, y que se
verifican de forma automática, no por convención:

1. **Ningún servicio importa código de otro servicio.** Solo puede importar de `libs/`.
2. **Ningún servicio declara un modelo de datos de un dominio ajeno.**
3. **Ningún servicio se conecta a la base de otro.** Cinco bases, un dueño cada una.
4. **Cada servicio construye su propia imagen y se despliega por separado.**
5. La comunicación es HTTP sincrónico para consultas y eventos asincrónicos para el resto.

Las reglas 1, 2 y 3 se implementan como pruebas que fallan la integración continua. Se
escriben **antes** de mover la primera tabla, para que el movimiento no borre las fronteras
en vez de trazarlas.

### Cómo se presenta en la memoria

La estructura de presentación que resuelve la objeción por construcción, en vez de
defenderse de ella:

| Vista | Contenido | Instrumento |
|---|---|---|
| Contexto | Actores y sistemas externos | C4 nivel 1 |
| Lógica | Contextos delimitados y su justificación | DDD, los cuatro criterios de descomposición |
| **Desarrollo** | **Monorepo, declarado explícitamente como distinto del despliegue** | 4+1, este ADR |
| **Física** | **Siete desplegables, cinco bases, minikube** | C4 nivel 2 |
| Procesos | Saga de pago, pipeline durable, eventos | Diagramas de secuencia |
| Datos | 67 tablas, clasificación, tenencia | `ESQUEMA_OBJETIVO.md` |
| Evaluación | Escenarios, puntos de sensibilidad y de compromiso | ATAM |
| **Evaluación continua** | **Funciones de aptitud en integración continua** | Arquitectura evolutiva |
| Decisiones | Las alternativas rechazadas y por qué | 14 ADR en formato Nygard |

Declarar la vista de desarrollo **por separado y a propósito** es lo que convierte el
monorepo de aparente inconsistencia en decisión informada. La fila de evaluación continua es
la que más distingue el trabajo: la mayoría de las tesis de arquitectura evalúan una vez, en
el ATAM, y presentan el diseño como una fotografía. Aquí la conformidad se verifica en cada
integración.

## Alternativas consideradas

**Un repositorio por servicio, ordenados.** Es la topología actual sin el desorden.
Rechazada por dos razones. Reproduce el costo de coordinación ya medido: un cambio de
contrato entre dos servicios necesita dos pull requests y un release intermedio, y durante
la ventana entre ambos el sistema está inconsistente. Y deja las funciones de aptitud sin
un lugar donde correr, que es justamente lo que permitió el defecto que este rediseño
corrige.

**Monorepo para Python y repositorios aparte para Go.** Rechazada porque el criterio de
partición sería el lenguaje, que es una propiedad de implementación, y no el dominio. Las
fronteras del sistema quedarían dibujadas por la herramienta en vez de por el negocio. Y
los dos componentes candidatos a Go, la ingesta y el gateway, son justamente los que más
necesitan compartir contratos con los servicios en Python.

> **Corrección.** La redacción original decía «los dos componentes **en** Go», en presente,
> como si existieran. **No existen: hoy el sistema tiene cero líneas de Go**, según el
> ADR 0003. Son candidatos, y ni siquiera firmes: el perfilado de latencia
> (`Arquitectura/PERFILADO_PIPELINE.md`) encontró que el 95,3 % del tiempo del pipeline lo
> causaba una sola línea de Python, la reconstrucción del grafo de sustituibilidad, que se
> arregla con caché y no cambiando de lenguaje. La ingesta sigue siendo candidata por su
> perfil de concurrencia, pero solo después de corregir los defectos estructurales que
> tiene hoy; migrarla antes solo traduciría el defecto a otro lenguaje.
>
> El argumento de esta alternativa no depende de que Go exista, así que la decisión no
> cambia: si algún día hay un componente en otro lenguaje, partir por lenguaje seguiría
> siendo partir por la herramienta.

**Un solo desplegable, o sea un monolito modular.** Se evaluó en detalle y se rechazó en el
rediseño. Los servicios tienen perfiles de recurso incompatibles: `inteligencia` necesita
GPU y memoria, mientras `comercio` necesita transaccionalidad y disponibilidad constante.
Empaquetarlos juntos obliga a dimensionar todo por el más exigente. A eso se suma una
frontera de cumplimiento: los datos de menores en `identidad` justifican aislamiento de
proceso y de base.

## Consecuencias

**A favor.** Un cambio de contrato cabe en un pull request con sus dos lados y sus pruebas.
Desaparecen los números de versión internos y los tags de las librerías compartidas. Las
funciones de aptitud pueden ver todo el sistema. La memoria cita un solo árbol con una sola
historia, en vez de reconciliar dieciséis.

**En contra.** La integración continua necesita ejecución selectiva por ruta para no correr
todo en cada commit; con siete servicios esto es configuración, no investigación. El árbol
mezcla hoy Python y TypeScript, y previsiblemente Go más adelante, así que hace falta un
ejecutor de tareas único que unifique los comandos. Y el permiso de lectura es de grano grueso: cualquiera con acceso al
repositorio ve todo el código, lo cual para un equipo de tres es irrelevante y para uno de
treinta no lo sería.

**Riesgo que hay que vigilar.** Un monorepo facilita importar de donde no se debe,
precisamente porque el código está ahí al alcance. Ese riesgo es real y es la razón por la
que las reglas 1, 2 y 3 se escriben como pruebas antes de mover la primera tabla, y no
después.
