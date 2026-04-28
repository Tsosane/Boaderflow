param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("depot", "border", "port", "hub", "tower")]
    [string]$Site
)

. (Join-Path $PSScriptRoot "Common.ps1")

$networkName = "borderflow_net"
$dbService = Resolve-ServiceName -Site $Site -Kind "db"
$containerId = Get-ServiceContainerId -ServiceName $dbService
$inspect = & docker inspect $containerId | ConvertFrom-Json
$attachedNetworks = $inspect[0].NetworkSettings.Networks.PSObject.Properties.Name

if ($attachedNetworks -contains $networkName) {
    & docker network disconnect $networkName $containerId | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to disconnect $dbService from $networkName."
    }
    Write-Host "Partitioned $dbService from $networkName."
}
else {
    Write-Host "$dbService is already disconnected from $networkName."
}
