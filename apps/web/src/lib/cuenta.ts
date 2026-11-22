export function saludoDeCuenta(nombre: string): string {
  const limpio = nombre.trim();
  return limpio && !limpio.includes("@") ? `Hola, ${limpio}` : "Hola";
}
