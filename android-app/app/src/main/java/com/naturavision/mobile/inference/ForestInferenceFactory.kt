package com.naturavision.mobile.inference

import android.content.Context

class ForestInferenceFactory {
    fun create(
        backend: InferenceBackend,
        context: Context? = null,
    ): ForestInferenceEngine = when (backend) {
        InferenceBackend.MOCK -> MockForestInferenceEngine()
        InferenceBackend.LOCAL_MODEL -> JsonForestInferenceEngine(
            context?.let { LlamaCppLocalModelRunner(it.applicationContext) }
                ?: UnwiredLocalModelRunner(),
        )
    }
}
