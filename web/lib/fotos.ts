/**
 * Prepara la foto del cuaderno antes de subirla.
 *
 * En el navegador mismo se endereza (según la orientación que guardó la
 * cámara), se reduce y se vuelve a guardar como JPEG. Así el estudiante gasta
 * muchos menos datos móviles, la foto nunca pasa el límite del backend y los
 * metadatos (como la ubicación GPS) no salen del teléfono: al redibujarla en un
 * lienzo solo quedan los pixeles.
 *
 * El backend igual la vuelve a limpiar, por si alguien llama a la API sin pasar
 * por esta página.
 */

const LADO_MAXIMO_PX = 1600;
const CALIDAD_JPEG = 0.82;
/** Tamaño máximo del archivo original. Una foto de celular pesa entre 3 y 12 MB. */
const MAX_ARCHIVO_BYTES = 40 * 1024 * 1024;

/** La foto no se puede usar. El mensaje está pensado para mostrárselo al estudiante. */
export class ErrorDeFoto extends Error {
  constructor(mensaje: string) {
    super(mensaje);
    this.name = "ErrorDeFoto";
  }
}

export type FotoLista = {
  /** JPEG reducido en base64, sin el prefijo "data:image/jpeg;base64,". */
  base64: string;
  /** Dirección local para mostrar la foto en el chat. */
  url: string;
  ancho: number;
  alto: number;
  /** Peso del JPEG reducido. */
  bytes: number;
};

type Decodificada = { fuente: CanvasImageSource; ancho: number; alto: number; soltar: () => void };

/** Abre el archivo como imagen, ya derecha. Prueba dos caminos porque no todos los navegadores soportan el primero. */
async function decodificar(archivo: File): Promise<Decodificada> {
  if (typeof createImageBitmap === "function") {
    try {
      const mapa = await createImageBitmap(archivo, { imageOrientation: "from-image" });
      return { fuente: mapa, ancho: mapa.width, alto: mapa.height, soltar: () => mapa.close() };
    } catch {
      // Se intenta con una etiqueta <img>, que soporta algunos formatos más.
    }
  }
  const url = URL.createObjectURL(archivo);
  try {
    const imagen = new Image();
    imagen.src = url;
    await imagen.decode();
    return { fuente: imagen, ancho: imagen.naturalWidth, alto: imagen.naturalHeight, soltar: () => URL.revokeObjectURL(url) };
  } catch {
    URL.revokeObjectURL(url);
    throw new ErrorDeFoto("No se pudo abrir la foto. Probá con una en JPG o PNG.");
  }
}

function aBase64(blob: Blob): Promise<string> {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader();
    lector.onload = () => resolver(String(lector.result).split(",")[1] ?? "");
    lector.onerror = () => rechazar(new ErrorDeFoto("No se pudo leer la foto. Probá con otra."));
    lector.readAsDataURL(blob);
  });
}

/** Devuelve la foto reducida, derecha y sin metadatos, lista para mandarla al tutor. */
export async function prepararFoto(archivo: File): Promise<FotoLista> {
  if (!archivo.type.startsWith("image/")) {
    throw new ErrorDeFoto("Ese archivo no es una imagen. Mandá una foto en JPG o PNG.");
  }
  if (archivo.size > MAX_ARCHIVO_BYTES) {
    throw new ErrorDeFoto("La foto es demasiado pesada. Probá con una de menor resolución.");
  }

  const { fuente, ancho, alto, soltar } = await decodificar(archivo);
  try {
    if (!ancho || !alto) throw new ErrorDeFoto("No se pudo abrir la foto. Probá con otra.");
    // Solo se reduce: una foto pequeña no se agranda.
    const escala = Math.min(1, LADO_MAXIMO_PX / Math.max(ancho, alto));
    const lienzo = document.createElement("canvas");
    lienzo.width = Math.max(1, Math.round(ancho * escala));
    lienzo.height = Math.max(1, Math.round(alto * escala));
    const contexto = lienzo.getContext("2d");
    if (!contexto) throw new ErrorDeFoto("Este navegador no puede preparar la foto. Probá con otro.");
    // JPEG no tiene transparencia: lo transparente queda blanco, como una hoja.
    contexto.fillStyle = "#ffffff";
    contexto.fillRect(0, 0, lienzo.width, lienzo.height);
    contexto.imageSmoothingQuality = "high";
    contexto.drawImage(fuente, 0, 0, lienzo.width, lienzo.height);

    const blob = await new Promise<Blob | null>((resolver) => lienzo.toBlob(resolver, "image/jpeg", CALIDAD_JPEG));
    if (!blob) throw new ErrorDeFoto("No se pudo preparar la foto. Probá con otra.");
    return {
      base64: await aBase64(blob),
      url: URL.createObjectURL(blob),
      ancho: lienzo.width,
      alto: lienzo.height,
      bytes: blob.size,
    };
  } finally {
    soltar();
  }
}
