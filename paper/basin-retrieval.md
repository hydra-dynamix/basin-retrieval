# Basin Retrieval: Structural Compatibility as a First-Stage Search-Space Compression Operator

## Abstract

This paper describes a retrieval method for relational data that does not try to retrieve a single correct answer but works as a search-space compressor, retrieving a bounded basin of candidates for downstream ranking, reasoning, filtering, or inspection. The method makes a deliberately narrow claim: it compresses the candidate set. It does not claim to reason, infer semantic truth, or provide a complete memory substrate.

The mechanism is a canonical structural signature over relational walks. We assign node identity by first occurrence while walking the relational graph of the data, rather than using semantic labels. This was determined empirically — when we let labels define the first neighborhood they fragmented the compatible sets we needed to preserve.

On held-out retrieval experiments the signature naturally organizes the data into topological neighborhoods, compressing the problem space into a small basin 34× with a target inclusion rate of 1.0. We achieved similar results on project-history content (32×) and on temporal window traces where the problem had time as a component (up to 554×), again with perfect inclusion. The operator's job is compression, not selection.

---

## 1. Introduction

### The problem

Reasoning over an entire corpus is expensive. Most retrieval systems are evaluated by their ability to retrieve a single element from a ranked list, and this works fine on smaller sample sizes. As the problem space scales up, though, it becomes prohibitively expensive — both in computation and in time — to reason over everything the first stage failed to rule out. The cost that actually dominates downstream is not the rank of the correct item; it is how many candidates the downstream stage is forced to consider at all.

Conventional retrieval pipelines try to solve two problems at once: find the correct item, and return it ranked first. We think those are two different problems, and that the first-pass stage should only be responsible for the cheap one.

### The alternative

Instead of asking

> Which item is correct?

we ask a prior, cheaper question:

> Which small set of items could still be correct?

That reframing changes the retrieval objective. Correctness becomes the downstream stage's job; the first stage is responsible only for compatibility — returning a small bounded set guaranteed to contain the target while eliminating everything structurally incompatible. We call this candidate-space compression. The method should be considered a success when the basin is small and the target is in it, not when the target is ranked first.

The contribution of this paper is an operator that does exactly this for relational data, using a semantically indifferent structural key. The design choice that makes it work is negative: do not let semantic labels define the first-pass neighborhood.

### Contributions

This paper contributes:

- a **structural retrieval operator** for basin formation — a semantically indifferent first stage that compresses the candidate space;
- a measured compression envelope (34× on synthetic relational families, 32× on project history, up to 554× on temporal traces, with perfect target inclusion throughout).

---

## 2. Retrieval Objectives

This is the conceptual core of the paper. We claim there are two fundamentally different retrieval goals, and that conflating them is where most of the wasted effort comes from.

### 2.1 Identity retrieval

The first goal is **find one object**. The system is scored on whether the correct item is ranked first. Vector nearest-neighbour search, dense embedding retrieval, and lexical methods like BM25 all live here. The metric is top-*k* accuracy or recall@*k*. The whole objective assumes that the corpus is the unit of cost and that a single best match exists and should surface immediately.

### 2.2 Compatibility retrieval

The second goal is **find all compatible continuations**. Given a partial query, the system should return the bounded set of items that remain possible — structurally consistent with everything observed so far — and aggressively discard everything that is not. The metric changes accordingly:

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
              │   (small active set, target          │   containing
              │    retained by construction)         │   the target
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

## 4. Structural Encoding

We now describe the encoding, with only enough detail that someone could reproduce it.

### 4.1 Data model

Each stored item is represented as a relational structure that can be traversed as one or more walks. A query is a partial walk, or a partial signature derived from incomplete evidence. The retrieval problem is to find stored items whose canonical recurrence signatures remain compatible with the query prefix.

The method does not require labels to be absent from the data. Labels exist in the stored payload — they may describe nodes, relation types, artifacts, commands, outcomes, or semantic content. The rule is narrower: labels cannot define the first-pass retrieval key.

### 4.2 Canonical recurrence signatures

A relational walk is canonicalized by assigning node ids according to first occurrence. The first distinct node is `0`, the next unseen node is `1`, and so on. Later encounters reuse the earlier id. The signature therefore records recurrence structure rather than concrete identity:

```text
walk:       A -> B -> A -> C -> B
signature: 0 -> 1 -> 0 -> 2 -> 1
```

This signature is the core index key. It lets distinct label realizations share the same retrieval neighborhood when their recurrence pattern matches, which is the behavior the system needs for candidate compression. The sequence structure preserves reusable structural basins instead of splitting them by local surface vocabulary. It also does not necessarily have to be applied to temporally organized structures alone — it should work with any transition that encodes a sequence of relationships across a corpus of similar traces.

### 4.3 Basin retrieval

Retrieval is performed by discrete prefix-consistency pruning. A partial query signature is checked against the indexed signatures and matches are collected. The resulting candidate basin contains all previously encountered candidates that can still continue that sequence. We consider retrieval a success when the basin is small and includes the target.

We state this explicitly, because it future-proofs the result:

> **The specific encoding is not the primary contribution. Any encoding that preserves structural compatibility may be substituted.** Canonical first-occurrence recurrence signatures are the one we evaluate; they are not claimed to be unique or optimal. The encoding is also not specific to relational graphs — it applies to any discrete transition sequence, including temporal event streams captured by sliding windows (the 554× temporal result used the same canonical signature). The contribution is the objective — compatibility retrieval that compresses — and the evidence that the compression envelope holds across input domains.

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

We index on instances `0..k−2` of each family and query the held-out instance `k−1`, so compression is measured on structurally novel items rather than exact replay.

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

Compression ranges from ~24× on small synthetic motifs to 554× on large temporal traces. Target inclusion is 1.0 wherever the operator returns a non-empty basin.

### 6.2 Basin size and polysemy

Basins are small (1–2 items on relational content, ~11 on large temporal corpora), and the operator does not collapse polysemy to a single answer. A prefix shared by divergent families correctly activates all compatible basins (ambiguity retention 1.0), with mean shared-preface basin ~5.6 narrowing to ~1.15 once a disambiguating relation is added. Returning a small set rather than one answer is by design — the operator compresses for a downstream selector.

### 6.3 What is stable and what is not

Compression and inclusion are stable across all three content types. The operator is a compression stage, and compression is what the data show. We introduce no new concepts here.

---

## 7. Discussion

The operator changes the shape of a retrieval pipeline. Instead of

```text
LLM  →  vector retrieval  →  reason
```

we propose

```text
LLM  →  structural basin retrieval  →  semantic retrieval  →  reasoning
```

The basin-retrieval stage is a first-stage search-space reduction. It does not identify the answer; it removes everything structurally incompatible, leaving a small bounded basin that a downstream semantic or reasoning stage can afford to process in full. Because the first stage is semantically indifferent, it does not pay the cost of semantic specificity where that cost is purely harmful, and it does not fragment the neighborhoods the downstream stage will need.

This reframes what a retrieval stage is for. The first stage's job is not to be smart; it is to be cheap and safe — to compress aggressively while guaranteeing the target survives. Smart discrimination belongs later, over a basin small enough to afford it. The compression results in Section 6 say that cheap-and-safe is achievable: 34× on relational data, 554× on temporal traces, with perfect inclusion. Downstream stages receive a tractable candidate set rather than a corpus.

Two observations from development that motivate the design but fall outside this paper's scope:

> During development we empirically found that introducing semantic information into the structural key consistently fragmented compatible neighborhoods. This motivated the deliberately semantically indifferent encoding used throughout the paper. A detailed investigation of semantic fragmentation is left to companion work.

> Because retrieved candidates already share structural prefixes, they naturally induce a relational graph that downstream systems may exploit for ranking or reasoning. We leave quantitative evaluation of those downstream mechanisms to companion work.

---

## 8. Limitations

We are deliberately blunt here, because honest boundaries are what make a compression claim credible.

- **No semantic understanding.** The operator retrieves recorded relational structure. It does not interpret, infer, or reason over content.
- **No ranking.** It returns a set, not an ordering. Top-1 accuracy is out of scope by design.
- **Assumes structural recurrence.** Compression depends on recurrence in the underlying content. Structure-poor or label-only corpora will compress poorly.
- **Cannot distinguish structurally identical sequences.** Two items with the same recurrence shape are indistinguishable to the first stage; only a downstream semantic stage can separate them.
- **Deletion of identity-establishing evidence is destructive.** Because the encoding keys on first-occurrence position, removing the evidence that establishes recurrence identity can collapse the basin. Realistic redundant queries usually survive this, but adversarial deletion does not.
- **Not intended to replace embeddings.** Embeddings and dense retrieval solve a different problem (identity retrieval, Section 2.1). This operator is a stage that runs before them, not a substitute.
- **Evaluated only as a compression operator.** Every number in this paper is measured on relational/temporal workloads used to develop the method. Whether the compression envelope is a property of structural compatibility or a property of these corpora can only be settled by testing on domains that did not shape the operator (code, documents, external knowledge graphs). That test is open.

---

## 9. Conclusion

Structural compatibility is a different retrieval objective than semantic identity. By separating those objectives, a semantically indifferent first-stage retrieval operator can substantially reduce the search space — 34× on relational data, up to 554× on temporal traces — while preserving compatible candidates for downstream semantic processing. The operator is not a semantic retrieval system and does not try to be. It compresses; a downstream stage reasons.

---

## Reproducibility

All experiments run with seed `20260706`. The synthetic corpus is generated by a fixed relational-family generator (20 disjoint families + 10 polysemy bases); project-history content is the LDGR observation/artifact/report corpus; temporal traces are long-window workflow event logs. Code, raw result JSON, and the project history used as memory content are archived:

```text
GitHub:   https://github.com/hydra-dynamix/basin-retrieval
HF data:  https://huggingface.co/datasets/Bakobiibizo/basin-retrieval
```
