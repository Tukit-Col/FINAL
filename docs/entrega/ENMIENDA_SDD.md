# Enmienda al SDD (alineación con el código de `validacion/oe5`, el SAD y la VFP v4)

Documento de trabajo, no es una versión aprobada del SDD. Fuente: `SDD/SDD_Tukit.pdf` (texto extraído con pdftotext; las citas conservan el texto, aunque el PDF pierde las ligaduras "fi" y "ti", p. ej. "delidad" por "fidelidad"). No se modificó el original. Patrón: Texto actual (cita textual) / Texto de reemplazo / Por qué. Los números de línea son los del texto extraído y sirven solo para ubicar; el título de sección ayuda a encontrar el pasaje en el PDF. Verificado contra `tukit/servicios/inteligencia/tukit_inteligencia/optimizador.py`, `trabajos.py` y el SAD.

## D1. "Seis servicios de dominio" frente a "siete"

**D1.a Sección 2.3, Dependencias externas (línea 516)**

Texto actual: "La base de datos relacional con extensión vectorial sostiene la persistencia de los seis servicios de dominio."

Texto de reemplazo: "La base de datos relacional con extensión vectorial sostiene la persistencia de los cinco servicios de dominio con base propia (identidad, catálogo, inteligencia, comercio y operación)."

Por qué: el SAD (líneas 315 a 323 del texto extraído) explica que el mapa de seis servicios de dominio era el del ADR 0001, que el ADR 0012 lo corrigió, y que el mapa vigente son cinco servicios de dominio, una puerta de enlace delgada y un desplegable de ingesta sin base propia: siete desplegables sobre cinco bases de datos (ADR 0012, 0014). El directorio `tukit/servicios/` contiene catalogo, comercio, gateway, identidad, inteligencia y operacion; ingesta es el séptimo desplegable. "Seis" quedó de la versión intermedia. Los otros dos pasajes con "siete servicios" (líneas 540 y 1289) son correctos si se leen como siete desplegables; se propone reemplazar "servicios" por "desplegables" por claridad:

Texto actual (línea 540): "se propaga a los siete servicios con un cambio de versión de librería y no con siete parches"
Texto de reemplazo: "se propaga a los siete desplegables con un cambio de versión de librería y no con siete parches"

Texto actual (línea 1289): "uniformes en los siete servicios"
Texto de reemplazo: "uniformes en los siete desplegables"

Por qué: el mismo SAD usa "desplegables" (líneas 322, 878, 998, 1430, 2106) y la VFP v4 también. Si el prefijo MS- del mapa anterior se mantiene en el SDD (decisión registrada: nombres heredados de MS-*), añadir una nota que remita al mapa vigente del SAD.

Hallazgo adicional: LEEME dice 70 tablas y el README 69; el manifiesto (`arquitectura/manifiesto.toml`) cuenta 74 y el código también (modelos SQLAlchemy). Cifra única para todos los documentos: 74.

## D2. Objetivos del optimizador: de tres a cuatro, con personaje como eje propio

**D2.a Sección 8.5.1 (líneas 2029 a 2036)**

Texto actual: "Los cuatro objetivos, todos expresados como minimización por convención de la biblioteca, son el costo total de los ítems cubiertos, la fidelidad negada como promedio ponderado de la similitud semántica, la calidad negada como promedio ponderado de la combinación de puntaje de calidad y puntaje de afinidad de personaje, y la cobertura negada como fracción de ítems cubiertos. Se declara una limitación conocida: la calidad y la afinidad de personaje están combinadas en un solo objetivo, de modo que no hay todavía un eje independiente de afinidad, y los tres perfiles distinguen sobre todo el compromiso entre costo, calidad y fidelidad."

Texto de reemplazo: "Los cuatro objetivos son el costo total de los ítems cubiertos (se minimiza), la fidelidad de marca, la disponibilidad y la afinidad de personaje (se maximizan; la biblioteca los recibe negados). La afinidad de personaje es un eje independiente, de modo que el perfil Fan se distingue por ese objetivo y no por un promedio con la calidad. La calidad ya no es un objetivo: entra en la selección a posteriori (D3). Los perfiles son Ahorrador, Fan, Premium y A tu Medida (ADR 0030)."

Por qué: el SDD describe una limitación que el código ya resolvió: el optimizador tiene cuatro objetivos (costo, fidelidad, disponibilidad, personaje) y cuatro perfiles. Hay una incoherencia interna del SDD: dice "cuatro objetivos" y luego "los tres perfiles"; la mezcla viene de comparar la versión de tres objetivos con la de cuatro. El SPMP v3 y la WBS v3 también hablan de tres perfiles o de calidad y cobertura como objetivos; ver sus enmiendas.

**D2.b Ejecución exacta y presupuesto**

Texto de reemplazo (añadir al final de 8.5.1): "Cuando el espacio de combinaciones es de hasta 4.096 (LIMITE_ENUMERACION) el frente se obtiene por enumeración exacta; por encima se usa NSGA-II (pymoo, sin respaldo heurístico: si la biblioteca falla, la corrida falla de forma visible). Las restricciones de disponibilidad y categoría se aplican por construcción; el presupuesto máximo se aplica después de obtener el frente (ADR 0029)."

Por qué: el código tiene `LIMITE_ENUMERACION = 4096` y no existe respaldo. Esto contradice la frase del SDD sobre restricciones "del solucionador" para el presupuesto; ajustar esa frase a "la cobertura mínima es la restricción del solucionador; el presupuesto se aplica después del frente".

## D3. Pesos de la utilidad multiatributo

**D3.a Tabla de parámetros (líneas 2724 a 2726)**

Texto actual: "Pesos de la utilidad multiatributo 0,6 / 0,3 / 0,1"

Texto de reemplazo: "Pesos de la utilidad multiatributo (selección a posteriori, MAUT) 0,285 precio / 0,273 marca / 0,255 calidad / 0,187 personaje (encuesta, P21)". Fórmula: U = w_precio·u_costo + (w_marca+w_calidad)·u_fidelidad + w_personaje·u_personaje. Se declara el supuesto de independencia preferencial. Regla de recomendación: Fan si pidió personaje; si no, A tu Medida cuando ese kit existe, es decir, cuando eligió el punto medio de gasto o declaró un tope (con el tope declarado o, sin tope, a mitad de camino entre Ahorrador y Premium); si no existe, Premium cuando el sobreprecio aceptado es de al menos 10 % y MAUT lo prefiere; en otro caso Ahorrador; y si el elegido se pasa del tope, el de mayor fidelidad que cabe.

Por qué: los pesos 0,6/0,3/0,1 eran de la versión anterior (tres criterios). El diseño de MAUT a posteriori está en `tukit/docs/diseno/specs/2026-09-22-optimizador-nsga2-maut-design.md`. Atención: en la tabla de resolución, el SDD usa "utilidad multiatributo" también para el puntaje del emparejamiento (similitud, precio y calidad), que es otra cosa; renombrar uno de los dos. Los pesos P21 están en `servicios/inteligencia/tukit_inteligencia/modelos/base.py` y MAUT en `optimizador.py` (`elegir_recomendado_maut`), desde a664810.

## D4. Población y generaciones

**D4.a Sección 8.5.2 (línea 2037) y tabla (línea 2730)**

Texto actual: "con población de sesenta individuos y cien generaciones, y semilla fija... Esos parámetros son fijos y no dependen del tamaño de la lista, lo que obliga a dos protecciones." y "Población y generaciones 60 / 100".

Texto de reemplazo: "con población min(200, max(40, 12·n)) y generaciones 20·log10(tamaño del espacio) acotadas entre 30 y 120, y semilla fija. Los parámetros dependen del tamaño de la lista, por lo que la protección principal es el tope de entrada y el tiempo de espera." Tabla: "Población y generaciones 40 a 200 (12 por ítem) / 30 a 120 (20·log10 del espacio)".

Por qué: el código (`optimizador.py`, líneas 113 a 137: `_POBLACION_MIN = 40`, `_POBLACION_MAX = 200`, `_GENERACIONES_MIN = 30`, `_GENERACIONES_MAX = 120`) escala ambos con el problema. Los parámetros "fijos 60/100" ya no existen. Pendiente: confirmar con el equipo el tope de 50 ítems, el tiempo de espera de 30 s y los 2 procesos concurrentes, que esta revisión no verificó en el código.

## D5. Los dos pares de "0,85"

**D5.a Tabla de parámetros (líneas 2727 y 2729) y secciones 8.3 y 8.4.1 (líneas 1907 a 1932)**

Texto actual: "Umbral de coincidencia exacta y parcial 0,85 / 0,50" y "Umbral y brecha de resolución 0,85 / 0,05".

Texto de reemplazo: separar y nombrar con claridad (decisión de la coordinación: τ vale 0,75 por configuración, sin calibrar, y se declara como limitación; se retiran 0,630 y 0,85 como τ):

1. "Clasificación del puntaje del mejor candidato (heredada del puntaje multiatributo): exacta desde 0,85, parcial desde 0,50 (regla adicional: un candidato sin precio nunca es exacta)." Estados de v3: coincidencia y coincidencia parcial.
2. "Decisión de resolución: umbral τ = 0,75 por omisión (`TAU_POR_OMISION`, variable de entorno TUKIT_TAU, en `trabajos.py`), aplicado al parecido del resolvedor híbrido (léxico más coseno de `gemini-embedding-001` de 1.024 dimensiones, índice HNSW en pgvector). El valor está configurado y no calibrado: en los datos disponibles hubo 1.265 resoluciones automáticas con similitud 1,0 y ninguna revisada por una persona, de modo que no hay casos dudosos con los cuales estimarlo. Es una limitación declarada." Estados vigentes: RESUELTO_AUTO, AMBIGUO, SIN_MATCH y HUECO_CATALOGO. En el código, `estado_desde_emparejamiento` usa solo τ; la brecha δ = 0,05 del SDD no aparece en esa función y se retira o se marca como no implementada.

Por qué: son dos mecanismos distintos que comparten el valor 0,85 por coincidencia y se leen como uno solo. El texto del SDD afirma que "los valores vigentes se calibraron sobre siete ejemplos sintéticos" y menciona 0,630 del ADR 0010. Ambos se retiran como valor de τ. El 0,85 y el 0,50 de la clasificación del puntaje multiatributo (punto 1) son otro parámetro y se nombran como tal, sin llamarlos τ. No se citan precisión, cobertura ni AUC de una calibración, porque no hay una válida.

## D6. Pendientes que el SDD no recoge (propuestos, no obligatorios)

1. NL2C: planificar y luego ejecutar, con separación de datos y control al estilo CaMeL; esquemas Pydantic con campos extra prohibidos; interfaz generativa armada por el servidor y validada de nuevo en la web; doble feature flag; límite de tasa en la puerta de enlace (ADR 0047); OWASP LLM01, 02, 05, 06 y 10. Modelo gemini-3.5-flash-lite a temperatura 0. NL2C está fusionado en `validacion/oe5` (S4). Sin cifras finales de utilidad ni de tasa de éxito de ataque en los documentos: la ronda 3 está en curso con un criterio modificado.
2. Pago: Wompi con widget (ADR 0033) y webhook (ADR 0034); modo por defecto simulado (WOMPI_MODO). Retracto de la Ley 1480, art. 47.
3. Despliegue: Minikube local; cualquier mención del SDD a autoescalado o Kubernetes productivo queda como trabajo futuro.

## Preguntas abiertas

1. Ninguna sobre τ: rige 0,75, sin calibrar.
2. MAUT (S2) y NL2C (S4) ya están fusionados en `validacion/oe5` (a664810).
3. Tablas: 74 (suma del manifiesto: identidad 16, catálogo 19, inteligencia 12, comercio 18, operación 9; coincide con los modelos del código). LEEME dice 70 y el README 69: ambos desactualizados.
4. El SDD ya mezcla los nombres MS-* (mapa de seis servicios) con el mapa vigente; decidir si se agrega una tabla de equivalencias.
