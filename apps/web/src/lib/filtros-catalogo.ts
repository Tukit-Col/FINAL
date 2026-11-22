export const TODOS = "__todos__";
export const SIN_PERSONAJE = "__sin_personaje__";

export interface Filtros {
  texto: string;
  categoria: string;
  nivel: string;
  personaje: string;
  tienda: string;
  soloHuecos: boolean;
}

export const SIN_FILTROS: Filtros = {
  texto: "",
  categoria: TODOS,
  nivel: TODOS,
  personaje: TODOS,
  tienda: TODOS,
  soloHuecos: false,
};

export interface ProductoFiltrable {
  nivel: string;
  personaje?: string | null;
  ofertas: readonly { tienda: string }[];
}

export function filtraProductos(filtros: Filtros): boolean {
  return filtros.nivel !== TODOS || filtros.personaje !== TODOS || filtros.tienda !== TODOS;
}

export function pasaProducto(producto: ProductoFiltrable, filtros: Filtros): boolean {
  if (filtros.nivel !== TODOS && producto.nivel !== filtros.nivel) return false;
  if (filtros.personaje === SIN_PERSONAJE && producto.personaje) return false;
  if (
    filtros.personaje !== TODOS &&
    filtros.personaje !== SIN_PERSONAJE &&
    producto.personaje !== filtros.personaje
  ) {
    return false;
  }
  if (filtros.tienda !== TODOS && !producto.ofertas.some((oferta) => oferta.tienda === filtros.tienda)) {
    return false;
  }
  return true;
}
