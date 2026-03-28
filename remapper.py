"""
remapper.py
Bone name normalizer, classifier, and matcher for the VRChat Bone Remapper addon.
Pure Python — no Blender dependency. Safe to test standalone.
"""

import re

# =============================================================================
# DICTIONARY
# =============================================================================
# Structure per category:
#   keywords  : if any token contains one of these → candidate for this category
#   excludes  : if any token contains one of these → disqualified from this category
#   side      : True if this bone type comes in L/R pairs
#   indexed   : True if multiple bones of this type exist in a chain (spine_01, spine_02)
#   bucket    : "body" | "twist" | "helper" | "physics" | "volume" | "adult" | "skip"
#   priority  : higher number wins when multiple categories match (jiggle > twist > volume > body)

DICTIONARY = {

    # -------------------------------------------------------------------------
    # BODY — always remap
    # -------------------------------------------------------------------------
    "hips": {
        "keywords": ["hips", "pelvis", "hip", "root", "cog", "centre", "center"],
        "excludes": ["hipdip", "hip_dip", "hipsdip", "dip", "dips", "hipswing",
                     "socket", "indent", "lovehandle", "twist", "jiggle"],
        "side": False, "indexed": False, "bucket": "body", "priority": 20,
    },
    "spine": {
        "keywords": ["spine", "spn", "vertebra", "torso"],
        "excludes": ["shoulder", "chest", "scapula"],
        "side": False, "indexed": True, "bucket": "body", "priority": 10,
    },
    "chest": {
        "keywords": ["chest", "thorax", "ribcage"],
        "excludes": ["nipple", "breast", "boob"],
        "side": False, "indexed": False, "bucket": "body", "priority": 10,
    },
    "neck": {
        "keywords": ["neck", "cervical", "nck"],
        "excludes": [],
        "side": False, "indexed": True, "bucket": "body", "priority": 10,
    },
    "head": {
        "keywords": ["head", "skull", "cranium"],
        "excludes": ["headband", "hair"],
        "side": False, "indexed": False, "bucket": "body", "priority": 10,
    },
    "shoulder": {
        "keywords": ["shoulder", "clavicle", "collar", "clav", "collarbone"],
        "excludes": ["scapula", "socket", "twist"],
        "side": True, "indexed": False, "bucket": "body", "priority": 10,
    },
    "upper_arm": {
        "keywords": ["upperarm", "upper_arm", "arm", "humerus"],
        "excludes": ["forearm", "lowerarm", "wrist", "twist", "roll",
                     "jiggle", "zbicep", "elbow", "lower", "fore"],
        "side": True, "indexed": False, "bucket": "body", "priority": 12,
    },
    "forearm": {
        "keywords": ["forearm", "lowerarm", "elbow", "radius", "ulna"],
        "excludes": ["twist", "roll", "wrist"],
        "side": True, "indexed": False, "bucket": "body", "priority": 10,
    },
    "hand": {
        "keywords": ["wrist", "hand", "manus", "palm"],
        "excludes": ["finger", "thumb", "index", "middle", "ring",
                     "pinky", "little", "small", "twist"],
        "side": True, "indexed": False, "bucket": "body", "priority": 10,
    },
    "thigh": {
        "keywords": ["thigh", "upleg", "upperleg", "femur", "leg"],
        "excludes": ["hipdip", "twist", "roll", "socket", "knee", "jiggle",
                     "lowerleg", "foreleg"],
        "side": True, "indexed": False, "bucket": "body", "priority": 10,
    },
    "shin": {
        "keywords": ["shin", "calf", "lowerleg", "foreleg", "tibia", "knee"],
        "excludes": [],
        "side": True, "indexed": False, "bucket": "body", "priority": 10,
    },
    "foot": {
        "keywords": ["foot", "ankle", "heel"],
        "excludes": ["toe", "ball", "twist"],
        "side": True, "indexed": False, "bucket": "body", "priority": 10,
    },
    "toe_group": {
        "keywords": ["toes"],
        "excludes": ["anchor"],
        "side": True, "indexed": False, "bucket": "body", "priority": 10,
    },
    "toe_single": {
        "keywords": ["toe"],
        "excludes": ["anchor", "index", "middle", "ring", "little",
                     "small", "big", "thumb", "pinky"],
        "side": True, "indexed": False, "bucket": "body", "priority": 9,
    },
    "toe_big": {
        "keywords": ["bigtoe", "hallux", "thumbtoe", "big"],
        "excludes": ["anchor", "finger", "arm", "leg"],
        "side": True, "indexed": False, "bucket": "body", "priority": 12,
    },
    "toe_index": {
        "keywords": ["indextoe"],
        "excludes": ["anchor", "finger"],
        "side": True, "indexed": False, "bucket": "body", "priority": 12,
    },
    "toe_middle": {
        "keywords": ["middletoe"],
        "excludes": ["anchor", "finger"],
        "side": True, "indexed": False, "bucket": "body", "priority": 12,
    },
    "toe_ring": {
        "keywords": ["ringtoe"],
        "excludes": ["anchor", "finger"],
        "side": True, "indexed": False, "bucket": "body", "priority": 12,
    },
    "toe_pinky": {
        "keywords": ["pinkytoe", "littletoe"],
        "excludes": ["anchor", "finger"],
        "side": True, "indexed": False, "bucket": "body", "priority": 12,
    },
    "eye": {
        "keywords": ["eye", "ocular", "iris"],
        "excludes": ["eyebrow", "eyelid", "brow", "lash"],
        "side": True, "indexed": False, "bucket": "body", "priority": 10,
    },

    # -------------------------------------------------------------------------
    # FINGERS
    # -------------------------------------------------------------------------
    "thumb": {
        "keywords": ["thumb", "pollex", "thm"],
        "excludes": ["toe"],
        "side": True, "indexed": True, "bucket": "body", "priority": 13,
    },
    "index_finger": {
        "keywords": ["index", "indexfinger", "pointer", "finger1"],
        "excludes": ["toe", "middle", "ring", "little", "small", "pinky"],
        "side": True, "indexed": True, "bucket": "body", "priority": 13,
    },
    "middle_finger": {
        "keywords": ["middle", "middlefinger", "finger2"],
        "excludes": ["toe"],
        "side": True, "indexed": True, "bucket": "body", "priority": 13,
    },
    "ring_finger": {
        "keywords": ["ring", "ringfinger", "finger3"],
        "excludes": ["toe"],
        "side": True, "indexed": True, "bucket": "body", "priority": 13,
    },
    "pinky_finger": {
        "keywords": ["pinky", "pinkie", "little", "littlefinger",
                     "small", "smallfinger", "finger4"],
        "excludes": ["toe", "index", "middle", "ring"],
        "side": True, "indexed": True, "bucket": "body", "priority": 14,
    },
    "metacarpal": {
        "keywords": ["metacarpal"],
        "excludes": [],
        "side": True, "indexed": True, "bucket": "body", "priority": 12,
    },

    # -------------------------------------------------------------------------
    # TWIST / ROTATION HELPERS — remap if target has equivalent
    # -------------------------------------------------------------------------
    "twist_upper_arm": {
        "keywords": ["twist"],
        "region_keywords": ["upperarm", "upper", "arm", "bicep", "zbicep", "midarm", "zarm"],
        "excludes": ["forearm", "lower", "elbow", "wrist", "shin",
                     "knee", "hip", "leg", "butt", "ankle", "fore", "zelbow", "zfore"],
        "side": True, "indexed": False, "bucket": "twist", "priority": 20,
    },
    "twist_elbow": {
        "keywords": ["twist"],
        "region_keywords": ["elbow", "zelbow"],
        "excludes": ["forearm", "wrist", "shin", "knee", "hip", "leg", "butt", "ankle", "upper"],
        "side": True, "indexed": False, "bucket": "twist", "priority": 22,
    },
    "twist_forearm": {
        "keywords": ["twist"],
        "region_keywords": ["forearm", "lowerarm", "lower", "zforearm", "zfore"],
        "excludes": ["shin", "knee", "hip", "leg", "upper", "wrist", "elbow", "zelbow"],
        "side": True, "indexed": False, "bucket": "twist", "priority": 21,
    },
    "twist_wrist": {
        "keywords": ["twist"],
        "region_keywords": ["wrist"],
        "excludes": ["shin", "knee", "hip", "leg", "elbow", "arm"],
        "side": True, "indexed": False, "bucket": "twist", "priority": 23,
    },
    "twist_hip": {
        "keywords": ["twist"],
        "region_keywords": ["hip", "thigh", "leg", "butt"],
        "excludes": ["shin", "knee", "arm", "wrist", "elbow", "ankle"],
        "side": True, "indexed": False, "bucket": "twist", "priority": 20,
    },
    "twist_knee": {
        "keywords": ["twist"],
        "region_keywords": ["knee", "zknee"],
        "excludes": ["arm", "wrist", "elbow", "shin"],
        "side": True, "indexed": False, "bucket": "twist", "priority": 20,
    },
    "twist_ankle": {
        "keywords": ["twist"],
        "region_keywords": ["ankle"],
        "excludes": [],
        "side": True, "indexed": False, "bucket": "twist", "priority": 20,
    },
    "twist_shin": {
        "keywords": ["twist"],
        "region_keywords": ["shin", "uppershin", "midshin", "lowershin"],
        "excludes": ["arm", "wrist", "elbow"],
        "side": True, "indexed": False, "bucket": "twist", "priority": 20,
    },

    # -------------------------------------------------------------------------
    # ANIMATION HELPERS — remap if exact/near match
    # -------------------------------------------------------------------------
    "bicep_helper": {
        "keywords": ["zbicep"],
        "excludes": [],
        "side": True, "indexed": False, "bucket": "helper", "priority": 15,
    },
    "jiggle": {
        "keywords": ["jiggle"],
        "excludes": [],
        "side": True, "indexed": False, "bucket": "helper", "priority": 30,
    },

    # -------------------------------------------------------------------------
    # VOLUME / SHAPE CORRECTION
    # -------------------------------------------------------------------------
    "volume_elbow": {
        "keywords": ["volume"],
        "region_keywords": ["elbow"],
        "excludes": [],
        "side": True, "indexed": False, "bucket": "volume", "priority": 25,
    },
    "volume_knee": {
        "keywords": ["volume"],
        "region_keywords": ["knee"],
        "excludes": [],
        "side": True, "indexed": False, "bucket": "volume", "priority": 25,
    },
    "volume_back": {
        "keywords": ["volume"],
        "region_keywords": ["back"],
        "excludes": [],
        "side": False, "indexed": False, "bucket": "volume", "priority": 25,
    },
    "belly": {
        "keywords": ["tummy", "belly", "stomach", "abdomen", "navel",
                     "fupa", "pouch", "gut", "paunch", "midsection", "midriff",
                     "volume_tummy"],
        "excludes": [],
        "side": False, "indexed": False, "bucket": "volume", "priority": 25,
    },

    # -------------------------------------------------------------------------
    # SECONDARY PHYSICS — remap if target has equivalent
    # -------------------------------------------------------------------------
    "glute": {
        "keywords": ["ass", "glute", "butt", "buttock", "booty", "rear",
                     "cheek", "rump", "buns", "backside", "bottom", "behind"],
        "excludes": ["root", "anchor", "parent"],
        "side": True, "indexed": False, "bucket": "physics", "priority": 15,
    },
    "breast": {
        "keywords": ["breast", "boob", "bust", "pec", "peck", "tit",
                     "tiddy", "titty", "knocker", "boobie", "bazonga"],
        "excludes": ["root", "anchor", "parent", "nipple"],
        "side": True, "indexed": True, "bucket": "physics", "priority": 15,
    },
    "nipple": {
        "keywords": ["nipple"],
        "excludes": [],
        "side": True, "indexed": False, "bucket": "physics", "priority": 16,
    },
    "hip_dip": {
        "keywords": ["hipdip", "hip_dip", "hipsdip", "hipindent", "lovehandle",
                     "dip", "dips"],
        "excludes": ["hand", "head"],
        "side": False, "indexed": False, "bucket": "physics", "priority": 15,
    },
    "thigh_secondary": {
        "keywords": ["thigh"],
        "excludes": ["twist", "roll"],
        "side": True, "indexed": False, "bucket": "physics", "priority": 5,
        # Low priority — only wins when parent context confirms it's secondary
    },
    "tail": {
        "keywords": ["tail"],
        "excludes": [],
        "side": False, "indexed": True, "bucket": "physics", "priority": 15,
    },

    # -------------------------------------------------------------------------
    # ADULT ANATOMY — always surface to Needs Review
    # -------------------------------------------------------------------------
    "adult": {
        "keywords": ["pussy", "coochy", "coochie", "cootchie", "vagina",
                     "penis", "cock", "bulge"],
        "excludes": [],
        "side": True, "indexed": False, "bucket": "adult", "priority": 50,
    },

    # -------------------------------------------------------------------------
    # SCAFFOLDING — skip, never remap
    # -------------------------------------------------------------------------
    "scaffolding": {
        "keywords": ["anchor", "parent"],
        "excludes": [],
        "side": False, "indexed": False, "bucket": "skip", "priority": 0,
    },
}

# Noise tokens to ignore during matching (never a category signal)
NOISE_TOKENS = {"bone", "base", "ctrl", "rig"}

# Namespace prefixes to strip before any processing
NAMESPACE_PREFIXES = ["mixamorig:", "ORG-", "DEF-"]

# =============================================================================
# NORMALIZER
# =============================================================================

def _split_camel(s):
    """Split camelCase into tokens: 'UpperArm' → ['Upper', 'Arm']"""
    return re.sub(r'([a-z])([A-Z])', r'\1 \2', s).split()


def _tokenize(name):
    """
    Split a bone name into lowercase tokens.
    Handles: spaces, underscores, dots, hyphens, camelCase, colons.
    Returns list of non-empty lowercase strings.
    """
    s = re.sub(r'[\._\-:]', ' ', name)
    parts = []
    for part in s.split():
        parts.extend(_split_camel(part))
    tokens = [p.lower().strip() for p in parts if p.strip()]
    return tokens


def _extract_side(name):
    """
    Detect L/R side from a bone name.
    Returns ('L', remainder) | ('R', remainder) | (None, original)
    Checks in order: fast prefix → full word prefix → suffix scan → token scan
    """
    s = name.strip()

    # 1. Fast path — single char prefix: "L Arm", "R.Leg", "L_Shoulder"
    if len(s) > 1 and s[0] in ('L', 'R') and s[1] in ('_', '.', ' '):
        return s[0], s[2:].strip()

    # 2. Full word prefix — "Left arm", "Right_Arm", "LeftArm"
    for side, word in [('L', 'Left'), ('R', 'Right')]:
        if s.lower().startswith(word.lower()):
            rest = s[len(word):]
            if rest and rest[0] in ('_', '.', ' ', '-'):
                return side, rest.lstrip('_.- ')
            elif rest and rest[0].isupper():
                return side, rest

    # 3. Suffix scan — strip Blender index first (.001/.002) then check side
    #    This handles "Ring Finger_R.001" → strip .001 → "Ring Finger_R" → suffix _R
    stripped = re.sub(r'\.\d{3}$', '', s).strip()
    suffixes = [
        ('.L', 'L'), ('_L', 'L'), ('.l', 'L'), ('_l', 'L'),
        ('.R', 'R'), ('_R', 'R'), ('.r', 'R'), ('_r', 'R'),
        ('.Left', 'L'), ('_Left', 'L'), ('.Right', 'R'), ('_Right', 'R'),
    ]
    for suffix, side in suffixes:
        if stripped.endswith(suffix):
            remainder = stripped[:-len(suffix)].strip()
            return side, remainder

    # 4. Token scan fallback — side buried anywhere in name
    tokens = _tokenize(s)
    for token in tokens:
        if token == 'left':
            return 'L', s
        if token == 'right':
            return 'R', s

    return None, s


def _extract_index(name):
    """
    Extract trailing numeric index from a bone name.
    Handles: .001, .002, _0, _1, 1, 2, 02, 03 etc.
    Returns (index_int_or_None, name_without_index)
    """
    # Blender style: .001 .002
    m = re.search(r'\.(\d{3})$', name)
    if m:
        return int(m.group(1)), name[:m.start()].strip()

    # Underscore+number suffix: _0, _1, _01, _02
    m = re.search(r'_(\d+)$', name)
    if m:
        return int(m.group(1)), name[:m.start()].strip()

    # Trailing space+number: "Spine 01", "Toe 2"
    m = re.search(r'\s+(\d+)$', name)
    if m:
        return int(m.group(1)), name[:m.start()].strip()

    # Trailing number stuck to last word: "Spine1", "IndexFinger2"
    m = re.search(r'(\d+)$', name)
    if m:
        return int(m.group(1)), name[:m.start()].strip()

    return None, name


def _detect_flags(name, tokens):
    """
    Detect special flags from name and tokens.
    Returns list of flag strings.
    """
    flags = []
    name_lower = name.lower().strip()

    # End bone
    if name_lower.endswith('_end') or name_lower.endswith(' end'):
        flags.append('end')

    # Z-prefix helper/twist (ZArm, ZBicep etc.)
    if re.match(r'^[Zz][A-Z]', name.strip()):
        flags.append('z_helper')

    # Twist keyword anywhere
    if 'twist' in tokens:
        flags.append('twist')

    # Volume keyword
    if 'volume' in tokens:
        flags.append('volume')

    # Jiggle keyword
    if 'jiggle' in tokens:
        flags.append('jiggle')

    # Physics scaffolding
    if any(t in tokens for t in ['anchor', 'parent']):
        flags.append('scaffolding')

    # Root — only flag as scaffolding if it's not the main hips/root bone
    # i.e. if "root" appears alongside another non-body keyword
    if 'root' in tokens and len(tokens) > 1:
        non_root = [t for t in tokens if t != 'root']
        body_keywords = {'hips', 'hip', 'pelvis', 'cog', 'center', 'centre'}
        if not any(t in body_keywords for t in non_root):
            flags.append('scaffolding')

    return flags


def normalize(raw_name):
    """
    Full normalization pipeline for a single bone name.
    Returns a dict with everything the classifier needs.
    """
    name = raw_name.strip()

    # Strip namespace prefixes
    for prefix in NAMESPACE_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    # Detect flags before side/index extraction (needs original form for Z-prefix check)
    tokens_pre = _tokenize(name)
    flags = _detect_flags(name, tokens_pre)

    # Strip Z-prefix from name for further processing
    # "ZForeArm" → "ForeArm", "ZArm" → "Arm", "ZBicep" → "Bicep"
    z_stripped = name
    if 'z_helper' in flags:
        z_stripped = name[1:]  # just drop the Z, rest is fine

    # Extract side
    side, name_no_side = _extract_side(z_stripped)

    # Extract index
    index, name_clean = _extract_index(name_no_side)

    # Final tokenize on cleaned name
    tokens = _tokenize(name_clean)

    # Remove noise tokens and side tokens that leaked through token scan
    side_tokens = {'left', 'right', 'l', 'r'}
    tokens = [t for t in tokens if t not in NOISE_TOKENS and t not in side_tokens]

    # Remove pure numeric tokens (already captured as index)
    tokens = [t for t in tokens if not t.isdigit()]

    return {
        "raw":    raw_name,
        "side":   side,
        "index":  index,
        "tokens": tokens,
        "flags":  flags,
        "clean":  name_clean,
    }


# =============================================================================
# CLASSIFIER
# =============================================================================

# Short keywords that must match exactly (3-4 chars, high collision risk)
EXACT_ONLY_KEYWORDS = {
    'arm', 'leg', 'hip', 'hips', 'toe', 'ear', 'eye', 'jaw', 'rib',
    'dip', 'dips', 'mid', 'low', 'top', 'end', 'pec', 'knee', 'shin',
    'big', 'ring', 'fore', 'head',
}

def _tokens_match(norm_tokens, keywords):
    """
    Match tokens against keywords.
    - Exact token == keyword: always matches
    - For keywords in EXACT_ONLY_KEYWORDS: exact match only
    - For longer keywords: substring match (kw in token or token in kw)
    - Compound join: join all tokens, check if compound keyword appears
    """
    joined = "".join(norm_tokens)
    for token in norm_tokens:
        for kw in keywords:
            if token == kw:
                return True
            if kw in EXACT_ONLY_KEYWORDS:
                continue  # exact only, no substring
            if len(kw) > 3:
                # kw in token: e.g. "forearm" in "forearmtwist" ✓
                if kw in token:
                    return True
                # token in kw: e.g. "fore" in "forearm" ✓
                # BUT skip if token is an exact-only keyword — "arm" should not match inside "forearm"
                if token not in EXACT_ONLY_KEYWORDS and token in kw:
                    return True
    # Compound join for multi-token keywords like 'midshin', 'forearm'
    for kw in keywords:
        if kw not in EXACT_ONLY_KEYWORDS and len(kw) > 4 and kw in joined:
            return True
    return False


def _region_match(norm_tokens, region_keywords):
    """
    Looser matching for twist/volume region keywords.
    Uses substring match — we want 'zarm' to match 'arm',
    'midshin' compound to match 'shin', etc.
    BUT short exact-only tokens (arm, leg, hip etc.) still require exact match
    to prevent 'arm' matching inside 'forearm'.
    Also checks joined token string.
    """
    joined = "".join(norm_tokens)
    for token in norm_tokens:
        for kw in region_keywords:
            if token == kw:
                return True
            # Skip substring check if token is in EXACT_ONLY_KEYWORDS
            if token in EXACT_ONLY_KEYWORDS:
                continue
            if kw in token or token in kw:
                return True
    for kw in region_keywords:
        if kw in joined:
            return True
    return False


def _tokens_excluded(norm_tokens, excludes):
    """Return True if any exclude keyword matches any token."""
    return _tokens_match(norm_tokens, excludes)


def classify(norm):
    """
    Classify a normalized bone into a category.
    Returns dict with category, bucket, confidence, and notes.
    """
    tokens = norm["tokens"]
    flags  = norm["flags"]

    # --- Fast exits ---
    if 'end' in flags:
        return {"category": "end_bone", "bucket": "skip",
                "confidence": "high", "notes": "terminal end bone"}

    if 'scaffolding' in flags:
        return {"category": "scaffolding", "bucket": "skip",
                "confidence": "high", "notes": "physics chain scaffolding"}

    if _tokens_match(tokens, DICTIONARY["adult"]["keywords"]):
        return {"category": "adult", "bucket": "review",
                "confidence": "high", "notes": "adult anatomy — surface to user"}

    # Named toe compound detection
    if 'toe' in tokens:
        if any(t in tokens for t in ['big', 'bigtoe', 'hallux', 'thumbtoe']):
            return {"category": "toe_big", "bucket": "body",
                    "confidence": "high", "notes": "big toe / hallux"}
        if any(t in tokens for t in ['little', 'littletoe', 'pinkytoe', 'small']):
            return {"category": "toe_pinky", "bucket": "body",
                    "confidence": "high", "notes": "little / pinky toe"}
        if any(t in tokens for t in ['index', 'indextoe']):
            return {"category": "toe_index", "bucket": "body",
                    "confidence": "high", "notes": "index toe"}
        if any(t in tokens for t in ['middle', 'middletoe']):
            return {"category": "toe_middle", "bucket": "body",
                    "confidence": "high", "notes": "middle toe"}
        if any(t in tokens for t in ['ring', 'ringtoe']):
            return {"category": "toe_ring", "bucket": "body",
                    "confidence": "high", "notes": "ring toe"}
        # Plain "toe" alone or with index number = single/group toe bone
        return {"category": "toe_single", "bucket": "body",
                "confidence": "high", "notes": "single toe bone"}

    # Named finger compound detection — specific name wins before general loop
    if 'finger' in tokens:
        # Metacarpal: bare "finger" with index 4 or 5 = ring/pinky metacarpal
        idx = norm.get("index")
        if idx in (4, 5) and not any(t in tokens for t in
                ['index', 'middle', 'ring', 'little', 'small', 'pinky']):
            return {"category": "metacarpal", "bucket": "body",
                    "confidence": "medium",
                    "notes": f"finger {idx} = {'ring' if idx==4 else 'pinky'} metacarpal"}
        if any(t in tokens for t in ['index', 'pointer']):
            return {"category": "index_finger", "bucket": "body",
                    "confidence": "high", "notes": "index finger"}
        if any(t in tokens for t in ['middle']):
            return {"category": "middle_finger", "bucket": "body",
                    "confidence": "high", "notes": "middle finger"}
        if any(t in tokens for t in ['ring']):
            return {"category": "ring_finger", "bucket": "body",
                    "confidence": "high", "notes": "ring finger"}
        if any(t in tokens for t in ['little', 'small', 'pinky', 'pinkie']):
            return {"category": "pinky_finger", "bucket": "body",
                    "confidence": "high", "notes": "pinky / little finger"}

    # Twist+shin compound: Twist_MidShin, Twist_UpperShin etc.
    if 'twist' in flags and 'shin' in tokens:
        return {"category": "twist_shin", "bucket": "twist",
                "confidence": "high", "notes": "shin twist"}
    if 'twist' in flags and _region_match(tokens, ['shin', 'midshin', 'uppershin', 'lowershin']):
        return {"category": "twist_shin", "bucket": "twist",
                "confidence": "high", "notes": "shin twist"}

    # --- Score all categories ---
    candidates = []

    for cat_name, cat in DICTIONARY.items():
        if cat["bucket"] == "skip":
            continue
        if cat_name == "adult":
            continue

        # Check excludes first
        if _tokens_excluded(tokens, cat.get("excludes", [])):
            continue

        # Check primary keywords
        if not _tokens_match(tokens, cat.get("keywords", [])):
            continue

        # Twist/volume categories also need a region keyword match
        region_kws = cat.get("region_keywords")
        if region_kws:
            if not ('twist' in flags or 'volume' in flags):
                continue
            # Use looser region matching (substring always)
            if _region_match(tokens, region_kws):
                candidates.append((cat["priority"], cat_name, "high"))
            elif 'twist' in flags:
                # Twist detected but region unclear — add as medium confidence
                candidates.append((cat["priority"] - 5, cat_name, "medium"))
            continue

        candidates.append((cat["priority"], cat_name, "high"))

    # Fallbacks if no candidates
    if not candidates:
        if 'jiggle' in flags or _tokens_match(tokens, ["jiggle"]):
            return {"category": "jiggle", "bucket": "helper",
                    "confidence": "medium", "notes": "jiggle bone, unknown region"}
        if 'twist' in flags:
            return {"category": "twist_unknown", "bucket": "twist",
                    "confidence": "low", "notes": "twist bone, region not identified"}
        return {"category": None, "bucket": "unmatched",
                "confidence": "none", "notes": "no category match"}

    # Highest priority wins
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, winner, confidence = candidates[0]

    cat = DICTIONARY[winner]
    return {
        "category":   winner,
        "bucket":     cat["bucket"],
        "confidence": confidence,
        "notes":      f"{len(candidates)} candidate(s)" if len(candidates) > 1 else "",
    }


# =============================================================================
# MATCHER
# =============================================================================

def build_bone_info(bone_names, hierarchy=None):
    """
    Normalize and classify a list of bone names.
    hierarchy: dict of {bone_name: parent_name} for context-aware disambiguation.
    Returns list of dicts with norm + classification merged.
    """
    results = []
    for name in bone_names:
        norm = normalize(name)
        cls  = classify(norm)

        # Context: thigh_secondary disambiguation
        # If classified as thigh but parent is also a thigh-category bone → secondary
        if cls["category"] == "thigh" and hierarchy:
            parent_name = hierarchy.get(name)
            if parent_name:
                parent_norm = normalize(parent_name)
                parent_cls  = classify(parent_norm)
                if parent_cls["category"] == "thigh":
                    cls["category"] = "thigh_secondary"
                    cls["bucket"]   = "physics"
                    cls["notes"]    = "child of thigh bone → secondary physics"

        results.append({**norm, **cls})
    return results


def _build_children_map(hierarchy):
    """Invert {child: parent} → {parent: [children]}"""
    children = {}
    for bone, parent in hierarchy.items():
        if parent is not None:
            children.setdefault(parent, []).append(bone)
    return children


# Expected child categories for each body category.
# Used as a tiebreaker when multiple target bones share the same category+side.
_EXPECTED_CHILDREN = {
    "upper_arm":  ["forearm", "twist_upper_arm", "twist_elbow", "bicep_helper"],
    "forearm":    ["hand", "twist_forearm", "twist_wrist"],
    "hand":       ["thumb", "index_finger", "middle_finger", "ring_finger",
                   "pinky_finger"],
    "thigh":      ["shin", "twist_hip", "thigh_secondary"],
    "shin":       ["foot", "twist_knee", "twist_shin"],
    "foot":       ["toe_single", "toe_group", "toe_big", "twist_ankle"],
    "shoulder":   ["upper_arm"],
    "chest":      ["shoulder", "neck", "breast", "nipple", "pec"],
    "spine":      ["chest"],
    "hips":       ["spine", "thigh", "glute", "hip_dip", "belly", "tail"],
    "neck":       ["head"],
    "head":       ["eye"],
}


def _topology_score(bone_name, category, children_map, bone_info_map):
    """
    Score a candidate bone based on whether its actual children
    match what we expect for its category.

    Returns:
      2  — has expected children (strong positive signal)
      1  — is a leaf with no real children (neutral/negative)
      0  — default / unknown
    """
    # Get real children (ignore _end bones)
    kids = [
        k for k in children_map.get(bone_name, [])
        if not (k.endswith('_end') or k.endswith(' end'))
    ]

    if not kids:
        # Leaf bone — strong signal it's a helper, not a primary segment
        return 1

    expected = _EXPECTED_CHILDREN.get(category, [])
    if not expected:
        return 0

    # Check if any child classifies as an expected category
    for kid in kids:
        if kid in bone_info_map:
            kid_cat = bone_info_map[kid].get("category")
            if kid_cat in expected:
                return 2

    return 0


def match(source_bones, target_bones, hierarchy=None):
    """
    Match source bone names to target bone names.

    source_bones: list of bone name strings (from mesh vertex groups)
    target_bones: list of bone name strings (from target armature)
    hierarchy:    dict {bone_name: parent_name} for disambiguation (optional)

    Returns list of mapping dicts:
    {
        "source":     original source name,
        "target":     matched target name or None,
        "bucket":     "matched" | "review" | "unmatched" | "skip",
        "confidence": "exact" | "high" | "medium" | "low" | "none",
        "notes":      short explanation string,
    }
    """
    # ----------------------------------------------------------------
    # Step 1: exact name match fast path
    # ----------------------------------------------------------------
    target_set     = set(target_bones)
    mappings       = []
    remaining_src  = []
    remaining_tgt  = list(target_bones)

    for src in source_bones:
        if src in target_set:
            mappings.append({
                "source": src, "target": src,
                "bucket": "matched", "confidence": "exact",
                "notes": "",
            })
            remaining_tgt.remove(src)
        else:
            remaining_src.append(src)

    # ----------------------------------------------------------------
    # Step 2: classify everything
    # ----------------------------------------------------------------
    src_info = build_bone_info(remaining_src, hierarchy)
    tgt_info = build_bone_info(remaining_tgt, hierarchy)

    # Build topology helpers from ALL target bones (not just remaining)
    # so children of exact-matched bones are still available for scoring
    all_tgt_info = build_bone_info(target_bones, hierarchy)
    children_map  = _build_children_map(hierarchy) if hierarchy else {}
    bone_info_map = {t["raw"]: t for t in all_tgt_info}

    # Build multi-level target lookup
    tgt_by_exact   = {}  # (cat, side, idx) → info  — only for non-None index
    tgt_by_cat     = {}  # (cat, side)      → [info, ...]
    tgt_used       = set()

    for t in tgt_info:
        if t["bucket"] == "skip":
            continue
        cat, side, idx = t["category"], t["side"], t["index"]

        # Only register exact key when index is meaningful (not None)
        if idx is not None:
            key_exact = (cat, side, idx)
            if key_exact not in tgt_by_exact:
                tgt_by_exact[key_exact] = t

        key_cat = (cat, side)
        tgt_by_cat.setdefault(key_cat, []).append(t)

    def _pick_best(candidates, prefer_category=None):
        """
        Return the best unused candidate.
        If multiple candidates exist for the same category+side,
        use topology score as a tiebreaker.
        Higher score = more likely to be the primary segment bone.
        """
        unused = [c for c in candidates if c["raw"] not in tgt_used]
        if not unused:
            return None
        if len(unused) == 1:
            return unused[0]

        # Multiple candidates — score by topology
        scored = []
        for c in unused:
            score = _topology_score(
                c["raw"],
                c.get("category") or prefer_category,
                children_map,
                bone_info_map,
            )
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]
        second_score = scored[1][0]

        # If topology gave a clear winner, use it
        if best_score > second_score:
            return best

        # Scores tied — return first (insertion order = armature order)
        return unused[0]

    # ----------------------------------------------------------------
    # Step 3: match each source bone
    # ----------------------------------------------------------------
    for s in src_info:

        # --- fast exits ---
        if s["bucket"] == "skip":
            mappings.append({
                "source": s["raw"], "target": None,
                "bucket": "skip", "confidence": "high",
                "notes": s["notes"],
            })
            continue

        if s["bucket"] == "adult":
            mappings.append({
                "source": s["raw"], "target": None,
                "bucket": "review", "confidence": "high",
                "notes": "adult — check manually",
            })
            continue

        if s["category"] is None:
            mappings.append({
                "source": s["raw"], "target": None,
                "bucket": "unmatched", "confidence": "none",
                "notes": "no category match",
            })
            continue

        cat, side, idx = s["category"], s["side"], s["index"]

        # --- level 1: exact (category + side + index) ---
        # Only when index is meaningful — prevents non-indexed bones
        # from grabbing the first candidate before topology scoring runs
        if idx is not None:
            hit = tgt_by_exact.get((cat, side, idx))
            if hit and hit["raw"] not in tgt_used:
                tgt_used.add(hit["raw"])
                mappings.append({
                    "source": s["raw"], "target": hit["raw"],
                    "bucket": "matched" if s["confidence"] == "high" else "review",
                    "confidence": s["confidence"],
                    "notes": "",
                })
                continue

        # --- level 2: category + side, topology tiebreaker ---
        hit = _pick_best(tgt_by_cat.get((cat, side), []), prefer_category=cat)
        if hit:
            tgt_used.add(hit["raw"])
            conf = "high" if s["confidence"] == "high" else "medium"
            mappings.append({
                "source": s["raw"], "target": hit["raw"],
                "bucket": "matched", "confidence": conf,
                "notes": "",
            })
            continue

        # --- level 3: category only (side mismatch — flag as review) ---
        hit = _pick_best(tgt_by_cat.get((cat, None), []), prefer_category=cat)
        if not hit:
            other = 'R' if side == 'L' else 'L'
            hit = _pick_best(tgt_by_cat.get((cat, other), []), prefer_category=cat)
        if hit:
            tgt_used.add(hit["raw"])
            mappings.append({
                "source": s["raw"], "target": hit["raw"],
                "bucket": "review", "confidence": "low",
                "notes": "side or index mismatch — confirm",
            })
            continue

        # --- level 4: no match — review with category info, no wrong guess ---
        mappings.append({
            "source": s["raw"], "target": None,
            "bucket": "review" if s["category"] else "unmatched",
            "confidence": "none",
            "notes": f"{cat} — no target",
        })

    # ----------------------------------------------------------------
    # Step 4: sibling consistency check (post-processing pass)
    # Twist bones whose name-based region doesn't agree with what
    # their same-side body bone actually mapped to get flagged.
    # e.g. Elbow_Twist.L → twist_elbow, but Elbow.L → forearm
    #      → twist_elbow region ≠ forearm → downgrade confidence
    # ----------------------------------------------------------------

    # Twist category → the body category it SHOULD be a sibling of
    _TWIST_PARENT_BODY = {
        "twist_upper_arm": "upper_arm",
        "twist_elbow":     "forearm",   # elbow twist lives on the forearm segment
        "twist_forearm":   "forearm",
        "twist_wrist":     "hand",
        "twist_hip":       "thigh",
        "twist_knee":      "shin",
        "twist_ankle":     "foot",
        "twist_shin":      "shin",
    }

    # Build a map: (body_category, side) → target category that source bone mapped to
    # This tells us what each body segment actually resolved to on the target
    src_body_resolved = {}
    for m in mappings:
        if not m["target"]:
            continue
        src_norm = normalize(m["source"])
        src_cls  = classify(src_norm)
        if src_cls["bucket"] == "body" and src_cls["category"]:
            key = (src_cls["category"], src_norm["side"])
            # Find what target category this resolved to
            tgt_entry = bone_info_map.get(m["target"])
            if tgt_entry:
                src_body_resolved[key] = tgt_entry.get("category")

    # Now check each twist mapping for sibling consistency
    for m in mappings:
        if m["bucket"] == "skip" or not m["target"]:
            continue

        src_norm = normalize(m["source"])
        src_cls  = classify(src_norm)
        twist_cat = src_cls.get("category", "")

        if not twist_cat.startswith("twist_"):
            continue

        expected_body = _TWIST_PARENT_BODY.get(twist_cat)
        if not expected_body:
            continue

        side = src_norm["side"]

        # What did the body bone of this type actually map to on the target?
        actual_body_cat = src_body_resolved.get((expected_body, side))

        if actual_body_cat is None:
            continue  # no sibling to compare against

        # Get the target's twist category
        tgt_entry = bone_info_map.get(m["target"])
        if not tgt_entry:
            continue

        tgt_twist_cat = tgt_entry.get("category", "")
        tgt_expected_body = _TWIST_PARENT_BODY.get(tgt_twist_cat)

        # If the target twist's expected body doesn't match what the
        # source body bone actually resolved to → inconsistency
        if tgt_expected_body and tgt_expected_body != actual_body_cat:
            m["confidence"] = "medium"
            m["bucket"]     = "review"
            m["notes"]      = f"twist region mismatch — verify"

    # ----------------------------------------------------------------
    # Step 5: orphan targets — target bones with a known category
    # that no source bone mapped to, BUT only within the same body
    # region groups as what the source actually covered.
    # e.g. source has arm/forearm → show missing hand/twist bones
    #      but NOT fingers, legs, spine etc.
    # ----------------------------------------------------------------

    # Region groups: categories that travel together
    _REGION_GROUPS = {
        "spine":   {"hips", "spine", "chest", "neck", "head", "eye"},
        "arm":     {"shoulder", "upper_arm", "forearm", "hand",
                    "twist_upper_arm", "twist_elbow", "twist_forearm",
                    "twist_wrist", "bicep_helper"},
        "hand":    {"thumb", "index_finger", "middle_finger", "ring_finger",
                    "pinky_finger", "metacarpal"},
        "leg":     {"thigh", "shin", "foot",
                    "twist_hip", "twist_knee", "twist_shin", "twist_ankle",
                    "thigh_secondary", "volume_knee"},
        "toe":     {"toe_single", "toe_group", "toe_big", "toe_index",
                    "toe_middle", "toe_ring", "toe_pinky"},
        "physics": {"glute", "breast", "nipple", "hip_dip", "belly",
                    "tail", "jiggle", "volume_elbow", "volume_back"},
    }

    # Collect all categories present in the source
    src_categories = set()
    for s in src_info:
        if s.get("category"):
            src_categories.add(s["category"])

    # Which region groups does the source touch?
    covered_regions = set()
    for region, cats in _REGION_GROUPS.items():
        if src_categories & cats:  # any overlap
            covered_regions.add(region)

    # All categories allowed to appear in missing rows
    allowed_missing_cats = set()
    for region in covered_regions:
        allowed_missing_cats |= _REGION_GROUPS[region]

    target_set_used = set(m["target"] for m in mappings if m.get("target"))

    for t in tgt_info:
        if t["raw"] in target_set_used:
            continue
        if t["bucket"] == "skip":
            continue
        if t["category"] is None:
            continue
        if t["bucket"] not in ("body", "twist", "helper", "physics", "volume"):
            continue
        # Only surface if this category is in a region the source touches
        if t["category"] not in allowed_missing_cats:
            continue
        mappings.append({
            "source":     "",
            "target":     t["raw"],
            "bucket":     "missing",
            "confidence": "none",
            "notes":      f"{t['category']} — no source group",
        })

    return mappings


# =============================================================================
# QUICK TEST — run this file directly to verify
# =============================================================================

if __name__ == "__main__":
    # --- classifier test ---
    test_names = [
        "L Arm", "R Leg", "L ZArm Twist", "L ZBicep", "L Index.001",
        "Left arm", "Left elbow", "Left wrist", "LittleFinger1_L",
        "Thumb0_L", "Left knee", "Left ankle",
        "Shoulder.L", "Arm.L", "Elbow.L", "Ring Finger .L",
        "Arm_L", "Leg_L", "Index Finger_L",
        "Left butt", "Butt.L", "Boob Right", "Boob_L",
        "Left breast_0", "Nipple.L", "Hip_Dip", "Hip-Dips", "Hips Dips",
        "Tummy", "Tummy Jiggle", "Thigh Jiggle_L", "Volume_Elbow.r",
        "Twist_Wrist.l", "Wrist_Twist.L", "L ZForeArm Twist",
        "Twist_MidShin.l", "Twist_Hip.l",
        "Left toe", "Toe 1.l", "Big Toe_L", "Little Toe_L",
        "BreastRoot.r", "ButtAnchor.l", "Head_end", "Left butt end",
        "Pussy Touch.L", "Coochy_L",
        "Arm_Left_Finger_4", "Thumb 03_L", "Ring Finger_R.001",
        "Index Finger Left 02.R",
        # New: cross-convention twist and physics
        "Arm_Twist.L", "Butt_Twist.L", "L Ass",
    ]

    print(f"{'RAW NAME':<35} {'SIDE':<5} {'IDX':<5} {'TOKENS':<35} {'CATEGORY':<22} {'BUCKET':<12} {'CONF'}")
    print("-" * 130)
    for name in test_names:
        n = normalize(name)
        c = classify(n)
        print(
            f"{n['raw']:<35} "
            f"{str(n['side']):<5} "
            f"{str(n['index']):<5} "
            f"{str(n['tokens']):<35} "
            f"{str(c['category']):<22} "
            f"{c['bucket']:<12} "
            f"{c['confidence']}"
        )

    # --- cross-convention matcher test ---
    # --- topology tiebreaker test ---
    print("\n" + "="*80)
    print("TOPOLOGY TIEBREAKER TEST")
    print("  Source: Elbow.L (forearm category)")
    print("  Target: two forearm candidates — 'Left elbow' (leaf) vs 'Left ForeArm' (has wrist child)")
    print("="*80)

    source2 = ["Elbow.L", "Elbow.R"]
    target2 = ["Left elbow", "Left ForeArm", "Left wrist",
                "Right elbow", "Right ForeArm", "Right wrist"]
    # Hierarchy: Left ForeArm → Left wrist, Left elbow is a leaf
    hier2 = {
        "Left elbow":   "Left arm",
        "Left ForeArm": "Left arm",
        "Left wrist":   "Left ForeArm",
        "Right elbow":  "Right arm",
        "Right ForeArm":"Right arm",
        "Right wrist":  "Right ForeArm",
        "Left arm":     None,
        "Right arm":    None,
    }
    results2 = match(source2, target2, hier2)
    print(f"{'SOURCE':<20} {'TARGET':<20} {'BUCKET':<12} {'CONF':<8} NOTES")
    print("-"*72)
    for r in results2:
        print(f"{r['source']:<20} {str(r['target']):<20} {r['bucket']:<12} {r['confidence']:<8} {r['notes']}")
    print("="*80)
    source = ["Arm_Twist.L", "Arm_Twist.R", "Butt_Twist.L", "Butt_Twist.R",
              "HipsDips", "Hips", "Boob.L", "Boob.R"]
    target = ["L ZArm Twist", "R ZArm Twist", "L Ass", "R Ass",
              "Hips", "L Pec", "R Pec"]
    results = match(source, target)
    print(f"{'SOURCE':<25} {'TARGET':<25} {'BUCKET':<12} {'CONF':<10} NOTES")
    print("-" * 90)
    for r in results:
        print(f"{r['source']:<25} {str(r['target']):<25} {r['bucket']:<12} {r['confidence']:<10} {r['notes']}")
