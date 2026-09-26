Set-StrictMode -Version Latest

function ConvertTo-NativeCommandLineArgument {
    param([AllowEmptyString()][string]$Value)

    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }
    $quoted = [Text.StringBuilder]::new()
    [void]$quoted.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes++
            continue
        }
        if ($character -eq '"') {
            [void]$quoted.Append('\' * (($backslashes * 2) + 1))
            [void]$quoted.Append('"')
        }
        else {
            [void]$quoted.Append('\' * $backslashes)
            [void]$quoted.Append($character)
        }
        $backslashes = 0
    }
    [void]$quoted.Append('\' * ($backslashes * 2))
    [void]$quoted.Append('"')
    return $quoted.ToString()
}

function Invoke-BinaryPipeline {
    <#
    .SYNOPSIS
    Pipes bytes between two native processes without converting them to text.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$SourceFile,
        [Parameter(Mandatory = $true)][string[]]$SourceArguments,
        [Parameter(Mandatory = $true)][string]$DestinationFile,
        [Parameter(Mandatory = $true)][string[]]$DestinationArguments
    )

    $sourceInfo = [Diagnostics.ProcessStartInfo]::new()
    $sourceInfo.FileName = $SourceFile
    $sourceInfo.UseShellExecute = $false
    $sourceInfo.RedirectStandardOutput = $true
    $sourceInfo.RedirectStandardError = $true
    # Windows PowerShell 5.1 runs on .NET Framework, where ProcessStartInfo has
    # no ArgumentList property. Build a correctly quoted native command line so
    # the encrypted streaming backup works on the production Windows host too.
    $sourceInfo.Arguments = ($SourceArguments | ForEach-Object {
        ConvertTo-NativeCommandLineArgument $_
    }) -join ' '

    $destinationInfo = [Diagnostics.ProcessStartInfo]::new()
    $destinationInfo.FileName = $DestinationFile
    $destinationInfo.UseShellExecute = $false
    $destinationInfo.RedirectStandardInput = $true
    $destinationInfo.RedirectStandardError = $true
    $destinationInfo.Arguments = ($DestinationArguments | ForEach-Object {
        ConvertTo-NativeCommandLineArgument $_
    }) -join ' '

    $source = [Diagnostics.Process]::new()
    $source.StartInfo = $sourceInfo
    $destination = [Diagnostics.Process]::new()
    $destination.StartInfo = $destinationInfo
    try {
        if (-not $destination.Start()) {
            throw "Could not start destination process '$DestinationFile'."
        }
        $destinationError = $destination.StandardError.ReadToEndAsync()
        if (-not $source.Start()) {
            throw "Could not start source process '$SourceFile'."
        }
        $sourceError = $source.StandardError.ReadToEndAsync()

        $source.StandardOutput.BaseStream.CopyTo($destination.StandardInput.BaseStream)
        $destination.StandardInput.Close()
        $source.WaitForExit()
        $destination.WaitForExit()
        $sourceMessage = $sourceError.GetAwaiter().GetResult().Trim()
        $destinationMessage = $destinationError.GetAwaiter().GetResult().Trim()
        if ($source.ExitCode -ne 0) {
            throw "Source process failed with exit code $($source.ExitCode): $sourceMessage"
        }
        if ($destination.ExitCode -ne 0) {
            throw "Destination process failed with exit code $($destination.ExitCode): $destinationMessage"
        }
    }
    finally {
        if (-not $source.HasExited) {
            $source.Kill($true)
        }
        if (-not $destination.HasExited) {
            try {
                $destination.StandardInput.Close()
            }
            catch {
                # The child may already have closed its stdin after reporting an error.
            }
            $destination.Kill($true)
        }
        $source.Dispose()
        $destination.Dispose()
    }
}
