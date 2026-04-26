package com.naturavision.mobile.model

data class ForestSpecies(
    val labelId: String,
    val kingdom: Kingdom,
    val scientificName: String,
    val polishName: String,
) {
    val titleLine: String
        get() = if (labelId == UNKNOWN_LABEL_ID) "Nieznany gatunek" else polishName

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
        )
    }
}
