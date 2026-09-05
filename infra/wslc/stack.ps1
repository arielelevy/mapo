<#
.SYNOPSIS
  Stack local de MAPO sobre wslc (contenedores nativos de WSL 2.9.10+). Reemplaza a
  docker compose, que wslc no trae.

.DESCRIPTION
  Levanta en orden: red `mapo`, volumen `mapo_pgdata`, Postgres 18 (ledger epistémico y
  persistencia de Temporal), Temporal server (auto-setup) y su UI.
  La contraseña de Postgres vive en HKCU:\Environment\MAPO_PG_PASSWORD, nunca en el repo.

.EXAMPLE
  .\stack.ps1 up        # crea lo que falte y arranca
  .\stack.ps1 down      # detiene y borra contenedores; conserva red y volumen
  .\stack.ps1 status    # ps + pg_isready + memoria de la VM
  .\stack.ps1 migrate   # aplica infra/postgres/*.sql pendientes al ledger
  .\stack.ps1 test      # corre infra/postgres/test_ledger.sql
  .\stack.ps1 psql      # shell psql sobre la base mapo
  .\stack.ps1 destroy   # down + borra el volumen (pierde el ledger)
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('up', 'down', 'status', 'migrate', 'test', 'psql', 'destroy', 'logs')]
  [string]$Action = 'status',
  [Parameter(Position = 1)]
  [string]$Target = 'mapo-temporal'
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$W = 'C:\Program Files\WSL\wslc.exe'
if (-not (Test-Path $W)) { throw "No está wslc.exe. Requiere WSL 2.9.3+ (wsl --update --pre-release)." }

$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$SqlDir = Join-Path $Root 'infra\postgres'

function Pw {
  $v = $env:MAPO_PG_PASSWORD
  if (-not $v) { $v = (Get-ItemProperty 'HKCU:\Environment' -Name MAPO_PG_PASSWORD -ErrorAction SilentlyContinue).MAPO_PG_PASSWORD }
  if (-not $v) { throw 'Falta MAPO_PG_PASSWORD (variable de usuario). Generarla antes de levantar el stack.' }
  return $v
}

function Exists($kind, $name) {
  $out = & $W $kind list 2>&1 | Out-String
  return ($out -match "(^|\s)$([regex]::Escape($name))(\s|$)")
}

function ContainerState($name) {
  $out = & $W ps -a 2>&1 | Out-String -Width 300
  $line = ($out -split "`n") | Where-Object { $_ -match "\s$([regex]::Escape($name))\s*$" }
  if (-not $line) { return 'absent' }
  if ($line -match '\sUp\s') { return 'up' }
  return 'stopped'
}

function EnsureRunning($name, [scriptblock]$run) {
  switch (ContainerState $name) {
    'up'      { Write-Host "  $name ya corre" }
    'stopped' { & $W start $name | Out-Null; Write-Host "  $name arrancado" }
    'absent'  { & $run | Out-Null; Write-Host "  $name creado" }
  }
}

function Up {
  $pw = Pw
  if (-not (Exists 'network' 'mapo'))        { & $W network create mapo | Out-Null; Write-Host '  red mapo creada' }
  if (-not (Exists 'volume' 'mapo_pgdata'))  { & $W volume create mapo_pgdata | Out-Null; Write-Host '  volumen mapo_pgdata creado' }

  EnsureRunning 'mapo-postgres' {
    & $W run -d --name mapo-postgres --network mapo `
      -e POSTGRES_USER=mapo -e "POSTGRES_PASSWORD=$pw" -e POSTGRES_DB=mapo `
      -p 5432:5432 -v mapo_pgdata:/var/lib/postgresql -m 512M postgres:18
  }
  $tries = 0
  do { Start-Sleep 2; $ok = (& $W exec mapo-postgres pg_isready -U mapo 2>&1 | Out-String) -match 'accepting'; $tries++ } until ($ok -or $tries -ge 15)
  if (-not $ok) { throw 'Postgres no respondió a tiempo.' }

  EnsureRunning 'mapo-temporal' {
    & $W run -d --name mapo-temporal --network mapo `
      -e DB=postgres12 -e DB_PORT=5432 -e POSTGRES_USER=mapo -e "POSTGRES_PWD=$pw" -e POSTGRES_SEEDS=mapo-postgres `
      -e DBNAME=temporal -e VISIBILITY_DBNAME=temporal_visibility `
      -p 7233:7233 -m 768M temporalio/auto-setup:latest
  }
  EnsureRunning 'mapo-temporal-ui' {
    & $W run -d --name mapo-temporal-ui --network mapo `
      -e TEMPORAL_ADDRESS=mapo-temporal:7233 -e TEMPORAL_CORS_ORIGINS=http://localhost:3000 `
      -p 8233:8080 -m 256M temporalio/ui:latest
  }
  Write-Host ''
  Write-Host 'Postgres  localhost:5432  base mapo, usuario mapo'
  Write-Host 'Temporal  localhost:7233'
  Write-Host 'UI        http://localhost:8233'
}

function Down {
  foreach ($c in 'mapo-temporal-ui', 'mapo-temporal', 'mapo-postgres') {
    if ((ContainerState $c) -ne 'absent') { & $W stop $c 2>&1 | Out-Null; & $W remove $c 2>&1 | Out-Null; Write-Host "  $c detenido y borrado" }
  }
}

function Status {
  & $W ps -a | Out-String -Width 220 | Write-Host
  if ((ContainerState 'mapo-postgres') -eq 'up') { & $W exec mapo-postgres pg_isready -U mapo }
  Get-Process vmmem*, wslservice -ErrorAction SilentlyContinue |
    ForEach-Object { '{0,-28} {1,6} MB' -f $_.ProcessName, [math]::Round($_.WorkingSet64 / 1MB) }
}

# psql escribe NOTICE por stderr y PowerShell 5.1 convierte stderr nativo en excepción:
# el 2>&1 se hace ADENTRO del contenedor, con sh, y el exit code se revisa a mano.
# Y todo SQL viaja por stdin: `wslc exec` parte por espacios los argumentos aunque vengan
# entrecomillados (medido 2026-09-05), así que un -c 'select ...' llega roto.
function PsqlStdin([string]$Text, [string[]]$ExtraArgs) {
  $pw = Pw
  $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  $Text | & $W exec -i -e "PGPASSWORD=$pw" mapo-postgres sh -c 'psql -U mapo -d mapo -v ON_ERROR_STOP=1 "$@" 2>&1' _ @ExtraArgs
  $code = $LASTEXITCODE; $ErrorActionPreference = $prev
  if ($code -ne 0) { throw "psql terminó con $code" }
}

function PsqlQuery([string]$Sql) { PsqlStdin $Sql @('-At') }

function PsqlFile([string]$File) { PsqlStdin (Get-Content -Raw -Encoding UTF8 $File) @() }

function PsqlShell {
  $pw = Pw
  & $W exec -i -t -e "PGPASSWORD=$pw" mapo-postgres psql -U mapo -d mapo
}

function Migrate {
  $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  $applied = (PsqlQuery 'select id from schema_migration' 2>&1 | Out-String) -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -notmatch 'ERROR|does not exist' }
  $ErrorActionPreference = $prev
  Get-ChildItem $SqlDir -File | Where-Object { $_.Name -match '^\d{3}_.*\.sql$' } | Sort-Object Name | ForEach-Object {
    $id = $_.BaseName
    if ($applied -contains $id) { Write-Host "  $id ya aplicada"; return }
    Write-Host "  aplicando $id"
    PsqlFile $_.FullName
  }
}

function Test { PsqlFile (Join-Path $SqlDir 'test_ledger.sql') }

switch ($Action) {
  'up'      { Up }
  'down'    { Down }
  'status'  { Status }
  'migrate' { Migrate }
  'test'    { Test }
  'psql'    { PsqlShell }
  'logs'    { & $W logs $Target }
  'destroy' { Down; if (Exists 'volume' 'mapo_pgdata') { & $W volume remove mapo_pgdata | Out-Null; Write-Host '  volumen mapo_pgdata borrado' } }
}
