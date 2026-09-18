# AcoustiForge Scaffold Validation
# Phase 0 repository hygiene and governance check

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Failures = 0

function Pass($Message) {
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Fail($Message) {
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    $script:Failures++
}

function Info($Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "============================================="
Write-Host " AcoustiForge Scaffold Validation"
Write-Host "============================================="
Write-Host "Repository: $RepoRoot"
Write-Host ""

# ------------------------------------------------------------
# Repository root
# ------------------------------------------------------------

if (Test-Path $RepoRoot) {
    Pass "Repository root exists"
}
else {
    Fail "Repository root does not exist"
}

# ------------------------------------------------------------
# Required Phase 0 directories
# ------------------------------------------------------------

$RequiredDirectories = @(
    "contracts",
    "data",
    "docs",
    "prompts",
    "scripts"
)

foreach ($Directory in $RequiredDirectories) {
    if (Test-Path (Join-Path $RepoRoot $Directory) -PathType Container) {
        Pass "Directory exists: $Directory"
    }
    else {
        Fail "Missing required directory: $Directory"
    }
}

# ------------------------------------------------------------
# Phase 0 directories that must NOT exist yet
# ------------------------------------------------------------

$DeferredDirectories = @(
    "src",
    "tests",
    ".kilo",
    ".project"
)

foreach ($Directory in $DeferredDirectories) {
    if (Test-Path (Join-Path $RepoRoot $Directory)) {
        Fail "Deferred directory unexpectedly exists: $Directory"
    }
}

# ------------------------------------------------------------
# Known inherited-project artifacts
# ------------------------------------------------------------

$ForbiddenArtifacts = @(
    ".kilo",
    ".project",
    "scripts/bootstrap-contracts.ps1",
    "scripts/contract-gate-0.ps1",
    "scripts/contract-gate-0.ps1.md",
    "scripts/contract_gate_0.py",
    "scripts/project-check.ps1",
    "scripts/project_check.ps1",
    "scripts/docker-check.ps1",
    "scripts/docker-lint.ps1",
    "scripts/docker-shell.ps1",
    "scripts/docker-test.ps1"
)

foreach ($Artifact in $ForbiddenArtifacts) {
    if (Test-Path (Join-Path $RepoRoot $Artifact)) {
        Fail "Inherited artifact detected: $Artifact"
    }
}

# ------------------------------------------------------------
# Required governance files
# ------------------------------------------------------------

$RequiredFiles = @(
    "prompts/MASTER_PROMPT.md",
    "prompts/PHASE_0_DISCOVERY.md",
    "docs/ARCHITECTURE.md",
    "scripts/validate_scaffold.ps1"
)

foreach ($File in $RequiredFiles) {
    if (Test-Path (Join-Path $RepoRoot $File) -PathType Leaf) {
        Pass "File exists: $File"
    }
    else {
        Fail "Missing required file: $File"
    }
}

# ------------------------------------------------------------
# Git repository
# ------------------------------------------------------------

git rev-parse --is-inside-work-tree *> $null

if ($LASTEXITCODE -eq 0) {
    Pass "Git repository initialized"
}
else {
    Fail "Git repository is not initialized"
}

# ------------------------------------------------------------
# Git remote
# ------------------------------------------------------------

$Origin = git remote get-url origin 2>$null

if ($LASTEXITCODE -eq 0 -and $Origin) {
    Info "Git remote: $Origin"

    if ($Origin -match "github\.com/radaikalam-lab/AcoustiForge") {
        Pass "Origin points to AcoustiForge GitHub repository"
    }
    else {
        Fail "Origin does not point to AcoustiForge GitHub repository"
    }
}
else {
    Fail "Git origin remote is not configured"
}

# ------------------------------------------------------------
# Top-level directory hygiene
# ------------------------------------------------------------

$AllowedTopLevel = @(
    ".git",
    "contracts",
    "data",
    "docs",
    "prompts",
    "scripts"
)

$TopLevelItems = Get-ChildItem -Force

foreach ($Item in $TopLevelItems) {

    if ($AllowedTopLevel -contains $Item.Name) {
        Pass "Recognized top-level directory: $($Item.Name)"
    }
    elseif ($Item.Name -eq ".git") {
        Pass "Git metadata directory present"
    }
    else {
        Fail "Unexpected top-level item: $($Item.Name)"
    }
}

# ------------------------------------------------------------
# Working tree state
# ------------------------------------------------------------

$Status = git status --short

if ($LASTEXITCODE -ne 0) {
    Fail "Unable to determine Git working tree status"
}
elseif ($Status) {
    Info "Working tree contains uncommitted/untracked content:"
    $Status | ForEach-Object {
        Write-Host "        $_"
    }
}
else {
    Pass "Working tree is clean"
}

# ------------------------------------------------------------
# Result
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================="

if ($Failures -eq 0) {
    Write-Host " RESULT: PASS" -ForegroundColor Green
}
else {
    Write-Host " RESULT: FAIL" -ForegroundColor Red
}

Write-Host " Failures: $Failures"
Write-Host "============================================="
Write-Host ""

if ($Failures -gt 0) {
    exit 1
}

exit 0