# Basin Retrieval: Structural Compatibility as a First-Stage Retrieval Objective

## Abstract

This paper describes a retrieval method for relational data that does not try to retrieve a single correct answer but works as a search-space compressor, retrieving a bounded basin of candidates for downstream ranking, reasoning, filtering, or inspection. The method makes a deliberately narrow claim: it compresses the candidate set. It does not claim to reason, infer semantic truth, or provide a complete memory substrate.

The mechanism is a canonical structural signature over relational walks. We assign node identity by first occurrence while walking the relational graph of the data, rather than using semantic labels. This was determined empirically — when we let labels define the first neighborhood they fragmented the compatible sets we needed to preserve.

On held-out retrieval, compression is domain-dependent: 34× on synthetic relational families, 32× on project-history content, up to 554× on temporal traces, and 12.7× on a domain the operator never saw during development (code call-graphs from unrelated repositories). Target inclusion is 1.0 throughout — the operator preserves the target on every corpus. Lexical and token-overlap baselines compress more aggressively on that fresh domain (66–540×) but drop inclusion to 0.02–0.35: they compress by losing the target. The operator's job is compression without losing the target, not selection.

---

## 1. Introduction

### The problem

Reasoning over an entire corpus is expensive. Most retrieval systems are evaluated by their ability to retrieve a single element from a ranked list, and this works fine on smaller sample sizes. As the problem space scales up, though, it becomes prohibitively expensive — both in computation and in time — to reason over everything the first stage failed to rule out. The cost that actually dominates downstream is not the rank of the correct item; it is how many candidates the downstream stage is forced to consider at all.

Conventional retrieval pipelines try to solve two problems at once: find the correct item, and return it ranked first. We think those are two different problems, and that the first-pass stage should only be responsible for the cheap one.

### The alternative

Conventional retrieval asks

> Which item is correct?

We investigate an alternative first-stage retrieval objective that asks a cheaper question instead. Correctness becomes the downstream stage's job; the first stage is responsible only for compatibility — returning a small set that preserves the target while eliminating everything structurally incompatible. We call this candidate-space compression. The method is a success when the basin is small and the target is in it, not when the target is ranked first.

The contribution of this paper is an operator that does exactly this for relational data, using a semantically indifferent structural key. The design choice that makes it work is negative: do not let semantic labels define the first-pass neighborhood. The operator is not a semantic retrieval system and does not try to be.

So the question the first stage answers is simply:

> Which small set of items could still be correct?

### Contributions

This paper contributes:

- a **first-stage structural retrieval operator that changes the retrieval objective from semantic identification to compatibility preservation**, retrieving bounded compatible basins for downstream processing — semantically indifferent, and evaluated by whether the target is preserved in the retrieved basin;
- a measured compression envelope, **domain-dependent but with perfect target inclusion throughout** (34× on synthetic relational families, 32× on project history, up to 554× on temporal traces, 12.7× on a fresh code-graph domain), contrasted against lexical and token-overlap baselines that compress more but fail to preserve the target.

---

## 2. Retrieval Objectives

The central move of this paper is conceptual: the first stage should not attempt semantic identification at all. It should change the retrieval objective from finding the correct item to preserving the compatible set. Compression is the consequence of that change, not the mechanism; once the first stage asks only what could still be correct, the basin it returns is expected to be substantially smaller than the original search space. We make the distinction concrete by naming two retrieval goals, because conflating them is where most of the wasted retrieval effort comes from.

### 2.1 Identity retrieval

The first goal is **find one object**. The system is scored on whether the correct item is ranked first. Vector nearest-neighbour search, dense embedding retrieval, and lexical methods like BM25 all live here. The metric is top-*k* accuracy or recall@*k*. The whole objective assumes that the corpus is the unit of cost and that a single best match exists and should surface immediately.

### 2.2 Compatibility retrieval

The second goal is **find all compatible continuations**. Given a partial query, the system should return the bounded set of items that remain possible — structurally consistent with everything observed so far — and aggressively discard everything that is not. We use two terms in a precise sense throughout:

> Two items are **compatible** if their canonical structural signatures remain consistent with the observed query prefix. Compatibility is a property of signature prefixes, not of semantic similarity, graph isomorphism, or prediction; the canonical signature is defined in Section 4.2.

> Throughout this paper, a basin is **bounded** if its size scales substantially below the indexed corpus. We mean empirically small relative to the store, not mathematically bounded.

The metric changes accordingly:

> small basin × target retained

replaces

> correct item ranked first.

We treat retrieval as compression, not selection. A retrieved basin of three items drawn from a hundred has compressed the search space 33×; whether the target was ranked first within those three is a separate, downstream question, and explicitly not this operator's job. The load-bearing metric is bundle reduction — the ratio of the full store to the retrieved basin — not top-1 accuracy.

### 2.3 Why the distinction matters

Identity retrieval and compatibility retrieval fail differently. Identity retrieval fails by ranking the wrong thing first. Compatibility retrieval fails by omitting the target (too aggressive) or by failing to compress (too permissive). Because the failure modes are different, the representations should be different. In particular, the semantic detail that helps an identity-retrieval system discriminate can be actively harmful to a compatibility-retrieval stage, because it fragments the very neighborhoods the stage is trying to preserve. This observation motivates the semantically indifferent encoding used throughout the paper; we leave its detailed investigation to companion work.

---

## 3. Basin Retrieval

We now describe the method conceptually, before any implementation detail. The operator takes a partial relational query and returns a bounded basin of compatible candidates.

```text
              ┌──────────────────────────────────────┐
              │   store of relational items          │
              │   (each item is a relational walk)   │
              └──────────────────┬───────────────────┘
                                 │
   ┌─────────────────────────────┴─────────────────────────────┐
   │  input  partial relational query (prefix of a walk)       │
   └─────────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────┐
              │   structural encoding                │   label-free;
              │   (canonical recurrence signature)   │   position, not
              └──────────────────┬───────────────────┘   meaning
                                 │
                                 ▼
              ┌──────────────────────────────────────┐
              │   prefix lookup                      │   discrete
              │   (consistency pruning, not          │   elimination,
              │    graded scoring)                   │   not settling
              └──────────────────┬───────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────┐
              │   compatible basin                   │   bounded set
              │   (small active set,                 │   preserving the
              │    target preserved)                 │   target
              └──────────────────┬───────────────────┘
                                 │
                                 ▼
              ┌─────────────────────────────────────┐
              │   semantic refinement (downstream)  │   labels, content,
              │                                     │   ranking, reasoning
              └─────────────────────────────────────┘
```

**Figure 1.** The basin-retrieval pipeline. The first stage — structural encoding, prefix lookup, compatible basin — is the operator this paper contributes. It is semantically indifferent and returns a bounded basin. Semantic refinement happens after the basin is formed, never before.

The decisive property is the ordering. We retrieve the basin before any semantic information is allowed to influence the result, so compression is robust to the presence or absence of labels. Two items with different concrete labels but the same relational structure produce the same retrieval key and land in the same basin. The operator compresses on structure; a later stage discriminates on content.

We precompute the relational traces as signatures, and use the signature of the query object as the lookup for like traces. For example with temporal traces, if a chain of events is given `A -> B -> C -> A`, querying it over a corpus of state sequences naturally returns all sequences that contain that signature — which is exactly the set of futures still available given that prefix.

---

## 4. One Structural Realization

The preceding sections define the retrieval objective: retrieve a bounded basin of structurally compatible candidates while preserving the target. That objective does not require any particular encoding. This section describes the specific realization evaluated in this paper.

The guiding design principle is simple:

> **The retrieval key should preserve structural compatibility without depending on semantic identity.**

We arrived at this design empirically rather than theoretically. During development we repeatedly found that allowing semantic labels to define the first retrieval neighborhood fragmented compatible candidate sets, reducing compression while providing no benefit to a stage whose only responsibility is compatibility preservation. The encoding presented here therefore deliberately ignores semantic identity during first-stage retrieval. Semantic information remains available to downstream stages after the basin has been formed.

### 4.1 Data model

Each stored item is represented as a relational structure that can be traversed as one or more walks. A query consists of a partial walk, producing an incomplete structural signature. Retrieval returns every stored item whose signature remains compatible with that observed prefix.

Labels are not removed from the data. They remain part of the stored payload and may describe entities, relation types, commands, observations, artifacts, or semantic content. The restriction is narrower: semantic labels are not permitted to define the first-stage retrieval key.

### 4.2 Canonical structural signatures

The realization evaluated in this paper represents each walk by its recurrence structure rather than its concrete node identities.

Nodes receive identifiers according to first occurrence during traversal. The first distinct node becomes `0`, the next unseen node becomes `1`, and subsequent visits reuse the existing identifier.

```text
walk:      A -> B -> A -> C -> B
signature: 0 -> 1 -> 0 -> 2 -> 1
```

The resulting signature records only the recurrence pattern. Distinct relational walks that share the same structural organization therefore produce identical retrieval keys despite differing entirely in their semantic labels.

This property is intentional. The objective of the first stage is not to distinguish between semantically different objects but to preserve every candidate that remains structurally compatible with the observed evidence.

Although this paper evaluates first-occurrence recurrence signatures, they are not claimed to be unique or optimal. Any encoding that preserves structural compatibility while remaining semantically indifferent could satisfy the retrieval contract established in Sections 2 and 3.

### 4.3 Basin retrieval

Retrieval is performed by prefix-consistency matching over the indexed structural signatures.

A partial query signature is compared against the stored signatures. Every stored item whose signature remains consistent with the observed prefix is retained. All structurally incompatible candidates are discarded.

The output is therefore a bounded compatibility basin rather than a ranked list.

Two consequences follow naturally from the retrieval objective.

First, retrieval is discrete rather than graded. Candidates either remain compatible with the observed structure or they do not. The operator performs elimination rather than scoring.

Second, retrieval success is evaluated differently from conventional search systems. The operator succeeds when it substantially reduces the candidate space while preserving the target within the returned basin. Ranking, semantic discrimination, and reasoning occur only after this structural reduction has completed.


We state this explicitly, because it future-proofs the result:

> **The specific encoding is not the primary contribution. Any encoding that preserves structural compatibility may be substituted.** The implementation presented here is one realization of the compatibility-retrieval objective introduced earlier. Its purpose is not to argue that first-occurrence recurrence signatures are the correct encoding, but to demonstrate that a semantically indifferent structural representation can satisfy the retrieval contract in practice.

---

## 5. Experiments

### Experimental question

> Can structural retrieval compress the candidate space while retaining the target?

Everything else is secondary. We do not evaluate ranking accuracy, because the operator is not a ranker.

### Datasets

Three sources, each relational but of different character:

1. **Synthetic relational families** — 20 disjoint generated families plus 10 polysemy bases (prefix-shared, divergent continuations), 68 stored items total. Used to measure clean compression and polysemy retention on held-out instances.
2. **Project history (LDGR)** — 32 items drawn from real observations, artifact descriptions, and report fragments. LDGR is a continuity tool our team uses that creates permanent event logs; we turned its workflow content into relational signatures to test the operator on natural rather than generated content.
3. **Temporal traces** — long-window workflow event logs (~6,400 sequences). Used to test the operator on genuinely temporal, high-volume content where the search space is large.
4. **Fresh-domain code call-graphs** — 2,552 typed walks extracted from the ASTs of four unrelated Python repositories (delta-top, rica, tdm, magi) the operator was not developed against. Functions become nodes; calls, inheritance, and imports become typed edges; bounded DFS walks become the indexed items. Used to test whether the compression envelope generalizes beyond the corpora that shaped the operator.

We index on a held-in split of each family and query the held-out members by their prefix, so compression is measured on structurally novel items rather than exact replay.

### Metrics

Only four, all serving the single question:

- **Candidate basin size** — mean number of items surviving retrieval (smaller is better).
- **Compression ratio** — store size ÷ basin size (larger is better).
- **Target inclusion** — fraction of queries in which the true item survives into the basin (must be 1.0 for the operator to be useful).
- **Coverage** — fraction of queries for which any non-empty basin is returned.

Nothing else. We deliberately do not report top-1 accuracy, because the operator does not rank.

---

## 6. Results

### 6.1 Compression and inclusion — the central result

On every content type we tested, the structural operator retrieves a small bounded basin containing the target while eliminating the overwhelming majority of the store:

| content | store size | retrieved basin | compression | inclusion |
|---|---:|---:|---:|---:|
| synthetic relational families (68 items) | 68 | 2.0 | **34×** | **1.0** |
| project history, LDGR (32 items) | 32 | 1.0 | **32×** | **1.0** |
| synthetic motifs, suffix set N=3 | 150 | ~2.1 | 23.9× | 1.0 (coverage 0.88) |
| temporal traces, long window (~6.4k seq) | ~6,400 | 11.5 | **554×** | 1.0 (coverage 1.0) |
| fresh-domain code call-graphs (~2.5k walks) | 1,255 | ~99 | **12.7×** | **1.0** |

Compression magnitude appears to track structural recurrence density. Target inclusion is 1.0 wherever the operator returns a non-empty basin, including on the domain it never saw during development. Compression scales with evidence length on the fresh domain: 1.7× at half-length prefixes rising to 12.7× at full evidence, with inclusion held at 1.0 across the sweep. Perfect inclusion is the invariant; compression magnitude is the variable.

### 6.2 Basin size and polysemy

Basins are small (1–2 items on relational content, ~11 on large temporal corpora), and the operator does not collapse polysemy to a single answer. A prefix shared by divergent families correctly activates all compatible basins (ambiguity retention 1.0), with mean shared-preface basin ~5.6 narrowing to ~1.15 once a disambiguating relation is added. Returning a small set rather than one answer is by design — the operator compresses for a downstream selector.

### 6.3 Baselines: compression versus inclusion

To check that the operator is not merely a worse compressor, we ran two fair baselines on the fresh-domain corpus under the same held-out protocol: a lexical token-prefix hash (shard by the concrete token sequence) and token-set Jaccard (return walks whose token-set overlap clears a threshold).

| method | compression | target inclusion | coverage |
|---|---:|---:|---:|
| basin-retrieval (typed) | **12.7×** | **1.0** | **1.0** |
| token-prefix-hash (lexical) | 540× | 0.025 | 0.025 |
| token-set-jaccard@0.5 | 82× | 0.244 | 0.278 |
| token-set-jaccard@0.3 | 66× | 0.353 | 0.423 |

The baselines compress more aggressively but lose the target: the lexical prefix-hash achieves 540× compression precisely because almost nothing survives, including the answer (inclusion 0.025). Token-overlap does better on inclusion but never reaches it. The operator sits at the safe end of the tradeoff — meaningful compression, perfect target preservation. That is the contribution: not maximum compression, but compression that does not discard the target.

### 6.4 What is stable and what is not

Compression magnitude is domain-dependent (12.7× on fresh code graphs versus 554× on temporal traces), but target inclusion is stable at 1.0 across every corpus, including the domain the operator never saw. The operator is a compression stage whose safety property generalizes; its compression magnitude appears to track the structural recurrence density of the content.

---

## 7. Discussion

What this paper changes is not an indexing scheme but a decomposition of the retrieval problem. Existing retrieval systems spend expensive semantic computation deciding what is *correct*. Basin retrieval deliberately postpones that decision. The first stage only decides what remains *possible*; discrimination among the possibilities is left to a later stage over a basin small enough to afford it.

Stated as a decomposition: instead of solving *identify the answer* in one stage, split it into (1) eliminate impossibilities, then (2) discriminate among the remaining possibilities. The operator in this paper is one realization of stage (1) — structurally incompatible items are eliminated, the target is preserved — but the decomposition is the deeper move. Any first-stage method that maximizes compression while preserving the target fills the same role.

The experiments say the decomposition is viable, not just the operator. Across four corpora including a domain the operator never saw, stage (1) alone removes 87–99.8% of the store while keeping the target (12.7×–554× compression at 1.0 inclusion). Lexical and token-overlap baselines fail the contract in the opposite direction: they compress more aggressively but drop inclusion to 0.02–0.35, eliminating the target along with everything else. A first stage that loses the answer is not a stage (2) can build on. The operator's contribution is satisfying the contract — compression that preserves the target — not maximum compression.

The concrete pipeline shape falls out of the decomposition: a semantically indifferent basin stage runs before, not instead of, semantic retrieval.

```text
LLM  →  basin retrieval (stage 1: eliminate impossibilities)  →  semantic retrieval (stage 2: discriminate)  →  reasoning
```

One observation from development motivated the semantically indifferent design and is reported here rather than investigated:

> During development we empirically found that introducing semantic information into the structural key consistently fragmented compatible neighborhoods. This motivated the deliberately semantically indifferent encoding used throughout the paper. A detailed investigation of semantic fragmentation is left to companion work.

A second observation — that retrieved candidates share structural prefixes and so naturally induce a relational graph — has been removed from this paper. It belongs in companion work that evaluates the graph as a downstream reasoning structure rather than a teaser.

---

## 8. Limitations

We are deliberately blunt here, because honest boundaries are what make a compression claim credible.

- **No semantic understanding.** The operator retrieves recorded relational structure. It does not interpret, infer, or reason over content.
- **No ranking.** It returns a set, not an ordering. Top-1 accuracy is out of scope by design.
- **Assumes structural recurrence.** Compression depends on recurrence in the underlying content. Structure-poor or label-only corpora will compress poorly.
- **Cannot distinguish structurally identical sequences.** Two items with the same recurrence shape are indistinguishable to the first stage; only a downstream semantic stage can separate them.
- **Deletion of identity-establishing evidence is destructive.** Because the encoding keys on first-occurrence position, removing the evidence that establishes recurrence identity can collapse the basin. Realistic redundant queries usually survive this, but adversarial deletion does not.
- **Not intended to replace embeddings.** Embeddings and dense retrieval solve a different problem (identity retrieval, Section 2.1). This operator is a stage that runs before them, not a substitute.
- **Compression magnitude is domain-dependent.** The fresh-domain test (code call-graphs) shows the operator generalizes to a domain it never saw, with perfect inclusion, but at lower compression (12.7× vs 34×). Compression appears to track structural recurrence density. Whether the envelope holds on documents and external knowledge graphs — domains structurally unlike code or workflow logs — remains open.

---

## 9. Conclusion

Structural compatibility is a different retrieval objective than semantic identity. By separating those objectives, a semantically indifferent first-stage retrieval operator can substantially reduce the search space — from 12.7× on a fresh code-graph domain to 554× on temporal traces — while preserving the target. Baselines compress more aggressively but fail to preserve it; the operator sits at the safe end of that tradeoff. It compresses without losing the answer; a downstream stage reasons.

---

## Reproducibility

All experiments run with seed `20260706`. The synthetic corpus is generated by a fixed relational-family generator (20 disjoint families + 10 polysemy bases); project-history content is the LDGR observation/artifact/report corpus; temporal traces are long-window workflow event logs; the fresh-domain corpus is extracted from four external Python repositories (delta-top, rica, tdm, magi). Code, raw result JSON, and the project history used as memory content are archived:

```text
GitHub:   https://github.com/hydra-dynamix/basin-retrieval
HF data:  https://huggingface.co/datasets/Bakobiibizo/basin-retrieval
```
