package com.naturavision.mobile.model

data class ClassificationResult(
    val species: ForestSpecies,
    val confidence: Float,
    val backendName: String,
    val elapsedMs: Long,
    val rawResponse: String,
    val note: String? = null,
)
