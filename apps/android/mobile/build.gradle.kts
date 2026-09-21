import java.util.zip.ZipFile

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.hilt.android)
}

android {
    namespace = "com.littleorbit.mobile"
    compileSdk = 37
    testBuildType = providers.gradleProperty("mobileTestBuildType").orElse("debug").get()
    defaultConfig {
        applicationId = "com.littleorbit.mobile"
        minSdk = 29
        targetSdk = 36
        versionCode = rootProject.extra["littleOrbitVersionCode"] as Int
        versionName = rootProject.extra["littleOrbitVersionName"] as String
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildTypes {
        create("smoke") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".smoke"
            versionNameSuffix = "-smoke"
            signingConfig = getByName("debug").signingConfig
            matchingFallbacks += listOf("debug")
        }
    }
    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
    sourceSets.getByName("smoke").assets.srcDir(
        layout.buildDirectory.dir("generated/smokeWearAssets").get().asFile,
    )
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

val prepareSmokeWearAsset by tasks.registering(Copy::class) {
    dependsOn(":apps:android:wear:assembleSmoke")
    from(project(":apps:android:wear").layout.buildDirectory.file(
        "outputs/apk/smoke/wear-smoke.apk",
    ))
    into(layout.buildDirectory.dir("generated/smokeWearAssets"))
    rename { "little-orbit-wear-smoke.apk" }
}

tasks.configureEach {
    if (name != "prepareSmokeWearAsset" && name.contains("Smoke")) {
        dependsOn(prepareSmokeWearAsset)
    }
}

tasks.register("verifyWearArtifactIsolation") {
    group = "verification"
    description = "Proves only the smoke phone APK embeds the generated Wear QA APK."
    dependsOn("assembleDebug", "assembleSmoke")
    doLast {
        val asset = "assets/little-orbit-wear-smoke.apk"
        fun contains(apk: java.io.File): Boolean = ZipFile(apk).use { zip ->
            zip.getEntry(asset) != null
        }
        val debugApk = layout.buildDirectory.file("outputs/apk/debug/mobile-debug.apk").get().asFile
        val smokeApk = layout.buildDirectory.file("outputs/apk/smoke/mobile-smoke.apk").get().asFile
        check(!contains(debugApk)) { "Non-smoke phone APK contains the Wear QA artifact" }
        check(contains(smokeApk)) { "Smoke phone APK is missing its trusted Wear QA artifact" }
    }
}

dependencies {
    implementation(project(":apps:android:domain"))
    implementation(project(":apps:android:data"))
    implementation(project(":apps:android:widget"))
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.drawerlayout)
    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.androidx.lifecycle.livedata)
    implementation(libs.androidx.work.runtime)
    implementation(libs.androidx.hilt.work)
    implementation(libs.play.services.wearable)
    implementation(libs.kadb) {
        exclude(group = "org.lsposed.hiddenapibypass", module = "hiddenapibypass")
    }
    implementation(libs.conscrypt.android)
    implementation(libs.image.cropper)
    implementation("io.noties.markwon:core:4.6.2")
    implementation("io.noties.markwon:ext-strikethrough:4.6.2")
    implementation("io.noties.markwon:ext-tables:4.6.2")
    implementation("io.noties.markwon:ext-tasklist:4.6.2")
    implementation("io.noties.markwon:linkify:4.6.2")
    implementation("io.noties.markwon:image:4.6.2")
    implementation("pl.droidsonroids.gif:android-gif-drawable:1.2.32")
    implementation(libs.okhttp)
    implementation(libs.retrofit)
    implementation("androidx.core:core:1.19.0")
    implementation(libs.material)
    implementation(libs.hilt.android)
    annotationProcessor(libs.androidx.hilt.compiler)
    annotationProcessor(libs.hilt.compiler)
    testImplementation(libs.junit4)
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.uiautomator)
}
