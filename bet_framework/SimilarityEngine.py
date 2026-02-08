from typing import Dict, Any
from rapidfuzz import fuzz
import unicodedata
import re

from bet_framework.SettingsManager import settings_manager


class SimilarityEngine:
    """Encapsulates match-name similarity logic.

    Configurable via SettingsManager under keys 'similarity' or 'similarity_config'.
    Exposes a single function `is_similar(a, b)` for external use.
    """

    def __init__(self, cfg: Dict[str, Any] = None):
        cfg = cfg or {}
        # Load config keys from SettingsManager if not provided
        if not cfg:
            cfg = settings_manager.get_config('similarity_config')

        self.acronyms = cfg.get('acronyms', {})
        self.team_shorts = cfg.get('team_shorts', {})

        # weights for hybrid matching
        weights = cfg.get('weights', {})
        self.token_weight = weights.get('token', 0.5)
        self.substr_weight = weights.get('substr', 0.1)
        self.phonetic_weight = weights.get('phonetic', 0.1)
        self.ratio_weight = weights.get('ratio', 0.3)

        self.similarity_threshold = cfg.get('threshold', 65)

    @staticmethod
    def _soundex(name: str) -> str:
        name = name.upper()
        replacements = {
            "BFPV": "1", "CGJKQSXZ": "2", "DT": "3",
            "L": "4", "MN": "5", "R": "6"
        }
        if not name:
            return "0000"
        soundex_code = name[0]
        for char in name[1:]:
            for key, value in replacements.items():
                if char in key:
                    if soundex_code[-1] != value:
                        soundex_code += value
        soundex_code = soundex_code[:4].ljust(4, "0")
        return soundex_code[:4]

    def _normalize(self, match_name: str) -> str:
        # Decompose Unicode and remove diacritics
        name = unicodedata.normalize('NFD', match_name)
        name = ''.join(ch for ch in name if unicodedata.category(ch) != 'Mn')
        name = re.sub(r"[(),.`]", "", name)
        name = re.sub(r"\s[v](?=[A-Z])", " vs ", name)
        name = re.sub(r"\b\s?(vs|v|-|:|,|@)\s?\b", " vs ", name, flags=re.IGNORECASE)
        name = " ".join(name.split()).lower()

        for k, v in self.team_shorts.items():
            if name == k:
                name = v

        for k, v in self.acronyms.items():
            if k in name:
                name = name.replace(k, v)

        return name

    def hybrid_match(self, s1: str, s2: str) -> float:
        token_score = fuzz.token_set_ratio(s1, s2)
        substr_presence = any(word in s2 for word in s1.split())
        substr_score = 100 if substr_presence else 0
        soundex1 = self._soundex(s1.split()[0]) if s1.split() else "0000"
        soundex2 = self._soundex(s2.split()[0]) if s2.split() else "0000"
        phonetic_score = 100 if soundex1 == soundex2 else 0
        ratio_score = fuzz.ratio(s1, s2)

        final_score = (
            self.token_weight * token_score +
            self.substr_weight * substr_score +
            self.phonetic_weight * phonetic_score +
            self.ratio_weight * ratio_score
        )
        return final_score

    # todo - make generic, look at book-finder
    def is_similar(self, match1: str, match2: str) -> bool:
        n1 = self._normalize(match1)
        n2 = self._normalize(match2)
        parts1 = n1.split(' vs ')
        parts2 = n2.split(' vs ')
        if len(parts1) < 2 or len(parts2) < 2:
            # fallback to direct ratio
            return self.hybrid_match(n1, n2) > self.similarity_threshold
        home1, away1 = parts1[0], parts1[1]
        home2, away2 = parts2[0], parts2[1]
        home_score = self.hybrid_match(home1, home2)
        away_score = self.hybrid_match(away1, away2)
        return (home_score + away_score) / 2 > self.similarity_threshold
