package com.naturavision.mobile.ui

import android.graphics.Bitmap
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Bolt
import androidx.compose.material.icons.rounded.CameraAlt
import androidx.compose.material.icons.rounded.Forest
import androidx.compose.material.icons.rounded.ImageSearch
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material.icons.rounded.RestartAlt
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.naturavision.mobile.inference.InferenceBackend
import com.naturavision.mobile.model.ClassificationResult

@Composable
fun NaturaVisionRoute(
    viewModel: ForestClassifierViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val galleryLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
    ) { uri ->
        if (uri != null) {
            viewModel.onGalleryImage(context, uri)
        }
    }
    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicturePreview(),
    ) { bitmap ->
        if (bitmap != null) {
            viewModel.onCameraPreview(bitmap)
        }
    }

    NaturaVisionScreen(
        state = state,
        onPickFromGallery = {
            galleryLauncher.launch(
                PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
            )
        },
        onCapturePhoto = { cameraLauncher.launch(null) },
        onAnalyze = viewModel::analyze,
        onClear = viewModel::clearSelection,
        onBackendSelected = viewModel::setBackend,
    )
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun NaturaVisionScreen(
    state: ForestClassifierUiState,
    onPickFromGallery: () -> Unit,
    onCapturePhoto: () -> Unit,
    onAnalyze: () -> Unit,
    onClear: () -> Unit,
    onBackendSelected: (InferenceBackend) -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("NaturaVision", fontWeight = FontWeight.Bold)
                        Text(
                            "Aplikacja Android do lokalnej identyfikacji gatunków leśnych",
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                },
            )
        },
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                IntroCard()
            }
            item {
                BackendCard(
                    selected = state.backend,
                    onSelected = onBackendSelected,
                )
            }
            item {
                ImagePickerCard(
                    bitmap = state.selectedBitmap,
                    sourceLabel = state.sourceLabel,
                    isPreparingImage = state.isPreparingImage,
                    onPickFromGallery = onPickFromGallery,
                    onCapturePhoto = onCapturePhoto,
                    onClear = onClear,
                )
            }
            item {
                AnalyzeCard(
                    canAnalyze = state.selectedBitmap != null && !state.isPreparingImage,
                    isAnalyzing = state.isAnalyzing,
                    backend = state.backend,
                    onAnalyze = onAnalyze,
                )
            }
            state.errorMessage?.let { error ->
                item {
                    StatusCard(
                        title = "Problem",
                        text = error,
                    )
                }
            }
            state.result?.let { result ->
                item {
                    ResultCard(result)
                }
            }
        }
    }
}

@Composable
private fun IntroCard() {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.Forest, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(
                    "Gotowy szkielet pod lokalny model",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Text(
                "Ta aplikacja jest przygotowana pod późniejsze podpięcie modelu wytrenowanego w projekcie NaturaVision. " +
                    "Już teraz obsługuje wybór zdjęcia, analizę i prezentację wyniku, a backend inferencji można podmienić bez przebudowy UI.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun BackendCard(
    selected: InferenceBackend,
    onSelected: (InferenceBackend) -> Unit,
) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Backend inferencji", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                InferenceBackend.entries.forEach { backend ->
                    FilterChip(
                        selected = backend == selected,
                        onClick = { onSelected(backend) },
                        label = { Text(backend.title) },
                        leadingIcon = {
                            Icon(
                                imageVector = if (backend == InferenceBackend.MOCK) Icons.Rounded.Bolt else Icons.Rounded.ImageSearch,
                                contentDescription = null,
                            )
                        },
                    )
                }
            }
            Text(
                selected.description,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun ImagePickerCard(
    bitmap: Bitmap?,
    sourceLabel: String?,
    isPreparingImage: Boolean,
    onPickFromGallery: () -> Unit,
    onCapturePhoto: () -> Unit,
    onClear: () -> Unit,
) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Zdjęcie wejściowe", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            if (bitmap == null) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(4f / 3f)
                        .clip(RoundedCornerShape(20.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant),
                    contentAlignment = Alignment.Center,
                ) {
                    if (isPreparingImage) {
                        CircularProgressIndicator()
                    } else {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                imageVector = Icons.Rounded.ImageSearch,
                                contentDescription = null,
                                modifier = Modifier.size(42.dp),
                            )
                            Spacer(Modifier.height(8.dp))
                            Text("Wybierz zdjęcie z galerii albo zrób nowe zdjęcie.")
                        }
                    }
                }
            } else {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = "Wybrane zdjęcie",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(4f / 3f)
                        .clip(RoundedCornerShape(20.dp)),
                )
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onCapturePhoto, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Rounded.CameraAlt, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Aparat")
                }
                OutlinedButton(onClick = onPickFromGallery, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Rounded.PhotoLibrary, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Galeria")
                }
            }

            if (bitmap != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    AssistChip(
                        onClick = {},
                        label = { Text(sourceLabel ?: "Źródło nieznane") },
                    )
                    OutlinedButton(onClick = onClear) {
                        Icon(Icons.Rounded.RestartAlt, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Wyczyść")
                    }
                }
            }
        }
    }
}

@Composable
private fun AnalyzeCard(
    canAnalyze: Boolean,
    isAnalyzing: Boolean,
    backend: InferenceBackend,
    onAnalyze: () -> Unit,
) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Analiza", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                if (backend == InferenceBackend.MOCK) {
                    "Tryb demo pozwala przetestować cały przepływ aplikacji jeszcze przed podłączeniem wytrenowanego modelu."
                } else {
                    "Tryb modelu lokalnego jest gotowy architektonicznie, ale czeka na finalny runner GGUF lub JNI."
                },
                style = MaterialTheme.typography.bodyMedium,
            )
            Button(
                onClick = onAnalyze,
                enabled = canAnalyze && !isAnalyzing,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (isAnalyzing) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text("Analizuję...")
                } else {
                    Text("Uruchom analizę")
                }
            }
        }
    }
}

@Composable
private fun StatusCard(
    title: String,
    text: String,
) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ResultCard(result: ClassificationResult) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Wynik", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(result.species.titleLine, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(result.species.scientificName, style = MaterialTheme.typography.bodyLarge)

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                AssistChip(
                    onClick = {},
                    label = { Text(result.species.labelId) },
                )
                AssistChip(
                    onClick = {},
                    label = { Text(result.backendName) },
                )
                AssistChip(
                    onClick = {},
                    label = { Text("${result.elapsedMs} ms") },
                )
            }

            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Pewność: ${(result.confidence * 100).toInt()}%")
                LinearProgressIndicator(
                    progress = result.confidence.coerceIn(0f, 1f),
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            result.note?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }

            Text("Surowa odpowiedź modelu", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            SelectionContainer {
                Text(
                    text = result.rawResponse,
                    style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(16.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                        .padding(12.dp),
                )
            }
        }
    }
}
