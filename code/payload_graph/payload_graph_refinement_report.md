# Payload Graph Projection Refinement

Memory content: LDGR historical findings. Coarse key: generic label-free recurrence motif. Payload: semantic/content graph connecting data inside the motif.

Real payload graphs: 32
Rewired decoys: 32

## Aggregate Results

| pool | scorer | top1 | target in top tie | target rank | top tie | bundle | reduction |
|---|---|---:|---:|---:|---:|---:|---:|
| real_only | coarse_only | 0.0 | 1.0 | 16.5 | 32.0 | 32.0 | 1.0 |
| real_only | node_bag | 0.7969 | 1.0 | 1.3516 | 1.7031 | 1.7031 | 27.25 |
| real_only | relation_topology | 0.0 | 1.0 | 16.5 | 32.0 | 32.0 | 1.0 |
| real_only | content_graph | 0.7969 | 1.0 | 1.3516 | 1.7031 | 1.7031 | 27.25 |
| real_plus_rewired_decoys | coarse_only | 0.0 | 1.0 | 16.5 | 64.0 | 64.0 | 1.0 |
| real_plus_rewired_decoys | node_bag | 0.0 | 1.0 | 1.3516 | 3.4062 | 3.4062 | 27.25 |
| real_plus_rewired_decoys | relation_topology | 0.0 | 1.0 | 16.5 | 64.0 | 64.0 | 1.0 |
| real_plus_rewired_decoys | content_graph | 0.7969 | 1.0 | 1.3516 | 1.7031 | 1.7031 | 54.5 |

## Decoy Pool By Query Mode

### core

| scorer | top1 | target in top tie | top tie | bundle | reduction | decoy rate |
|---|---:|---:|---:|---:|---:|---:|
| coarse_only | 0.0 | 1.0 | 64.0 | 64.0 | 1.0 | 0.5 |
| node_bag | 0.0 | 1.0 | 2.0 | 2.0 | 32.0 | 0.5 |
| relation_topology | 0.0 | 1.0 | 64.0 | 64.0 | 1.0 | 0.5 |
| content_graph | 1.0 | 1.0 | 1.0 | 1.0 | 64.0 | 0.0 |

### partial

| scorer | top1 | target in top tie | top tie | bundle | reduction | decoy rate |
|---|---:|---:|---:|---:|---:|---:|
| coarse_only | 0.0 | 1.0 | 64.0 | 64.0 | 1.0 | 0.5 |
| node_bag | 0.0 | 1.0 | 2.0 | 2.0 | 32.0 | 0.5 |
| relation_topology | 0.0 | 1.0 | 64.0 | 64.0 | 1.0 | 0.5 |
| content_graph | 1.0 | 1.0 | 1.0 | 1.0 | 64.0 | 0.0 |

### noisy

| scorer | top1 | target in top tie | top tie | bundle | reduction | decoy rate |
|---|---:|---:|---:|---:|---:|---:|
| coarse_only | 0.0 | 1.0 | 64.0 | 64.0 | 1.0 | 0.5 |
| node_bag | 0.0 | 1.0 | 2.0 | 2.0 | 32.0 | 0.5 |
| relation_topology | 0.0 | 1.0 | 64.0 | 64.0 | 1.0 | 0.5 |
| content_graph | 1.0 | 1.0 | 1.0 | 1.0 | 64.0 | 0.0 |

### topic_mechanism

| scorer | top1 | target in top tie | top tie | bundle | reduction | decoy rate |
|---|---:|---:|---:|---:|---:|---:|
| coarse_only | 0.0 | 1.0 | 64.0 | 64.0 | 1.0 | 0.5 |
| node_bag | 0.0 | 1.0 | 7.625 | 7.625 | 13.0 | 0.5 |
| relation_topology | 0.0 | 1.0 | 64.0 | 64.0 | 1.0 | 0.5 |
| content_graph | 0.1875 | 1.0 | 3.8125 | 3.8125 | 26.0 | 0.0 |

## Interpretation

The rewired-decoy pool is the decisive control. Each decoy has the same payload nodes and same relation-label multiset as its paired real item, but different semantic connections. If node-bag and relation-topology tie while content_graph isolates the original, then the stored payload graph connections are doing refinement work beyond flat overlap.
