# Runs one unittest suite exactly as the local runs do: PYTHONPATH = features src; contracts src; tests/<dir>; tests; repo root.
param([Parameter(Mandatory = $true)][string]$Dir)
$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = (@('packages/features/src', 'packages/option-contracts/src', "tests/$Dir", 'tests', '.') -join ';')
Remove-Item Env:M2B_MEMORY -ErrorAction SilentlyContinue
$py = if ($env:CI_PYTHON) { $env:CI_PYTHON } else { 'python' }
& $py -B -m unittest discover -s "tests/$Dir" -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw "suite $Dir failed with exit code $LASTEXITCODE" }
