$ErrorActionPreference = 'Stop'
$pgdata = 'C:\Program Files\PostgreSQL\17\data'
$psql = 'C:\Program Files\PostgreSQL\17\bin\psql.exe'
$service = 'postgresql-x64-17'
$conf = Join-Path $pgdata 'pg_hba.conf'
$backup = Join-Path $pgdata 'pg_hba.conf.bak'

Write-Host '[0/5] Ensuring service is stopped...'
$svc = Get-Service $service -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq 'Running') { Stop-Service $service }

if (Test-Path $backup) {
    Write-Host '[1/5] Restoring previous pg_hba.conf backup...'
    Move-Item -Force $backup $conf
}

Write-Host '[2/5] Rewriting pg_hba.conf to trust mode (ASCII no BOM)...'
Copy-Item $conf $backup -Force
$lines = [System.IO.File]::ReadAllLines($conf)
$newLines = foreach ($line in $lines) {
    if ($line -match '^(host|local|hostssl|hostnossl)\s+') {
        $line -replace '(scram-sha-256|md5|password)\s*$', 'trust'
    } else {
        $line
    }
}
[System.IO.File]::WriteAllLines($conf, $newLines, [System.Text.ASCIIEncoding]::new())

Write-Host '[3/5] Starting service with trust auth...'
Start-Service $service
Start-Sleep -Seconds 3

Write-Host '[4/5] Resetting postgres password to dev123...'
& $psql -U postgres -h localhost -p 1128 -d postgres -c "ALTER USER postgres PASSWORD 'dev123';"

Write-Host '[5/5] Restoring pg_hba.conf and restarting...'
Move-Item -Force $backup $conf
Restart-Service $service
Start-Sleep -Seconds 2

Write-Host ''
Write-Host 'Done! v17 postgres password reset to: dev123'
Write-Host 'URL: postgresql://postgres:dev123@localhost:1128/postgres'
