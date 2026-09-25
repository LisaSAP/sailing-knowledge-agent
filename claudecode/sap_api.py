"""SAP Sailing API wrappers — see sailing-sap-api.md for full context."""
import os
import httpx

_MAIN_BASE = "https://www.sapsailing.com/sailingserver/api/v1"
_API_PATH = "/sailingserver/api/v1"

# Key: substring in regatta name; value: subdomain base URL.
_SUBDOMAIN_MAP: dict[str, str] = {
    "Austrian Sailing League 2026": "https://austrianleague2026.sapsailing.com",
    "Polish Sailing League 2026":   "https://plz2026.sapsailing.com",
    "TLZ2026":                      "https://tlz2026.sapsailing.com",
    "Warsaw Sailing League 2026":   "https://wlz2026.sapsailing.com",
    "ZYC":                          "https://zyc.sapsailing.com",
    "Youth Polish Sailing League":  "https://yplz2026.sapsailing.com",
    "LYC":                          "https://lyc.sapsailing.com",
    "VSaW":                         "https://vsaw.sapsailing.com",
    "CLZ2026":                      "https://clz2026.sapsailing.com",
    "flr2026":                      "https://flr2026.sapsailing.com",
    "Peter Wagner":                 "https://peterwagner.sapsailing.com",
    "WLZ26":                        "https://wlz26.sapsailing.com",
    "CNR2026":                      "https://cnr2026.sapsailing.com",
}


def resolve_base_url(regatta: str) -> str:
    for key, subdomain in _SUBDOMAIN_MAP.items():
        if key in regatta:
            return subdomain + _API_PATH
    return _MAIN_BASE


def _load_auth() -> tuple[str, str] | None:
    user = os.environ.get("SAP_SAILING_USERNAME")
    pw = os.environ.get("SAP_SAILING_PASSWORD")
    return (user, pw) if user and pw else None


def _get(
    base_url: str,
    path: str,
    params: dict | list = None,
    auth: tuple[str, str] | None = None,
    timeout: int = 30,
) -> dict | list:
    # params may be a list of (key, value) tuples to support repeated keys
    r = httpx.get(f"{base_url}{path}", params=params, auth=auth, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ── Events ────────────────────────────────────────────────────────────────────

def get_events(base_url: str = None) -> list[dict]:
    base = base_url or _MAIN_BASE
    return _get(base, "/events")


def get_event(event_id: str, base_url: str = None) -> dict:
    base = base_url or _MAIN_BASE
    return _get(base, f"/events/{event_id}")


def get_event_racestates(event_id: str, base_url: str = None) -> list[dict]:
    base = base_url or _MAIN_BASE
    return _get(base, f"/events/{event_id}/racestates")


# ── Regattas ──────────────────────────────────────────────────────────────────

def search_regattas(query: str) -> list[dict]:
    seen: set[str] = set()
    results: list[dict] = []
    bases_to_search = [_MAIN_BASE] + [s + _API_PATH for s in _SUBDOMAIN_MAP.values()]
    for base in bases_to_search:
        try:
            data = _get(base, "/regattas")
            for r in data:
                name = r.get("name", "")
                if query.lower() in name.lower() and name not in seen:
                    seen.add(name)
                    results.append(r)
        except Exception:
            pass
    return results


def get_regatta(regatta: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}")


def get_race_list(regatta: str) -> list[dict]:
    base = resolve_base_url(regatta)
    result = _get(base, f"/regattas/{regatta}/races")
    if isinstance(result, list):
        return result
    if "races" in result:
        return result["races"]
    raise ValueError(f"Unexpected response shape from /races: {list(result.keys())}")


def get_regatta_entries(regatta: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/entries")


def get_race_entries(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/entries")


def get_regatta_competitors(regatta: str) -> list[dict]:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/competitors")


def get_wind_summary(regatta: str) -> list[dict]:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/windsummary")


# ── Race-level ────────────────────────────────────────────────────────────────

def get_race_standings(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/competitors/live")


def get_competitor_legs(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/competitors/legs")


def get_leg_times(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/times")


def get_mark_passings(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/markpassings")


def get_course(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/course")


def get_first_leg_bearing(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/firstlegbearing")


def get_target_time(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/targettime")


def get_start_analysis(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/startanalysis")


def get_maneuvers(regatta: str, race: str) -> dict:
    base = resolve_base_url(regatta)
    return _get(base, f"/regattas/{regatta}/races/{race}/maneuvers")


# ── Competitor data (time-series) ─────────────────────────────────────────────

def get_competitor_data(
    regatta: str,
    race: str,
    competitor_ids: list[str],
    leaderboard_group_id: str,
    from_ms: int,
    to_ms: int,
    detail_types: tuple[str, ...] = (),
    step_ms: int = 1000,
    timeout: int = 60,
) -> dict | str:
    base = resolve_base_url(regatta)
    params = []
    for cid in competitor_ids:
        params.append(("competitorId", cid))
    for dt in detail_types:
        params.append(("detailType", dt))
    params += [
        ("leaderboardName", regatta),
        ("leaderboardGroupNameOrUUID", leaderboard_group_id),
        ("fromtimeasmillis", from_ms),
        ("totimeasmillis", to_ms),
        ("steptimeasmillis", step_ms),
    ]
    try:
        return _get(base, f"/regattas/{regatta}/races/{race}/competitordata", params=params, auth=_load_auth(), timeout=timeout)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            return "Competitor data requires account credentials — not available without auth."
        raise


# ── Datamining ────────────────────────────────────────────────────────────────

def get_datamining_queries(base_url: str = None) -> list[dict]:
    base = base_url or _MAIN_BASE
    return _get(base, "/regattas/datamining")


def run_datamining_query(regatta: str, query_identifier: str, race: str = None) -> dict | str:
    base = resolve_base_url(regatta)
    if race:
        path = f"/regattas/{regatta}/races/{race}/datamining/{query_identifier}"
    else:
        path = f"/regattas/{regatta}/datamining/{query_identifier}"
    try:
        return _get(base, path, auth=_load_auth())
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            return f"Query '{query_identifier}' requires TRACKED_RACE:EXPORT permission."
        raise


# ── Leaderboards ──────────────────────────────────────────────────────────────

def list_leaderboard_groups(base_url: str = None) -> list[str]:
    base = base_url or _MAIN_BASE
    return _get(base, "/leaderboardgroups")


def get_leaderboard_group(name: str, base_url: str = None) -> dict:
    base = base_url or _MAIN_BASE
    return _get(base, f"/leaderboardgroups/{name}")


def list_leaderboards(base_url: str = None) -> list[str]:
    base = base_url or _MAIN_BASE
    return _get(base, "/leaderboards")


def get_leaderboard(name: str, base_url: str = None) -> dict:
    base = base_url or resolve_base_url(name)
    try:
        return _get(base, f"/leaderboards/{name}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404 and base != _MAIN_BASE:
            return _get(_MAIN_BASE, f"/leaderboards/{name}")
        raise


def get_leaderboard_competitor(leaderboard_name: str, competitor_id: str, base_url: str = None) -> dict:
    base = base_url or resolve_base_url(leaderboard_name)
    return _get(base, f"/leaderboards/{leaderboard_name}/competitors/{competitor_id}")


def get_leaderboard_marks(leaderboard_name: str, base_url: str = None) -> list[dict]:
    base = base_url or resolve_base_url(leaderboard_name)
    return _get(base, f"/leaderboards/{leaderboard_name}/marks")


def get_leaderboard_mark(leaderboard_name: str, mark_id: str, base_url: str = None) -> dict:
    base = base_url or resolve_base_url(leaderboard_name)
    return _get(base, f"/leaderboards/{leaderboard_name}/marks/{mark_id}")


def get_leaderboard_start_order(leaderboard_name: str, base_url: str = None) -> dict:
    base = base_url or resolve_base_url(leaderboard_name)
    return _get(base, f"/leaderboards/{leaderboard_name}/startorder")


# ── Competitors ───────────────────────────────────────────────────────────────

def get_competitor(competitor_id: str, base_url: str = None) -> dict:
    base = base_url or _MAIN_BASE
    return _get(base, f"/competitors/{competitor_id}")


def get_competitor_team(competitor_id: str, base_url: str = None) -> dict:
    base = base_url or _MAIN_BASE
    return _get(base, f"/competitors/{competitor_id}/team")


# ── Wind (requires TRACKED_RACE:EXPORT) ───────────────────────────────────────

def get_wind_data(regatta: str, race: str) -> dict | str:
    try:
        times = get_leg_times(regatta, race)
        from_ms = times.get("startOfRace-ms")
        to_ms = times.get("endOfRace-ms")
        if from_ms is None or to_ms is None:
            return "Wind data unavailable: race timing not found."
        base = resolve_base_url(regatta)
        return _get(base, f"/regattas/{regatta}/races/{race}/wind",
                    params={"fromtimeasmillis": from_ms, "totimeasmillis": to_ms},
                    auth=_load_auth())
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            return "Wind data requires TRACKED_RACE:EXPORT permission."
        raise


# ── Reference / lookup ────────────────────────────────────────────────────────

def get_boat_classes(base_url: str = None) -> list[dict]:
    base = base_url or _MAIN_BASE
    return _get(base, "/boatclasses")


def get_country_codes(base_url: str = None) -> list[dict]:
    base = base_url or _MAIN_BASE
    return _get(base, "/countrycodes")


def get_tracked_races_all(base_url: str = None) -> list[dict]:
    base = base_url or _MAIN_BASE
    return _get(base, "/trackedRaces/allRaces")


def get_tracked_races_recent(base_url: str = None) -> list[dict]:
    base = base_url or _MAIN_BASE
    return _get(base, "/trackedRaces/getRaces")


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_competitor_id(regatta: str, name_fragment: str) -> str | None:
    fragment = name_fragment.lower()
    entries = get_regatta_entries(regatta)
    for c in entries.get("competitors", []):
        if fragment in c.get("name", "").lower():
            return c.get("id")
    return None


def get_leg_wind(regatta: str, race: str, leg_index: int) -> dict:
    legs = get_target_time(regatta, race).get("legs", [])
    if not 0 <= leg_index < len(legs):
        raise IndexError(f"leg_index {leg_index} out of range — race has {len(legs)} legs")
    leg = legs[leg_index]
    wind = leg.get("legWind", {})
    return {
        "direction_deg": wind.get("direction"),
        "speed_kts": wind.get("speedinknots"),
        "leg_type": leg.get("legType"),
        "bearing_deg": leg.get("legBearingDegrees"),
    }


def get_maneuvers_in_window(
    regatta: str,
    race: str,
    competitor_id: str,
    from_ms: int,
    to_ms: int,
    types: list[str] | None = None,
) -> list[dict]:
    all_maneuvers = get_maneuvers(regatta, race)
    entry = next(
        (e for e in all_maneuvers.get("bycompetitor", [])
         if e.get("competitor") == competitor_id),
        None,
    )
    if entry is None:
        return []
    upper = {t.upper() for t in types} if types else None
    result = []
    for m in entry.get("maneuvers", []):
        ts = m.get("positionAndTime", {}).get("unixtime", 0)
        if from_ms <= ts <= to_ms:
            if upper is None or m.get("maneuverType", "").upper() in upper:
                result.append(m)
    return result


def find_competitor_by_sail(regatta: str, sail_fragment: str) -> list[dict]:
    fragment = sail_fragment.lower()
    entries = get_regatta_entries(regatta)
    return [
        c for c in entries.get("competitors", [])
        if fragment in c.get("sailID", "").lower()
    ]


def get_competitor_leg_stats(regatta: str, race: str, competitor_id: str) -> list[dict]:
    data = get_competitor_legs(regatta, race)
    result = []
    for leg in data.get("legs", []):
        for c in leg.get("competitors", []):
            if c.get("id") == competitor_id:
                entry = {k: v for k, v in leg.items() if k != "competitors"}
                entry.update(c)
                result.append(entry)
                break
    return result


def get_leaderboard_group_id(regatta: str) -> str | None:
    group = get_leaderboard_group(regatta)
    if isinstance(group, dict):
        return group.get("id")
    return None


def get_competitor_mark_passings(regatta: str, race: str, competitor_id: str) -> list[dict]:
    data = get_mark_passings(regatta, race)
    for entry in data.get("bycompetitor", []):
        cid = entry.get("competitor", {}).get("id")
        if cid == competitor_id:
            return entry.get("markpassings", [])
    return []


def get_fleet_state_at_time(regatta: str, race: str, timestamp_ms: int) -> list[dict]:
    standings = get_race_standings(regatta, race)
    id_to_name = {c["id"]: c["name"] for c in standings.get("competitors", [])}
    all_maneuvers = get_maneuvers(regatta, race)

    result = []
    for entry in all_maneuvers.get("bycompetitor", []):
        comp_id = entry.get("competitor", "")
        name = id_to_name.get(comp_id, comp_id)
        mlist = entry.get("maneuvers", [])

        last = None
        for m in mlist:
            if m.get("positionAndTime", {}).get("unixtime", 0) <= timestamp_ms:
                last = m

        if last is not None:
            pat = last.get("positionAndTime", {})
            ts = pat.get("unixtime")
            result.append({
                "id": comp_id,
                "name": name,
                "tack": last.get("newTack", "UNKNOWN"),
                "heading_deg": last.get("cogAfterInTrueDegrees"),
                "lat_deg": pat.get("lat_deg"),
                "lon_deg": pat.get("lon_deg"),
                "seconds_since_last_maneuver": (timestamp_ms - ts) // 1000 if ts else None,
                "last_maneuver_type": last.get("maneuverType"),
                "last_maneuver_time_ms": ts,
            })
        elif mlist:
            # No maneuver before timestamp — infer original tack from first maneuver's COG
            first = mlist[0]
            result.append({
                "id": comp_id,
                "name": name,
                "tack": "UNKNOWN",
                "heading_deg": first.get("cogBeforeInTrueDegrees"),
                "lat_deg": None,
                "lon_deg": None,
                "seconds_since_last_maneuver": None,
                "last_maneuver_type": None,
                "last_maneuver_time_ms": None,
            })
        else:
            result.append({
                "id": comp_id,
                "name": name,
                "tack": "UNKNOWN",
                "heading_deg": None,
                "lat_deg": None,
                "lon_deg": None,
                "seconds_since_last_maneuver": None,
                "last_maneuver_type": None,
                "last_maneuver_time_ms": None,
            })

    return result


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    def _coerce(value: str):
        if value.startswith(("[", "{")):
            return json.loads(value)
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            return int(value)
        try:
            return float(value)
        except ValueError:
            pass
        if value.lower() in ("none", "null"):
            return None
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        return value

    if len(sys.argv) < 2:
        print("Usage: python3 sap_api.py <function_name> [arg1 arg2 ...]")
        print("\nAvailable functions:")
        import inspect
        fns = [
            name for name, obj in inspect.getmembers(sys.modules[__name__])
            if inspect.isfunction(obj) and not name.startswith("_")
        ]
        for fn in sorted(fns):
            print(f"  {fn}")
        sys.exit(1)

    fn_name = sys.argv[1]
    args = [_coerce(a) for a in sys.argv[2:]]

    fn = globals().get(fn_name)
    if fn is None or not callable(fn):
        print(f"Error: '{fn_name}' is not a known function.", file=sys.stderr)
        sys.exit(1)

    try:
        result = fn(*args)
        print(json.dumps(result, indent=2, default=str))
    except TypeError as e:
        print(f"Error: {e}", file=sys.stderr)
        import inspect
        sig = inspect.signature(fn)
        print(f"Signature: {fn_name}{sig}", file=sys.stderr)
        sys.exit(1)
