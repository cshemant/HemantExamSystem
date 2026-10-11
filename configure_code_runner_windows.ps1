$ErrorActionPreference='Stop'
$projectDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath=Join-Path $projectDir '.code-runner.profiles.json'
$settingsPath=Join-Path $projectDir 'CODE_RUNNER_PROFILES.txt'

function Read-Settings {
    $v=@{}
    foreach($line in Get-Content -LiteralPath $settingsPath -ErrorAction SilentlyContinue){
        $line=$line.Trim();if(-not $line -or $line.StartsWith('#')){continue};$at=$line.IndexOf('=')
        if($at -gt 0){$v[$line.Substring(0,$at).Trim().ToUpperInvariant()]=$line.Substring($at+1).Trim()}
    };return $v
}
if(-not(Test-Path $settingsPath)){
@'
# Configure only the sites this computer may compile for.
PRODUCTION_SERVER_URL=https://exam.learnwithhemant.com
PRODUCTION_RUNNER_TOKEN=PASTE_PRODUCTION_RUNNER_TOKEN_HERE
PRODUCTION_WORKERS=1
STAGING_SERVER_URL=https://staging.exam.learnwithhemant.com
STAGING_RUNNER_TOKEN=
STAGING_WORKERS=1
PRELIVE_SERVER_URL=https://prelive.learnwithhemant.com
PRELIVE_RUNNER_TOKEN=
PRELIVE_WORKERS=1
'@ | Set-Content -Encoding UTF8 $settingsPath
}
Write-Host 'Enter the website URL and runner token, save, then close Notepad.' -ForegroundColor Yellow
Start-Process notepad.exe -ArgumentList ('"'+$settingsPath+'"') -Wait
$settings=Read-Settings;$profiles=@{}
foreach($name in @('PRODUCTION','STAGING','PRELIVE')){
    $url=[string]$settings["${name}_SERVER_URL"];$token=[string]$settings["${name}_RUNNER_TOKEN"]
    if(-not $token){continue}
    if($url -notmatch '^https://[^/]+/?$'){throw "$name server URL must be an HTTPS origin without a path."}
    if($token.Length -lt 32 -or $token -match 'PASTE_.*_HERE'){throw "$name runner token must be a real random secret of at least 32 characters."}
    $workers=0
    if (-not [int]::TryParse([string]$settings["${name}_WORKERS"],[ref]$workers) -or $workers -lt 1 -or $workers -gt 4) { throw "${name}_WORKERS must be 1 to 4." }
    $secureToken=ConvertTo-SecureString $token -AsPlainText -Force
    $encryptedToken=ConvertFrom-SecureString $secureToken
    $profiles[$name]=@{server_url=$url.TrimEnd('/');token_dpapi=$encryptedToken;workers=$workers}
}
if ($profiles.Count -eq 0) { throw 'Enter at least one runner token and run CONFIGURE_CODE_RUNNER.bat again.' }
@{profiles=$profiles}|ConvertTo-Json -Depth 5|Set-Content -Encoding UTF8 $configPath
Write-Host "Configured: $($profiles.Keys -join ', '). No database or Google Cloud credentials are stored." -ForegroundColor Green
Write-Host 'Keep CODE_RUNNER_PROFILES.txt private because it contains runner tokens.' -ForegroundColor Yellow
