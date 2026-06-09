param(
    [int]$Days = 1,
    [int]$Limit = 20,
    [switch]$Apply,
    [switch]$ForceApply,
    [switch]$NoWeb,
    [switch]$CodexReview,
    [switch]$CodexSearch
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Local venv is missing. Run .\scripts\setup_windows.ps1 first."
}

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*#" -or $_ -notmatch "=") { return }
        $name, $value = $_ -split "=", 2
        if ($name) {
            [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "Process")
        }
    }
}

$dbPath = $env:REKORDBOX_DB_PATH
if (-not $dbPath) {
    $dbPath = "C:\Users\Admin\AppData\Roaming\Pioneer\rekordbox\master.db"
}

$argsList = @(
    "rekordbox_set_agent.py",
    "--db", $dbPath,
    "--days", "$Days",
    "--limit", "$Limit"
)

if ($Apply) { $argsList += "--apply" }
if ($ForceApply) { $argsList += "--force-apply" }
if ($NoWeb) { $argsList += "--no-web" }
if ($CodexReview) { $argsList += "--codex-review" }
if ($CodexSearch) { $argsList += "--codex-search" }

& ".\.venv\Scripts\python.exe" @argsList
