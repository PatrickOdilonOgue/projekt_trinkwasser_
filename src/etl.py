"""ETL für Trinkwasser-Messwerte (reale, öffentliche Datenquellen).

Ergebnis ist eine *lange* Tabelle (ein Messwert pro Zeile) mit einheitlicher
Einheit (mg/L bzw. °dH), Herkunftsnachweis (Quelle + Zeilennummer) und
Qualitäts-Flags. Es wird nichts stillschweigend gelöscht: Auffälligkeiten
werden als Flag markiert, ausgeschlossen wird nur über `use_for_compliance`.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# Umrechnung in mg/L
UNIT_TO_MGL = {"mg/l": 1.0, "ug/l": 1e-3, "µg/l": 1e-3, "g/l": 1e3, "ng/l": 1e-6}

PARAM_MAP = {  # Rohspaltenname -> (Parameter, Einheit)
    "natrium": ("Natrium", "mg/L"), "kalium": ("Kalium", "mg/L"),
    "calcium": ("Calcium", "mg/L"), "magnesium": ("Magnesium", "mg/L"),
    "chlorid": ("Chlorid", "mg/L"), "nitrat": ("Nitrat", "mg/L"),
    "sulfat": ("Sulfat", "mg/L"),
}
LONG_COLS = [
    "source", "src_file", "src_row", "station_id", "station", "region",
    "sample_date", "sample_type", "parameter", "value_raw", "value", "unit",
    "value_min", "value_max", "qc_flag", "use_for_compliance",
]


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------
def parse_de_number(raw) -> tuple[float, float, float, str]:
    """Parst deutsche Zahlenangaben aus Webtabellen.

    Rückgabe: (Wert für die Prüfung, Min, Max, Flag)
    - '12,5'            -> 12.5                      (ok)
    - '15-17' / '15-7,8'-> Maximum (konservativ)     (range_max)
    - '<1'              -> 1 (Bestimmungsgrenze)     (below_loq)
    - 'K: 13,3\\nR: 33,1' -> Maximum der Teilwerte   (multi_max)
    - 'k.A.', '-', leer -> NaN                       (missing)
    Für Bereiche wird bewusst der *höchste* Wert verwendet, damit eine mögliche
    Überschreitung nicht durch Mittelung verschwindet.
    """
    nan = float("nan")
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return nan, nan, nan, "missing"
    text = str(raw).strip()
    if not text or re.fullmatch(r"[-–—\s]*", text) or re.search(
        r"k\.?\s*a\.?|n\.?\s*a\.?|hart", text, flags=re.I
    ) and not re.search(r"\d+[.,]?\d*\s*$", text.split(":")[-1]):
        return nan, nan, nan, "missing"
    values, flags = [], set()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        flags.add("multi_max")
    for ln in lines:
        ln = ln.split(":")[-1].strip().replace(" ", "")  # Label 'K:' entfernen
        if ln.startswith("<"):
            flags.add("below_loq")
            ln = ln[1:]
        parts = re.split(r"[-–]", ln)
        nums = [float(p.replace(",", ".")) for p in parts
                if re.fullmatch(r"\d+(?:[.,]\d+)?", p)]
        if len(parts) > 1 and len(nums) > 1:
            flags.add("range_max")
        values.extend(nums)
    if not values:
        return nan, nan, nan, "missing"
    return max(values), min(values), max(values), "|".join(sorted(flags)) or "ok"


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    for c in LONG_COLS:
        if c not in df:
            df[c] = np.nan
    return df[LONG_COLS]


# --------------------------------------------------------------------------
# Quellen
# --------------------------------------------------------------------------
def load_michigan() -> pd.DataFrame:
    """Michigan, Einzelproben Blei an Entnahmestellen, 2016-2019 (APM Reports /
    EGLE-Daten per Open-Records-Anfrage). Rohdaten mit gemischten Einheiten
    (MG/L und UG/L) und abgelehnten Proben ('R')."""
    f = "mi_system_samples_2016-2019.csv"
    d = pd.read_csv(RAW / f, dtype=str)
    d = d.apply(lambda c: c.str.strip())
    d["src_row"] = np.arange(2, len(d) + 2)  # Zeilennummer in der Rohdatei

    v = pd.to_numeric(d["lead_level"], errors="coerce")
    factor = d["unit"].str.lower().map(UNIT_TO_MGL)
    value = v * factor

    flags = pd.Series("", index=d.index)

    def add(mask, label):
        nonlocal flags
        flags = flags.where(~mask, flags + label + ";")

    add(v.isna() | factor.isna(), "invalid_value")
    add(d["accepted_rejected"].eq("R"), "rejected_" + d["reject_reason"].fillna(""))
    dup = d.duplicated(["id", "lab_id", "collect_date", "lead_level", "unit"], keep="first")
    add(dup, "duplicate")
    add(value.eq(0), "nd_zero")  # 0 = nicht nachweisbar in den Rohdaten
    add(d["unit"].str.lower().eq("ug/l"), "unit_converted")
    # Konsistenz zur bereits standardisierten ppb-Spalte der Quelle
    ppb = pd.to_numeric(d["lead_level_ppb"], errors="coerce")
    add((value * 1000 - ppb).abs() > 0.01 * ppb.clip(lower=1), "ppb_mismatch")

    out = pd.DataFrame({
        "source": "Michigan EGLE / APM Reports",
        "src_file": f, "src_row": d["src_row"],
        "station_id": d["id"], "station": d["system_name"],
        "region": "Michigan (USA)",
        "sample_date": pd.to_datetime(d["collect_date"], errors="coerce"),
        "sample_type": d["first_or_fifth"].replace({"": "n/a"}),
        "parameter": "Blei",
        "value_raw": d["lead_level"] + " " + d["unit"],
        "value": value, "unit": "mg/L", "value_min": value, "value_max": value,
        "qc_flag": flags.str.rstrip(";").replace("", "ok"),
    })
    return _finish(out)


def load_heilbronn() -> pd.DataFrame:
    """Landkreis Heilbronn, Jahresmittelwerte je Ortsteil/Zone (2010-2015)."""
    f = "heilbronn_landkreis_2012-2015.csv"
    d = pd.read_csv(RAW / f, dtype=str)
    d["src_row"] = np.arange(2, len(d) + 2)
    for c in ("Stadt", "Ortsteil", "Zone"):
        d[c] = d[c].fillna("").str.strip()
    d["year"] = pd.to_numeric(d["Jahresmittelwerte"], errors="coerce")
    d["station"] = ("Heilbronn LK: " + d["Stadt"]
                    + np.where(d["Ortsteil"] != "", " / " + d["Ortsteil"], "")
                    + np.where(d["Zone"] != "", " (" + d["Zone"] + ")", ""))
    cols = {"Natrium": "natrium", "Kalium": "kalium", "Calcium": "calcium",
            "Magnesium": "magnesium", "Chlorid": "chlorid", "Nitrat": "nitrat",
            "Sulfat": "sulfat", "Härtegrad": "haerte"}
    parts = []
    for col, key in cols.items():
        parsed = d[col].map(parse_de_number)
        p, u = PARAM_MAP.get(key, ("Gesamthärte", "°dH"))
        parts.append(pd.DataFrame({
            "source": "Landkreis Heilbronn (Gemeinden/Stadtwerke)",
            "src_file": f, "src_row": d["src_row"],
            "station_id": "HN:" + d["station"].str.replace(r"\W+", "_", regex=True),
            "station": d["station"], "region": "Landkreis Heilbronn (DE)",
            "sample_date": pd.to_datetime(d["year"].astype("Int64").astype(str) + "-12-31",
                                          errors="coerce"),
            "sample_type": "Jahresmittel",
            "parameter": p, "value_raw": d[col],
            "value": [x[0] for x in parsed], "unit": u,
            "value_min": [x[1] for x in parsed], "value_max": [x[2] for x in parsed],
            "qc_flag": [x[3] for x in parsed],
        }))
    out = pd.concat(parts, ignore_index=True)
    # Straßenweise Wiederholungen derselben Zone sind dieselbe Messung
    key = ["station", "parameter", "sample_date", "value_raw"]
    dup = out.duplicated(key, keep="first")
    out.loc[dup, "qc_flag"] = (out.loc[dup, "qc_flag"].replace("ok", "") + ";duplicate").str.strip(";")
    return _finish(out)


def load_odrn() -> pd.DataFrame:
    """Rhein-Neckar-Region (Open Data Rhein-Neckar, Stand 17.08.2014)."""
    f = "odrn_rhein_neckar_2014.csv"
    d = pd.read_csv(RAW / f, header=1, dtype=str)
    d.columns = [re.sub(r"\s+", " ", c.replace("\n", " ")).strip() for c in d.columns]
    d["src_row"] = np.arange(3, len(d) + 3)
    d["Kommune"] = d["Kommune"].fillna("").str.strip()
    d = d[d["Kommune"] != ""].copy()
    sub = d["Sublevel Wasserwerk / Stadtteile"].fillna("").str.strip()
    d["station"] = "Rhein-Neckar: " + d["Kommune"] + np.where(sub != "", " / " + sub.str[:60], "")
    parts = []
    for col, key in [("Natrium", "natrium"), ("Kalium", "kalium"), ("Calcium", "calcium"),
                     ("Magnesium", "magnesium"), ("Chlorid", "chlorid"),
                     ("Nitrat", "nitrat"), ("Sulfat", "sulfat")]:
        parsed = d[col].map(parse_de_number)
        p, u = PARAM_MAP[key]
        parts.append(pd.DataFrame({
            "source": "Open Data Rhein-Neckar (2014)",
            "src_file": f, "src_row": d["src_row"],
            "station_id": "RN:" + d["station"].str.replace(r"\W+", "_", regex=True),
            "station": d["station"], "region": "Rhein-Neckar (DE)",
            "sample_date": pd.Timestamp("2014-08-17"),
            "sample_type": "Veröffentlichter Wert", "parameter": p,
            "value_raw": d[col], "value": [x[0] for x in parsed], "unit": u,
            "value_min": [x[1] for x in parsed], "value_max": [x[2] for x in parsed],
            "qc_flag": [x[3] for x in parsed],
        }))
    out = pd.concat(parts, ignore_index=True)
    out = out[out["qc_flag"] != "missing"]  # leere Zellen gehören nicht zur Messreihe
    return _finish(out)


def load_koeln() -> pd.DataFrame:
    """Köln (Rheinenergie), Jahreswerte 2022 und 2023, aus Veröffentlichungen
    der Trinkwasseranalysen (Werte aus Repo CodeforCologne/trinkwasser)."""
    f = "koeln_rheinenergie_2022_2023.csv"
    d = pd.read_csv(RAW / f)
    d["src_row"] = np.arange(2, len(d) + 2)
    parts = []
    for key, (p, u) in {**PARAM_MAP, "haerte_dh": ("Gesamthärte", "°dH")}.items():
        parts.append(pd.DataFrame({
            "source": "Rheinenergie Köln", "src_file": f, "src_row": d["src_row"],
            "station_id": "KOELN:" + d["station"].str.replace(r"\W+", "_", regex=True),
            "station": d["station"], "region": "Köln (DE)",
            "sample_date": pd.to_datetime(d["year"].astype(str) + "-12-31"),
            "sample_type": "Jahreswert", "parameter": p,
            "value_raw": d[key].astype(str), "value": d[key].astype(float), "unit": u,
            "value_min": d[key].astype(float), "value_max": d[key].astype(float),
            "qc_flag": "ok",
        }))
    return _finish(pd.concat(parts, ignore_index=True))


# --------------------------------------------------------------------------
# Plausibilisierung
# --------------------------------------------------------------------------
def plausibilize(df: pd.DataFrame, limits: pd.DataFrame) -> pd.DataFrame:
    """Setzt Plausibilitäts-Flags und `use_for_compliance`.

    Ausschluss (use_for_compliance=False): fehlender/ungültiger Wert, negativer
    Wert, physikalisch unplausibel (> plaus_max), abgelehnte Probe, Duplikat.
    Statistische Ausreißer werden nur markiert (`stat_outlier`), NICHT entfernt:
    Bei Schadstoffen sind extreme Werte oft genau das Signal.
    """
    df = df.copy()
    lim = limits.set_index("parameter")
    pmax = df["parameter"].map(lim["plaus_max"])
    flags = df["qc_flag"].where(df["qc_flag"] != "ok", "")

    def add(mask, label):
        nonlocal flags
        flags = flags.where(~mask, flags.str.cat([pd.Series(label, index=df.index)], sep=";")
                            .str.strip(";"))

    add(df["value"] < 0, "negative")
    add(df["value"] > pmax, "implausible_high")

    # Statistische Ausreißer: log10-IQR-Regel je Parameter auf positiven Werten
    stat = pd.Series(False, index=df.index)
    for p, g in df[df["value"] > 0].groupby("parameter"):
        lg = np.log10(g["value"])
        q1, q3 = lg.quantile([0.25, 0.75])
        stat.loc[g.index] = lg > q3 + 3 * (q3 - q1)
    add(stat, "stat_outlier")

    df["qc_flag"] = flags.replace("", "ok")
    bad = (df["value"].isna()
           | df["qc_flag"].str.contains(r"negative|implausible_high|rejected_|duplicate|invalid_value"))
    df["use_for_compliance"] = ~bad
    return df


def build_clean_table() -> pd.DataFrame:
    limits = pd.read_csv(ROOT / "data" / "limits.csv")
    raw = pd.concat([load_michigan(), load_heilbronn(), load_odrn(), load_koeln()],
                    ignore_index=True)
    clean = plausibilize(raw, limits)
    clean.insert(0, "measurement_id", np.arange(1, len(clean) + 1))
    return clean


if __name__ == "__main__":
    t = build_clean_table()
    print(t.groupby("source").size())
    print(t["qc_flag"].value_counts().head(15))
