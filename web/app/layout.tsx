import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible, Bricolage_Grotesque, Caveat } from "next/font/google";
import "./globals.css";

// Las fuentes se descargan al compilar y se sirven desde el mismo sitio.
const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["400", "800"],
  variable: "--fuente-titulos",
  display: "swap",
});

const atkinson = Atkinson_Hyperlegible({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--fuente-texto",
  display: "swap",
});

const caveat = Caveat({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--fuente-tiza",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MAEstro",
  description:
    "Tutor de IA gratuito que te guía con pistas para la Prueba de Aptitud Académica de la UCR y la UNA.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#B3CCAE" },
    { media: "(prefers-color-scheme: dark)", color: "#0F1613" },
  ],
};

// Aplica el tema guardado antes de pintar, para que no parpadee al cargar.
const SCRIPT_TEMA = `try{var t=localStorage.getItem("maestro-tema");if(t==="dark"||t==="light")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-CR" className={`${bricolage.variable} ${atkinson.variable} ${caveat.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
