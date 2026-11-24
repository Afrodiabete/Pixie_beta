plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.pixie.pet"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.pixie.pet"
        minSdk = 26          // Android 8.0+
        targetSdk = 35
        versionCode = 3
        versionName = "0.1.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")   // 掃描配對 QR code

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")   // 單元測試在 JVM 上跑，需要真的 org.json
}
