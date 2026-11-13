"""Nombres de pila frecuentes en Colombia, para redactar el nombre de un menor
aunque el padre no use frase gatillo ("Sofia quiere Bluey") ni mayuscula
("mi hijo juan esteban").

En minuscula y sin tildes. Quedan fuera a proposito los que tambien son palabras
del dominio o del idioma (rosa, luz, sol, paz, mar, cruz, angel, victoria,
esperanza, blanca, pilar, leon, reyes...) y los que son personajes (elsa): borrar
"cuaderno rosa" o "quiere Elsa" le quita al modelo justo lo que necesita.
"""

from __future__ import annotations

_LISTA = """
    aaron abigail adriana agustin aitana alan alejandra alejandro alexander alexandra alicia alison
    allison amelia ana andrea andres angela angelica antonella antonia antonio ariadna ariana ashley
    axel benjamin bianca brayan camila camilo carla carlos carmen carolina catalina cesar clara cristian
    cristina cristobal dana daniel daniela david diana diego dilan dylan eduardo elena eliana elias
    emilia emiliano emily emma enrique esteban estefania fabian felipe fernanda fernando francisco
    gabriel gabriela gael gerardo german gustavo hector helena hernan ignacio isaac isabel isabela
    isabella ivan jacobo javier jeronimo jesus jhon jimena joaquin johan jorge jose josefina juan juana
    juanita julian juliana julieta julio karen karol katherine kevin laura leonardo lina lorena lucas
    lucia luciana luis luisa manuel manuela marcela marco marcos maria mariana mariano martin martina
    mateo matias mauricio maximiliano melany melissa miguel miranda monica natalia nataly nicolas nicole
    oscar pablo paola paula paulina pedro rafael ricardo roberto rodrigo salome samantha samuel santiago
    sara sarah sebastian sergio silvana simon sofia sophia stefany susana tatiana tomas valentina
    valeria valery vanessa veronica violeta ximena yesenia yuliana zoe
"""
NOMBRES_COMUNES: frozenset[str] = frozenset(_LISTA.split())

__all__ = ["NOMBRES_COMUNES"]
