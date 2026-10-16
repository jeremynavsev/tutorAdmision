import Logo from "./Logo";

const PASOS = [
  "Escribí el problema o tomale una foto.",
  "Lo copio en la pizarra y encierro los datos.",
  "Te guío con preguntas y pistas, sin darte la respuesta.",
];

/** Lo que se ve en un chat nuevo, antes del primer mensaje. */
export default function Bienvenida() {
  return (
    <div className="bienvenida">
      <Logo ancho={190} />
      <h1>¿Qué problema vamos a resolver hoy?</h1>
      <p className="bienvenida-texto">
        Traé un ejercicio de razonamiento matemático o verbal, como los de la Prueba de Aptitud Académica de la UCR
        y la UNA.
      </p>
      <ol className="bienvenida-pasos">
        {PASOS.map((paso, i) => (
          <li key={paso} style={{ ["--i" as string]: i }}>
            <span className="bienvenida-numero" aria-hidden="true">
              {i + 1}
            </span>
            {paso}
          </li>
        ))}
      </ol>
    </div>
  );
}
