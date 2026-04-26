package com.naturavision.mobile.inference

object PromptTemplates {
    const val SYSTEM_PROMPT =
        "You identify one forest organism from a fixed taxonomy and answer in JSON only."

    const val USER_PROMPT =
        "<image>Identify the organism. If it is not in the supported taxonomy or the image is ambiguous, return unknown."
}
