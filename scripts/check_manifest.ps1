$ErrorActionPreference = 'Stop'
$packageRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\pnr_handoff'))
$manifestPath = Join-Path $packageRoot 'HANDOFF_MANIFEST.md'
$seenPaths = @{}
foreach ($row in (Get-Content -LiteralPath $manifestPath)) {
    if ($row -match '^\| `([^`]+)` \| (\d+) \| `([0-9a-fA-F]+)` \|$') {
        $relativePath = $Matches[1]
        $claimedSize = [long]$Matches[2]
        $claimedHash = $Matches[3]
        if ($seenPaths.ContainsKey($relativePath) -or $claimedHash.Length -ne 64) { throw "Invalid/duplicate entry: $relativePath" }
        $artifactPath = [IO.Path]::GetFullPath((Join-Path $packageRoot $relativePath))
        if (-not $artifactPath.StartsWith($packageRoot + [IO.Path]::DirectorySeparatorChar)) { throw "Outside package: $relativePath" }
        $artifact = Get-Item -LiteralPath $artifactPath
        $actualHash = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash
        if ($artifact.Length -ne $claimedSize -or $actualHash -ne $claimedHash) { throw "Hash/size mismatch: $relativePath" }
        $seenPaths[$relativePath] = $true
    }
}
$actualFiles = @(Get-ChildItem -LiteralPath $packageRoot -Recurse -File | Where-Object { $_.FullName -ne $manifestPath })
if ($seenPaths.Count -ne $actualFiles.Count) { throw 'Missing package files' }
$result = @{status='PASS'; files=$seenPaths.Count; manifest_sha256=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash}
$result | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot '..\evidence\review\final\powershell_manifest_check.json')
$result | ConvertTo-Json
