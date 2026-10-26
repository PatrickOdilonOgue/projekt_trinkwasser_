-- Abfragen gegen die SQLite-Datenbank data/processed/trinkwasser.db
-- Tabelle: evaluation (eine Zeile je Messwert inkl. Bewertung)
-- Format: "-- name: <abfrage>" leitet jeweils eine Abfrage ein.

-- name: timeseries_monthly
-- Zeitreihe je Messstelle und Parameter (Monatsaggregat)
SELECT station_id, station, parameter,
       strftime('%Y-%m', sample_date)            AS month,
       COUNT(*)                                  AS n_samples,
       ROUND(AVG(value), 5)                      AS mean_value,
       MAX(value)                                AS max_value,
       SUM(status = 'Überschreitung')            AS n_exceed
FROM evaluation
WHERE use_for_compliance = 1 AND sample_date IS NOT NULL
GROUP BY station_id, station, parameter, month
ORDER BY station_id, parameter, month;

-- name: exceedance_rate_parameter
-- Überschreitungsquote und maximale Grenzwertauslastung je Parameter und Quelle
SELECT parameter, source,
       COUNT(*)                                                    AS n_valid,
       SUM(status = 'Überschreitung')                              AS n_exceed,
       ROUND(100.0 * SUM(status = 'Überschreitung') / COUNT(*), 2) AS exceed_rate_pct,
       SUM(status LIKE 'Vorwarn%')                                 AS n_warn,
       ROUND(100.0 * MAX(ratio_trinkwv), 1)                        AS max_utilisation_pct
FROM evaluation
WHERE use_for_compliance = 1 AND limit_trinkwv IS NOT NULL
GROUP BY parameter, source
ORDER BY exceed_rate_pct DESC, max_utilisation_pct DESC;

-- name: ranking_critical_parameters
-- Rangliste der kritischen Parameter (Quote, dann höchste Auslastung)
WITH p AS (
  SELECT parameter,
         COUNT(*) AS n_valid,
         SUM(status = 'Überschreitung') AS n_exceed,
         100.0 * SUM(status = 'Überschreitung') / COUNT(*) AS exceed_rate_pct,
         100.0 * MAX(ratio_trinkwv) AS max_utilisation_pct
  FROM evaluation
  WHERE use_for_compliance = 1 AND limit_trinkwv IS NOT NULL
  GROUP BY parameter)
SELECT RANK() OVER (ORDER BY exceed_rate_pct DESC, max_utilisation_pct DESC) AS rang,
       parameter, n_valid, n_exceed,
       ROUND(exceed_rate_pct, 2) AS exceed_rate_pct,
       ROUND(max_utilisation_pct, 1) AS max_utilisation_pct
FROM p ORDER BY rang;

-- name: top_stations
-- Messstellen mit den meisten Überschreitungen
SELECT station_id, station, source,
       COUNT(*)                        AS n_valid,
       SUM(status = 'Überschreitung')  AS n_exceed,
       ROUND(100.0 * SUM(status = 'Überschreitung') / COUNT(*), 1) AS exceed_rate_pct,
       ROUND(MAX(value), 4)            AS max_value,
       MIN(sample_date)                AS first_date,
       MAX(sample_date)                AS last_date
FROM evaluation
WHERE use_for_compliance = 1 AND limit_trinkwv IS NOT NULL
GROUP BY station_id, station, source
HAVING n_exceed > 0
ORDER BY n_exceed DESC, max_value DESC
LIMIT 15;

-- name: trend_quarterly_lead
-- Trend der Bleiüberschreitungen je Quartal
SELECT strftime('%Y', sample_date) || '-Q' ||
       ((CAST(strftime('%m', sample_date) AS INTEGER) + 2) / 3) AS quarter,
       COUNT(*)                                                    AS n_valid,
       SUM(status = 'Überschreitung')                              AS n_exceed,
       ROUND(100.0 * SUM(status = 'Überschreitung') / COUNT(*), 2) AS exceed_rate_pct
FROM evaluation
WHERE parameter = 'Blei' AND use_for_compliance = 1
GROUP BY quarter ORDER BY quarter;

-- name: p90_lead_system_year
-- 90. Perzentil Blei je Wasserversorger und Jahr (Nearest-Rank, n >= 5),
-- zum Vergleich mit dem US-EPA-Action-Level von 15 µg/L (Kontext)
WITH r AS (
  SELECT station_id, station, strftime('%Y', sample_date) AS year, value,
         ROW_NUMBER() OVER (PARTITION BY station_id, strftime('%Y', sample_date) ORDER BY value) AS rn,
         COUNT(*)     OVER (PARTITION BY station_id, strftime('%Y', sample_date)) AS n
  FROM evaluation
  WHERE parameter = 'Blei' AND use_for_compliance = 1)
SELECT station_id, station, year, n,
       ROUND(value * 1000, 1)                AS p90_ug_l,
       CASE WHEN value * 1000 > 15 THEN 1 ELSE 0 END AS above_epa_action_level
FROM r
WHERE n >= 5 AND rn = CAST(0.9 * n + 0.999999 AS INTEGER)
ORDER BY p90_ug_l DESC;
