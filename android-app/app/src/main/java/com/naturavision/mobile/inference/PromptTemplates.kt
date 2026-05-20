package com.naturavision.mobile.inference

import com.naturavision.mobile.data.TaxonomyCatalog

object PromptTemplates {
    private val supportedLabels = TaxonomyCatalog.supportedLabelIds.joinToString(separator = ",")

    val SYSTEM_PROMPT: String =
        "You identify one forest organism from an image. " +
            "Do not think step by step. Do not output <think>. " +
            "Return JSON only as {\"label_id\":\"<id>\"}. " +
            "Allowed label_id values: $supportedLabels."

    const val USER_PROMPT =
        "<image>Classify the forest organism. If uncertain or out of taxonomy, return {\"label_id\":\"unknown\"}."
}
