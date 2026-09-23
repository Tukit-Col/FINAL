import { origenDeDatos } from "@tukit/contrato/servidor";
import FormularioEmpezar from "./FormularioEmpezar";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Armar mi kit — Tukit",
};

// Las cuatro anclas de una franquicia OFRECIBLE: cuaderno, cartuchera, carpeta
// y maleta. Una franquicia solo entra a la rejilla si el catalogo la surte
// completa en las cuatro; no se codifica la lista de franquicias (bluey, cars,
// frozen, minnie, paw patrol, spiderman, stitch hoy), se DERIVA de los conceptos
// que cada personaje trae, para que siga siendo correcta cuando el catalogo
// crezca.
const ANCLAS = ["C001", "C009", "C011", "C086"] as const;

export default async function Empezar() {
  // Los colegios y los personajes se leen en el servidor y viajan como prop: el
  // selector necesita la lista entera de colegios para filtrar grados, y la lista
  // de personajes surtidos completos para pintar solo lo que sí cumplimos.
  const [colegios, personajes] = await Promise.all([
    origenDeDatos().colegios(),
    origenDeDatos().personajes(),
  ]);

  // Filtro de las cuatro anclas: solo las franquicias cuyo conjunto de conceptos
  // es superconjunto de {C001, C009, C011, C086}. Ordenadas por popularidad
  // (conteo de productos) para que las más pedidas caigan primero.
  const surtidos = personajes
    .filter((p) => {
      const conceptos = new Set(p.conceptos ?? []);
      return ANCLAS.every((ancla) => conceptos.has(ancla));
    })
    .sort((a, b) => b.productos - a.productos)
    .map((p) => p.nombre.toLowerCase());

  return <FormularioEmpezar colegios={colegios} surtidos={surtidos} />;
}
