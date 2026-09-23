"""Hace paquete a las pruebas de Identidad, y no es cosmetico.

Cada servicio tiene su propio banco de pruebas y sus ficheros se llaman por lo
que prueban, asi que dos servicios acaban teniendo un `test_cargador.py` cada
uno: los dos cargadores existen y los dos se prueban. Sin este fichero, pytest
importa cada modulo de prueba por su nombre suelto, los dos se llaman
`test_cargador` y la recoleccion se interrumpe con un choque de nombres antes
de ejecutar una sola prueba.

La alternativa era renombrar el fichero a algo que no chocara, y eso arregla
el sintoma dejando el problema: el siguiente servicio que estrene cargador
vuelve a romper la suite. Con el paquete, el modulo pasa a llamarse
`tests.test_cargador` dentro de `servicios/identidad`, que es unico por
construccion.
"""
