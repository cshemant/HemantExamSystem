$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$cliDir = Join-Path $projectDir "code-runner-cli"

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Test-DockerEngine {
    # Windows PowerShell 5.1 turns native stderr into NativeCommandError when
    # ErrorActionPreference is Stop. Docker emits a normal connection message
    # while Desktop is starting, so probe through cmd.exe and inspect only the
    # exit code instead of terminating the installer.
    & cmd.exe /d /c "docker info 1>nul 2>nul"
    return ($LASTEXITCODE -eq 0)
}

function Try-DockerContexts {
    foreach ($contextName in @('desktop-linux', 'default')) {
        & cmd.exe /d /c "docker context use $contextName 1>nul 2>nul"
        if (Test-DockerEngine) { return $true }
    }
    return $false
}

function Invoke-NativeChecked([scriptblock]$Command, [string]$FailureMessage) {
    $previousPreference=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    & $Command
    $nativeExit=$LASTEXITCODE
    $ErrorActionPreference=$previousPreference
    if ($nativeExit -ne 0) { throw "$FailureMessage (exit $nativeExit)." }
}

function Test-PistonApi {
    & cmd.exe /d /c "curl.exe --fail --silent http://127.0.0.1:2000/api/v2/runtimes 1>nul 2>nul"
    return ($LASTEXITCODE -eq 0)
}

function Wait-PistonApi {
    for ($i=0; $i -lt 60; $i++) {
        if (Test-PistonApi) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Install-WithWinget([string]$Id, [string]$Label) {
    Write-Host "Installing $Label ..." -ForegroundColor Cyan
    Invoke-NativeChecked { winget install --exact --id $Id --accept-package-agreements --accept-source-agreements --silent } "Installation failed for $Label"
    Refresh-Path
}

function Install-AndroidBuildTools {
    $sdkRoot=Join-Path $projectDir '.android-sdk'
    $sdkManager=Join-Path $sdkRoot 'cmdline-tools\latest\bin\sdkmanager.bat'
    if (-not (Get-Command javac -ErrorAction SilentlyContinue)) { Install-WithWinget 'EclipseAdoptium.Temurin.17.JDK' 'Java 17 JDK' }
    if (-not (Get-Command javac -ErrorAction SilentlyContinue)) { Refresh-Path }
    if (-not (Get-Command javac -ErrorAction SilentlyContinue)) { throw 'Java JDK was installed but javac is not available. Restart Windows and run this installer again.' }
    if (-not (Test-Path $sdkManager)) {
        Write-Host 'Installing Android command-line SDK (one time only)...' -ForegroundColor Cyan
        $download=Join-Path $env:TEMP 'lwh-android-command-line-tools.zip'
        $extract=Join-Path $env:TEMP 'lwh-android-command-line-tools'
        if(Test-Path $extract){Remove-Item -LiteralPath $extract -Recurse -Force}
        Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip' -OutFile $download
        Expand-Archive -LiteralPath $download -DestinationPath $extract -Force
        $latest=Join-Path $sdkRoot 'cmdline-tools\latest'
        New-Item -ItemType Directory -Force -Path $latest|Out-Null
        Copy-Item -Path (Join-Path $extract 'cmdline-tools\*') -Destination $latest -Recurse -Force
        Remove-Item -LiteralPath $download -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
    } else { Write-Host 'Existing Android command-line SDK detected; keeping it.' -ForegroundColor Green }
    $env:ANDROID_SDK_ROOT=$sdkRoot;$env:ANDROID_HOME=$sdkRoot
    & cmd.exe /d /c "(for /l %i in (1,1,30) do @echo y) | `"$sdkManager`" --sdk_root=`"$sdkRoot`" --licenses 1>nul"
    if($LASTEXITCODE -ne 0){throw 'Android SDK licence acceptance failed.'}
    Invoke-NativeChecked { & $sdkManager --sdk_root=$sdkRoot 'platform-tools' 'platforms;android-35' 'build-tools;35.0.0' } 'Android SDK package installation failed'
    $keyDir=Join-Path $projectDir '.android-debug';$keyStore=Join-Path $keyDir 'debug.keystore'
    if(-not(Test-Path $keyStore)){
        New-Item -ItemType Directory -Force -Path $keyDir|Out-Null
        Invoke-NativeChecked { keytool -genkeypair -v -keystore $keyStore -storepass android -alias androiddebugkey -keypass android -dname 'CN=Android Debug,O=Learn with Hemant,C=IN' -keyalg RSA -keysize 2048 -validity 10000 } 'Android debug signing-key creation failed'
    } else { Write-Host 'Existing Android debug signing key detected; keeping it.' -ForegroundColor Green }
    [Environment]::SetEnvironmentVariable('LWH_ANDROID_SDK_ROOT',$sdkRoot,'User')
    [Environment]::SetEnvironmentVariable('LWH_ANDROID_DEBUG_KEYSTORE',$keyStore,'User')
    Write-Host 'Android APK builder is ready.' -ForegroundColor Green
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw 'Windows Package Manager (winget) is required. Install App Installer from Microsoft Store, then run INSTALL_CODE_RUNNER.bat again.'
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Install-WithWinget 'Git.Git' 'Git' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Install-WithWinget 'OpenJS.NodeJS.LTS' 'Node.js LTS' }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Install-WithWinget 'Python.Python.3.12' 'Python 3.12' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Install-WithWinget 'Docker.DockerDesktop' 'Docker Desktop'
    Write-Host "Docker Desktop was installed. Restart Windows, then run INSTALL_CODE_RUNNER.bat once more." -ForegroundColor Yellow
    exit 10
}

$dockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
if (-not (Test-DockerEngine)) {
    # A stale DOCKER_HOST can force the CLI toward a pipe that does not exist.
    Remove-Item Env:DOCKER_HOST -ErrorAction SilentlyContinue
    $contextReady = Try-DockerContexts
    if (-not $contextReady -and (Test-Path $dockerDesktop)) {
        $desktopProcess = Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue
        if (-not $desktopProcess) { Start-Process $dockerDesktop }
    }
    Write-Host 'Waiting for Docker Engine (up to 3 minutes)...' -ForegroundColor Cyan
    $ready = $false
    for ($i=0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 2
        if (Test-DockerEngine) { $ready=$true; break }
        if (($i % 10) -eq 9 -and (Try-DockerContexts)) { $ready=$true; break }
    }
    if (-not $ready) {
        throw 'Docker Engine did not start. Restart Windows, open Docker Desktop once, finish its WSL prompt, and rerun INSTALL_CODE_RUNNER.bat.'
    }
}

$venvPython = Join-Path $projectDir '.venv-code-runner\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Invoke-NativeChecked { python -m venv (Join-Path $projectDir '.venv-code-runner') } 'Python environment creation failed'
}
# The HTTPS queue worker uses only Python's standard library. It intentionally
# receives neither the web application dependencies nor a PostgreSQL driver.

if (-not (Test-PistonApi)) {
    & cmd.exe /d /c "docker inspect learnwithhemant_piston 1>nul 2>nul"
    if ($LASTEXITCODE -eq 0) {
        Invoke-NativeChecked { docker start learnwithhemant_piston } 'The existing Piston container could not be started'
    } else {
        Invoke-NativeChecked { docker compose -f (Join-Path $projectDir 'docker-compose.code-runner.yml') up -d } 'The Piston container could not be created'
    }
    Write-Host 'Waiting for the private compiler service...' -ForegroundColor Cyan
    if (-not (Wait-PistonApi)) { throw 'Piston started but its API did not become ready within two minutes.' }
} else {
    Write-Host 'Existing Piston service detected; keeping it.' -ForegroundColor Green
}

if (-not (Test-Path (Join-Path $cliDir '.git'))) {
    if (Test-Path $cliDir) { Remove-Item -Recurse -Force $cliDir }
    Invoke-NativeChecked { git clone --depth 1 https://github.com/engineer-man/piston.git $cliDir } 'Piston download failed'
}

Push-Location (Join-Path $cliDir 'cli')
try {
    Invoke-NativeChecked { npm ci } 'Piston package manager setup failed'
    # gcc installs both the C and C++ runtimes. Piston does not provide
    # packages named "c" or "c++".
    foreach ($packageName in @('gcc', 'java', 'python', 'php')) {
        Invoke-NativeChecked { node index.js -u http://127.0.0.1:2000 ppman install $packageName } "Piston runtime installation failed: $packageName"
    }
} finally { Pop-Location }

$configPath=Join-Path $projectDir '.code-runner.profiles.json'
if (-not (Test-Path $configPath)) {
    & (Join-Path $projectDir 'configure_code_runner_windows.ps1')
} else {
    Write-Host 'Existing environment profiles detected; keeping them.' -ForegroundColor Green
}

$previousPreference=$ErrorActionPreference; $ErrorActionPreference='Continue'
$runtimes = curl.exe --fail --silent http://127.0.0.1:2000/api/v2/runtimes
$curlExit=$LASTEXITCODE; $ErrorActionPreference=$previousPreference
if ($curlExit -ne 0) { throw 'Piston runtime health check failed.' }
foreach ($runtimeName in @('"language":"c"','"language":"c++"','"language":"java"','"language":"python"','"language":"php"')) {
    if ($runtimes -notlike "*$runtimeName*") { throw "Required runtime is missing: $runtimeName" }
}
Install-AndroidBuildTools
Write-Host "`nSetup complete. Code execution and Android APK building are ready. Use the STAGING, PRELIVE, or PRODUCTION launcher." -ForegroundColor Green
