import Link from "next/link";
import DocumentoLegal, { Dato } from "../DocumentoLegal";
import { RESPONSABLE } from "../datos-legales";

export const metadata = { title: "Derecho de retracto y garantía | Tukit" };

export default function PaginaRetracto() {
  return (
    <DocumentoLegal
      titulo="Derecho de retracto y garantía"
      resumen="Puedes devolver tu pedido en los 5 días hábiles siguientes a recibirlo, y los productos con defectos tienen garantía. Se rige por la Ley 1480 de 2011."
    >
      <h2>Derecho de retracto (artículo 47)</h2>
      <p>
        Como compras a distancia, puedes retractarte de la compra y devolver el producto sin dar explicaciones, dentro
        de los <strong>5 días hábiles contados desde la entrega</strong>. En tu pedido te mostramos la fecha límite.
      </p>
      <ul>
        <li>Pídelo desde <Link href="/dashboard">Mis pedidos</Link>, con el botón de retracto. Solo aparece mientras el plazo esté vigente.</li>
        <li>Devuelve los productos en buen estado, sin usar y con su empaque, tal como los recibiste.</li>
        <li>Te devolvemos el dinero sin descuentos, a más tardar 30 días calendario después de que ejerces el derecho.</li>
        <li>Los costos de transporte y otros de la devolución corren por tu cuenta, como lo establece la ley.</li>
      </ul>

      <h2>Cuándo no aplica (artículo 50)</h2>
      <p>La ley excluye el retracto, entre otros casos, cuando se trata de:</p>
      <ul>
        <li>Productos hechos según tus especificaciones o claramente personalizados.</li>
        <li>Bienes que por su naturaleza no pueden devolverse o se deterioran con rapidez.</li>
        <li>Programas informáticos y archivos digitales descargables que ya abriste o usaste, como las licencias digitales.</li>
        <li>Prensa y publicaciones periódicas.</li>
      </ul>
      <p>
        Si un producto de tu pedido está en alguno de estos casos, te lo diremos al responder tu solicitud.
      </p>

      <h2>Garantía legal (artículo 7)</h2>
      <p>
        Los productos tienen garantía legal: si llegan defectuosos o no sirven para lo que se ofrecen, puedes pedir
        que los reparemos, cambiemos o te devolvamos el dinero. La garantía se pide aparte del retracto y no depende
        del plazo de 5 días. El tiempo de garantía lo define cada producto, según la ley o la información del
        fabricante.
      </p>
      <p>
        Para pedirla abre un caso desde <Link href="/dashboard">Mis casos</Link> contando qué pasó, o escribe a{" "}
        <Dato valor={RESPONSABLE.correo} />.
      </p>

      <h2>Si no estás de acuerdo con nuestra respuesta</h2>
      <p>Puedes presentar tu reclamación ante la Superintendencia de Industria y Comercio.</p>
    </DocumentoLegal>
  );
}
