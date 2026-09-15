Set-StrictMode -Version Latest

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
    foreach ($argument in $SourceArguments) {
        [void]$sourceInfo.ArgumentList.Add($argument)
    }

    $destinationInfo = [Diagnostics.ProcessStartInfo]::new()
    $destinationInfo.FileName = $DestinationFile
    $destinationInfo.UseShellExecute = $false
    $destinationInfo.RedirectStandardInput = $true
    $destinationInfo.RedirectStandardError = $true
    foreach ($argument in $DestinationArguments) {
        [void]$destinationInfo.ArgumentList.Add($argument)
    }

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
