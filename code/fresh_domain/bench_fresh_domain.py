"""Fresh-domain generalization test: code call-graphs as relational walks.

This experiment addresses the central rejection risk identified in review:
every number in the paper is measured on corpora used to develop the operator.
This tests whether the compression envelope holds on a domain the operator
never saw -- Python source code from unrelated repositories.

WHAT THIS DOES
--------------
1. Extract typed call-graph walks from fresh Python repos (delta-top, rica, tdm).
   Each function becomes a relational walk: [(func, None, None), (callee, CALLS, out), ...]
   traversing the call/inherit/import graph to bounded depth.

2. Group functions into structural families by their full canonical signature.
   This is the ground-truth grouping -- functions with identical recurrence shape.

3. Run held-out retrieval: index a subset, query held-out members by their prefix.
   Measures the SAME metrics as the paper: basin size, compression, target inclusion,
   coverage.

4. Compare against two fair baselines on the same axes:
   - token-prefix-hash : hash-shard by the first-k concrete tokens (lexical prefix)
   - token-set-jaccard : return walks whose token-set Jaccard >= threshold

This is the discriminating experiment the paper does not close.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import fmean

_HERE = Path(__file__).resolve().parent
_CORE = _HERE.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from generator import Instance
from relaxation import RelaxationIndex


# ---------------------------------------------------------------------------
# 1. Code-graph extraction
# ---------------------------------------------------------------------------

def _qualified_name(node: ast.AST, module: str) -> str:
    """Best-effort qualified name for a function/class/method."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return f"{module}.{node.name}"
    return f"{module}.<anon>"


def _callee_name(node: ast.AST) -> str | None:
    """Extract a callee name from a Call node (handles attr chains)."""
    func = node.func
    parts: list[str] = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    elif isinstance(func, ast.Call):
        return None  # nested call result — skip for cleanliness
    else:
        return None
    return ".".join(reversed(parts)) if parts else None


@dataclass
class CodeGraph:
    """Typed directed graph extracted from one Python module."""
    module: str
    nodes: set[str] = field(default_factory=set)
    edges: list[tuple[str, str, str]] = field(default_factory=list)  # (src, rel, dst)

    def successors(self, node: str) -> list[tuple[str, str]]:
        return [(rel, dst) for (src, rel, dst) in self.edges if src == node]


def extract_module_graph(path: Path, repo_name: str) -> CodeGraph | None:
    """Parse a .py file into a typed call/inherit/import graph."""
    try:
        source = path.read_text(errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError):
        return None

    module = f"{repo_name}:{path.stem}"
    g = CodeGraph(module=module)
    g.nodes.add(module)  # module-level entry point

    # collect all function/class defs with qualified names
    defs: dict[ast.AST, str] = {}
    imports: list[tuple[str, str]] = []  # (alias, full_name)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = _qualified_name(node, module)
            defs[node] = name
            g.nodes.add(name)
        elif isinstance(node, ast.ClassDef):
            name = _qualified_name(node, module)
            defs[node] = name
            g.nodes.add(name)
            # inheritance edges
            for base in node.bases:
                bname = _callee_name(base) if hasattr(base, "func") else getattr(base, "id", None)
                if bname:
                    g.edges.append((name, "INHERITS", bname))
                    g.nodes.add(bname)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                alias_name = alias.asname or alias.name.split(".")[0]
                imports.append((alias_name, alias.name))
                g.nodes.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod_prefix = node.module or ""
            for alias in node.names:
                full = f"{mod_prefix}.{alias.name}" if mod_prefix else alias.name
                alias_name = alias.asname or alias.name
                imports.append((alias_name, full))
                g.nodes.add(full)

    # build call edges inside each function
    for node, fname in defs.items():
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                callee = _callee_name(child)
                if callee is None:
                    continue
                # resolve import aliases
                resolved = callee
                for alias_name, full in imports:
                    if callee == alias_name or callee.startswith(alias_name + "."):
                        resolved = callee.replace(alias_name, full, 1)
                        break
                g.edges.append((fname, "CALLS", resolved))
                g.nodes.add(resolved)

    return g


def walks_from_graph(g: CodeGraph, max_depth: int = 6, max_walks: int = 40) -> list[list[tuple]]:
    """Produce bounded DFS walks rooted at each function node.

    Walk format matches the operator: [(root, None, None), (node, rel, direction), ...]
    direction = 'out' (we follow edges forward).
    """
    walks: list[list[tuple]] = []
    roots = sorted(n for n in g.nodes if any(s in g.nodes for s, _, _ in g.edges if s == n)
                   or any(n == dst for _, _, dst in g.edges))
    if not roots:
        roots = sorted(g.nodes)

    for root in roots[:max_walks]:
        # iterative DFS, record the path
        walk: list[tuple] = [(root, None, None)]
        visited_in_walk: set[str] = {root}
        stack = [(root, iter(g.successors(root)))]

        while stack and len(walk) < max_depth + 1:
            current, succ_iter = stack[-1]
            advanced = False
            for rel, dst in succ_iter:
                if dst in visited_in_walk and len(walk) > 2:
                    # allow ONE revisit to create recurrence, then stop this branch
                    walk.append((dst, rel, "out"))
                    continue
                if dst not in g.nodes and not any(dst == n for n in g.nodes):
                    continue
                walk.append((dst, rel, "out"))
                visited_in_walk.add(dst)
                stack.append((dst, iter(g.successors(dst))))
                advanced = True
                break
            if not advanced:
                stack.pop()

        if len(walk) >= 3:  # need at least root + 2 steps for a meaningful signature
            walks.append(walk)
    return walks


# ---------------------------------------------------------------------------
# 2. Corpus assembly
# ---------------------------------------------------------------------------

@dataclass
class CodeInstance:
    """Wraps a code walk as an operator Instance."""
    family: str  # structural-family key (assigned later)
    walk: list
    _focal: str

    def focal_node(self) -> str:
        return self._focal


def build_corpus(repo_roots: list[Path], min_walks_per_repo: int = 20) -> list[CodeInstance]:
    """Extract walks from all fresh repos, return as CodeInstances (family TBD)."""
    raw: list[CodeInstance] = []
    from signature import typed_canonical_signature

    for repo in repo_roots:
        repo_name = repo.name
        py_files = sorted(repo.rglob("*.py"))
        py_files = [p for p in py_files if ".venv" not in str(p) and "__pycache__" not in str(p)]
        repo_walks: list[tuple[str, list[tuple]]] = []
        for pf in py_files[:300]:
            g = extract_module_graph(pf, repo_name)
            if g is None or not g.edges:
                continue
            for w in walks_from_graph(g):
                repo_walks.append((g.module, w))

        for module, walk in repo_walks:
            raw.append(CodeInstance(family="_pending", walk=walk, _focal=walk[0][0]))

    # assign structural family = canonical signature key (ground truth grouping)
    for inst in raw:
        sig = typed_canonical_signature(inst.walk)
        inst.family = f"sig_{hashlib.md5(sig.key().encode()).hexdigest()[:8]}"

    # keep only families with >= 2 members (need >=1 indexed + >=1 held-out)
    family_counts: dict[str, int] = defaultdict(int)
    for inst in raw:
        family_counts[inst.family] += 1
    raw = [inst for inst in raw if family_counts[inst.family] >= 2]

    return raw


# ---------------------------------------------------------------------------
# 3. Held-out retrieval (mirrors the paper's protocol)
# ---------------------------------------------------------------------------

def operator_retrieval(instances: list, variant: str = "labelfree"):
    """Index on a held-in split, query held-out by prefix; return per-query basin."""
    from relaxation import RelaxationIndex

    # split each family: index floor(n/2), query the rest (min 1 each)
    by_family: dict[str, list] = defaultdict(list)
    for inst in instances:
        by_family[inst.family].append(inst)

    index_insts: list = []
    query_insts: list = []
    for fam, members in by_family.items():
        members_sorted = sorted(members, key=lambda x: x.focal_node())
        split = max(1, len(members_sorted) // 2)
        index_insts.extend(members_sorted[:split])
        query_insts.extend(members_sorted[split:])

    if not index_insts or not query_insts:
        return [], 0, 0

    idx = RelaxationIndex(variant=variant)
    # adapt CodeInstance -> Instance for the index
    op_instances = []
    for ci in index_insts:
        op_instances.append(Instance(family=ci.family, labels=(ci._focal,), walk=ci.walk))
    idx.add_all(op_instances)

    results = []
    store_size = len(index_insts)
    for q in query_insts:
        prefix_len = max(2, len(q.walk) // 2)
        state = idx.relax(q.walk, length=prefix_len)
        target_family_in_basin = q.family in state.family_counts or any(
            idx.instances[i].family == q.family for i in range(len(idx.instances))
            if idx.instances[i].focal_node() in state.active_instances
        ) if False else (q.family in dict(state.family_counts))
        results.append({
            "query_focal": q.focal_node(),
            "query_family": q.family,
            "prefix_len": prefix_len,
            "walk_len": len(q.walk),
            "basin_size": state.n_active,
            "store_size": store_size,
            "target_family_in_basin": target_family_in_basin,
            "families_in_basin": state.n_distinct_families,
        })
    return results, store_size, len(query_insts)


# ---------------------------------------------------------------------------
# 4. Baselines (same protocol, different retrieval key)
# ---------------------------------------------------------------------------

def baseline_token_prefix(instances: list, prefix_len: int | None = None):
    """Lexical token-prefix hash: shard by first-k concrete tokens."""
    by_family: dict[str, list] = defaultdict(list)
    for inst in instances:
        by_family[inst.family].append(inst)

    index_insts: list = []
    query_insts: list = []
    for fam, members in by_family.items():
        ms = sorted(members, key=lambda x: x.focal_node())
        split = max(1, len(ms) // 2)
        index_insts.extend(ms[:split])
        query_insts.extend(ms[split:])

    results = []
    store_size = len(index_insts)
    for q in query_insts:
        pl = prefix_len or max(2, len(q.walk) // 2)
        q_prefix = tuple(node for node, _, _ in q.walk[:pl])
        basin_families: set[str] = set()
        basin_size = 0
        for inst in index_insts:
            i_prefix = tuple(node for node, _, _ in inst.walk[:pl])
            if i_prefix == q_prefix:
                basin_size += 1
                basin_families.add(inst.family)
        results.append({
            "query_focal": q.focal_node(),
            "query_family": q.family,
            "prefix_len": pl,
            "basin_size": basin_size,
            "store_size": store_size,
            "target_family_in_basin": q.family in basin_families,
            "families_in_basin": len(basin_families),
        })
    return results, store_size, len(query_insts)


def baseline_token_jaccard(instances: list, threshold: float = 0.5):
    """Token-set Jaccard: return walks whose token-set overlap >= threshold."""
    by_family: dict[str, list] = defaultdict(list)
    for inst in instances:
        by_family[inst.family].append(inst)

    index_insts: list = []
    query_insts: list = []
    for fam, members in by_family.items():
        ms = sorted(members, key=lambda x: x.focal_node())
        split = max(1, len(ms) // 2)
        index_insts.extend(ms[:split])
        query_insts.extend(ms[split:])

    index_token_sets = [(inst, set(node for node, _, _ in inst.walk)) for inst in index_insts]
    results = []
    store_size = len(index_insts)
    for q in query_insts:
        q_tokens = set(node for node, _, _ in q.walk)
        basin_families: set[str] = set()
        basin_size = 0
        for inst, i_tokens in index_token_sets:
            union = q_tokens | i_tokens
            if not union:
                continue
            jac = len(q_tokens & i_tokens) / len(union)
            if jac >= threshold:
                basin_size += 1
                basin_families.add(inst.family)
        results.append({
            "query_focal": q.focal_node(),
            "query_family": q.family,
            "basin_size": basin_size,
            "store_size": store_size,
            "target_family_in_basin": q.family in basin_families,
            "families_in_basin": len(basin_families),
        })
    return results, store_size, len(query_insts)


# ---------------------------------------------------------------------------
# 5. Metrics + reporting
# ---------------------------------------------------------------------------

def summarize(name: str, results: list, store_size: int, n_queries: int) -> dict:
    if not results:
        return {"method": name, "n_queries": 0, "note": "no queries"}
    basin_sizes = [r["basin_size"] for r in results]
    inclusions = [1.0 if r["target_family_in_basin"] else 0.0 for r in results]
    nonempty = [r for r in results if r["basin_size"] > 0]
    coverage = len(nonempty) / len(results) if results else 0.0

    # geometric mean of compression (store/basin) over nonempty basins
    import math
    compressions = [store_size / r["basin_size"] for r in nonempty] if nonempty else [0.0]
    geo_compression = math.exp(fmean(math.log(c) for c in compressions)) if compressions else 0.0

    return {
        "method": name,
        "n_queries": n_queries,
        "store_size": store_size,
        "mean_basin_size": round(fmean(basin_sizes), 2),
        "median_basin_size": round(sorted(basin_sizes)[len(basin_sizes) // 2], 2),
        "geomean_compression": round(geo_compression, 2),
        "target_inclusion": round(fmean(inclusions), 4),
        "coverage": round(coverage, 4),
    }


def main():
    # fresh repos the operator NEVER saw during development
    # (NOT topology, ecphory, ecphory-2, or episteme which built it)
    repo_roots = [
        Path("/home/bakobi/repos/bako/research/delta-top"),
        Path("/home/bakobi/repos/bako/research/rica"),
        Path("/home/bakobi/repos/bako/research/tdm"),
        Path("/home/bakobi/repos/bako/research/magi"),
    ]
    repo_roots = [r for r in repo_roots if r.exists()]

    print("=" * 70)
    print("FRESH-DOMAIN GENERALIZATION TEST")
    print("Code call-graphs as relational walks (operator never saw this domain)")
    print("=" * 70)
    print(f"repos: {[r.name for r in repo_roots]}")
    print()

    corpus = build_corpus(repo_roots)
    families = set(inst.family for inst in corpus)
    print(f"corpus: {len(corpus)} walks, {len(families)} structural families")
    fam_sizes = [sum(1 for i in corpus if i.family == f) for f in families]
    print(f"family sizes: min={min(fam_sizes)} median={sorted(fam_sizes)[len(fam_sizes)//2]} "
          f"max={max(fam_sizes)} mean={fmean(fam_sizes):.1f}")
    walk_lens = [len(inst.walk) for inst in corpus]
    print(f"walk lengths: min={min(walk_lens)} median={sorted(walk_lens)[len(walk_lens)//2]} "
          f"max={max(walk_lens)} mean={fmean(walk_lens):.1f}")
    print()

    if len(corpus) < 20:
        print("WARNING: corpus too small for meaningful results")
        return

    print("METHOD COMPARISON (same held-out protocol, same metrics)")
    print("-" * 70)

    methods = [
        ("basin-retrieval (labelfree)", lambda: operator_retrieval(corpus, "labelfree")),
        ("basin-retrieval (typed)", lambda: operator_retrieval(corpus, "typed")),
        ("token-prefix-hash (lexical)", lambda: baseline_token_prefix(corpus)),
        ("token-set-jaccard@0.5", lambda: baseline_token_jaccard(corpus, 0.5)),
        ("token-set-jaccard@0.3", lambda: baseline_token_jaccard(corpus, 0.3)),
    ]

    summaries = []
    for name, fn in methods:
        results, store, nq = fn()
        s = summarize(name, results, store, nq)
        summaries.append(s)
        print(f"\n  {name}")
        print(f"    queries={s.get('n_queries',0)}  store={s.get('store_size',0)}")
        print(f"    mean basin={s.get('mean_basin_size','-')}  "
              f"compression={s.get('geomean_compression','-')}x  "
              f"inclusion={s.get('target_inclusion','-')}  "
              f"coverage={s.get('coverage','-')}")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)

    out = {
        "experiment": "fresh-domain-generalization-code-callgraphs",
        "repos": [r.name for r in repo_roots],
        "corpus": {
            "n_walks": len(corpus),
            "n_families": len(families),
            "family_size_stats": {
                "min": min(fam_sizes), "median": sorted(fam_sizes)[len(fam_sizes)//2],
                "max": max(fam_sizes), "mean": round(fmean(fam_sizes), 2),
            },
            "walk_length_stats": {
                "min": min(walk_lens), "median": sorted(walk_lens)[len(walk_lens)//2],
                "max": max(walk_lens), "mean": round(fmean(walk_lens), 2),
            },
        },
        "results": summaries,
    }
    out_path = _HERE / "fresh_domain_results.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
