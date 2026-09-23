// ============================================================
// MOCK DATA — TuKit MVP
// Datos de muestra que hoy solo alimentan la "Vista de diseño" del
// dashboard (perfiles de hijos y pedidos). Viven en `identidad` y
// `comercio`, que todavia no publican superficie de lectura; se
// reemplazaran por esas llamadas cuando esos servicios existan.
// ============================================================

export interface Hijo {
  id: string;
  nombre: string;
  inicial: string;
  colorInicial: string;
  grado: string;
  colegio: string;
}

export interface Pedido {
  id: string;
  fecha: string;
  estado: "Entregado" | "En camino" | "Pendiente" | "Cancelado";
  total: string;
}

export interface Usuario {
  nombre: string;
  apellido: string;
}

// ---- USUARIO ----
export const mockUsuario: Usuario = {
  nombre: "Camila",
  apellido: "R.",
};

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

// ---- PEDIDOS RECIENTES ----
export const mockPedidos: Pedido[] = [
  {
    id: "#ORD-4920",
    fecha: "Oct 24, 2023",
    estado: "Entregado",
    total: "$345.000 COP",
  },
  {
    id: "#ORD-4892",
    fecha: "Sep 12, 2023",
    estado: "Entregado",
    total: "$120.500 COP",
  },
];

