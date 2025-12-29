from typing import Dict, Any, List
from collections import Counter
import math

# --- H2H and scoring constants used by discrepancy calculation ---
H2H_WIN_WEIGHT = 3
WIN_WEIGHT = 3
DRAW_WEIGHT = 1
LOSE_WEIGHT = -3
LEAGUE_POINTS_WEIGHT = 1


class MatchAnalyzer:
    """Analyze a Match object and provide three main pieces of information:

    - discrepancy(match): how 'apart' teams are based on standings, form, h2h and stats
    - suggestions(match): aggregated suggestions from scores, probabilities and tips, each with a confidence 0-100
    - value(match): an overall value indicator (0-100) saying whether the match is a good pick

    The analyzer is defensive: any missing data is skipped and the code falls back
    to available inputs.
    """

    def __init__(self):
        pass

    def analyze_match(self, match) -> Dict[str, Any]:
        """Run full analysis and return a dict with three keys: discrepancy, suggestions, value."""
        disc = self.discrepancy(match)
        suggs = self.suggestions(match)
        val = self.value(match, suggestions=suggs, discrepancy=disc)

        return {
            'discrepancy': disc,
            'suggestions': suggs,
            'value': val,
        }

    def discrepancy(self, match) -> Dict[str, Any]:
        details: Dict[str, Any] = {}

        # --- compute internal base score (league points + form + H2H bias) ---
        try:
            def _team_base(team):
                lp = getattr(team, 'league_points', 0) or 0
                form = getattr(team, 'form', '') or ''
                # form may be list like ['W','D','L'] or string 'WWDLD'
                if isinstance(form, (list, tuple)):
                    fcount = ''.join(form)
                else:
                    fcount = str(form)
                form_value = WIN_WEIGHT * fcount.count('W') + DRAW_WEIGHT * fcount.count('D') + LOSE_WEIGHT * fcount.count('L')
                return float(lp) + float(form_value)

            home_team_score = _team_base(match.home_team)
            away_team_score = _team_base(match.away_team)

            # apply H2H bias if present
            if getattr(match, 'h2h', None):
                h2h_home_wins = getattr(match.h2h, 'home', 0) or 0
                h2h_away_wins = getattr(match.h2h, 'away', 0) or 0
                h2h_bias = H2H_WIN_WEIGHT * (h2h_home_wins - h2h_away_wins)
                if h2h_bias < 0:
                    away_team_score += abs(h2h_bias)
                else:
                    home_team_score += h2h_bias

            base = abs(home_team_score - away_team_score)
        except Exception:
            base = 0.0

        details['base_discrepancy'] = float(base)
        details['home_team_score'] = float(home_team_score) if 'home_team_score' not in details else details['home_team_score']
        details['away_team_score'] = float(away_team_score) if 'away_team_score' not in details else details['away_team_score']

        return {
            'score': float(round(base, 2)),
            'details': details,
        }

    def suggestions(self, match) -> List[Dict[str, Any]]:
        """Aggregate suggestions from predicted scores, probabilities and scraped tips.

        Each suggestion is a dict: { suggestion: str, confidence: 0-100, source: 'scores'|'probabilities'|'tips', details: {...} }
        """
        suggestions: List[Dict[str, Any]] = []

        preds = getattr(match, 'predictions', None)

        # policy: minimum number of sources required for a suggestion and agreement threshold
        min_sources = 2
        threshold_pct = 10.0

        # ---------- Scores-based votes ----------
        try:
            scores = preds.scores if preds and getattr(preds, 'scores', None) else []
            total_scores = len(scores)
            if total_scores >= min_sources:
                # result votes
                res_counts = Counter()
                # DC votes
                dc_hd_count = 0
                dc_ad_count = 0
                # BTTS votes
                btts_count = 0
                no_btts_count = 0
                # total goals frequency
                goals = []
                for s in scores:
                    goals.append(s.home + s.away)
                    if s.home > s.away:
                        res_counts['home'] += 1
                    elif s.home < s.away:
                        res_counts['away'] += 1
                    else:
                        res_counts['draw'] += 1

                    if s.home >= s.away:
                        dc_hd_count += 1
                    if s.away >= s.home:
                        dc_ad_count += 1

                    if s.home > 0 and s.away > 0:
                        btts_count += 1
                    elif s.home == 0 or s.away == 0:
                        no_btts_count += 1

                # result consensus
                for label_key, count in res_counts.items():
                    pct = (count / total_scores) * 100.0
                    if pct >= threshold_pct:
                        label = 'Home Win' if label_key == 'home' else ('Away Win' if label_key == 'away' else 'Draw')
                        suggestions.append({
                            'suggestion': f"{label}",
                            'confidence': round(pct, 1),
                            'source': 'scores',
                            'details': {'count': count, 'total': total_scores}
                        })

                # Double chance from scores (per-source vote)
                dc_hd_pct = (dc_hd_count / total_scores) * 100.0
                dc_ad_pct = (dc_ad_count / total_scores) * 100.0
                if dc_hd_pct >= threshold_pct and dc_hd_pct >= dc_ad_pct:
                    suggestions.append({
                        'suggestion': 'Double Chance (Home or Draw)',
                        'confidence': round(dc_hd_pct, 1),
                        'source': 'scores',
                        'details': {'count': dc_hd_count, 'total': total_scores}
                    })
                elif dc_ad_pct >= threshold_pct and dc_ad_pct > dc_hd_pct:
                    suggestions.append({
                        'suggestion': 'Double Chance (Away or Draw)',
                        'confidence': round(dc_ad_pct, 1),
                        'source': 'scores',
                        'details': {'count': dc_ad_count, 'total': total_scores}
                    })

                # BTTS
                btts_pct = (btts_count / total_scores) * 100.0
                if btts_pct >= threshold_pct:
                    suggestions.append({
                        'suggestion': 'BTTS Yes',
                        'confidence': round(btts_pct, 1),
                        'source': 'scores',
                        'details': {'count': btts_count, 'total': total_scores}
                    })
                no_btts_pct = (no_btts_count / total_scores) * 100.0
                if no_btts_pct >= threshold_pct:
                    suggestions.append({
                        'suggestion': 'BTTS No',
                        'confidence': round(no_btts_pct, 1),
                        'source': 'scores',
                        'details': {'count': no_btts_count, 'total': total_scores}
                    })

                # Most common total goals
                # Over/Under 2.5 goals consensus
                if goals:
                    over_count = sum(1 for t in goals if t >= 3)
                    under_count = total_scores - over_count
                    over_pct = (over_count / total_scores) * 100.0
                    under_pct = (under_count / total_scores) * 100.0
                    if over_pct >= threshold_pct:
                        suggestions.append({
                            'suggestion': 'Over 2.5 Goals',
                            'confidence': round(over_pct, 1),
                            'source': 'scores',
                            'details': {'count': over_count, 'total': total_scores}
                        })
                    elif under_pct >= threshold_pct:
                        suggestions.append({
                            'suggestion': 'Under 2.5 Goals',
                            'confidence': round(under_pct, 1),
                            'source': 'scores',
                            'details': {'count': under_count, 'total': total_scores}
                        })

        except Exception:
            pass

        # Merge duplicate suggestions across sources but preserve provenance.
        merged: Dict[str, Dict[str, Any]] = {}
        for s in suggestions:
            key = s['suggestion']
            if key not in merged:
                # start a merged entry with evidence list
                merged[key] = {
                    'suggestion': key,
                    'confidence': s.get('confidence', 0.0),
                    'evidence': [
                        {
                            'source': s.get('source'),
                            'confidence': s.get('confidence', 0.0),
                            'details': s.get('details', {})
                        }
                    ]
                }
            else:
                # append evidence and update confidence to max
                merged[key]['evidence'].append({
                    'source': s.get('source'),
                    'confidence': s.get('confidence', 0.0),
                    'details': s.get('details', {})
                })
                merged[key]['confidence'] = max(merged[key]['confidence'], s.get('confidence', 0.0))

        # convert merged map to list; compute evidence_count as the sum of
        # per-evidence 'details.count' when available (this represents
        # aggregated support within a single evidence entry, e.g. multiple
        # score-model votes), otherwise fall back to the number of evidence
        # items. This prevents evidence_count from always being 1 when a
        # single source bundles multiple supporting votes in details.count.
        results = []
        for k, v in merged.items():
            ev = v.get('evidence', []) or []
            # try to sum 'details.count' across evidence entries when present
            try:
                cnts = [int(e.get('details', {}).get('count')) for e in ev if isinstance(e.get('details', {}), dict) and e.get('details', {}).get('count') is not None]
                if cnts:
                    evidence_count = sum(cnts)
                else:
                    evidence_count = len(ev)
            except Exception:
                evidence_count = len(ev)

            v['evidence_count'] = evidence_count
            results.append(v)

        # sort results by evidence_count desc then confidence desc
        results = sorted(results, key=lambda x: (x['evidence_count'], x['confidence']), reverse=True)

        return results

    def value(self, match, suggestions: List[Dict[str, Any]] = None, discrepancy: Dict[str, Any] = None) -> Dict[str, Any]:
        """Return an overall value indicator (0-100) and breakdown.

        Uses number of tip sources, top suggestion confidence, probability strength and number of score predictions.
        """
        # New value formula per request:
        # value = number_of_unique_sources + average(max(confidence(tips per unique source)))
        preds = getattr(match, 'predictions', None)

        # Safely collect tips
        tips = []
        try:
            tips = preds.tips if preds and getattr(preds, 'tips', None) else []
        except Exception:
            tips = []

        # New formula: prefer the tip that has the most sources agreeing on it.
        # - unique_sources: number of distinct tip sources overall (as before)
        # - find the most-agreed tip (group by tip.to_text()) and compute the
        #   average confidence for that tip across sources
        # - add bonus points of 0.5 per source that agrees on that same tip
        # - scale the avg confidence into the same units as unique_sources
        #   (avg_conf/100 * unique_sources) to keep contributions comparable

        # map of source -> max confidence per source (used to count unique sources)
        max_conf_by_source: Dict[str, float] = {}
        for t in tips:
            src = getattr(t, 'source', None)
            if not src:
                continue
            try:
                conf = float(getattr(t, 'confidence', 0.0) or 0.0)
            except Exception:
                conf = 0.0
            prev = max_conf_by_source.get(src)
            if prev is None or conf > prev:
                max_conf_by_source[src] = conf

        unique_sources = len(max_conf_by_source)

        # Group tips by normalized text and gather per-group confidences and sources
        groups: Dict[str, Dict[str, Any]] = {}
        for t in tips:
            try:
                if hasattr(t, 'to_text') and callable(getattr(t, 'to_text')):
                    key = t.to_text()
                else:
                    key = str(getattr(t, 'raw_text', '') or '')
            except Exception:
                key = str(getattr(t, 'raw_text', '') or '')

            if key not in groups:
                groups[key] = {'confs': [], 'sources': set()}
            try:
                conf = float(getattr(t, 'confidence', 0.0) or 0.0)
            except Exception:
                conf = 0.0
            src = getattr(t, 'source', None)
            groups[key]['confs'].append(conf)
            if src:
                groups[key]['sources'].add(src)

        # Find the group with the most distinct sources; tie-breaker = higher avg conf
        best_key = None
        best_sources_count = 0
        best_avg_conf = 0.0
        for k, v in groups.items():
            scount = len(v['sources'])
            avgc = (sum(v['confs']) / len(v['confs'])) if v['confs'] else 0.0
            if scount > best_sources_count or (scount == best_sources_count and avgc > best_avg_conf):
                best_key = k
                best_sources_count = scount
                best_avg_conf = avgc

        # Scale average confidence contribution into same scale as unique_sources
        avg_conf_contrib = 0.0
        if unique_sources > 0 and best_key is not None:
            avg_conf_contrib = (best_avg_conf / 100.0) * unique_sources

        # Bonus points per agreeing source on the top-agreed tip
        bonus_per_source = 0.5
        bonus = bonus_per_source * best_sources_count

        # Base value: number of unique sources + scaled avg confidence for the
        # most-agreed tip + bonus for number of agreeing sources
        value_score = unique_sources + avg_conf_contrib + bonus

        # Optionally add normalized top suggestion confidence (0..unique_sources)
        try:
            if suggestions:
                top_conf = 0.0
                for s in suggestions:
                    try:
                        c = float(s.get('confidence', 0.0) or 0.0)
                    except Exception:
                        c = 0.0
                    if c > top_conf:
                        top_conf = c
                norm_top = (top_conf / 100.0) * unique_sources if unique_sources > 0 else 0.0
                value_score += norm_top
        except Exception:
            pass

        return {
            'score': round(value_score, 2),
            'breakdown': {
                'unique_sources': unique_sources,
                'most_agreed_tip': best_key,
                'agreeing_sources_on_top_tip': best_sources_count,
                'avg_confidence_on_top_tip': round(best_avg_conf, 3),
                'avg_conf_contrib': round(avg_conf_contrib, 3),
                'bonus_for_agreement': round(bonus, 3),
                'raw_value': round(value_score, 3)
            }
        }
