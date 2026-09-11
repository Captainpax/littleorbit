plugins { alias(libs.plugins.android.application) }

android {
    namespace = "com.littleorbit.wear"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.littleorbit.mobile"
        minSdk = 30
        targetSdk = 36
        versionCode = rootProject.extra["littleOrbitVersionCode"] as Int
        versionName = rootProject.extra["littleOrbitVersionName"] as String
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(project(":apps:android:domain"))
    implementation(libs.androidx.activity)
    implementation(libs.androidx.wear)
    implementation(libs.androidx.wear.tiles)
    implementation(libs.androidx.wear.protolayout)
    implementation(libs.androidx.watchface.complications)
    implementation(libs.androidx.concurrent.futures)
    implementation(libs.guava)
    implementation(libs.play.services.wearable)
}
