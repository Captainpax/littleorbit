plugins { `java-library` }

java {
    toolchain { languageVersion = JavaLanguageVersion.of(17) }
}

dependencies { testImplementation(libs.junit.jupiter) }
dependencies { testRuntimeOnly(libs.junit.platform.launcher) }

tasks.test { useJUnitPlatform() }
