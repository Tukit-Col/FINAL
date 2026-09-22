// Superficie publica para los componentes: tipos y funciones puras.
//
// A proposito NO exporta el origen de datos. El origen simulado lee ficheros y
// el cliente HTTP guarda la URL del backend: los dos son de servidor, y
// mezclarlos aqui haria que un `import` desde un componente de cliente
// arrastrara `node:fs` al bundle del navegador. Eso vive en `./servidor.ts`.

export * from "./contrato";
export * from "./catalogo";
export * from "./dinero";
export * from "./linea";
export { ErrorTukit, type ArchivoLista, type OrigenDatos } from "./origen";
