"""Fits the calibrated resolver on development data and reports how it behaves there.

Model: a conditional logit with an outside option. For an input with candidates c_1..c_k,
    score(c_i) = w . x_i          score(none) = v . g
    P(answer = c_i) = softmax(scores)_i,   P(none of them) = softmax(scores)_{k+1}
fitted by maximum likelihood (L-BFGS, small L2 penalty) on company addresses, then calibrated
with one temperature on the care-office calibration half. Two versions are fitted: one that sees
only the address ("address"), and one that may also use the organisation's name ("address+name").

From the calibration half it also chooses
  - the answer threshold: the lowest probability tau such that, for every input type, the 95%
    Clopper-Pearson upper bound of the wrong-answer rate among answers with p >= tau is at most
    the target (1%): selective classification with a guaranteed risk (Geifman and El-Yaniv 2017);
  - split-conformal quantiles per input type for candidate sets that hold the right answer (or
    'none of these' when it is none) with probability at least 95% (Vovk et al.; Angelopoulos and
    Bates 2021).

Usage:
    python benchmarks/calibration/train.py            # writes data/model.json and data/dev_report.md
"""

import gzip
import json
import math
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize
from scipy.stats import beta

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from candidates import FEATURES, NONE_FEATURES  # noqa: E402

DATA = HERE / "data"
NAME_COLUMNS = [FEATURES.index("name_mentions_muni"), FEATURES.index("name_mentions_pref")]
VARIANTS = ("town only", "with prefecture", "full")
TARGET_RISK = 0.01
ALPHA = 0.05
L2 = 1e-3


def load(name: str) -> List[Dict[str, Any]]:
    with gzip.open(DATA / f"{name}.pkl.gz", "rb") as fh:
        return pickle.load(fh)


class Packed:
    """Items as flat arrays: candidate rows X with group ids, and one 'none' row per item."""

    def __init__(self, items: Sequence[Dict[str, Any]], use_name: bool) -> None:
        self.n = len(items)
        sizes = np.array([len(it["x"]) for it in items], dtype=np.int64)
        self.sizes = sizes
        self.offsets = np.concatenate([[0], np.cumsum(sizes)])
        rows = [r for it in items for r in it["x"]]
        self.X = np.array(rows, dtype=np.float64).reshape(-1, len(FEATURES))
        if not use_name:
            self.X[:, NAME_COLUMNS] = 0.0
        self.G = np.array([it["g"] for it in items], dtype=np.float64)
        self.group = np.repeat(np.arange(self.n), sizes)
        self.label = np.array([it["label"] for it in items], dtype=np.int64)
        self.is_none = self.label >= sizes
        # position of the right candidate in X (or -1 when the answer is 'none')
        self.label_row = np.where(self.is_none, -1, self.offsets[:-1] + np.minimum(self.label, np.maximum(sizes - 1, 0)))

    def scores(self, theta: np.ndarray, temperature: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        w, v = theta[:len(FEATURES)], theta[len(FEATURES):]
        return self.X @ w / temperature, self.G @ v / temperature

    def log_norm(self, s: np.ndarray, s_none: np.ndarray) -> np.ndarray:
        m = s_none.copy()
        np.maximum.at(m, self.group, s)
        z = np.exp(s_none - m)
        np.add.at(z, self.group, np.exp(s - m[self.group]))
        return m + np.log(z)

    def probs(self, theta: np.ndarray, temperature: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        s, s_none = self.scores(theta, temperature)
        lz = self.log_norm(s, s_none)
        return np.exp(s - lz[self.group]), np.exp(s_none - lz)


def nll_and_grad(theta: np.ndarray, data: Packed) -> Tuple[float, np.ndarray]:
    s, s_none = data.scores(theta)
    lz = data.log_norm(s, s_none)
    p = np.exp(s - lz[data.group])
    p_none = np.exp(s_none - lz)
    picked = np.where(data.is_none, s_none, s[np.maximum(data.label_row, 0)])
    loss = float(np.sum(lz - picked)) / data.n
    # gradient: expected features minus observed
    gw = data.X.T @ p
    gv = data.G.T @ p_none
    obs_w = data.X[data.label_row[~data.is_none]].sum(axis=0)
    obs_v = data.G[data.is_none].sum(axis=0)
    grad = np.concatenate([gw - obs_w, gv - obs_v]) / data.n
    loss += L2 * float(theta @ theta)
    grad += 2 * L2 * theta
    return loss, grad


def fit(data: Packed) -> np.ndarray:
    theta0 = np.zeros(len(FEATURES) + len(NONE_FEATURES))
    res = minimize(nll_and_grad, theta0, args=(data,), jac=True, method="L-BFGS-B", options={"maxiter": 500})
    return res.x


def fit_temperature(theta: np.ndarray, data: Packed) -> float:
    def nll(t: float) -> float:
        s, s_none = data.scores(theta, t)
        lz = data.log_norm(s, s_none)
        picked = np.where(data.is_none, s_none, s[np.maximum(data.label_row, 0)])
        return float(np.mean(lz - picked))
    grid = np.exp(np.linspace(math.log(0.25), math.log(4), 81))
    return float(min(grid, key=nll))


def top_answers(data: Packed, theta: np.ndarray, temperature: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each input: probability of its best candidate, whether that candidate is right, and P(none)."""
    p, p_none = data.probs(theta, temperature)
    best_p = np.zeros(data.n)
    best_row = np.full(data.n, -1)
    for i in range(data.n):  # small loops are fine at this size
        a, b = data.offsets[i], data.offsets[i + 1]
        if b > a:
            j = a + int(np.argmax(p[a:b]))
            best_p[i], best_row[i] = p[j], j
    right = (best_row >= 0) & (best_row == data.label_row)
    return best_p, right, p_none


def clopper_upper(k: int, n: int, conf: float = 0.95) -> float:
    return 1.0 if n == 0 else float(beta.ppf(conf, k + 1, n - k)) if k < n else 1.0


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def ece(prob: np.ndarray, right: np.ndarray, bins: int = 15) -> float:
    """Expected calibration error with equal-mass bins over the answered inputs."""
    if len(prob) == 0:
        return float("nan")
    order = np.argsort(prob)
    total = 0.0
    for chunk in np.array_split(order, bins):
        if len(chunk):
            total += len(chunk) * abs(prob[chunk].mean() - right[chunk].mean())
    return total / len(prob)


def risk_coverage(prob: np.ndarray, right: np.ndarray, answerable: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    """Coverage and risk when answering the k most confident inputs, k = 1..n; and the area under it."""
    n = len(prob)
    order = np.argsort(-np.where(answerable, prob, -1.0))
    wrong = np.cumsum(~right[order] & answerable[order])
    answered = np.cumsum(answerable[order])
    coverage = answered / n
    risk = np.where(answered > 0, wrong / np.maximum(answered, 1), 0.0)
    aurc = float(np.mean(risk[answerable[order]])) if answerable.any() else float("nan")
    return coverage, risk, aurc


def choose_threshold(per_variant: Dict[str, Tuple[np.ndarray, np.ndarray]], target: float) -> float:
    grid = np.unique(np.concatenate([p for p, _ in per_variant.values()]))
    for tau in grid:
        ok = True
        for p, right in per_variant.values():
            sel = p >= tau
            k, n = int((~right[sel]).sum()), int(sel.sum())
            if n and clopper_upper(k, n) > target:
                ok = False
                break
        if ok:
            return float(tau)
    return 1.0


def conformal_quantile(data: Packed, theta: np.ndarray, temperature: float, mask: np.ndarray, alpha: float) -> float:
    p, p_none = data.probs(theta, temperature)
    p_label = np.where(data.is_none, p_none, p[np.maximum(data.label_row, 0)])
    scores = np.sort(1.0 - p_label[mask])
    n = len(scores)
    k = min(n - 1, int(math.ceil((n + 1) * (1 - alpha))) - 1)
    return float(scores[k])


def conformal_sets(data: Packed, theta: np.ndarray, temperature: float, qhat: float, mask: np.ndarray) -> Tuple[float, float]:
    p, p_none = data.probs(theta, temperature)
    covered = sizes = 0
    idx = np.nonzero(mask)[0]
    for i in idx:
        a, b = data.offsets[i], data.offsets[i + 1]
        members = [j for j in range(a, b) if 1 - p[j] <= qhat]
        none_in = 1 - p_none[i] <= qhat
        sizes += len(members) + int(none_in)
        covered += int((data.label_row[i] in members) if not data.is_none[i] else none_in)
    return covered / max(1, len(idx)), sizes / max(1, len(idx))


def main() -> int:
    train, calib, devcheck = load("train"), load("calib"), load("devcheck")
    print(f"train {len(train):,}  calib {len(calib):,}  devcheck {len(devcheck):,}", file=sys.stderr)
    model: Dict[str, Any] = {"features": FEATURES, "none_features": NONE_FEATURES, "target_risk": TARGET_RISK,
                             "alpha": ALPHA, "models": {}}
    lines = ["# Calibrated resolver: development results", "",
             "Fitted on company addresses, calibrated on half the care offices, checked on the other half. "
             "No held-out test data is used here.", ""]
    for name, use_name in (("address", False), ("address+name", True)):
        tr = Packed(train, use_name)
        theta = fit(tr)
        ca = Packed(calib, use_name)
        temperature = fit_temperature(theta, ca)
        variants = np.array([it["variant"] for it in calib])
        best_p, right, _ = top_answers(ca, theta, temperature)
        per_variant = {v: (best_p[variants == v], right[variants == v]) for v in VARIANTS}
        tau = choose_threshold(per_variant, TARGET_RISK)
        qhat = {v: conformal_quantile(ca, theta, temperature, variants == v, ALPHA) for v in VARIANTS}
        model["models"][name] = {"w": theta[:len(FEATURES)].tolist(), "v": theta[len(FEATURES):].tolist(),
                                 "temperature": temperature, "threshold": tau, "conformal_qhat": qhat}
        lines += [f"## {name}", "", f"Temperature {temperature:.3f}; answer threshold {tau:.4f} (1% target); "
                  "weights: " + ", ".join(f"{f} {x:+.2f}" for f, x in zip(FEATURES + NONE_FEATURES, theta)), ""]
        lines.append("| Set | Input | Inputs | Rules: right / wrong / no answer | Calibrated at threshold: right / wrong (95% CI) / answered | AURC | ECE | Conformal 95%: coverage / mean size |")
        lines.append("| :--- | :--- | ---: | :--- | :--- | ---: | ---: | :--- |")
        for set_name, items in (("calib", calib), ("devcheck", devcheck)):
            d = ca if set_name == "calib" else Packed(items, use_name)
            vs = np.array([it["variant"] for it in items])
            bp, rt, _ = top_answers(d, theta, temperature)
            rules_acc = np.array([it["status"] == "ACCEPTED" for it in items])
            for v in VARIANTS:
                m = vs == v
                n = int(m.sum())
                rr = int((rules_acc & rt & m).sum())
                rw = int((rules_acc & ~rt & m).sum())
                sel = m & (bp >= tau)
                k_wrong = int((~rt & sel).sum())
                lo, hi = wilson(k_wrong, int(sel.sum()))
                cov, risk, aurc = risk_coverage(bp[m], rt[m], d.sizes[m] > 0)
                cc, cs = conformal_sets(d, theta, temperature, qhat[v], m)
                lines.append(f"| {set_name} | {v} | {n:,} | {rr / n:.2%} / {rw:,} / {(n - rr - rw) / n:.2%} | "
                             f"{int((rt & sel).sum()) / n:.2%} / {k_wrong:,} ({lo:.2%}–{hi:.2%}) / {sel.sum() / n:.2%} | "
                             f"{aurc:.4f} | {ece(bp[m & (d.sizes > 0)], rt[m & (d.sizes > 0)]):.4f} | {cc:.2%} / {cs:.2f} |")
        lines.append("")
    (DATA / "model.json").write_text(json.dumps(model, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATA / "dev_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
