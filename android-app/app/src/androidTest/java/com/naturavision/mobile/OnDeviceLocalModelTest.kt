package com.naturavision.mobile

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.naturavision.mobile.data.TaxonomyCatalog
import com.naturavision.mobile.inference.ForestInferenceFactory
import com.naturavision.mobile.inference.InferenceBackend
import com.naturavision.mobile.inference.LocalModelPackage
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OnDeviceLocalModelTest {
    @Test
    fun localModelRunnerReturnsSupportedLabel() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext as Context
        assumeTrue(LocalModelPackage.inspect(context).hasRunnableGgufBundle)

        val bitmap = Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888).apply {
            eraseColor(Color.rgb(64, 92, 54))
        }
        val result = ForestInferenceFactory()
            .create(InferenceBackend.LOCAL_MODEL, context)
            .classify(bitmap)

        assertTrue(result.species.labelId in TaxonomyCatalog.supportedLabelIds)
        assertTrue(result.rawResponse.contains("label_id", ignoreCase = true))
    }
}
