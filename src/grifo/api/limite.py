"""Travas de custo do `/ask`: limite por IP e teto diário.

Uma demo pública com LLM gasta dinheiro por visitante, e quem paga é o dono da chave.
Sem trava, um robô batendo no endpoint queima crédito durante a noite. Isto não
substitui o limite de crédito na conta do provedor -- essa é a única que não depende
de o código estar certo -- mas evita que o teto seja atingido por acesso repetido.

Contadores em memória: valem por instância. O deploy da demo roda uma instância só
(Cloud Run com `--max-instances 1`), então basta. Com réplicas, isto precisaria de contador
compartilhado, e a alternativa honesta seria um Redis, não fingir que funciona.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

#: Tempo em que as marcas de um IP ainda contam para o limite por minuto.
JANELA_SEGUNDOS = 60


class Limitador:
    """Conta perguntas por IP na janela de um minuto e no total do dia.

    `por_minuto` ou `diario` em 0 desligam a respectiva trava: é o padrão para quem
    roda local, onde o custo é do próprio dono e não existe visitante anônimo.
    """

    def __init__(self, por_minuto: int, diario: int) -> None:
        self.por_minuto = por_minuto
        self.diario = diario
        self._marcas: dict[str, deque[float]] = {}
        self._dia: str = ""
        self._do_dia = 0

    def _virar_o_dia(self, agora: datetime) -> None:
        hoje = agora.strftime("%Y-%m-%d")
        if hoje != self._dia:
            self._dia, self._do_dia = hoje, 0

    def checar(self, ip: str, agora: datetime | None = None) -> str | None:
        """Devolve o motivo da recusa, ou `None` quando a pergunta pode passar.

        Só conta o que passa: pergunta barrada não consome cota, senão um robô
        insistente empurraria o teto diário sozinho.
        """
        agora = agora or datetime.now(UTC)
        self._virar_o_dia(agora)

        if self.diario and self._do_dia >= self.diario:
            return (
                "A demo atingiu o limite de perguntas de hoje. "
                "O código está no repositório e roda na sua máquina sem limite."
            )

        if self.por_minuto:
            marcas = self._marcas.setdefault(ip, deque())
            agora_s = agora.timestamp()
            while marcas and agora_s - marcas[0] > JANELA_SEGUNDOS:
                marcas.popleft()
            if len(marcas) >= self.por_minuto:
                return "Muitas perguntas seguidas. Espere um minuto e tente de novo."
            marcas.append(agora_s)

        self._do_dia += 1
        return None

    @property
    def usadas_hoje(self) -> int:
        return self._do_dia
