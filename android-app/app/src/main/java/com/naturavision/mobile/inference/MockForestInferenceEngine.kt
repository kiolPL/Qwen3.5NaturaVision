package com.naturavision.mobile.inference

import android.graphics.Bitmap
import com.naturavision.mobile.data.TaxonomyCatalog
import com.naturavision.mobile.model.ClassificationResult
import com.naturavision.mobile.model.ForestSpecies
import kotlinx.coroutines.delay
import org.json.JSONObject
import kotlin.math.absoluteValue
import kotlin.system.measureTimeMillis

class MockForestInferenceEngine : ForestInferenceEngine {
    override val backendName: String = "Demo backend"

    override suspend fun classify(bitmap: Bitmap): ClassificationResult {
        var result: ClassificationResult? = null
        val elapsed = measureTimeMillis {
            delay(900)
            result = buildResult(bitmap)
        }
        return result!!.copy(elapsedMs = elapsed)
    }

    private fun buildResult(bitmap: Bitmap): ClassificationResult {
        val signature = bitmapSignature(bitmap)
        val species = chooseSpecies(signature)
        val confidence = 0.54f + ((signature % 37).toFloat() / 100f)
        val rawJson = JSONObject()
            .put("label_id", species.labelId)
            .put("kingdom", species.kingdom.name.lowercase())
            .put("scientific_name", species.scientificName)
            .put("polish_name", species.polishName)
            .put("english_name", species.englishName)
            .toString(2)

        return ClassificationResult(
            species = species,
            confidence = confidence.coerceIn(0f, 0.96f),
            backendName = backendName,
            elapsedMs = 0L,
            rawResponse = rawJson,
            note = "To jest wynik demonstracyjny. Po podpięciu lokalnego modelu ten backend zostanie zastąpiony inferencją na urządzeniu.",
        )
    }

    private fun chooseSpecies(signature: Int): ForestSpecies {
        val candidates = TaxonomyCatalog.all
        if (signature % 7 == 0) {
            return ForestSpecies.Unknown
        }
        return candidates[signature.absoluteValue % (candidates.size - 1)]
    }

    private fun bitmapSignature(bitmap: Bitmap): Int {
        val width = bitmap.width
        val height = bitmap.height
        var acc = width * 31 + height
        val stepX = (width / 6).coerceAtLeast(1)
        val stepY = (height / 6).coerceAtLeast(1)
        var y = 0
        while (y < height) {
            var x = 0
            while (x < width) {
                acc = acc * 31 + bitmap.getPixel(x, y)
                x += stepX
            }
            y += stepY
        }
        return acc
    }
}
