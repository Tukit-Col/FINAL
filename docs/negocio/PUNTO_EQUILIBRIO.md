# Punto de equilibrio de Tukit, recalculado desde las fuentes

Fecha: 2026-11-05. Commit de `datos/`: `7aba82c`. Todas las cifras de este documento salen de
`python3 docs/negocio/punto_equilibrio.py`, que no usa red ni base de datos. Los datos medidos están
copiados en el script junto con la consulta que los produjo.

## 1. El ticket, medido

Se usaron los 13 kits canónicos del Colegio Agustiniano Ciudad Salitre (Jardín a Once, año 2026)
publicados el 2026-11-02 en `tukit_inteligencia.kit_canonico`. Son trabajos con origen
`canonico_lista` y sin usuario, así que no tocan los pedidos ni la prueba de carga del 2026-11-05
(110 usuarios `qa-carga-*` y 110 trabajos de ese día). `ensayos/kits_offline.py` da los mismos
totales sobre `datos/` (Ahorrador $10.604.060, Premium $19.812.327).

| Perfil | Base | Kits | Promedio | Mediana | Mínimo | Máximo |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Ahorrador | solo útiles | 13 | $609.343 | $622.350 | $406.780 | $801.290 |
| Ahorrador | útiles + plan lector | 13 | $815.697 | $755.930 | $527.337 | $1.149.881 |
| Premium | solo útiles | 13 | $1.171.629 | $1.290.724 | $742.255 | $1.535.495 |
| Premium | útiles + plan lector | 13 | $1.524.025 | $1.362.438 | $925.949 | $2.136.881 |
| A tu Medida | útiles + plan lector (pedidos OE5) | 6 | $1.225.525 | $1.238.640 | $937.129 | $1.539.404 |
| Fan | útiles + plan lector (pedidos OE5) | 5 | $984.978 | $1.070.580 | $698.180 | $1.233.817 |

- Ahorrador solo útiles, ponderado por estudiantes por grado (estudio 06): $594.826.
- El «plan lector» son los libros con ISBN (concepto `libro_libre`) que entraron al catálogo después
  de la auditoría v4. El $8.057.305 / 13 = $620.000 del flujo de caja es la auditoría v4 (commit
  `4dc3bc8`, 2026-10-12), que no tenía libros. La cifra de hoy en solo útiles ($7.921.461) es casi la misma.
- A tu Medida y Fan solo se arman cuando un acudiente los pide (ADR 0030), así que no tienen kit
  canónico. Las muestras vienen de las sesiones OE5 y no cubren los 13 grados, por eso no se usaron
  como ticket.

## 2. Supuestos y su fuente

| Rubro | Valor | Estado | Fuente |
| --- | ---: | --- | --- |
| Ticket (Ahorrador, solo útiles) | $609.343 | medido | kits canónicos, ver §1 |
| Comisión | 15 % | supuesto del equipo | Dossier OE1; no hay acuerdo con proveedores |
| Wompi | 2,65 % + $700 + IVA 19 % | tarifa publicada | wompi.com/es/co/planes-tarifas, Plan Avanzado, consultado 2026-11-05; la misma para tarjeta, PSE y Nequi |
| IA por kit | $1.000 | supuesto del equipo (cota alta) | Dossier OE1; no hay medición del costo por lista. Lo medido es NL2C: US$0,000078 por pedido (`docs/informes/nl2c/tablas_ronda3.md`) |
| Logística a domicilio | $20.000 / $33.000 / $54.000 | supuesto del equipo sobre tarifas publicadas de terceros | `docs/validacion/oe5/07_logistica_e_infra_piloto.md` |
| Logística consolidada en el colegio | $8.000 / $13.000 / $22.000 | supuesto del equipo sobre tarifas publicadas | mismo estudio |
| CAC | $8.000 | supuesto del equipo | Dossier OE1 («decisión interna, sin respaldo») |
| Infraestructura del piloto | $100.000/mes | supuesto del equipo sobre tarifas publicadas | estudio 07 §D suma ~$63.000; se dejó margen |
| Infraestructura escalable | $1.250.000/mes | supuesto del equipo | Dossier: $15.000.000/año (cloud + herramientas) |
| Familias del colegio | 1.340 | medido + supuesto | MEN 2025 (1.705 alumnos) y 1,25 hijos por familia de la encuesta (estudio 06) |
| Conversión | 5 % / 8 % / 15 % | supuesto del equipo | no hay compra medida; el 58,3 % es intención |

## 3. Resultado

| Escenario | Ticket | Comisión 15 % | Wompi + IVA | IA | Logística | CAC | Contribución por kit | Equilibrio, infra piloto ($1,2 M/año) | Equilibrio, infra escalable ($15 M/año) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bajo (domicilio caro) | $609.343 | $91.401 | $20.049 | $1.000 | $54.000 | $8.000 | **$8.353** | 144 | 1.796 |
| Base (domicilio) | $609.343 | $91.401 | $20.049 | $1.000 | $33.000 | $8.000 | **$29.353** | 41 | 512 |
| Alto (entrega en el colegio) | $609.343 | $91.401 | $20.049 | $1.000 | $13.000 | $8.000 | **$49.353** | 25 | 304 |

Sensibilidad sobre el escenario base (se cambia una sola cosa):

| Cambio | Contribución por kit | Equilibrio piloto | Equilibrio escalable |
| --- | ---: | ---: | ---: |
| Ticket con plan lector | $53.799 | 23 | 279 |
| Ticket mediano (solo útiles) | $30.894 | 39 | 486 |
| Ticket ponderado por estudiantes | $27.633 | 44 | 543 |
| Ticket del flujo de caja ($620.000) | $30.615 | 40 | 490 |
| Comisión 10 % | -$1.114 | no se alcanza | no se alcanza |
| Comisión 20 % | $59.820 | 21 | 251 |
| Wompi 2,99 % (cifra de tercero) | $26.887 | 45 | 558 |
| Sin CAC | $37.353 | 33 | 402 |

Proyección del piloto, escenario base, con $1.300.000 de arranque (SAS y sesiones, del flujo de caja):

| Conversión (supuesto) | Kits | Contribución total | Infra del año | Arranque | Resultado |
| --- | ---: | ---: | ---: | ---: | ---: |
| floja (5%) | 67 | $1.966.640 | $1.200.000 | $1.300.000 | -$533.360 |
| base (8%) | 107 | $3.140.754 | $1.200.000 | $1.300.000 | $640.754 |
| buena (15%) | 201 | $5.899.920 | $1.200.000 | $1.300.000 | $3.399.920 |

Para cubrir la infraestructura del año más el arranque hacen falta 86 kits (6,4 % de las familias).

**VPN.** No se recalculó. La rampa de 1.500, 8.000 y 25.000 kits, la inversión de $70.000.000 y los
costos fijos de $40 M y $120 M de los años 2 y 3 son supuestos del equipo sin fuente. Además, el VPN
del Dossier usa una contribución sin logística ni CAC. Con un ticket de $180.000 y esos dos costos, la
contribución queda en -$21.509 por kit. El $235 M no se puede sostener con lo que hay en el repo.

## 4. Conciliación

| Cifra | De dónde sale | Por qué difiere |
| --- | --- | --- |
| **770** | Dossier OE1: $15.000.000 / ($27.000 - Wompi $6.509 - IA $1.000 = $19.491) = 770 | Usa un ticket supuesto de $180.000, deja fuera la logística y el CAC, y toma la infra escalable como costo fijo del año 1. |
| **490** | `Nestle/scripts/flujo_caja.py`: $15.000.000 / $30.615 | Usa el ticket medido de la v4 ($620.000), con logística a domicilio y CAC, sobre la misma infra escalable del Dossier. |
| **40** | Mismo flujo de caja: $1.200.000 / $30.615 | El mismo kit que en 490, pero sobre la infra real del piloto ($100.000/mes). |
| **47** | Lo dijo la autora en la sesión del 2026-11-03 (grabación de las 9:07, min 13:46: «solo con 47 kits ya somos rentables») | Ninguna fórmula ni archivo del repo produce 47. Lo más probable es que fuera el 40 del flujo de caja recordado de memoria. |
| **43** | No tiene fuente | Hay dos coincidencias numéricas sin respaldo: el flujo de caja con Wompi al 2,99 % ($1.200.000 / $28.107 = 43) y los kits de diciembre del flujo de caja (1.340 × 8 % × 40 % = 43). Ninguna está escrita como punto de equilibrio. |
| **41 / 512** | Este script, escenario base | El ticket es el de hoy ($609.343, sin libros), $10.657 menos que en la v4; todo lo demás es igual al flujo de caja. |

## 5. Recomendación para la tesis

Recomiendo el escenario **base**: Ahorrador solo útiles, entrega a domicilio, contribución de $29.353,
**41 kits** con la infra del piloto y **512** con la escalable. Hay tres razones. El ticket es medido y
reproducible. Excluir los libros es la opción prudente, porque el margen de una editorial sobre un
texto con ISBN no está negociado. Y la logística a domicilio es la promesa del producto («se lo
llevamos a la casa»). La entrega en el colegio (25 kits) puede citarse como una palanca. La cifra de
770 debería salir de la memoria, porque omite la logística, que es el costo variable más grande.

Párrafo para «Justificación económica» (memoria, `descripcionGeneral.tex`):

> Para estimar la viabilidad económica se midió el valor de los kits canónicos que el sistema publicó
> para los trece grados del Colegio Agustiniano Ciudad Salitre, y el kit Ahorrador costó en promedio
> $609.343 en útiles escolares, sin contar los libros del plan lector. Sobre ese valor se supuso una
> comisión del 15 %, equivalente a $91.401 por kit; al descontar la pasarela de pagos Wompi con IVA
> ($20.049, según su tarifa publicada), la inteligencia artificial ($1.000), la entrega a domicilio en
> Bogotá ($33.000) y la adquisición de clientes ($8.000), cada kit dejó una contribución de $29.353.
> Con la infraestructura del piloto, de $1.200.000 al año, el punto de equilibrio fue de 41 kits,
> cerca del 3 % de las 1.340 familias estimadas del colegio, y con la infraestructura escalable, de
> $15.000.000 al año, fue de 512 kits. La comisión, la logística, la adquisición y la conversión de
> las familias fueron supuestos del equipo que la operación real debía confirmar, y con una comisión
> del 10 % la contribución por kit resultó negativa.
