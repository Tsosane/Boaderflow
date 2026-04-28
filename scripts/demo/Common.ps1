function Get-BorderFlowRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Get-ComposeFile {
    return (Join-Path (Get-BorderFlowRoot) "infra\docker-compose.yml")
}

function Resolve-ServiceName {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("depot", "border", "port", "hub", "tower")]
        [string]$Site,

        [Parameter(Mandatory = $true)]
        [ValidateSet("api", "worker", "db", "redis")]
        [string]$Kind
    )

    return "$($Site.ToLowerInvariant())-$Kind"
}

function Get-ServiceContainerId {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    $composeFile = Get-ComposeFile
    $containerId = (& docker compose -f $composeFile ps -q $ServiceName).Trim()
    if (-not $containerId) {
        throw "No running container found for service '$ServiceName'. Bring the stack up first."
    }

    return $containerId
}
