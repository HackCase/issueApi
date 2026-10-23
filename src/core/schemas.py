import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Prioridade = Literal["baixa", "media", "alta", "urgente"]
Severidade = Literal["baixa", "media", "alta", "critica"]


class MeetingInput(BaseModel):
    titulo: str
    data: date
    participantes: list[str] = []
    acompanhamento: str  # rotina / status
    problemas: list[str] = Field(min_length=1)  # 1..N problemas em texto livre

    @property
    def reuniao_id(self) -> str:
        slug = unicodedata.normalize("NFKD", self.titulo).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "reuniao"
        return f"{self.data.isoformat()}-{slug}"

    @property
    def problema_ids(self) -> list[str]:
        return [f"p{i}" for i in range(1, len(self.problemas) + 1)]


class GrillPergunta(BaseModel):
    id: str  # r1q1, r1q2, r2q1...
    problema_id: str | None = None  # p1, p2... ou null para pergunta geral
    pergunta: str
    recomendacao: str | None = None  # resposta sugerida pela IA (estilo grill-me)
    resposta: str | None = None  # preenchida pelo usuário


class GrillRodada(BaseModel):
    perguntas: list[GrillPergunta]


class GrillSessao(BaseModel):
    sessao_id: str
    reuniao_id: str
    rodadas: list[GrillRodada]  # a última é a que está em aberto enquanto status=em_andamento
    status: Literal["em_andamento", "concluida"]
    max_rodadas: int = 2


class Acao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str  # a1, a2...
    titulo: str  # curto, verbo no infinitivo
    descricao: str
    criterios_aceite: list[str] = Field(min_length=1)
    labels: list[str]  # exatamente 1 diretoria + opcionais
    prioridade: Prioridade
    severidade: Severidade
    estimativa: Literal[1, 2, 3, 5, 8, 13]
    responsavel: str | None = None  # deve estar em membros.yaml, se informado
    prazo: date | None = None
    problema_origem: str  # ex.: p1


class Duplicata(BaseModel):
    reuniao_id: str
    acao_id: str
    titulo: str
    similaridade: float


class PlanoAcao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reuniao_id: str
    status: Literal["rascunho", "aprovado"] = "rascunho"
    acoes: list[Acao]
    # problema_id -> justificativa de não gerar ação (5.4, última regra)
    justificativas: dict[str, str] = {}
    # preenchidos pela memória vetorial; só informativos (o humano decide), não vão pro YAML
    recorrencias: dict[str, int] = {}  # problema_id -> nº de reuniões anteriores com o problema
    possiveis_duplicatas: dict[str, Duplicata] = {}  # acao_id -> issue anterior parecida
    avisos: list[str] = []  # ex.: memória vetorial indisponível (modo degradado)
