package com.naturavision.mobile.inference

import android.graphics.Bitmap
import android.util.Log
import com.naturavision.mobile.model.ClassificationResult
import kotlin.system.measureTimeMillis

class JsonForestInferenceEngine(
    private val runner: LocalModelRunner,
) : ForestInferenceEngine {
    override val backendName: String = "Lokalny model NaturaVision"

    override suspend fun classify(bitmap: Bitmap): ClassificationResult {
        var response = ""
        Log.i(TAG, "classification start")
        val elapsed = measureTimeMillis {
            response = runner.run(bitmap)
        }
        Log.i(TAG, "classification finished in ${elapsed}ms, response=$response")
        val species = ModelOutputParser.parse(response)
        return ClassificationResult(
            species = species,
            confidence = 0.0f,
            backendName = backendName,
            elapsedMs = elapsed,
            rawResponse = response,
            note = "Wynik pochodzi bezposrednio z odpowiedzi modelu. Confidence moze zostac dodane, gdy runner zacznie je zwracac.",
        )
    }

    private companion object {
        const val TAG = "NaturaVisionInference"
    }
}
