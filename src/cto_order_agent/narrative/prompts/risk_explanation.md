# Risk explanation mode

Produce a short explanation for a production planner, in this order:

1. **Position** — one sentence: is the order at risk, and how severely.
2. **Confirmed facts** — bullet per fact, each prefixed with its `fact_id` and the label
   "(confirmed fact)".
3. **Inferred risks** — bullet per inference, each prefixed with its `inference_id` and the label
   "(inferred risk, confidence <level>)". State what would change the conclusion.
4. **Recommended actions** — bullet per recommendation, prefixed with `recommendation_id`, the
   urgency, the owning role, and the evidence that would confirm resolution.

Do not summarise beyond the bundle. Do not speculate about causes that are not in the bundle. If a
fact is missing that a planner would obviously want, say it is missing rather than filling it in.
