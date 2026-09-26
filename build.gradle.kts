import com.android.build.api.dsl.ApplicationExtension
import org.gradle.api.GradleException
import java.io.File

plugins {
    base
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.hilt.android) apply false
    alias(libs.plugins.room) apply false
}

group = "com.littleorbit"
version = "1.3.0"
extra["littleOrbitVersionCode"] = 29
extra["littleOrbitWearVersionCode"] = 21
extra["littleOrbitVersionName"] = "1.3.0"
extra["littleOrbitWearVersionName"] = "1.3.0"

val signingEnvironment = listOf(
    "ANDROID_SIGNING_STORE_FILE",
    "ANDROID_SIGNING_STORE_PASSWORD",
    "ANDROID_SIGNING_KEY_ALIAS",
    "ANDROID_SIGNING_KEY_PASSWORD",
).associateWith { providers.environmentVariable(it).orNull }
val missingSigningValues = signingEnvironment.filterValues { it.isNullOrBlank() }.keys
val isolatedUnsignedReleaseBuilder =
    providers.environmentVariable("LITTLE_ORBIT_ISOLATED_UNSIGNED_BUILDER").orNull == "1" &&
        File("/opt/little-orbit-android-builder").isFile

subprojects {
    pluginManager.withPlugin("com.android.application") {
        extensions.configure<ApplicationExtension> {
            if (missingSigningValues.isEmpty() && !isolatedUnsignedReleaseBuilder) {
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
            if (packagesRelease && missingSigningValues.isNotEmpty() && !isolatedUnsignedReleaseBuilder) {
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
    gradleVersion = "9.7.1"
    distributionType = Wrapper.DistributionType.BIN
    distributionSha256Sum = "acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a"
}
