import re
from pathlib import Path

import yaml

from ..schemas import MeetingInput

# Ordem importa: e-mail antes dos números; CNPJ antes de CPF antes de telefone.
# ponytail: 11 dígitos soltos viram CPF (não telefone) e qualquer grupo de 8 dígitos vira
# telefone; super-mascarar é o lado seguro (refinar com dígito verificador se incomodar).
PADROES = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("CNPJ", re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")),
    ("CPF", re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")),
    (
        "TELEFONE",
        re.compile(r"(?<!\d)(?:\+?55[\s-]?)?(?:\(?\d{2}\)?[\s-]?)?9?\d{4}[-\s]?\d{4}(?!\d)"),
    ),
]


def carregar_clientes(config_dir: Path) -> list[str]:
    arq = config_dir / "clientes.yaml"
    if not arq.exists():
        return []
    return (yaml.safe_load(arq.read_text(encoding="utf-8")) or {}).get("clientes") or []


class Sanitizador:
    """Mascara dados sensíveis antes do envio ao LLM e guarda o mapa de reversão (só local).

    Um Sanitizador por requisição: o mapa cresce a cada `mascarar` e `reverter` desfaz tudo.
    """

    def __init__(self, clientes: list[str] = ()):
        self.mapa: dict[str, str] = {}  # placeholder -> original
        self._ids: dict[tuple[str, str], str] = {}
        self._padroes = list(PADROES)
        nomes = sorted({c.strip() for c in clientes if c.strip()}, key=len, reverse=True)
        if nomes:
            rx = re.compile(r"\b(?:" + "|".join(map(re.escape, nomes)) + r")\b", re.IGNORECASE)
            self._padroes.insert(0, ("CLIENTE", rx))

    def _placeholder(self, tipo: str, original: str) -> str:
        chave = (tipo, original.casefold())
        if chave not in self._ids:
            n = sum(1 for t, _ in self._ids if t == tipo) + 1
            self._ids[chave] = f"[{tipo}_{n}]"
            self.mapa[self._ids[chave]] = original
        return self._ids[chave]

    def mascarar(self, texto: str) -> str:
        for tipo, rx in self._padroes:
            texto = rx.sub(lambda m, t=tipo: self._placeholder(t, m.group()), texto)
        return texto

    def reverter(self, texto: str) -> str:
        for ph, original in self.mapa.items():
            texto = texto.replace(ph, original)
        return texto

    def reverter_dados(self, x):
        """Reverte recursivamente todas as strings de dict/list (saída JSON do LLM)."""
        if isinstance(x, str):
            return self.reverter(x)
        if isinstance(x, list):
            return [self.reverter_dados(i) for i in x]
        if isinstance(x, dict):
            return {k: self.reverter_dados(v) for k, v in x.items()}
        return x

    def mascarar_reuniao(self, r: MeetingInput) -> MeetingInput:
        # participantes são membros da EJ (internos): não mascarados
        return r.model_copy(
            update={
                "titulo": self.mascarar(r.titulo),
                "acompanhamento": self.mascarar(r.acompanhamento),
                "problemas": [self.mascarar(p) for p in r.problemas],
            }
        )
