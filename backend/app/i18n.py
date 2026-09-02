"""Turkish for the prose the API writes.

Anything with a stable key — a sector, a material, a workflow status, one of
the eight checks — is named by the interface, which holds one catalogue for
both languages. What lives here is the text that has no key to name it by: the
standing disclaimer, the scope and principles on the transparency page, the
signal summaries, and the sentences the pilot and impact services compose out
of live figures.

A request carries `?lang=`; anything other than a language listed here falls
back to English rather than failing, so an old client keeps working.
"""

from __future__ import annotations

from fastapi import Query

DEFAULT_LANG = "en"
LANGUAGES = ("en", "tr")


def resolve_lang(
    lang: str = Query(default=DEFAULT_LANG, description="Response language: en or tr"),
) -> str:
    return lang if lang in LANGUAGES else DEFAULT_LANG


# --------------------------------------------------------------------------- #
# Fixed prose
# --------------------------------------------------------------------------- #

TEXT: dict[str, dict[str, str]] = {
    "disclaimer": {
        "en": (
            "The priority score is an inspection prioritisation indicator. It is not a "
            "probability of violation and not a legal conclusion. Final decisions remain with "
            "authorised human auditors."
        ),
        "tr": (
            "Öncelik puanı bir denetim önceliklendirme göstergesidir. İhlal olasılığı değildir "
            "ve hukuki bir sonuç değildir. Nihai kararlar yetkili insan denetçilere aittir."
        ),
    },
}

LISTS: dict[str, dict[str, list[str]]] = {
    "does": {
        "en": [
            "Ranks companies for inspection using the data already held about them.",
            "Compares a declaration with the same company's earlier filings.",
            "Compares a declaration with companies of similar sector, size and output.",
            "States which evidence produced each result and how much it contributed.",
            "Reports when a check could not be run, and why.",
            "Keeps every auditor decision in a log that cannot be quietly edited.",
        ],
        "tr": [
            "Firmaları, haklarında hâlihazırda tutulan veriyle denetim için sıralar.",
            "Bir beyanı, aynı firmanın önceki beyanlarıyla karşılaştırır.",
            "Bir beyanı, benzer sektör, büyüklük ve üretimdeki firmalarla karşılaştırır.",
            "Her sonucu hangi kanıtın ürettiğini ve ne kadar katkı verdiğini belirtir.",
            "Bir kontrolün ne zaman çalıştırılamadığını ve nedenini bildirir.",
            "Her denetçi kararını, sessizce değiştirilemeyen bir kayda işler.",
        ],
    },
    "does_not": {
        "en": [
            "Decide whether a company has broken the law.",
            "Issue penalties or start proceedings.",
            "Treat a low score as a finding of compliance.",
            "Treat missing data as evidence of good standing.",
            "Replace the judgement of the inspector who visits the site.",
        ],
        "tr": [
            "Bir firmanın kanunu ihlal edip etmediğine karar vermez.",
            "Ceza kesmez veya işlem başlatmaz.",
            "Düşük bir puanı uygunluk tespiti saymaz.",
            "Eksik veriyi iyi durumda olmanın kanıtı saymaz.",
            "Sahaya giden denetçinin takdirinin yerine geçmez.",
        ],
    },
}

PRINCIPLES: dict[str, list[tuple[str, str]]] = {
    "en": [
        (
            "Absent evidence is not clean evidence",
            "A check that cannot run is reported as unavailable and its weight is removed from "
            "the calculation. It is never recorded as a check that passed.",
        ),
        (
            "The interval widens when the inputs are thin",
            "An expected range is only as tight as the data behind it. Where records are "
            "incomplete the range opens up, so a company is not flagged on the strength of a "
            "figure the platform never had.",
        ),
        (
            "Every score is reproducible",
            "Each result carries the engine, the model version and the policy version that "
            "produced it, and the comparisons behind each signal are stated in full.",
        ),
        (
            "Decisions are appended, not overwritten",
            "Changing a company's standing writes a new record linked to the one before it. "
            "Altering the history breaks the chain and the check reports where.",
        ),
    ],
    "tr": [
        (
            "Kanıtın yokluğu temiz kanıt değildir",
            "Çalıştırılamayan bir kontrol, kullanılamaz olarak bildirilir ve ağırlığı "
            "hesaplamadan çıkarılır. Hiçbir zaman geçmiş bir kontrol olarak kaydedilmez.",
        ),
        (
            "Girdiler zayıfsa aralık genişler",
            "Beklenen bir aralık, ancak arkasındaki veri kadar dardır. Kayıtların eksik olduğu "
            "yerde aralık açılır; böylece bir firma, platformun hiç sahip olmadığı bir rakama "
            "dayanılarak işaretlenmez.",
        ),
        (
            "Her puan yeniden üretilebilir",
            "Her sonuç; kendisini üreten motoru, model sürümünü ve politika sürümünü taşır ve "
            "her sinyalin arkasındaki karşılaştırmalar eksiksiz belirtilir.",
        ),
        (
            "Kararlar eklenir, üzerine yazılmaz",
            "Bir firmanın durumunu değiştirmek, bir öncekine bağlı yeni bir kayıt yazar. "
            "Geçmişi değiştirmek zinciri kırar ve kontrol nerede kırıldığını bildirir.",
        ),
    ],
}

SIGNAL_SUMMARIES: dict[str, dict[str, str]] = {
    "E1": {
        "en": "Declared packaging against the company's own established declaration behaviour.",
        "tr": "Beyan edilen ambalaj, firmanın kendi yerleşik beyan davranışına karşı.",
    },
    "E2": {
        "en": "Declared packaging against the volume the company's own output and imports imply.",
        "tr": "Beyan edilen ambalaj, firmanın üretim ve ithalatının ima ettiği hacme karşı.",
    },
    "E3": {
        "en": "Packaging intensity against comparable companies in the same sector and size class.",
        "tr": "Ambalaj yoğunluğu, aynı sektör ve büyüklük sınıfındaki benzer firmalara karşı.",
    },
    "E4": {
        "en": "Movement in output compared with movement in the declared amount.",
        "tr": "Üretimdeki değişimin, beyan edilen miktardaki değişimle karşılaştırılması.",
    },
    "E5": {
        "en": "Stability of the declared packaging intensity across reporting periods.",
        "tr": "Beyan edilen ambalaj yoğunluğunun raporlama dönemleri boyunca istikrarı.",
    },
    "E6": {
        "en": "Rounding, repetition and threshold behaviour in the reported figures.",
        "tr": "Bildirilen rakamlardaki yuvarlama, tekrar ve eşik davranışı.",
    },
    "E7": {
        "en": "Site observations set against what the company reported for the same period.",
        "tr": "Saha gözlemlerinin, firmanın aynı dönem için bildirdikleriyle karşılaştırılması.",
    },
    "E8": {
        "en": "Packaging implied by declared GTIP lines against the packaging reported.",
        "tr": "Beyan edilen GTİP kalemlerinin ima ettiği ambalajın, bildirilen ambalaja karşı.",
    },
}

SIGNAL_INPUTS: dict[str, str] = {
    "Declaration history": "Beyan geçmişi",
    "Production volume": "Üretim miktarı",
    "Import volume": "İthalat miktarı",
    "Sector coefficients": "Sektör katsayıları",
    "Packaging coefficients": "Ambalaj katsayıları",
    "Peer cohort": "Emsal grubu",
    "Field inspection records": "Saha denetim kayıtları",
    "GTIP customs lines": "GTİP gümrük kalemleri",
}

# Engine prose is looked up by its English text: there are two engines, the
# strings are stable, and a lookup beats threading a key through the scoring
# registry, which has no business knowing about languages.
ENGINE_STRINGS: dict[str, str] = {
    "Eight independent comparisons against the company's own history, its output, its peer "
    "group and its customs lines.": (
        "Firmanın kendi geçmişine, üretimine, emsal grubuna ve gümrük kalemlerine karşı sekiz "
        "bağımsız karşılaştırma."
    ),
    "Sector coefficients adjusted by the company's own declaration behaviour, widened where "
    "inputs are incomplete.": (
        "Firmanın kendi beyan davranışına göre düzeltilmiş sektör katsayıları; girdiler eksik "
        "olduğunda genişletilir."
    ),
    "Gradient boosted quantile models over production, import, sector and history features, "
    "with a conformal step that calibrates the interval separately for each sector and size "
    "group.": (
        "Üretim, ithalat, sektör ve geçmiş öznitelikleri üzerinde gradyan artırmalı kuantil "
        "modelleri; aralığı her sektör ve büyüklük grubu için ayrı kalibre eden bir konformal "
        "adımla birlikte."
    ),
    "q05, q50 and q95 predictions, widened by the conformal residual for the company's own "
    "group.": (
        "q05, q50 ve q95 tahminleri; firmanın kendi grubuna ait konformal artıkla genişletilir."
    ),
}

NOTE_STRINGS: dict[str, str] = {
    "Deterministic: identical inputs give identical scores.": (
        "Belirlenimci: aynı girdiler aynı puanları verir."
    ),
    "A signal without inputs is reported as unavailable and carries no weight.": (
        "Girdisi olmayan bir sinyal kullanılamaz olarak bildirilir ve hiç ağırlık taşımaz."
    ),
    "The interval widens as data quality falls rather than narrowing on assumptions.": (
        "Aralık, varsayımlarla daralmak yerine veri kalitesi düştükçe genişler."
    ),
    "The trained model has not been delivered yet, so the rule engine remains in service.": (
        "Eğitilmiş model henüz teslim edilmedi, bu nedenle kural motoru kullanımda kalır."
    ),
    "Switching to it changes no part of the interface: the result carries the same fields, and "
    "each one still names the evidence behind it.": (
        "Ona geçmek arayüzün hiçbir yanını değiştirmez: sonuç aynı alanları taşır ve her biri "
        "arkasındaki kanıtı adlandırmaya devam eder."
    ),
}


def text(key: str, lang: str) -> str:
    entry = TEXT[key]
    return entry.get(lang, entry["en"])


def string_list(key: str, lang: str) -> list[str]:
    entry = LISTS[key]
    return entry.get(lang, entry["en"])


def principles(lang: str) -> list[tuple[str, str]]:
    return PRINCIPLES.get(lang, PRINCIPLES["en"])


def signal_summary(code: str, fallback: str, lang: str) -> str:
    return SIGNAL_SUMMARIES.get(code, {}).get(lang, fallback)


def signal_inputs(inputs: list[str], lang: str) -> list[str]:
    if lang == "en":
        return inputs
    return [SIGNAL_INPUTS.get(item, item) for item in inputs]


def engine_string(value: str, lang: str) -> str:
    """Engine prose, looked up by its English text."""
    if lang == "en":
        return value
    return ENGINE_STRINGS.get(value, value)


def engine_notes(notes: list[str], lang: str) -> list[str]:
    if lang == "en":
        return notes
    return [NOTE_STRINGS.get(note, note) for note in notes]


# --------------------------------------------------------------------------- #
# Composed sentences
#
# The pilot run sequence and the impact chain describe live figures, so each
# one is a template rather than a fixed string. Named placeholders let Turkish
# put the words in its own order.
# --------------------------------------------------------------------------- #

PILOT_STEPS: dict[str, dict[str, dict[str, str]]] = {
    "region": {
        "label": {"en": "Pilot region set", "tr": "Pilot bölgesi belirlendi"},
        "detail": {
            "en": "{region} province, {municipalities} participating municipalities.",
            "tr": "{region} ili, {municipalities} katılımcı belediye.",
        },
    },
    "sector": {
        "label": {"en": "Sector scope set", "tr": "Sektör kapsamı belirlendi"},
        "detail": {
            "en": "Packaging intensive sectors carry the largest declaration gaps.",
            "tr": "Ambalaj yoğun sektörler en büyük beyan farklarını taşır.",
        },
        "scoped": {"en": "Scoped to {sector}.", "tr": "{sector} ile sınırlandırıldı."},
        "all": {"en": "All sectors", "tr": "Tüm sektörler"},
    },
    "load": {
        "label": {"en": "Records loaded", "tr": "Kayıtlar yüklendi"},
        "detail": {
            "en": "{declarations} declaration periods and {lines} customs lines across "
            "{companies} companies.",
            "tr": "{companies} firmada {declarations} beyan dönemi ve {lines} gümrük kalemi.",
        },
        "value": {"en": "{companies} companies", "tr": "{companies} firma"},
    },
    "analyse": {
        "label": {"en": "Analysis run", "tr": "Analiz çalıştırıldı"},
        "detail": {
            "en": "Eight signals evaluated per company for {period}.",
            "tr": "{period} için firma başına sekiz sinyal değerlendirildi.",
        },
    },
    "shortlist": {
        "label": {"en": "Shortlist produced", "tr": "Kısa liste oluşturuldu"},
        "detail": {
            "en": "{critical} critical and {high} high priority in the top {size}.",
            "tr": "İlk {size} kayıtta {critical} kritik ve {high} yüksek öncelik.",
        },
        "value": {"en": "Top {size}", "tr": "İlk {size}"},
    },
    "reasons": {
        "label": {"en": "Reasons attached", "tr": "Gerekçeler eklendi"},
        "detail": {
            "en": "{count} signal evaluations could not be run and are marked unavailable "
            "rather than clear.",
            "tr": "{count} sinyal değerlendirmesi çalıştırılamadı ve temiz yerine "
            "kullanılamaz olarak işaretlendi.",
        },
        "value": {
            "en": "{quality}% mean data quality",
            "tr": "ortalama %{quality} veri kalitesi",
        },
    },
    "outcomes": {
        "label": {"en": "Outcomes applied", "tr": "Sonuçlar uygulandı"},
        "detail": {
            "en": "Closed inspections in the system have confirmed {ratio}% of the tonnage "
            "they were sent to check.",
            "tr": "Sistemdeki kapanmış denetimler, kontrol için gönderildikleri tonajın "
            "%{ratio} kadarını doğruladı.",
        },
        "off": {
            "en": "Outcome projection switched off for this run.",
            "tr": "Bu çalıştırma için sonuç öngörüsü kapatıldı.",
        },
        "value": {"en": "{ratio}% confirmed", "tr": "%{ratio} doğrulandı"},
        "valueOff": {"en": "off", "tr": "kapalı"},
    },
    "impact": {
        "label": {"en": "Impact calculated", "tr": "Etki hesaplandı"},
        "detail": {
            "en": "{tonnes} t into formal recovery, {co2e} t CO2e avoided.",
            "tr": "{tonnes} t kayıtlı geri kazanıma, {co2e} t CO2e önlendi.",
        },
        "value": {"en": "{value}M TL at stake", "tr": "{value}M TL risk altında"},
    },
    "publish": {
        "label": {"en": "Published to impact dashboard", "tr": "Etki panosuna yayımlandı"},
        "detail": {
            "en": "{share}% of recovered contribution is earmarked for collector "
            "formalisation.",
            "tr": "Tahsil edilen katkı payının %{share} kadarı toplayıcıların kayıt altına "
            "alınmasına ayrılır.",
        },
        "value": {"en": "Live", "tr": "Yayında"},
    },
}

CHAIN_STEPS: dict[str, dict[str, dict[str, str]]] = {
    "analysed": {
        "label": {"en": "Companies analysed", "tr": "Analiz edilen firma"},
        "note": {"en": "Period {period}", "tr": "{period} dönemi"},
    },
    "flagged": {
        "label": {"en": "Raised for inspection", "tr": "Denetime çıkarılan"},
        "note": {
            "en": "High and critical priority with an unexplained amount",
            "tr": "Açıklanamayan miktarı olan yüksek ve kritik öncelikliler",
        },
    },
    "identified": {
        "label": {"en": "Tonnage identified", "tr": "Tespit edilen tonaj"},
        "note": {
            "en": "Below the expected range, before inspection",
            "tr": "Beklenen aralığın altında, denetimden önce",
        },
    },
    "confirmed": {
        "label": {"en": "Tonnage confirmed", "tr": "Doğrulanan tonaj"},
        "note": {
            "en": "Established by {count} completed inspections",
            "tr": "Tamamlanan {count} denetimle tespit edildi",
        },
    },
    "recovery": {
        "label": {"en": "Entering formal recovery", "tr": "Kayıtlı geri kazanıma giren"},
        "note": {
            "en": "{share}% of confirmed tonnage",
            "tr": "doğrulanan tonajın %{share} kadarı",
        },
    },
    "co2e": {
        "label": {"en": "Emissions avoided", "tr": "Önlenen emisyon"},
        "note": {
            "en": "Against disposal of the same material",
            "tr": "Aynı malzemenin bertarafına kıyasla",
        },
    },
}


PILOT_NAME = {
    "en": {
        "default": "COP31 Antalya Packaging Transparency Pilot",
        "other": "{region} packaging transparency pilot",
    },
    "tr": {
        "default": "COP31 Antalya Ambalaj Şeffaflık Pilotu",
        "other": "{region} ambalaj şeffaflık pilotu",
    },
}


def pilot_name(lang: str, region: str, default_region: str) -> str:
    words = PILOT_NAME.get(lang, PILOT_NAME["en"])
    if region == default_region:
        return words["default"]
    return words["other"].format(region=region)


def phrase(table: dict, key: str, part: str, lang: str, **params) -> str:
    """One template from a table above, filled in."""
    entry = table[key][part]
    return entry.get(lang, entry["en"]).format(**params)
