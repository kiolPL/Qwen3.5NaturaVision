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
import com.naturavision.mobile.testing.ModelTestSuite
import com.naturavision.mobile.testing.ModelTestSuiteReport
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
    val isRunningTestSuite: Boolean = false,
    val result: ClassificationResult? = null,
    val testSuiteReport: ModelTestSuiteReport? = null,
    val errorMessage: String? = null,
)

class ForestClassifierViewModel : ViewModel() {
    private val inferenceFactory = ForestInferenceFactory()
    private val modelTestSuite = ModelTestSuite(inferenceFactory)
    private val _uiState = MutableStateFlow(ForestClassifierUiState())
    val uiState: StateFlow<ForestClassifierUiState> = _uiState.asStateFlow()

    fun setBackend(backend: InferenceBackend) {
        _uiState.update { state ->
            state.copy(
                backend = backend,
                errorMessage = null,
                result = null,
                testSuiteReport = null,
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
                testSuiteReport = null,
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
                    testSuiteReport = null,
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

    fun analyze(context: Context) {
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
                inferenceFactory.create(backend, context.applicationContext).classify(bitmap)
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

    fun runModelTestSuite(context: Context) {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isRunningTestSuite = true,
                    errorMessage = null,
                    testSuiteReport = null,
                )
            }
            runCatching {
                modelTestSuite.run(context.applicationContext)
            }.onSuccess { report ->
                _uiState.update {
                    it.copy(
                        isRunningTestSuite = false,
                        testSuiteReport = report,
                    )
                }
            }.onFailure { throwable ->
                _uiState.update {
                    it.copy(
                        isRunningTestSuite = false,
                        errorMessage = throwable.message ?: "Test suite nie zakonczyl sie poprawnie.",
                    )
                }
            }
        }
    }

    fun clearSelection() {
        _uiState.value = ForestClassifierUiState(
            backend = _uiState.value.backend,
            testSuiteReport = _uiState.value.testSuiteReport,
        )
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
