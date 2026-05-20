package com.naturavision.mobile.testing

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import com.naturavision.mobile.data.TaxonomyCatalog
import com.naturavision.mobile.inference.ForestInferenceFactory
import com.naturavision.mobile.inference.InferenceBackend
import com.naturavision.mobile.inference.LocalModelPackage
import com.naturavision.mobile.inference.ModelOutputParser
import com.naturavision.mobile.inference.PromptTemplates
import com.naturavision.mobile.model.ForestSpecies
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlin.system.measureTimeMillis

enum class ModelTestStatus {
    PASS,
    WARNING,
    FAIL,
}

data class ModelTestCaseResult(
    val name: String,
    val status: ModelTestStatus,
    val details: String,
)

data class ModelTestSuiteReport(
    val results: List<ModelTestCaseResult>,
    val elapsedMs: Long,
) {
    val passed: Int = results.count { it.status == ModelTestStatus.PASS }
    val warnings: Int = results.count { it.status == ModelTestStatus.WARNING }
    val failed: Int = results.count { it.status == ModelTestStatus.FAIL }
    val summaryLine: String = "$passed PASS / $warnings WARN / $failed FAIL"
}

class ModelTestSuite(
    private val inferenceFactory: ForestInferenceFactory = ForestInferenceFactory(),
) {
    suspend fun run(context: Context): ModelTestSuiteReport = withContext(Dispatchers.Default) {
        val results = mutableListOf<ModelTestCaseResult>()
        val elapsed = measureTimeMillis {
            results += taxonomyCompleteness()
            results += labelUniqueness()
            results += parserRoundTrip()
            results += promptCoverage()
            results += adapterWeightBundle(context.applicationContext)
            results += runnableModelBundle(context.applicationContext)
            results += demoInferenceSmoke()
            results += localModelReadiness(context.applicationContext)
        }
        ModelTestSuiteReport(results = results, elapsedMs = elapsed)
    }

    private fun taxonomyCompleteness(): ModelTestCaseResult {
        val ok = TaxonomyCatalog.plants.size == 20 &&
            TaxonomyCatalog.fungi.size == 20 &&
            TaxonomyCatalog.all.any { it.labelId == ForestSpecies.UNKNOWN_LABEL_ID }

        return if (ok) {
            ModelTestCaseResult(
                name = "Katalog gatunkow",
                status = ModelTestStatus.PASS,
                details = "20 roslin, 20 grzybow i publiczne unknown sa dostepne w aplikacji.",
            )
        } else {
            ModelTestCaseResult(
                name = "Katalog gatunkow",
                status = ModelTestStatus.FAIL,
                details = "Oczekiwano 20 roslin, 20 grzybow i unknown, ale katalog ma ${TaxonomyCatalog.all.size} wpisow.",
            )
        }
    }

    private fun labelUniqueness(): ModelTestCaseResult {
        val labels = TaxonomyCatalog.supportedLabelIds
        val duplicates = labels.groupingBy { it }.eachCount().filterValues { it > 1 }.keys
        return if (duplicates.isEmpty()) {
            ModelTestCaseResult(
                name = "Unikalnosc label_id",
                status = ModelTestStatus.PASS,
                details = "Wszystkie ${labels.size} publiczne etykiety sa unikalne.",
            )
        } else {
            ModelTestCaseResult(
                name = "Unikalnosc label_id",
                status = ModelTestStatus.FAIL,
                details = "Powtorzone etykiety: ${duplicates.joinToString()}",
            )
        }
    }

    private fun parserRoundTrip(): ModelTestCaseResult {
        val failures = TaxonomyCatalog.supportedLabelIds.filter { labelId ->
            val parsed = ModelOutputParser.parse("""{"label_id":"$labelId"}""")
            parsed.labelId != labelId
        }
        val unknownCollapsed = listOf(
            "UNK_NON_TARGET_PLANT",
            "UNK_NON_TARGET_FUNGUS",
            "UNK_OTHER_OR_AMBIGUOUS",
        ).all { internalLabel ->
            ModelOutputParser.parse("""{"label_id":"$internalLabel"}""").labelId == ForestSpecies.UNKNOWN_LABEL_ID
        }

        return if (failures.isEmpty() && unknownCollapsed) {
            ModelTestCaseResult(
                name = "Parser odpowiedzi modelu",
                status = ModelTestStatus.PASS,
                details = "Parser poprawnie mapuje wszystkie label_id i scala wewnetrzne UNK_* do unknown.",
            )
        } else {
            ModelTestCaseResult(
                name = "Parser odpowiedzi modelu",
                status = ModelTestStatus.FAIL,
                details = "Problem z etykietami: ${failures.joinToString().ifBlank { "UNK_*" }}",
            )
        }
    }

    private fun promptCoverage(): ModelTestCaseResult {
        val missing = TaxonomyCatalog.knownTargets
            .map(ForestSpecies::labelId)
            .filterNot { PromptTemplates.SYSTEM_PROMPT.contains(it) }

        return if (missing.isEmpty() && PromptTemplates.USER_PROMPT.contains("label_id")) {
            ModelTestCaseResult(
                name = "Prompt modelu",
                status = ModelTestStatus.PASS,
                details = "System prompt zawiera wszystkie klasy, a user prompt wymusza minimalny JSON.",
            )
        } else {
            ModelTestCaseResult(
                name = "Prompt modelu",
                status = ModelTestStatus.FAIL,
                details = "Brakujace klasy w prompcie: ${missing.joinToString()}",
            )
        }
    }

    private fun adapterWeightBundle(context: Context): ModelTestCaseResult {
        val packageState = LocalModelPackage.inspect(context)
        if (packageState.hasRunnableGgufBundle) {
            return ModelTestCaseResult(
                name = "Pakiet wag adaptera",
                status = ModelTestStatus.PASS,
                details = "Zainstalowano samodzielny model GGUF, wiec adapter QLoRA nie jest wymagany do inferencji na telefonie.",
            )
        }

        val completeLocation = packageState.adapterLocation

        return if (completeLocation != null) {
            val totalBytes = LocalModelPackage.adapterBundleSizeBytes(completeLocation)
            ModelTestCaseResult(
                name = "Pakiet wag adaptera",
                status = ModelTestStatus.PASS,
                details = "Znaleziono ${LocalModelPackage.requiredAdapterFiles.size} plikow adaptera QLoRA w ${completeLocation.path} (${totalBytes / 1024} KiB).",
            )
        } else {
            val missingByLocation = packageState.searchedLocations.joinToString(separator = " | ") { location ->
                val missing = LocalModelPackage.missingAdapterFiles(location)
                "${location.path}: ${missing.joinToString()}"
            }
            ModelTestCaseResult(
                name = "Pakiet wag adaptera",
                status = ModelTestStatus.WARNING,
                details = "Brak kompletnego pakietu. ${missingByLocation}",
            )
        }
    }

    private fun runnableModelBundle(context: Context): ModelTestCaseResult {
        val packageState = LocalModelPackage.inspect(context)
        return if (packageState.hasRunnableGgufBundle) {
            ModelTestCaseResult(
                name = "Pelny model GGUF",
                status = ModelTestStatus.PASS,
                details = "Znaleziono model ${packageState.languageModelFile?.name} i projektor ${packageState.projectorFile?.name}.",
            )
        } else {
            val locations = packageState.searchedLocations.joinToString { it.path }
            val installedAdapter = if (packageState.hasAdapterBundle) {
                "Adapter QLoRA jest zainstalowany, ale to nie jest samodzielny model inferencyjny."
            } else {
                "Nie znaleziono kompletnego adaptera QLoRA."
            }
            ModelTestCaseResult(
                name = "Pelny model GGUF",
                status = ModelTestStatus.WARNING,
                details = "$installedAdapter Do inferencji na telefonie potrzebny jest po merge+quant plik *.gguf oraz *mmproj*.gguf w: $locations.",
            )
        }
    }

    private suspend fun demoInferenceSmoke(): ModelTestCaseResult {
        val engine = inferenceFactory.create(InferenceBackend.MOCK)
        val bitmaps = listOf(
            syntheticBitmap(Color.rgb(49, 86, 48)),
            syntheticBitmap(Color.rgb(112, 72, 38)),
            syntheticBitmap(Color.rgb(188, 196, 124)),
        )

        val results = bitmaps.map { bitmap -> engine.classify(bitmap) }
        val allValid = results.all { it.species.labelId in TaxonomyCatalog.supportedLabelIds && it.rawResponse.contains("label_id") }
        return if (allValid) {
            ModelTestCaseResult(
                name = "Smoke test inferencji",
                status = ModelTestStatus.PASS,
                details = "Demo backend zwrocil poprawny JSON dla ${results.size} obrazow testowych na telefonie.",
            )
        } else {
            ModelTestCaseResult(
                name = "Smoke test inferencji",
                status = ModelTestStatus.FAIL,
                details = "Co najmniej jeden wynik demo backendu nie zawieral poprawnego label_id.",
            )
        }
    }

    private suspend fun localModelReadiness(context: Context): ModelTestCaseResult {
        val bitmap = syntheticBitmap(Color.rgb(64, 92, 54))
        return runCatching {
            inferenceFactory.create(InferenceBackend.LOCAL_MODEL, context).classify(bitmap)
        }.fold(
            onSuccess = { result ->
                ModelTestCaseResult(
                    name = "Runner modelu lokalnego",
                    status = ModelTestStatus.PASS,
                    details = "Lokalny runner zwrocil ${result.species.labelId} w ${result.elapsedMs} ms.",
                )
            },
            onFailure = { throwable ->
                ModelTestCaseResult(
                    name = "Runner modelu lokalnego",
                    status = ModelTestStatus.WARNING,
                    details = throwable.message ?: "Runner lokalny nie jest jeszcze gotowy.",
                )
            },
        )
    }

    private fun syntheticBitmap(color: Int): Bitmap =
        Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888).apply {
            eraseColor(color)
        }
}
