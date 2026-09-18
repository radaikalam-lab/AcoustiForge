$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$RequiredDirectories = @(
    ".kilo",
    ".project",
    "contracts",
    "data",
    "docs",
    "prompts",
    "scripts"
)

$RequiredFiles = @(
    # Intentionally empty at initial scaffold stage.
    # Files will become mandatory as phases are implemented.
)

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
# 1. Repository root
# ------------------------------------------------------------

if ((Test-Path $RepoRoot) -and ((Get-Item $RepoRoot).PSIsContainer)) {
    Pass "Repository root exists"
}
else {
    Fail "Repository root does not exist"
}

# ------------------------------------------------------------
# 2. Required directories
# ------------------------------------------------------------

foreach ($Dir in $RequiredDirectories) {

    $Path = Join-Path $RepoRoot $Dir

    if (Test-Path $Path -PathType Container) {
        Pass "Directory exists: $Dir"
    }
    else {
        Fail "Missing required directory: $Dir"
    }
}

# ------------------------------------------------------------
# 3. Required files
# ------------------------------------------------------------

foreach ($File in $RequiredFiles) {

    $Path = Join-Path $RepoRoot $File

    if (Test-Path $Path -PathType Leaf) {
        Pass "File exists: $File"
    }
    else {
        Fail "Missing required file: $File"
    }
}

# ------------------------------------------------------------
# 4. Git repository
# ------------------------------------------------------------

if (Test-Path (Join-Path $RepoRoot ".git")) {
    Pass "Git repository initialized"
}
else {
    Fail "Git repository not initialized"
}

# ------------------------------------------------------------
# 5. Git remote
# ------------------------------------------------------------

try {
    $Remote = git remote get-url origin 2>$null

    if ($Remote) {
        Info "Git remote: $Remote"

        if ($Remote -match "github\.com/radaikalam-lab/AcoustiForge") {
            Pass "Origin points to AcoustiForge GitHub repository"
        }
        else {
            Fail "Origin does not point to radaikalam-lab/AcoustiForge"
        }
    }
    else {
        Fail "No origin remote configured"
    }
}
catch {
    Fail "Unable to inspect Git remote"
}

# ------------------------------------------------------------
# 6. Unexpected top-level directories
# ------------------------------------------------------------

$AllowedDirectories = @(
    ".git",
    ".github",
    ".kilo",
    ".project",
    "contracts",
    "data",
    "docs",
    "prompts",
    "scripts",
    "src",
    "tests",
    "upstream",
    "hardware",
    "tools"
)

$TopLevelDirectories = Get-ChildItem -Path $RepoRoot -Directory -Force |
    Select-Object -ExpandProperty Name

foreach ($Dir in $TopLevelDirectories) {

    if ($AllowedDirectories -contains $Dir) {
        Pass "Recognized top-level directory: $Dir"
    }
    else {
        Write-Host "[WARN] Unrecognized top-level directory: $Dir" `
            -ForegroundColor Yellow
    }
}

# ------------------------------------------------------------
# 7. Check for accidental build/cache artifacts
# ------------------------------------------------------------

$ForbiddenPatterns = @(
    "bin",
    "obj",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "node_modules"
)

foreach ($Pattern in $ForbiddenPatterns) {

    $Found = Get-ChildItem `
        -Path $RepoRoot `
        -Directory `
        -Force `
        -Recurse `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $Pattern }

    if ($Found) {
        Write-Host "[WARN] Build/cache directory detected: $Pattern" `
            -ForegroundColor Yellow
    }
}

# ------------------------------------------------------------
# 8. Git status
# ------------------------------------------------------------

try {
    $Status = git status --short

    if ($Status) {
        Info "Working tree contains uncommitted/untracked content:"
        $Status | ForEach-Object {
            Write-Host "       $_"
        }
    }
    else {
        Pass "Git working tree is clean"
    }
}
catch {
    Fail "Unable to inspect Git status"
}

# ------------------------------------------------------------
# Final result
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================="

if ($Failures -eq 0) {
    Write-Host " RESULT: PASS" -ForegroundColor Green
    Write-Host " Scaffold is structurally valid."
}
else {
    Write-Host " RESULT: FAIL" -ForegroundColor Red
    Write-Host " Failures: $Failures"
}

Write-Host "============================================="
Write-Host ""

exit $Failures