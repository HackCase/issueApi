import os
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv

from github_client import paginar, get, BASE

load_dotenv()
ORG = os.environ["GITHUB_ORG"]
DB_URL = os.environ["DATABASE_URL"]


def get_last_sync(conn, key: str):
    row = conn.execute(
        "SELECT last_sync FROM sync_state WHERE resource = %s", (key,)
    ).fetchone()
    return row[0].isoformat() if row else None


def set_last_sync(conn, key: str, quando: datetime):
    conn.execute(
        """INSERT INTO sync_state (resource, last_sync) VALUES (%s, %s)
           ON CONFLICT (resource) DO UPDATE SET last_sync = EXCLUDED.last_sync""",
        (key, quando),
    )


def coletar_repos(conn):
    ids = []
    for r in paginar(f"{BASE}/orgs/{ORG}/repos", {"type": "all"}):
        conn.execute(
            """INSERT INTO repos (id, name, full_name, archived, pushed_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET
                 name=EXCLUDED.name, archived=EXCLUDED.archived,
                 pushed_at=EXCLUDED.pushed_at, updated_at=EXCLUDED.updated_at""",
            (r["id"], r["name"], r["full_name"], r["archived"],
             r["pushed_at"], r["updated_at"]),
        )
        ids.append((r["id"], r["name"]))
    return ids


def coletar_issues(conn, repo_id: int, repo_name: str):
    key = f"issues:{repo_name}"
    inicio = datetime.now(timezone.utc)
    params = {"state": "all"}
    since = get_last_sync(conn, key)

    if since:
        params["since"] = since

    for i in paginar(f"{BASE}/repos/{ORG}/{repo_name}/issues", params):

        if "pull_request" in i:
            continue

        conn.execute(
            """INSERT INTO issues
               (id, repo_id, number, title, state, author, assignee, labels,
                comments, created_at, closed_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET
                 title=EXCLUDED.title, state=EXCLUDED.state,
                 assignee=EXCLUDED.assignee, labels=EXCLUDED.labels,
                 comments=EXCLUDED.comments, closed_at=EXCLUDED.closed_at,
                 updated_at=EXCLUDED.updated_at""",
            (
                i["id"], repo_id, i["number"], i["title"], i["state"],
                (i.get("user") or {}).get("login"),
                (i.get("assignee") or {}).get("login"),
                [l["name"] for l in i["labels"]],
                i["comments"], i["created_at"], i["closed_at"], i["updated_at"],
            ),
        )

    set_last_sync(conn, key, inicio)


def coletar_prs(conn, repo_id: int, repo_name: str):
    key = f"prs:{repo_name}"
    inicio = datetime.now(timezone.utc)
    ultimo = get_last_sync(conn, key)

    params = {"state": "all", "sort": "updated", "direction": "desc"}

    for pr in paginar(f"{BASE}/repos/{ORG}/{repo_name}/pulls", params):

        if ultimo and pr["updated_at"] < ultimo:
            break

        det = get(pr["url"])

        reviews = list(paginar(pr["url"] + "/reviews"))
        datas = [r["submitted_at"] for r in reviews
                 if r.get("submitted_at")
                 and (r.get("user") or {}).get("login") != (pr.get("user") or {}).get("login")]
        primeira = min(datas) if datas else None

        conn.execute(
            """INSERT INTO pull_requests
               (id, repo_id, number, title, state, author, draft, additions,
                deletions, changed_files, review_comments, created_at,
                first_review_at, merged_at, closed_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET
                 state=EXCLUDED.state, draft=EXCLUDED.draft,
                 additions=EXCLUDED.additions, deletions=EXCLUDED.deletions,
                 changed_files=EXCLUDED.changed_files,
                 review_comments=EXCLUDED.review_comments,
                 first_review_at=EXCLUDED.first_review_at,
                 merged_at=EXCLUDED.merged_at, closed_at=EXCLUDED.closed_at,
                 updated_at=EXCLUDED.updated_at""",
            (
                pr["id"], repo_id, pr["number"], pr["title"], pr["state"],
                (pr.get("user") or {}).get("login"), pr["draft"],
                det["additions"], det["deletions"], det["changed_files"],
                det["review_comments"], pr["created_at"], primeira,
                pr["merged_at"], pr["closed_at"], pr["updated_at"],
            ),
        )

    set_last_sync(conn, key, inicio)


def main():

    with psycopg.connect(DB_URL, autocommit=False) as conn:

        with open("schema.sql") as f:
            conn.execute(f.read())
        conn.commit()

        for repo_id, repo_name in coletar_repos(conn):
            print(f"Coletando {repo_name}...")
            coletar_issues(conn, repo_id, repo_name)
            coletar_prs(conn, repo_id, repo_name)
            conn.commit()


if __name__ == "__main__":
    main()