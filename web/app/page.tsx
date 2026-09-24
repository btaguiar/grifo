import Image from "next/image"
import { ArrowUpRight } from "lucide-react"

import { Conversa } from "@/components/conversa"
import { AULAS } from "@/lib/aulas"

const REPO = "https://github.com/btaguiar/grifo"

export default function Home() {
  return (
    <>
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-6 px-5">
          <span className="flex items-baseline gap-2.5">
            <span className="text-lg font-semibold tracking-tight">Grifo</span>
            <span className="hidden text-sm text-muted-foreground sm:inline">
              assistente de dúvidas de curso
            </span>
          </span>
          <a
            href={REPO}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Código
            <ArrowUpRight aria-hidden className="size-3.5" strokeWidth={2} />
          </a>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-5 pt-12 pb-20 sm:pt-16">
        <h1 className="max-w-[24ch] text-4xl font-semibold tracking-tight text-balance sm:text-[3.25rem] sm:leading-[1.05]">
          Pergunte ao curso. A resposta <span className="marca-texto">grifa</span> a aula
          e abre no minuto.
        </h1>
        <p className="mt-4 max-w-[52ch] text-lg text-muted-foreground">
          Responde só com o material oficial. Quando a resposta não está lá, recusa em
          vez de inventar.
        </p>

        <section className="mt-10" aria-label="Conversa com o assistente">
          <Conversa />
        </section>
      </main>

      <section className="border-t border-border bg-muted/30">
        <div className="mx-auto max-w-5xl px-5 py-16">
          <h2 className="text-2xl font-semibold tracking-tight">
            O material indexado
          </h2>
          <p className="mt-2 max-w-[60ch] text-muted-foreground">
            Seis aulas públicas, quase três horas de vídeo, 332 trechos indexados. A
            resposta sempre aponta de volta para um destes vídeos, no segundo exato.
          </p>

          <ul className="mt-8 grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
            {AULAS.map((aula) => (
              <li key={aula.videoId}>
                <a
                  href={`https://www.youtube.com/watch?v=${aula.videoId}`}
                  target="_blank"
                  rel="noreferrer"
                  className="group block"
                >
                  <Image
                    src={`https://i.ytimg.com/vi/${aula.videoId}/hqdefault.jpg`}
                    alt={`Aula ${aula.numero}, ${aula.titulo}, com ${aula.autor}`}
                    width={480}
                    height={360}
                    className="aspect-video w-full rounded-xl border border-border object-cover transition-colors group-hover:border-primary/70"
                  />
                  <p className="mt-3 flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
                    <span>
                      Aula {aula.numero} · {aula.modulo}
                    </span>
                    <span>{aula.duracao}</span>
                  </p>
                  <p className="mt-1 font-medium tracking-tight group-hover:underline">
                    {aula.titulo}
                  </p>
                  <p className="text-sm text-muted-foreground">{aula.autor}</p>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="border-t border-border">
        <div className="mx-auto max-w-5xl px-5 py-16">
          <h2 className="max-w-[24ch] text-2xl font-semibold tracking-tight">
            Cada número abaixo saiu de uma rodada que você consegue repetir
          </h2>

          <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-8 lg:grid-cols-4">
            <Numero valor="1.00" rotulo="Recusa correta" nota="5 de 5 fora do escopo" />
            <Numero
              valor="0.00"
              rotulo="Taxa de alucinação"
              nota="juiz calibrado, κ 0.905"
            />
            <Numero
              valor="19/19"
              rotulo="Fonte certa quando responde"
              nota="a aula citada é a aula certa"
            />
            <Numero
              valor="US$ 0,0063"
              rotulo="Custo da rodada"
              nota="25 perguntas, tokens medidos"
            />
          </dl>

          <p className="mt-10 max-w-[65ch] text-muted-foreground">
            O modo de falha deste assistente é recusar demais, não inventar: das 20
            perguntas respondíveis, uma foi recusada indevidamente. O motivo está medido
            e publicado.
          </p>
          <a
            href={`${REPO}/blob/main/EVALUATION.md`}
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-flex items-center gap-1 font-medium underline decoration-primary decoration-2 underline-offset-4"
          >
            Ler a metodologia
            <ArrowUpRight aria-hidden className="size-4" strokeWidth={2} />
          </a>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-sm text-muted-foreground">
          <p>
            Projeto de portfólio de Bruno Aguiar. O material das aulas é do canal que o
            publicou.
          </p>
          <a
            href={REPO}
            target="_blank"
            rel="noreferrer"
            className="transition-colors hover:text-foreground"
          >
            github.com/btaguiar/grifo
          </a>
        </div>
      </footer>
    </>
  )
}

function Numero({
  valor,
  rotulo,
  nota,
}: {
  valor: string
  rotulo: string
  nota: string
}) {
  return (
    <div className="border-t border-border pt-4">
      <dt className="text-sm font-medium">{rotulo}</dt>
      <dd className="mt-2 font-mono text-3xl tracking-tight tabular-nums">{valor}</dd>
      <dd className="mt-1 text-sm text-muted-foreground">{nota}</dd>
    </div>
  )
}
