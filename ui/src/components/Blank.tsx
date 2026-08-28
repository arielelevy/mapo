import s from "./Blank.module.css";

/** Una pantalla vacía es una invitación a actuar, no un cartel de estado. */
export default function Blank() {
  return (
    <div className={s.blank}>
      <h1>Mirá al motor decidir antes de que responda.</h1>
      <p>
        MAPO poda trece paradigmas por aritmética, filtra por el dial de garantía y puntúa
        lo que queda con&nbsp;θ. Recién entonces ejecuta — o se abstiene.
      </p>
      <ol>
        <li>
          <span>01</span>
          <div>
            Soltá documentos en el workspace. La ingesta corre asincrónica y te muestra
            qué decidió el sensor en cada archivo.
          </div>
        </li>
        <li>
          <span>02</span>
          <div>
            Arrastrá unidades a la bandeja de contexto. Ahí elegís qué entra y qué no, y
            ves cuántos paradigmas te queda cada elección.
          </div>
        </li>
        <li>
          <span>03</span>
          <div>
            Preguntá. La escalera de decisión se resuelve arriba; la respuesta llega
            después.
          </div>
        </li>
      </ol>
    </div>
  );
}
