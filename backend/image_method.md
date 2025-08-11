Awesome question. Here’s a **repeatable, step-by-step way to “read” any figure** (flowcharts, architecture diagrams, UML, networks, Sankey, timelines, etc.)—first the universal workflow, then quick playbooks for common diagram types, and finally a worked example using a figure from the PDF you shared.

# The universal 7-step workflow (works for almost any diagram)

1. **Classify the diagram**

   * What is it? (flowchart, architecture/block, sequence, state machine, tree/DAG, network, ER/UML, Sankey, timeline/Gantt, heatmap/confusion matrix, etc.)
   * Note the legend, axes, units, and color encodings if present.

2. **Index the primitives**

   * Nodes/boxes (what entities or steps exist?), edges/arrows (what connects to what, and in what direction?), containers/swimlanes (which group belongs to which subsystem?), symbols (diamond = decision, cylinder = DB, etc.).

3. **Extract structure**

   * Build a mental (or literal) graph: a list of `nodes` and `edges`. For edges, capture direction, labels/conditions, and multiplicity (one→many, many→many).
   * For charts (bar/line/heatmap), capture axes, series, scales, and encodings.

4. **Read the flow**

   * Start → end (or root → leaves). At each decision/branch, note conditions. For timelines/sequence/UML, go left→right or top→bottom strictly.

5. **Summarize semantics**

   * For each node: **inputs**, **operation/meaning**, **outputs**.
   * For each edge: **what is transferred** (data/control), **when** (condition), **direction** (cause/effect).

6. **Validate + compress**

   * Sanity checks: cycles where there shouldn’t be, missing joins, unlabeled axes, inconsistent units, arrows pointing both ways without reason.
   * Reduce to a concise narrative and (optionally) a machine-readable form (JSON / XMind Markdown / Mermaid).

7. **Answer your purpose**

   * If you need: troubleshooting → find bottlenecks/risks; implementation → map to modules/APIs; reporting → produce a clean summary; automation → emit JSON/CSV/XMind.

---

# Quick playbooks by diagram type

## Flowchart / process map

* Look for: **start/terminator**, **process rectangles**, **decision diamonds**, **loops**, **merge points**.
* Steps:

  1. Trace the main happy-path first.
  2. List each decision with its Yes/No (or condition) and destinations.
  3. Note loops and their exit conditions.
* Output skeleton:

  ```json
  {"nodes":[{"id":"start","type":"start"},...],
   "edges":[{"from":"A","to":"B","label":"yes"},...]}
  ```

## Architecture / block diagram

* Look for: **subsystems**, **data/control flows**, **stores/queues**, **external actors**.
* Steps:

  1. Identify containers (frontend, backend, memory, services).
  2. For each connection: protocol/payload/frequency (if shown).
  3. Mark sync vs async, hot path vs batch.

## Sequence diagram (UML)

* Left-to-right actors, time flows downward.
* Steps:

  1. List lifelines;
  2. Copy each message (name, sync/async, return);
  3. Note alt/loop fragments and their guards.

## State machine

* States (rounded rectangles), transitions (arrows), events/guards/actions on edges.
* Steps:

  1. Initial state;
  2. For each event: `state + event [guard] / action → next state`;
  3. Check for unreachable or terminal states.

## Tree / DAG / mind map / org chart

* Parent→children hierarchy, sometimes cross-links.
* Steps:

  1. Root;
  2. Per level: summarize siblings;
  3. For DAGs, list prerequisites (topological order).

## Network/graph (topology, dependency)

* Look for hubs, bridges, clusters; direction may matter.
* Steps:

  1. Degree of each node (in/out);
  2. Critical paths, cycles;
  3. Cut edges (single-point failures).

## ER/UML class

* Entities/classes + attributes; relationships with cardinality.
* Steps:

  1. Primary keys;
  2. 1:1, 1\:N, M\:N (and associative entities);
  3. Inheritance vs composition.

## Sankey/flow

* Width encodes magnitude.
* Steps:

  1. Verify totals (inputs≈outputs);
  2. Identify biggest contributors and losses;
  3. Track a single stream end-to-end.

## Timeline / Gantt

* Time axis; tasks with start/end; dependencies.
* Steps:

  1. Critical path;
  2. Slack;
  3. Resource overlaps.

## Heatmap / confusion matrix / ROC etc.

* Heatmap: check colorbar scale, row/col labels; look for clusters/outliers.
* Confusion matrix: read diagonal first (accuracy), then off-diagonal errors; compute precision/recall if needed.
* ROC/PR: higher AUC is better; compare curves at operating points.

---

# Worked example on your PDF (how I’d read it, step-by-step)

## Example A — Figure 2 “Framework of Free-MoRef Inference”

1. **Classify**: Architecture + flow (pipeline with parallel branches).&#x20;
2. **Index primitives**: Nodes include *Temporal Segmentation*, *Multi-Reference Split*, *Parallel Inference Chunks*, *Vision Encoder*, *MoRef-Attention* (with Flash-Attention, Gating Function), *Reference-Fusion*, *Default Decoder Layers*, and final *Answer*. Edges show data flowing from split → parallel chunks → attention → fusion → decoder.&#x20;
3. **Extract structure (JSON sketch)**:

   ```json
   {
     "nodes":[
       {"id":"seg","label":"Temporal Segmentation"},
       {"id":"split","label":"Multi-Reference Split"},
       {"id":"chunks","label":"Parallel Inference Chunks"},
       {"id":"enc","label":"Vision Encoder"},
       {"id":"attn","label":"MoRef-Attention (Flash Attention + Gating)"},
       {"id":"fuse","label":"Reference Fusion (mid-decoder)"},
       {"id":"dec","label":"Default Decoder Layers"},
       {"id":"ans","label":"Answer"}
     ],
     "edges":[
       {"from":"seg","to":"split"},{"from":"split","to":"chunks"},
       {"from":"chunks","to":"enc"},{"from":"enc","to":"attn"},
       {"from":"attn","to":"fuse"},{"from":"fuse","to":"dec"},
       {"from":"dec","to":"ans"}
     ],
     "parallelism":{"node":"chunks","mode":"N parallel references"}
   }
   ```
4. **Read the flow**: Long video is split into multiple reference chunks → each chunk is encoded → MoRef-Attention queries all chunks in parallel and aggregates a *unified activation* per layer → mid-decoder, *Reference-Fusion* merges key tokens into a global reference → remaining layers decode → answer.&#x20;
5. **Semantics**: The diagram implies **parallel reasoning** (gating weights over references) and later **cross-chunk interaction** via fusion to recover global context.&#x20;
6. **Validate**: Inputs/outputs labeled; direction clear; fusion timing (layer L) is annotated in text (details discussed near the figure).&#x20;
7. **Compress** (one-liner): *Split long vision tokens → parallel MoRef attention → fuse references mid-way → finish decoding.*&#x20;

## Example B — Figure 1 (design comparison + metrics)

* **Left**: design taxonomy vs. Free-MoRef (compression vs streaming vs MoRef); **Right**: FLOPs, latency (TTFT), and accuracy across frame budgets. Read bar/axis labels and compare paired conditions (64 vs 128 vs 128\@Free-MoRef). Takeaway: *MoRef improves accuracy with far fewer FLOPs and lower latency at extended context.*&#x20;

---

# Prompt templates you can reuse (LLM/VLM)

## Generic “diagram to JSON graph”

> You are extracting structure from a diagram image.
> Output **valid JSON** with this schema:
>
> ```
> {"nodes":[{"id":"...", "text":"...", "type":"(start|process|decision|store|actor|state|class|subsystem)"}],
>  "edges":[{"from":"...", "to":"...", "label":"...", "condition":"...", "direction":"(uni|bi)"}],
>  "groups":[{"id":"...", "label":"...", "members":["nodeId1","nodeId2"]}],
>  "meta":{"diagram_type":"...", "assumptions":[...]}}
> ```
>
> If a label/condition is missing, use null. If uncertain, add to `assumptions`. Do not invent nodes.

## Flowchart → steps

> From the JSON graph, produce a **numbered step list** of the main path, then list each decision with its conditions and destinations, then any loops with exit conditions.

## Architecture → interface table

> Build a table of subsystem→subsystem links with payload/protocol/frequency if present; otherwise leave blank and flag as assumption.

## Sankey/Confusion Matrix

> Read axis/legend precisely. Summarize top-3 flows (Sankey) OR major error modes (confusion matrix) and compute derived metrics if possible.

---

# Pitfalls (quick checklist)

* Unlabeled axes/units (never assume).
* Arrowhead ambiguity (confirm direction).
* Colors without a legend (treat as decorative unless legend exists).
* Overlapping lines (may indicate multiple edges—zoom in).
* Aggregated shapes (container vs node—check border/label style).

---

If you want, I can **convert any figure you paste here into JSON + a short human summary**, or into **XMind tab-indented text** ready to paste. If you point to a specific figure in your PDF, I’ll run the full 7-step process on it and hand you both outputs.
