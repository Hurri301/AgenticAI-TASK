$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sourceRoot = Join-Path $repoRoot 'skill_updates\irap-width-facility-coder'
$targetRoot = Join-Path $repoRoot '.agents\skills\irap-width-facility-coder'

if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
    throw "Staged skill not found: $sourceRoot"
}
if (-not (Test-Path -LiteralPath $targetRoot -PathType Container)) {
    throw "Active skill not found: $targetRoot"
}

$relativeFiles = @(
    'SKILL.md',
    'references\coding-rules.md',
    'references\example_input.json',
    'references\input_contract.md',
    'references\intermediate_outputs.md',
    'references\sidewalk-passenger-prompt.md',
    'references\sidewalk-passenger-workflow.md',
    'references\tool_selection.md',
    'scripts\prepare_sidewalk_passenger_crops.py',
    'scripts\width_facility_router.py'
)

foreach ($relativePath in $relativeFiles) {
    $source = Join-Path $sourceRoot $relativePath
    $target = Join-Path $targetRoot $relativePath
    $targetParent = Split-Path $target
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Required staged file not found: $source"
    }
    if (-not (Test-Path -LiteralPath $targetParent -PathType Container)) {
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
}

foreach ($relativePath in $relativeFiles) {
    $source = Join-Path $sourceRoot $relativePath
    $target = Join-Path $targetRoot $relativePath
    $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    if ($sourceHash -ne $targetHash) {
        throw "Promotion verification failed: $relativePath"
    }
}

Write-Output "Promoted and verified $($relativeFiles.Count) files in $targetRoot"
