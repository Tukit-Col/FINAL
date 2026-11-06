# ADR 0009 — Diferir la aplicación móvil nativa a trabajo futuro

- **Estado:** aceptada
- **Objetivo afectado:** OE4
- **Requiere:** enmienda al enunciado de OE4 en el VFP

## Contexto

El enunciado del cuarto objetivo específico en el VFP versión 3 pide que las
recomendaciones queden integradas en el sistema "con interfaz web progresiva y aplicación
móvil nativa para iOS y Android".

Sin embargo, los propios documentos del proyecto ya habían reconocido que ese alcance no
estaba financiado:

1. El VFP declara textualmente que la aplicación móvil nativa **no tiene paquete de
   trabajo en la WBS vigente**, y lo registra como **riesgo R-06** del plan de gestión.
2. El hito que cierra OE4 en el WBS, el paquete F4-12.2, pide literalmente **"MVP web
   funcional"** con todas las pantallas núcleo del SRS. La aplicación nativa no aparece en
   su criterio de aceptación.

Es decir, el objetivo enuncia un alcance que el plan de trabajo nunca presupuestó. No es
un incumplimiento sobrevenido: es una inconsistencia de formulación que estuvo declarada
como riesgo desde el principio y que ahora hay que resolver en el papel.

Hay un hecho adicional que ayuda: la aplicación web progresiva ya está envuelta con
Capacitor, y el repositorio tiene los proyectos de Android y de iOS generados. Eso produce
artefactos instalables reales, aunque híbridos y no nativos.

## Decisión

**La aplicación móvil nativa sale del alcance de la versión 1 y pasa a trabajo futuro.**

En consecuencia:

1. **Se enmienda el enunciado de OE4 en el VFP final**, retirando la mención a la
   aplicación móvil nativa para iOS y Android, y dejando la interfaz web progresiva como la
   entrega de interfaz del objetivo.
2. La aplicación nativa se traslada a la sección de trabajo futuro, con la justificación
   de riesgo R-06 como sustento.
3. **Capacitor se documenta como mitigación parcial**, con su naturaleza dicha sin
   adornos: es empaquetado híbrido de la aplicación web, no desarrollo nativo. Da presencia
   en tienda de aplicaciones y acceso a cámara, no rendimiento nativo.

## Consecuencias

### Positivas

- El objetivo pasa a ser verificable con lo que efectivamente se construyó, lo que permite
  declararlo cerrado sin forzar la evidencia.
- Se elimina la pregunta más incómoda de la sustentación, que sería mostrar una web y decir
  que el objetivo pedía dos aplicaciones nativas.
- Capacitor da una respuesta honesta y demostrable a la pregunta por el móvil.

### Negativas, y las asumimos

- **Se reduce el alcance declarado del objetivo**, y eso hay que sustentarlo ante el
  director y el codirector con el riesgo R-06 en la mano. Es una conversación necesaria, no
  evitable.
- **La experiencia móvil híbrida es inferior a la nativa** en gestos, rendimiento de
  desplazamiento y acceso a funciones del sistema. Para el flujo de Tukit, que es subir una
  foto y revisar un kit, la diferencia es tolerable, pero es una diferencia real.
- **Queda sin explorar el trabajo sin conexión**, que era uno de los argumentos a favor de
  lo nativo. También pasa a trabajo futuro.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Construir las dos aplicaciones nativas | Sin paquete de trabajo, sin tiempo y sin capacidad de equipo. Intentarlo pondría en riesgo la entrega completa por un objetivo secundario |
| Declarar que Capacitor es desarrollo nativo | Es falso y un jurado técnico lo detecta de inmediato. El costo de la imprecisión es mucho mayor que el de reconocer el descope |
| Dejar el enunciado como está y entregar solo web | Deja una discrepancia visible entre el objetivo y la evidencia, sin nada en el documento que la explique |

## Evidencia

- El VFP registra la aplicación móvil nativa como sin paquete de trabajo y como riesgo R-06.
- El criterio de aceptación de F4-12.2 en el WBS pide MVP web funcional.
- Configuración de Capacitor y proyectos de Android e iOS presentes en la aplicación de
  padres.
