from fastapi import APIRouter, Query
from ..db import pool

router = APIRouter()


@router.get("/review-time")
def review_time(days: int = Query(90, ge=7, le=730)):
    """Tempo até a primeira revisão e tempo até o merge (horas), por semana."""
    sql = """
        SELECT
            date_trunc('week', created_at) AS semana,
            percentile_cont(0.5) WITHIN GROUP
              (ORDER BY EXTRACT(EPOCH FROM (first_review_at - created_at))/3600)
              FILTER (WHERE first_review_at IS NOT NULL) AS primeira_review_h,
            percentile_cont(0.5) WITHIN GROUP
              (ORDER BY EXTRACT(EPOCH FROM (merged_at - created_at))/3600)
              FILTER (WHERE merged_at IS NOT NULL) AS ate_merge_h
        FROM pull_requests
        WHERE created_at >= now() - make_interval(days => %s)
        GROUP BY 1 ORDER BY 1
    """
    with pool.connection() as conn:
        return conn.execute(sql, (days,)).fetchall()


@router.get("/size-distribution")
def size_distribution():
    sql = """
        SELECT faixa, COUNT(*) AS total FROM (
            SELECT CASE
                WHEN additions + deletions <= 50   THEN 1
                WHEN additions + deletions <= 250  THEN 2
                WHEN additions + deletions <= 1000 THEN 3
                ELSE 4
            END AS ordem,
            CASE
                WHEN additions + deletions <= 50   THEN 'P (até 50)'
                WHEN additions + deletions <= 250  THEN 'M (51-250)'
                WHEN additions + deletions <= 1000 THEN 'G (251-1000)'
                ELSE 'GG (1000+)'
            END AS faixa
            FROM pull_requests
            WHERE merged_at IS NOT NULL
              AND additions IS NOT NULL AND deletions IS NOT NULL
        ) t GROUP BY ordem, faixa ORDER BY ordem
    """
    with pool.connection() as conn:
        return conn.execute(sql).fetchall()


@router.get("/merge-rate")
def merge_rate():
    sql = """
        SELECT
          COUNT(*) FILTER (WHERE merged_at IS NOT NULL)                       AS merged,
          COUNT(*) FILTER (WHERE state='closed' AND merged_at IS NULL)        AS fechados_sem_merge,
          COUNT(*) FILTER (WHERE state='open')                                AS abertos
        FROM pull_requests
    """
    with pool.connection() as conn:
        return conn.execute(sql).fetchone()
