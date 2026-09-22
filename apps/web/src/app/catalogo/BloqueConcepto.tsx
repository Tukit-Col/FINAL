import {
  ETIQUETA_NIVEL,
  NIVELES,
  ORDEN_NIVEL,
  precioMasBarato,
  type CoberturaConcepto,
  type ConceptoCatalogo,
  type ProductoCatalogo,
} from "@tukit/contrato";
import TarjetaProducto from "./TarjetaProducto";
import estilos from "./Catalogo.module.css";

const NIVELES_EN_ORDEN = [...NIVELES].sort((a, b) => ORDEN_NIVEL[a] - ORDEN_NIVEL[b]);

// Lo que significa cada tipo de renglon cuando NO es un util. Un concepto
// `no_comprar` sin productos no es un hueco de catalogo: es una instruccion
// del colegio de no comprar nada, y contarlo como carencia empujaria a
// taparlo con un producto inventado.
const ETIQUETA_TIPO: Partial<Record<ConceptoCatalogo["tipo_item"], string>> = {
  texto: "texto escolar",
  libro_libre: "libro de edición libre",
  licencia_digital: "se paga fuera de Tukit",
  no_comprar: "el colegio pide no comprarlo",
  diferido: "el colegio lo define durante el año",
  uniforme: "uniforme",
  otro: "otro",
};

interface Props {
  concepto: ConceptoCatalogo;
  cobertura: CoberturaConcepto;
  /** Los productos que pasaron los filtros, no necesariamente todos. */
  productos: ProductoCatalogo[];
  ocultos: number;
}

export default function BloqueConcepto({ concepto, cobertura, productos, ocultos }: Props) {
  const nivelesDelConcepto = new Set(concepto.productos.map((producto) => producto.nivel));
  const tipo = concepto.tipo_item === "util" ? null : ETIQUETA_TIPO[concepto.tipo_item];

  const grupos = NIVELES_EN_ORDEN.map((nivel) => ({
    nivel,
    // Dentro de un nivel lo unico que queda por comparar es el precio: el
    // nivel ya dijo la calidad. Los que no tienen precio conocido van al final
    // porque no se pueden comparar, no porque sean caros.
    productos: productos.filter((producto) => producto.nivel === nivel).sort(porPrecio),
  })).filter((grupo) => grupo.productos.length > 0);

  return (
    <section className={estilos.concepto} aria-labelledby={`concepto-${concepto.codigo}`}>
      <header className={estilos.cabeceraConcepto}>
        <div className={estilos.filaTitulo}>
          <h2 className={estilos.nombreConcepto} id={`concepto-${concepto.codigo}`}>
            {concepto.nombre_canonico}
          </h2>
          <span className={estilos.codigoConcepto}>{concepto.codigo}</span>
          <span className={estilos.categoria}>{concepto.categoria}</span>

          <div className={estilos.pastillas}>
            <span
              className={`${estilos.pastilla} ${estilos.pastillaDemanda}`}
              title="Cuántas líneas del corpus de listas piden este útil."
            >
              <span className="cifra">{concepto.frecuencia_demanda}</span> listas lo piden
            </span>

            {concepto.admite_personaje && (
              <span
                className={`${estilos.pastilla} ${estilos.pastillaPersonaje}`}
                title="El concepto admite variantes con personaje, y el personaje es independiente del nivel de calidad."
              >
                admite personaje
              </span>
            )}

            {tipo && <span className={`${estilos.pastilla} ${estilos.pastillaInfo}`}>{tipo}</span>}

            {cobertura === "tres_niveles" && (
              <span className={`${estilos.pastilla} ${estilos.pastillaCompleta}`}>3 niveles</span>
            )}
            {cobertura === "parcial" && (
              <span className={`${estilos.pastilla} ${estilos.pastillaParcial}`}>
                <span className="cifra">{nivelesDelConcepto.size}</span> de 3 niveles
              </span>
            )}
            {cobertura === "sin_productos" && (
              <span className={`${estilos.pastilla} ${estilos.pastillaVacia}`}>sin productos</span>
            )}
          </div>
        </div>

        {/* Los dos grupos de atributos se ven distintos porque hacen cosas
            distintas: los discriminantes descartan candidatos y los
            descriptivos solo le cuentan al acudiente que esta comprando. Quien
            cura el catalogo necesita esa diferencia de un vistazo, porque de
            ella depende si un atributo que casi ningun producto declara esta
            dejando sin resolver a un concepto entero. */}
        <div className={estilos.atributos}>
          <div className={estilos.grupoAtributos}>
            <span className={estilos.rotuloAtributos} title="Descartan candidatos al resolver la lista.">
              filtran
            </span>
            {concepto.atributos_discriminantes.length > 0 ? (
              concepto.atributos_discriminantes.map((atributo) => (
                <code key={atributo} className={estilos.atributoFiltra}>
                  {atributo}
                </code>
              ))
            ) : (
              <span className={estilos.atributoNinguno}>
                ninguno: se resuelve por nombre y nivel
              </span>
            )}
          </div>

          <div className={estilos.grupoAtributos}>
            <span
              className={estilos.rotuloAtributos}
              title="Se le muestran al acudiente, pero no descartan a nadie."
            >
              solo informan
            </span>
            {concepto.atributos_descriptivos.length > 0 ? (
              concepto.atributos_descriptivos.map((atributo) => (
                <code key={atributo} className={estilos.atributoInforma}>
                  {atributo}
                </code>
              ))
            ) : (
              <span className={estilos.atributoNinguno}>ninguno</span>
            )}
          </div>

          {concepto.sinonimos.length > 0 && (
            <span
              className={estilos.sinonimos}
              title={concepto.sinonimos.join(" · ")}
            >
              <span className="cifra">{concepto.sinonimos.length}</span>{" "}
              {concepto.sinonimos.length === 1 ? "sinónimo" : "sinónimos"} en las listas
            </span>
          )}
        </div>
      </header>

      {grupos.length === 0 ? (
        <p className={estilos.conceptoVacio}>
          Ningún producto todavía. Es un hueco real del catálogo y no un fallo de esta pantalla:
          cuando una lista pida <strong>{concepto.nombre_canonico}</strong>, el kit no lo va a poder
          incluir.
        </p>
      ) : (
        grupos.map((grupo) => (
          <div key={grupo.nivel} className={estilos.grupoNivel} data-nivel={grupo.nivel}>
            <h3 className={estilos.rotuloNivel}>
              {ETIQUETA_NIVEL[grupo.nivel]}
              <span className={estilos.conteoNivel}>
                <span className="cifra">{grupo.productos.length}</span>{" "}
                {grupo.productos.length === 1 ? "producto" : "productos"}
              </span>
            </h3>
            <div className={estilos.rejilla}>
              {grupo.productos.map((producto) => (
                <TarjetaProducto key={producto.sku} producto={producto} />
              ))}
            </div>
          </div>
        ))
      )}

      {ocultos > 0 && (
        <p className={estilos.notaOcultos}>
          <span className="cifra">{ocultos}</span>{" "}
          {ocultos === 1 ? "producto de este concepto no cumple" : "productos de este concepto no cumplen"}{" "}
          los filtros.
        </p>
      )}
    </section>
  );
}

function porPrecio(a: ProductoCatalogo, b: ProductoCatalogo): number {
  const precioA = precioMasBarato(a);
  const precioB = precioMasBarato(b);
  if (precioA === null) return precioB === null ? 0 : 1;
  if (precioB === null) return -1;
  return precioA - precioB;
}
