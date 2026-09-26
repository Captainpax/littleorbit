#Requires -RunAsAdministrator

<#
.SYNOPSIS
Restricts the Little Orbit gateway to the Nginx Proxy Manager host.

.DESCRIPTION
Creates or updates one named inbound Windows Firewall rule. The rule permits
TCP traffic to the Little Orbit gateway only from the configured Nginx Proxy
Manager address. Unrelated firewall rules are never changed.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidatePattern('^(?:\d{1,3}\.){3}\d{1,3}$')]
    [string] $ProxyManagerAddress = '192.168.50.6',

    [ValidateRange(1, 65535)]
    [int] $GatewayPort = 8180
)

$displayName = 'Little Orbit Gateway - NPM only'
$existingRules = @(Get-NetFirewallRule -DisplayName $displayName -ErrorAction SilentlyContinue)

if ($existingRules.Count -eq 0) {
    if ($PSCmdlet.ShouldProcess($displayName, 'Create scoped inbound firewall rule')) {
        New-NetFirewallRule `
            -DisplayName $displayName `
            -Direction Inbound `
            -Action Allow `
            -Protocol TCP `
            -LocalPort $GatewayPort `
            -RemoteAddress $ProxyManagerAddress `
            -Profile Any | Out-Null
    }
}
else {
    foreach ($rule in $existingRules) {
        if ($PSCmdlet.ShouldProcess($rule.Name, 'Update scoped inbound firewall rule')) {
            $rule | Set-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -Profile Any
            $rule | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort $GatewayPort
            $rule | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress $ProxyManagerAddress
        }
    }
}

$configuredRule = Get-NetFirewallRule -DisplayName $displayName
$portFilter = $configuredRule | Get-NetFirewallPortFilter
$addressFilter = $configuredRule | Get-NetFirewallAddressFilter

[pscustomobject]@{
    DisplayName   = $configuredRule.DisplayName
    Enabled       = $configuredRule.Enabled
    Action        = $configuredRule.Action
    Protocol      = $portFilter.Protocol
    LocalPort     = $portFilter.LocalPort
    RemoteAddress = $addressFilter.RemoteAddress
}
