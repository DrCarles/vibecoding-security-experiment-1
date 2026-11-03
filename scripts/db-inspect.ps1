<#
.SYNOPSIS
  Inspect the Chirp database (PowerShell version of db-inspect.sh).

.DESCRIPTION
  Queries run inside the db container in a read-only session, so nothing here can
  modify data (except the interactive 'psql' shell).

.EXAMPLE
  .\scripts\db-inspect.ps1 summary
  .\scripts\db-inspect.ps1 posts 50
  .\scripts\db-inspect.ps1 user alice
  .\scripts\db-inspect.ps1 sql "SELECT count(*) FROM posts"
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('summary', 'users', 'posts', 'user', 'integrity', 'media', 'sql', 'tables', 'psql', 'all', 'help')]
    [string]$Command = 'help',

    [Parameter(Position = 1)]
    [string]$Arg,

    [Parameter(Position = 2)]
    [string]$Arg2
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$SqlDir = Join-Path $PSScriptRoot 'sql'

# Pipe UTF-8 to docker and read UTF-8 back (Windows PowerShell defaults to ASCII/OEM).
# (No double quotes inside arguments below: Windows PowerShell 5.1 strips them.)
$Utf8 = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = $Utf8
[Console]::OutputEncoding = $Utf8

Push-Location $Root
try {
    function Invoke-Psql([string]$Sql, [string[]]$Vars = @()) {
        $psqlArgs = @()
        foreach ($v in $Vars) { $psqlArgs += @('-v', $v) }
        $inner = 'psql -X -q -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB -P pager=off -P null=NULL $@ -f -'
        $Sql | docker compose exec -T -e 'PGOPTIONS=-c default_transaction_read_only=on' db sh -c $inner psql @psqlArgs
        if ($LASTEXITCODE -ne 0) { throw "psql exited with code $LASTEXITCODE" }
    }

    function Invoke-SqlFile([string]$Name, [string[]]$Vars = @()) {
        Invoke-Psql (Get-Content -Raw -Encoding UTF8 (Join-Path $SqlDir "$Name.sql")) $Vars
    }

    function Invoke-MediaCheck {
        Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'check_media.py') |
            docker compose exec -T backend python -
    }

    function Get-Limit([string]$Value, [int]$Default) {
        if (-not $Value) { return $Default }
        if ($Value -notmatch '^[1-9][0-9]*$') { throw "Limit must be a positive number, got '$Value'" }
        return [int]$Value
    }

    switch ($Command) {
        'summary'   { Invoke-SqlFile 'summary' }
        'users'     { Invoke-SqlFile 'users' @("limit=$(Get-Limit $Arg 50)") }
        'posts'     { Invoke-SqlFile 'posts' @("limit=$(Get-Limit $Arg 20)") }
        'user' {
            if (-not $Arg) { throw 'Usage: db-inspect.ps1 user <username>' }
            Invoke-SqlFile 'user' @("username=$Arg", "limit=$(Get-Limit $Arg2 10)")
        }
        'integrity' { Invoke-SqlFile 'integrity' }
        'media'     { Invoke-MediaCheck }
        'sql' {
            if (-not $Arg) { throw 'Usage: db-inspect.ps1 sql "SELECT ..."' }
            Invoke-Psql $Arg
        }
        'tables'    { Invoke-Psql "\d+ users`n\d+ posts" }
        'psql'      { docker compose exec db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB' }
        'all' {
            Write-Host '######## SUMMARY';   Invoke-SqlFile 'summary'
            Write-Host '######## INTEGRITY'; Invoke-SqlFile 'integrity'
            Write-Host '######## MEDIA';     Invoke-MediaCheck
        }
        default     { Get-Help $PSCommandPath -Detailed }
    }
}
finally {
    Pop-Location
}
