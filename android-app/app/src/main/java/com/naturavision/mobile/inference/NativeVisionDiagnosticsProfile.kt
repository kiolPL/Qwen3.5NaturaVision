package com.naturavision.mobile.inference

enum class NativeFlashAttentionMode(val nativeValue: Int) {
    AUTO(-1),
    DISABLED(0),
}

data class NativeVisionDiagnosticsProfile(
    val name: String,
    val gpuLayers: Int,
    val useVisionGpu: Boolean,
    val flashAttention: NativeFlashAttentionMode,
    val imageMinTokens: Int,
    val imageMaxTokens: Int,
    val forceResponsePrefix: Boolean = true,
    val maxNewTokens: Int = 16,
) {
    init {
        require(name.isNotBlank()) { "Diagnostic profile name cannot be blank." }
        require(imageMinTokens > 0) { "imageMinTokens must be positive." }
        require(imageMaxTokens >= imageMinTokens) { "imageMaxTokens must be >= imageMinTokens." }
        require(maxNewTokens in 1..96) { "maxNewTokens must be in 1..96." }
    }
}

object NativeVisionDiagnosticsProfiles {
    val PhoneVulkanCurrent = NativeVisionDiagnosticsProfile(
        name = "phone_vulkan_current",
        gpuLayers = 99,
        useVisionGpu = true,
        flashAttention = NativeFlashAttentionMode.AUTO,
        imageMinTokens = 1,
        imageMaxTokens = 32,
    )

    val PhoneVulkanNoFlash = NativeVisionDiagnosticsProfile(
        name = "phone_vulkan_no_flash",
        gpuLayers = 99,
        useVisionGpu = true,
        flashAttention = NativeFlashAttentionMode.DISABLED,
        imageMinTokens = 1,
        imageMaxTokens = 32,
    )

    val PhoneCpuTiny = NativeVisionDiagnosticsProfile(
        name = "phone_cpu_tiny",
        gpuLayers = 0,
        useVisionGpu = false,
        flashAttention = NativeFlashAttentionMode.DISABLED,
        imageMinTokens = 1,
        imageMaxTokens = 32,
        maxNewTokens = 4,
    )

    val PhoneVulkanImageTokenLadder = listOf(32, 128, 256, 512, 1024).map { imageTokens ->
        NativeVisionDiagnosticsProfile(
            name = "phone_vulkan_image_tokens_$imageTokens",
            gpuLayers = 99,
            useVisionGpu = true,
            flashAttention = NativeFlashAttentionMode.AUTO,
            imageMinTokens = imageTokens,
            imageMaxTokens = imageTokens,
            maxNewTokens = 4,
        )
    }

    val DefaultPhoneProfiles = listOf(
        PhoneVulkanCurrent,
        PhoneVulkanNoFlash,
    )
}
