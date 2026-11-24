# 編譯 Android APK。
#   powershell -ExecutionPolicy Bypass -File android\tools\build_apk.ps1
#
# 專案路徑含中文（文件）時，Windows 上的 gradlew 會找不到 wrapper，
# 所以先把 android 專案同步到純英文路徑 %LOCALAPPDATA%\PixieBuild 再編譯，APK 複製回 dist\。
$ErrorActionPreference = "Stop"

$src = Split-Path -Parent $PSScriptRoot                     # ...\android
$root = Split-Path -Parent $src                             # 專案根目錄
$work = Join-Path $env:LOCALAPPDATA "PixieBuild\android"
$env:JAVA_HOME = Join-Path $env:LOCALAPPDATA "Programs\jdk-17"
$env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA "Android\Sdk"

if (-not (Test-Path "$env:JAVA_HOME\bin\java.exe")) { throw "找不到 JDK，請先執行 android\tools\setup_toolchain.sh" }

# 同步原始碼（排除建置產物；/MIR 會刪掉目的地多餘的檔案，只影響 PixieBuild 資料夾）
robocopy $src $work /MIR /XD build .gradle .kotlin /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 失敗 ($LASTEXITCODE)" }
"sdk.dir=$($env:ANDROID_HOME -replace '\\','/')" | Set-Content -Encoding ascii (Join-Path $work "local.properties")

Push-Location $work
try {
    & .\gradlew.bat testDebugUnitTest assembleDebug --console=plain
    if ($LASTEXITCODE -ne 0) { throw "Gradle 建置失敗" }
} finally {
    Pop-Location
}

$apk = Join-Path $work "app\build\outputs\apk\debug\app-debug.apk"
$outDir = Join-Path $root "dist"
New-Item -ItemType Directory -Force $outDir | Out-Null
$out = Join-Path $outDir "Pixie-android.apk"
Copy-Item $apk $out -Force
"APK: $out ($([math]::Round((Get-Item $out).Length / 1MB, 1)) MB)"
