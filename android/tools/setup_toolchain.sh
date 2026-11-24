#!/usr/bin/env bash
# 安裝編譯 Android app 需要的命令列工具（不需要 Android Studio）。
# 全部裝在 %LOCALAPPDATA% 底下，不需要系統管理員權限。可以重複執行，已經裝好的會跳過。
set -euo pipefail

LOCAL="$(cygpath -u "$LOCALAPPDATA")"
JDK_DIR="$LOCAL/Programs/jdk-17"
SDK_DIR="$LOCAL/Android/Sdk"
GRADLE_VER="8.9"
GRADLE_DIR="$LOCAL/Programs/gradle-$GRADLE_VER"
DL="$(mktemp -d)"   # 下載暫存（新的空資料夾）

log() { echo "[$(date +%H:%M:%S)] $*"; }

# 1. JDK 17（Eclipse Temurin）
if [ ! -x "$JDK_DIR/bin/java.exe" ]; then
  log "下載 JDK 17..."
  curl -fsSL -o "$DL/jdk.zip" \
    "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse"
  mkdir -p "$DL/jdk" && unzip -q "$DL/jdk.zip" -d "$DL/jdk"
  mkdir -p "$(dirname "$JDK_DIR")" && mv "$DL"/jdk/jdk-17* "$JDK_DIR"
fi
log "JDK: $("$JDK_DIR/bin/java.exe" -version 2>&1 | head -1)"

# 2. Android SDK command-line tools
if [ ! -f "$SDK_DIR/cmdline-tools/latest/bin/sdkmanager.bat" ]; then
  log "下載 Android command-line tools..."
  curl -fsSL -o "$DL/cmdline.zip" \
    "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
  mkdir -p "$DL/cmd" && unzip -q "$DL/cmdline.zip" -d "$DL/cmd"
  mkdir -p "$SDK_DIR/cmdline-tools" && mv "$DL/cmd/cmdline-tools" "$SDK_DIR/cmdline-tools/latest"
fi

# 3. SDK 套件
export JAVA_HOME="$(cygpath -w "$JDK_DIR")"
SDKMANAGER="$SDK_DIR/cmdline-tools/latest/bin/sdkmanager.bat"
log "接受 SDK 授權並安裝 platform / build-tools..."
yes 2>/dev/null | cmd.exe //c "$(cygpath -w "$SDKMANAGER")" --licenses > /dev/null || true
cmd.exe //c "$(cygpath -w "$SDKMANAGER")" --install "platform-tools" "platforms;android-35" "build-tools;35.0.0" \
  | grep -v "^\[=*" | tail -5

# 4. Gradle（只用來產生 gradle wrapper）
if [ ! -x "$GRADLE_DIR/bin/gradle.bat" ]; then
  log "下載 Gradle $GRADLE_VER..."
  curl -fsSL -o "$DL/gradle.zip" "https://services.gradle.org/distributions/gradle-$GRADLE_VER-bin.zip"
  unzip -q "$DL/gradle.zip" -d "$LOCAL/Programs"
fi

rm -rf "$DL"
log "完成"
echo "JAVA_HOME=$(cygpath -w "$JDK_DIR")"
echo "ANDROID_HOME=$(cygpath -w "$SDK_DIR")"
echo "GRADLE=$(cygpath -w "$GRADLE_DIR/bin/gradle.bat")"
