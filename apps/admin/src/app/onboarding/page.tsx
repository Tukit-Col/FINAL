// `/onboarding` — P4, la entrada del revisor de listas.
//
// El administrador elige (colegio, grado) y sube el PDF de esa lista. El
// archivo va a inteligencia, que lo percibe y crea una version importada; la
// pantalla salta entonces al revisor de cuatro paneles de esa version.
//
// Server Component para leer: `colegios()` sale del origen directamente, sin
// pasar por el navegador. La subida si va por un Route Handler, que es donde la
// URL del backend y la bandera del origen se quedan del lado del servidor.

import { origenDeDatos } from "@tukit/contrato/servidor";
import FormularioOnboarding from "@/components/FormularioOnboarding";
import styles from "./Onboarding.module.css";

export const dynamic = "force-dynamic";

export default async function PaginaOnboarding() {
  // Todos los colegios, no solo los aliados: el onboarding es justo el paso que
  // convierte un colegio sin listas revisadas en aliado, asi que filtrar por
  // `es_partner` aqui esconderia los que mas falta hacen.
  const colegios = await origenDeDatos().colegios();

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Onboarding de una lista</h1>
          <p className={styles.bajada}>
            Sube el PDF de un grado y lo perciba inteligencia. Al terminar entras al revisor
            de cuatro paneles: el PDF, lo que leyó el modelo, las coincidencias de concepto y
            los tres kits, para aprobar la lista antes de que la vea un acudiente.
          </p>
        </div>
      </header>

      <FormularioOnboarding colegios={colegios} />
    </div>
  );
}
