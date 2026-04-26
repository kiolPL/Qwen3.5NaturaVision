package com.naturavision.mobile.inference

import android.graphics.Bitmap

class UnwiredLocalModelRunner : LocalModelRunner {
    override suspend fun run(bitmap: Bitmap): String {
        error(
            "Backend lokalnego modelu nie jest jeszcze podłączony. " +
                "Tutaj trzeba dodać runner JNI lub bibliotekę inferencyjną dla wyeksportowanego modelu.",
        )
    }
}
