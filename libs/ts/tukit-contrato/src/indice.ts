// Superficie publica para los componentes: tipos y funciones puras.
//
// A proposito NO exporta el origen de datos. El cliente HTTP guarda la URL del
// backend y solo corre en el servidor; exportarlo aqui arriesgaria arrastrarlo
// al bundle del navegador desde un componente de cliente. Eso vive en
// `./servidor.ts`.

export * from "./contrato";
export * from "./catalogo";
export * from "./comercio";
export * from "./operacion";
export * from "./admin";
export * from "./metricas";
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
  type NuevaCuenta,
  type MatriculaAcudiente,
  type RegistroAcudiente,
  type HijoNuevo,
  type AcudienteAdmin,
  type HijoAcudiente,
} from "./origen";
