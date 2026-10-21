class ErroApi(Exception):
    """Erro de negócio com status HTTP; vira `{erro, detalhe}` em main.py."""

    def __init__(self, status: int, erro: str, detalhe: str = ""):
        super().__init__(detalhe or erro)
        self.status, self.erro, self.detalhe = status, erro, detalhe
