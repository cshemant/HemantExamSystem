param([ValidateSet('STAGING','PRELIVE','PRODUCTION')][string]$Profile='PRODUCTION')
$ErrorActionPreference='Stop';$projectDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath=Join-Path $projectDir '.code-runner.profiles.json';$python=Join-Path $projectDir '.venv-code-runner\Scripts\python.exe'
$mutex=New-Object Threading.Mutex($false,'Local\LearnWithHemantCodeRunner')
if(-not $mutex.WaitOne(0)){throw 'A compiler is already running on this computer. Use its existing window or stop it with Ctrl+C.'}
function Native([scriptblock]$Command,[string]$Message){$old=$ErrorActionPreference;$ErrorActionPreference='Continue';& $Command;$exit=$LASTEXITCODE;$ErrorActionPreference=$old;if($exit -ne 0){throw "$Message (exit $exit)."}}
function Docker-Ready{& cmd.exe /d /c 'docker info 1>nul 2>nul';return $LASTEXITCODE -eq 0}
function Piston-Ready{& cmd.exe /d /c 'curl.exe --fail --silent http://127.0.0.1:2000/api/v2/runtimes 1>nul 2>nul';return $LASTEXITCODE -eq 0}
function Wait-For([scriptblock]$Probe,[int]$Seconds){for($i=0;$i -lt $Seconds;$i+=2){if(& $Probe){return $true};Start-Sleep 2};return $false}
try{
    if (-not (Test-Path $configPath) -or -not (Test-Path $python)) { throw 'Run INSTALL_CODE_RUNNER.bat and CONFIGURE_CODE_RUNNER.bat first.' }
    $savedSdk=[Environment]::GetEnvironmentVariable('LWH_ANDROID_SDK_ROOT','User');$savedKey=[Environment]::GetEnvironmentVariable('LWH_ANDROID_DEBUG_KEYSTORE','User')
    if(-not $savedSdk -or -not(Test-Path $savedSdk) -or -not $savedKey -or -not(Test-Path $savedKey)){
        Write-Host 'Android builder is not installed yet. Installing it automatically...' -ForegroundColor Cyan
        & (Join-Path $projectDir 'setup_code_runner_windows.ps1')
        if($LASTEXITCODE -ne 0){throw 'Automatic Android builder installation did not complete.'}
    }
    $config=Get-Content -Raw $configPath|ConvertFrom-Json;$entry=$config.profiles.$Profile
    if(-not $entry){throw "$Profile is not configured. Run CONFIGURE_CODE_RUNNER.bat."}
    $secure=ConvertTo-SecureString $entry.token_dpapi;$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try{$token=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
    if(-not(Docker-Ready)){$desktop=Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe';if(Test-Path $desktop){Start-Process $desktop};Write-Host 'Waiting for Docker...' -ForegroundColor Cyan;if(-not(Wait-For{Docker-Ready}180)){throw 'Docker did not become ready.'}}
    if(-not(Piston-Ready)){& cmd.exe /d /c 'docker inspect learnwithhemant_piston 1>nul 2>nul';if($LASTEXITCODE -eq 0){Native{docker start learnwithhemant_piston}'Existing compiler container could not start'}else{Native{docker compose -f (Join-Path $projectDir 'docker-compose.code-runner.yml') up -d}'Compiler container could not be created'};Write-Host 'Waiting for compiler...' -ForegroundColor Cyan;if(-not(Wait-For{Piston-Ready}120)){throw 'Compiler health check failed.'}}
    $env:CODE_RUNNER_SERVER_URL=[string]$entry.server_url;$env:CODE_RUNNER_TOKEN=$token;$env:CODE_RUNNER_WORKERS=[string]$entry.workers
    $env:CODE_RUNNER_API_URL='http://127.0.0.1:2000/api/v2/execute';$env:CODE_RUNNER_NAME="$env:COMPUTERNAME-$Profile"
    $env:ANDROID_SDK_ROOT=[Environment]::GetEnvironmentVariable('LWH_ANDROID_SDK_ROOT','User');$env:ANDROID_HOME=$env:ANDROID_SDK_ROOT
    $env:ANDROID_DEBUG_KEYSTORE=[Environment]::GetEnvironmentVariable('LWH_ANDROID_DEBUG_KEYSTORE','User')
    if(-not $env:ANDROID_SDK_ROOT -or -not(Test-Path $env:ANDROID_SDK_ROOT)){throw 'Automatic Android SDK installation failed.'}
    if(-not $env:ANDROID_DEBUG_KEYSTORE -or -not(Test-Path $env:ANDROID_DEBUG_KEYSTORE)){throw 'Automatic Android signing-key creation failed.'}
    Write-Host "Connecting this computer securely to $Profile..." -ForegroundColor Cyan
    & $python (Join-Path $projectDir 'code_runner_worker.py')
}finally{try{$mutex.ReleaseMutex()}catch{};$mutex.Dispose()}
