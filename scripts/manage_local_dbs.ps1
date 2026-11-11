<#
.SYNOPSIS
    Zero-admin local database lifecycle manager for PostgreSQL 17 and MongoDB 9.
.DESCRIPTION
    Initializes, starts, stops, and checks user-space local database instances
    configured from case_study.json and .env (without hardcoded secrets).
#>
[CmdletBinding()]
param(
    [ValidateSet("init", "start", "stop", "status")]
    [string]$Action = "status",
    [string]$ToolsRoot = "$env:USERPROFILE\tools\databases",
    [string]$DataRoot = "$env:USERPROFILE\tools\database-data"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvPath = Join-Path $RepoRoot ".env"
$EnvExamplePath = Join-Path $RepoRoot ".env.example"
$CaseStudyPath = Join-Path $RepoRoot "case_study.json"

$PgBin = Join-Path $ToolsRoot "pgsql17\pgsql\bin"
$PgData = Join-Path $DataRoot "pg17"
$PgLog = Join-Path $DataRoot "pg17.log"

$MongoBin = Join-Path $ToolsRoot "mongodb9\bin"
$MongoData = Join-Path $DataRoot "mongo9"
$MongoLog = Join-Path $DataRoot "mongo9.log"
$MongoPid = Join-Path $DataRoot "mongo9.pid"

function New-RandomPassword {
    param([int]$Length = 20)
    $chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

function Read-DotEnv {
    $map = @{}
    if (Test-Path $EnvPath) {
        foreach ($line in Get-Content $EnvPath) {
            $trimmed = $line.Trim().TrimStart([char]0xFEFF)
            if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
            $k, $v = $trimmed.Split("=", 2)
            $map[$k.Trim().TrimStart([char]0xFEFF)] = $v.Trim()
        }
    }
    return $map
}

function Ensure-EnvFile {
    if (Test-Path $EnvPath) { return }
    if (-not (Test-Path $CaseStudyPath)) {
        throw "case_study.json not found at $CaseStudyPath"
    }
    $cs = Get-Content $CaseStudyPath -Raw | ConvertFrom-Json
    $shortCode = $cs.organisation.short_code
    $pgDb = $cs.databases.relational.database_name
    $mongoDb = $cs.databases.nosql.database_name

    $content = Get-Content $EnvExamplePath -Raw
    $content = $content.Replace("PGDATABASE=portfolio_db", "PGDATABASE=$pgDb")
    $content = $content.Replace("PGUSER=portfolio_app", "PGUSER=${shortCode}_app")
    $content = $content.Replace("PGPASSWORD=CHANGE_ME_LOCAL_DEV_PASSWORD", "PGPASSWORD=$(New-RandomPassword)")
    $content = $content.Replace("PGADMIN_PASSWORD=CHANGE_ME_ADMIN_PASSWORD", "PGADMIN_PASSWORD=$(New-RandomPassword)")
    $content = $content.Replace("MONGO_DATABASE=portfolio_nosql", "MONGO_DATABASE=$mongoDb")
    [System.IO.File]::WriteAllText($EnvPath, $content, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[OK] Created gitignored .env from .env.example and case_study.json"
}

function Start-LocalPostgres {
    $pgCtl = Join-Path $PgBin "pg_ctl.exe"
    $pgIsReady = Join-Path $PgBin "pg_isready.exe"
    if (-not (Test-Path $pgCtl)) { throw "PostgreSQL binaries not found at $PgBin" }
    & $pgCtl -D $PgData status *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] PostgreSQL already running"
        return
    }
    $postgresExe = Join-Path $PgBin "postgres.exe"
    Start-Process -FilePath $postgresExe -ArgumentList @(
        "-D", $PgData,
        "-p", $envCfg["PGPORT"]
    ) -RedirectStandardOutput $PgLog -RedirectStandardError ($PgLog + ".err") -WindowStyle Hidden | Out-Null

    for ($i = 0; $i -lt 30; $i++) {
        & $pgIsReady -h $envCfg["PGHOST"] -p $envCfg["PGPORT"] *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] PostgreSQL 17 started on port $($envCfg['PGPORT'])"
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "PostgreSQL 17 did not become ready within 15 seconds. Check $PgLog"
}

function Stop-LocalPostgres {
    $pgCtl = Join-Path $PgBin "pg_ctl.exe"
    if ((Test-Path $pgCtl) -and (Test-Path $PgData)) {
        & $pgCtl -D $PgData status *> $null
        if ($LASTEXITCODE -eq 0) {
            & $pgCtl -D $PgData stop -m fast | Out-Null
            Write-Host "[OK] PostgreSQL 17 stopped"
        }
    }
}

function Start-LocalMongo {
    $mongod = Join-Path $MongoBin "mongod.exe"
    if (-not (Test-Path $mongod)) {
        Write-Host "[SKIP] mongod.exe not present yet at $MongoBin"
        return
    }
    New-Item -ItemType Directory -Force -Path $MongoData | Out-Null
    $running = Get-Process mongod -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host "[OK] MongoDB already running (PID $($running.Id -join ','))"
        return
    }
    $proc = Start-Process -FilePath $mongod -ArgumentList @(
        "--dbpath", $MongoData,
        "--logpath", $MongoLog,
        "--port", "27017",
        "--bind_ip", "127.0.0.1"
    ) -WindowStyle Hidden -PassThru
    Set-Content -Path $MongoPid -Value $proc.Id -Encoding ASCII
    Start-Sleep -Seconds 2
    Write-Host "[OK] MongoDB 9 started (PID $($proc.Id))"
}

function Stop-LocalMongo {
    $running = Get-Process mongod -ErrorAction SilentlyContinue
    if ($running) {
        $running | Stop-Process -Force
        Write-Host "[OK] MongoDB stopped"
    }
}

Ensure-EnvFile
$envCfg = Read-DotEnv
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

switch ($Action) {
    "init" {
        $initdb = Join-Path $PgBin "initdb.exe"
        $psql = Join-Path $PgBin "psql.exe"
        if (-not (Test-Path $initdb)) { throw "initdb.exe not found at $PgBin" }

        if (-not (Test-Path (Join-Path $PgData "PG_VERSION"))) {
            $pwFile = Join-Path $DataRoot ".init_pw.tmp"
            try {
                [System.IO.File]::WriteAllText($pwFile, $envCfg["PGADMIN_PASSWORD"])
                & $initdb -D $PgData -U $envCfg["PGADMIN_USER"] -E UTF8 --locale=C --auth-local=scram-sha-256 --auth-host=scram-sha-256 --pwfile=$pwFile
                if ($LASTEXITCODE -ne 0) { throw "initdb failed with exit code $LASTEXITCODE" }
            } finally {
                if (Test-Path $pwFile) { Remove-Item $pwFile -Force }
            }
            Write-Host "[OK] Initialized PostgreSQL 17 cluster at $PgData"
        }

        Start-LocalPostgres

        $env:PGPASSWORD = $envCfg["PGADMIN_PASSWORD"]
        try {
            $appUser = $envCfg["PGUSER"]
            $appPass = $envCfg["PGPASSWORD"]
            $appDb = $envCfg["PGDATABASE"]
            if ($appUser -notmatch '^[a-zA-Z_][a-zA-Z0-9_]*$') { throw "Unsafe PGUSER identifier: $appUser" }
            if ($appDb -notmatch '^[a-zA-Z_][a-zA-Z0-9_]*$') { throw "Unsafe PGDATABASE identifier: $appDb" }

            $roleExists = (& $psql -h $envCfg["PGHOST"] -p $envCfg["PGPORT"] -U $envCfg["PGADMIN_USER"] -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$appUser'") | Out-String
            if ($roleExists.Trim() -ne "1") {
                & $psql -h $envCfg["PGHOST"] -p $envCfg["PGPORT"] -U $envCfg["PGADMIN_USER"] -d postgres -c "CREATE ROLE $appUser WITH LOGIN PASSWORD '$appPass';"
                if ($LASTEXITCODE -ne 0) { throw "Failed creating role $appUser" }
            }
            $dbExists = (& $psql -h $envCfg["PGHOST"] -p $envCfg["PGPORT"] -U $envCfg["PGADMIN_USER"] -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$appDb'") | Out-String
            if ($dbExists.Trim() -ne "1") {
                & $psql -h $envCfg["PGHOST"] -p $envCfg["PGPORT"] -U $envCfg["PGADMIN_USER"] -d postgres -c "CREATE DATABASE $appDb OWNER $appUser;"
                if ($LASTEXITCODE -ne 0) { throw "Failed creating database $appDb" }
            }
            Write-Host "[OK] Least-privilege role '$appUser' and database '$appDb' ready"
        } finally {
            Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
        }

        Start-LocalMongo
    }
    "start" {
        Start-LocalPostgres
        Start-LocalMongo
    }
    "stop" {
        Stop-LocalMongo
        Stop-LocalPostgres
    }
    "status" {
        $pgCtl = Join-Path $PgBin "pg_ctl.exe"
        if ((Test-Path $pgCtl) -and (Test-Path $PgData)) {
            & $pgCtl -D $PgData status
        } else {
            Write-Host "PostgreSQL: not initialized"
        }
        $m = Get-Process mongod -ErrorAction SilentlyContinue
        if ($m) {
            Write-Host "MongoDB: running (PID $($m.Id -join ','))"
        } else {
            Write-Host "MongoDB: stopped or not installed"
        }
    }
}
