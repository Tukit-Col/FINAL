import { origenDeDatos } from "@tukit/contrato/servidor";
import { sesionActual, matriculasDeLaSesion } from "@/lib/sesion";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
import FormularioEmpezar from "./FormularioEmpezar";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Armar mi kit · Tukit",
};

// Las cuatro anclas de una franquicia OFRECIBLE: cuaderno, cartuchera, carpeta
// y maleta. Una franquicia solo entra a la rejilla si el catalogo la surte
// completa en las cuatro; no se codifica la lista de franquicias (bluey, cars,
// frozen, minnie, paw patrol, spiderman, stitch hoy), se DERIVA de los conceptos
// que cada personaje trae, para que siga siendo correcta cuando el catalogo
// crezca.
const ANCLAS = ["C001", "C009", "C011", "C086"] as const;

// Con el cupo agotado (429) se pinta el aviso del limite: "sin sesion" o "sin
// hijos" haria que el acudiente con cuenta se registrara otra vez.
export default async function Empezar() {
  return conAvisoDeLimite(formulario);
}

async function formulario() {
  // Los colegios y los personajes se leen en el servidor y viajan como prop: el
  // selector necesita la lista entera de colegios para filtrar grados, y la lista
  // de personajes surtidos completos para pintar solo lo que sí cumplimos.
  // La sesion y las matriculas van juntas: si el acudiente ya entro (camino "ya
  // tengo cuenta"), el formulario arranca precargado con colegio+grado de cada
  // hijo. Sin sesion, `matriculasDeLaSesion()` devuelve [] y el formulario pide
  // escoger camino. Nunca viaja dato del menor: solo colegio, grado y anio.
  const [colegios, personajes, canonicos, sesion, matriculasIniciales] = await Promise.all([
    origenDeDatos().colegios(),
    origenDeDatos().personajes(),
    // Los (colegio, grado) con cache bendita: un hogar de un solo hijo verificado
    // que caiga en uno de estos toma la ruta rapida (aplicar_canonico, sin NSGA).
    origenDeDatos().gradosCanonicos(),
    sesionActual(),
    matriculasDeLaSesion(),
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

  return (
    <FormularioEmpezar
      colegios={colegios}
      surtidos={surtidos}
      canonicos={canonicos}
      sesion={sesion ? { correo: sesion.correo } : null}
      matriculasIniciales={matriculasIniciales}
    />
  );
}
