package com.naturavision.mobile.inference

import com.naturavision.mobile.data.TaxonomyCatalog
import com.naturavision.mobile.model.ForestSpecies
import org.json.JSONObject

object ModelOutputParser {
    fun parse(rawJson: String): ForestSpecies {
        val payload = JSONObject(rawJson.trim())
        val labelId = payload.optString("label_id", ForestSpecies.UNKNOWN_LABEL_ID)
        return TaxonomyCatalog.lookup(labelId)
    }
}
