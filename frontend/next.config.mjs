/** @type {import('next').NextConfig} */
const nextConfig = {
  // Salida autónoma para la imagen de Docker (`node server.js`).
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    // Solo para `next dev` local: en producción /api lo resuelve Nginx.
    const apiInterna = process.env.API_INTERNA;
    if (!apiInterna) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${apiInterna.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
