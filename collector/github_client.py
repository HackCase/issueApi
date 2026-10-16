import os
import time
import httpx

TOKEN = os.environ["GITHUB_TOKEN"]
BASE = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

def respeitar_rate_limit(resp: httpx.Response) -> None:

    restante = int(resp.headers.get("X-RateLimit-Remaining", 1))

    if restante < 5:
        reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
        espera = max(reset - time.time(), 0) + 2
        print(f"Rate limit quase no fim {espera:.0f}s...")
        time.sleep(espera)


def paginar(url: str, params: dict | None = None):

    params = {**(params or {}), "per_page": 100}

    with httpx.Client(headers=HEADERS, timeout=30) as client:
    
        while url:
            resp = client.get(url, params=params)

            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                respeitar_rate_limit(resp)
                continue

            resp.raise_for_status()
            respeitar_rate_limit(resp)
            yield from resp.json()
            url = resp.links.get("next", {}).get("url")
            params = None


def get(url: str, params: dict | None = None) -> dict:

    with httpx.Client(headers=HEADERS, timeout=30) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()