import logging

import httpx
import yaml
from fastapi import APIRouter, Depends

from ..deps import get_config, get_memoria, get_store, novo_sanitizador
from ..erros import ErroApi
from ..integrations.atas_repo import salvar_ata
from ..pipeline.issues_yaml import atualizar_ata, caminho_yaml, gerar_issues
from ..rotas.grill import _reuniao
from ..schemas import PlanoAcao
from ..settings import Settings, get_settings
from ..store import obter, salvar

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/reunioes/{reuniao_id}/issues")
def gerar(
    reuniao_id: str,
    s: Settings = Depends(get_settings),
    store=Depends(get_store),
    memoria=Depends(get_memoria),
):
    reg = _reuniao(store, reuniao_id)
    plano = obter(store, "plano", reuniao_id, PlanoAcao)
    if plano is None:
        raise ErroApi(404, "plano_nao_encontrado", reuniao_id)
    yamls = gerar_issues(plano, reg.reuniao, reg.ata_path, get_config(s), s.max_acoes)

    pasta = s.out_dir / "issues" / reuniao_id  # sempre dentro de out/, inclusive com DRY_RUN
    pasta.mkdir(parents=True, exist_ok=True)
    for velho in [*pasta.glob("*.yml"), *pasta.glob("*.criada")]:  # só as issues desta geração
        velho.unlink()
    for acao_id, texto in yamls.items():
        (pasta / f"{acao_id}.yml").write_text(texto, encoding="utf-8")

    ata = atualizar_ata(reg.ata_md, plano)
    salvar_ata(reuniao_id, ata, s)
    salvar(store, "reuniao", reuniao_id, reg.model_copy(update={"ata_md": ata}))
    if memoria:
        try:
            memoria.registrar_issues(plano, novo_sanitizador(s))
        except Exception as e:  # noqa: BLE001 - modo degradado: os YAMLs já foram gerados
            logger.warning("memória vetorial falhou ao registrar as issues: %s", e)
    return [
        {"acao_id": a, "path": caminho_yaml(reuniao_id, a), "conteudo": t} for a, t in yamls.items()
    ]


@router.post("/reunioes/{reuniao_id}/issues/publicar")
def publicar(reuniao_id: str, s: Settings = Depends(get_settings)):
    """Cria no GitHub as issues dos YAMLs gerados. Idempotente por issue (marca .criada)."""
    pasta = s.out_dir / "issues" / reuniao_id
    arquivos = sorted(pasta.glob("*.yml"))
    if not arquivos:
        raise ErroApi(404, "issues_nao_geradas", reuniao_id)
    if not (s.github_token and s.github_repo):
        raise ErroApi(400, "github_nao_configurado", "defina GITHUB_TOKEN e GITHUB_REPO")
    headers = {
        "Authorization": f"Bearer {s.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    criadas = []
    for f in arquivos:
        marca = f.with_suffix(".criada")  # url da issue já criada: reenvio/retry não duplica
        if marca.exists():
            url, titulo = marca.read_text(encoding="utf-8").split("\n", 1)
            criadas.append({"acao_id": f.stem, "titulo": titulo, "url": url})
            continue
        y = yaml.safe_load(f.read_text(encoding="utf-8"))
        payload = {k: y.get(k) or d for k, d in (("title", ""), ("body", ""), ("labels", []), ("assignees", []))}
        r = httpx.post(
            f"https://api.github.com/repos/{s.github_repo}/issues", json=payload, headers=headers, timeout=30
        )
        if r.status_code >= 400:
            raise ErroApi(502, "github_falhou", f"{f.stem}: {r.status_code} {r.text[:300]}")
        url = r.json()["html_url"]
        marca.write_text(f"{url}\n{payload['title']}", encoding="utf-8")
        criadas.append({"acao_id": f.stem, "titulo": payload["title"], "url": url})
    return criadas
