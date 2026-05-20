package com.naturavision.mobile.inference

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class NativeVisionInferenceRequestTest {
    @Test
    fun requestUsesMtmdImageMarkerAndStrictJsonPrompt() {
        val languageModel = File("/models/forest-q4.gguf")
        val projector = File("/models/forest-mmproj.gguf")
        val request = NativeVisionInferenceRequest.create(
            languageModel = languageModel,
            projector = projector,
        )

        assertEquals(languageModel.absolutePath, request.languageModelPath)
        assertEquals(projector.absolutePath, request.projectorPath)
        assertEquals(48, request.maxNewTokens)
        assertTrue(request.prompt.contains("<__media__>"))
        assertTrue(request.prompt.contains("Return JSON only"))
        assertTrue(request.prompt.contains("""{"label_id":"unknown"}"""))
    }
}
