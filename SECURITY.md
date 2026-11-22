# Política de seguridad

## Reportar una vulnerabilidad

No abras un issue público. Usa **[Report a vulnerability](https://github.com/Tukit-Col/FINAL/security/advisories/new)**
(pestaña *Security*) o escribe a **tukit.ayuda@gmail.com** con:

- qué encontraste y dónde (archivo, endpoint o pantalla),
- cómo reproducirlo,
- el impacto que crees que tiene.

Respondemos en un máximo de 7 días y te avisamos cuando esté corregido.

## Alcance

Cubre el código de este repositorio: los seis servicios, las apps `web` y `admin`, y `libs/`.
Las cuentas demo (`demo1234`) y la llave de sesión de desarrollo son públicas a propósito y no
son una vulnerabilidad; en producción el sistema no arranca sin llaves propias
(ver *Producción: llaves obligatorias* en el README).
