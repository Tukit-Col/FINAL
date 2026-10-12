import ResultadoPago from "./ResultadoPago";

// Wompi vuelve aqui con ?id=<transaccion>&env=test; el simulador, con
// ?id=falsa-APPROVED-<ref>. Solo hace falta el id.
export default async function PaginaResultadoPago({
  searchParams,
}: {
  searchParams: Promise<{ id?: string | string[] }>;
}) {
  const { id } = await searchParams;
  return <ResultadoPago id={Array.isArray(id) ? id[0] : id} />;
}
