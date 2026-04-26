package com.naturavision.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = MossGreen,
    onPrimary = Mist,
    secondary = PineGreen,
    tertiary = BarkBrown,
    background = Mist,
    surface = Mist,
    surfaceVariant = WarmStone,
    onSurface = ForestInk,
)

private val DarkColors = darkColorScheme(
    primary = Fern,
    secondary = WarmStone,
    tertiary = MossGreen,
    background = ForestInk,
    surface = ForestInk,
    onSurface = Mist,
)

@Composable
fun NaturaVisionTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
