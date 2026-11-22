import ResultadoPago from "./ResultadoPago";

export default async function PaginaResultadoPago({
  searchParams,
}: {
  searchParams: Promise<{ id?: string | string[] }>;
}) {
  const { id } = await searchParams;
  return <ResultadoPago id={Array.isArray(id) ? id[0] : id} />;
}
