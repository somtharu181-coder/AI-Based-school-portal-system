"""
Quiz Services
=============
AI question generation based on Nepal CDC Curriculum Specification Grid.
- Subject-wise chapters per class per Nepali month
- Uses Gemini/OpenAI if API key set in settings; clean fallback per subject
"""
import json
import random
import re
from datetime import datetime
from django.utils import timezone
from .models import QuizSession, Question


# ══════════════════════════════════════════════════════════════════
# NEPAL CDC SPECIFICATION GRID
# Class → Subject → Nepali Month → Chapters covered
# Months: Baishakh=1 … Chaitra=12
# Subjects normalised to lowercase for matching
# ══════════════════════════════════════════════════════════════════

SPEC_GRID = {
    # ── CLASS 1 ──────────────────────────────────────────────────
    "1": {
        "mathematics": {
            1:["Numbers 1-10","Counting"],
            2:["Numbers 11-20","Addition basics"],
            3:["Subtraction basics"],
            4:["Shapes","Patterns"],
            5:["Numbers 21-50"],
            6:["Addition with 2 digits"],
            7:["Subtraction with 2 digits"],
            8:["Measurement: length","Weight"],
            9:["Time: Days and Months"],
            10:["Revision 1-50"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "english": {
            1:["Alphabet A-M","Vowels"],
            2:["Alphabet N-Z","Consonants"],
            3:["Simple words","Animals"],
            4:["Numbers in English","Colours"],
            5:["Body parts","Family"],
            6:["Simple sentences"],
            7:["Greetings","Questions"],
            8:["Fruits and vegetables"],
            9:["Action words (verbs)"],
            10:["Revision: vocabulary"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "nepali": {
            1:["Ka Kha Ga","Vowels"],
            2:["Consonants continued"],
            3:["Simple words"],
            4:["Short sentences"],
            5:["Body parts in Nepali"],
            6:["Family members"],
            7:["Animals","Plants"],
            8:["Reading short stories"],
            9:["Writing practice"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 2 ──────────────────────────────────────────────────
    "2": {
        "mathematics": {
            1:["Numbers up to 100","Place value"],
            2:["Addition up to 100"],
            3:["Subtraction up to 100"],
            4:["Multiplication tables 1-5"],
            5:["Multiplication tables 6-10"],
            6:["Division basics"],
            7:["Fractions: half, quarter"],
            8:["Shapes","Measurement"],
            9:["Time","Money"],
            10:["Revision 1-7"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "english": {
            1:["Nouns","Articles"],
            2:["Pronouns","Simple sentences"],
            3:["Verbs: is, am, are"],
            4:["Adjectives","Colours"],
            5:["Prepositions"],
            6:["Questions: What, Where"],
            7:["Reading comprehension"],
            8:["Writing: My family"],
            9:["Dictation","Spelling"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 3 ──────────────────────────────────────────────────
    "3": {
        "mathematics": {
            1:["Numbers up to 1000","Place value"],
            2:["Addition with carrying"],
            3:["Subtraction with borrowing"],
            4:["Multiplication 2-digit"],
            5:["Division 2-digit"],
            6:["Fractions"],
            7:["Geometry: shapes"],
            8:["Measurement: length, weight, capacity"],
            9:["Time","Calendar"],
            10:["Money"],
            11:["Revision"],
            12:["Final Review"],
        },
        "english": {
            1:["Parts of speech: Noun, Pronoun"],
            2:["Verb forms: Simple present"],
            3:["Adjectives","Adverbs"],
            4:["Simple past tense"],
            5:["Prepositions","Conjunctions"],
            6:["Reading: short stories"],
            7:["Writing: paragraphs"],
            8:["Punctuation"],
            9:["Comprehension"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "science": {
            1:["Living and non-living things"],
            2:["Plants: parts and uses"],
            3:["Animals: domestic and wild"],
            4:["Our body"],
            5:["Food and nutrition"],
            6:["Water","Air"],
            7:["Weather","Seasons"],
            8:["Earth and sky"],
            9:["Simple machines"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 4 ──────────────────────────────────────────────────
    "4": {
        "mathematics": {
            1:["Numbers up to 10000","Place value"],
            2:["Addition and Subtraction"],
            3:["Multiplication"],
            4:["Division"],
            5:["Fractions","Decimals basics"],
            6:["Geometry: shapes, angles"],
            7:["Measurement"],
            8:["Area and Perimeter"],
            9:["Time and Calendar"],
            10:["Data and graphs"],
            11:["Revision"],
            12:["Final Review"],
        },
        "english": {
            1:["Nouns: common, proper, collective"],
            2:["Pronouns","Verbs"],
            3:["Tenses: Present, Past, Future"],
            4:["Adjectives","Degrees of comparison"],
            5:["Prepositions","Conjunctions"],
            6:["Reading comprehension"],
            7:["Composition","Letter writing"],
            8:["Punctuation","Grammar"],
            9:["Vocabulary","Synonyms"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "science": {
            1:["Matter and materials"],
            2:["Plants: photosynthesis"],
            3:["Animals: classification"],
            4:["Human body systems"],
            5:["Food chains"],
            6:["Water cycle"],
            7:["Air and weather"],
            8:["Light and shadow"],
            9:["Simple machines","Force"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "social studies": {
            1:["Our community"],
            2:["Nepal: geography basics"],
            3:["Natural resources"],
            4:["Festivals of Nepal"],
            5:["Transport and communication"],
            6:["Government and democracy"],
            7:["History: ancient Nepal"],
            8:["Maps and directions"],
            9:["Citizenship"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 5 ──────────────────────────────────────────────────
    "5": {
        "mathematics": {
            1:["Sets","Natural numbers"],
            2:["Operations on whole numbers"],
            3:["LCM and HCF"],
            4:["Fractions","Decimals"],
            5:["Percentage","Ratio and Proportion"],
            6:["Unitary method"],
            7:["Geometry: angles, triangles"],
            8:["Area and Volume"],
            9:["Statistics: tables, graphs"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "english": {
            1:["Grammar: parts of speech"],
            2:["Tenses: all forms"],
            3:["Active and passive voice"],
            4:["Direct and indirect speech"],
            5:["Reading comprehension"],
            6:["Composition: essay, letter"],
            7:["Vocabulary: synonyms, antonyms"],
            8:["Idioms and phrases"],
            9:["Comprehension and grammar"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "science": {
            1:["Matter: states and properties"],
            2:["Mixtures and solutions"],
            3:["Living things: cell basics"],
            4:["Plants: reproduction"],
            5:["Human body: organ systems"],
            6:["Energy: forms and sources"],
            7:["Light","Sound"],
            8:["Electricity basics"],
            9:["Environment","Pollution"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "social studies": {
            1:["Nepal: physical features"],
            2:["Climate and vegetation"],
            3:["Population and society"],
            4:["Economic activities"],
            5:["History of Nepal"],
            6:["Cultural heritage"],
            7:["Government structure"],
            8:["Maps and globe"],
            9:["SAARC and UN"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 6 ──────────────────────────────────────────────────
    "6": {
        "mathematics": {
            1:["Natural numbers, integers"],
            2:["Factors and multiples"],
            3:["Fractions and decimals"],
            4:["Ratio and proportion"],
            5:["Percentage","Profit and loss"],
            6:["Algebra: expressions"],
            7:["Geometry: lines and angles"],
            8:["Triangles","Quadrilaterals"],
            9:["Mensuration: area, perimeter"],
            10:["Statistics"],
            11:["Revision"],
            12:["Final Review"],
        },
        "science": {
            1:["Matter and changes"],
            2:["Elements, compounds, mixtures"],
            3:["Cell: structure and function"],
            4:["Plant kingdom"],
            5:["Animal kingdom"],
            6:["Human digestive system"],
            7:["Force and motion"],
            8:["Energy: types"],
            9:["Earth: structure"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "english": {
            1:["Tenses: review and advanced"],
            2:["Modals","Conditionals"],
            3:["Reported speech"],
            4:["Reading: prose and poetry"],
            5:["Essay writing"],
            6:["Letter and email writing"],
            7:["Vocabulary development"],
            8:["Comprehension skills"],
            9:["Grammar: revision"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 7 ──────────────────────────────────────────────────
    "7": {
        "mathematics": {
            1:["Integers: operations"],
            2:["Fractions: operations"],
            3:["Decimals and percentages"],
            4:["Ratio, proportion, unitary method"],
            5:["Algebra: linear expressions"],
            6:["Simple equations"],
            7:["Geometry: congruence"],
            8:["Mensuration"],
            9:["Statistics: mean, median, mode"],
            10:["Probability introduction"],
            11:["Revision"],
            12:["Final Review"],
        },
        "science": {
            1:["Nutrition in plants and animals"],
            2:["Fibre to fabric"],
            3:["Heat and temperature"],
            4:["Acids, bases, salts"],
            5:["Physical and chemical changes"],
            6:["Weather, climate, adaptation"],
            7:["Winds, storms, cyclones"],
            8:["Motion and time"],
            9:["Electric current and circuits"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 8 ──────────────────────────────────────────────────
    "8": {
        "mathematics": {
            1:["Rational numbers","Exponents"],
            2:["Algebraic expressions","Identities"],
            3:["Linear equations","Inequalities"],
            4:["Quadrilaterals","Practical geometry"],
            5:["Mensuration: area, volume"],
            6:["Statistics: bar graphs, pie charts"],
            7:["Probability"],
            8:["Square roots and cube roots"],
            9:["Comparing quantities","Percentage"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "science": {
            1:["Crop production","Microorganisms"],
            2:["Conservation of flora and fauna"],
            3:["Cell: structure, division"],
            4:["Reproduction in plants and animals"],
            5:["Reaching the age of adolescence"],
            6:["Force: pressure, friction"],
            7:["Sound"],
            8:["Chemical effects of current"],
            9:["Light","Stars and solar system"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "english": {
            1:["Reading comprehension: passages"],
            2:["Grammar: tenses, voice"],
            3:["Reported speech","Conditionals"],
            4:["Essay and paragraph writing"],
            5:["Letter, email, notice writing"],
            6:["Poetry analysis"],
            7:["Vocabulary: idioms, phrases"],
            8:["Short stories: themes"],
            9:["Grammar revision"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "social studies": {
            1:["Nepal: historical development"],
            2:["Political system of Nepal"],
            3:["Economic development"],
            4:["Natural resources management"],
            5:["Social diversity and inclusion"],
            6:["Human rights"],
            7:["Global organizations"],
            8:["Disaster management"],
            9:["Environmental issues"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 9 ──────────────────────────────────────────────────
    "9": {
        "mathematics": {
            1:["Sets","Real numbers"],
            2:["Algebra: polynomials"],
            3:["Linear equations in two variables"],
            4:["Quadratic equations"],
            5:["Geometry: triangles, circles"],
            6:["Trigonometry: basics"],
            7:["Statistics: frequency distribution"],
            8:["Probability"],
            9:["Coordinate geometry"],
            10:["Mensuration: surface area, volume"],
            11:["Revision"],
            12:["Final Review"],
        },
        "science": {
            1:["Matter: atoms and molecules"],
            2:["Structure of atom"],
            3:["Motion: laws of Newton"],
            4:["Force and laws of motion"],
            5:["Gravitation"],
            6:["Work, energy, power"],
            7:["Sound"],
            8:["Natural resources","Improvement in food resources"],
            9:["Tissues","Diversity in living organisms"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
        "english": {
            1:["Reading: prose extracts"],
            2:["Grammar: advanced tenses"],
            3:["Modals","Conditionals"],
            4:["Reading poetry"],
            5:["Essay writing"],
            6:["Report and article writing"],
            7:["Comprehension"],
            8:["Drama and plays"],
            9:["Vocabulary"],
            10:["Revision"],
            11:["Full Revision"],
            12:["Final Review"],
        },
    },
    # ── CLASS 10 ─────────────────────────────────────────────────
    "10": {
        "mathematics": {
            1:["Algebra: quadratics, sequences"],
            2:["Polynomials","Remainder theorem"],
            3:["Coordinate geometry"],
            4:["Circles: theorems"],
            5:["Trigonometry: identities"],
            6:["Heights and distances"],
            7:["Statistics: mean, median, mode from grouped data"],
            8:["Probability"],
            9:["Mensuration: revision"],
            10:["Full syllabus revision"],
            11:["SEE Preparation"],
            12:["Final SEE Revision"],
        },
        "science": {
            1:["Chemical reactions"],
            2:["Acids, bases, salts"],
            3:["Metals and non-metals"],
            4:["Carbon compounds"],
            5:["Life processes"],
            6:["Control and coordination"],
            7:["Electricity and magnetism"],
            8:["Light: refraction, lenses"],
            9:["Heredity and evolution"],
            10:["Full syllabus revision"],
            11:["SEE Preparation"],
            12:["Final SEE Revision"],
        },
        "english": {
            1:["Prose: stories and essays"],
            2:["Grammar: advanced"],
            3:["Poetry analysis"],
            4:["Drama"],
            5:["Formal and informal writing"],
            6:["Report writing","Summary"],
            7:["Comprehension: complex passages"],
            8:["Vocabulary: advanced"],
            9:["Grammar: full revision"],
            10:["Full revision"],
            11:["SEE Preparation"],
            12:["Final SEE Revision"],
        },
    },
}

# Subject name aliases for matching
SUBJECT_ALIASES = {
    "maths": "mathematics",
    "math": "mathematics",
    "गणित": "mathematics",
    "eng": "english",
    "अंग्रेजी": "english",
    "sci": "science",
    "विज्ञान": "science",
    "sst": "social studies",
    "social": "social studies",
    "सामाजिक": "social studies",
    "nepali": "nepali",
    "नेपाली": "nepali",
    "computer": "computer",
    "health": "health",
    "hpe": "health",
}

# Subject-specific fallback questions
FALLBACK_POOL = {
    "mathematics": [
        {"text":"What is 15 × 8?","option_a":"110","option_b":"120","option_c":"115","option_d":"125","correct":"B"},
        {"text":"LCM of 6 and 8 is?","option_a":"14","option_b":"24","option_c":"48","option_d":"16","correct":"B"},
        {"text":"What is 25% of 400?","option_a":"75","option_b":"80","option_c":"100","option_d":"125","correct":"C"},
        {"text":"√196 = ?","option_a":"12","option_b":"13","option_c":"14","option_d":"16","correct":"C"},
        {"text":"3³ = ?","option_a":"9","option_b":"18","option_c":"27","option_d":"81","correct":"C"},
        {"text":"Area of rectangle 8×5?","option_a":"26","option_b":"40","option_c":"13","option_d":"80","correct":"B"},
        {"text":"HCF of 24 and 36?","option_a":"4","option_b":"6","option_c":"12","option_d":"18","correct":"C"},
        {"text":"0.75 as fraction?","option_a":"3/4","option_b":"7/5","option_c":"7/10","option_d":"3/5","correct":"A"},
        {"text":"2/3 of 90 = ?","option_a":"30","option_b":"45","option_c":"60","option_d":"75","correct":"C"},
        {"text":"Which is prime?","option_a":"21","option_b":"27","option_c":"29","option_d":"33","correct":"C"},
    ],
    "english": [
        {"text":"Which is a noun?","option_a":"run","option_b":"quickly","option_c":"mountain","option_d":"beautiful","correct":"C"},
        {"text":"Correct sentence?","option_a":"She go to school","option_b":"She goes to school","option_c":"She going school","option_d":"She goed school","correct":"B"},
        {"text":"Opposite of 'ancient'?","option_a":"old","option_b":"modern","option_c":"historic","option_d":"antique","correct":"B"},
        {"text":"Plural of 'child'?","option_a":"childs","option_b":"childes","option_c":"children","option_d":"childrens","correct":"C"},
        {"text":"'The dog ran __ the road.' Which preposition?","option_a":"in","option_b":"at","option_c":"on","option_d":"across","correct":"D"},
        {"text":"Synonym of 'happy'?","option_a":"sad","option_b":"angry","option_c":"joyful","option_d":"tired","correct":"C"},
        {"text":"Past tense of 'write'?","option_a":"writed","option_b":"written","option_c":"wrote","option_d":"writ","correct":"C"},
        {"text":"Which is a verb?","option_a":"beauty","option_b":"quickly","option_c":"sing","option_d":"tall","correct":"C"},
        {"text":"Article before 'elephant'?","option_a":"a","option_b":"an","option_c":"the","option_d":"no article","correct":"B"},
        {"text":"Antonym of 'victory'?","option_a":"win","option_b":"success","option_c":"defeat","option_d":"triumph","correct":"C"},
    ],
    "science": [
        {"text":"Photosynthesis occurs in which part of plant?","option_a":"Root","option_b":"Stem","option_c":"Leaf","option_d":"Flower","correct":"C"},
        {"text":"Which gas do plants absorb during photosynthesis?","option_a":"Oxygen","option_b":"Nitrogen","option_c":"Carbon dioxide","option_d":"Hydrogen","correct":"C"},
        {"text":"Largest planet in solar system?","option_a":"Earth","option_b":"Saturn","option_c":"Jupiter","option_d":"Uranus","correct":"C"},
        {"text":"Chemical formula of water?","option_a":"HO","option_b":"H2O","option_c":"H2O2","option_d":"OH","correct":"B"},
        {"text":"Force = ?","option_a":"Mass + Acceleration","option_b":"Mass × Velocity","option_c":"Mass × Acceleration","option_d":"Mass / Acceleration","correct":"C"},
        {"text":"Unit of electric current?","option_a":"Volt","option_b":"Watt","option_c":"Ohm","option_d":"Ampere","correct":"D"},
        {"text":"Which organ pumps blood?","option_a":"Liver","option_b":"Lungs","option_c":"Heart","option_d":"Kidney","correct":"C"},
        {"text":"State of water at 100°C?","option_a":"Solid","option_b":"Liquid","option_c":"Gas","option_d":"Plasma","correct":"C"},
        {"text":"Speed of light (approx)?","option_a":"3×10⁶ m/s","option_b":"3×10⁸ m/s","option_c":"3×10⁴ m/s","option_d":"3×10¹⁰ m/s","correct":"B"},
        {"text":"Smallest unit of life?","option_a":"Atom","option_b":"Tissue","option_c":"Cell","option_d":"Organ","correct":"C"},
    ],
    "social studies": [
        {"text":"Capital city of Nepal?","option_a":"Pokhara","option_b":"Biratnagar","option_c":"Kathmandu","option_d":"Lalitpur","correct":"C"},
        {"text":"Highest mountain in the world?","option_a":"K2","option_b":"Kanchenjunga","option_c":"Lhotse","option_d":"Mount Everest","correct":"D"},
        {"text":"Nepal is a __ country?","option_a":"Island","option_b":"Landlocked","option_c":"Coastal","option_d":"Peninsula","correct":"B"},
        {"text":"National flower of Nepal?","option_a":"Rose","option_b":"Lotus","option_c":"Rhododendron","option_d":"Sunflower","correct":"C"},
        {"text":"National animal of Nepal?","option_a":"Tiger","option_b":"Elephant","option_c":"Snow Leopard","option_d":"Cow","correct":"D"},
        {"text":"How many provinces in Nepal?","option_a":"5","option_b":"6","option_c":"7","option_d":"8","correct":"C"},
        {"text":"UN was established in?","option_a":"1939","option_b":"1945","option_c":"1950","option_d":"1955","correct":"B"},
        {"text":"Largest ocean?","option_a":"Atlantic","option_b":"Indian","option_c":"Arctic","option_d":"Pacific","correct":"D"},
        {"text":"SAARC headquarters?","option_a":"Delhi","option_b":"Colombo","option_c":"Dhaka","option_d":"Kathmandu","correct":"D"},
        {"text":"Nepal gained democracy in?","option_a":"1990","option_b":"1950","option_c":"2006","option_d":"1960","correct":"A"},
    ],
    "nepali": [
        {"text":"'सुन्दर' शब्दको विलोम के हो?","option_a":"राम्रो","option_b":"असुन्दर","option_c":"कुरूप","option_d":"सुन्दरता","correct":"C"},
        {"text":"नेपालको राष्ट्रिय भाषा?","option_a":"मैथिली","option_b":"नेपाली","option_c":"तामाङ","option_d":"थारू","correct":"B"},
        {"text":"'घर' शब्दको बहुवचन?","option_a":"घरहरू","option_b":"घरहरु","option_c":"घरौ","option_d":"घरें","correct":"A"},
        {"text":"'पानी' कुन जातको शब्द हो?","option_a":"पुल्लिंग","option_b":"स्त्रीलिंग","option_c":"नपुंसकलिंग","option_d":"उभयलिंग","correct":"A"},
        {"text":"निम्नमध्ये क्रियापद कुन हो?","option_a":"सुन्दर","option_b":"घर","option_c":"दौड्छ","option_d":"राम्रो","correct":"C"},
        {"text":"'आमा' शब्दको विपरीत?","option_a":"बाबा","option_b":"बहिनी","option_c":"छोरी","option_d":"दिदी","correct":"A"},
        {"text":"नेपाली वर्णमालामा स्वरवर्ण कतिवटा?","option_a":"10","option_b":"11","option_c":"12","option_d":"13","correct":"D"},
        {"text":"'पुस्तक' शब्दको अर्थ?","option_a":"कलम","option_b":"किताब","option_c":"कापी","option_d":"थैला","correct":"B"},
        {"text":"'म स्कुल जान्छु' — यो कुन कालको वाक्य हो?","option_a":"भूतकाल","option_b":"वर्तमानकाल","option_c":"भविष्यकाल","option_d":"आज्ञार्थ","correct":"B"},
        {"text":"निम्नमध्ये संज्ञा शब्द कुन हो?","option_a":"राम्रो","option_b":"हिँड्छ","option_c":"नेपाल","option_d":"छिटो","correct":"C"},
    ],
    "computer": [
        {"text":"CPU stands for?","option_a":"Central Processing Unit","option_b":"Computer Processing Unit","option_c":"Central Program Unit","option_d":"Control Processing Unit","correct":"A"},
        {"text":"Which is an input device?","option_a":"Monitor","option_b":"Printer","option_c":"Keyboard","option_d":"Speaker","correct":"C"},
        {"text":"RAM stands for?","option_a":"Read Access Memory","option_b":"Random Access Memory","option_c":"Rapid Access Memory","option_d":"Random Arithmetic Memory","correct":"B"},
        {"text":"1 byte = ? bits","option_a":"4","option_b":"6","option_c":"8","option_d":"16","correct":"C"},
        {"text":"Which is an operating system?","option_a":"MS Word","option_b":"Windows","option_c":"Chrome","option_d":"Photoshop","correct":"B"},
        {"text":"www stands for?","option_a":"World Wide Web","option_b":"World Web Wide","option_c":"Wide World Web","option_d":"Web World Wide","correct":"A"},
        {"text":"Which is a programming language?","option_a":"HTML","option_b":"HTTP","option_c":"FTP","option_d":"SMTP","correct":"A"},
        {"text":"Full form of USB?","option_a":"Universal Serial Bus","option_b":"Unique Serial Bus","option_c":"Universal System Bus","option_d":"Unified Serial Base","correct":"A"},
        {"text":"Which stores data permanently?","option_a":"RAM","option_b":"Cache","option_c":"Hard disk","option_d":"Register","correct":"C"},
        {"text":"Which is an output device?","option_a":"Keyboard","option_b":"Mouse","option_c":"Scanner","option_d":"Monitor","correct":"D"},
    ],
}


def _normalise_subject(subject_name: str) -> str:
    """Normalise subject name to lowercase key used in SPEC_GRID."""
    name = subject_name.strip().lower()
    return SUBJECT_ALIASES.get(name, name)


def _get_class_key(class_name: str) -> str:
    """Extract numeric class key from class name."""
    m = re.search(r'\d+', class_name)
    return m.group() if m else class_name.strip().lower()


def _get_current_nepali_month() -> int:
    """Approximate Nepali month from Gregorian date."""
    month = datetime.now().month
    nepali = ((month - 4) % 12) + 1
    return max(1, min(12, nepali))


def _get_chapters_for_class_subject(class_name: str, subject_name: str) -> list:
    """Return chapters taught so far for a class+subject based on current month."""
    class_key   = _get_class_key(class_name)
    subject_key = _normalise_subject(subject_name)

    class_grid = SPEC_GRID.get(class_key)
    if not class_grid:
        # find nearest class
        available = sorted(SPEC_GRID.keys(), key=lambda x: abs(int(x) - int(class_key or 8)))
        class_grid = SPEC_GRID.get(available[0], {}) if available else {}

    subject_grid = class_grid.get(subject_key)
    if not subject_grid:
        # Try partial match
        for key in class_grid:
            if subject_key in key or key in subject_key:
                subject_grid = class_grid[key]
                break
    if not subject_grid:
        subject_grid = next(iter(class_grid.values()), {})

    month = _get_current_nepali_month()
    chapters = []
    for m in range(1, month + 1):
        chapters.extend(subject_grid.get(m, []))
    return list(dict.fromkeys(chapters)) or [f"{subject_name} Chapter 1", f"{subject_name} Chapter 2"]


def _generate_questions_ai(class_name: str, subject_name: str, chapters: list, count: int = 10) -> list:
    """
    Generate questions using AI (OpenAI/Gemini).
    Falls back to subject-specific question pool if AI unavailable.
    """
    chapter_str = ", ".join(chapters[:8])

    # Try OpenAI
    try:
        import openai
        from django.conf import settings
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("No API key")
        client = openai.OpenAI(api_key=api_key)
        prompt = (
            f"You are a Nepal CDC curriculum expert. Generate exactly {count} multiple choice "
            f"questions for a {class_name} student studying '{subject_name}'. "
            f"The chapters covered so far this year are: {chapter_str}. "
            f"Questions must be appropriate for Nepal CDC curriculum level. "
            f"Return ONLY a valid JSON array. Each item must have exactly these keys: "
            f"text (question), option_a, option_b, option_c, option_d, correct (A/B/C/D), chapter. "
            f"No extra text outside the JSON array."
        )
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=2000,
        )
        content = resp.choices[0].message.content.strip()
        start = content.find("[")
        end   = content.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            if data and len(data) >= 5:
                return data[:count]
    except Exception:
        pass

    # Try Gemini
    try:
        import google.generativeai as genai
        from django.conf import settings
        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("No Gemini key")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"Nepal CDC curriculum quiz. Generate {count} MCQ for class {class_name}, "
            f"subject '{subject_name}', chapters: {chapter_str}. "
            f"Return valid JSON array only. Each item: text, option_a, option_b, option_c, option_d, correct (A/B/C/D), chapter."
        )
        response = model.generate_content(prompt)
        content  = response.text.strip()
        start = content.find("[")
        end   = content.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            if data and len(data) >= 5:
                return data[:count]
    except Exception:
        pass

    # Fallback: subject-specific questions
    return _fallback_questions(class_name, subject_name, chapters, count)


def _fallback_questions(class_name: str, subject_name: str, chapters: list, count: int) -> list:
    """Return subject-specific fallback questions when AI is unavailable."""
    subject_key = _normalise_subject(subject_name)

    # Try exact match first, then partial
    pool = FALLBACK_POOL.get(subject_key)
    if not pool:
        for key in FALLBACK_POOL:
            if subject_key in key or key in subject_key:
                pool = FALLBACK_POOL[key]
                break
    if not pool:
        pool = FALLBACK_POOL["mathematics"]  # last resort

    # Tag each question with the appropriate chapter
    tagged = []
    for i, q in enumerate(pool):
        item = dict(q)
        item["chapter"] = chapters[i % len(chapters)] if chapters else f"{subject_name} Ch.1"
        tagged.append(item)

    random.shuffle(tagged)
    return tagged[:count]


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def start_quiz_session(student, subject=None) -> QuizSession:
    """Create a QuizSession with AI-generated subject-specific questions."""
    class_obj    = student.section.class_obj
    subject_name = subject.name if subject else "Mathematics"

    chapters = _get_chapters_for_class_subject(class_obj.name, subject_name)
    q_data   = _generate_questions_ai(class_obj.name, subject_name, chapters, count=10)

    session = QuizSession.objects.create(
        student=student,
        subject=subject,
        class_obj=class_obj,
        total=len(q_data),
    )
    for i, qd in enumerate(q_data):
        Question.objects.create(
            session=session,
            text=qd.get("text", ""),
            option_a=qd.get("option_a", ""),
            option_b=qd.get("option_b", ""),
            option_c=qd.get("option_c", ""),
            option_d=qd.get("option_d", ""),
            correct=str(qd.get("correct", "A")).upper()[:1],
            chapter=qd.get("chapter", ""),
            order=i,
        )
    return session


def submit_answer(question_pk, chosen: str):
    q = Question.objects.get(pk=question_pk)
    q.chosen     = chosen.upper()[:1]
    q.is_correct = (q.chosen == q.correct.upper())
    q.save(update_fields=["chosen", "is_correct"])
    return q


def finish_session(session_pk):
    session = QuizSession.objects.get(pk=session_pk)
    score   = session.questions.filter(is_correct=True).count()
    session.score      = score
    session.completed  = True
    session.finished_at = timezone.now()
    session.save(update_fields=["score", "completed", "finished_at"])
    return session
