plugins { alias(libs.plugins.android.library) }

android {
    namespace = "com.littleorbit.widget"
    compileSdk = 36
    defaultConfig { minSdk = 29 }
    buildFeatures { viewBinding = false }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(project(":apps:android:domain"))
    implementation(project(":apps:android:data"))
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.work.runtime)
}
