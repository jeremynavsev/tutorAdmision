import Logo from "./Logo";

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
    </div>
  );
}
