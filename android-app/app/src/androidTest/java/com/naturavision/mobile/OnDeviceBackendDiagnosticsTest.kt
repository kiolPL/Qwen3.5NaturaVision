package com.naturavision.mobile

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.naturavision.mobile.inference.JniNativeVisionModelBridge
import com.naturavision.mobile.inference.LocalModelPackage
import com.naturavision.mobile.inference.NativeVisionDiagnosticsProfile
import com.naturavision.mobile.inference.NativeVisionDiagnosticsProfiles
import com.naturavision.mobile.inference.NativeVisionInferenceRequest
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.io.File
import kotlin.io.println

@RunWith(AndroidJUnit4::class)
class OnDeviceBackendDiagnosticsTest {
    @Test
    fun phoneBackendProfilesEmitDiagnosticReports() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext as Context
        val packageState = LocalModelPackage.inspect(context)
        assumeTrue(packageState.hasRunnableGgufBundle)

        val request = NativeVisionInferenceRequest.create(
            languageModel = packageState.languageModelFile!!,
            projector = packageState.projectorFile!!,
            maxNewTokens = 16,
        )
        runProfiles(
            context = context,
            request = request,
            profiles = selectedDefaultProfiles(),
        )
    }

    @Test
    fun public2bPhoneProfileEmitsDiagnosticReportWhenBundleExists() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext as Context
        val packageState = LocalModelPackage.inspect(context)
        val languageModel = packageState.searchedLocations.firstNotNullOfOrNull(::findPublic2bLanguageModel)
        val projector = packageState.searchedLocations.firstNotNullOfOrNull(::findPublic2bProjector)
        assumeTrue(languageModel != null && projector != null)

        val request = NativeVisionInferenceRequest.create(
            languageModel = languageModel!!,
            projector = projector!!,
            maxNewTokens = 16,
        )
        runProfiles(
            context = context,
            request = request,
            profiles = listOf(
                NativeVisionDiagnosticsProfiles.PhoneVulkanCurrent.copy(name = "public_2b_phone"),
            ),
        )
    }

    private fun selectedDefaultProfiles(): List<NativeVisionDiagnosticsProfile> {
        val args = InstrumentationRegistry.getArguments()
        args.getString("diagnosticProfile")?.let { profileName ->
            return listOf(resolveDiagnosticProfile(profileName))
        }
        return buildList {
            addAll(NativeVisionDiagnosticsProfiles.DefaultPhoneProfiles)
            if (args.getString("includeCpuTiny") == "true") {
                add(NativeVisionDiagnosticsProfiles.PhoneCpuTiny)
            }
            if (args.getString("includeImageTokenLadder") == "true") {
                addAll(NativeVisionDiagnosticsProfiles.PhoneVulkanImageTokenLadder)
            }
        }
    }

    private fun resolveDiagnosticProfile(profileName: String): NativeVisionDiagnosticsProfile {
        val selectableProfiles = buildList {
            addAll(NativeVisionDiagnosticsProfiles.DefaultPhoneProfiles)
            add(NativeVisionDiagnosticsProfiles.PhoneCpuTiny)
            addAll(NativeVisionDiagnosticsProfiles.PhoneVulkanImageTokenLadder)
        }
        return selectableProfiles.firstOrNull { it.name == profileName }
            ?: error(
                "Unknown diagnosticProfile=$profileName. Available profiles: " +
                    selectableProfiles.joinToString { it.name },
            )
    }

    private fun runProfiles(
        context: Context,
        request: NativeVisionInferenceRequest,
        profiles: List<NativeVisionDiagnosticsProfile>,
    ) {
        val bridge = JniNativeVisionModelBridge()
        val imagePng = Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888)
            .apply { eraseColor(Color.rgb(64, 92, 54)) }
            .toPngBytes()
        val nativeLibraryDir = context.applicationInfo.nativeLibraryDir

        profiles.forEach { profile ->
            val reportText = bridge.diagnose(
                nativeLibraryDir = nativeLibraryDir,
                request = request,
                imagePng = imagePng,
                profile = profile,
            )
            Log.i(TAG, "diagnostic_report=$reportText")
            println("diagnostic_report=$reportText")
            InstrumentationRegistry.getInstrumentation().sendStatus(
                0,
                Bundle().apply {
                    putString("diagnostic_profile", profile.name)
                    putString("diagnostic_report", reportText)
                },
            )

            val report = JSONObject(reportText)
            assertEquals(profile.name, report.getString("profile"))
            assertEquals(profile.maxNewTokens, report.getInt("max_new_tokens"))
            assertEquals(profile.imageMinTokens, report.getInt("image_min_tokens"))
            assertEquals(profile.imageMaxTokens, report.getInt("image_max_tokens"))
            assertTrue(report.getJSONArray("first_token_ids").length() <= 16)
            assertTrue(report.has("raw_text"))
            assertTrue(report.has("normalized_text"))
            assertTrue(report.getLong("prefill_ms") >= 0L)
            assertTrue(report.getLong("generation_ms") >= 0L)
        }
    }

    private fun findPublic2bLanguageModel(location: File): File? =
        location.listFiles()
            ?.filter { file -> file.isFile && file.extension.equals("gguf", ignoreCase = true) }
            ?.filter { file -> file.name.contains("2b", ignoreCase = true) }
            ?.firstOrNull { file ->
                !file.name.contains("mmproj", ignoreCase = true) &&
                    !file.name.contains("projector", ignoreCase = true)
            }

    private fun findPublic2bProjector(location: File): File? =
        location.listFiles()
            ?.filter { file -> file.isFile && file.extension.equals("gguf", ignoreCase = true) }
            ?.filter { file -> file.name.contains("2b", ignoreCase = true) }
            ?.firstOrNull { file ->
                file.name.contains("mmproj", ignoreCase = true) ||
                    file.name.contains("projector", ignoreCase = true)
            }

    private fun Bitmap.toPngBytes(): ByteArray =
        ByteArrayOutputStream().use { output ->
            compress(Bitmap.CompressFormat.PNG, 100, output)
            output.toByteArray()
        }

    private companion object {
        const val TAG = "NaturaVisionDiag"
    }
}
