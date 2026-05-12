# Prepends elan's bin dir to PATH for this PowerShell session, then runs your command.
# Usage: .\scripts\with-lean.ps1 lean --version
#        .\scripts\with-lean.ps1 uv run lean2py examples\Add.lean -o .
$ElanBin = Join-Path $env:USERPROFILE ".elan\bin"
if (Test-Path $ElanBin) {
    $env:PATH = "$ElanBin;$env:PATH"
} else {
    Write-Warning "Elan bin not found at $ElanBin — install elan: https://github.com/leanprover/elan"
}
if ($args.Count -gt 0) {
    & @args
}
