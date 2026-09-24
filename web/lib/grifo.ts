/** Contrato DC-2 da API do Grifo, e o pouco de lógica que o front precisa ter. */

export type Fonte = {
  modulo: string
  aula: string
  autor: string | null
  timestamp: string | null
  /** A aula já no minuto do trecho. `null` quando o corpus não declara a URL. */
  url: string | null
  /** O modelo CITOU esta fonte, contra apenas tê-la consultado. */
  cited: boolean
  score: number
}

export type Resposta = {
  answer: string
  sources: Fonte[]
  found: boolean
  latency_ms: number
  tokens: { input: number; output: number }
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010"
const CURSO = process.env.NEXT_PUBLIC_CURSO ?? "G4 Business (aulas públicas)"

/** Uma linha por AULA, e não por trecho.
 *
 * A API devolve um item por chunk recuperado, e dois trechos da mesma aula viravam
 * duas linhas idênticas. Aqui a aula fica com o melhor score e o timestamp do trecho
 * que o obteve; `cited` vale se qualquer trecho dela foi citado. Citadas primeiro.
 */
export function agruparPorAula(fontes: Fonte[]): (Fonte & { trechos: number })[] {
  const porAula = new Map<string, Fonte & { trechos: number }>()
  for (const fonte of fontes) {
    const chave = `${fonte.modulo}|${fonte.aula}`
    const atual = porAula.get(chave)
    if (!atual) {
      porAula.set(chave, { ...fonte, trechos: 1 })
      continue
    }
    atual.trechos += 1
    atual.cited = atual.cited || fonte.cited
    if (fonte.score > atual.score) {
      atual.score = fonte.score
      atual.timestamp = fonte.timestamp
      atual.url = fonte.url
    }
  }
  return [...porAula.values()].sort(
    (a, b) => Number(b.cited) - Number(a.cited) || b.score - a.score
  )
}

export class FalhaDaApi extends Error {
  constructor(
    message: string,
    readonly tipo: "timeout" | "http" | "rede"
  ) {
    super(message)
  }
}

/** Manda a dúvida para o `POST /ask`.
 *
 * O timeout é generoso porque a resposta passa por retrieval e LLM: no modelo local
 * a primeira pergunta já levou 30s. Quem estoura recebe uma mensagem que diz o que
 * falhou, em vez do genérico "não consegui falar com o serviço".
 */
export async function perguntar(question: string, sessionId: string): Promise<Resposta> {
  const controle = new AbortController()
  const corta = setTimeout(() => controle.abort(), 90_000)
  try {
    const r = await fetch(`${API}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId, curso: CURSO }),
      signal: controle.signal,
    })
    if (!r.ok) {
      throw new FalhaDaApi(
        `A API respondeu com erro ${r.status}. O log dela diz o motivo, em geral o provedor do LLM.`,
        "http"
      )
    }
    return (await r.json()) as Resposta
  } catch (erro) {
    if (erro instanceof FalhaDaApi) throw erro
    if (erro instanceof DOMException && erro.name === "AbortError") {
      throw new FalhaDaApi("A resposta passou de 90 segundos. Tente de novo.", "timeout")
    }
    throw new FalhaDaApi(
      "Não consegui falar com o serviço do Grifo. Confira se a API está no ar.",
      "rede"
    )
  } finally {
    clearTimeout(corta)
  }
}
