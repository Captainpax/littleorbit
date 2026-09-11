plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.hilt.android)
    alias(libs.plugins.room)
}

room { schemaDirectory("$projectDir/schemas") }

android {
    namespace = "com.littleorbit.data"
    compileSdk = 36
    defaultConfig {
        minSdk = 29
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
}
