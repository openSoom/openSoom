# Air-quality measurement review

Cursor CLI completed a read-only review with the available `claude-fable-5-2-high` model (Claude Fable 5.2). It received a public hypothetical description of the metric and the three virtual cases, without facility records or repository access through the prompt. The rubric teams’ release assessment is separate.

| Failure raised by Fable | Product acceptance |
| --- | --- |
| Missing acquisition interval earns dwell credit | A skipped native container sequence or an interval exceeding the zone freshness window ends the observed span. The next in-range sample begins a zero-second span. |
| Clock advances after observations stop | Stale evidence takes the current span out of the live display and preserves the last measured duration. A new wall-clock tick alone cannot add duration. |
| A newer command borrows an earlier acknowledgement or baseline | Each command carries its own pre-action CSE record, site targets and matched ACK. Superseded windows stop. |
| Partial readings or replayed samples validate the target | Both PM2.5 and CO₂ must be present together. Replayed CINs cannot extend an interval. An equal-time conflict can invalidate the disputed point. |
| Post-action change presented as causal or as physical validation | The interface identifies virtual sensors. The article and scripts distinguish observed changes, equipment state and later field evaluation. |

The baseline is captured when the command is issued. First observed attainment is measured from the matched ACK. The demo profiles use their facility freshness window as the maximum admissible gap. The next acquisition can extend the observed span only when the sample is eligible. This interval describes available samples, including the explicit gap rule. It does not demonstrate continuous measurement between them.

[Focused regression tests](../../tests/test_air_quality_outcome.py) · [Native timed runs](../../evidence/runtime/air-quality-outcomes.json) · [Browser interaction](../../evidence/application/air-quality-dashboard.json) · [Rendered film](../../evidence/video/air-quality-film.json)
