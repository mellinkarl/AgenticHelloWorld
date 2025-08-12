text = '''
# Methods

We evaluated a routing and refinement pipeline for large language models on a corpus of 312 English research abstracts collected in May 2024. Texts were deduplicated via normalized string matching and filtered to lengths between 120 and 280 tokens. The dataset was split 60/20/20 into train/dev/test (187/62/63 items) with stratification by domain label (biomedicine, computer science, and social science).
Two prompting strategies were compared: (A) instruction-only (baseline) and (B) instruction-plus-schema (ours). All models were queried with temperature = 0.2, top-p = 0.95, max\_tokens = 128, and nucleus sampling enabled. For each input we sampled k = 3 candidates and used a lightweight refiner that prefers candidates satisfying JSON schema constraints and penalizes hallucinated fields via a rule score (-1 per violation).
Routing proceeded in two stages. A rule router first inspected surface cues (presence of keywords “IRB,” “randomized,” “GPU,” or “regression”) to assign a tentative domain. An LLM router then confirmed or overrode this label using a short hypothesis prompt. When conflicts occurred, the refiner requested one re-generation with the stricter schema.
Evaluation on the test split used exact-match for schema validity, F1 for key-phrase extraction, and accuracy for domain routing. The baseline achieved 71.4% schema validity and 76.2% routing accuracy. Our method achieved 78.9% schema validity and 81.0% routing accuracy. Average latency per example was 842 ms (baseline) versus 1,036 ms (ours). To support downstream auditing, all runs logged a machine-readable diff between the best candidate and its refined counterpart, using a unified-diff format with contextual radius = 2.
'''

