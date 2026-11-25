"""Offline tests for the M4 clustering, on synthetic prescribers with 7 obvious prescribing styles."""

import numpy as np
import pandas as pd

from obesity_ci.segment import clusters as C


def synthetic(n_per=60, seed=1):
    """n_per prescribers per style: ~70% of claims in one class, the rest spread with noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for i, main in enumerate(C.FEATURES):
        for j in range(n_per):
            w = rng.dirichlet(np.ones(len(C.FEATURES))) * 0.3
            w[i] += 0.7
            rows.append({"npi": f"{i}-{j}", "eligible": True, **dict(zip(C.FEATURES, w))})
    rows.append({"npi": "small", "eligible": False, **dict.fromkeys(C.FEATURES, 1 / 7)})
    return pd.DataFrame(rows)


def test_each_style_found_and_named():
    seg, model, X = C.assign(synthetic())
    seg = seg.set_index("npi")
    for i, feat in enumerate(C.FEATURES):
        names = seg.loc[[f"{i}-{j}" for j in range(60)], "cluster"]
        assert (names == C.NAMES[feat]).all(), feat
    assert seg.loc["small", "cluster"] == C.LOW_VOLUME


def test_stable_on_clear_structure():
    X = C.matrix(synthetic())
    assert np.mean(C.stability(X, n_boot=3)) > 0.95
    assert C.silhouette(X, C.fit(X).labels_) > 0.3


def test_duplicate_names_are_numbered():
    X = C.matrix(synthetic(n_per=40))
    names = C.name_clusters(C.fit(X, k=9))  # more clusters than styles -> some share a top feature
    assert len(set(names.values())) == 9 and any(n.endswith("(2)") for n in names.values())


def test_scan_reports_each_k():
    X = C.matrix(synthetic(n_per=20))
    s = C.scan(X, ks=[3, 7], n_boot=1)
    assert list(s["k"]) == [3, 7] and s.loc[s["k"] == 7, "silhouette"].iloc[0] > s.loc[s["k"] == 3, "silhouette"].iloc[0]
