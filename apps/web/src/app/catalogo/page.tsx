import type { ResumenCatalogo } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import ExploradorCatalogo from "./ExploradorCatalogo";
import estilos from "./Catalogo.module.css";

// Esta es la pantalla que el equipo abre para saber si el catalogo crecio
// desde la ultima carga. Servida desde cache contestaria con la foto anterior,
// que es justo la pregunta que no se puede contestar mal.
export const dynamic = "force-dynamic";

type TonoCifra = "neutro" | "aviso" | "alerta";

interface Cifra {
  clave: string;
  valor: number;
  etiqueta: string;
  nota: string;
  tono: TonoCifra;
}

/**
 * Las siete cifras del resumen, cada una con su tono.
 *
 * Los tonos no son decoracion: que 17 conceptos no tengan un solo producto es
 * el dato mas util del encabezado, y pintarlo igual que "99 conceptos" lo
 * esconderia entre los numeros que si son buenos. La pantalla se usa para
 * decidir que curar, asi que la carencia tiene que resaltar mas que el logro.
 */
function cifrasDe(resumen: ResumenCatalogo): Cifra[] {
  return [
    {
      clave: "conceptos",
      valor: resumen.conceptos,
      etiqueta: "conceptos",
      nota: "necesidades distintas que piden las listas",
      tono: "neutro",
    },
    {
      clave: "productos",
      valor: resumen.productos,
      etiqueta: "productos",
      nota: "referencias curadas, no resultados de búsqueda",
      tono: "neutro",
    },
    {
      clave: "tres-niveles",
      valor: resumen.conceptos_con_tres_niveles,
      etiqueta: "con los 3 niveles",
      nota: `de ${resumen.conceptos} conceptos; el resto no se puede ofrecer en económico, confiable y premium a la vez`,
      tono: "aviso",
    },
    {
      clave: "sin-producto",
      valor: resumen.conceptos_sin_producto,
      etiqueta: "sin ningún producto",
      nota: "hoy no hay nada que ofrecer ahí",
      tono: "alerta",
    },
    {
      clave: "con-foto",
      valor: resumen.productos_con_foto,
      etiqueta: "con foto",
      nota: `de ${resumen.productos} productos; los demás se eligen leyendo el nombre`,
      tono: "aviso",
    },
    {
      clave: "tiendas",
      valor: resumen.tiendas,
      etiqueta: "tiendas",
      nota: "entre las que se compara precio",
      tono: "neutro",
    },
    {
      clave: "sin-revisar",
      valor: resumen.productos_sin_revisar,
      etiqueta: "sin revisar",
      nota: "los sugirió la búsqueda y nadie los confirmó todavía",
      tono: "aviso",
    },
  ];
}

export default async function PaginaCatalogo() {
  const catalogo = await origenDeDatos().catalogo();

  return (
    <div className={estilos.pagina}>
      <header className={estilos.encabezado}>
        <div className={estilos.interior}>
          <h1 className={estilos.titulo}>Catálogo curado</h1>
          <p className={estilos.entradilla}>
            Lo que hoy se le puede ofrecer a un acudiente: {catalogo.resumen.productos} productos
            revisados, repartidos entre los {catalogo.resumen.conceptos} útiles distintos que piden
            las listas de los colegios del corpus. Los huecos también están aquí y sin tapar,
            porque son lo que hay que curar después.
          </p>

          <ul className={estilos.cifras}>
            {cifrasDe(catalogo.resumen).map((cifra) => (
              <li key={cifra.clave} className={`${estilos.bloqueCifra} ${estilos[cifra.tono]}`}>
                <span className={`${estilos.valorCifra} cifra`}>{cifra.valor}</span>
                <span className={estilos.etiquetaCifra}>{cifra.etiqueta}</span>
                <span className={estilos.notaCifra}>{cifra.nota}</span>
              </li>
            ))}
          </ul>
        </div>
      </header>

      <ExploradorCatalogo catalogo={catalogo} />
    </div>
  );
}
