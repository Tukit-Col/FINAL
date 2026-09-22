// ============================================================
// MOCK DATA — TuKit MVP
// En etapas posteriores este archivo será reemplazado por
// llamadas reales al API Gateway / GenUI streaming.
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

export interface KitGuardado {
  id: string;
  nombre: string;
  articulos: number;
  precio: string;
  imagen: string;
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

// ---- KITS GUARDADOS ----
export const mockKitsGuardados: KitGuardado[] = [
  {
    id: "1",
    nombre: "Kit Básico Primaria",
    articulos: 24,
    precio: "$85.000",
    imagen: "/kit-basico.jpg",
  },
  {
    id: "2",
    nombre: "Pack de Artes",
    articulos: 12,
    precio: "$45.000",
    imagen: "/pack-artes.jpg",
  },
];

// ---- OPCIONES BUSCADOR ----
export const localidades = [
  "Usaquén",
  "Chapinero",
  "Santa Fe",
  "San Cristóbal",
  "Usme",
  "Tunjuelito",
  "Bosa",
  "Kennedy",
  "Fontibón",
  "Engativá",
  "Suba",
  "Barrios Unidos",
  "Teusaquillo",
  "Mártires",
  "Antonio Nariño",
  "Puente Aranda",
  "Candelaria",
  "Rafael Uribe Uribe",
  "Ciudad Bolívar",
];

export const grados = [
  "Jardín",
  "Transición",
  "Primero",
  "Segundo",
  "Tercero",
  "Cuarto",
  "Quinto",
  "Sexto",
  "Séptimo",
  "Octavo",
  "Noveno",
  "Décimo",
  "Undécimo",
];
