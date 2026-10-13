import type { NextConfig } from "next";

// Sitio estático: `npm run build` genera la carpeta out/.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
