/** O corpus da demo: as seis aulas públicas indexadas.
 *
 * Mesma fonte de verdade do `corpus/aulas-publicas/fontes.json` do repositório. Os
 * ids são os do YouTube, e é deles que sai a miniatura real de cada aula.
 */

export type Aula = {
  modulo: string
  numero: number
  titulo: string
  autor: string
  videoId: string
  duracao: string
}

export const AULAS: Aula[] = [
  {
    modulo: "Vendas",
    numero: 1,
    titulo: "Como vender mais e melhor",
    autor: "Alfredo Soares",
    videoId: "bhOSSMFs1gI",
    duracao: "40 min",
  },
  {
    modulo: "Crescimento",
    numero: 2,
    titulo: "Como crescer uma empresa",
    autor: "Bruno Nardon",
    videoId: "exYVpYbERno",
    duracao: "40 min",
  },
  {
    modulo: "Crescimento",
    numero: 3,
    titulo: "Empreender do zero no Brasil",
    autor: "Guilherme Benchimol",
    videoId: "5TXx-P8qnr8",
    duracao: "46 min",
  },
  {
    modulo: "Crescimento",
    numero: 4,
    titulo: "Construir uma empresa do zero",
    autor: "Tallis Gomes",
    videoId: "k2zFLImP0kM",
    duracao: "50 min",
  },
  {
    modulo: "Marketing",
    numero: 5,
    titulo: "Marketing em 2026",
    autor: "Fernando Miranda",
    videoId: "8Nd-iMcUbXE",
    duracao: "28 min",
  },
  {
    modulo: "Inteligência artificial",
    numero: 6,
    titulo: "IA nos negócios em 2026",
    autor: "João Vitor Chaves",
    videoId: "PzNNFxg-dng",
    duracao: "34 min",
  },
]

/** Perguntas de partida.
 *
 * Saem do golden set revisado (`eval/golden_set_aulas_publicas.jsonl`): são as mesmas
 * que a suíte de avaliação usa, então o que o visitante clica é o que está medido. A
 * última é fora do escopo de propósito, para a recusa aparecer sem ninguém precisar
 * inventar uma pergunta ruim.
 */
export const SUGESTOES = [
  "Qual a diferença entre assistente de IA e agente de IA?",
  "Qual é a primeira crise de crescimento que uma empresa enfrenta?",
  "Como decidir qual vendedor atende cada lead?",
  "O que acontece quando uma empresa cresce muito por delegação?",
  "Qual a receita do bolo de cenoura?",
]
