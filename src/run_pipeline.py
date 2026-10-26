"""Gesamte Pipeline: ETL -> Compliance -> SQLite/SQL -> Exporte -> Grafiken."""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import etl, compliance, db, plots

ROOT = etl.ROOT
PROC, TAB, FIG = ROOT / "data/processed", ROOT / "tableau", ROOT / "reports/figures"


def main():
    limits = pd.read_csv(ROOT / "data/limits.csv")
    clean = etl.build_clean_table()
    clean.to_csv(PROC / "measurements_clean.csv", index=False, encoding="utf-8")

    ev = compliance.evaluate(clean, limits)
    log = compliance.exceedance_log(ev)
    dq = compliance.data_quality_report(clean)
    log.to_csv(PROC / "exceedance_log.csv", index=False, encoding="utf-8")
    dq.to_csv(PROC / "data_quality_report.csv", index=False, encoding="utf-8")

    db.build_db(ev, limits)
    rate = db.run("exceedance_rate_parameter")
    trend = db.run("trend_quarterly_lead")
    top = db.run("top_stations")
    rank = db.run("ranking_critical_parameters")
    p90 = db.run("p90_lead_system_year")

    # Exporte für Tableau (UTF-8, ein Fakt + vier Aggregate)
    fact_cols = ["measurement_id", "source", "region", "station_id", "station", "sample_date",
                 "year", "quarter", "parameter", "value", "unit", "limit_trinkwv", "limit_who",
                 "ratio_trinkwv", "status", "status_who", "severity", "qc_flag", "use_for_compliance"]
    ev[fact_cols].to_csv(TAB / "tableau_measurements.csv", index=False, encoding="utf-8")
    rate.to_csv(TAB / "tableau_kpi_parameter.csv", index=False, encoding="utf-8")
    trend.to_csv(TAB / "tableau_trend_quarterly_lead.csv", index=False, encoding="utf-8")
    top.to_csv(TAB / "tableau_top_stations.csv", index=False, encoding="utf-8")
    rank.to_csv(TAB / "tableau_ranking_parameters.csv", index=False, encoding="utf-8")
    log.to_csv(TAB / "tableau_exceedances.csv", index=False, encoding="utf-8")
    p90.to_csv(TAB / "tableau_p90_lead_system_year.csv", index=False, encoding="utf-8")

    plots.dashboard(rate, trend, top, FIG / "dashboard_preview.png")
    plots.quality(dq, FIG / "data_quality.png")
    print(dq.to_string()); print(rank.to_string()); print(len(log), "Überschreitungen protokolliert")


if __name__ == "__main__":
    main()
