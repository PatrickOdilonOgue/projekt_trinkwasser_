# Trinkwasserqualität: Analyse und Grenzwert-Compliance

Analysepipeline für Trinkwasser-Messwerte: Rohdaten einlesen, plausibilisieren, gegen TrinkwV 2023 und WHO prüfen und jede Überschreitung bis zur Rohdatei-Zeile nachvollziehbar dokumentieren. Dazu SQL-Zeitreihen und Tableau-Exporte.

**Stack:** Python · pandas · SQL (SQLite) · Tableau · Jupyter

## Ergebnisse (reale Daten)
* 39.387 Messwerte aus 4 öffentlichen Quellen, davon 32.910 gültig für die Prüfung.
* **Blei**: 1.059 von 30.946 gültigen Michigan-Proben (3,4 %) über 10 µg/L, Maximum ≈ 114 × Grenzwert.
* **Nitrat, Sulfat, Natrium, Chlorid** (Heilbronn, Rhein-Neckar, Köln): keine Überschreitung; höchste Auslastung Nitrat 100 % und Sulfat 98,8 % des Grenzwerts.
* Details und Einschränkungen: `reports/pruefbericht_trinkwasser.html` bzw. Notebook.

## Struktur
```
data/raw/            Rohdaten (unverändert aus den Quellen)
data/limits.csv      Grenzwerte TrinkwV 2023 / WHO inkl. Rechtsgrundlage
src/etl.py           Einlesen, Einheiten, Bereiche/Mehrfachwerte, Plausibilität
src/compliance.py    Prüflogik, Überschreitungsprotokoll, Datenqualitätsbericht
src/db.py            SQLite-Aufbau, benannte SQL-Abfragen
sql/queries.sql      Zeitreihen, Quoten, Rangliste, 90. Perzentil (Fensterfunktionen)
src/run_pipeline.py  Gesamtlauf
notebooks/           Prüfbericht als reproduzierbares Notebook (ausgeführt)
tableau/             CSV-Exporte + Anleitung für das Dashboard
reports/             HTML-Bericht, Dashboard-Vorschau
```

## Reproduzieren
```bash
pip install -r requirements.txt
python src/run_pipeline.py
jupyter nbconvert --to notebook --execute --inplace notebooks/01_pruefbericht_trinkwasser.ipynb
```

## Datenquellen und Lizenz-Hinweis
| Quelle | Inhalt |
|---|---|
| github.com/APM-Reports/lead-data-analysis | Michigan, Einzelproben Blei 2016–2019 |
| github.com/CodeforCologne/trinkwasser (Ordner `converter`, `src/data`) | Landkreis Heilbronn, Open Data Rhein-Neckar, Köln |

Die Rohdaten gehören den jeweiligen Herausgebern; vor einer Veröffentlichung Lizenzen der Repos prüfen (das Köln/Heilbronn-Repo nennt für Teile der Daten ausdrücklich eine abweichende Lizenz).

## Methodische Grenzen
* US-Proben (Lead-and-Copper-Rule) und deutsche Veröffentlichungswerte sind nicht gleichartig; US-„Überschreitungen“ sind kein formaler TrinkwV-Verstoß.
* Zeitreihen gibt es nur für Michigan (Blei); deutsche Quellen sind Jahres-/Stichtagswerte.
* Bereichsangaben → Maximum (konservativ); „nicht nachweisbar“ → 0.
* WHO-Werte für Na/Cl/SO₄ sind Geschmacksschwellen, kein Gesundheitswert; vor Veröffentlichung gegen die aktuelle WHO-Ausgabe prüfen.
