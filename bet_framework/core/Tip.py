from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import re
import yaml

from bet_framework.SettingsManager import settings_manager


class TipOrganizer:
    """
    Inline tip categorization helper embedded in `Tip.py`.
    """

    @classmethod
    def _load_templates(cls):
        cfg = settings_manager.get_config('tip_templates')
        if cfg:
            if isinstance(cfg, dict) and 'markets' in cfg:
                return cfg.get('markets') or {}
            return cfg

    @classmethod
    def categorize(cls, text: str):
        if not text:
            return None
        templates = cls._load_templates()
        lower = text.lower()

        if not templates:
            return None

        import re as _re
        for _, market_cfg in templates.items():
            for pattern in market_cfg.get('patterns', []):
                try:
                    match = _re.search(pattern.get('regex', ''), lower, _re.IGNORECASE)
                except _re.error:
                    continue
                if not match:
                    continue

                groups = match.groupdict()
                res = {
                    'market': market_cfg.get('market', 'UNKNOWN'),
                    'selection': pattern.get('selection'),
                    'period': market_cfg.get('period', 'FULL_TIME'),
                    'subject': groups.get('player') or groups.get('team') or pattern.get('subject'),
                    'line': None,
                }
                if 'line' in groups and groups.get('line') is not None:
                    try:
                        res['line'] = float(groups['line'])
                    except ValueError:
                        res['line'] = None

                return res

        return None


@dataclass
class Tip:
    # ---- inputs ----
    raw_text: str
    source: str
    confidence: float
    odds: float
    market: str = "UNKNOWN"

    # ---- derived fields ----
    selection: Optional[str] = None
    subject: Optional[str] = None
    line: Optional[float] = None
    period: str = "FULL_TIME"

    # ---- misc ----
    meta: Dict[str, Any] = field(default_factory=dict)
    valid: bool = False

    def __post_init__(self):
        self.confidence = float(self.confidence) if self.confidence is not None else None
        self.odds = float(self.odds) if self.odds is not None else None
        self._categorize()
        self._validate()

    def _categorize(self):
        """Delegate categorization to TipCategorizer and populate fields."""
        try:
            res = TipOrganizer.categorize(self.raw_text)
        except Exception as e:
            self.meta['error'] = f'categorizer_failed: {e}'
            return

        if not res:
            return

        self.market = res.get('market', self.market)
        self.selection = res.get('selection', self.selection)
        self.period = res.get('period', self.period)
        self.subject = res.get('subject', self.subject)
        self.line = res.get('line', self.line)

    def _validate(self):
        """
        Validate the parsed tip and mark validity.
        """

        # Unknown market → invalid
        if self.market == "UNKNOWN" or self.selection is None:
            self.valid = False
            self.meta["validation_error"] = "unrecognized_tip"
            return

        # Market-specific validation
        if self.market.startswith("OVER_UNDER") and self.line is None:
            self.valid = False
            self.meta["validation_error"] = "missing_line"
            return

        if self.market == "GOALSCORER" and not self.subject:
            self.valid = False
            self.meta["validation_error"] = "missing_subject"
            return

        # Passed all checks
        self.valid = True

    def to_text(self) -> str:
        """Return a normalized text representation for this tip.

        Uses market, selection, subject and line to produce a stable string that
        can be used to compare tips across sources (e.g. "Home Win", "Over 2.5 goals").
        Falls back to raw_text when not enough structured data is available.
        """
        def _fmt_line(ln):
            try:
                if ln is None:
                    return None
                f = float(ln)
                if f.is_integer():
                    return str(int(f))
                return str(f)
            except Exception:
                return str(ln)

        market = (self.market or "").upper()
        sel = (self.selection or "").upper() if self.selection else None

        # Match result
        if market == 'MATCH_RESULT':
            if sel == 'HOME':
                return 'Home Win'
            if sel == 'AWAY':
                return 'Away Win'
            if sel == 'DRAW':
                return 'Draw'

        # Over/Under goals
        if market == 'OVER_UNDER_GOALS' or market == 'OVER_UNDER':
            if sel in ('OVER', 'UNDER'):
                ln = _fmt_line(self.line)
                if ln:
                    return f"{sel.capitalize()} {ln} goals"
                return f"{sel.capitalize()} goals"

        # Both teams to score
        if market == 'BTTS' or market == 'BTTS_YES_NO':
            if sel == 'YES':
                return 'BTTS Yes'
            if sel == 'NO':
                return 'BTTS No'

        # Goalscorer / anytime goalscorer
        if market == 'GOALSCORER' or market == 'GOALSCORER_ANYTIME' or market == 'GOALSCORER_ANYTIME':
            if sel == 'YES' or sel == 'ANYTIME':
                if self.subject:
                    return f"{self.subject.strip()} to score"
                return 'Goalscorer'

        # Over/Under corners/cards
        if market in ('OVER_UNDER_CORNERS', 'OVER_UNDER_CARDS'):
            if sel in ('OVER', 'UNDER'):
                ln = _fmt_line(self.line)
                unit = 'corners' if 'CORNERS' in market else 'cards'
                if ln:
                    return f"{sel.capitalize()} {ln} {unit}"
                return f"{sel.capitalize()} {unit}"

        # Fallback: use selection + subject if possible
        parts = []
        if sel:
            parts.append(sel.capitalize())
        if self.subject:
            parts.append(str(self.subject).strip())
        if parts:
            return " ".join(parts)

        # Final fallback: raw_text trimmed
        return (self.raw_text or '').strip()

    def to_dict(self) -> dict:
        """
        Database-ready representation (safe even if invalid)
        """
        return {
            "market": self.market,
            "selection": self.selection,
            "subject": self.subject,
            "line": self.line,
            "period": self.period,
            "confidence": self.confidence,
            "odds": self.odds,
            "source": self.source,
            "raw_text": self.raw_text,
            "valid": self.valid,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tip":
        """
        Reconstruct Tip from database without re-parsing
        """
        # Create instance without invoking __post_init__ (no re-parse)
        obj = cls.__new__(cls)
        # Manually set attributes
        obj.raw_text = data.get('raw_text', '')
        obj.source = data.get('source', '')
        obj.confidence = data.get('confidence', 0.0)
        obj.odds = data.get('odds', 0.0)
        obj.market = data.get('market', 'UNKNOWN')
        obj.selection = data.get('selection')
        obj.subject = data.get('subject')
        obj.line = data.get('line')
        obj.period = data.get('period', 'FULL_TIME')
        obj.meta = data.get('meta', {}) or {}
        obj.valid = data.get('valid', False)
        return obj