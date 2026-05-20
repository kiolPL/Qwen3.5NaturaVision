package com.naturavision.mobile.inference

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import kotlin.math.max

class LlamaCppLocalModelRunner(
    context: Context,
    private val bridge: NativeVisionModelBridge = JniNativeVisionModelBridge(),
) : LocalModelRunner {
    private val appContext = context.applicationContext
    private val nativeLibraryDir = appContext.applicationInfo.nativeLibraryDir

    override suspend fun run(bitmap: Bitmap): String = withContext(Dispatchers.IO) {
        val packageState = LocalModelPackage.inspect(appContext)
        Log.i(TAG, "searched model locations=${packageState.searchedLocations.joinToString { it.path }}")
        val languageModel = packageState.languageModelFile
            ?: error(missingModelMessage(packageState))
        val projector = packageState.projectorFile
            ?: error(missingModelMessage(packageState))
        Log.i(TAG, "selected languageModel=${languageModel.path}, projector=${projector.path}")

        val request = NativeVisionInferenceRequest.create(
            languageModel = languageModel,
            projector = projector,
        )
        Log.i(TAG, "calling native runner with maxNewTokens=${request.maxNewTokens}")
        bridge.generate(
            nativeLibraryDir = nativeLibraryDir,
            request = request,
            imagePng = bitmap.toPngBytes(maxEdge = 448),
        ).also { output ->
            Log.i(TAG, "native runner returned $output")
        }
    }

    private fun missingModelMessage(packageState: LocalModelPackageState): String {
        val locations = packageState.searchedLocations.joinToString { it.path }
        return "Nie znaleziono kompletnego pakietu GGUF dla lokalnej inferencji. " +
            "Wymagany jest plik modelu *.gguf oraz projektor *mmproj*.gguf w: $locations."
    }

    private companion object {
        const val TAG = "NaturaVisionRunner"
    }
}

private fun Bitmap.toPngBytes(maxEdge: Int): ByteArray {
    val source = if (max(width, height) > maxEdge) {
        val scale = maxEdge.toFloat() / max(width, height).toFloat()
        Bitmap.createScaledBitmap(
            this,
            (width * scale).toInt().coerceAtLeast(1),
            (height * scale).toInt().coerceAtLeast(1),
            true,
        )
    } else {
        this
    }

    return ByteArrayOutputStream().use { output ->
        source.compress(Bitmap.CompressFormat.PNG, 100, output)
        if (source !== this) {
            source.recycle()
        }
        output.toByteArray()
    }
}
