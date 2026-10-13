# Passenger-Side Object Detection

This dataset's passenger-side roadside is the **left forward crop** of the panorama.
Use the passenger crop `[1, 260, 600, 920]` as the primary detection region. This includes the visible lower road surface while stopping before the bonnet/black panorama artifact.

Projection orientation is checked per dataset folder before linking detections to LAS. A passenger crop remains the left forward roadside in the image; `flip_pano_u` only controls the image-to-world projection convention and must not redefine the passenger side.

## Include

- The paved edge and shoulder on the passenger side.
- The roadside immediately beyond that edge.
- Trees, poles, signs, barriers, walls, buildings, cliffs, slopes, ditches, and other iRAP hazards visible there.
- Adjacent-frame evidence from the same left roadside.

## Exclude

- The center and lower vehicle/bonnet region.
- The right-side roadside.
- The median and opposite carriageway.
- Objects beyond the passenger-side road edge that belong to another carriageway.
- Panorama stitching artifacts, crop borders, shadows, and moving vehicles.

## Decision Rules

1. Confirm travel direction and carriageway layout before interpreting left as passenger side.
2. Keep all plausible passenger-side candidates; do not collapse detection to one label before projection.
3. Preserve each candidate bbox and keep object type and measured distance tied to that same candidate.
4. Use adjacent left-side frames to reject transient detections and confirm barriers, trees, poles, walls, terrain, and barrier ends.
5. Apply the iRAP risk hierarchy only after candidate validation and distance measurement.
6. If the passenger side is ambiguous or the candidate belongs to the median/opposite carriageway, return a review flag rather than a guessed object.
