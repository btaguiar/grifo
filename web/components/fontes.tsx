import { ArrowUpRight, Quote } from "lucide-react"

import { agruparPorAula, type Fonte } from "@/lib/grifo"

/** "4 - Inteligencia Artificial" chega como um campo só; na tela o número e o nome
 * ocupam lugares diferentes, então são separados aqui. */
function partes(rotulo: string): { numero: string; nome: string } {
  const m = rotulo.match(/^\s*(\d+)\s*-\s*(.+)$/)
  return m ? { numero: m[1], nome: m[2] } : { numero: "", nome: rotulo }
}

/** As fontes de uma resposta: citadas primeiro, uma linha por aula.
 *
 * `cited` vem do contrato validado da API: separa o que o modelo atribuiu do que ele
 * apenas leu. Sem essa distinção, "fontes" é só a lista do que o retrieval trouxe.
 */
export function Fontes({ fontes }: { fontes: Fonte[] }) {
  const aulas = agruparPorAula(fontes)
  if (aulas.length === 0) return null

  const citadas = aulas.filter((a) => a.cited)
  const consultadas = aulas.filter((a) => !a.cited)

  return (
    <div className="mt-5 border-t border-border pt-4">
      <ul className="grid gap-2">
        {citadas.map((aula) => (
          <LinhaFonte key={`${aula.modulo}${aula.aula}`} aula={aula} citada />
        ))}
      </ul>
      {consultadas.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer list-none px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
            {consultadas.length === 1
              ? "1 aula consultada sem citação"
              : `${consultadas.length} aulas consultadas sem citação`}
          </summary>
          <ul className="grid gap-2">
            {consultadas.map((aula) => (
              <LinhaFonte key={`${aula.modulo}${aula.aula}`} aula={aula} citada={false} />
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

function LinhaFonte({
  aula,
  citada,
}: {
  aula: Fonte & { trechos: number }
  citada: boolean
}) {
  const daAula = partes(aula.aula)
  const doModulo = partes(aula.modulo)

  const detalhe = [
    doModulo.numero ? `Módulo ${doModulo.numero}` : doModulo.nome,
    aula.autor,
    aula.trechos > 1 ? `${aula.trechos} trechos` : null,
  ]
    .filter(Boolean)
    .join(" · ")

  const corpo = (
    <>
      <span className="min-w-0">
        <span className="flex items-center gap-2 text-sm font-medium">
          {citada && (
            <Quote aria-hidden className="size-3.5 shrink-0 text-primary" strokeWidth={2.5} />
          )}
          <span className="truncate">
            {daAula.numero && `Aula ${daAula.numero}, `}
            {daAula.nome}
          </span>
        </span>
        <span className="mt-0.5 block text-xs text-muted-foreground">{detalhe}</span>
      </span>
      {aula.timestamp && (
        <span className="flex shrink-0 items-center gap-1 font-mono text-xs">
          {aula.timestamp}
          {aula.url && <ArrowUpRight aria-hidden className="size-3.5" strokeWidth={2} />}
        </span>
      )}
    </>
  )

  const base =
    "flex items-center justify-between gap-4 rounded-xl px-3 py-2.5 border transition-colors"
  const cor = citada
    ? "border-border bg-background"
    : "border-transparent bg-muted/60 text-muted-foreground"

  if (!aula.url) {
    return <li className={`${base} ${cor}`}>{corpo}</li>
  }

  return (
    <li>
      <a
        href={aula.url}
        target="_blank"
        rel="noreferrer"
        className={`${base} ${cor} hover:border-primary/60 hover:bg-primary/5 active:translate-y-px`}
      >
        {corpo}
      </a>
    </li>
  )
}
