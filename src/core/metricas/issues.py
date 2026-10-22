from fastapi import APIRouter, Query

from . import db

router = APIRouter()


@router.get("/resolution-time")
def resolution_time(days: int = Query(90, ge=7, le=730)):
    sql = """
        SELECT
            date_trunc('week', closed_at) AS semana,
            COUNT(*) AS fechadas,
            percentile_cont(0.5) WITHIN GROUP
                (ORDER BY EXTRACT(EPOCH FROM (closed_at - created_at))/3600) AS mediana_h,
            percentile_cont(0.9) WITHIN GROUP
                (ORDER BY EXTRACT(EPOCH FROM (closed_at - created_at))/3600) AS p90_h
        FROM issues
        WHERE closed_at IS NOT NULL
          AND closed_at >= now() - make_interval(days => %s)
        GROUP BY 1
        ORDER BY 1
    """
    return db.todos(sql, (days,))


@router.get("/throughput")
def throughput(days: int = Query(90, ge=7, le=730)):
    sql = """
        WITH abertas AS (
            SELECT date_trunc('week', created_at) AS semana, COUNT(*) AS n
            FROM issues WHERE created_at >= now() - make_interval(days => %(d)s)
            GROUP BY 1
        ), fechadas AS (
            SELECT date_trunc('week', closed_at) AS semana, COUNT(*) AS n
            FROM issues WHERE closed_at >= now() - make_interval(days => %(d)s)
            GROUP BY 1
        )
        SELECT COALESCE(a.semana, f.semana) AS semana,
               COALESCE(a.n, 0) AS abertas,
               COALESCE(f.n, 0) AS fechadas
        FROM abertas a FULL OUTER JOIN fechadas f ON a.semana = f.semana
        ORDER BY 1
    """
    return db.todos(sql, {"d": days})


@router.get("/by-label")
def by_label():
    sql = """
        SELECT label, COUNT(*) AS total
        FROM issues, unnest(labels) AS label
        GROUP BY label
        ORDER BY total DESC
        LIMIT 20
    """
    return db.todos(sql)


@router.get("/backlog-aging")
def backlog_aging():
    sql = """
        SELECT faixa, COUNT(*) AS total FROM (
            SELECT CASE
                WHEN now() - created_at < interval '7 days'  THEN 1
                WHEN now() - created_at < interval '30 days' THEN 2
                WHEN now() - created_at < interval '90 days' THEN 3
                ELSE 4
            END AS ordem,
            CASE
                WHEN now() - created_at < interval '7 days'  THEN '0-7 dias'
                WHEN now() - created_at < interval '30 days' THEN '8-30 dias'
                WHEN now() - created_at < interval '90 days' THEN '31-90 dias'
                ELSE '90+ dias'
            END AS faixa
            FROM issues WHERE state = 'open'
        ) t GROUP BY ordem, faixa ORDER BY ordem
    """
    return db.todos(sql)


@router.get("/summary")
def summary():
    sql = """
        SELECT
          COUNT(*) FILTER (WHERE state = 'open')   AS abertas,
          COUNT(*) FILTER (WHERE state = 'closed') AS fechadas,
          COUNT(*) FILTER (WHERE state = 'open'
                           AND created_at < now() - interval '90 days') AS abertas_90d
        FROM issues
    """
    return db.um(sql)
