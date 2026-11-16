# Local (non-Docker) backup on Windows: PostgreSQL dump + ChromaDB + uploads.
# Run from the project root in PowerShell:   .\deploy\backup_windows.ps1
# pg_dump asks for the database password (or set $env:PGPASSWORD first).
$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$dest = "backups\$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

pg_dump -U krishimitra -h localhost -d krishimitra -Fc -f "$dest\krishimitra.dump"
Compress-Archive -Path "knowledge_base" -DestinationPath "$dest\knowledge_base.zip"
Compress-Archive -Path "storage" -DestinationPath "$dest\storage.zip"

Get-ChildItem backups -Directory | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-14) } | Remove-Item -Recurse -Force
Write-Host "Backup written to $dest"
# Restore: pg_restore -U krishimitra -h localhost -d krishimitra --clean backups\<stamp>\krishimitra.dump
