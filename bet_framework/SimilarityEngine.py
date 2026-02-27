from functools import lru_cache
from typing import Dict, Any, Tuple
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

    @lru_cache(maxsize=1024)
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

        # Clean acronyms using positional logic:
        # 1. No spaces (e.g., 'fc'): Replaced anywhere as a whole word (\bword\b).
        # 2. Leading space (e.g., ' utd'): Replaced ONLY as a suffix at the end of the string.
        # 3. Trailing space (e.g., 'as '): Replaced ONLY as a prefix at the start of the string.
        # 4. Both spaces (e.g., ' de '): Replaced ONLY when found in the middle of words.
        for k, v in self.acronyms.items():
            if not k.strip():
                continue

            starts_space = k.startswith(' ')
            ends_space = k.endswith(' ')
            word = k.strip()
            pattern = re.escape(word)

            if starts_space and ends_space:
                pattern = rf"\s+{pattern}\s+"
                repl = str(v)  # Preserve intended spaces in replacement (e.g., ' de ' -> ' ')
            elif starts_space:
                pattern = rf"\s+{pattern}$"
                repl = ""
            elif ends_space:
                pattern = rf"^{pattern}\s+"
                repl = ""
            else:
                # Default: Whole-word boundary. Protects 'medias' from 'as' matches.
                pattern = rf"\b{pattern}\b"
                repl = ""

            name = re.sub(pattern, repl, name)

        # Final cleanup of any double spaces or dangling edges
        name = " ".join(name.split())

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

    def is_similar(self, s1: str, s2: str, n1: str = None, n2: str = None) -> Tuple[bool, float]:
        """Check similarity. Can accept pre-normalized strings n1, n2 for efficiency."""
        n1 = n1 if n1 is not None else self._normalize(s1)
        n2 = n2 if n2 is not None else self._normalize(s2)
        score = self.hybrid_match(n1, n2)
        return score > self.similarity_threshold, score
