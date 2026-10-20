import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

# open=False: o pool abre/fecha no lifespan do FastAPI (ver main.py)
pool = ConnectionPool(
    os.environ["DATABASE_URL"],
    kwargs={"row_factory": dict_row},
    open=False,
)
