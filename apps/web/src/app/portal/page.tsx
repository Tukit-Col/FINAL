// Portal del colegio (aliado B2B).
//
// La app `apps/colegio` esta pendiente de portar (ADR 0008: tres apps por
// rol). En vez de un 404 o un portal falso, se muestra un aviso honesto: el rol
// se reconoce, el destino existe en el diseno, y lo que falta es construir la
// app. Se protege por rol en el servidor: quien no sea del colegio se va a
// /ingresar, fail-closed como `puede()`.

import Link from "next/link";
import { redirect } from "next/navigation";
import { Construction, GraduationCap } from "lucide-react";
import { sesionActual } from "@/lib/sesion";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
import SalirBoton from "@/components/SalirBoton";
import styles from "./Portal.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Portal del colegio — Tukit" };

const ROLES_COLEGIO = new Set(["colegio_admin", "colegio_docente"]);

export default async function Portal() {
  return conAvisoDeLimite(portal);
}

async function portal() {
  const sesion = await sesionActual();
  if (!sesion) redirect("/ingresar");
  const esColegio = sesion.roles.some((r) => ROLES_COLEGIO.has(r.rol));
  if (!esColegio) redirect("/ingresar");

  return (
    <div className={styles.pagina}>
      <section className={styles.tarjeta}>
        <span className={styles.icono} aria-hidden="true">
          <Construction size={26} strokeWidth={2.2} />
        </span>
        <h1 className={styles.titulo}>Portal del colegio, en construcción</h1>
        <p className={styles.saludo}>
          <GraduationCap size={15} strokeWidth={2.2} aria-hidden="true" />
          Hola, {sesion.nombre}
        </p>
        <p className={styles.texto}>
          Aquí vivirá el portal del aliado: publicar la lista oficial de cada grado y
          ver el panel institucional. Es una app aparte (<code>apps/colegio</code>) que
          todavía no está portada, así que reconocemos tu rol pero aún no hay pantalla
          que mostrarte. No te fabricamos una falsa.
        </p>
        <div className={styles.acciones}>
          <Link href="/" className={styles.secundario}>
            Volver al inicio
          </Link>
          <SalirBoton />
        </div>
      </section>
    </div>
  );
}
