import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"

import { TooltipProvider } from "@/components/ui/tooltip"
import "./globals.css"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "Grifo, assistente de dúvidas de curso",
  description:
    "Responde só com o material oficial, cita a aula e abre o vídeo no minuto. Quando a resposta não está no material, recusa.",
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      // O script abaixo troca a classe do tema antes da hidratacao: sem isto o React
      // reclama de divergencia entre o HTML do servidor e o do cliente.
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        {/* O tema escuro do shadcn depende da classe `dark`. Sem alguem aplica-la a
            preferencia do sistema era ignorada. Roda antes da pintura para nao
            piscar o tema errado, e acompanha a troca em tempo real. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(()=>{const m=matchMedia("(prefers-color-scheme: dark)");const a=e=>document.documentElement.classList.toggle("dark",e.matches);a(m);m.addEventListener("change",a)})()`,
          }}
        />
      </head>
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  )
}
