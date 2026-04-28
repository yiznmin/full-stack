# Adds Windows Defender exclusions for the dev environment.
# Root cause: Defender real-time scan slows / hangs Python C-extension loads (.pyd),
# which makes asyncpg / SQLAlchemy / uvicorn unusable in dev.
#
# Run ONCE as Administrator. Effect is permanent until removed.
# To remove later:
#   Remove-MpPreference -ExclusionPath '<path>'

$ErrorActionPreference = 'Stop'

Write-Host '[1/4] Excluding backend venv from Defender real-time scan...'
Add-MpPreference -ExclusionPath 'D:\website\PaintLearn\backend\venv'

Write-Host '[2/4] Excluding admin node_modules...'
Add-MpPreference -ExclusionPath 'D:\website\PaintLearn\admin\node_modules'

Write-Host '[3/4] Excluding Python interpreter process...'
Add-MpPreference -ExclusionProcess 'python.exe'

Write-Host '[4/4] Verifying...'
$exclusions = (Get-MpPreference).ExclusionPath
foreach ($path in 'D:\website\PaintLearn\backend\venv', 'D:\website\PaintLearn\admin\node_modules') {
    if ($exclusions -contains $path) {
        Write-Host "  OK  $path"
    } else {
        Write-Host "  FAIL $path"
    }
}

Write-Host ''
Write-Host 'Done. Python C-extensions should now load instantly.'
Write-Host 'Test by running: cd D:\website\PaintLearn\backend; .\venv\Scripts\python.exe scripts\diagnose_asyncpg.py'
