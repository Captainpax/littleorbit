plugins { alias(libs.plugins.android.application) }

android {
    namespace = "com.littleorbit.wear"
    compileSdk = 37
    testBuildType = providers.gradleProperty("wearTestBuildType").orElse("debug").get()
    defaultConfig {
        applicationId = "com.littleorbit.mobile"
        minSdk = 30
        targetSdk = 36
        versionCode = rootProject.extra["littleOrbitWearVersionCode"] as Int
        versionName = rootProject.extra["littleOrbitWearVersionName"] as String
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildTypes {
        create("smoke") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".smoke"
            versionNameSuffix = "-qa"
            signingConfig = getByName("debug").signingConfig
        }
        create("smokeBaseline") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".smoke"
            versionNameSuffix = "-qa-baseline"
            signingConfig = getByName("debug").signingConfig
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { buildConfig = true }
}

androidComponents {
    onVariants(selector().withBuildType("smokeBaseline")) { variant ->
        variant.outputs.forEach { output -> output.versionCode.set(19) }
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
    testImplementation(libs.junit4)
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.ext.junit)
}
