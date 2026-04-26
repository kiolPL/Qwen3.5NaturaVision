package com.naturavision.mobile.inference

import android.graphics.Bitmap
import com.naturavision.mobile.model.ClassificationResult

interface ForestInferenceEngine {
    val backendName: String

    suspend fun classify(bitmap: Bitmap): ClassificationResult
}
