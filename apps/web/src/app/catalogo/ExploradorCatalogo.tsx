"use client";

import { useMemo, useState } from "react";
import {
  coberturaDe,
  ETIQUETA_NIVEL,
  NIVELES,
  ORDEN_NIVEL,
  type Catalogo,
  type ConceptoCatalogo,
  type CoberturaConcepto,
  type ProductoCatalogo,
} from "@tukit/contrato";
import BloqueConcepto from "./BloqueConcepto";
import estilos from "./Catalogo.module.css";

// Centinelas de los selectores. Llevan guiones bajos para que no choquen con
// un nombre de categoria, de personaje o de tienda que venga del catalogo.
const TODOS = "__todos__";
const SIN_PERSONAJE = "__sin_personaje__";

interface Filtros {
  texto: string;
  categoria: string;
  nivel: string;
  personaje: string;
  tienda: string;
  soloHuecos: boolean;
}

const SIN_FILTROS: Filtros = {
  texto: "",
  categoria: TODOS,
  nivel: TODOS,
  personaje: TODOS,
  tienda: TODOS,
  soloHuecos: false,
};

// `NIVELES` es el conjunto y `ORDEN_NIVEL` es la escala. Se ordena por la
// escala para que un reordenamiento del arreglo del contrato no cambie en
// silencio la direccion en la que se lee la pantalla.
const NIVELES_EN_ORDEN = [...NIVELES].sort((a, b) => ORDEN_NIVEL[a] - ORDEN_NIVEL[b]);

// Buscar "lapiz" tiene que encontrar "lápiz": el corpus escribe los nombres
// con tilde y nadie las teclea en un buscador.
function normalizar(texto: string): string {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

interface ConceptoIndexado {
  concepto: ConceptoCatalogo;
  cobertura: CoberturaConcepto;
  // Todo el texto por el que se puede encontrar el concepto, ya normalizado.
  // Se arma una vez porque la alternativa es recorrer 99 conceptos y 242
  // productos en cada tecla pulsada.
  buscable: string;
}

interface ConceptoVisible extends ConceptoIndexado {
  productos: ProductoCatalogo[];
  ocultos: number;
}

interface Props {
  catalogo: Catalogo;
}

export default function ExploradorCatalogo({ catalogo }: Props) {
  const [filtros, setFiltros] = useState<Filtros>(SIN_FILTROS);

  const indexados = useMemo<ConceptoIndexado[]>(
    () =>
      catalogo.conceptos.map((concepto) => ({
        concepto,
        cobertura: coberturaDe(concepto),
        buscable: normalizar(
          [
            concepto.nombre_canonico,
            concepto.codigo,
            concepto.categoria,
            ...concepto.sinonimos,
            ...concepto.productos.flatMap((producto) => [
              producto.nombre,
              producto.marca ?? "",
              producto.personaje ?? "",
            ]),
          ].join(" "),
        ),
      })),
    [catalogo],
  );

  const opciones = useMemo(() => {
    const categorias = new Set<string>();
    const personajes = new Set<string>();
    for (const concepto of catalogo.conceptos) {
      categorias.add(concepto.categoria);
      for (const producto of concepto.productos) {
        if (producto.personaje) personajes.add(producto.personaje);
      }
    }
    const alfabetico = (a: string, b: string) => a.localeCompare(b, "es");
    return {
      categorias: [...categorias].sort(alfabetico),
      personajes: [...personajes].sort(alfabetico),
    };
  }, [catalogo]);

  const visibles = useMemo<ConceptoVisible[]>(() => {
    const consulta = normalizar(filtros.texto.trim());
    // Nivel, personaje y tienda filtran PRODUCTOS; categoria, texto y huecos
    // filtran CONCEPTOS. Saber si hay alguno del primer grupo puesto decide
    // que hacer con un concepto que se queda sin productos.
    const filtraProductos =
      filtros.nivel !== TODOS || filtros.personaje !== TODOS || filtros.tienda !== TODOS;

    const resultado: ConceptoVisible[] = [];
    for (const entrada of indexados) {
      const { concepto } = entrada;
      if (filtros.categoria !== TODOS && concepto.categoria !== filtros.categoria) continue;
      if (consulta && !entrada.buscable.includes(consulta)) continue;
      if (filtros.soloHuecos && entrada.cobertura === "tres_niveles") continue;

      const productos = filtraProductos
        ? concepto.productos.filter((producto) => pasaProducto(producto, filtros))
        : concepto.productos;

      // Con un filtro de producto puesto, un concepto sin coincidencias no
      // dice nada y solo empuja hacia abajo lo que si coincide. Sin filtros de
      // producto los conceptos vacios SI se listan: son la mitad de la
      // informacion de esta pantalla.
      if (filtraProductos && productos.length === 0) continue;

      resultado.push({
        ...entrada,
        productos,
        ocultos: concepto.productos.length - productos.length,
      });
    }
    return resultado;
  }, [indexados, filtros]);

  const conteo = useMemo(() => {
    let productos = 0;
    let vacios = 0;
    for (const visible of visibles) {
      productos += visible.productos.length;
      if (visible.concepto.productos.length === 0) vacios += 1;
    }
    return { productos, vacios };
  }, [visibles]);

  const hayFiltros =
    filtros.texto !== "" ||
    filtros.categoria !== TODOS ||
    filtros.nivel !== TODOS ||
    filtros.personaje !== TODOS ||
    filtros.tienda !== TODOS ||
    filtros.soloHuecos;

  function cambiar(parcial: Partial<Filtros>) {
    setFiltros((previos) => ({ ...previos, ...parcial }));
  }

  return (
    <>
      <div className={estilos.barra}>
        <div className={estilos.barraInterior} role="search">
          <input
            type="search"
            className={estilos.busqueda}
            placeholder="Buscar un útil, una marca, un personaje…"
            aria-label="Buscar por útil, sinónimo, marca o personaje"
            value={filtros.texto}
            onChange={(evento) => cambiar({ texto: evento.target.value })}
          />

          <select
            className={estilos.selector}
            aria-label="Filtrar por categoría"
            value={filtros.categoria}
            onChange={(evento) => cambiar({ categoria: evento.target.value })}
          >
            <option value={TODOS}>Todas las categorías</option>
            {opciones.categorias.map((categoria) => (
              <option key={categoria} value={categoria}>
                {categoria}
              </option>
            ))}
          </select>

          {/* Dos selectores y no uno: el nivel de calidad y el personaje son
              ejes ortogonales, asi que "premium" y "Spiderman" se pueden pedir
              juntos. Fundirlos en una sola lista haria del personaje un cuarto
              nivel, que es lo que la base prohibe con una restriccion. */}
          <select
            className={estilos.selector}
            aria-label="Filtrar por nivel de calidad"
            value={filtros.nivel}
            onChange={(evento) => cambiar({ nivel: evento.target.value })}
          >
            <option value={TODOS}>Cualquier nivel</option>
            {NIVELES_EN_ORDEN.map((nivel) => (
              <option key={nivel} value={nivel}>
                {ETIQUETA_NIVEL[nivel]}
              </option>
            ))}
          </select>

          <select
            className={estilos.selector}
            aria-label="Filtrar por personaje"
            value={filtros.personaje}
            onChange={(evento) => cambiar({ personaje: evento.target.value })}
          >
            <option value={TODOS}>Con o sin personaje</option>
            <option value={SIN_PERSONAJE}>Sin personaje</option>
            {opciones.personajes.map((personaje) => (
              <option key={personaje} value={personaje}>
                {personaje}
              </option>
            ))}
          </select>

          <select
            className={estilos.selector}
            aria-label="Filtrar por tienda"
            value={filtros.tienda}
            onChange={(evento) => cambiar({ tienda: evento.target.value })}
          >
            <option value={TODOS}>Todas las tiendas</option>
            {catalogo.tiendas.map((tienda) => (
              <option key={tienda.slug} value={tienda.slug}>
                {tienda.nombre}
              </option>
            ))}
          </select>

          <label
            className={`${estilos.interruptor} ${filtros.soloHuecos ? estilos.interruptorActivo : ""}`}
            title="Conceptos sin ningún producto o que no llegan a los tres niveles."
          >
            <input
              type="checkbox"
              checked={filtros.soloHuecos}
              aria-label="Mostrar solo los conceptos incompletos"
              onChange={(evento) => cambiar({ soloHuecos: evento.target.checked })}
            />
            Solo lo que no tenemos
          </label>

          <button
            type="button"
            className={estilos.limpiar}
            disabled={!hayFiltros}
            onClick={() => setFiltros(SIN_FILTROS)}
          >
            Limpiar
          </button>

          <p className={estilos.contador} role="status">
            <strong className="cifra">{visibles.length}</strong> de{" "}
            <span className="cifra">{catalogo.resumen.conceptos}</span> conceptos ·{" "}
            <strong className="cifra">{conteo.productos}</strong> de{" "}
            <span className="cifra">{catalogo.resumen.productos}</span> productos
            {conteo.vacios > 0 && (
              <span className={estilos.contadorHuecos}>
                {" "}
                · <span className="cifra">{conteo.vacios}</span>{" "}
                {conteo.vacios === 1 ? "concepto sin nada" : "conceptos sin nada"} que ofrecer
              </span>
            )}
          </p>
        </div>
      </div>

      <div className={estilos.lista}>
        {visibles.length === 0 ? (
          <div className={estilos.sinResultados}>
            <p className={estilos.sinResultadosTitulo}>Ningún concepto cumple estos filtros.</p>
            <p className={estilos.sinResultadosNota}>
              El catálogo tiene {catalogo.resumen.conceptos} conceptos y{" "}
              {catalogo.resumen.productos} productos; ninguno coincide con lo que pediste. Prueba
              con menos condiciones.
            </p>
            <button type="button" className={estilos.botonLimpiar} onClick={() => setFiltros(SIN_FILTROS)}>
              Quitar todos los filtros
            </button>
          </div>
        ) : (
          visibles.map((visible) => (
            <BloqueConcepto
              key={visible.concepto.codigo}
              concepto={visible.concepto}
              cobertura={visible.cobertura}
              productos={visible.productos}
              ocultos={visible.ocultos}
            />
          ))
        )}
      </div>
    </>
  );
}

function pasaProducto(producto: ProductoCatalogo, filtros: Filtros): boolean {
  if (filtros.nivel !== TODOS && producto.nivel !== filtros.nivel) return false;
  if (filtros.personaje === SIN_PERSONAJE && producto.personaje) return false;
  if (
    filtros.personaje !== TODOS &&
    filtros.personaje !== SIN_PERSONAJE &&
    producto.personaje !== filtros.personaje
  ) {
    return false;
  }
  // Un producto pasa el filtro de tienda si ALGUNA de sus ofertas es de esa
  // tienda. Las ofertas que no lo son se siguen mostrando en la tarjeta: la
  // pantalla existe para comparar precios entre tiendas, y esconder la
  // competencia seria quitarle el sentido a la comparacion.
  if (filtros.tienda !== TODOS && !producto.ofertas.some((oferta) => oferta.tienda === filtros.tienda)) {
    return false;
  }
  return true;
}
