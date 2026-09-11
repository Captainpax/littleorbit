pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "little-orbit"

include(
    ":apps:android:domain",
    ":apps:android:data",
    ":apps:android:widget",
    ":apps:android:mobile",
    ":apps:android:wear",
)
