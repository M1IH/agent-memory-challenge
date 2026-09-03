$ErrorActionPreference = "Stop"

$features = @(
    "Microsoft-Windows-Subsystem-Linux",
    "VirtualMachinePlatform"
)

foreach ($feature in $features) {
    $result = Enable-WindowsOptionalFeature `
        -Online `
        -FeatureName $feature `
        -All `
        -NoRestart
    Write-Host "$feature : $($result.State) RestartNeeded=$($result.RestartNeeded)"
}
