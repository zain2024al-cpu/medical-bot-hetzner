# modules/healthcare/medical_followup/constants.py
# Static data for the medical follow-up flow.
# flow.py / views.py import from here — never define lists/maps inline.

from shared.multiselect import Option

# ── Step 4: نوع الإجراء — 6 options, no "أخرى" ───────────────────────────────
# IDs are stable — never change them (existing DB records store procedure_type_ids).

PROCEDURE_TYPE_OPTIONS: list[Option] = [
    Option(id="exam_med",      label="معاينة وصرف دواء",                                 icon="💊"),
    Option(id="nursing_iv",    label="إجراءات تمريضية (تركيب فراشة - ضرب إبر)",         icon="💉"),
    Option(id="nursing_cath",  label="إجراءات تمريضية (تغيير قسطرة بولية)",              icon="🏥"),
    Option(id="field_post_dc", label="متابعة ميدانية بعد خروج من المستشفى",              icon="🏠"),
    Option(id="field_routine", label="متابعة ميدانية دورية",                             icon="📅"),
    Option(id="emergency",     label="حالة طارئة",                                       icon="🚨"),
]

# ── Step 5: الشكوى الرئيسية / الأعراض — 30 + أخرى = 31 ─────────────────────
# IDs are stable — never change them (existing DB records store complaint_ids).

COMPLAINT_OPTIONS: list[Option] = [
    Option(id="visit_routine",    label="زيارة متابعة دورية (لا توجد شكوى جديدة)",    icon="📅"),
    Option(id="visit_post_op",    label="زيارة متابعة بعد العملية (لا توجد شكوى)",     icon="🏥"),
    Option(id="pain_surgical",    label="ألم في مكان العملية",                          icon="🩹"),
    Option(id="fever_chills",     label="حمى وقشعريرة",                                icon="🌡️"),
    Option(id="headache",         label="صداع وألم في الرأس",                           icon="🤕"),
    Option(id="dizziness",        label="دوخة ودوار",                                  icon="😵"),
    Option(id="sore_throat",      label="ألم والتهاب في الحلق",                        icon="🤒"),
    Option(id="dry_cough",        label="سعال جاف",                                    icon="🫁"),
    Option(id="wet_cough",        label="سعال مع بلغم",                                icon="😷"),
    Option(id="nasal",            label="انسداد أو سيلان الأنف",                       icon="👃"),
    Option(id="abdominal_pain",   label="ألم وتقلصات في البطن",                        icon="🤕"),
    Option(id="diarrhea",         label="إسهال",                                       icon="💩"),
    Option(id="nausea",           label="غثيان وفقدان للشهية",                         icon="🤢"),
    Option(id="vomiting",         label="قيء (طَرْش)",                                 icon="🤮"),
    Option(id="bloating",         label="انتفاخ وغازات وقرقرة بالبطن",                 icon="🫧"),
    Option(id="constipation",     label="إمساك",                                       icon="🚽"),
    Option(id="gastric_pain",     label="ألم وحرقة في المعدة",                         icon="🔥"),
    Option(id="mouth_ulcers",     label="تقرحات مؤلمة في الفم",                        icon="👄"),
    Option(id="anal_worms",       label="ديدان في فتحة الشرج",                         icon="🦠"),
    Option(id="dysuria",          label="حرقة أثناء التبول",                           icon="🔥"),
    Option(id="flank_pain",       label="ألم في جانب البطن",                           icon="🫀"),
    Option(id="urinary_freq",     label="تقطع البول",                                  icon="💧"),
    Option(id="catheter_change",  label="يحتاج تغيير القسطرة البولية",                 icon="🏥"),
    Option(id="iv_fluids",        label="يحتاج سوائل لدعم التغذية (IV fluids)",        icon="💧"),
    Option(id="iv_antibiotic",    label="يحتاج ضرب جرعة المضاد الحيوي IV",            icon="💉"),
    Option(id="iv_gcsf",          label="يحتاج ضرب حقنة الـ G-CSF",                   icon="💉"),
    Option(id="skin_rash",        label="احمرار أو طفح جلدي مع حكة",                  icon="🔴"),
    Option(id="anxiety_insomnia", label="قلق وعدم القدرة على النوم",                   icon="😰"),
    Option(id="back_pain",        label="ألم في الظهر",                                icon="🦴"),
    Option(id="joint_pain",       label="ألم في المفاصل",                              icon="🦴"),
    Option(id="cmp_other",        label="أخرى",                                        icon="📝"),
]

# ── Step 7: الأدوية والمستلزمات — 65 options (official form) ─────────────────
# IDs are stable — never change them (existing DB records store meds_supply_ids).

MEDS_SUPPLY_OPTIONS: list[Option] = [
    # ── 💉 IV Fluids & Injections ─────────────────────────────────────────────
    Option(id="iv_pcm_inf",    label="Paracetamol 1g infusion",                                  icon="💉"),
    Option(id="iv_dns_inf",    label="DNS infusion 500ml",                                       icon="💉"),
    Option(id="iv_ns_inf",     label="N/S infusion 100/500ml",                                   icon="💉"),
    Option(id="iv_rl_inf",     label="RL infusion 500ml",                                        icon="💉"),
    Option(id="iv_panto_inj",  label="Pantoprazole 40mg INJ.",                                   icon="💉"),
    Option(id="iv_rani_inj",   label="Ranitidine 50mg INJ.",                                     icon="💉"),
    Option(id="iv_hyos_inj",   label="Hyoscine 20mg INJ.",                                       icon="💉"),
    Option(id="iv_vitc_inj",   label="Vitamin C 500mg INJ.",                                     icon="💉"),
    Option(id="iv_vitb_inj",   label="Vitamin B Complex INJ.",                                   icon="💉"),
    Option(id="iv_diclo_inj",  label="Diclofenac 75mg INJ.",                                     icon="💉"),
    Option(id="iv_ceft_inj",   label="Ceftriaxone 1g INJ.",                                      icon="💉"),
    Option(id="iv_emes_inj",   label="Emeset 8mg INJ.",                                          icon="💉"),
    Option(id="iv_meto_inj",   label="Metoclopramide 10mg INJ.",                                 icon="💉"),
    Option(id="iv_tram_inj",   label="Tramadol 100ml INJ.",                                      icon="💉"),
    Option(id="iv_dexa_inj",   label="Dexamethasone 4mg INJ.",                                   icon="💉"),
    Option(id="iv_neuro_inj",  label="Neurobion injection",                                      icon="💉"),
    Option(id="iv_metro_inf",  label="Metronidazole infusion",                                   icon="💉"),
    # ── 💊 Oral Analgesics & Anti-inflammatory ────────────────────────────────
    Option(id="oral_dolo",     label="Dolo tab 1-1-1 for 3 days then SOS",                      icon="💊"),
    Option(id="oral_ultr",     label="Ultracet tab 1-0-1 for 3 days then SOS",                  icon="💊"),
    Option(id="oral_diclo",    label="Diclofenac tab 1-0-1 for 3 days then SOS",                icon="💊"),
    Option(id="oral_flex",     label="Flexon MR tab 1-0-1 for 3 days then SOS",                 icon="💊"),
    # ── 🫁 Respiratory ─────────────────────────────────────────────────────────
    Option(id="resp_chest",    label="Cheston Cold Total tab 1-0-1 for 5 days",                 icon="🫁"),
    Option(id="resp_dry_syp",  label="Dry Cough syrup 10ml-0-10ml",                             icon="🫁"),
    Option(id="resp_exp_syp",  label="Cough Expectorant syrup 10ml-0-10ml",                     icon="🫁"),
    Option(id="resp_mont",     label="Montelukast tab 0-0-1 for 10 days",                       icon="🫁"),
    Option(id="resp_lcet",     label="Levocetirizine 5mg tab 0-0-1 for 10 days",               icon="🫁"),
    # ── 💊 Antibiotics ─────────────────────────────────────────────────────────
    Option(id="ab_augm",       label="Augmentin 625mg tab 1-1-1 for 5 days",                    icon="💊"),
    Option(id="ab_azith",      label="Azithromycin tab 0-0-1 for 5 days",                       icon="💊"),
    Option(id="ab_levof",      label="Levofloxacin 750mg tab 1-0-0 for 5 days",                 icon="💊"),
    Option(id="ab_cotri",      label="Co-trimoxazole 480mg tab 1-0-1 for 5 days",               icon="💊"),
    Option(id="ab_niftas",     label="Niftas 100mg tab 1-0-1 for 7 days",                       icon="💊"),
    Option(id="ab_metro",      label="Metronidazole 400mg tab 1-1-1 for 5 days",                icon="💊"),
    # ── 💊 GI & Antiemetics ────────────────────────────────────────────────────
    Option(id="gi_pantoD_10",  label="Pantosec D SR tab 1-0-1 (30 min B/F) for 10 days",       icon="💊"),
    Option(id="gi_pantoD_1m",  label="Pantosec D SR tab 1-0-1 (30 min B/F) for 1 month",       icon="💊"),
    Option(id="gi_panto40",    label="Pantoprazole 40mg tab 1-0-0 (30 min. B/F) 10 days",      icon="💊"),
    Option(id="gi_emes4",      label="Emeset 4mg tab 1-0-1 (30 min B/F) for 5 days",           icon="💊"),
    Option(id="gi_dompe",      label="Domperidone 10mg tab 1-0-1 (30 min B/F) for 5 days",     icon="💊"),
    Option(id="gi_hyos_tab",   label="Hyoscine tab 1-0-1 for 5 days",                          icon="💊"),
    Option(id="gi_mucaine",    label="Mucaine syrup 10ml-10ml-10ml (30 min B/F) for 2 weeks",  icon="💊"),
    Option(id="gi_colospa",    label="Colospa 135mg tab 0-0-2 for 2 months",                   icon="💊"),
    Option(id="gi_cizasp",     label="Cizaspa-X tab 0-0-1 for 1 month",                        icon="💊"),
    Option(id="gi_bisth",      label="Bisthera 120mg tab 1-1-1-1 for 14 days",                 icon="💊"),
    Option(id="gi_esog",       label="Esogress D tab 1-0-1 (B/F) for 3 months",               icon="💊"),
    Option(id="gi_somp_hp",    label="Sompraz HP kit tab 3-0-3 for 14 days",                   icon="💊"),
    # ── 🪱 Antiparasitic / Laxatives ────────────────────────────────────────────
    Option(id="ap_alben",      label="Albendazole 400mg tab (1 today + 1 after 2 weeks)",       icon="🪱"),
    Option(id="ap_dulco",      label="Dulcoflex (Bisacodyl) 5mg tab 0-0-1 for 5 days then SOS",icon="🪱"),
    Option(id="ap_duphal",     label="Duphalac syrup 0-0-20ml for 3 days then SOS",             icon="🪱"),
    # ── 💊 Urology ─────────────────────────────────────────────────────────────
    Option(id="uro_tams",      label="Tamsulosin tab 0-0-1 for 10 days",                        icon="💊"),
    Option(id="uro_urisp",     label="Urispas 200mg tab 1-1-1 for 5 days",                      icon="💊"),
    Option(id="uro_cyst",      label="Cystone tab 1-0-1 for 1 month",                           icon="💊"),
    Option(id="uro_urik",      label="Urikind KM sachet 1-0-1 for 5 days",                      icon="💊"),
    # ── 🍊 Supplements ─────────────────────────────────────────────────────────
    Option(id="supl_vitc",     label="Vitamin C tab 1-0-1 for 5 days",                         icon="🍊"),
    Option(id="supl_multiv",   label="Multivitamin tab 0-1-0 for 1 month",                     icon="🍊"),
    Option(id="supl_appet",    label="Appetite syrup 10ml-0-10ml (30 min B/F)",                icon="🍊"),
    Option(id="supl_plac",     label="Placida 0.5/10mg tab 0-0-1 for one month",              icon="🍊"),
    # ── 🧴 Topical ─────────────────────────────────────────────────────────────
    Option(id="top_mupi",      label="Mupirocin ointment 1-0-1",                               icon="🧴"),
    Option(id="top_wan",       label="Wanita cream 1-0-1",                                     icon="🧴"),
    Option(id="top_mug",       label="Mouth ulcer gel 1-1-1",                                  icon="🧴"),
    # ── 🏥 Medical supplies ────────────────────────────────────────────────────
    Option(id="msup_cann",     label="IV cannula and cannula fixator",                          icon="🏥"),
    Option(id="msup_ivset",    label="IV set",                                                  icon="🏥"),
    Option(id="msup_syr",      label="Syringe and Alcohol swab",                               icon="🏥"),
    Option(id="msup_cath",     label="Urinary catheter",                                       icon="🏥"),
    Option(id="msup_ubag",     label="Urine bag",                                              icon="🏥"),
    Option(id="msup_none",     label="المريض لا يحتاج إعطاء أي دواء",                         icon="✅"),
    Option(id="ms_other",      label="Other (Specify)",                                        icon="📝"),
]

# ── Step 10: اسم الصحي — shared staff registry ───────────────────────────────

from modules.healthcare.staff import HC_SP_MAP as SP_MAP, HC_STAFF_LIST as STAFF_LIST

# ── "أخرى" guard IDs ─────────────────────────────────────────────────────────

DEPT_OTHER_ID         = "dept_other"
COMPLAINT_OTHER_ID    = "cmp_other"
MEDS_SUPPLY_OTHER_ID  = "ms_other"
