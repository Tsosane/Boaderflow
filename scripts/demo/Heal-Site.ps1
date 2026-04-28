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
    Write-Host "$dbService is already attached to $networkName."
}
else {
    & docker network connect $networkName $containerId | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to reconnect $dbService to $networkName."
    }
    Write-Host "Healed $dbService back onto $networkName."
}
