param([string]$Version = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $Version) { $Version = (Get-Content VERSION -Raw).Trim() }
if (-not $Version) { throw "VERSION is empty." }

$dirty = git status --porcelain
if ($dirty) { throw "Release builds require a clean committed tree." }

$trackedPrivate = git ls-files state backups logs screenshots scratch scraped_wiki assets/templates
if ($trackedPrivate) {
    Write-Host $trackedPrivate
    throw "Private/generated runtime paths are tracked; refusing to build."
}

$sha = (git rev-parse HEAD).Trim()
$short = (git rev-parse --short=12 HEAD).Trim()
$dist = Join-Path $Root "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null
$name = "Realm-Grinder-Dragon-Tamer-Control-HUD-v$Version-$short.zip"
$artifact = Join-Path $dist $name
$temporaryArtifact = Join-Path $dist ("." + $name + "." + [Guid]::NewGuid().ToString("N") + ".tmp")
$backupArtifact = Join-Path $dist ("." + $name + "." + [Guid]::NewGuid().ToString("N") + ".bak")
try {
    git archive --format=zip --prefix="Realm_Grinder_Dragon_Tamer_Control_HUD-$Version/" -o $temporaryArtifact HEAD
    $archiveExitCode = $LASTEXITCODE
    if ($archiveExitCode -ne 0) { throw "git archive failed with exit code $archiveExitCode." }
    if (-not (Test-Path -LiteralPath $temporaryArtifact) -or (Get-Item -LiteralPath $temporaryArtifact).Length -eq 0) {
        throw "git archive reported success but did not produce a non-empty archive."
    }
    if (Test-Path -LiteralPath $artifact) {
        [System.IO.File]::Replace($temporaryArtifact, $artifact, $backupArtifact)
        Remove-Item -LiteralPath $backupArtifact -Force
    } else {
        [System.IO.File]::Move($temporaryArtifact, $artifact)
    }
} finally {
    if (Test-Path -LiteralPath $temporaryArtifact) { Remove-Item -LiteralPath $temporaryArtifact -Force }
    if (Test-Path -LiteralPath $backupArtifact) { Remove-Item -LiteralPath $backupArtifact -Force }
}
$hash = (Get-FileHash $artifact -Algorithm SHA256).Hash.ToLowerInvariant()
$manifest = [ordered]@{
    version = $Version
    commit = $sha
    artifact = $name
    sha256 = $hash
    source = "git archive of committed HEAD only"
}
$manifestPath = Join-Path $dist "release-manifest-$Version.json"
$manifest | ConvertTo-Json | Set-Content -Encoding utf8 $manifestPath

Write-Host "Built: $artifact"
Write-Host "SHA256: $hash"
Write-Host "Manifest: $manifestPath"
