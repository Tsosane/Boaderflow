param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("depot", "border", "port", "hub", "tower")]
    [string]$Site
)

. (Join-Path $PSScriptRoot "Common.ps1")

$composeFile = Get-ComposeFile
$apiService = Resolve-ServiceName -Site $Site -Kind "api"
$workerService = Resolve-ServiceName -Site $Site -Kind "worker"

& docker compose -f $composeFile up -d $apiService $workerService
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start services for $Site."
}

Write-Host "Started $apiService and $workerService."
