package com.naturavision.mobile.inference

interface NativeVisionModelBridge {
    fun generate(
        nativeLibraryDir: String,
        request: NativeVisionInferenceRequest,
        imagePng: ByteArray,
    ): String

    fun diagnose(
        nativeLibraryDir: String,
        request: NativeVisionInferenceRequest,
        imagePng: ByteArray,
        profile: NativeVisionDiagnosticsProfile,
    ): String
}

class JniNativeVisionModelBridge : NativeVisionModelBridge {
    override fun generate(
        nativeLibraryDir: String,
        request: NativeVisionInferenceRequest,
        imagePng: ByteArray,
    ): String = generateNative(
        nativeLibraryDir = nativeLibraryDir,
        languageModelPath = request.languageModelPath,
        projectorPath = request.projectorPath,
        systemPrompt = request.systemPrompt,
        userPrompt = request.userPrompt,
        imagePng = imagePng,
        maxNewTokens = request.maxNewTokens,
    )

    override fun diagnose(
        nativeLibraryDir: String,
        request: NativeVisionInferenceRequest,
        imagePng: ByteArray,
        profile: NativeVisionDiagnosticsProfile,
    ): String = diagnoseNative(
        nativeLibraryDir = nativeLibraryDir,
        languageModelPath = request.languageModelPath,
        projectorPath = request.projectorPath,
        systemPrompt = request.systemPrompt,
        userPrompt = request.userPrompt,
        imagePng = imagePng,
        profileName = profile.name,
        maxNewTokens = profile.maxNewTokens,
        gpuLayers = profile.gpuLayers,
        useVisionGpu = profile.useVisionGpu,
        flashAttention = profile.flashAttention.nativeValue,
        imageMinTokens = profile.imageMinTokens,
        imageMaxTokens = profile.imageMaxTokens,
        forceResponsePrefix = profile.forceResponsePrefix,
    )

    private external fun generateNative(
        nativeLibraryDir: String,
        languageModelPath: String,
        projectorPath: String,
        systemPrompt: String,
        userPrompt: String,
        imagePng: ByteArray,
        maxNewTokens: Int,
    ): String

    private external fun diagnoseNative(
        nativeLibraryDir: String,
        languageModelPath: String,
        projectorPath: String,
        systemPrompt: String,
        userPrompt: String,
        imagePng: ByteArray,
        profileName: String,
        maxNewTokens: Int,
        gpuLayers: Int,
        useVisionGpu: Boolean,
        flashAttention: Int,
        imageMinTokens: Int,
        imageMaxTokens: Int,
        forceResponsePrefix: Boolean,
    ): String

    companion object {
        init {
            System.loadLibrary("naturavision-llama")
        }
    }
}
