import com.android.build.api.dsl.ApplicationExtension
import org.gradle.api.GradleException

plugins {
    base
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.hilt.android) apply false
    alias(libs.plugins.room) apply false
}

group = "com.littleorbit"
version = "0.1.0"
extra["littleOrbitVersionCode"] = 13
extra["littleOrbitWearVersionCode"] = 12
extra["littleOrbitVersionName"] = "1.0.0-rc.11.1"

val signingEnvironment = listOf(
    "ANDROID_SIGNING_STORE_FILE",
    "ANDROID_SIGNING_STORE_PASSWORD",
    "ANDROID_SIGNING_KEY_ALIAS",
    "ANDROID_SIGNING_KEY_PASSWORD",
).associateWith { providers.environmentVariable(it).orNull }
val missingSigningValues = signingEnvironment.filterValues { it.isNullOrBlank() }.keys

subprojects {
    pluginManager.withPlugin("com.android.application") {
        extensions.configure<ApplicationExtension> {
            if (missingSigningValues.isEmpty()) {
                val releaseSigning = signingConfigs.create("release") {
                    storeFile = rootProject.file(
                        signingEnvironment.getValue("ANDROID_SIGNING_STORE_FILE")!!,
                    )
                    storePassword = signingEnvironment.getValue("ANDROID_SIGNING_STORE_PASSWORD")
                    keyAlias = signingEnvironment.getValue("ANDROID_SIGNING_KEY_ALIAS")
                    keyPassword = signingEnvironment.getValue("ANDROID_SIGNING_KEY_PASSWORD")
                    enableV1Signing = false
                    enableV2Signing = true
                    enableV3Signing = true
                    enableV4Signing = false
                }
                buildTypes.getByName("release").signingConfig = releaseSigning
            }
        }
        tasks.configureEach {
            val packagesRelease = name in setOf("assembleRelease", "bundleRelease", "packageRelease")
            if (packagesRelease && missingSigningValues.isNotEmpty()) {
                doFirst {
                    throw GradleException(
                        "Release signing is incomplete: ${missingSigningValues.sorted().joinToString()}",
                    )
                }
            }
        }
    }
}

tasks.wrapper {
    gradleVersion = "9.4.1"
    distributionType = Wrapper.DistributionType.BIN
    distributionSha256Sum = "2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb"
}
