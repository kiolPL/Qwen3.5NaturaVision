package com.naturavision.mobile.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.naturavision.mobile.inference.ForestInferenceFactory
import com.naturavision.mobile.inference.InferenceBackend
import com.naturavision.mobile.model.ClassificationResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.max

data class ForestClassifierUiState(
    val backend: InferenceBackend = InferenceBackend.MOCK,
    val selectedBitmap: Bitmap? = null,
    val sourceLabel: String? = null,
    val isPreparingImage: Boolean = false,
    val isAnalyzing: Boolean = false,
    val result: ClassificationResult? = null,
    val errorMessage: String? = null,
)

class ForestClassifierViewModel : ViewModel() {
    private val inferenceFactory = ForestInferenceFactory()
    private val _uiState = MutableStateFlow(ForestClassifierUiState())
    val uiState: StateFlow<ForestClassifierUiState> = _uiState.asStateFlow()

    fun setBackend(backend: InferenceBackend) {
        _uiState.update { state ->
            state.copy(
                backend = backend,
                errorMessage = null,
                result = null,
            )
        }
    }

    fun onCameraPreview(bitmap: Bitmap) {
        _uiState.update { state ->
            state.copy(
                selectedBitmap = bitmap,
                sourceLabel = "Aparat",
                isPreparingImage = false,
                result = null,
                errorMessage = null,
            )
        }
    }

    fun onGalleryImage(context: Context, uri: Uri) {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isPreparingImage = true,
                    errorMessage = null,
                    result = null,
                )
            }
            runCatching {
                decodeBitmap(context, uri)
            }.onSuccess { bitmap ->
                _uiState.update {
                    it.copy(
                        selectedBitmap = bitmap,
                        sourceLabel = "Galeria",
                        isPreparingImage = false,
                    )
                }
            }.onFailure { throwable ->
                _uiState.update {
                    it.copy(
                        isPreparingImage = false,
                        errorMessage = throwable.message ?: "Nie udało się wczytać obrazu.",
                    )
                }
            }
        }
    }

    fun analyze() {
        val bitmap = _uiState.value.selectedBitmap ?: run {
            _uiState.update { it.copy(errorMessage = "Najpierw wybierz zdjęcie do analizy.") }
            return
        }
        val backend = _uiState.value.backend
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isAnalyzing = true,
                    result = null,
                    errorMessage = null,
                )
            }
            runCatching {
                inferenceFactory.create(backend).classify(bitmap)
            }.onSuccess { result ->
                _uiState.update {
                    it.copy(
                        isAnalyzing = false,
                        result = result,
                    )
                }
            }.onFailure { throwable ->
                _uiState.update {
                    it.copy(
                        isAnalyzing = false,
                        errorMessage = throwable.message ?: "Analiza obrazu nie powiodła się.",
                    )
                }
            }
        }
    }

    fun clearSelection() {
        _uiState.value = ForestClassifierUiState(backend = _uiState.value.backend)
    }

    private suspend fun decodeBitmap(context: Context, uri: Uri): Bitmap = withContext(Dispatchers.IO) {
        val source = ImageDecoder.createSource(context.contentResolver, uri)
        ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
            decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
            val maxEdge = max(info.size.width, info.size.height)
            if (maxEdge > 1600) {
                val scale = 1600f / maxEdge.toFloat()
                val targetWidth = (info.size.width * scale).toInt().coerceAtLeast(1)
                val targetHeight = (info.size.height * scale).toInt().coerceAtLeast(1)
                decoder.setTargetSize(targetWidth, targetHeight)
            }
        }
    }
}
