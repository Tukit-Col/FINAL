import type { AcudienteAdmin } from "@tukit/contrato";

export const POR_PAGINA = 25;
export const DOMINIO_PRUEBA = "@example.test";

export type OrdenClientes = "nuevo" | "antiguo";
export type CantidadHijos = "" | "0" | "1" | "2" | "3+";

export interface FiltrosClientes {
  q: string;
  colegio: string;
  grado: string;
  hijos: CantidadHijos;
  orden: OrdenClientes;
  sinPrueba: boolean;
  pagina: number;
}

type Parametros = Record<string, string | string[] | undefined>;

function primero(valor: string | string[] | undefined): string {
  return (Array.isArray(valor) ? valor[0] : valor)?.trim() ?? "";
}

export function leerFiltrosClientes(parametros: Parametros): FiltrosClientes {
  const hijos = primero(parametros.hijos);
  const pagina = Number.parseInt(primero(parametros.pagina), 10);
  return {
    q: primero(parametros.q),
    colegio: primero(parametros.colegio),
    grado: primero(parametros.grado),
    hijos: hijos === "0" || hijos === "1" || hijos === "2" || hijos === "3+" ? hijos : "",
    orden: primero(parametros.orden) === "antiguo" ? "antiguo" : "nuevo",
    sinPrueba: primero(parametros.sinprueba) === "1",
    pagina: Number.isFinite(pagina) && pagina > 0 ? pagina : 1,
  };
}

export function hayFiltrosClientes(f: FiltrosClientes): boolean {
  return Boolean(f.q || f.colegio || f.grado || f.hijos || f.sinPrueba);
}

export function esCuentaDePrueba(a: Pick<AcudienteAdmin, "correo">): boolean {
  return a.correo.toLowerCase().endsWith(DOMINIO_PRUEBA);
}

function instante(iso: string): number {
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function coincideHijos(n: number, cantidad: CantidadHijos): boolean {
  if (cantidad === "") return true;
  return cantidad === "3+" ? n >= 3 : n === Number(cantidad);
}

export function filtrarClientes(
  acudientes: readonly AcudienteAdmin[],
  f: FiltrosClientes,
): AcudienteAdmin[] {
  const q = f.q.toLowerCase();
  const salida = acudientes.filter((a) => {
    if (q && !a.correo.toLowerCase().includes(q)) return false;
    if (f.sinPrueba && esCuentaDePrueba(a)) return false;
    if (!coincideHijos(a.hijos.length, f.hijos)) return false;
    if (f.colegio && !a.hijos.some((h) => h.colegio_id === f.colegio)) return false;
    if (f.grado && !a.hijos.some((h) => h.grado === f.grado)) return false;
    return true;
  });
  const signo = f.orden === "antiguo" ? 1 : -1;
  return salida.sort((a, b) => signo * (instante(a.creado_en) - instante(b.creado_en)));
}

export function opcionesClientes(acudientes: readonly AcudienteAdmin[]): {
  colegios: { id: string; nombre: string }[];
  grados: string[];
} {
  const colegios = new Map<string, string>();
  const grados = new Set<string>();
  for (const a of acudientes) {
    for (const h of a.hijos) {
      colegios.set(h.colegio_id, h.colegio_nombre);
      grados.add(h.grado);
    }
  }
  return {
    colegios: [...colegios].map(([id, nombre]) => ({ id, nombre })).sort((x, y) => x.nombre.localeCompare(y.nombre, "es")),
    grados: [...grados].sort((x, y) => x.localeCompare(y, "es", { numeric: true })),
  };
}

export interface PaginaClientes<T> {
  items: T[];
  pagina: number;
  paginas: number;
  total: number;
  desde: number;
  hasta: number;
}

export function paginar<T>(items: readonly T[], pagina: number, tamano = POR_PAGINA): PaginaClientes<T> {
  const total = items.length;
  const paginas = Math.max(1, Math.ceil(total / tamano));
  const actual = Math.min(Math.max(1, pagina), paginas);
  const inicio = (actual - 1) * tamano;
  const parte = items.slice(inicio, inicio + tamano);
  return {
    items: parte,
    pagina: actual,
    paginas,
    total,
    desde: total === 0 ? 0 : inicio + 1,
    hasta: inicio + parte.length,
  };
}

export function hrefClientes(f: FiltrosClientes, cambios: Partial<FiltrosClientes> = {}): string {
  const x = { ...f, ...cambios };
  const p = new URLSearchParams();
  if (x.q) p.set("q", x.q);
  if (x.colegio) p.set("colegio", x.colegio);
  if (x.grado) p.set("grado", x.grado);
  if (x.hijos) p.set("hijos", x.hijos);
  if (x.orden !== "nuevo") p.set("orden", x.orden);
  if (x.sinPrueba) p.set("sinprueba", "1");
  if (x.pagina > 1) p.set("pagina", String(x.pagina));
  const cola = p.toString();
  return cola ? `/clientes?${cola}` : "/clientes";
}

export interface ClientesDeColegio {
  colegio_id: string;
  colegio_nombre: string;
  acudientes: number;
  hijos: number;
  grados: { grado: string; acudientes: number; hijos: number }[];
}

export function clientesPorColegio(acudientes: readonly AcudienteAdmin[]): ClientesDeColegio[] {
  type Acum = { nombre: string; padres: Set<string>; hijos: number; grados: Map<string, { padres: Set<string>; hijos: number }> };
  const colegios = new Map<string, Acum>();
  for (const a of acudientes) {
    for (const h of a.hijos) {
      let c = colegios.get(h.colegio_id);
      if (!c) {
        c = { nombre: h.colegio_nombre, padres: new Set(), hijos: 0, grados: new Map() };
        colegios.set(h.colegio_id, c);
      }
      c.padres.add(a.usuario_id);
      c.hijos += 1;
      let g = c.grados.get(h.grado);
      if (!g) {
        g = { padres: new Set(), hijos: 0 };
        c.grados.set(h.grado, g);
      }
      g.padres.add(a.usuario_id);
      g.hijos += 1;
    }
  }
  return [...colegios.entries()]
    .map(([colegio_id, c]) => ({
      colegio_id,
      colegio_nombre: c.nombre,
      acudientes: c.padres.size,
      hijos: c.hijos,
      grados: [...c.grados.entries()]
        .map(([grado, g]) => ({ grado, acudientes: g.padres.size, hijos: g.hijos }))
        .sort((x, y) => y.hijos - x.hijos || x.grado.localeCompare(y.grado, "es")),
    }))
    .sort((x, y) => y.acudientes - x.acudientes || x.colegio_nombre.localeCompare(y.colegio_nombre, "es"));
}

export type TonoPedido = "exito" | "curso" | "aviso" | "neutro";

export interface PedidoDeFamilia {
  estado: string;
  tono: TonoPedido;
  pedidos: number;
}

const TONO: Record<string, TonoPedido> = {
  entregado: "exito",
  pagado: "curso",
  en_preparacion: "curso",
  despachado: "curso",
  en_reparto: "curso",
  pendiente_pago: "aviso",
  incidencia: "aviso",
  cancelado: "neutro",
};

export function pedidosPorFamilia(
  pedidos: readonly { usuario_id: string; estado: string; creado_en: string }[],
): Map<string, PedidoDeFamilia> {
  const porUsuario = new Map<string, { estado: string; creado_en: string }[]>();
  for (const p of pedidos) {
    const lista = porUsuario.get(p.usuario_id) ?? [];
    lista.push(p);
    porUsuario.set(p.usuario_id, lista);
  }
  const salida = new Map<string, PedidoDeFamilia>();
  for (const [usuario, lista] of porUsuario) {
    const ordenados = [...lista].sort((a, b) => b.creado_en.localeCompare(a.creado_en));
    const vivo = ordenados.find((p) => p.estado !== "cancelado") ?? ordenados[0]!;
    salida.set(usuario, { estado: vivo.estado, tono: TONO[vivo.estado] ?? "neutro", pedidos: lista.length });
  }
  return salida;
}
