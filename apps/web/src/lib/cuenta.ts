// El saludo del panel. Identidad llena `nombre` con el correo cuando la cuenta
// no tiene uno (el alta de /empezar no lo pide), y "Hola, alguien@correo.com"
// no es un saludo: con un nombre de verdad se usa; si no, "Hola" a secas.
export function saludoDeCuenta(nombre: string): string {
  const limpio = nombre.trim();
  return limpio && !limpio.includes("@") ? `Hola, ${limpio}` : "Hola";
}
