package com.naturavision.mobile

import com.naturavision.mobile.data.TaxonomyCatalog
import com.naturavision.mobile.inference.ModelOutputParser
import com.naturavision.mobile.inference.PromptTemplates
import com.naturavision.mobile.model.ForestSpecies
import com.naturavision.mobile.model.ForestSpecies.Kingdom
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TaxonomyAndPromptTest {
    @Test
    fun taxonomyContainsExpectedClosedSet() {
        assertEquals(41, TaxonomyCatalog.all.size)
        assertEquals(40, TaxonomyCatalog.knownTargets.size)
        assertEquals(20, TaxonomyCatalog.plants.size)
        assertEquals(20, TaxonomyCatalog.fungi.size)
        assertEquals(ForestSpecies.Unknown, TaxonomyCatalog.lookup(ForestSpecies.UNKNOWN_LABEL_ID))
    }

    @Test
    fun labelIdsAreUniqueAndHaveExpectedPrefixes() {
        val labels = TaxonomyCatalog.supportedLabelIds

        assertEquals(labels.size, labels.toSet().size)
        assertTrue(TaxonomyCatalog.plants.all { it.kingdom == Kingdom.PLANTS && it.labelId.startsWith("PLANT_") })
        assertTrue(TaxonomyCatalog.fungi.all { it.kingdom == Kingdom.FUNGI && it.labelId.startsWith("FUN_") })
    }

    @Test
    fun unknownSubclassesCollapseToPublicUnknown() {
        assertEquals(ForestSpecies.Unknown, TaxonomyCatalog.lookup("UNK_NON_TARGET_PLANT"))
        assertEquals(ForestSpecies.Unknown, TaxonomyCatalog.lookup("UNK_NON_TARGET_FUNGUS"))
        assertEquals(ForestSpecies.Unknown, TaxonomyCatalog.lookup("UNK_OTHER_OR_AMBIGUOUS"))
    }

    @Test
    fun parserAcceptsStrictJsonAndTextWrappedJson() {
        assertEquals("PLANT_01", ModelOutputParser.extractLabelId("""{"label_id":"PLANT_01"}"""))
        assertEquals("FUN_12", ModelOutputParser.extractLabelId("""thinking... {"label_id":"FUN_12"} done"""))
        assertEquals(ForestSpecies.UNKNOWN_LABEL_ID, ModelOutputParser.extractLabelId("""<think></think>{label_id:unknown}"""))
    }

    @Test
    fun parserFallsBackToUnknownForInvalidOrUnsupportedOutput() {
        assertEquals(ForestSpecies.UNKNOWN_LABEL_ID, ModelOutputParser.extractLabelId("not json"))
        assertEquals(ForestSpecies.UNKNOWN_LABEL_ID, ModelOutputParser.extractLabelId("""{"label_id":"DOG"}"""))
    }

    @Test
    fun promptContainsEveryKnownLabelAndRequiresJsonOnly() {
        TaxonomyCatalog.all.forEach { species ->
            assertTrue(PromptTemplates.SYSTEM_PROMPT.contains(species.labelId))
        }
        assertTrue(PromptTemplates.SYSTEM_PROMPT.contains("Return JSON only"))
        assertTrue(PromptTemplates.SYSTEM_PROMPT.contains("Do not output <think>"))
        assertTrue(PromptTemplates.USER_PROMPT.contains(ForestSpecies.UNKNOWN_LABEL_ID))
        assertTrue(PromptTemplates.USER_PROMPT.contains("Classify the forest organism"))
    }
}
