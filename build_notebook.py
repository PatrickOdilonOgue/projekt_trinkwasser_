import nbformat as nbf
nb = nbf.v4.new_notebook()
M = lambda t: nbf.v4.new_markdown_cell(t)
C = lambda t: nbf.v4.new_code_cell(t)
nb.cells = [
M("""# Trinkwasserqualität: Analyse und Grenzwert-Compliance
**Prüfbericht (reproduzierbar)** – Reihenfolge: Daten → Qualitätssicherung → Compliance-Logik → SQL-Auswertung → Befunde.

**Datenquellen (alle real und öffentlich):**
1. Michigan, Einzelproben Blei 2016–2019 (APM Reports, Open-Records-Daten, GitHub `APM-Reports/lead-data-analysis`)
2. Landkreis Heilbronn, Jahresmittelwerte je Ortsteil (GitHub `CodeforCologne/trinkwasser`)
3. Open Data Rhein-Neckar, Stand 2014 (ebenfalls in diesem Repo)
4. Rheinenergie Köln, Jahreswerte 2022/2023 (aus den veröffentlichten Trinkwasseranalysen)

**Grenzwerte:** TrinkwV 2023 (Anlage 2/3) und WHO, siehe `data/limits.csv`."""),
C("""import sys, pandas as pd
sys.path.insert(0, '../src')
import etl, compliance, db
pd.set_option('display.width', 160); pd.set_option('display.max_columns', 30)
limits = pd.read_csv('../data/limits.csv')
limits[['parameter','unit','limit_trinkwv','trinkwv_ref','limit_who','who_type']]"""),
M("## 1 · ETL und Qualitätssicherung\nEinheiten werden auf mg/L vereinheitlicht (Michigan liefert MG/L und UG/L gemischt), Bereiche und Mehrfachwerte aus Webtabellen werden konservativ mit dem **Maximum** übernommen, abgelehnte Proben, Duplikate und fehlende Werte werden aus der Prüfung ausgeschlossen – aber nicht gelöscht, sondern über `qc_flag` dokumentiert."),
C("""clean = etl.build_clean_table()
dq = compliance.data_quality_report(clean)
dq.set_index('source').T"""),
C("""clean['qc_flag'].str.split(';').explode().value_counts().to_frame('Anzahl')"""),
M("**Ausreißer:** Statistische Ausreißer (log-IQR-Regel) werden nur *markiert*. Bei Bleiproben sind hohe Werte das eigentliche Signal und keine Messfehler; sie bleiben in der Compliance-Prüfung. Entfernt werden nur physikalisch Unmögliches (negativ, über `plaus_max`) und formal ungültige Proben."),
C("""clean[clean.qc_flag.str.contains('stat_outlier')].groupby('parameter')['value'].describe()[['count','min','50%','max']]"""),
M("## 2 · Compliance-Logik\nJeder gültige Wert wird gegen TrinkwV und WHO geprüft. `Überschreitung` = Wert > Grenzwert, `Vorwarnbereich` = ≥ 80 % des Grenzwerts. Parameter ohne Grenzwert (Kalium, Calcium, Magnesium, Härte) werden mitgeführt, aber nicht bewertet."),
C("""ev = compliance.evaluate(clean, limits)
ev[ev.use_for_compliance].groupby(['parameter','status']).size().unstack(fill_value=0)"""),
C("""log = compliance.exceedance_log(ev)
print(len(log), 'Überschreitungen im Protokoll')
log[['station','sample_date','value','ratio_trinkwv','severity','datenherkunft']].head(8)"""),
C("""print(log.loc[0, 'begruendung']); print(log.loc[0, 'bewertungshinweis'])"""),
M("## 3 · SQL-Auswertung\nDie bewertete Tabelle liegt in SQLite; die Abfragen stehen in `sql/queries.sql`."),
C("""limits = pd.read_csv('../data/limits.csv')
db.build_db(ev, limits)
sorted(db.load_queries())"""),
C("""db.run('ranking_critical_parameters')"""),
C("""db.run('exceedance_rate_parameter')"""),
C("""db.run('timeseries_monthly').query("parameter=='Blei'").sort_values('n_samples', ascending=False).head(10)"""),
C("""db.run('trend_quarterly_lead')"""),
C("""db.run('top_stations').head(10)"""),
C("""p90 = db.run('p90_lead_system_year'); print(len(p90), 'System-Jahre mit n>=5; davon über 15 µg/L:', int(p90.above_epa_action_level.sum())); p90.head(8)"""),
M("## 4 · Dashboard-Vorschau (Python)\nDas Tableau-Dashboard nutzt dieselben Daten aus `tableau/`; diese Grafik dient als Kontrollansicht."),
C("""from IPython.display import Image
Image('../reports/figures/dashboard_preview.png')"""),
C("""Image('../reports/figures/data_quality.png')"""),
M("""## 5 · Befunde und Grenzen
* **Blei ist der einzige Parameter mit Überschreitungen:** rund 3,4 % der gültigen Michigan-Proben liegen über 10 µg/L, einzelne Proben bis zum ~114-Fachen des Grenzwerts.
* **Nitrat, Sulfat, Natrium, Chlorid** halten in den deutschen Daten den Grenzwert ein. Nitrat erreicht in einem Rhein-Neckar-Eintrag exakt 100 % des Grenzwerts (50 mg/L, nicht überschritten), Sulfat 98,8 %: das sind die Kandidaten für eine Beobachtung.
* **Trend:** Die Quote steigt von 2016 bis 2019 von ca. 2 % auf ca. 5 %. Achtung, das ist *kein* belastbarer Trend: Anzahl und Auswahl der Proben ändern sich stark von Quartal zu Quartal (siehe Balken).
* **Nicht vergleichbar:** Die US-Proben sind Einzelproben nach Lead-and-Copper-Rule-Protokoll (Stagnation, Risikohaushalte), die deutschen Werte sind veröffentlichte Jahresmittel. Eine Überschreitung in den US-Daten ist deshalb *kein* TrinkwV-Verstoß, sondern ein Zahlenvergleich gegen den Grenzwert.
* **Bereiche** wurden mit dem Maximum angesetzt (konservativ), `Nicht nachweisbar` bei Blei als 0 behandelt.
* Chlorid fehlt in vielen Heilbronner Datensätzen; die WHO-Werte für Natrium, Chlorid und Sulfat sind Geschmacksschwellen, keine Gesundheitswerte."""),
]
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, "notebooks/01_pruefbericht_trinkwasser.ipynb")
