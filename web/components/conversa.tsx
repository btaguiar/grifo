"use client"

import { motion, useReducedMotion } from "motion/react"
import { ArrowUp, Info, Lightbulb, TriangleAlert } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"

import { Fontes } from "@/components/fontes"
import { Button } from "@/components/ui/button"
import {
  PromptInput,
  PromptInputActions,
  PromptInputTextarea,
} from "@/components/ui/prompt-input"
import { PromptSuggestion } from "@/components/ui/prompt-suggestion"
import { SUGESTOES } from "@/lib/aulas"
import { FalhaDaApi, perguntar, type Resposta } from "@/lib/grifo"

type Turno = {
  id: string
  pergunta: string
  resposta?: Resposta
  erro?: string
}

export function Conversa() {
  const [texto, setTexto] = useState("")
  const [turnos, setTurnos] = useState<Turno[]>([])
  const [carregando, setCarregando] = useState(false)
  // Os chips ocupavam quatro linhas DENTRO do bloco fixo, e o espaco reservado
  // para ele virava um vao enorme entre a ultima resposta e o campo. Depois da
  // primeira pergunta eles viram um botao: quem quiser mais ideias abre.
  const [sugestoesAbertas, setSugestoesAbertas] = useState(false)
  // `useId` em vez de Math.random(): identificador estável e sem efeito colateral
  // no render, que é o que a regra de pureza do React exige.
  const sessao = useId()
  const fim = useRef<HTMLDivElement>(null)
  const campo = useRef<HTMLDivElement>(null)
  // Altura real do bloco fixo. Chutar um valor em Tailwind dava certo num
  // tamanho de tela e escondia a ultima resposta noutro, porque os chips
  // quebram em mais linhas conforme a largura.
  const [alturaDoCampo, setAlturaDoCampo] = useState(220)
  const semMovimento = useReducedMotion()

  useEffect(() => {
    const alvo = campo.current
    if (!alvo) return
    const observador = new ResizeObserver(([entrada]) =>
      setAlturaDoCampo(entrada.contentRect.height)
    )
    observador.observe(alvo)
    return () => observador.disconnect()
  }, [])

  useEffect(() => {
    if (turnos.length > 0) {
      fim.current?.scrollIntoView({
        behavior: semMovimento ? "auto" : "smooth",
        block: "end",
      })
    }
  }, [turnos, carregando, semMovimento])

  async function enviar(pergunta: string) {
    const limpa = pergunta.trim()
    if (!limpa || carregando) return
    const id = `${Date.now()}`
    setTexto("")
    setTurnos((anteriores) => [...anteriores, { id, pergunta: limpa }])
    setCarregando(true)
    try {
      const resposta = await perguntar(limpa, sessao)
      setTurnos((anteriores) =>
        anteriores.map((t) => (t.id === id ? { ...t, resposta } : t))
      )
    } catch (erro) {
      const mensagem =
        erro instanceof FalhaDaApi ? erro.message : "Algo deu errado ao perguntar."
      setTurnos((anteriores) =>
        anteriores.map((t) => (t.id === id ? { ...t, erro: mensagem } : t))
      )
    } finally {
      setCarregando(false)
    }
  }

  const vazia = turnos.length === 0

  return (
    <div className="flex flex-col gap-6">
      {/* Sem reservar a altura do campo aqui: a pagina CONTINUA depois do chat (a secao
          das aulas), entao ja existe rolagem de sobra para o ultimo turno sair de tras
          do campo fixo. Reservar de novo abria um vao morto no meio da tela. Quem
          garante que o scroll automatico nao para escondido e o `scrollMarginBottom`
          do elemento abaixo. */}
      {!vazia && (
        <div className="flex flex-col gap-8 pb-6">
          {turnos.map((turno) => (
            <Turno key={turno.id} turno={turno} semMovimento={semMovimento} />
          ))}
          {carregando && <Carregando />}
          {/* `scroll-mb` reserva a altura do campo fixo: sem isso o scroll ate o fim
              parava com a ultima resposta escondida atras dele */}
          <div ref={fim} className="h-2" style={{ scrollMarginBottom: alturaDoCampo + 16 }} />
        </div>
      )}

      <div
        ref={campo}
        className="sticky bottom-0 -mx-5 flex flex-col gap-3 border-t border-border bg-background px-5 pt-4 pb-5"
      >
        <PromptInput
          value={texto}
          onValueChange={setTexto}
          onSubmit={() => enviar(texto)}
          isLoading={carregando}
          className="rounded-2xl border border-input bg-card shadow-sm"
        >
          <PromptInputTextarea
            placeholder="O que você quer saber sobre as aulas?"
            className="text-base"
            aria-label="Sua dúvida"
          />
          <PromptInputActions className="justify-end">
            <Button
              size="icon"
              className="size-9 rounded-full"
              onClick={() => enviar(texto)}
              disabled={!texto.trim() || carregando}
              aria-label="Enviar pergunta"
            >
              <ArrowUp className="size-4" strokeWidth={2.5} />
            </Button>
          </PromptInputActions>
        </PromptInput>

        {(vazia || sugestoesAbertas) && (
          <div className="flex flex-wrap gap-2">
            {SUGESTOES.map((sugestao) => (
              <PromptSuggestion
                key={sugestao}
                size="sm"
                className="h-auto rounded-full px-3.5 py-1.5 text-sm font-normal whitespace-normal text-left active:translate-y-px"
                onClick={() => {
                  setSugestoesAbertas(false)
                  enviar(sugestao)
                }}
                disabled={carregando}
              >
                {sugestao}
              </PromptSuggestion>
            ))}
          </div>
        )}

        {!vazia && (
          <button
            type="button"
            onClick={() => setSugestoesAbertas((aberto) => !aberto)}
            className="flex items-center gap-1.5 self-start text-sm text-muted-foreground transition-colors hover:text-foreground"
            aria-expanded={sugestoesAbertas}
          >
            <Lightbulb aria-hidden className="size-4" strokeWidth={2} />
            {sugestoesAbertas ? "Esconder sugestões" : "Ver perguntas sugeridas"}
          </button>
        )}

        {vazia && (
          <p className="text-sm text-muted-foreground">
            As sugestões saem do conjunto de avaliação do projeto. A última não tem
            resposta no material, de propósito.
          </p>
        )}
      </div>
    </div>
  )
}

function Turno({ turno, semMovimento }: { turno: Turno; semMovimento: boolean | null }) {
  return (
    <motion.article
      initial={semMovimento ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col gap-4"
    >
      <p className="self-end max-w-[85%] rounded-2xl bg-secondary px-4 py-2.5 text-secondary-foreground">
        {turno.pergunta}
      </p>

      {turno.erro && <Falha mensagem={turno.erro} />}

      {turno.resposta &&
        (turno.resposta.found ? (
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="leading-relaxed whitespace-pre-wrap">{turno.resposta.answer}</p>
            <Fontes fontes={turno.resposta.sources} />
            <p className="mt-4 font-mono text-[11px] text-muted-foreground">
              {(turno.resposta.latency_ms / 1000).toFixed(1)}s ·{" "}
              {turno.resposta.tokens.input + turno.resposta.tokens.output} tokens
            </p>
          </div>
        ) : (
          <Recusa texto={turno.resposta.answer} />
        ))}
    </motion.article>
  )
}

/** A recusa é o comportamento certo, não um erro.
 *
 * Ela ganha peso visual próprio: borda tracejada e o acento da marca, porque é o que
 * distingue este assistente de um que responde qualquer coisa com confiança.
 */
function Recusa({ texto }: { texto: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-primary/60 bg-primary/5 p-5">
      <p className="flex items-start gap-2.5 font-medium">
        <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-primary" strokeWidth={2.5} />
        {texto}
      </p>
      <p className="mt-2 pl-[26px] text-sm text-muted-foreground">
        Prefiro dizer que não sei a inventar uma resposta.
      </p>
    </div>
  )
}

function Falha({ mensagem }: { mensagem: string }) {
  return (
    <p
      role="alert"
      className="flex items-start gap-2.5 rounded-2xl border border-destructive/40 bg-destructive/5 p-4 text-sm"
    >
      <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-destructive" />
      {mensagem}
    </p>
  )
}

/** Esqueleto com a forma da resposta: parágrafo mais bloco de fontes. */
function Carregando() {
  return (
    <div className="rounded-2xl border border-border bg-card p-5" aria-live="polite">
      <span className="sr-only">Consultando o material do curso</span>
      <div className="grid gap-2.5" aria-hidden>
        <div className="h-3.5 w-[92%] animate-pulse rounded bg-muted" />
        <div className="h-3.5 w-[84%] animate-pulse rounded bg-muted [animation-delay:120ms]" />
        <div className="h-3.5 w-[61%] animate-pulse rounded bg-muted [animation-delay:240ms]" />
        <div className="mt-3 h-9 w-full animate-pulse rounded-xl bg-muted [animation-delay:360ms]" />
      </div>
    </div>
  )
}
