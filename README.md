# Tukit

Armado asistido de kits escolares. Un acudiente sube la lista de útiles que le dio el
colegio, el sistema la interpreta, la normaliza contra un catálogo canónico y le arma kits
optimizados que balancean precio, calidad y preferencias.

Este repositorio reemplaza a los dieciséis anteriores. No es una reescritura: el trabajo
bueno y probado se porta, y lo que cambia es el modelo de dominio, que era donde estaban
los defectos.

```bash
make preparar     # entorno y dependencias
make fronteras    # verifica las fronteras de arquitectura
make verificar    # todo lo que corre la integración continua
```

---

## Cómo está organizado, y por qué así

Un monorepo con **siete desplegables independientes y cinco bases de datos separadas**.

```
servicios/     identidad  catalogo  inteligencia  comercio  operacion  ingesta  gateway
apps/          web  admin
libs/          py/tukit_comun   go/tukitgo
arquitectura/  manifiesto.toml + las funciones de aptitud
datos/         corpus, conceptos, conjuntos de referencia
infra/         minikube, compose, despliegue
```

Un repositorio no es un desplegable. Que el código viva junto y se despliegue por separado
son dos decisiones distintas, y aquí se toman distinto a propósito: el
[ADR 0014](../Arquitectura/adr/0014-monorepo-con-despliegue-independiente.md) lo argumenta
con la norma 42010 y el modelo 4+1, que separan la vista de desarrollo de la vista física.

La razón concreta de haber juntado el código: mover una función de redacción a la librería
compartida, en la estructura anterior, exigió editar **siete archivos `pyproject.toml`** y
publicar un tag antes de que algo instalara. Aquí es un commit.

---

## Los cinco invariantes

No son recomendaciones. Los cuatro primeros los verifica `arquitectura/test_fronteras.py`
en cada integración, y rompen la construcción.

1. **Ningún servicio importa código de otro servicio.** Solo de `libs/`.
2. **Ningún servicio declara una tabla de un dominio ajeno.**
3. **Ningún servicio se conecta a la base de otro.** Cinco bases, un dueño cada una.
4. **Toda referencia a otro dominio está declarada** en `arquitectura/manifiesto.toml`.
   Postgres no puede imponerla, así que al menos tiene que estar escrita.
5. **Cada servicio construye su imagen y se despliega por separado.**

### Por qué existen estas pruebas

El defecto más grave del sistema anterior fue que `productos_catalogo` estaba declarada
como maestro en dos servicios a la vez. No pasó por falta de criterio: pasó porque nada
verificaba el criterio. La disciplina humana ya falló una vez en este proyecto.

En términos de arquitectura evolutiva, son **funciones de aptitud**: pruebas automáticas y
continuas sobre una característica arquitectónica. Son la diferencia entre *afirmar* que
hay contextos delimitados y *demostrarlo*.

Y están demostradas: `arquitectura/test_fronteras_se_activan.py` le da de comer una
infracción de cada tipo y comprueba que la detecte. Una función de aptitud que nunca ha
fallado no está probada, podría estar midiendo nada.

---

## Por qué estos siete servicios

La separación **no** se justifica por escalabilidad. Se midió la carga proyectada y sobra
capacidad por unos tres órdenes de magnitud; sostener ese argumento frente a un jurado no
resistiría la primera pregunta. Las tres razones que sí se sostienen:

| Criterio | Qué separa |
|---|---|
| **Recuperabilidad asimétrica** | `catalogo` se reconstruye scrapeando y tolera perder horas. `comercio` no puede perder un byte. Objetivos de punto de recuperación incompatibles en el mismo almacén. |
| **Frontera de cumplimiento** | Los datos de menores de edad (Ley 1581 de 2012) viven aislados en `identidad`, con proceso y base propios. |
| **Perfil de recurso** | `inteligencia` es intensiva en CPU y modelos; `comercio` necesita transaccionalidad y disponibilidad. Juntas obligan a dimensionar todo por la más exigente. |

---

## Por qué casi todo es Python

Se midió antes de decidir. El resultado está en
[`PERFILADO_PIPELINE.md`](../Arquitectura/PERFILADO_PIPELINE.md) y contradice la intuición
de partida en algo importante: la latencia del pipeline **sí** era CPU de Python, un 96,3 %,
pero el 95,3 % del total lo producía **una sola línea** que reconstruía un grafo de
NetworkX completo en cada ítem. Construirlo cuesta 1.673 ms; consultarlo, 0,137 ms.

Cacheándolo, una lista de veinte ítems baja de 35,1 s a 1,7 s. Reescribir en Go lo que
queda daría, por la ley de Amdahl, entre 20,0 % y 21,7 %, y casi todo sería reimplementar
pymoo, que no tiene equivalente en Go y con el que se produjeron los resultados de
hipervolumen de la tesis.

Por eso **seis de siete componentes son Python**. El único con argumento real para Go es
`ingesta`, y aun ahí sus cuellos de hoy son estructurales y no de lenguaje: los vendedores
se recorren en serie, hay 1,5 s de espera deliberada por producto y no hay pool de
conexiones. Eso se arregla en Python primero, y Go se evalúa después con datos.

La estructura ya es políglota (`libs/go/`, el manifiesto declara el lenguaje de cada
servicio y una prueba lo verifica), así que mover un componente a Go es agregarlo, no
reestructurar.

---

## Estado

Andamiaje. Existen el manifiesto de las 67 tablas, las funciones de aptitud con sus
pruebas, el ejecutor de tareas y la integración continua con ejecución selectiva por ruta.
Los servicios están vacíos: se llenan portando desde los repositorios anteriores, en el
orden del [plan](../Arquitectura/PLAN_TUKIT_V2.md).

### Deuda conocida, anotada para que no se pierda

- **No hay dirección de entrega** en ninguna parte del modelo, en un negocio que entrega a
  domicilio. Falta también en `ESQUEMA_OBJETIVO.md`, así que no está en el manifiesto.
  Hay que modelarla y clasificarla como `personal_sensible`.
- El diccionario de datos cubre Identidad y Catálogo; faltan Inteligencia, Comercio y
  Operación. El manifiesto de esos tres se derivó de `ESQUEMA_OBJETIVO.md`.
- Las 53 referencias cruzadas entre bases están contadas pero solo 8 declaradas. Se van
  declarando a medida que cada tabla se implementa.
