# issueApi

**Atas → Plano de ação → Issues.** Transforma uma reunião de gestão da Mega Jr. em tarefas rastreáveis:
a IA escreve a ata, entrevista o usuário sobre os problemas (estilo *grill-me*), gera um plano de ação
validado e produz os YAMLs das issues do GitHub. Uma API (FastAPI) também coleta issues da organização
para um dashboard.

Projeto da Batalha de Inovação Conecta v360, Trilha B (Tecnologia & TI).

## O problema

Decisões e problemas levantados em reuniões de gestão se perdem, e transformar uma reunião em tarefas no
board é lento e inconsistente. Cada pessoa registra de um jeito, ninguém sabe quem ficou responsável, e o
mesmo problema reaparece semana após semana sem que ninguém perceba.

## Como funciona

```
Reunião ──► Ata ──► Grill ──► Plano de ação ──► Aprovação ──► YAML das issues ──► (script) GitHub
(formulário) (IA)   (IA pergunta,  (IA gera JSON,   (humano)    (código renderiza,     create_issues.py
                    você responde)  guardrails valida)           o LLM nunca escreve YAML)
                          ▲                │
                          └── memória vetorial (pgvector): recorrência e possíveis duplicatas
```

1. `POST /reunioes` registra a reunião e gera a ata (resumo, acompanhamento, problemas).
2. `POST /reunioes/{id}/grill` e `POST /grill/{sessao}/respostas`: o grill acontece em **rodadas**. Cada
   rodada traz de uma vez as perguntas de todos os problemas (dono, prazo, critério de sucesso), cada uma com
   uma resposta sugerida; o usuário responde tudo e envia junto. Só se sobrarem lacunas há uma nova rodada,
   até `MAX_RODADAS_GRILL` (padrão 2). Contrato em [`docs/front-grill-rodadas.md`](docs/front-grill-rodadas.md).
3. `POST /reunioes/{id}/plano` gera o plano. `PATCH` edita o rascunho e `POST .../plano/aprovar` aprova.
4. `POST /reunioes/{id}/issues` gera um YAML por ação em `out/issues/<reuniao>/`.

O contrato completo está no Swagger: http://localhost:8000/docs.

### Guardrails

- **Sanitização:** e-mail, CPF, CNPJ e telefone são mascarados antes de ir ao LLM e revertidos na resposta.
  Os clientes são citados pelo título do projeto, então nomes de clientes não são mascarados.
- **Prompt injection:** o texto da reunião vai dentro de tags e é tratado como dado, nunca como instrução.
- **O LLM não escreve YAML:** devolve JSON validado por Pydantic, e o código renderiza o YAML.
- **Validação do plano:** labels só entre as de `config/labels.yaml`, responsáveis só entre os de
  `config/membros.yaml`, no máximo `MAX_ACOES` ações. Se falhar, há uma nova tentativa antes do erro.
- **`DRY_RUN`:** com `true` nada é commitado no repositório de atas, só escrito em `out/`.
- **Aprovação humana:** nenhuma issue é gerada sem o plano aprovado (`AUTO_APPROVE=false`).

## Rodar

Pré-requisitos: Docker e uma chave de API de LLM (veja a seção seguinte).

```bash
cp .env.example .env        # preencha GITHUB_TOKEN, GITHUB_ORG e LLM_API_KEY
docker compose up -d --build   # banco (pgvector) + API em http://localhost:8000/docs
```

Frontend (repositório `issueDash`):

```bash
cd ../issueDash && cp .env.example .env && npm install && npm run dev   # http://localhost:5173
```

Para testar o fluxo inteiro, use as reuniões de [`docs/exemplos-reunioes.md`](docs/exemplos-reunioes.md).

## Configurar o LLM

O núcleo fala o protocolo da OpenAI ou da Anthropic. Qualquer API compatível com a OpenAI funciona
trocando `OPENAI_BASE_URL`. Exemplo com o **Gemini** (chave gratuita em aistudio.google.com/apikey):

```
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_API_KEY=<chave>
LLM_MODEL_FAST=gemini-3.1-flash-lite     # ata
LLM_MODEL_STRONG=gemini-3.5-flash-lite   # grill e plano
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=1536                       # deve bater com a coluna vector(1536)
```

- Os modelos do Gemini mudam e ficam sobrecarregados com frequência; confira a lista em
  `GET {OPENAI_BASE_URL}/models`. O cliente repete a chamada em 429/5xx (5, 20, 40 e 60 s).
- O plano gratuito do Gemini limita cerca de 5 requisições por minuto **por modelo**, então um fluxo
  completo faz cerca de 4 chamadas ao LLM (ata, rodada 1 do grill, decisão da rodada 2, plano), por isso
  cabe na cota. Use modelos diferentes para `FAST` e `STRONG` para dividir a cota.
- A Anthropic não oferece embeddings: com `LLM_PROVIDER=anthropic`, defina `EMBEDDING_PROVIDER=openai`
  (ou outro compatível), senão a memória vetorial fica desligada e o resto continua funcionando.

### Atas no GitHub

`ATAS_MODE=github` commita as atas em `ATAS_REPO` (formato `org/repo`) na branch `ATAS_BRANCH`, e o token
precisa de *Contents: read and write* nesse repositório. Mantenha `DRY_RUN=true` até terminar os testes.

## Criar as issues no GitHub

A API só gera os YAMLs. O script cria as issues de verdade (**sem modo de simulação**):

```bash
pip install -r requirements.txt
python create_issues.py issues.yaml
```

`GITHUB_TOKEN` precisa de *Issues: write* e `GITHUB_REPO` (`org/repo`) define o destino.

## Desenvolvimento

```bash
pip install -e ".[dev]"
ruff check src tests && pytest
uvicorn core.main:app --reload
```

Os testes usam um cliente de LLM falso (`FakeLLM`), então não gastam cota nem dependem de rede.

## Configuração (`config/`)

| Arquivo | Para quê |
| --- | --- |
| `contexto_mega.md` | contexto da Mega (diretorias, valores, produtos); entra nos prompts de ata, grill e plano |
| `membros.yaml` | `membros: [{nome, github}]`; define os responsáveis válidos e os assignees das issues |
| `labels.yaml` | labels permitidas; precisam bater com as que existem no GitHub |
| `precos.yaml` | preço por 1M de tokens, para calcular o custo |

Os prompts ficam em `prompts/*.md`, versionados (`ata.v1`, `grill.v2`, `plano.v1`).

## Estrutura

```
src/core/        API e núcleo de IA (pipeline, guardrails, llm, memory, rotas)
collector/       coleta issues/PRs da org para o Postgres (dashboard)
prompts/         prompts versionados
config/          contexto, membros, labels, preços
docs/            exemplos de reuniões, roteiro do pitch e exemplo de issue
tests/           pytest
```

## Limites conhecidos

- Memória vetorial e deduplicação usam `DEDUP_THRESHOLD=0.85`, calibrado com poucos exemplos.
- A criação das issues no GitHub e no board é feita pelo `create_issues.py`, fora da API.
- Não há medição de custo por reunião exposta na API nem avaliação automática da qualidade da IA.

## Créditos

- Sessão de perguntas inspirada na skill **grill-me**, de Matt Pocock.
- O gerador de relatórios existente da EJ serviu apenas de inspiração de padrões; o código deste projeto
  foi escrito do zero.
