import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // As miniaturas das aulas vêm do próprio YouTube: é a imagem real do material
    // que o assistente indexa, e ela some junto se o vídeo sair do ar - o que é a
    // informação certa para quem olha a demo.
    remotePatterns: [{ protocol: "https", hostname: "i.ytimg.com" }],
  },
};

export default nextConfig;
