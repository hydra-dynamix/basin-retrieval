"""Behavioral relevance of identity-establishing deletion on LDGR history.

This experiment uses the project's own LDGR historical findings as the memory
content, rather than synthetic motif families.

Question:
  In realistic retrieval conditions, how often does a query omit
  identity-establishing evidence (first occurrence of a recurring node) versus
  merely being incomplete/noisy, and can extra evidence recover the basin?

Current architecture under test:

    label-free canonical topology index
      -> broad basin retrieval
      -> typed payload projection
      -> DP/LCS soft alignment
      -> fine discrimination

Important: this is a behavioral relevance profile, not another deletion fix.
"""

from __future__ import annotations

import json
import os
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CORE = _HERE.parent / "core"
for _p in (str(_CORE),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from matcher_relaxation import SigView, score
from signature import label_free_canonical_signature, typed_canonical_signature

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT_DIR = HERE
DATA_DIR = ROOT / "data" / "ldgr_history"
REPORTS_DIR = ROOT / "reports"

WEIGHTS = {"w_structure": 1.0, "w_typed": 0.5, "w_contradict": 0.7,
           "w_missing": 1.0, "w_extraneous": 0.15}
PLAUSIBLE_MODES = {"prefix_4", "prefix_6", "prefix_8", "prefix_plus_noise",
                   "salient_summary", "single_omission_0", "single_omission_1"}
CONTROL_MODES = {"random_partial_0", "random_partial_1", "adversarial_first_recurring_drop"}

TOPIC_RULES = [
    ("deletion", r"delet|drop|first-occurrence|first_recurring|identity-establishing"),
    ("noise", r"noise|insert|foreign|extraneous"),
    ("matcher", r"matcher|greedy|DP|LCS|alignment|subsequence"),
    ("identity", r"identity|canonical|role_payload|label-stable|renumber"),
    ("polysemy", r"polysemy|prefix-shared|disambiguat|ambigu"),
    ("typed", r"typed|payload|edge label|relation"),
    ("phase0", r"phase 0|toy|unordered|ordered|shuffled"),
    ("boundary", r"boundary|architecture|substrate|destructive"),
]

MECH_RULES = [
    ("matcher_repair", r"DP|LCS|skip-capable|greedy|alignment"),
    ("identity_boundary", r"first-occurrence|identity-establishing|canonical|renumber"),
    ("typed_projection", r"typed payload|typed edge|relation type"),
    ("bag_tradeoff", r"bag|edge_sequence|control"),
    ("generator_bug", r"generator bug|pair-7|truncated prefix"),
]

STOPWORDS = {
    "the", "and", "that", "with", "this", "from", "into", "under", "after", "before",
    "branch", "experiment", "surface", "result", "results", "artifact", "artifacts",
    "completed", "created", "updated", "report", "code", "data", "raw", "project",
    "experiments", "motif", "topology", "retrieval", "canonical", "identity", "typed",
    "payload", "evidence", "family", "families", "score", "scoring", "query", "walk",
    "memory", "substrate", "basin", "basins", "transition", "transitions", "survival",
}


def salient_terms(text: str, n=4) -> list[str]:
    """Content-derived payload terms, excluding generic experiment vocabulary."""
    toks = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text.lower())
    toks = [t.replace("-", "_") for t in toks]
    counts = Counter(t for t in toks if t not in STOPWORDS and not t.isdigit())
    # Prefer distinctive technical tokens, but keep deterministic order.
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out = [norm(t)[:28] for t, _c in ranked[:n]]
    while len(out) < n:
        out.append(f"term_absent_{len(out)}")
    return out


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "x"


def first_match(text: str, rules, default="general"):
    for name, pat in rules:
        if re.search(pat, text, re.I):
            return name
    return default


def metric_tag(text: str) -> str:
    nums = re.findall(r"\b\d+(?:\.\d+)?x?|\bnone\b", text, flags=re.I)
    if not nums:
        return "metric_absent"
    # bucket rather than storing exact full text; still content-derived payload
    if any("34x" in n.lower() or "36x" in n.lower() for n in nums):
        return "metric_reduction_high"
    if any(n in ("1.0", "1") for n in nums):
        return "metric_perfect_or_one"
    if any("0." in n for n in nums):
        return "metric_fractional"
    if any(n.lower() == "none" for n in nums):
        return "metric_none_transition"
    return "metric_numeric"


@dataclass
class MemoryItem:
    family: str
    source: str
    text: str
    topic: str
    mechanism: str
    metric: str
    artifact_kind: str
    walk: list[tuple[str, str | None, str | None]]

    def focal_node(self):
        return self.family


def load_ldgr_history() -> list[dict]:
    """Load observations + artifact descriptions + selected report snippets
    from the extracted JSONL snapshots (self-contained, no DB required)."""
    rows = []
    obs_path = DATA_DIR / "observations.jsonl"
    art_path = DATA_DIR / "artifacts.jsonl"
    for line in obs_path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        rows.append({"source": f"observation:{r['id']}", "kind": "observation", "text": r["body"]})
    for line in art_path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        rows.append({"source": f"artifact:{r['id']}:{r['path']}", "kind": f"artifact_{r['kind']}", "text": f"{r['path']}: {r['description']}"})

    # Add report chunks because they contain the most compressed historical findings.
    report_paths = [
        REPORTS_DIR / "architecture_boundary_report.md",
        REPORTS_DIR / "deletion_controls_report.md",
        REPORTS_DIR / "dp_lcs_surface_report.md",
        REPORTS_DIR / "findings.md",
    ]
    for path in report_paths:
        if not path.exists():
            continue
        text = path.read_text()
        chunks = [c.strip() for c in re.split(r"\n(?=## )", text) if len(c.strip()) > 80]
        for i, c in enumerate(chunks[:8]):  # cap per report to avoid one report dominating
            rows.append({"source": f"report:{path.name}:{i}", "kind": "report", "text": c})
    return rows


def build_walk(family: str, row: dict) -> MemoryItem:
    text = row["text"]
    topic = first_match(text, TOPIC_RULES)
    mech = first_match(text, MECH_RULES)
    metric = metric_tag(text)
    kind = norm(row["kind"])
    source = norm(row["source"])
    terms = salient_terms(text, n=4)

    # Concrete node labels contain historical content; canonical signatures erase
    # node names. Edge labels are typed payload projections from content roles and
    # salient LDGR-history terms. This uses the LDGR findings as memory content
    # while still testing canonical recurrence identity rather than direct labels.
    root = f"finding::{family}"
    topic_node = f"topic::{topic}"
    mechanism_node = f"mechanism::{mech}"
    metric_node = f"metric::{metric}"
    source_node = f"source::{source}"
    kind_node = f"kind::{kind}"
    boundary_node = f"boundary::{topic}:{mech}"
    term_nodes = [f"term::{t}" for t in terms]

    # Recurrence-sensitive shape: topic, mechanism, and two content terms recur.
    # This creates identity-establishing evidence in realistic historical content
    # without adopting a new identity representation.
    walk = [
        (root, None, None),
        (topic_node, f"TOPIC_{topic.upper()}", "out"),
        (term_nodes[0], f"TERM_{terms[0].upper()}", "out"),
        (mechanism_node, f"MECHANISM_{mech.upper()}", "out"),
        (term_nodes[1], f"TERM_{terms[1].upper()}", "out"),
        (topic_node, f"RETURNS_TO_TOPIC_{topic.upper()}", "in"),
        (metric_node, f"METRIC_{metric.upper()}", "out"),
        (term_nodes[2], f"TERM_{terms[2].upper()}", "out"),
        (mechanism_node, f"MECHANISM_RECURS_{mech.upper()}", "in"),
        (term_nodes[0], f"TERM_RECURS_{terms[0].upper()}", "in"),
        (kind_node, f"SOURCE_KIND_{kind.upper()}", "out"),
        (term_nodes[1], f"TERM_RECURS_{terms[1].upper()}", "in"),
        (boundary_node, f"BOUNDARY_{topic.upper()}_{mech.upper()}", "out"),
        (source_node, f"SUPPORTED_BY_{kind.upper()}", "out"),
    ]
    return MemoryItem(family, row["source"], text, topic, mech, metric, kind, walk)


def build_corpus(max_items=32, per_topic_cap=8) -> list[MemoryItem]:
    rows = load_ldgr_history()
    # Prefer historical observations/reports but stratify by topic so one recent
    # report cluster (e.g. deletion) does not dominate and make clean retrieval
    # impossible for reasons unrelated to the boundary being tested.
    scored = []
    for row in rows:
        text = row["text"]
        topic = first_match(text, TOPIC_RULES)
        relevance = sum(1 for _name, pat in TOPIC_RULES + MECH_RULES if re.search(pat, text, re.I))
        if relevance == 0 and row["kind"] not in ("report",):
            continue
        scored.append((topic, relevance, len(text), row))
    scored.sort(key=lambda x: (-x[1], -x[2]))
    selected = []
    topic_counts = Counter()
    # pass 1: topic cap
    for topic, _rel, _len, row in scored:
        if len(selected) >= max_items:
            break
        if topic_counts[topic] >= per_topic_cap:
            continue
        selected.append(row)
        topic_counts[topic] += 1
    # pass 2: fill remaining if needed
    for topic, _rel, _len, row in scored:
        if len(selected) >= max_items:
            break
        if row in selected:
            continue
        selected.append(row)
    return [build_walk(f"hist_{i:03d}", row) for i, row in enumerate(selected)]


# ---------------------------------------------------------------------------
# architecture index
# ---------------------------------------------------------------------------

def _view_from_sig(sig) -> SigView:
    edge_bag = Counter(lab for lab in sig.edge_label_trace[1:] if lab != "—")
    return SigView(
        node_trace=sig.node_trace,
        edge_label_trace=sig.edge_label_trace,
        typed_edges=frozenset(sig.typed_edges),
        typed_edge_counts=sig.typed_edge_counts,
        node_set=frozenset(range(sig.node_count)),
        edge_bag=tuple(sorted(edge_bag.items())),
    )


def typed_view(walk):
    return _view_from_sig(typed_canonical_signature(walk))


def lf_view(walk):
    return _view_from_sig(label_free_canonical_signature(walk))


class HistoricalMemoryIndex:
    def __init__(self, items: list[MemoryItem]):
        self.entries = []
        for it in items:
            self.entries.append({"family": it.family, "item": it,
                                 "lf": lf_view(it.walk), "typed": typed_view(it.walk)})

    def relax(self, evidence_walk) -> dict:
        e_lf = lf_view(evidence_walk)
        e_typed = typed_view(evidence_walk)
        coarse = []
        for ent in self.entries:
            s = score(ent["lf"], e_lf, matcher="dp", weights=WEIGHTS)
            coarse.append({"family": ent["family"], "entry": ent, **s.__dict__})
        coarse.sort(key=lambda r: r["total"], reverse=True)
        coarse_bundle = top_bundle(coarse)
        fine = []
        for c in coarse_bundle:
            ent = c["entry"]
            s = score(ent["typed"], e_typed, matcher="dp", weights=WEIGHTS)
            fine.append({"family": ent["family"], "source": ent["item"].source, **s.__dict__})
        fine.sort(key=lambda r: r["total"], reverse=True)
        fine_bundle = top_bundle(fine)
        dom = None
        if fine:
            top = fine[0]["total"]
            fams = {r["family"] for r in fine if abs(r["total"] - top) < 1e-9}
            dom = next(iter(fams)) if len(fams) == 1 else None
        return {"dominant_family": dom,
                "top_score": fine[0]["total"] if fine else None,
                "coarse_bundle_size": len(coarse_bundle),
                "fine_bundle_size": len(fine_bundle),
                "family_counts": dict(Counter(r["family"] for r in fine_bundle)),
                "ranked": fine}


def top_bundle(scored, frac=0.9):
    if not scored:
        return []
    top = scored[0]["total"]
    threshold = top * frac if top > 0 else top * (2 - frac)
    out = []
    for r in scored:
        if (top >= 0 and r["total"] >= threshold) or (top < 0 and r["total"] <= threshold):
            out.append(r)
        else:
            break
    return out or scored[:1]


# ---------------------------------------------------------------------------
# behavioral query generation
# ---------------------------------------------------------------------------

def deletion_category(walk, i) -> str:
    labels = [s[0] for s in walk]
    node = labels[i]
    first = labels.index(node) == i
    total = labels.count(node)
    if first and total > 1:
        return "first_recurring_occurrence"
    if total > 1:
        return "repeat_occurrence"
    return "singleton_occurrence"


def classify_omissions(full_walk, kept_indices) -> dict:
    """Classify omitted evidence.

    Important distinction:
      - interior omitted (<= max kept position) = deletion / note-taking gap
      - tail omitted (> max kept position) = incomplete query, not deletion yet

    Behavioral relevance hinges on this distinction. Prefix truncation should not
    be counted as deleting identity-establishing evidence.
    """
    max_seen = max(kept_indices) if kept_indices else 0
    omitted = [i for i in range(1, len(full_walk)) if i not in kept_indices]
    deleted = [i for i in omitted if i <= max_seen]
    tail_unseen = [i for i in omitted if i > max_seen]
    cats = Counter(deletion_category(full_walk, i) for i in deleted)
    tail_cats = Counter(deletion_category(full_walk, i) for i in tail_unseen)
    return {"deleted_indices": deleted,
            "tail_unseen_indices": tail_unseen,
            "first_recurring_deleted": cats["first_recurring_occurrence"],
            "repeat_deleted": cats["repeat_occurrence"],
            "singleton_deleted": cats["singleton_occurrence"],
            "first_recurring_tail_unseen": tail_cats["first_recurring_occurrence"],
            "repeat_tail_unseen": tail_cats["repeat_occurrence"],
            "singleton_tail_unseen": tail_cats["singleton_occurrence"],
            "n_deleted": len(deleted),
            "n_tail_unseen": len(tail_unseen)}


def materialize(full_walk, kept_indices, noise_steps=None):
    out = [full_walk[i] for i in sorted(kept_indices)]
    if noise_steps:
        # insert noise after root / between evidence items
        out = list(out)
        for pos, step in noise_steps:
            p = max(1, min(pos, len(out)))
            out.insert(p, step)
    return out


def query_profiles(full_walk, rng: random.Random):
    n = len(full_walk)
    all_idx = set(range(n))
    root = {0}
    profiles = []

    # 1. Prefix/incomplete recall: tail missing, no interior identity deletion.
    for k in (4, 6, 8):
        keep = set(range(min(k, n)))
        profiles.append((f"prefix_{k}", keep, []))

    # 2. Salient historical note: keep topic/mechanism/metric/source-like positions.
    salient = root | {1, 2, 4, 5, 8}
    profiles.append(("salient_summary", {i for i in salient if i < n}, []))

    # 3. Noisy incomplete note: prefix plus neutral insertions.
    keep = set(range(min(7, n)))
    noise = [(rng.randint(1, len(keep)), (f"foreign::{rng.randint(0,9999)}", "FOREIGN_NOTE", "out"))]
    profiles.append(("prefix_plus_noise", keep, noise))

    # 4. Behaviorally plausible omission: lose one middle evidence item from a near-complete note.
    middle = list(range(1, n - 1))
    for j in range(2):
        drop = rng.choice(middle)
        keep = all_idx - {drop}
        profiles.append((f"single_omission_{j}", keep, []))

    # 5. Random partial note baseline (not claimed realistic, useful incidence comparator).
    for j, keep_n in enumerate((6, 7)):
        interior = rng.sample(list(range(1, n)), k=min(keep_n - 1, n - 1))
        keep = root | set(interior)
        profiles.append((f"random_partial_{j}", keep, []))

    # 6. Adversarial calibration: explicitly remove a first-recurring occurrence if present.
    first_rec = [i for i in range(1, n - 1) if deletion_category(full_walk, i) == "first_recurring_occurrence"]
    if first_rec:
        keep = all_idx - {first_rec[0]}
        profiles.append(("adversarial_first_recurring_drop", keep, []))

    return profiles


def recovery_curve(idx: HistoricalMemoryIndex, item: MemoryItem, kept_indices, max_extra=3):
    full = item.walk
    deleted = [i for i in range(1, len(full)) if i not in kept_indices]
    # Add back non-deleted future evidence first; if none remains, no recovery path.
    remaining = [i for i in range(1, len(full)) if i not in kept_indices]
    # To model "extra evidence" without simply restoring the exact missing earliest anchor,
    # add later omitted evidence first, preserving root; the deleted anchor may remain absent
    # unless it is the only evidence left.
    remaining.sort(reverse=True)
    curve = []
    cur = set(kept_indices)
    for step in range(max_extra + 1):
        r = idx.relax(materialize(full, cur))
        curve.append({"extra": step, "survived": r["dominant_family"] == item.family,
                      "dominant": r["dominant_family"], "fine_bundle": r["fine_bundle_size"]})
        if step < max_extra and remaining:
            cur.add(remaining.pop(0))
    return curve


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def clean_baseline(idx: HistoricalMemoryIndex, items: list[MemoryItem]):
    rows = []
    for it in items:
        r = idx.relax(it.walk)
        rows.append({"family": it.family, "source": it.source,
                     "survived": r["dominant_family"] == it.family,
                     "dominant": r["dominant_family"],
                     "fine_bundle_size": r["fine_bundle_size"],
                     "coarse_bundle_size": r["coarse_bundle_size"]})
    mean_bundle = statistics.fmean([r["fine_bundle_size"] for r in rows]) if rows else 0.0
    return {"clean_accuracy": round(statistics.fmean([r["survived"] for r in rows]), 4) if rows else None,
            "mean_fine_bundle": round(mean_bundle, 4),
            "bundle_reduction": round(len(items) / mean_bundle, 4) if mean_bundle else 0.0,
            "rows": rows}


def aggregate_modes(rows, modes):
    xs = [r for r in rows if r["mode"] in modes]
    if not xs:
        return {}
    first = [r for r in xs if r["first_recurring_deleted"] > 0]
    nofirst = [r for r in xs if r["first_recurring_deleted"] == 0]
    return {
        "n": len(xs),
        "first_recurring_deletion_incidence": round(statistics.fmean([r["first_recurring_deleted"] > 0 for r in xs]), 4),
        "survival": round(statistics.fmean([r["survived"] for r in xs]), 4),
        "survival_when_first_recurring_deleted": mean_or_none([r["survived"] for r in first]),
        "survival_without_first_recurring_deleted": mean_or_none([r["survived"] for r in nofirst]),
        "mean_fine_bundle": round(statistics.fmean([r["fine_bundle_size"] for r in xs]), 4),
    }


def summarize(rows):
    by_mode = defaultdict(list)
    for r in rows:
        by_mode[r["mode"]].append(r)
    mode_summary = {}
    for mode, xs in sorted(by_mode.items()):
        mode_summary[mode] = {
            "n": len(xs),
            "first_recurring_deletion_incidence": round(statistics.fmean([x["first_recurring_deleted"] > 0 for x in xs]), 4),
            "repeat_deletion_incidence": round(statistics.fmean([x["repeat_deleted"] > 0 for x in xs]), 4),
            "singleton_deletion_incidence": round(statistics.fmean([x["singleton_deleted"] > 0 for x in xs]), 4),
            "survival": round(statistics.fmean([x["survived"] for x in xs]), 4),
            "mean_fine_bundle": round(statistics.fmean([x["fine_bundle_size"] for x in xs]), 4),
        }
    overall = {
        "n_queries": len(rows),
        "first_recurring_deletion_incidence": round(statistics.fmean([r["first_recurring_deleted"] > 0 for r in rows]), 4),
        "survival": round(statistics.fmean([r["survived"] for r in rows]), 4),
        "survival_when_first_recurring_deleted": mean_or_none([r["survived"] for r in rows if r["first_recurring_deleted"] > 0]),
        "survival_without_first_recurring_deleted": mean_or_none([r["survived"] for r in rows if r["first_recurring_deleted"] == 0]),
        "mean_fine_bundle": round(statistics.fmean([r["fine_bundle_size"] for r in rows]), 4),
    }
    return {"overall": overall, "by_mode": mode_summary}


def mean_or_none(xs):
    return round(statistics.fmean(xs), 4) if xs else None


def summarize_recoveries(recoveries):
    by_mode = defaultdict(lambda: defaultdict(list))
    overall = defaultdict(list)
    for rec in recoveries:
        mode = rec["mode"]
        for pt in rec["curve"]:
            by_mode[mode][pt["extra"]].append(pt["survived"])
            overall[pt["extra"]].append(pt["survived"])
    return {
        "overall": {str(k): round(statistics.fmean(v), 4) for k, v in sorted(overall.items())},
        "by_mode": {
            mode: {str(k): round(statistics.fmean(v), 4) for k, v in sorted(extra.items())}
            for mode, extra in sorted(by_mode.items())
        },
    }


def topic_polysemy_probe(idx: HistoricalMemoryIndex, items: list[MemoryItem]):
    """Probe ambiguous topical starts and +mechanism disambiguation on history corpus."""
    by_topic = defaultdict(list)
    for it in items:
        by_topic[it.topic].append(it)
    rows = []
    for topic, group in sorted(by_topic.items()):
        if len(group) < 2:
            continue
        for it in group[:5]:
            shared = it.walk[:2]          # root + topic payload; weak evidence
            plus = it.walk[:3]            # add mechanism edge
            r0 = idx.relax(shared)
            r1 = idx.relax(plus)
            rows.append({"topic": topic, "family": it.family,
                         "topic_group_size": len(group),
                         "shared_survived": it.family in r0["family_counts"],
                         "plus_dominant_correct": r1["dominant_family"] == it.family,
                         "shared_bundle": r0["fine_bundle_size"],
                         "plus_bundle": r1["fine_bundle_size"]})
    return {"n": len(rows),
            "shared_inclusion": mean_or_none([r["shared_survived"] for r in rows]),
            "plus_disambiguation": mean_or_none([r["plus_dominant_correct"] for r in rows]),
            "mean_shared_bundle": mean_or_none([r["shared_bundle"] for r in rows]),
            "mean_plus_bundle": mean_or_none([r["plus_bundle"] for r in rows]),
            "rows": rows}


def render_report(out):
    lines = [
        "# Behavioral Relevance of Identity-Establishing Deletion",
        "",
        "Memory content: LDGR historical observations, artifact descriptions, and report chunks from this project.",
        "Architecture: label-free canonical topology index → typed payload projection → DP/LCS soft alignment.",
        "",
        "## Corpus",
        "",
        f"- memory items: {out['corpus']['n_items']}",
        f"- topics: {out['corpus']['topic_counts']}",
        "",
        "## Clean Baseline",
        "",
        f"- clean accuracy: {out['clean_baseline']['clean_accuracy']}",
        f"- mean fine bundle: {out['clean_baseline']['mean_fine_bundle']}",
        f"- bundle reduction: {out['clean_baseline']['bundle_reduction']}",
        "",
        "If clean accuracy is poor, the behavioral relevance profile should be treated as a corpus/encoding failure, not as evidence about deletion brittleness.",
        "",
        "## Overall Query Profile",
        "",
    ]
    overall = out["summary"]["overall"]
    for k, v in overall.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## By Query Mode", "",
              "| mode | n | first-rec incidence | repeat incidence | singleton incidence | survival | fine bundle |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for mode, s in out["summary"]["by_mode"].items():
        lines.append(f"| {mode} | {s['n']} | {s['first_recurring_deletion_incidence']} | "
                     f"{s['repeat_deletion_incidence']} | {s['singleton_deletion_incidence']} | "
                     f"{s['survival']} | {s['mean_fine_bundle']} |")
    rec = out["recovery_summary"]
    lines += ["", "## Plausible vs Control Modes", ""]
    for name, vals in out["stratified_summary"].items():
        lines.append(f"- {name}: {vals}")
    lines += ["", "## Recovery With Extra Evidence", "",
              f"- overall survival by added evidence step: {rec['overall']}",
              "", "By mode:", ""]
    for mode, vals in rec["by_mode"].items():
        lines.append(f"- {mode}: {vals}")
    p = out["topic_polysemy"]
    lines += ["", "## Topic Polysemy Probe", "",
              f"- probes: {p['n']}",
              f"- shared topical inclusion: {p['shared_inclusion']}",
              f"- +mechanism disambiguation: {p['plus_disambiguation']}",
              f"- mean shared bundle: {p['mean_shared_bundle']}",
              f"- mean +mechanism bundle: {p['mean_plus_bundle']}",
              "", "## Interpretation", ""]
    o = out["summary"]["overall"]
    lines.append(
        "This profile estimates whether the known destructive perturbation appears under behaviorally plausible historical-query conditions. "
        "Prefix/incomplete and noisy-prefix modes model missing tail evidence and inserted noise; single/random omissions model note-taking gaps; adversarial mode calibrates the known boundary."
    )
    lines.append("")
    plausible = out["stratified_summary"]["plausible_modes"]
    controls = out["stratified_summary"]["control_modes"]
    lines.append(
        f"Overall first-recurring deletion incidence was {o['first_recurring_deletion_incidence']}; survival with first-recurring deletion was {o['survival_when_first_recurring_deleted']} vs {o['survival_without_first_recurring_deleted']} without it."
    )
    lines.append("")
    lines.append(
        f"For the behaviorally plausible modes only, first-recurring deletion incidence was {plausible['first_recurring_deletion_incidence']} and survival stayed {plausible['survival']} ({plausible['survival_when_first_recurring_deleted']} with first-recurring deletion vs {plausible['survival_without_first_recurring_deleted']} without)."
    )
    lines.append("")
    lines.append(
        f"For control/adversarial modes, first-recurring deletion incidence was {controls['first_recurring_deletion_incidence']} and survival dropped to {controls['survival']}. This separates realistic note/incomplete queries from destructive random/adversarial omissions."
    )
    lines.append("")
    lines.append(
        "Use the by-mode table, not the overall average alone: adversarial calibration is intentionally included and should not be mistaken for expected workload frequency."
    )
    return "\n".join(lines) + "\n"


def main():
    print("building LDGR historical memory corpus...")
    items = build_corpus(max_items=32, per_topic_cap=8)
    idx = HistoricalMemoryIndex(items)
    clean = clean_baseline(idx, items)
    rng = random.Random(20260706)

    rows = []
    recoveries = []
    for it in items:
        for mode, kept, noise in query_profiles(it.walk, rng):
            kept = set(i for i in kept if i < len(it.walk))
            q = materialize(it.walk, kept, noise)
            om = classify_omissions(it.walk, kept)
            r = idx.relax(q)
            row = {"family": it.family, "source": it.source, "topic": it.topic,
                   "mode": mode, "query_len": len(q), **om,
                   "survived": r["dominant_family"] == it.family,
                   "dominant": r["dominant_family"],
                   "fine_bundle_size": r["fine_bundle_size"],
                   "coarse_bundle_size": r["coarse_bundle_size"],
                   "top_score": r["top_score"]}
            rows.append(row)
            if om["first_recurring_deleted"] > 0:
                recoveries.append({"family": it.family, "source": it.source, "mode": mode,
                                   "curve": recovery_curve(idx, it, kept, max_extra=3)})

    topic_poly = topic_polysemy_probe(idx, items)
    corpus = {"n_items": len(items),
              "topic_counts": dict(Counter(it.topic for it in items)),
              "mechanism_counts": dict(Counter(it.mechanism for it in items)),
              "items": [it.__dict__ | {"walk": it.walk} for it in items]}
    out = {"experiment": "behavioral-relevance-of-identity-deletion",
           "branch": "behavioral-relevance-of-identity-deletion",
           "architecture": "label-free topology index -> typed payload projection -> DP/LCS soft alignment",
           "weights": WEIGHTS,
           "corpus": corpus,
           "clean_baseline": clean,
           "summary": summarize(rows),
           "stratified_summary": {
               "plausible_modes": aggregate_modes(rows, PLAUSIBLE_MODES),
               "control_modes": aggregate_modes(rows, CONTROL_MODES),
           },
           "recovery_summary": summarize_recoveries(recoveries),
           "topic_polysemy": topic_poly,
           "queries": rows,
           "recoveries": recoveries}

    json_path = OUT_DIR / "behavioral_relevance_results.json"
    json_path.write_text(json.dumps(out, indent=2))
    report_path = OUT_DIR / "behavioral_relevance_report.md"
    report_path.write_text(render_report(out))

    print("\nBEHAVIORAL RELEVANCE PROFILE")
    print("=" * 78)
    print("corpus items:", len(items), "topics:", dict(Counter(it.topic for it in items)))
    print("clean:", clean)
    print("overall:", out["summary"]["overall"])
    print("stratified:", out["stratified_summary"])
    print("\nby mode:")
    for mode, s in out["summary"]["by_mode"].items():
        print(f"  {mode:<34} first-rec={s['first_recurring_deletion_incidence']:<6} survival={s['survival']:<6} bundle={s['mean_fine_bundle']}")
    print("\nrecovery:", out["recovery_summary"]["overall"])
    print("\ntopic polysemy:", {k: v for k, v in topic_poly.items() if k != "rows"})
    print(f"\nwrote {json_path.name}")
    print(f"wrote {report_path.name}")


if __name__ == "__main__":
    main()
