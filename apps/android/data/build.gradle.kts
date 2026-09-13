plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.hilt.android)
    alias(libs.plugins.room)
}

room { schemaDirectory("$projectDir/schemas") }

android {
    namespace = "com.littleorbit.data"
    compileSdk = 37
    defaultConfig {
        minSdk = 29
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField(
            "int",
            "CLIENT_VERSION_CODE",
            (rootProject.extra["littleOrbitVersionCode"] as Int).toString(),
        )
        buildConfigField(
            "String",
            "CLIENT_VERSION_NAME",
            "\"${rootProject.extra["littleOrbitVersionName"] as String}\"",
        )
        buildConfigField("String", "API_BASE_URL", "\"https://lil-orb.pax-kun.com/\"")
        buildConfigField("String", "WS_BASE_URL", "\"wss://lil-orb.pax-kun.com/\"")
    }
    buildTypes {
        create("smoke") {
            val apiBase = providers.gradleProperty("littleOrbitSmokeApiBaseUrl")
                .orElse("http://127.0.0.1:18180/").get()
            val wsBase = providers.gradleProperty("littleOrbitSmokeWsBaseUrl")
                .orElse("ws://127.0.0.1:18180/").get()
            buildConfigField("String", "API_BASE_URL", "\"$apiBase\"")
            buildConfigField("String", "WS_BASE_URL", "\"$wsBase\"")
        }
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    api(project(":apps:android:domain"))
    implementation(libs.androidx.room.runtime)
    annotationProcessor(libs.androidx.room.compiler)
    implementation(libs.androidx.work.runtime)
    implementation(libs.androidx.hilt.work)
    annotationProcessor(libs.androidx.hilt.compiler)
    implementation(libs.play.services.location)
    implementation(libs.play.services.wearable)
    implementation(libs.hilt.android)
    annotationProcessor(libs.hilt.compiler)
    implementation(libs.retrofit)
    implementation(libs.retrofit.moshi)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.moshi)
    testImplementation(libs.junit4)
    androidTestImplementation(libs.androidx.room.testing)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.ext.junit)
}
