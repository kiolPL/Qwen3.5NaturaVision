package com.naturavision.mobile.inference

import android.graphics.Bitmap

interface LocalModelRunner {
    suspend fun run(bitmap: Bitmap): String
}
