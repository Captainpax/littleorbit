plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.hilt.android)
}

fun javaString(value: String): String = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

val firebaseApplicationId = providers.gradleProperty("littleOrbitFirebaseApplicationId")
    .orElse(providers.environmentVariable("LITTLE_ORBIT_FIREBASE_APPLICATION_ID"))
    .getOrElse("")
val firebaseApiKey = providers.gradleProperty("littleOrbitFirebaseApiKey")
    .orElse(providers.environmentVariable("LITTLE_ORBIT_FIREBASE_API_KEY"))
    .getOrElse("")
val firebaseProjectId = providers.gradleProperty("littleOrbitFirebaseProjectId")
    .orElse(providers.environmentVariable("LITTLE_ORBIT_FIREBASE_PROJECT_ID"))
    .getOrElse("")
val firebaseSenderId = providers.gradleProperty("littleOrbitFirebaseSenderId")
    .orElse(providers.environmentVariable("LITTLE_ORBIT_FIREBASE_SENDER_ID"))
    .getOrElse("")

android {
    namespace = "com.littleorbit.mobile"
    compileSdk = 37
    defaultConfig {
        applicationId = "com.littleorbit.mobile"
        minSdk = 29
        targetSdk = 36
        versionCode = rootProject.extra["littleOrbitVersionCode"] as Int
        versionName = rootProject.extra["littleOrbitVersionName"] as String
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "FIREBASE_APPLICATION_ID", javaString(firebaseApplicationId))
        buildConfigField("String", "FIREBASE_API_KEY", javaString(firebaseApiKey))
        buildConfigField("String", "FIREBASE_PROJECT_ID", javaString(firebaseProjectId))
        buildConfigField("String", "FIREBASE_SENDER_ID", javaString(firebaseSenderId))
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
    implementation(libs.firebase.messaging)
    implementation("io.noties.markwon:core:4.6.2")
    implementation("io.noties.markwon:ext-strikethrough:4.6.2")
    implementation("io.noties.markwon:ext-tables:4.6.2")
    implementation("io.noties.markwon:ext-tasklist:4.6.2")
    implementation("io.noties.markwon:linkify:4.6.2")
    implementation("io.noties.markwon:image:4.6.2")
    implementation("pl.droidsonroids.gif:android-gif-drawable:1.2.32")
    implementation(libs.okhttp)
    implementation(libs.retrofit)
    implementation("androidx.core:core:1.16.0")
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
