package com.naturavision.mobile.inference

class ForestInferenceFactory(
    private val localModelRunner: LocalModelRunner = UnwiredLocalModelRunner(),
) {
    fun create(backend: InferenceBackend): ForestInferenceEngine = when (backend) {
        InferenceBackend.MOCK -> MockForestInferenceEngine()
        InferenceBackend.LOCAL_MODEL -> JsonForestInferenceEngine(localModelRunner)
    }
}
