# ADR 0010 — La resolución decide sobre el score del reranker y no sobre el score MAUT

- **Estado:** aceptada
- **Objetivo afectado:** OE3
- **Refuerza:** la compuerta G4 del acta de aprobación de OE3

## Contexto

La normalización clasifica cada ítem en resuelto automáticamente, ambiguo o sin
coincidencia, usando un umbral de confianza y, en producción, una separación mínima entre
el primer y el segundo candidato.

Hay dos problemas con la configuración vigente.

**El primero es el tamaño de la muestra.** Los umbrales de producción, 0,85 de confianza y
0,05 de separación, se calibraron sobre **siete ejemplos sintéticos** con macro-F1 igual a
1,0. Un macro-F1 perfecto con siete casos no es evidencia de nada. El propio código lo
reconoce y anota que no existe un conjunto de referencia propio contra el cual recalibrar.

Sí existe. La investigación del MVP construyó un conjunto anotado de **542 ítems**, y sobre
él concluyó un umbral de 0,630 y que la separación mínima **no aportaba** sobre usar el
umbral solo. La mejor señal discriminante resultó ser el score del reranker, con área bajo
la curva de 0,880.

**El segundo problema es más de fondo y es de diseño.** Producción decide sobre el score
MAUT, que ya combina similitud, precio y calidad con pesos. Es decir, el umbral que
determina si acertamos con el producto **depende del precio del producto**. Eso mezcla dos
preguntas que deben permanecer separadas: si el candidato corresponde a lo que pide la
lista, y si es una buena compra.

## Decisión

**La resolución decide sobre el score del reranker, con umbral 0,630 y sin separación
mínima.** El score MAUT se conserva para **ordenar** candidatos, no para decidir estados.

Se traslada el conjunto de 542 ítems anotados al servicio de búsqueda como suite de
calibración reejecutable, y se revalida allí, porque el catálogo de producción no es el
del MVP.

## Consecuencias

### Positivas

- Cierra el flanco más débil de la evidencia de OE3. La pregunta por el tamaño de muestra
  de la calibración pasa de siete casos sintéticos a 542 anotados.
- Separa correctamente relevancia de conveniencia económica. El precio se optimiza donde
  corresponde, en el algoritmo multiobjetivo, no en el umbral de coincidencia.
- Baja la proporción de ítems enviados a revisión humana. Con umbral 0,85 el sistema
  escalaba a un humano casos que ya podía resolver, y la corrida de referencia mostraba
  cerca del 36 % de ítems ambiguos.
- Deja una suite de calibración que se puede volver a correr, donde hoy no hay ninguna.

### Negativas, y las asumimos

- **Baja el umbral, así que sube la cobertura automática y, con ella, la exposición a
  errores automáticos.** La cifra medida en el MVP es 65,3 % de cobertura con 86,7 % de
  precisión. Mitigación: el verificador por modelo de lenguaje, que la evidencia del MVP
  sitúa llevando esa precisión a 93,6 %.
- **Hay que rehacer la calibración tras el cambio de modelo de reranker.** El modelo
  cambió a la variante multilingüe, y aunque la normalización interna acota el efecto de
  escala, la forma de la distribución sí cambia. La revalidación no es opcional.
- **El acta de OE3 queda con una compuerta corregida.** Hay que documentar la corrección
  como mejora posterior al hito, no ocultarla.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Mantener 0,85 con separación de 0,05 | Calibrado sobre siete casos sintéticos y con el precio contaminando la decisión de coincidencia |
| Copiar 0,630 al umbral vigente sin cambiar la señal | Sería incorrecto: 0,630 se midió sobre el score del reranker, no sobre el score MAUT. Son escalas y cantidades distintas |
| Recalibrar el umbral sobre el score MAUT con los 542 ítems | Técnicamente posible, pero conserva el defecto de diseño de que el precio influya en si hay coincidencia |

## Evidencia

- Umbrales de producción y su calibración sobre siete ejemplos, en la evidencia del
  paquete F3-7.1.
- Reconocimiento explícito en el código de producción de que no existe conjunto de
  referencia propio.
- Conjunto anotado de 542 ítems y resultados de calibración en la investigación del MVP.
- Corrida de referencia de extremo a extremo con 60 sublistas y 2.176 ítems, con 36,5 % de
  ítems escalados a revisión del padre.
