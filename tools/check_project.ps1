param(
    [string]$Python = 'python',
    [string]$Node = 'node'
)
$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location -LiteralPath $repository
try {
    & $Python -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
    if ($LASTEXITCODE -ne 0) { throw 'Python public-interface tests failed' }
    & $Node --test --test-isolation=none tests/renderer.test.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Presentation rendering tests failed' }
    & $Python -X utf8 tools/validate_plugin.py --plugin ppt-drawer --require-runtime --json
    if ($LASTEXITCODE -ne 0) { throw 'Plugin package validation failed' }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'Git whitespace check failed' }
} finally {
    Pop-Location
}
