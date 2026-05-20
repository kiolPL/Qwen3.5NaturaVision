package com.naturavision.mobile.inference

import java.io.File

data class NativeVisionInferenceRequest(
    val languageModelPath: String,
    val projectorPath: String,
    val systemPrompt: String,
    val userPrompt: String,
    val maxNewTokens: Int,
) {
    val prompt: String = "$systemPrompt\n\n$userPrompt"

    companion object {
        const val MTMD_MEDIA_MARKER = "<__media__>"
        const val MAX_NEW_TOKENS = 48

        fun create(
            languageModel: File,
            projector: File,
            maxNewTokens: Int = MAX_NEW_TOKENS,
        ): NativeVisionInferenceRequest {
            val userPrompt = PromptTemplates.USER_PROMPT
                .replace("<image>", "$MTMD_MEDIA_MARKER\n")

            return NativeVisionInferenceRequest(
                languageModelPath = languageModel.absolutePath,
                projectorPath = projector.absolutePath,
                systemPrompt = PromptTemplates.SYSTEM_PROMPT,
                userPrompt = userPrompt,
                maxNewTokens = maxNewTokens,
            )
        }
    }
}
