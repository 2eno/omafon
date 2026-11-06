plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "de.omafon.companion"
    compileSdk = 35

    defaultConfig {
        applicationId = "de.omafon.companion"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.9.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    testOptions {
        unitTests {
            isReturnDefaultValues = true
            isIncludeAndroidResources = true      // Robolectric: Oberfläche mit echten Ressourcen
            all { it.maxHeapSize = "2g" }
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.datastore.preferences)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.material.icons)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    debugImplementation(libs.compose.ui.tooling)
    debugImplementation(libs.compose.ui.test.manifest)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.okhttp.tls)
    testImplementation(libs.kotlinx.coroutines.test)
    // Oberflächentests auf der JVM (Robolectric) mit Bildschirmfotos
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)
    testImplementation(libs.androidx.test.ext.junit)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.compose.ui.test.junit4)
}

// Robolectric lädt den Android-Rahmen sonst erst im Test selbst aus dem Netz
// (ohne Gradle-Cache, bricht bei Störungen von Maven Central ab). So holt ihn
// Gradle wie jede Abhängigkeit, und Robolectric läuft offline.
val robolectricRuntime: Configuration by configurations.creating
dependencies {
    robolectricRuntime(libs.robolectric.android.all)
}
val robolectricJars = layout.buildDirectory.dir("robolectric-jars")
val copyRobolectricJars by tasks.registering(Copy::class) {
    from(robolectricRuntime)
    into(robolectricJars)
}
tasks.withType<Test>().configureEach {
    dependsOn(copyRobolectricJars)
    systemProperty("robolectric.offline", "true")
    systemProperty("robolectric.pixelCopyRenderMode", "hardware")   // Bildschirmfotos (captureToImage)
    systemProperty("robolectric.dependency.dir", robolectricJars.get().asFile.absolutePath)
}
