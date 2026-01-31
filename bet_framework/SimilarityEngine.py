from functools import lru_cache
from typing import Dict, Any, Tuple
from rapidfuzz import fuzz
import unicodedata
import re

class SimilarityEngine:
    """Encapsulates match-name similarity logic.
    Exposes a single function `is_similar(a, b)` for external use.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimilarityEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, cfg: Dict[str, Any]):
        if self._initialized:
            return

        self.acronyms = cfg.get('acronyms', {})
        self.team_shorts = cfg.get('team_shorts', {})

        # weights for hybrid matching
        weights = cfg.get('weights', {})
        self.token_weight = weights.get('token', 0.5)
        self.substr_weight = weights.get('substr', 0.1)
        self.phonetic_weight = weights.get('phonetic', 0.1)
        self.ratio_weight = weights.get('ratio', 0.3)

        self.similarity_threshold = cfg.get('threshold', 65)

        # Caches
        self._norm_cache: Dict[str, str] = {}
        self._soundex_cache: Dict[str, str] = {}
        self._result_cache: Dict[Tuple[str, str], Tuple[bool, float]] = {}

        self._initialized = True

    def _soundex(self, name: str) -> str:
        if name in self._soundex_cache:
            return self._soundex_cache[name]

        orig_name = name
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
        res = soundex_code[:4]
        self._soundex_cache[orig_name] = res
        return res

    def _normalize(self, match_name: str) -> str:
        if match_name in self._norm_cache:
            return self._norm_cache[match_name]

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

        # TODO: problem, they overwrite even part of names in teams ! like "medias " , detects "as "
        for k, v in self.acronyms.items():
            if k in name:
                name = name.replace(k, v)

        self._norm_cache[match_name] = name
        return name

    def _share_token(self, s1: str, s2: str) -> bool:
        """Fast pre-filter: check if s1 and s2 share at least one word token."""
        tokens1 = set(s1.split())
        tokens2 = set(s2.split())
        return not tokens1.isdisjoint(tokens2)

    def hybrid_match(self, s1: str, s2: str) -> float:
        # Fast path: token pre-filter
        if not self._share_token(s1, s2):
            return 0.0

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

    def is_similar(self, s1: str, s2: str) -> Tuple[bool, float]:
        """Check similarity between two raw strings. Normalization and caching are handled internally."""
        # Check global cache
        cache_key = tuple(sorted([s1, s2]))
        if cache_key in self._result_cache:
            return self._result_cache[cache_key]

        n1 = self._normalize(s1)
        n2 = self._normalize(s2)

        score = self.hybrid_match(n1, n2)
        res = (score > self.similarity_threshold, score)

        self._result_cache[cache_key] = res
        return res
