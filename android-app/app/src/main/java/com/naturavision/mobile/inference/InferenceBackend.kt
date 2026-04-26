package com.naturavision.mobile.inference

enum class InferenceBackend(
    val title: String,
    val description: String,
) {
    MOCK(
        title = "Demo",
        description = "Działa od razu i pozwala przetestować cały interfejs bez gotowego modelu.",
    ),
    LOCAL_MODEL(
        title = "Model lokalny",
        description = "Docelowe miejsce pod integrację GGUF lub JNI po zakończeniu treningu.",
    ),
}
