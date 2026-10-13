# GroundTruth Focused Attribute Values

Created: 2026-05-06  
Source: `GroundTruth.csv`  
Rows checked: 469

Purpose: summarize the values already used in the labelled dataset for the focused Step 2 attributes. The next task is to map each numeric value to the exact iRAP manual meaning.

| Attribute | Values found in `GroundTruth.csv` |
| --- | --- |
| Area type | `1` = 353, `2` = 116 |
| Number of lanes | `2` = 408, `1` = 33, `3` = 28 |
| Lane width | `2` = 434, `1` = 19, `3` = 16 |
| Street lighting | `1` = 275, `2` = 194 |
| Service road | `1` = 454, `2` = 15 |
| Sight distance | `1` = 466, `2` = 3 |
| Median Type | `11` = 296, `1` = 114, `13` = 16, `7` = 14, `2` = 10, `10` = 5, `3` = 5, `14` = 4, `5` = 3, `6` = 1, `4` = 1 |
| Delineation | `1` = 441, `2` = 28 |
| Roadside severity - driver side object | `1` = 176, `17` = 55, `11` = 53, `6` = 52, `12` = 47, `13` = 32, `2` = 26, `8` = 13, `4` = 11, `10` = 1, `5` = 1, `9` = 1, `3` = 1 |
| Roadside severity - passenger side object | `1` = 144, `11` = 72, `12` = 63, `8` = 59, `13` = 34, `6` = 33, `17` = 22, `9` = 21, `4` = 9, `2` = 7, `16` = 2, `14` = 2, `10` = 1 |
| Roadside severity - drivers side distance | `1` = 245, `2` = 203, `4` = 13, `3` = 8 |
| Roadside severity - passenger side distance | `2` = 265, `1` = 196, `3` = 7, `4` = 1 |
| Paved shoulder - drivers side | `3` = 328, `2` = 60, `4` = 49, `1` = 32 |
| Paved shoulder - passenger side | `3` = 215, `1` = 145, `2` = 61, `4` = 48 |
| Property access points | `4` = 309, `2` = 60, `3` = 51, `1` = 49 |
| Curvature | `1` = 238, `2` = 227, `3` = 4 |

## What This Means

The dataset is already coded in iRAP-style numeric labels. Our tools must therefore produce numeric codes, not only descriptions. The immediate next work is the codebook:

1. Extract each focused attribute's coding options from the manual.
2. Write the meaning of each number, for example `1 = not present` or `2 = present`.
3. Compare those meanings to the values above.
4. Use that table as the final output schema for every automated workflow.
