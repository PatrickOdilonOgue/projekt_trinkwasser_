"""SQLite-Datenbank aufbauen und benannte SQL-Abfragen ausführen."""
import re, sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "trinkwasser.db"


def build_db(evaluation: pd.DataFrame, limits: pd.DataFrame) -> Path:
    DB.unlink(missing_ok=True)
    with sqlite3.connect(DB) as con:
        evaluation.assign(use_for_compliance=evaluation["use_for_compliance"].astype(int)) \
            .to_sql("evaluation", con, index=False)
        limits.to_sql("limits", con, index=False)
        con.execute("CREATE INDEX ix_eval ON evaluation(station_id, parameter, sample_date)")
    return DB


def load_queries(path=ROOT / "sql" / "queries.sql") -> dict[str, str]:
    text = Path(path).read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run(name: str) -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql_query(load_queries()[name], con)
