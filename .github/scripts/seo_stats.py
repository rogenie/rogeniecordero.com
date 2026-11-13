"""
seo_stats.py - daily search and visitor numbers for the 9nth Dimension SEO dashboard.

Reads Google Search Console (keywords, ranking pages, devices from search) and
Google Analytics 4 (devices, where visitors came from, landing pages) for
9nthdimension.com and writes 9nthdimension/seo/stats.json, which the dashboard
at rogeniecordero.com/9nthdimension/seo loads. Read-only: it never changes
anything in Search Console or Analytics.

Settings (GitHub repo Settings > Secrets and variables > Actions):
  secret   GOOGLE_SERVICE_ACCOUNT_JSON  the service account's JSON key
  variable GSC_SITE                     Search Console property, e.g. sc-domain:9nthdimension.com
  variable GA4_PROPERTY_ID              the numeric GA4 property ID (not the G-... measurement ID)
Either source can be left unset; its part of the dashboard then says it isn't connected.
"""
import json, os, sys, urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "9nthdimension" / "seo" / "stats.json"
DAYS = 28
GSC_LAG = 3          # Search Console data settles after ~2-3 days
TOP = 25

SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
GSC_SITE = os.environ.get("GSC_SITE", "").strip() or "sc-domain:9nthdimension.com"
GA4_PROPERTY = os.environ.get("GA4_PROPERTY_ID", "").strip()

_session = None
def session():
    """An authorized requests session for the service account (both read-only scopes)."""
    global _session
    if _session is None:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        creds = service_account.Credentials.from_service_account_info(json.loads(SA_JSON), scopes=[
            "https://www.googleapis.com/auth/webmasters.readonly",
            "https://www.googleapis.com/auth/analytics.readonly"])
        _session = AuthorizedSession(creds)
    return _session

def post(url, body):
    r = session().post(url, json=body, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()

# ---------------- Search Console ----------------
def gsc(dimensions, start, end, limit=TOP):
    url = ("https://searchconsole.googleapis.com/webmasters/v3/sites/"
           + urllib.parse.quote(GSC_SITE, safe="") + "/searchAnalytics/query")
    data = post(url, {"startDate": start, "endDate": end, "dimensions": dimensions, "rowLimit": limit})
    rows = []
    for r in data.get("rows", []):
        row = {d: k for d, k in zip(dimensions, r.get("keys", []))}
        row.update(clicks=int(r.get("clicks", 0)), impressions=int(r.get("impressions", 0)),
                   ctr=round(float(r.get("ctr", 0)), 4), position=round(float(r.get("position", 0)), 1))
        rows.append(row)
    return rows

def search_console():
    if not SA_JSON:
        return {"connected": False, "reason": "No Google service account key is set."}
    end = date.today() - timedelta(days=GSC_LAG)
    start = end - timedelta(days=DAYS - 1)
    s, e = start.isoformat(), end.isoformat()
    try:
        total = gsc([], s, e, 1)
        return {
            "connected": True, "site": GSC_SITE, "start": s, "end": e,
            "totals": total[0] if total else {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0},
            "queries": gsc(["query"], s, e),
            "pages": gsc(["page"], s, e),
            "devices": gsc(["device"], s, e, 10),
            "countries": gsc(["country"], s, e, 10),
            "daily": sorted(gsc(["date"], s, e, 100), key=lambda r: r["date"]),
        }
    except Exception as ex:
        return {"connected": False, "reason": f"Search Console request failed: {ex}"}

# ---------------- Google Analytics 4 ----------------
def ga(dimensions, metrics, limit=TOP, order_metric=None):
    body = {"dateRanges": [{"startDate": f"{DAYS}daysAgo", "endDate": "yesterday"}],
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics], "limit": limit}
    if dimensions:
        body["orderBys"] = [{"metric": {"metricName": order_metric or metrics[0]}, "desc": True}]
    data = post(f"https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY}:runReport", body)
    rows = []
    for r in data.get("rows", []):
        row = {d: v.get("value") for d, v in zip(dimensions, r.get("dimensionValues", []))}
        for m, v in zip(metrics, r.get("metricValues", [])):
            x = float(v.get("value") or 0)
            row[m] = int(x) if x.is_integer() else round(x, 4)
        rows.append(row)
    return rows

def analytics():
    if not (SA_JSON and GA4_PROPERTY):
        return {"connected": False, "reason": "No Google Analytics property ID or service account key is set."}
    try:
        total = ga([], ["sessions", "activeUsers", "screenPageViews", "engagementRate"], 1)
        return {
            "connected": True, "days": DAYS,
            "totals": total[0] if total else {},
            "devices": ga(["deviceCategory"], ["sessions", "activeUsers"], 10),
            "sources": ga(["sessionSource", "sessionMedium"], ["sessions", "activeUsers"], TOP),
            "landingPages": ga(["landingPagePlusQueryString"], ["sessions"], TOP),
            "countries": ga(["country"], ["activeUsers"], 10),
        }
    except Exception as ex:
        return {"connected": False, "reason": f"Google Analytics request failed: {ex}"}

def main():
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "searchConsole": search_console(), "analytics": analytics()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for k in ("searchConsole", "analytics"):
        print(f"{k}: {'connected' if out[k]['connected'] else out[k]['reason']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
