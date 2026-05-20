package com.naturavision.mobile.model

data class ForestSpecies(
    val labelId: String,
    val kingdom: Kingdom,
    val scientificName: String,
    val polishName: String,
    val englishName: String,
) {
    val titleLine: String
        get() = if (labelId == UNKNOWN_LABEL_ID) "Poza rozpoznawana taksonomia" else polishName

    val kingdomLabel: String
        get() = when (kingdom) {
            Kingdom.PLANTS -> "Rosliny"
            Kingdom.FUNGI -> "Grzyby"
            Kingdom.UNKNOWN -> "Unknown"
        }

    val isKnownTarget: Boolean
        get() = kingdom != Kingdom.UNKNOWN

    enum class Kingdom {
        PLANTS,
        FUNGI,
        UNKNOWN,
    }

    companion object {
        const val UNKNOWN_LABEL_ID = "unknown"

        val Unknown = ForestSpecies(
            labelId = UNKNOWN_LABEL_ID,
            kingdom = Kingdom.UNKNOWN,
            scientificName = "unknown",
            polishName = "unknown",
            englishName = "unknown",
        )
    }
}
