// Superficie publica para los componentes: tipos y funciones puras.
//
// A proposito NO exporta el origen de datos. El origen simulado lee ficheros y
// el cliente HTTP guarda la URL del backend: los dos son de servidor, y
// mezclarlos aqui haria que un `import` desde un componente de cliente
// arrastrara `node:fs` al bundle del navegador. Eso vive en `./servidor.ts`.

export * from "./contrato";
export * from "./catalogo";
export * from "./comercio";
export * from "./operacion";
export * from "./dinero";
export * from "./linea";
export {
  ErrorTukit,
  destinoDe,
  type ArchivoLista,
  type OrigenDatos,
  type Rol,
  type AmbitoTipo,
  type RolAsignado,
  type Sesion,
  type Credenciales,
} from "./origen";
