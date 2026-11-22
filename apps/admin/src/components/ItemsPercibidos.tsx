"use client";

import { useState } from "react";
import { type ConceptoCreado, type ItemRevision, type PropuestaRevision } from "@tukit/contrato";
import { candidatosDe } from "@/lib/atributos-renglon";
import type { OpcionConcepto } from "./PanelReclasificar";
import type { VocabularioConceptos } from "@/lib/vocabulario-conceptos";
import styles from "@/app/onboarding/Onboarding.module.css";
import RenglonEditable from "./RenglonEditable";
import AltaRenglon from "./AltaRenglon";

interface Props {
  versionId: string;
  revisada: boolean;
  items: ItemRevision[];
  propuestas: PropuestaRevision[];
  conceptos: OpcionConcepto[];
  vocabulario: VocabularioConceptos;
  valoresAtributos?: Record<string, Record<string, string[]>>;
}

export default function ItemsPercibidos({
  versionId,
  revisada,
  items,
  propuestas,
  conceptos: conceptosIniciales,
  vocabulario,
  valoresAtributos = {},
}: Props) {
  const [conceptos, setConceptos] = useState(conceptosIniciales);

  function alCrearConcepto(creado: ConceptoCreado) {
    setConceptos((previos) =>
      [...previos, { codigo: creado.codigo, nombre: creado.nombre_canonico }].sort((a, b) =>
        a.nombre.localeCompare(b.nombre),
      ),
    );
  }

  if (items.length === 0) {
    return <p className={styles.pendienteContrato}>El modelo no itemizó ninguna línea.</p>;
  }

  return (
    <div className={styles.items}>
      {items.map((item) => (
        <RenglonEditable
          key={item.id}
          versionId={versionId}
          revisada={revisada}
          item={item}
          candidatos={candidatosDe(item, propuestas)}
          conceptos={conceptos}
          vocabulario={vocabulario}
          sugerencias={item.concepto_codigo ? (valoresAtributos[item.concepto_codigo] ?? {}) : {}}
          onConceptoCreado={alCrearConcepto}
        />
      ))}
      <AltaRenglon versionId={versionId} revisada={revisada} />
    </div>
  );
}
