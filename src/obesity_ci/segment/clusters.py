"""Behavioural clusters (M4, chunk 4): k-means on WHAT prescribers write, not how much.

Features: the 7 class-mix shares from chunk 2 (legacy oral, DPP-4, SGLT2, injectable GLP-1,
oral GLP-1, GIP/GLP-1, insulin), standardised. Volume is left out on purpose: the baseline
grid already ranks by volume, so the clusters answer a different question ("what kind of
prescriber is this?") and are crossed with value in chunk 5.

k = 7 (see docs/M4_DECISIONS.md): stable across bootstrap samples (adjusted Rand index ~0.98)
and every cluster has a clear prescribing story. k = 6 separates slightly better (silhouette
0.275 vs 0.266) but merges Ozempic/Trulicity-led and Mounjaro-led prescribers, which is the
split a Lilly launch cares about.

Each cluster is named after the feature where its centre is highest relative to the
others (z-score), so names don't depend on k-means' arbitrary label numbers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from obesity_ci import config

FEATURES = ["share_legacy_oral", "share_dpp4", "share_sglt2", "share_glp1_injectable", "share_glp1_oral",
            "share_gip_glp1", "share_insulin"]
NAMES = {
    "share_legacy_oral": "Generic-first (metformin / sulfonylurea)",
    "share_dpp4": "DPP-4 loyal",
    "share_sglt2": "SGLT2 cardiorenal",
    "share_glp1_injectable": "Injectable GLP-1 adopters (Ozempic / Trulicity)",
    "share_glp1_oral": "Oral GLP-1 users (Rybelsus)",
    "share_gip_glp1": "Tirzepatide-led (Mounjaro)",
    "share_insulin": "Insulin-intensive",
}
K = 7
SEED = 0
LOW_VOLUME = "Low volume (not profiled)"


def matrix(eligible: pd.DataFrame) -> np.ndarray:
    return StandardScaler().fit_transform(eligible[FEATURES].to_numpy(dtype=float))


def fit(X: np.ndarray, k: int = K, seed: int = SEED) -> KMeans:
    return KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X)


def name_clusters(model: KMeans) -> dict[int, str]:
    """Label -> name from each centre's most distinctive feature; duplicates get a number."""
    centres = pd.DataFrame(model.cluster_centers_, columns=FEATURES)
    names, seen = {}, {}
    for label, row in centres.iterrows():
        base = NAMES[row.idxmax()]
        seen[base] = seen.get(base, 0) + 1
        names[label] = base if seen[base] == 1 else f"{base} ({seen[base]})"
    return names


def stability(X: np.ndarray, k: int = K, n_boot: int = 5, seed: int = SEED) -> list[float]:
    """Refit on bootstrap samples with new seeds; adjusted Rand index vs the reference fit
    (1 = identical grouping, 0 = chance). Exit criterion: mean >= 0.8."""
    ref = fit(X, k, seed).labels_
    rng = np.random.default_rng(seed)
    scores = []
    for b in range(1, n_boot + 1):
        idx = rng.choice(len(X), len(X), replace=True)
        scores.append(adjusted_rand_score(ref, fit(X[idx], k, seed + b).predict(X)))
    return scores


def silhouette(X: np.ndarray, labels: np.ndarray, sample: int = 20000, seed: int = SEED) -> float:
    """Silhouette on a random sample (the full computation is quadratic in rows)."""
    idx = np.random.default_rng(seed).choice(len(X), min(sample, len(X)), replace=False)
    return float(silhouette_score(X[idx], labels[idx]))


def scan(X: np.ndarray, ks=range(3, 11), n_boot: int = 3) -> pd.DataFrame:
    rows = []
    for k in ks:
        m = fit(X, k)
        s = stability(X, k, n_boot)
        rows.append({"k": k, "silhouette": round(silhouette(X, m.labels_), 3),
                     "stability_mean_ari": round(float(np.mean(s)), 3), "stability_min_ari": round(min(s), 3),
                     "smallest_cluster": int(np.bincount(m.labels_).min())})
    return pd.DataFrame(rows)


def assign(prescribers: pd.DataFrame, k: int = K) -> tuple[pd.DataFrame, KMeans, np.ndarray]:
    f = prescribers.copy()
    elig = f["eligible"].to_numpy()
    X = matrix(f[elig])
    model = fit(X, k)
    names = name_clusters(model)
    f["cluster"] = LOW_VOLUME
    f.loc[elig, "cluster"] = [names[label] for label in model.labels_]
    return f, model, X


def run(snapshot: str | None = None, do_scan: bool = False, n_boot: int = 5) -> dict:
    from obesity_ci.segment import baseline

    b = baseline.run(snapshot)
    seg, model, X = assign(b["segments"])
    e = seg[seg["eligible"]]
    result = {
        "snapshot": b["snapshot"], "data_year": b["data_year"], "out": b["out"], "segments": seg,
        "silhouette": silhouette(X, model.labels_),
        "stability": stability(X, K, n_boot),
        "ari_vs_baseline": adjusted_rand_score(e["baseline_segment"], e["cluster"]),
        "by_cluster": baseline.profile(seg, "cluster"),
        "scan": scan(X) if do_scan else None,
    }
    seg[["npi", "cluster"]].to_parquet(b["out"] / "clusters.parquet", index=False)
    result["by_cluster"].to_csv(b["out"] / "cluster_profile.csv")
    return result
