# COPYRIGHT ILINE TECH 2026 BY FERAK ALADDIN
"""
Configuration centralisée — TASHIL
Smart Health Management System
Institutions : EPSP, EPH, CHU, EHU
"""

APP_NAME        = "TASHIL"
APP_TAGLINE     = "Smart Health Management System"
APP_FULL_NAME   = f"{APP_NAME}: {APP_TAGLINE}"
APP_AUTHOR      = "ILINE TECH — FERAK ALADDIN"
APP_YEAR        = "2026"
APP_GITHUB_REPO = "Aladdinweb/TASHIL-ES"
APP_GITHUB_API  = (
    "https://api.github.com/repos/"
    "Aladdinweb/TASHIL-ES/releases/latest")

# ── Identité institutionnelle ─────────────────
INSTITUTION_AR  = "وزارة الصحة"
REPUBLIQUE_AR   = "الجمهورية الجزائرية الديمقراطية الشعبية"
MINISTERE_FR    = "Ministère de la Santé"

# ── Profils d'institutions médicales ─────────
INSTITUTIONS = {
    "EPSP": {
        "nom_fr":    "Établissement Public de Santé de Proximité",
        "nom_ar":    "المؤسسة العمومية للصحة الجوارية",
        "code":      "EPSP",
        "prefixe_serial": "ES",
        "serial_format":  "ES-{POLY:02d}-{NUM:04d}",
        "niveaux": ["Polyclinique", "Salle de Soins", "Unité de Dépistage"],
        "services_autorises": [
            "Urgences", "Consultation", "Dentaire",
            "PMI", "Pédiatre", "Psychologue", "Vaccin",
            "Sage Femme", "Salle de Soin", "ECG",
            "Pharmacie", "Secrétariat", "Administration",
        ],
    },
    "EPH": {
        "nom_fr":    "Établissement Public Hospitalier",
        "nom_ar":    "المؤسسة العمومية الاستشفائية",
        "code":      "EPH",
        "prefixe_serial": "EH",
        "serial_format":  "EH-{WILAYA:02d}-{NUM:04d}",
        "niveaux": ["Hôpital", "Service Hospitalier", "Bloc Opératoire"],
        "services_autorises": [
            "Urgences", "Consultation", "Médecine Interne / Endocrinologue",
            "Service Ophtalmologie", "Dentaire Urgences",
            "Dermatologue", "Pneumologue", "ORL",
            "Pharmacie", "Laboratoire", "Radiologie",
            "Chirurgie", "Maternité", "Pédiatrie",
            "Réanimation", "Administration",
        ],
    },
    "CHU": {
        "nom_fr":    "Centre Hospitalo-Universitaire",
        "nom_ar":    "المركز الاستشفائي الجامعي",
        "code":      "CHU",
        "prefixe_serial": "CU",
        "serial_format":  "CU-{WILAYA:02d}-{NUM:04d}",
        "niveaux": ["CHU Principal", "Clinique Universitaire", "Institut Spécialisé"],
        "services_autorises": "__TOUS__",
    },
    "EHU": {
        "nom_fr":    "Établissement Hospitalo-Universitaire",
        "nom_ar":    "المؤسسة الاستشفائية الجامعية",
        "code":      "EHU",
        "prefixe_serial": "EU",
        "serial_format":  "EU-{WILAYA:02d}-{NUM:04d}",
        "niveaux": ["EHU National", "Centre de Référence"],
        "services_autorises": "__TOUS__",
    },
}

TYPES_INSTITUTION = list(INSTITUTIONS.keys())


def get_institution(code: str) -> dict:
    """Retourne le profil d'une institution."""
    return INSTITUTIONS.get(code.upper(), INSTITUTIONS["EPSP"])


def generer_serial(code_institution: str,
                   num_poly: int = 1,
                   num_seq: int = 1,
                   wilaya: int = 31) -> str:
    """Génère un numéro de série unique."""
    inst = get_institution(code_institution)
    fmt  = inst["serial_format"]
    try:
        return fmt.format(
            POLY=num_poly,
            NUM=num_seq,
            WILAYA=wilaya)
    except Exception:
        return f"{inst['prefixe_serial']}-{num_seq:04d}"


# ── Smart Hub ─────────────────────────────────
SMART_HUB_HOST    = "0.0.0.0"
SMART_HUB_PORT    = 7890
SMART_HUB_SECRET  = "TASHIL2026"
SMART_HUB_TIMEOUT = 30

# ── Services cliniques (20) ───────────────────
SERVICES_CLINIQUES = [
    "Urgences",
    "Consultation",
    "Dentaire",
    "PMI",
    "Pédiatre",
    "Psychologue",
    "Vaccin",
    "Sage Femme",
    "Salle de Soin",
    "ECG",
    "Pharmacie",
    "Médecine Interne / Endocrinologue",
    "Service Ophtalmologie",
    "Secrétariat",
    "Dentaire Urgences",
    "Dermatologue",
    "Pneumologue",
    "ORL",
    "Administration",
    "Autre",
]

# ── Hiérarchie grades ─────────────────────────
HIERARCHIE_GRADES = [
    "Médecin Coordinateur",
    "Médecin Chef",
    "Médecin",
    "Médecin Spécialiste",
    "Chirurgien Dentiste",
    "Pharmacien",
    "Biologiste",
    "Psychologue",
    "Manipulateur Radio",
    "Infirmier Anesthésiste",
    "Sage-Femme",
    "Infirmière",
    "Infirmier",
    "Puéricultrice",
    "Aide-Puéricultrice",
    "ATS (Agent Technique de Santé)",
    "Laborantine",
    "Préparatrice en Pharmacie",
    "Opticien",
    "Assistante Médicale",
    "Assistante Sociale",
    "Aide Soignant",
    "Administrateur (ADM)",
    "Agent de Bureau",
    "Agent de Sécurité (OP)",
    "Ambulancier (OP)",
    "Femme de Ménage (OP)",
    "Autre",
]

GRADES = HIERARCHIE_GRADES

# ── Postes par grade ──────────────────────────
POSTES_PAR_GRADE = {
    "Médecin": [
        "Généraliste",
        "Médecin des Urgences",
        "Médecin Chef de Service",
        "Médecin Coordinateur",
    ],
    "Médecin Spécialiste": [
        "Cardiologue", "Pneumologue", "Pédiatre",
        "Gynécologue", "Ophtalmologue",
        "Dermatologue", "Neurologue",
        "Endocrinologue", "ORL",
    ],
    "Ambulancier (OP)": [
        "Conducteur niveau 1",
        "Conducteur niveau 2",
        "Ambulancier Principal",
    ],
    "Agent de Sécurité (OP)": [
        "Agent de Sécurité",
        "Chef d'Équipe Sécurité",
    ],
    "Infirmière": [
        "Infirmière de Soins",
        "Infirmière Principale",
        "Infirmière Chef",
        "Infirmière des Urgences",
    ],
    "Infirmier": [
        "Infirmier de Soins",
        "Infirmier Principal",
        "Infirmier des Urgences",
    ],
    "Administrateur (ADM)": [
        "Responsable RH",
        "Responsable Administratif",
        "Secrétaire de Direction",
    ],
    "Sage-Femme": [
        "Sage-Femme",
        "Sage-Femme Principale",
        "Sage-Femme Chef",
    ],
}

# ── Types de service tableau ──────────────────
TYPES_SERVICE = [
    "M", "S", "N", "G", "R", "C", "A"
]
TYPES_SERVICE_LABELS = {
    "M": "Matin",
    "S": "Soir",
    "N": "Nuit",
    "G": "Garde",
    "R": "Repos",
    "C": "Congé",
    "A": "Absent",
}

# ── Catégories bordereau ──────────────────────
CATEGORIES_BORDEREAU = [
    "CONGE_ANNUEL",
    "CERTIFICAT_MEDICAL_ARRET",
    "CERTIFICAT_MEDICAL_REPRISE",
    "DEMANDE_3_JOURS_NAISSANCE",
    "DEMANDE_ANNULATION_CONGE",
]
