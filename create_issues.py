import os
import sys
import yaml
import requests
from dotenv import load_dotenv

load_dotenv()


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_issue(repo, token, issue):
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "title": issue["title"],
        "body": issue.get("body", ""),
        "labels": issue.get("labels", []),
        "assignees": issue.get("assignees", []),
    }
    
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()["html_url"]

def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is missing. Add it to your .env file.")

    path = sys.argv[1] if len(sys.argv) > 1 else "issues.yaml"
    config = load_config(path)

    repo = config.get("repo") or os.getenv("GITHUB_REPO")
    if not repo:
        sys.exit("No repo defined in the YAML or in GITHUB_REPO.")

    issues = config.get("issues") or []
    if not issues:
        sys.exit("No issues defined in the YAML.")

    falhas = 0
    for issue in issues:
        try:
            url = create_issue(repo, token, issue)
            print(f"Created: {issue['title']} -> {url}")
        except requests.HTTPError as e:
            falhas += 1
            print(f"Failed: {issue['title']} -> {e.response.status_code} {e.response.text}")
        except requests.RequestException as e:
            falhas += 1
            print(f"Failed: {issue['title']} -> {e}")

    sys.exit(1 if falhas else 0)

if __name__ == "__main__":
    main()




