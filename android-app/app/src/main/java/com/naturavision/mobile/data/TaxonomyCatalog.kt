package com.naturavision.mobile.data

import com.naturavision.mobile.model.ForestSpecies
import com.naturavision.mobile.model.ForestSpecies.Kingdom

object TaxonomyCatalog {
    val all: List<ForestSpecies> = listOf(
        ForestSpecies("PLANT_01", Kingdom.PLANTS, "Pinus sylvestris", "sosna zwyczajna"),
        ForestSpecies("PLANT_02", Kingdom.PLANTS, "Picea abies", "świerk pospolity"),
        ForestSpecies("PLANT_03", Kingdom.PLANTS, "Betula pendula", "brzoza brodawkowata"),
        ForestSpecies("PLANT_04", Kingdom.PLANTS, "Betula pubescens", "brzoza omszona"),
        ForestSpecies("PLANT_05", Kingdom.PLANTS, "Quercus robur", "dąb szypułkowy"),
        ForestSpecies("PLANT_06", Kingdom.PLANTS, "Quercus petraea", "dąb bezszypułkowy"),
        ForestSpecies("PLANT_07", Kingdom.PLANTS, "Fagus sylvatica", "buk zwyczajny"),
        ForestSpecies("PLANT_08", Kingdom.PLANTS, "Alnus glutinosa", "olsza czarna"),
        ForestSpecies("PLANT_09", Kingdom.PLANTS, "Populus tremula", "osika"),
        ForestSpecies("PLANT_10", Kingdom.PLANTS, "Acer platanoides", "klon zwyczajny"),
        ForestSpecies("PLANT_11", Kingdom.PLANTS, "Sorbus aucuparia", "jarząb pospolity"),
        ForestSpecies("PLANT_12", Kingdom.PLANTS, "Corylus avellana", "leszczyna pospolita"),
        ForestSpecies("PLANT_13", Kingdom.PLANTS, "Vaccinium myrtillus", "borówka czarna"),
        ForestSpecies("PLANT_14", Kingdom.PLANTS, "Vaccinium vitis-idaea", "borówka brusznica"),
        ForestSpecies("PLANT_15", Kingdom.PLANTS, "Calluna vulgaris", "wrzos zwyczajny"),
        ForestSpecies("PLANT_16", Kingdom.PLANTS, "Convallaria majalis", "konwalia majowa"),
        ForestSpecies("PLANT_17", Kingdom.PLANTS, "Oxalis acetosella", "szczawik zajęczy"),
        ForestSpecies("PLANT_18", Kingdom.PLANTS, "Anemone nemorosa", "zawilec gajowy"),
        ForestSpecies("PLANT_19", Kingdom.PLANTS, "Maianthemum bifolium", "konwalijka dwulistna"),
        ForestSpecies("PLANT_20", Kingdom.PLANTS, "Pteridium aquilinum", "orlica pospolita"),
        ForestSpecies("FUN_01", Kingdom.FUNGI, "Boletus edulis", "borowik szlachetny"),
        ForestSpecies("FUN_02", Kingdom.FUNGI, "Leccinum scabrum", "koźlarz babka"),
        ForestSpecies("FUN_03", Kingdom.FUNGI, "Leccinum aurantiacum", "koźlarz czerwony"),
        ForestSpecies("FUN_04", Kingdom.FUNGI, "Cantharellus cibarius", "pieprznik jadalny"),
        ForestSpecies("FUN_05", Kingdom.FUNGI, "Suillus luteus", "maślak zwyczajny"),
        ForestSpecies("FUN_06", Kingdom.FUNGI, "Suillus bovinus", "maślak sitarz"),
        ForestSpecies("FUN_07", Kingdom.FUNGI, "Lactarius deliciosus", "mleczaj rydz"),
        ForestSpecies("FUN_08", Kingdom.FUNGI, "Lactarius deterrimus", "mleczaj świerkowy"),
        ForestSpecies("FUN_09", Kingdom.FUNGI, "Russula cyanoxantha", "gołąbek zielonawofioletowy"),
        ForestSpecies("FUN_10", Kingdom.FUNGI, "Russula claroflava", "gołąbek błotny"),
        ForestSpecies("FUN_11", Kingdom.FUNGI, "Macrolepiota procera", "czubajka kania"),
        ForestSpecies("FUN_12", Kingdom.FUNGI, "Amanita muscaria", "muchomor czerwony"),
        ForestSpecies("FUN_13", Kingdom.FUNGI, "Amanita phalloides", "muchomor sromotnikowy"),
        ForestSpecies("FUN_14", Kingdom.FUNGI, "Armillaria mellea", "opieńka miodowa"),
        ForestSpecies("FUN_15", Kingdom.FUNGI, "Coprinus comatus", "czernidłak kołpakowaty"),
        ForestSpecies("FUN_16", Kingdom.FUNGI, "Lycoperdon perlatum", "purchawka chropowata"),
        ForestSpecies("FUN_17", Kingdom.FUNGI, "Phallus impudicus", "sromotnik bezwstydny"),
        ForestSpecies("FUN_18", Kingdom.FUNGI, "Fomitopsis pinicola", "pniarek obrzeżony"),
        ForestSpecies("FUN_19", Kingdom.FUNGI, "Trametes versicolor", "wrośniak różnobarwny"),
        ForestSpecies("FUN_20", Kingdom.FUNGI, "Xerocomellus chrysenteron", "podgrzybek czerwonawy"),
        ForestSpecies.Unknown,
    )

    val byId: Map<String, ForestSpecies> = all.associateBy(ForestSpecies::labelId)

    fun lookup(labelId: String): ForestSpecies = byId[labelId] ?: ForestSpecies.Unknown
}
