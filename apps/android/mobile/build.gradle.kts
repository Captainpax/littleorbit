plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.hilt.android)
}

android {
    namespace = "com.littleorbit.mobile"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.littleorbit.mobile"
        minSdk = 29
        targetSdk = 36
        versionCode = rootProject.extra["littleOrbitVersionCode"] as Int
        versionName = rootProject.extra["littleOrbitVersionName"] as String
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(project(":apps:android:domain"))
    implementation(project(":apps:android:data"))
    implementation(project(":apps:android:widget"))
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.androidx.lifecycle.livedata)
    implementation(libs.androidx.work.runtime)
    implementation(libs.androidx.hilt.work)
    implementation(libs.play.services.wearable)
    implementation("androidx.core:core:1.16.0")
    implementation(libs.material)
    implementation(libs.hilt.android)
    annotationProcessor(libs.hilt.compiler)
    testImplementation(libs.junit4)
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.ext.junit)
}
