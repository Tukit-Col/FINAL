// `/onboarding/{version_id}/preview/{trabajo_id}` — la vista previa de los tres
// kits que saldrían de una versión de lista (región 4 del revisor).
//
// El `trabajo_id` es de un trabajo de PREVIEW desechable que armó
// `previewDeVersion` (POST /api/listas/{version_id}/preview), NO el trabajo de un
// acudiente. Por eso la página es de solo lectura: se leen los kits con el
// `trabajoAdmin(trabajo_id)` de siempre y se pintan con `KitsPreview`, sin ninguna
// acción que valide, edite o publique —esas viven en la página de revisión.
//
// Server Component para leer; un 404 (`trabajo_no_existe`) se traduce a
// `notFound()`.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { TrabajoAdmin } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import KitsPreview from "./KitsPreview";
import styles from "../../../Onboarding.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ version_id: string; trabajo_id: string }>;
}

export default async function PaginaPreviewKits({ params }: Props) {
  const { version_id, trabajo_id } = await params;

  let trabajo: TrabajoAdmin;
  try {
    trabajo = await origenDeDatos().trabajoAdmin(trabajo_id);
  } catch (causa) {
    if (causa instanceof ErrorTukit && causa.estado === 404) notFound();
    throw causa;
  }

  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href={`/onboarding/${encodeURIComponent(version_id)}`}>← Volver a la revisión</Link>
      </nav>

      <header className={styles.encabezado}>
        <div>
          <h1>Vista previa de los 3 kits</h1>
          <p className={styles.bajada}>
            Estos son los tres kits que saldrían de esta versión de lista. Es una vista de{" "}
            <strong>solo lectura</strong>: no aprueba ni publica nada. Para publicar, vuelve a la
            revisión y usa <em>Aprobar y publicar</em>.
          </p>
        </div>
      </header>

      <KitsPreview trabajo={trabajo} />
    </div>
  );
}
