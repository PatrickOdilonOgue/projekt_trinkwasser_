"""Matplotlib-Dashboard als Vorschau/Kontrolle für das Tableau-Dashboard."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

C = {"blue": "#1f5f8b", "red": "#c0392b", "grey": "#9aa5ad", "amber": "#e0a030"}


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)


def dashboard(rate, trend, top, path):
    fig, ax = plt.subplots(2, 2, figsize=(14, 9))
    r = rate.groupby("parameter").agg(n=("n_valid", "sum"), ex=("n_exceed", "sum"),
                                      mx=("max_utilisation_pct", "max")).reset_index()
    r["rate"] = 100 * r["ex"] / r["n"]
    r = r.sort_values(["rate", "mx"], ascending=True)

    a = ax[0, 0]
    a.barh(r["parameter"], r["rate"], color=[C["red"] if v > 0 else C["grey"] for v in r["rate"]])
    for i, v in enumerate(r["rate"]):
        a.text(v + 0.05, i, f"{v:.2f} %", va="center", fontsize=9)
    a.set_xlabel("Überschreitungsquote (% der gültigen Messwerte)")
    _style(a, "Überschreitungsquote je Parameter (TrinkwV 2023)")

    b = ax[0, 1]
    b.barh(r["parameter"], r["mx"], color=[C["red"] if v > 100 else C["amber"] if v >= 80
                                           else C["blue"] for v in r["mx"]])
    b.axvline(100, color="black", lw=1, ls="--"); b.axvline(80, color=C["amber"], lw=1, ls=":")
    b.set_xscale("log"); b.set_xlim(10, 30000)
    for v, t in zip(r["mx"], range(len(r))):
        b.text(v * 1.1, t, f"{v:,.0f} %".replace(",", "."), va="center", fontsize=9)
    b.set_xlabel("Maximale Grenzwertauslastung (%, logarithmisch; gestrichelt = 100 %)")
    _style(b, "Höchste Auslastung des Grenzwerts (Rangliste)")

    c = ax[1, 0]
    c.bar(trend["quarter"], trend["n_valid"], color="#dfe6ea", label="Anzahl gültiger Proben")
    c.set_ylabel("Proben"); c.tick_params(axis="x", rotation=60, labelsize=8)
    c2 = c.twinx()
    c2.plot(trend["quarter"], trend["exceed_rate_pct"], color=C["red"], marker="o", label="Quote")
    c2.set_ylabel("Überschreitungsquote Blei (%)", color=C["red"])
    c.spines[["top"]].set_visible(False)
    _style(c, "Trend: Blei-Überschreitungen je Quartal (Michigan)")

    d = ax[1, 1]
    t = top.head(12).iloc[::-1]
    d.barh(t["station"].str.slice(0, 34), t["n_exceed"], color=C["blue"])
    d.set_xlabel("Anzahl Überschreitungen")
    _style(d, "Messstellen mit den meisten Überschreitungen")
    fig.suptitle("Trinkwasserqualität – Grenzwert-Compliance (reale Daten)", fontsize=14,
                 fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def quality(dq, path):
    d = dq.set_index("source")
    cols = ["rows_used", "excl_rejected", "excl_duplicate", "excl_missing", "excl_implausible"]
    labels = ["verwendet", "abgelehnt (Probe)", "Duplikat", "fehlend", "unplausibel"]
    colors = [C["blue"], C["red"], C["grey"], C["amber"], "black"]
    fig, ax = plt.subplots(figsize=(11, 4))
    left = 0 * d["rows_raw"]
    share = d[cols].div(d["rows_raw"], axis=0) * 100
    for c, l, col in zip(cols, labels, colors):
        ax.barh(d.index.str.slice(0, 40), share[c], left=left, label=l, color=col)
        left = left + share[c]
    ax.set_xlabel("Anteil an Rohzeilen (%) – Kategorien können sich überlappen")
    ax.legend(ncol=5, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
