package com.naturavision.mobile.inference

import com.naturavision.mobile.data.TaxonomyCatalog
import com.naturavision.mobile.model.ForestSpecies

object ModelOutputParser {
    private val labelIdPattern = Regex(
        pattern = """"?label_id"?\s*:\s*"?([A-Za-z0-9_]+)"?""",
        option = RegexOption.IGNORE_CASE,
    )

    fun parse(rawJson: String): ForestSpecies {
        val labelId = labelIdPattern
            .find(extractJsonObject(rawJson))
            ?.groupValues
            ?.getOrNull(1)
            ?.trim()
            ?: ForestSpecies.UNKNOWN_LABEL_ID
        return TaxonomyCatalog.lookup(labelId)
    }

    fun extractLabelId(rawJson: String): String = parse(rawJson).labelId

    private fun extractJsonObject(rawText: String): String {
        val trimmed = rawText.trim()
        val start = trimmed.indexOf('{')
        val end = trimmed.lastIndexOf('}')
        if (start >= 0 && end > start) {
            return trimmed.substring(start, end + 1)
        }
        return """{"label_id":"${ForestSpecies.UNKNOWN_LABEL_ID}"}"""
    }
}
