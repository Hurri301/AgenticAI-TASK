# Attribute Rule Engine Implementation

Date: 2026-05-14

Purpose:
- Prevent the 17 iRAP attributes from being coded by the same image-only heuristic.
- Route each attribute to the right evidence source before prediction: visual scene, visual detection, segment context, trajectory context, or LAS measurement.

Implemented files:
- `src/mm_link/attribute_rules.py`
- `scripts/build_attribute_rule_plan.py`
- `tests/test_attribute_rules.py`

Validated image:
- `Dataset/16_N243/from-16/Portugal-16_000_601.jpg`

Generated artifacts:
- `artifacts/attribute_rule_engine_16_N243_601_2026-05-14/routing_plan.json`
- `artifacts/attribute_rule_engine_16_N243_601_2026-05-14/routing_plan.csv`

Routing result:
- 12 attributes ready from visual, detection, segment, or trajectory context.
- 5 attributes routed to measurement workflows:
  - `Lane width`
  - `Roadside severity - drivers side distance`
  - `Roadside severity - passenger side distance`
  - `Paved shoulder - drivers side`
  - `Paved shoulder - passenger side`

Key failure gates added from the previous pilot:
- Street lighting requires a visible luminaire/light head; utility poles or wires alone do not count.
- One-way/median logic now requires strong one-way evidence; otherwise undivided roads prefer the centre-line/undivided class.
- Lane width, roadside distances, and paved shoulder width are not final from image-only evidence.
- Property access uses segment context and should not be overridden by one visible shop sign.
- Sidewalk coding requires a continuous walkable passenger-side facility, not an isolated kerb or wall edge.

Verification:
- `python -m pytest tests\test_attribute_rules.py`
- Result: 5 passed.
