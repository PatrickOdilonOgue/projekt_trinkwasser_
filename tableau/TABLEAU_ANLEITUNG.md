# Tableau-Dashboard: Aufbau in ~20 Minuten

Das Tableau-Workbook (.twbx) lässt sich nicht automatisch erzeugen; alle Daten und Kennzahlen liegen aber fertig vor.
Kontrollansicht zum Nachbauen: `reports/figures/dashboard_preview.png`.

## Datenquellen (Text-Dateien, UTF-8, Trennzeichen Komma)
| Datei | Zweck |
|---|---|
| `tableau_measurements.csv` | Faktentabelle, 1 Zeile je Messwert (Filter `use_for_compliance = True`) |
| `tableau_kpi_parameter.csv` | Quote und Auslastung je Parameter und Quelle |
| `tableau_trend_quarterly_lead.csv` | Quartalstrend Blei |
| `tableau_top_stations.csv` | Messstellen mit den meisten Überschreitungen |
| `tableau_ranking_parameters.csv` | Rangliste der kritischen Parameter |
| `tableau_exceedances.csv` | Protokoll aller Überschreitungen (Tooltip/Detailtabelle) |

## Berechnete Felder (auf `tableau_measurements`)
```
Gültig            = [Use For Compliance] = TRUE
Überschreitung    = IF [Status] = 'Überschreitung' THEN 1 ELSE 0 END
Überschreitungsquote = SUM([Überschreitung]) / COUNT([Measurement Id])   // mit Filter Gültig
Auslastung %      = MAX([Ratio Trinkwv]) * 100
```

## Blätter
1. **Überschreitungsquote** – Balken: Parameter × Überschreitungsquote, Farbe rot bei > 0.
2. **Trend** – Linie: Quartal (`Quarter`) × Überschreitungsquote, Filter Parameter = Blei; zusätzlich Balken `COUNT(Measurement Id)` als Doppelachse, damit Stichprobengröße sichtbar bleibt.
3. **Rangliste** – Balken: Parameter nach Auslastung % (absteigend), Referenzlinie bei 100 und 80 %; logarithmische Achse, weil Blei sonst alles überdeckt.
4. **Messstellen** – Top 15 aus `tableau_top_stations.csv`.

## Dashboard-Layout
Oben KPI-Kacheln (Anzahl gültiger Messwerte, Überschreitungen, Quote), links Blatt 1 + 3, rechts Blatt 2 + 4.
Filter: Quelle, Region, Parameter, Jahr. Hinweis-Textfeld: *„US-Einzelproben (LCR-Protokoll) sind nicht mit TrinkwV-Probenahme vergleichbar.“*
