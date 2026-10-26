"""Compliance-Logik: Messwerte gegen TrinkwV 2023 und WHO prüfen.

Jede Zeile bekommt einen Status und eine Auslastung (Wert / Grenzwert).
Überschreitungen landen zusätzlich in einem Protokoll, das jede einzelne
Bewertung bis zur Rohdatei-Zeile zurückverfolgbar macht.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WARN_FRACTION = 0.8  # Vorwarnbereich: >= 80 % des Grenzwerts

HINWEIS_US_LCR = (
    "Einzelprobe an US-Entnahmestelle (Lead-and-Copper-Rule-Probenahme, i. d. R. "
    "Stagnationsproben an Risikohaushalten). Zeigt eine Überschreitung des "
    "deutschen/WHO-Zahlenwerts, ist aber keine formale TrinkwV-Grenzwertverletzung."
)


def evaluate(clean: pd.DataFrame, limits: pd.DataFrame) -> pd.DataFrame:
    cols = ["parameter", "limit_trinkwv", "trinkwv_ref", "limit_who", "who_ref", "who_type"]
    m = clean.merge(limits[cols], on="parameter", how="left")

    m["ratio_trinkwv"] = m["value"] / m["limit_trinkwv"]
    m["ratio_who"] = m["value"] / m["limit_who"]

    def status(ratio, limit_present, used):
        s = np.where(ratio > 1, "Überschreitung",
                     np.where(ratio >= WARN_FRACTION, "Vorwarnbereich (≥80 % GW)", "eingehalten"))
        s = np.where(~limit_present, "kein Grenzwert", s)
        return np.where(~used, "ausgeschlossen (QS)", s)

    has_tw = m["limit_trinkwv"].notna()
    has_who = m["limit_who"].notna()
    m["status"] = status(m["ratio_trinkwv"], has_tw, m["use_for_compliance"])
    m["status_who"] = status(m["ratio_who"], has_who, m["use_for_compliance"])

    sev = pd.cut(m["ratio_trinkwv"], [1, 2, 5, np.inf], right=True,
                 labels=["1–2× GW", "2–5× GW", ">5× GW"])
    m["severity"] = sev.astype("object").where(m["status"] == "Überschreitung", None)

    m["year"] = m["sample_date"].dt.year
    m["quarter"] = m["sample_date"].dt.to_period("Q").astype(str).where(m["sample_date"].notna())
    m["sample_date"] = m["sample_date"].dt.strftime("%Y-%m-%d")
    return m


def exceedance_log(ev: pd.DataFrame) -> pd.DataFrame:
    """Nachvollziehbares Protokoll aller Überschreitungen (TrinkwV)."""
    e = ev[ev["status"] == "Überschreitung"].copy()

    def fmt(x):
        return f"{x:.4g}".replace(".", ",")

    e["begruendung"] = (
        e["parameter"] + " " + e["value"].map(fmt) + " " + e["unit"]
        + " > Grenzwert " + e["limit_trinkwv"].map(fmt) + " " + e["unit"]
        + " (" + e["trinkwv_ref"] + "); " + e["ratio_trinkwv"].round(2).astype(str)
        + "× GW; WHO-Status: " + e["status_who"] + " [" + e["who_type"] + "]"
    )
    e["datenherkunft"] = e["src_file"] + ", Zeile " + e["src_row"].astype(int).astype(str) \
        + ", Rohwert '" + e["value_raw"].astype(str) + "'"
    e["bewertungshinweis"] = np.where(e["source"].str.startswith("Michigan"), HINWEIS_US_LCR, "")
    keep = ["measurement_id", "source", "station_id", "station", "sample_date", "parameter",
            "value", "unit", "limit_trinkwv", "ratio_trinkwv", "severity", "status_who",
            "qc_flag", "begruendung", "datenherkunft", "bewertungshinweis"]
    return e[keep].sort_values(["ratio_trinkwv"], ascending=False).reset_index(drop=True)


def data_quality_report(clean: pd.DataFrame) -> pd.DataFrame:
    """Zeilen je Quelle: Rohbestand, verwendet, ausgeschlossen nach Grund."""
    rows = []
    for src, g in clean.groupby("source"):
        f = g["qc_flag"]
        rows.append({
            "source": src,
            "rows_raw": len(g),
            "rows_used": int(g["use_for_compliance"].sum()),
            "excl_missing": int(f.str.contains("missing|invalid_value").sum()),
            "excl_rejected": int(f.str.contains("rejected_").sum()),
            "excl_duplicate": int(f.str.contains("duplicate").sum()),
            "excl_implausible": int(f.str.contains("negative|implausible_high").sum()),
            "flag_unit_converted": int(f.str.contains("unit_converted").sum()),
            "flag_range_or_multi": int(f.str.contains("range_max|multi_max").sum()),
            "flag_below_loq": int(f.str.contains("below_loq").sum()),
            "flag_nd_zero": int(f.str.contains("nd_zero").sum()),
            "flag_stat_outlier": int(f.str.contains("stat_outlier").sum()),
        })
    return pd.DataFrame(rows)
