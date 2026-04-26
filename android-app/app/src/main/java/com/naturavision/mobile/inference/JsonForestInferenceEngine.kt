package com.naturavision.mobile.inference

import android.graphics.Bitmap
import com.naturavision.mobile.model.ClassificationResult
import kotlin.system.measureTimeMillis

class JsonForestInferenceEngine(
    private val runner: LocalModelRunner,
) : ForestInferenceEngine {
    override val backendName: String = "Lokalny model GGUF"

    override suspend fun classify(bitmap: Bitmap): ClassificationResult {
        var response = ""
        var elapsed = 0L
        elapsed = measureTimeMillis {
            response = runner.run(bitmap)
        }
        val species = ModelOutputParser.parse(response)
        return ClassificationResult(
            species = species,
            confidence = 0.0f,
            backendName = backendName,
            elapsedMs = elapsed,
            rawResponse = response,
            note = "Wynik pochodzi bezpośrednio z odpowiedzi modelu. Dodaj własne confidence, gdy runner zacznie je zwracać.",
        )
    }
}
