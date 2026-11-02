// La spec de interfaz que devuelve el asistente y su validador.
//
// El servidor compila la spec a partir de datos ya validados, pero el navegador
// no confia en eso: antes de pintar, cada componente se revisa contra esta lista
// blanca. Lo que no encaja se descarta entero. Nunca se pinta HTML recibido: los
// textos entran a React como texto y las imagenes solo si son https.

export type ClavePeso = "precio" | "marca_exigida" | "calidad" | "personaje";
export const CLAVES_PESO: readonly ClavePeso[] = ["precio", "marca_exigida", "calidad", "personaje"];

export const ETIQUETA_PESO: Record<ClavePeso, string> = {
  precio: "Que cueste poco",
  marca_exigida: "Que sea de marca conocida",
  calidad: "Que dure y sea bueno",
  personaje: "Que tenga su personaje",
};

export interface TarjetaProducto {
  sku: string;
  nombre: string;
  marca: string | null;
  nivel: string | null;
  imagen_url: string | null;
  precio_unitario: number | null;
}

export type Componente =
  | { tipo: "TarjetaPersonaje"; props: { nombre: string; imagen_url: string | null } }
  | {
      tipo: "SelectorPresupuesto";
      props: { minimo: number; maximo: number; paso: number; valor: number | null };
    }
  | { tipo: "Prioridades"; props: { orden: ClavePeso[] } }
  | { tipo: "ResumenRestricciones"; props: Record<string, never> }
  | {
      tipo: "PropuestaCambio";
      props: {
        trabajo_id: string;
        perfil: string;
        item_id: string;
        descripcion: string;
        antes: TarjetaProducto;
        despues: TarjetaProducto;
        unidades: number;
        delta_cop: number;
        aplicable: boolean;
      };
    }
  | {
      tipo: "PropuestaDescarte";
      props: {
        trabajo_id: string;
        perfil: string;
        item_id: string;
        descripcion: string;
        motivo_texto: string;
        producto: TarjetaProducto;
        ahorro_cop: number;
        aplicable: boolean;
      };
    }
  | {
      // El resumen de un pedido por categoria: el texto lo redacta el servidor.
      tipo: "ResumenLote";
      props: {
        accion: "mas_barato" | "mejor_calidad" | "variar";
        categoria: string;
        propuestas: number;
        delta_total_cop: number;
        texto: string;
      };
    }
  | {
      tipo: "ExplicacionKit";
      props: {
        perfil: string;
        renglones: number;
        por_nivel: Record<string, number>;
        total_cop: number | null;
      };
    };

export interface EspecUi {
  version: 1;
  componentes: Componente[];
}

export const TIPOS_PERMITIDOS = [
  "TarjetaPersonaje",
  "SelectorPresupuesto",
  "Prioridades",
  "ResumenRestricciones",
  "PropuestaCambio",
  "PropuestaDescarte",
  "ResumenLote",
  "ExplicacionKit",
] as const;

// Un resumen de lote más hasta 12 propuestas (MAX_PROPUESTAS_LOTE del servidor).
const MAX_COMPONENTES = 13;
const MAX_TEXTO = 160;

type Obj = Record<string, unknown>;
const esObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const texto = (v: unknown): string | null =>
  typeof v === "string" && v.length > 0 && v.length <= MAX_TEXTO ? v : null;
const entero = (v: unknown): number | null =>
  typeof v === "number" && Number.isSafeInteger(v) ? v : null;
const imagen = (v: unknown): string | null => {
  if (typeof v !== "string" || v.length > 500) return null;
  try {
    return new URL(v).protocol === "https:" ? v : null;
  } catch {
    return null;
  }
};

function tarjeta(v: unknown): TarjetaProducto | null {
  if (!esObj(v)) return null;
  const sku = texto(v["sku"]);
  const nombre = texto(v["nombre"]);
  if (!sku || !nombre) return null;
  const precio = v["precio_unitario"];
  return {
    sku,
    nombre,
    marca: texto(v["marca"]),
    nivel: texto(v["nivel"]),
    imagen_url: imagen(v["imagen_url"]),
    precio_unitario: typeof precio === "number" && Number.isSafeInteger(precio) ? precio : null,
  };
}

function componente(v: unknown): Componente | null {
  if (!esObj(v) || !esObj(v["props"])) return null;
  const p = v["props"];
  switch (v["tipo"]) {
    case "TarjetaPersonaje": {
      const nombre = texto(p["nombre"]);
      return nombre ? { tipo: "TarjetaPersonaje", props: { nombre, imagen_url: imagen(p["imagen_url"]) } } : null;
    }
    case "SelectorPresupuesto": {
      const minimo = entero(p["minimo"]);
      const maximo = entero(p["maximo"]);
      const paso = entero(p["paso"]);
      const valor = p["valor"] === null || p["valor"] === undefined ? null : entero(p["valor"]);
      if (minimo === null || maximo === null || paso === null || paso <= 0 || minimo >= maximo) return null;
      if (p["valor"] != null && valor === null) return null;
      return { tipo: "SelectorPresupuesto", props: { minimo, maximo, paso, valor } };
    }
    case "Prioridades": {
      const orden = p["orden"];
      if (!Array.isArray(orden) || orden.length !== CLAVES_PESO.length) return null;
      const claves = orden.filter((c): c is ClavePeso => CLAVES_PESO.includes(c as ClavePeso));
      return new Set(claves).size === CLAVES_PESO.length ? { tipo: "Prioridades", props: { orden: claves } } : null;
    }
    case "ResumenRestricciones":
      return { tipo: "ResumenRestricciones", props: {} };
    case "PropuestaCambio": {
      const antes = tarjeta(p["antes"]);
      const despues = tarjeta(p["despues"]);
      const trabajo_id = texto(p["trabajo_id"]);
      const perfil = texto(p["perfil"]);
      const item_id = texto(p["item_id"]);
      const descripcion = texto(p["descripcion"]);
      const unidades = entero(p["unidades"]);
      const delta_cop = entero(p["delta_cop"]);
      if (!antes || !despues || !trabajo_id || !perfil || !item_id || !descripcion) return null;
      if (unidades === null || delta_cop === null || typeof p["aplicable"] !== "boolean") return null;
      return {
        tipo: "PropuestaCambio",
        props: { trabajo_id, perfil, item_id, descripcion, antes, despues, unidades, delta_cop, aplicable: p["aplicable"] },
      };
    }
    case "PropuestaDescarte": {
      const producto = tarjeta(p["producto"]);
      const trabajo_id = texto(p["trabajo_id"]);
      const perfil = texto(p["perfil"]);
      const item_id = texto(p["item_id"]);
      const descripcion = texto(p["descripcion"]);
      const motivo_texto = texto(p["motivo_texto"]);
      const ahorro_cop = entero(p["ahorro_cop"]);
      if (!producto || !trabajo_id || !perfil || !item_id || !descripcion || !motivo_texto) return null;
      if (ahorro_cop === null || typeof p["aplicable"] !== "boolean") return null;
      return {
        tipo: "PropuestaDescarte",
        props: { trabajo_id, perfil, item_id, descripcion, motivo_texto, producto, ahorro_cop, aplicable: p["aplicable"] },
      };
    }
    case "ResumenLote": {
      const accion = p["accion"];
      const categoria = texto(p["categoria"]);
      const propuestas = entero(p["propuestas"]);
      const delta = entero(p["delta_total_cop"]);
      const t = texto(p["texto"]);
      if (accion !== "mas_barato" && accion !== "mejor_calidad" && accion !== "variar") return null;
      if (!categoria || propuestas === null || propuestas < 0 || delta === null || !t) return null;
      return { tipo: "ResumenLote", props: { accion, categoria, propuestas, delta_total_cop: delta, texto: t } };
    }
    case "ExplicacionKit": {
      const perfil = texto(p["perfil"]);
      const renglones = entero(p["renglones"]);
      const total = p["total_cop"] === null ? null : entero(p["total_cop"]);
      if (!perfil || renglones === null || !esObj(p["por_nivel"])) return null;
      const por_nivel: Record<string, number> = {};
      for (const [k, n] of Object.entries(p["por_nivel"])) {
        const cuenta = entero(n);
        if (cuenta === null || k.length > 30) return null;
        por_nivel[k] = cuenta;
      }
      return { tipo: "ExplicacionKit", props: { perfil, renglones, por_nivel, total_cop: total } };
    }
    default:
      return null;
  }
}

/** La spec si todos sus componentes son de la lista blanca y estan bien formados; si no, `null`. */
export function validarEspec(v: unknown): EspecUi | null {
  if (!esObj(v) || v["version"] !== 1 || !Array.isArray(v["componentes"])) return null;
  if (v["componentes"].length > MAX_COMPONENTES) return null;
  const salida: Componente[] = [];
  for (const crudo of v["componentes"]) {
    const c = componente(crudo);
    if (c === null) return null;
    salida.push(c);
  }
  return { version: 1, componentes: salida };
}

/** Reparte los pesos originales (de mayor a menor) segun el nuevo orden de prioridad. */
export function pesosDesdeOrden(
  originales: Record<ClavePeso, number>,
  orden: readonly ClavePeso[],
): Record<ClavePeso, number> {
  const valores = [...CLAVES_PESO].map((k) => originales[k]).sort((a, b) => b - a);
  const salida = { ...originales };
  orden.forEach((clave, i) => {
    salida[clave] = valores[i] ?? 0;
  });
  return salida;
}

/** Los pesos de R que importan primero: el mayor da la prioridad que entiende el formulario. */
export function prioridadDeOrden(orden: readonly ClavePeso[]): "precio" | "equilibrio" | "calidad" {
  const primera = orden[0];
  if (primera === "precio") return "precio";
  if (primera === "calidad" || primera === "marca_exigida") return "calidad";
  return "equilibrio";
}

export function formatearCop(valor: number): string {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(valor);
}

export function textoDelta(delta: number): string {
  if (delta === 0) return "Cuesta lo mismo";
  return delta < 0 ? `Ahorras ${formatearCop(-delta)}` : `Cuesta ${formatearCop(delta)} más`;
}

/** El pedido que el navegador recuerda para el turno siguiente ("y en colores también"). */
export interface PedidoAnterior {
  accion: "mas_barato" | "mejor_calidad" | "variar";
  categoria: string;
}

/** Lo que el servidor devolvió como contexto, solo si es una acción de la lista y una palabra corta. */
export function pedidoAnteriorSeguro(v: unknown): PedidoAnterior | null {
  if (!esObj(v)) return null;
  const { accion, categoria } = v;
  if (accion !== "mas_barato" && accion !== "mejor_calidad" && accion !== "variar") return null;
  if (typeof categoria !== "string" || !/^[a-zñáéíóúü]{3,24}$/.test(categoria)) return null;
  return { accion, categoria };
}

/** Los ejemplos tocables de la respuesta de ayuda: pocos, cortos y solo texto. */
export function ejemplosSeguros(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((e): e is string => typeof e === "string" && e.length > 0 && e.length <= 60).slice(0, 6);
}
