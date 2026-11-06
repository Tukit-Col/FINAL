# ADR 0003 — MS-Comercio permanece en Python

- **Estado:** aceptada
- **Objetivo afectado:** OE4
- **Supersede:** la decisión previa de migrar MS-Comercio a Go

## Contexto

Se había decidido reescribir MS-Comercio en Go, con el argumento de que el catálogo es
grande y Go rinde mejor.

Al inventariar el servicio aparecieron los hechos que la decisión no había considerado:

- Son cerca de 7.600 líneas de Python **ya funcionando**, con cobertura de pruebas del 90 %.
- El ciclo completo de pedidos está implementado con su máquina de estados.
- La última milla está implementada, con zonas, rutas, operador y estados.
- La lógica de retracto de la Ley 1480 está implementada.
- El extractor de datos web es multi-proveedor y usa Playwright, que en Go no tiene
  equivalente maduro.
- El servicio depende de las dos librerías privadas del proyecto, ambas en Python.
- Usa seguridad a nivel de fila de Postgres y transacciones, que habría que reimplementar.

Y el argumento de rendimiento no tiene medición que lo respalde. No existe ninguna
prueba de carga que muestre que Python sea el cuello de botella en este servicio. El
componente que sí tiene un perfil de recursos problemático medido es el reranker, y ese
se trata aparte en el ADR 0005.

## Decisión

**MS-Comercio se queda en Python.** La migración a Go se descarta para la versión 1.

Si en el futuro aparece un cuello de botella **medido**, la respuesta será extraer ese
camino caliente concreto a un trabajador en Go detrás de un puerto, no reescribir el
servicio.

## Consecuencias

### Positivas

- Se liberan aproximadamente dos semanas de trabajo que la reescritura habría consumido
  sin entregar ninguna funcionalidad nueva.
- Se conserva la cobertura de pruebas del 90 % en lugar de reconstruirla desde cero.
- Homogeneidad de lenguaje en el backend: un solo conjunto de herramientas, un solo
  formato de imagen, una sola manera de hacer las cosas para un equipo de cuatro.

### Negativas, y las asumimos

- **Se renuncia al mejor uso de memoria y concurrencia de Go.** Aceptable mientras el
  volumen sea de un piloto escolar y no haya medición que lo exija.
- **La decisión previa queda revertida en el papel.** Esto es una consecuencia real y hay
  que registrarla con honestidad: la decisión original se tomó sin inventariar el código
  existente. Corregirla al descubrir los hechos es el comportamiento correcto, y este ADR
  es el mecanismo para dejarlo trazado.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Reescribir todo MS-Comercio en Go | Alto costo, cero funcionalidad nueva, beneficio no medido, y pérdida de Playwright y de las librerías compartidas |
| Escribir solo los módulos nuevos en Go | Dos lenguajes dentro del mismo servicio, con dos despliegues y dos cadenas de compilación, para un equipo que no tiene capacidad de operar eso |
| Extraer ya el extractor de datos a un trabajador en Go | El extractor corre mensualmente y fuera del camino de petición; optimizarlo no mejora ninguna latencia que el usuario perciba |

## Evidencia

- Cerca de 7.600 líneas de Python en MS-Comercio, con cobertura del 90 % verificada en su
  integración continua.
- Cero líneas de Go en el repositorio.
- Ausencia de pruebas de carga que señalen a Python como limitante.
