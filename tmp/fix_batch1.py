import io

P = "/a0/usr/projects/bet_assistant/bet_dashboard/backend/core/logic.py"
src = io.open(P, encoding="utf-8").read()
orig = src

def rep(old, new, tag):
    global src
    assert src.count(old) == 1, f"{tag}: count={src.count(old)}"
    src = src.replace(old, new)

# 1. claim lock in __init__
rep(
    "        # Initialize services\n        svc_cfg = self._settings.get(\"services\") or {}",
    "        # Serializes the check-generate-claim sequence (ticker vs manual button)\n        self._claim_lock = RLock()\n\n        # Initialize services\n        svc_cfg = self._settings.get(\"services\") or {}",
    "init-lock",
)

# 2. helpers after _order_sort_key
rep(
    "    except (TypeError, ValueError):\n        return (1, 0.0)\n\n\ndef _units_std",
    '''    except (TypeError, ValueError):
        return (1, 0.0)


def _safe_int(value: Any) -> int | None:
    """Coerce to int, returning None on failure — never raises.

    Hand-edited profile YAML can hold \"abc\"/2.5 next to an int; a ValueError
    here would kill the generator daemon thread (review F4/H2 class).
    """
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_zoneinfo(tz_name: Any) -> ZoneInfo:
    """ZoneInfo with UTC fallback — a config typo must not kill the daemon (M6)."""
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _units_std''',
    "helpers",
)

# 3. _profile_is_active safe coercion
rep(
    '    if cfg.get("auto_generate") is False:\n        return False\n    return bool(cfg.get("auto_generate") or int(cfg.get("run_daily_count") or 0) > 0)',
    '''    auto = cfg.get("auto_generate")
    if isinstance(auto, str) and auto.strip().lower() in ("false", "off", "no", "0"):
        return False
    if auto is False or auto is None:
        if auto is False:
            return False
        count = _safe_int(cfg.get("run_daily_count"))
        return count is not None and count > 0
    return True''',
    "profile-is-active",
)

# 4. _do_generate except-handler guarded (daemon survival)
rep(
    '''        except Exception as exc:
            print(f"[Generator] ERROR: {exc}")
            # Mark failing due profiles — status only, no separate stamp map
            due = {name: None for name in (self._get_active_profiles() or {}) if self._is_profile_due(name)}
            if due:
                self._claim_profile_runs(due, status="failed", error=str(exc))''',
    '''        except Exception as exc:
            print(f"[Generator] ERROR: {exc}")
            # Mark failing due profiles — status only. Guarded so a raise here
            # cannot take down the ticker daemon thread (review H3).
            try:
                due = {name: None for name in (self._get_active_profiles() or {}) if self._is_profile_due(name)}
                if due:
                    self._claim_profile_runs(due, status="failed", error=str(exc))
            except Exception as exc2:
                print(f"[Generator] failure-marking ERROR: {exc2}")''',
    "do-generate-except",
)

# 5. _local_tz fallback
rep(
    '        tz_name = (self._settings.get("scraper_config") or {}).get("local_timezone", "Europe/Bucharest")
        return ZoneInfo(tz_name)',
    '        tz_name = (self._settings.get("scraper_config") or {}).get("local_timezone", "Europe/Bucharest")
        return _safe_zoneinfo(tz_name)',
    "local-tz",
)

# 6. _profile_schedule_met safe int
rep(
    '''        target = now.replace(
            hour=int(hour),
            minute=int(minute or 0),
            second=0,
            microsecond=0,
        )''',
    '''        hour_i, minute_i = _safe_int(hour), _safe_int(minute)
        if hour_i is None or minute_i is None or not (0 <= hour_i <= 23 and 0 <= minute_i <= 59):
            return False
        target = now.replace(
            hour=hour_i,
            minute=minute_i,
            second=0,
            microsecond=0,
        )''',
    "schedule-met-int",
)

# 7. _last_run_local_date: only ok status gates the day + broader catch + naive tz
rep(
    '''        runtime = self._settings.get("runtime_state") or {}
        entry = (runtime.get("profile_last_run") or {}).get(name) or {}
        at = entry.get("at")
        if not at:
            return None
        try:
            return datetime.fromisoformat(str(at)).astimezone(self._local_tz()).strftime("%Y-%m-%d")
        except ValueError:
            return None''',
    '''        runtime = self._settings.get("runtime_state") or {}
        entry = (runtime.get("profile_last_run") or {}).get(name) or {}
        # Only a SUCCESSFUL run consumes the once-per-day guard; a failed run
        # records status for the Services table but must not block a retry
        # until midnight (review B1).
        if entry.get("status") != "ok":
            return None
        at = entry.get("at")
        if not at:
            return None
        try:
            dt = datetime.fromisoformat(str(at))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt.astimezone(self._local_tz()).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None''',
    "last-run-date",
)

# 8. _profile_next_run safe int
rep(
    '''        if hour is None or minute is None:
            return None
        first = local_now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)''',
    '''        if hour is None or minute is None:
            return None
        hour_i, minute_i = _safe_int(hour), _safe_int(minute)
        if hour_i is None or minute_i is None or not (0 <= hour_i <= 23 and 0 <= minute_i <= 59):
            return None
        first = local_now.replace(hour=hour_i, minute=minute_i, second=0, microsecond=0)''',
    "next-run-int",
)

# 9. save_profile_schedules: empty-cfg never overwrites; None never overwrites scheduling keys
rep(
    '''            cfg = dict(self._profile_cfg(name))
            if not cfg and name not in (self._settings.get("profiles") or {}):
                continue
            cfg.update(
                {
                    k: row[k]
                    for k in (
                        "auto_generate",
                        "generate_hour",
                        "generate_minute",
                        "run_daily_count",
                        "order",
                    )
                    if k in row
                }
            )''',
    '''            cfg = dict(self._profile_cfg(name))
            # A profile whose stored YAML is empty (parse failure / hand-edit)
            # must never be rewritten from schedule keys alone — that wipes
            # every BetSlipConfig field (review H1).
            if not cfg:
                continue
            # None means "not provided": it must not clear a persisted value,
            # matching the tri-state contract used for stake fields (review M8).
            cfg.update(
                {
                    k: row[k]
                    for k in (
                        "auto_generate",
                        "generate_hour",
                        "generate_minute",
                        "run_daily_count",
                        "order",
                    )
                    if k in row and row[k] is not None
                }
            )''',
    "save-schedules-guard",
)

# 10. _claim_profile_runs under claim lock
rep(
    '''        iso_now = datetime.now().astimezone(ZoneInfo("UTC")).isoformat()
        runtime = self._settings.get("runtime_state") or {}
        runs = runtime.get("profile_last_run") or {}
        for name in profiles:
            runs[name] = {"at": iso_now, "status": status, "error": error}
        runtime["profile_last_run"] = runs
        # Drop superseded keys — no legacy fallback.
        for legacy_key in ("profile_last_generated", "profile_last_generated_at", "profile_run_status", "last_time_generated"):
            runtime.pop(legacy_key, None)
        self._settings.write("runtime_state", runtime)''',
    '''        iso_now = datetime.now().astimezone(ZoneInfo("UTC")).isoformat()
        # The whole read-modify-write must be one critical section: the RLock
        # inside get/write only serializes individual ops, so a concurrent
        # ticker + manual Generate could otherwise drop a claim (review H7/H5).
        with self._claim_lock:
            runtime = self._settings.get("runtime_state") or {}
            runs = runtime.get("profile_last_run") or {}
            for name in profiles:
                runs[name] = {"at": iso_now, "status": status, "error": error}
            runtime["profile_last_run"] = runs
            # Drop superseded keys — no legacy fallback.
            for legacy_key in ("profile_last_generated", "profile_last_generated_at", "profile_run_status", "last_time_generated"):
                runtime.pop(legacy_key, None)
            self._settings.write("runtime_state", runtime)''',
    "claim-lock",
)

# 11. generate_and_broadcast: manual button must not claim guards for not-yet-due profiles (B2)
rep(
    '''        profiles = self._get_active_profiles()
        result: dict = {}
        try:
            if profiles:
                result = self.generate_slips(profiles)
                self._claim_profile_runs(profiles, status="ok")
            self._broadcast_slips_updated()
            return result
        except Exception as exc:
            print(f"[Generator] manual ERROR: {exc}")
            self._claim_profile_runs(profiles, status="failed", error=str(exc))
            self._broadcast_slips_updated()
            raise''',
    '''        profiles = self._get_active_profiles()
        # Only profiles whose window is actually due get generated/claimed;
        # claiming every active profile would consume tomorrow\'s guard today
        # for not-yet-due profiles (review B2).
        due = {name: tup for name, tup in profiles.items() if self._is_profile_due(name)}
        result: dict = {}
        try:
            if due:
                result = self.generate_slips(due)
                self._claim_profile_runs(due, status="ok")
            self._broadcast_slips_updated()
            return result
        except Exception as exc:
            print(f"[Generator] manual ERROR: {exc}")
            if due:
                self._claim_profile_runs(due, status="failed", error=str(exc))
            self._broadcast_slips_updated()
            raise''',
    "generate-and-broadcast",
)

io.open(P, "w", encoding="utf-8").write(src)
print(f"APPLIED {len(src)-len(orig)} bytes delta, all 11 assertions passed")
