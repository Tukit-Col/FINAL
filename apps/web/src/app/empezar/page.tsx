import { origenDeDatos } from "@tukit/contrato/servidor";
import { sesionActual, matriculasDeLaSesion } from "@/lib/sesion";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
import FormularioEmpezar from "./FormularioEmpezar";
import AsistenteSlot from "./AsistenteSlot";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Armar mi kit · Tukit",
};

const ANCLAS = ["C001", "C009", "C011", "C086"] as const;

export default async function Empezar() {
  return conAvisoDeLimite(formulario);
}

async function formulario() {
  const [colegios, personajes, canonicos, sesion, matriculasIniciales] = await Promise.all([
    origenDeDatos().colegios(),
    origenDeDatos().personajes(),
    origenDeDatos().gradosCanonicos(),
    sesionActual(),
    matriculasDeLaSesion(),
  ]);

  const surtidos = personajes
    .filter((p) => {
      const conceptos = new Set(p.conceptos ?? []);
      return ANCLAS.every((ancla) => conceptos.has(ancla));
    })
    .sort((a, b) => b.productos - a.productos)
    .map((p) => p.nombre.toLowerCase());

  return (
    <>
      <AsistenteSlot />
      <FormularioEmpezar
        colegios={colegios}
        surtidos={surtidos}
        canonicos={canonicos}
        sesion={sesion ? { correo: sesion.correo } : null}
        matriculasIniciales={matriculasIniciales}
      />
    </>
  );
}
