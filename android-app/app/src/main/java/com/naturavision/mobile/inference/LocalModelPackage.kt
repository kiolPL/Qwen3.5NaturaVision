package com.naturavision.mobile.inference

import android.content.Context
import java.io.File

data class LocalModelPackageState(
    val searchedLocations: List<File>,
    val adapterLocation: File?,
    val languageModelFile: File?,
    val projectorFile: File?,
) {
    val hasAdapterBundle: Boolean = adapterLocation != null
    val hasRunnableGgufBundle: Boolean = languageModelFile != null && projectorFile != null
}

object LocalModelPackage {
    const val MODEL_DIR_NAME = "naturavision"

    val requiredAdapterFiles = listOf(
        "adapter_model.safetensors",
        "adapter_config.json",
        "additional_config.json",
        "args.json",
        "labels.json",
        "species_manifest.csv",
        "trainer_state.json",
    )

    fun inspect(context: Context): LocalModelPackageState {
        val locations = candidateLocations(context.applicationContext)
        val adapterLocation = locations.firstOrNull(::hasCompleteAdapterBundle)

        return LocalModelPackageState(
            searchedLocations = locations,
            adapterLocation = adapterLocation,
            languageModelFile = locations.firstNotNullOfOrNull(::findLanguageModelGguf),
            projectorFile = locations.firstNotNullOfOrNull(::findProjectorGguf),
        )
    }

    fun adapterBundleSizeBytes(location: File): Long =
        requiredAdapterFiles.sumOf { fileName -> location.resolve(fileName).length() }

    fun missingAdapterFiles(location: File): List<String> =
        requiredAdapterFiles.filterNot { fileName ->
            location.resolve(fileName).let { it.isFile && it.length() > 0L }
        }

    private fun candidateLocations(context: Context): List<File> =
        listOfNotNull(
            context.noBackupFilesDir.resolve("model").resolve(MODEL_DIR_NAME),
            context.getExternalFilesDir("model")?.resolve(MODEL_DIR_NAME),
            context.filesDir.resolve("model").resolve(MODEL_DIR_NAME),
        ).distinctBy(File::getAbsolutePath)

    private fun hasCompleteAdapterBundle(location: File): Boolean =
        missingAdapterFiles(location).isEmpty()

    private fun findLanguageModelGguf(location: File): File? =
        location.listFiles()
            ?.filter { file -> file.isFile && file.extension.equals("gguf", ignoreCase = true) }
            ?.filterNot { file -> file.name.contains("mmproj", ignoreCase = true) }
            ?.filterNot { file -> file.name.contains("projector", ignoreCase = true) }
            ?.minWithOrNull(
                compareBy<File> { mobileQuantRank(it.name) }
                    .thenBy { metadataFixRank(it.name) }
                    .thenByDescending { it.length() },
            )

    private fun findProjectorGguf(location: File): File? =
        location.listFiles()
            ?.filter { file -> file.isFile && file.extension.equals("gguf", ignoreCase = true) }
            ?.firstOrNull { file ->
                file.name.contains("mmproj", ignoreCase = true) ||
                    file.name.contains("projector", ignoreCase = true)
            }

    private fun mobileQuantRank(fileName: String): Int {
        val lower = fileName.lowercase()
        return when {
            lower.contains("q3_k_s") -> 0
            lower.contains("q3_k_m") -> 1
            lower.contains("q2_k") -> 2
            lower.contains("iq3") -> 3
            lower.contains("iq2") -> 4
            lower.contains("q4_k_m") -> 5
            lower.contains("q4_k_s") -> 6
            else -> 100
        }
    }

    private fun metadataFixRank(fileName: String): Int {
        val lower = fileName.lowercase()
        return if (lower.contains("fixed") || lower.contains("mobile")) 0 else 1
    }
}
