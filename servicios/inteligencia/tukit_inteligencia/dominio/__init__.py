"""El nucleo puro de Inteligencia: decisiones sin motor ni red (ADR 0019).

`pipeline` reune los helpers que traducen y ordenan datos del pipeline de
resolucion (estado desde emparejamiento, normalizacion de renglones, anclaje de
personaje) sin tocar la base ni los clientes remotos. La maquina de estados vive
en `modelos` (fuente unica); aqui no se duplica.
"""

from __future__ import annotations
