package com.naturavision.mobile.inference

import android.graphics.Bitmap

class UnwiredLocalModelRunner : LocalModelRunner {
    override suspend fun run(bitmap: Bitmap): String {
        error(
            "Lokalny runner modelu nie jest jeszcze podlaczony do natywnej biblioteki inferencji. " +
                "Zainstalowany adapter QLoRA nie wystarcza do inferencji na telefonie: trzeba najpierw scalic adapter z Qwen/Qwen3.5-4B, " +
                "wyeksportowac pelny model do GGUF, dodac plik mmproj dla obrazu i podlaczyc runtime JNI/NDK. " +
                "Runner powinien zwracac JSON w formacie {\"label_id\":\"PLANT_01\"}.",
        )
    }
}
