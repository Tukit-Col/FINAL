// ============================================================
// MOCK DATA — TuKit MVP
// Lo unico que queda de muestra es "Mis hijos" del dashboard: los perfiles de
// menores viven en `identidad`, que mantiene esa superficie CERRADA a
// proposito (Anexo M, Ley 1581) y no la abre solo para pintar una tarjeta. El
// saludo y los pedidos del panel ya salen del backend real (sesion de
// identidad + `/v1/comercio/mis-pedidos`), asi que su mock se eliminó.
// ============================================================

export interface Hijo {
  id: string;
  nombre: string;
  inicial: string;
  colorInicial: string;
  grado: string;
  colegio: string;
}

// ---- HIJOS ----
export const mockHijos: Hijo[] = [
  {
    id: "1",
    nombre: "Mateo",
    inicial: "M",
    colorInicial: "#7c3aed",
    grado: "Grado 3",
    colegio: "Colegio Reyes Católicos",
  },
  {
    id: "2",
    nombre: "Sofía",
    inicial: "S",
    colorInicial: "#7c3aed",
    grado: "Grado 5",
    colegio: "Gimnasio Moderno",
  },
];
