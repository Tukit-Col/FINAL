import { origenDeDatos } from "@tukit/contrato/servidor";
import FormularioEmpezar from "./FormularioEmpezar";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Armar mi kit — Tukit",
};

export default async function Empezar() {
  // Los colegios se leen en el servidor y viajan como prop: el selector
  // necesita la lista entera para poder filtrar los grados de cada colegio, y
  // pedirla desde el navegador solo agregaria una espera antes de poder
  // escribir.
  const colegios = await origenDeDatos().colegios();
  return <FormularioEmpezar colegios={colegios} />;
}
