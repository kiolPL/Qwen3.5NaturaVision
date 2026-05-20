package com.naturavision.mobile.data

import com.naturavision.mobile.model.ForestSpecies
import com.naturavision.mobile.model.ForestSpecies.Kingdom

object TaxonomyCatalog {
    val all: List<ForestSpecies> = listOf(
        ForestSpecies("PLANT_01", Kingdom.PLANTS, "Pinus sylvestris", "sosna zwyczajna", "Scots pine"),
        ForestSpecies("PLANT_02", Kingdom.PLANTS, "Picea abies", "swierk pospolity", "Norway spruce"),
        ForestSpecies("PLANT_03", Kingdom.PLANTS, "Betula pendula", "brzoza brodawkowata", "silver birch"),
        ForestSpecies("PLANT_04", Kingdom.PLANTS, "Betula pubescens", "brzoza omszona", "downy birch"),
        ForestSpecies("PLANT_05", Kingdom.PLANTS, "Quercus robur", "dab szypulkowy", "pedunculate oak"),
        ForestSpecies("PLANT_06", Kingdom.PLANTS, "Quercus petraea", "dab bezszypulkowy", "sessile oak"),
        ForestSpecies("PLANT_07", Kingdom.PLANTS, "Fagus sylvatica", "buk zwyczajny", "European beech"),
        ForestSpecies("PLANT_08", Kingdom.PLANTS, "Alnus glutinosa", "olsza czarna", "black alder"),
        ForestSpecies("PLANT_09", Kingdom.PLANTS, "Populus tremula", "osika", "European aspen"),
        ForestSpecies("PLANT_10", Kingdom.PLANTS, "Acer platanoides", "klon zwyczajny", "Norway maple"),
        ForestSpecies("PLANT_11", Kingdom.PLANTS, "Sorbus aucuparia", "jarzab pospolity", "rowan"),
        ForestSpecies("PLANT_12", Kingdom.PLANTS, "Corylus avellana", "leszczyna pospolita", "common hazel"),
        ForestSpecies("PLANT_13", Kingdom.PLANTS, "Vaccinium myrtillus", "borowka czarna", "bilberry"),
        ForestSpecies("PLANT_14", Kingdom.PLANTS, "Vaccinium vitis-idaea", "borowka brusznica", "lingonberry"),
        ForestSpecies("PLANT_15", Kingdom.PLANTS, "Calluna vulgaris", "wrzos zwyczajny", "heather"),
        ForestSpecies("PLANT_16", Kingdom.PLANTS, "Convallaria majalis", "konwalia majowa", "lily of the valley"),
        ForestSpecies("PLANT_17", Kingdom.PLANTS, "Oxalis acetosella", "szczawik zajeczy", "wood sorrel"),
        ForestSpecies("PLANT_18", Kingdom.PLANTS, "Anemone nemorosa", "zawilec gajowy", "wood anemone"),
        ForestSpecies("PLANT_19", Kingdom.PLANTS, "Maianthemum bifolium", "konwalijka dwulistna", "false lily of the valley"),
        ForestSpecies("PLANT_20", Kingdom.PLANTS, "Pteridium aquilinum", "orlica pospolita", "bracken"),
        ForestSpecies("FUN_01", Kingdom.FUNGI, "Boletus edulis", "borowik szlachetny", "king bolete"),
        ForestSpecies("FUN_02", Kingdom.FUNGI, "Leccinum scabrum", "kozlarz babka", "birch bolete"),
        ForestSpecies("FUN_03", Kingdom.FUNGI, "Leccinum aurantiacum", "kozlarz czerwony", "red-capped scaber stalk"),
        ForestSpecies("FUN_04", Kingdom.FUNGI, "Cantharellus cibarius", "pieprznik jadalny", "chanterelle"),
        ForestSpecies("FUN_05", Kingdom.FUNGI, "Suillus luteus", "maslak zwyczajny", "slippery jack"),
        ForestSpecies("FUN_06", Kingdom.FUNGI, "Suillus bovinus", "maslak sitarz", "Jersey cow mushroom"),
        ForestSpecies("FUN_07", Kingdom.FUNGI, "Lactarius deliciosus", "mleczaj rydz", "saffron milk cap"),
        ForestSpecies("FUN_08", Kingdom.FUNGI, "Lactarius deterrimus", "mleczaj swierkowy", "spruce milk cap"),
        ForestSpecies("FUN_09", Kingdom.FUNGI, "Russula cyanoxantha", "golabek zielonawofioletowy", "charcoal burner"),
        ForestSpecies("FUN_10", Kingdom.FUNGI, "Russula claroflava", "golabek blotny", "yellow swamp russula"),
        ForestSpecies("FUN_11", Kingdom.FUNGI, "Macrolepiota procera", "czubajka kania", "parasol mushroom"),
        ForestSpecies("FUN_12", Kingdom.FUNGI, "Amanita muscaria", "muchomor czerwony", "fly agaric"),
        ForestSpecies("FUN_13", Kingdom.FUNGI, "Amanita phalloides", "muchomor sromotnikowy", "death cap"),
        ForestSpecies("FUN_14", Kingdom.FUNGI, "Armillaria mellea", "opienka miodowa", "honey fungus"),
        ForestSpecies("FUN_15", Kingdom.FUNGI, "Coprinus comatus", "czernidlak kolpakowaty", "shaggy ink cap"),
        ForestSpecies("FUN_16", Kingdom.FUNGI, "Lycoperdon perlatum", "purchawka chropowata", "common puffball"),
        ForestSpecies("FUN_17", Kingdom.FUNGI, "Phallus impudicus", "sromotnik bezwstydny", "common stinkhorn"),
        ForestSpecies("FUN_18", Kingdom.FUNGI, "Fomitopsis pinicola", "pniarek obrzezony", "red-belted bracket"),
        ForestSpecies("FUN_19", Kingdom.FUNGI, "Trametes versicolor", "wrosniak roznobarwny", "turkey tail"),
        ForestSpecies("FUN_20", Kingdom.FUNGI, "Xerocomellus chrysenteron", "podgrzybek czerwonawy", "red cracking bolete"),
        ForestSpecies.Unknown,
    )

    val knownTargets: List<ForestSpecies> = all.filter(ForestSpecies::isKnownTarget)
    val plants: List<ForestSpecies> = knownTargets.filter { it.kingdom == Kingdom.PLANTS }
    val fungi: List<ForestSpecies> = knownTargets.filter { it.kingdom == Kingdom.FUNGI }
    val supportedLabelIds: List<String> = all.map(ForestSpecies::labelId)

    private val collapseToPublic: Map<String, String> = mapOf(
        "UNK_NON_TARGET_PLANT" to ForestSpecies.UNKNOWN_LABEL_ID,
        "UNK_NON_TARGET_FUNGUS" to ForestSpecies.UNKNOWN_LABEL_ID,
        "UNK_OTHER_OR_AMBIGUOUS" to ForestSpecies.UNKNOWN_LABEL_ID,
    )

    private val byId: Map<String, ForestSpecies> = all.associateBy(ForestSpecies::labelId)

    val promptTaxonomy: String = knownTargets.joinToString(separator = "\n") { species ->
        "${species.labelId}: ${species.scientificName} (${species.polishName}; ${species.englishName})"
    } + "\n${ForestSpecies.UNKNOWN_LABEL_ID}: organism spoza listy albo obraz niejednoznaczny"

    fun lookup(labelId: String): ForestSpecies {
        val publicLabel = collapseToPublic[labelId] ?: labelId
        return byId[publicLabel] ?: ForestSpecies.Unknown
    }
}
