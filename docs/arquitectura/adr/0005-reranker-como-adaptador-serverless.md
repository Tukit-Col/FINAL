# ADR 0005 — Reranker como adaptador a GPU serverless y no como servicio

- **Estado:** aceptada
- **Objetivos afectados:** OE2, OE3

## Contexto

El reranker de tipo codificador cruzado es el único componente del sistema con un perfil
de recursos radicalmente distinto al resto: necesita GPU para ser rápido, y el resto del
sistema no necesita GPU en absoluto.

Su carga además es extremadamente estacional. La temporada escolar concentra la enorme
mayoría de las transacciones en unos dos meses del año. Un servicio con GPU encendido
todo el año cobra los diez meses en que nadie sube listas.

En procesador, con cuatro núcleos, reordenar los pares de una lista completa toma decenas
de segundos, que es inaceptable dentro de una petición.

## Decisión

**El reranker no es un microservicio: es un puerto con dos adaptadores.**

- Adaptador local en procesador, que es el que corre en desarrollo y en la demostración
  académica, y sirve de respaldo.
- Adaptador a GPU serverless para producción.

La plataforma elegida es Modal, por el tiempo de arranque en frío: entre 1,5 y 3,5
segundos, contra 15 a 40 segundos de RunPod y varios minutos de SageMaker. Con carga
estacional, el arranque en frío es el criterio dominante, porque la primera petición
después de una pausa es la que define la latencia percibida.

El puerto garantiza además que si el adaptador remoto falla, el pipeline **degrada al
orden de la fusión recíproca** en vez de romperse.

## Consecuencias

### Positivas

- Costo fijo cero los meses sin temporada, que es exactamente el perfil de una startup
  estacional sin financiación.
- La degradación elegante ya está implementada: si el reranker no responde, el sistema
  entrega el orden de la fusión, con peor calidad pero sin caerse.
- Un desplegable menos en el clúster, y ninguna GPU que administrar.

### Negativas, y las asumimos

- **Dependencia de un proveedor externo en el camino de la petición.** Mitigación: el
  puerto y el respaldo en procesador; el sistema funciona sin Modal, solo más lento.
- **El arranque en frío es visible.** Unos segundos en la primera lista tras una pausa.
  Mitigación: calentamiento programado en horas de tráfico esperado durante temporada.
- **La calidad del reranker vigente es cuestionable y hay que decirlo.** El modelo
  documentado como base está entrenado para chino e inglés, y todo el catálogo y las
  consultas de Tukit están en español. El código ya migró al modelo multilingüe, pero la
  recalibración de umbrales contra ese cambio de distribución está pendiente y se trata en
  el ADR 0010.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Microservicio con GPU dedicada permanente | Paga diez meses de inactividad al año |
| Solo procesador, sin GPU | Decenas de segundos por lista dentro de la petición, inaceptable para la meta de latencia percibida |
| RunPod | Arranque en frío de 15 a 40 segundos, que con carga intermitente es la métrica que más duele |
| SageMaker | Arranque en frío de minutos y complejidad de configuración desproporcionada |
| Renunciar al reranking | Perdería la mejora de precisión que el reordenamiento aporta sobre la fusión, y es justo el componente que sostiene la corrección del mapeo |
