package com.naturavision.mobile.inference

enum class InferenceBackend(
    val title: String,
    val description: String,
) {
    MOCK(
        title = "Demo",
        description = "Dziala od razu i pozwala przetestowac caly interfejs bez wag modelu.",
    ),
    LOCAL_MODEL(
        title = "Model lokalny",
        description = "Docelowa sciezka dla pelnego modelu GGUF z projektorem obrazu i runtime JNI. Sam adapter QLoRA nie wystarcza do inferencji.",
    ),
}
