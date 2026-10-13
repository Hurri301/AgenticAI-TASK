# iRAP Roadside Categories and Prompts

Use this file when you need:
- The allowed iRAP roadside category names.
- A compact 2-4 word object description per category.
- A simple GroundingDINO label for each description.

## Category Mapping

| iRAP category | Short description (2-4 words) | GroundingDINO label |
| --- | --- | --- |
| Cliff | cliff edge | cliff |
| Tree >=10cm | tree trunk | tree trunk |
| Rigid sign, post or pole >=10cm | sign pole | sign pole |
| Unprotected safety barrier end | barrier end | guardrail end |
| Aggressive vertical face | rock face | rock face |
| Upwards slope - roll over | earth embankment | earth embankment |
| Deep drainage ditch | deep ditch | drainage ditch |
| Downwards slope | steep roadside drop | steep slope |
| Low rigid object >=20cm high | low concrete wall | low wall |
| Rigid structure or building | retaining wall | retaining wall |
| Upwards slope - no roll over | steep cut slope | steep cut slope |
| Semi-rigid structure or building | brick boundary wall | brick wall |
| Safety barrier - concrete | concrete barrier | concrete barrier |
| Safety barrier - metal | metal guardrail | metal guardrail |
| Safety barrier - wire rope | wire rope barrier | wire rope barrier |
| Safety barrier - motorcycle friendly | motorcycle barrier rail | motorcycle barrier |
| No object | no roadside object | N/A |

## Guidance

1. Keep descriptions concrete and visual.
2. Use categories exactly as written here in output JSON.
3. Treat slope/ditch/cliff detections conservatively; they are often ambiguous in a single image.
4. If no valid object appears on one side, set that side to `No object`.
