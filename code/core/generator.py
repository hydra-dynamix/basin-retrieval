"""Typed-graph motif generator (predeclared, rejection-sampled).

Faithful port of ../topology/src/generalized_trajectory_experiment.py to a TYPED
knowledge graph. The topology program generates opaque-symbol traces; we generate
walks over a ROLE GRAPH (claim/record/method/metric/domain/verdict) where each
step carries a typed edge (SUPPORTS, WEAKENS, USES_METHOD, ...). This makes the
output resemble real knowledge subgraphs while staying identity-free after
canonicalization.

Generation (mirrors the topology program):
  1. Walk the role graph from a focal role (claim), depth-bounded.
  2. At each step pick a random incident typed edge; decide recurrence vs new node
     (constrained so all roles get introduced, like generate_candidate_trace).
  3. Keep skeletons with >=2 structural properties (recurrence/branch/convergence/
     repeated_subtrace/loop_closure). Reject simple paths (already falsified).
  4. Dedupe skeletons by typed canonical signature.
  5. Instantiate each skeleton K times with disjoint labels per role slot.

Why this is not circular: families are SAMPLED from a fixed grammar before any
retrieval runs. Consolidation is a property of the generator's output, not an
input to it. The benchmark then asks whether retrieval can recover the right
family from partial evidence, against degree-matched controls the generator
also produces.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from graph_dataset import TypedGraph, walks_for
from signature import WalkStep, typed_canonical_signature

# ---------------------------------------------------------------------------
# role graph: the typed grammar. (source_role, edge_type, target_role).
# This is the only place "semantics" enter; after this everything is topology.
# ---------------------------------------------------------------------------

ROLES = ("claim", "record", "method", "metric", "domain", "verdict")

# valid directed typed edges between roles. direction='out' means source->target.
ROLE_EDGES: list[tuple[str, str, str]] = [
    ("record", "SUPPORTS", "claim"),
    ("record", "WEAKENS", "claim"),
    ("record", "CONTRADICTS", "claim"),
    ("record", "USES_METHOD", "method"),
    ("record", "MEASURES", "metric"),
    ("record", "IN_DOMAIN", "domain"),
    ("record", "HAS_VERDICT", "verdict"),
    ("claim", "SUPERSEDED_BY", "claim"),
    ("claim", "DERIVES_FROM", "claim"),
]

# adjacency over roles: role -> list of (edge_type, direction, neighbor_role)
ROLE_ADJ: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
for src, et, tgt in ROLE_EDGES:
    ROLE_ADJ[src].append((et, "out", tgt))
    ROLE_ADJ[tgt].append((et, "in", src))
for k in ROLE_ADJ:
    ROLE_ADJ[k].sort()


@dataclass(frozen=True)
class Skeleton:
    """A motif skeleton over the role graph.

    trace       : canonical node ids (first-occurrence encoding)
    node_roles  : role of each canonical node id (index = node id)
    edge_labels : (edge_type, direction) per transition, aligned with trace[1:]
    properties  : structural tags (recurrence/branch/convergence/...)
    """
    trace: tuple[int, ...]
    node_roles: tuple[str, ...]
    edge_labels: tuple[tuple[str, str], ...]
    properties: tuple[str, ...]

    def role_of(self, node_id: int) -> str:
        return self.node_roles[node_id]

    def signature_key(self) -> str:
        """The typed canonical signature key, computed from a canonical walk."""
        walk = self._canonical_walk()
        return typed_canonical_signature(walk).key()

    def _canonical_walk(self) -> list[WalkStep]:
        # reconstruct a walk whose node labels are the canonical ids themselves,
        # so typed_canonical_signature reproduces the skeleton's key deterministically
        steps: list[WalkStep] = [(str(self.trace[0]), None, None)]
        for i in range(1, len(self.trace)):
            et, direction = self.edge_labels[i - 1]
            steps.append((str(self.trace[i]), et, direction))
        return steps


# ---------------------------------------------------------------------------
# structural property classification (port of motif_properties)
# ---------------------------------------------------------------------------

def _properties(trace: Sequence[int], edge_labels: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    props: list[str] = []
    if len(set(trace)) < len(trace):
        props.append("recurrence")
    successors: dict[int, set[int]] = defaultdict(set)
    predecessors: dict[int, set[int]] = defaultdict(set)
    edge_pairs: Counter[tuple[int, str, str, int]] = Counter()
    for i in range(1, len(trace)):
        a, b = trace[i - 1], trace[i]
        lab = edge_labels[i - 1]
        successors[a].add(b)
        predecessors[b].add(a)
        edge_pairs[(a, lab[0], lab[1], b)] += 1
    if any(len(v) >= 2 for v in successors.values()):
        props.append("branch")
    if any(len(v) >= 2 for v in predecessors.values()):
        props.append("convergence")
    if any(c >= 2 for c in edge_pairs.values()):
        props.append("repeated_subtrace")
    if len(trace) > 2 and trace[-1] == trace[0]:
        props.append("loop_closure")
    return tuple(props)


# ---------------------------------------------------------------------------
# skeleton generation (port of generate_candidate_trace + generate_motifs)
# ---------------------------------------------------------------------------

def _generate_walk(
    rng: random.Random, max_depth: int, max_nodes: int
) -> list[tuple[str, str, str, str]] | None:
    """One random walk over the role graph. Returns steps as (node_label, role, edge_type, direction).

    node_label is a fresh concrete id per slot so recurrence is explicit. Returns
    None if the walk couldn't stay type-consistent within bounds.
    """
    focal = "claim"
    # node slots: each is (role, slot_index_within_role)
    slots: list[tuple[str, int]] = [(focal, 0)]
    role_counters: Counter[str] = Counter({focal: 1})
    steps: list[tuple[int, str, str, str]] = [(0, focal, "", "")]  # (slot_idx, role, et, dir)
    depth = 0
    while depth < max_depth:
        cur_slot, cur_role, _, _ = steps[-1]
        options = ROLE_ADJ[cur_role]
        if not options:
            break
        et, direction, nbr_role = rng.choice(options)
        # decide: new slot or recurrence of an existing slot of nbr_role?
        existing = [i for i, (r, _) in enumerate(slots) if r == nbr_role]
        can_new = role_counters[nbr_role] < max_nodes // len(ROLES) + 1
        if existing and (not can_new or rng.random() < 0.5):
            nbr_slot = rng.choice(existing)
        elif can_new:
            role_counters[nbr_role] += 1
            slots.append((nbr_role, role_counters[nbr_role]))
            nbr_slot = len(slots) - 1
        else:
            break
        steps.append((nbr_slot, nbr_role, et, direction))
        depth += 1
    if len(steps) < 4:
        return None
    # convert to (node_label, role, et, dir)
    out = [(f"n{s}", role, et, direction) for (s, role, et, direction) in steps]
    return out


def _walk_to_skeleton(walk: list[tuple[str, str, str, str]]) -> Skeleton:
    ids: dict[str, int] = {}
    trace: list[int] = []
    node_roles_by_id: dict[int, str] = {}
    for node_label, role, _et, _dir in walk:
        if node_label not in ids:
            ids[node_label] = len(ids)
            node_roles_by_id[ids[node_label]] = role
        trace.append(ids[node_label])
    edge_labels = [(et, dir_) for (_n, _r, et, dir_) in walk[1:]]
    props = _properties(trace, edge_labels)
    return Skeleton(
        trace=tuple(trace),
        node_roles=tuple(node_roles_by_id[i] for i in range(len(node_roles_by_id))),
        edge_labels=tuple(edge_labels),
        properties=props,
    )


def generate_skeletons(
    *, count: int, seed: int = 20260706, max_depth: int = 8, max_nodes: int = 9,
    min_properties: int = 2, max_attempts: int = 50_000,
) -> list[Skeleton]:
    """Rejection-sample `count` unique skeletons with >=min_properties structural props."""
    rng = random.Random(seed)
    skeletons: list[Skeleton] = []
    seen: set[str] = set()
    attempts = 0
    while len(skeletons) < count and attempts < max_attempts:
        attempts += 1
        walk = _generate_walk(rng, max_depth=max_depth, max_nodes=max_nodes)
        if walk is None:
            continue
        skel = _walk_to_skeleton(walk)
        if len(skel.properties) < min_properties:
            continue
        if len(set(skel.trace)) == len(skel.trace):  # reject pure paths
            continue
        key = skel.signature_key()
        if key in seen:
            continue
        seen.add(key)
        skeletons.append(skel)
    if len(skeletons) < count:
        raise RuntimeError(
            f"generated only {len(skeletons)} of {count} skeletons after {attempts} attempts"
        )
    return skeletons


# ---------------------------------------------------------------------------
# instantiation: skeleton + K disjoint label assignments -> concrete TypedGraph
# ---------------------------------------------------------------------------

_ROLE_PREFIX = {"claim": "K", "record": "L", "method": "M", "metric": "Q", "domain": "D", "verdict": "V"}


@dataclass
class Instance:
    family: str                 # skeleton index name, e.g. "gen_000"
    labels: tuple[str, ...]     # concrete label per skeleton node id
    edges: list[tuple[str, str, str]] = field(default_factory=list)
    walk: list = field(default_factory=list)  # concrete walk: [(label, et|None, dir|None), ...]

    def focal_node(self) -> str:
        return self.labels[0]   # node 0 is the focal claim


def instantiate_skeleton(skel: Skeleton, family: str, k: int) -> list[Instance]:
    """Produce k instances with disjoint labels. Each instance is a family member."""
    instances: list[Instance] = []
    for j in range(k):
        labels: list[str] = []
        for node_id, role in enumerate(skel.node_roles):
            prefix = _ROLE_PREFIX[role]
            labels.append(f"{prefix}-{family}-{j:02d}-{node_id:02d}")
        edges: list[tuple[str, str, str]] = []
        # concrete walk = skeleton trace realized with labels. This IS the memory
        # object; no global graph traversal. (The topology program stores one
        # isolated sequence per memory object; the per-instance walk preserves
        # that boundary.)
        walk: list[tuple] = [(labels[skel.trace[0]], None, None)]
        for i in range(1, len(skel.trace)):
            a, b = skel.trace[i - 1], skel.trace[i]
            et, _direction = skel.edge_labels[i - 1]
            if _direction == "in":
                edges.append((labels[b], et, labels[a]))
            else:
                edges.append((labels[a], et, labels[b]))
            walk.append((labels[skel.trace[i]], et, _direction))
        instances.append(Instance(family=family, labels=tuple(labels), edges=edges, walk=walk))
    return instances


def build_generated_graph(
    *, n_families: int, instances_per: int, seed: int = 20260706,
    max_depth: int = 8, max_nodes: int = 9,
) -> tuple[TypedGraph, list[Skeleton], dict[str, list[Instance]]]:
    """Generate skeletons, instantiate, and emit one TypedGraph containing all families."""
    skeletons = generate_skeletons(count=n_families, seed=seed, max_depth=max_depth, max_nodes=max_nodes)
    all_instances: dict[str, list[Instance]] = {}
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []
    for idx, skel in enumerate(skeletons):
        family = f"gen_{idx:03d}"
        insts = instantiate_skeleton(skel, family, instances_per)
        all_instances[family] = insts
        for inst in insts:
            for node_id, role in enumerate(skel.node_roles):
                nodes[inst.labels[node_id]] = role
            edges.extend(inst.edges)
    g = TypedGraph(nodes=nodes)
    for src, et, tgt in edges:
        g.out_edges.setdefault(src, []).append((et, tgt))
        g.in_edges.setdefault(tgt, []).append((et, src))
    for d in (g.out_edges, g.in_edges):
        for k in d:
            d[k].sort()
    return g, skeletons, all_instances


# ---------------------------------------------------------------------------
# prefix-shared divergent (polysemy) pairs -- the `bat`/`bank` construction.
# Two distinct skeletons that SHARE the first k canonical steps (shared
# activation prefix) then DIVERGE. Both are valid basins. On the shared prefix
# the relaxation must keep BOTH active (ambiguity); the disambiguating suffix
# collapses to the correct one. (The topology program had prefix-divergent as a
# REJECT control; here both are POSITIVES = polysemy.)
# ---------------------------------------------------------------------------

def _continue_prefix(
    rng: random.Random, skel: Skeleton, share_k: int, max_total_depth: int, max_nodes: int,
) -> Skeleton:
    """Continue a skeleton's first share_k steps into a NEW full skeleton.

    Reconstructs the canonical trace/role/edge state from the shared prefix, then
    appends random role-graph steps (recurrence vs new slot) until depth bound.
    Returns a fresh Skeleton that shares the prefix with `skel`.
    """
    trace = list(skel.trace[:share_k])
    node_roles_by_id: dict[int, str] = {nid: skel.node_roles[nid] for nid in trace}
    edge_labels: list[tuple[str, str]] = list(skel.edge_labels[: share_k - 1])
    role_counters: Counter[str] = Counter(node_roles_by_id.values())
    cur = trace[-1]
    depth = len(trace)
    while depth < max_total_depth:
        cur_role = node_roles_by_id[cur]
        options = ROLE_ADJ[cur_role]
        if not options:
            break
        et, direction, nbr_role = rng.choice(options)
        existing = [nid for nid in set(trace) if node_roles_by_id.get(nid) == nbr_role]
        can_new = role_counters[nbr_role] < max_nodes // len(ROLES) + 1
        if existing and (not can_new or rng.random() < 0.5):
            nbr = rng.choice(existing)
        elif can_new:
            new_id = max(trace) + 1
            node_roles_by_id[new_id] = nbr_role
            role_counters[nbr_role] += 1
            trace.append(new_id)
            nbr = new_id
        else:
            break
        edge_labels.append((et, direction))
        cur = nbr
        depth += 1
    props = _properties(trace, edge_labels)
    node_count = max(trace) + 1
    return Skeleton(
        trace=tuple(trace),
        node_roles=tuple(node_roles_by_id[i] for i in range(node_count)),
        edge_labels=tuple(edge_labels),
        properties=props,
    )


def generate_prefix_shared_pairs(
    base_skeletons: list[Skeleton], *, share_fraction: float = 0.5,
    seed: int = 20260707, max_depth: int = 8, max_nodes: int = 9,
    max_attempts: int = 5000,
) -> list[tuple[Skeleton, Skeleton, int]]:
    """For each base skeleton, build a partner sharing the first k=share_fraction*len steps.

    Rejection-samples the continuation until the partner is valid (>=2 properties,
    has recurrence) AND has a different full signature from the base. Returns
    (base, partner, share_k) triples.
    """
    rng = random.Random(seed)
    pairs: list[tuple[Skeleton, Skeleton, int]] = []
    for base in base_skeletons:
        share_k = max(3, int(len(base.trace) * share_fraction))
        if share_k >= len(base.trace):
            continue
        attempts = 0
        chosen = None
        base_key = base.signature_key()
        while attempts < max_attempts:
            attempts += 1
            cand = _continue_prefix(rng, base, share_k, max_total_depth=max_depth, max_nodes=max_nodes)
            if len(cand.properties) < 2:
                continue
            if len(set(cand.trace)) == len(cand.trace):  # reject pure paths
                continue
            if cand.signature_key() == base_key:
                continue
            # must actually share the prefix
            if cand.trace[:share_k] != base.trace[:share_k]:
                continue
            if cand.edge_labels[: share_k - 1] != base.edge_labels[: share_k - 1]:
                continue
            # DIVERGENCE CHECK (bugfix): the partner must (a) have at least one
            # step past the shared prefix, and (b) actually differ from the base
            # at index share_k (different canonical node id OR different edge
            # label). Without this, a truncated prefix of the base passes all
            # prior checks (its full signature trivially differs because it is
            # shorter) and produces a fake 'pair' with nothing to disambiguate.
            # This was the pair-7 defect: B was a 5-step prefix of a 9-step A.
            if len(cand.trace) <= share_k:
                continue
            node_diff = cand.trace[share_k] != base.trace[share_k] if share_k < len(base.trace) else True
            edge_diff = (
                share_k - 1 < len(cand.edge_labels) and share_k - 1 < len(base.edge_labels)
                and cand.edge_labels[share_k - 1] != base.edge_labels[share_k - 1]
            )
            if not (node_diff or edge_diff):
                continue
            chosen = cand
            break
        if chosen is not None:
            pairs.append((base, chosen, share_k))
    return pairs


def build_generated_graph_with_polysemy(
    *, n_disjoint_families: int, n_polysemy_bases: int, instances_per: int,
    seed: int = 20260706, max_depth: int = 8, max_nodes: int = 9,
    share_fraction: float = 0.5,
) -> tuple[TypedGraph, list[Skeleton], dict[str, list[Instance]],
           list[tuple[str, str, int]], dict[str, list[Instance]]]:
    """Generate disjoint families + polysemy pairs and emit one TypedGraph.

    Returns (graph, disjoint_skeletons, disjoint_instances, polysemy_pairs_meta,
    polysemy_instances). Polysemy pair families are named poly_A_NNN / poly_B_NNN
    so the relaxation can ask 'does the shared prefix keep both active?'
    """
    disjoint_skeletons = generate_skeletons(
        count=n_disjoint_families, seed=seed, max_depth=max_depth, max_nodes=max_nodes)
    # use a separate slice of base skeletons for polysemy so they don't collide
    poly_bases = generate_skeletons(
        count=n_polysemy_bases, seed=seed + 1, max_depth=max_depth, max_nodes=max_nodes)
    pairs = generate_prefix_shared_pairs(
        poly_bases, share_fraction=share_fraction, seed=seed + 2,
        max_depth=max_depth, max_nodes=max_nodes)

    all_instances: dict[str, list[Instance]] = {}
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []

    def emit(family: str, skel: Skeleton) -> None:
        insts = instantiate_skeleton(skel, family, instances_per)
        all_instances[family] = insts
        for inst in insts:
            for node_id, role in enumerate(skel.node_roles):
                nodes[inst.labels[node_id]] = role
            edges.extend(inst.edges)

    for idx, skel in enumerate(disjoint_skeletons):
        emit(f"gen_{idx:03d}", skel)

    polysemy_meta: list[tuple[str, str, int]] = []
    polysemy_instances: dict[str, list[Instance]] = {}
    for idx, (base, partner, share_k) in enumerate(pairs):
        fa = f"poly_A_{idx:03d}"
        fb = f"poly_B_{idx:03d}"
        emit(fa, base)
        emit(fb, partner)
        polysemy_meta.append((fa, fb, share_k))
        polysemy_instances[fa] = all_instances[fa]
        polysemy_instances[fb] = all_instances[fb]

    g = TypedGraph(nodes=nodes)
    for src, et, tgt in edges:
        g.out_edges.setdefault(src, []).append((et, tgt))
        g.in_edges.setdefault(tgt, []).append((et, src))
    for d in (g.out_edges, g.in_edges):
        for k in d:
            d[k].sort()
    return g, disjoint_skeletons, all_instances, polysemy_meta, polysemy_instances
