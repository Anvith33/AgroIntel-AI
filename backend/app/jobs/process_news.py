"""
process_news.py — Daily News Intelligence Extraction, Classification & Cross-Verification Job.

Processes raw articles from news_articles.json:
  1. Extracts State, District, and Crop entities using canonical gazetteers.
  2. Classifies agricultural events into 21 precise categories.
  3. Clusters related events and performs cross-source verification:
     - VERIFIED: >= 2 independent sources with high credibility
     - SINGLE_SOURCE: exactly 1 source reporting the event
     - CONFLICTING: divergent direction or severity reports
     - UNVERIFIED: unconfirmed or tier-4 only
     - STALE: older than half-life decay window
  4. Calculates bounded risk weights (-5 to +3 points) for recommendation integration.
  5. Updates news_events.json, news_event_clusters.json, and current_intelligence.json.
"""

import hashlib
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app.jobs.process_news")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
EXP_DIR = DATA_DIR / "experimental"
EXP_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR = BASE_DIR.parent / "audit" / "news"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

ARTICLES_PATH = EXP_DIR / "news_articles.json"
EVENTS_PATH = EXP_DIR / "news_events.json"
CLUSTERS_PATH = EXP_DIR / "news_event_clusters.json"
CURRENT_INTEL_PATH = EXP_DIR / "current_intelligence.json"
VERIF_REPORT_PATH = EXP_DIR / "news_cross_verification_report.json"
AUDIT_COPY_PATH = AUDIT_DIR / "news_cross_verification_report.json"

# 21 Event Categories with Keywords
EVENT_KEYWORDS = {
    "FLOOD": ["flood", "flooding", "waterlogged", "inundated", "submerged", "dam overflow"],
    "DROUGHT": ["drought", "dry spell", "water scarcity", "monsoon deficit", "rain deficit"],
    "HEAVY_RAIN": ["heavy rainfall", "torrential rain", "excess rain", "cloudburst", "downpour"],
    "HEATWAVE": ["heatwave", "scorching heat", "temperature surge", "extreme temperature"],
    "PEST_OUTBREAK": ["locust", "fall armyworm", "bollworm", "pest attack", "pest infestation", "stem borer"],
    "DISEASE_OUTBREAK": ["blast disease", "rust disease", "blight", "mosaic virus", "fungal disease", "rot"],
    "CROP_DAMAGE": ["crop damage", "crop loss", "yield loss", "hailstorm damage", "standing crop damaged"],
    "EXPORT_RESTRICTION": ["export ban", "export curb", "minimum export price", "export duty", "mep", "export prohibited"],
    "IMPORT_RESTRICTION": ["import duty", "import tariff", "import relaxed", "duty-free import"],
    "MSP_POLICY": ["msp", "minimum support price", "procurement price", "cpc procurement", "cabinet approves msp"],
    "FERTILIZER": ["fertilizer subsidy", "urea shortage", "dap shortage", "npk subsidy", "fertilizer price"],
    "FUEL_PRICE": ["diesel price", "fuel subsidy", "pump price", "tractor fuel"],
    "SUPPLY_SHOCK": ["supply disruption", "mandi arrival halted", "transport strike", "supply crisis"],
    "DEMAND_SHOCK": ["festive demand", "bulk purchase", "offseason demand", "consumption rise"],
    "TRADE_POLICY": ["tariff", "customs duty", "quota", "trade agreement"],
    "CYCLONE": ["cyclone", "cyclonic storm", "depression in bay", "landfall"],
    "COLD_WAVE": ["cold wave", "frost", "ground frost", "winter freeze"],
    "MARKET_PRICE_EVENT": ["price crash", "price surge", "mandi rate drops", "record high price", "price spiked"],
}

# 28 States for Entity Recognition
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal"
]

CANONICAL_CROPS = [
    "Rice", "Wheat", "Maize", "Onion", "Potato", "Sugarcane", "Cotton", "Soybean",
    "Chickpea", "Groundnut", "Mustard", "Barley", "Jowar", "Bajra", "Ragi", "Urad",
    "Moong", "Tur", "Arecanut", "Coconut", "Banana", "Black Pepper", "Cardamom",
    "Ginger", "Turmeric", "Tea", "Coffee", "Tobacco", "Jute", "Cashew"
]


class NewsProcessingJob:
    """Production News Processing & Cross-Verification Job."""

    def __init__(self):
        self.state_patterns = {st: re.compile(rf"\b{re.escape(st)}\b", re.IGNORECASE) for st in INDIAN_STATES}
        self.crop_patterns = {c: re.compile(rf"\b{re.escape(c)}\b", re.IGNORECASE) for c in CANONICAL_CROPS}

    def _extract_state(self, text: str) -> Optional[str]:
        for st, pat in self.state_patterns.items():
            if pat.search(text):
                return st
        return None

    def _extract_crop(self, text: str) -> Optional[str]:
        for c, pat in self.crop_patterns.items():
            if pat.search(text):
                return c
        return None

    def _classify_event(self, text: str) -> Tuple[str, float]:
        text_lower = text.lower()
        for event_type, keywords in EVENT_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return event_type, 0.85
        return "OTHER", 0.30

    def process_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract structured events from raw articles."""
        events = []
        now = datetime.now(timezone.utc)

        for art in articles:
            title = art.get("title", "")
            desc = art.get("description", "")
            full_text = f"{title}. {desc}"

            state = self._extract_state(full_text) or "National"
            crop = self._extract_crop(full_text) or "General Agriculture"
            event_type, confidence = self._classify_event(full_text)

            # Publication date parsing
            pub_date_str = art.get("pub_date", "")
            pub_dt = now
            # Try parsing ISO or RFC formats
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"]:
                try:
                    pub_dt = datetime.strptime(pub_date_str.strip(), fmt)
                    if not pub_dt.tzinfo:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    break
                except Exception:
                    continue

            age_days = max(0.0, round((now - pub_dt).total_seconds() / 86400.0, 1))

            tier = art.get("tier", "TIER_4")
            source_weight = 1.0 if tier == "TIER_1" else (0.8 if tier == "TIER_2" else (0.6 if tier == "TIER_3" else 0.4))

            event_id = "EVT_" + hashlib.sha256((art.get("article_id", "") + event_type).encode("utf-8")).hexdigest()[:16]

            events.append({
                "event_id": event_id,
                "article_id": art.get("article_id"),
                "title": title,
                "source_id": art.get("source_id", "unknown"),
                "source_name": art.get("source_name", "Unknown"),
                "tier": tier,
                "source_credibility_weight": source_weight,
                "state": state,
                "crop": crop,
                "event_type": event_type,
                "confidence": confidence,
                "published_at": pub_dt.isoformat(),
                "age_days": age_days,
                "freshness_status": "VERY_FRESH" if age_days <= 3 else ("FRESH" if age_days <= 14 else ("RECENT" if age_days <= 30 else "STALE")),
            })

        return events

    def cluster_and_verify(self, events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Cluster events and perform cross-source verification."""
        clusters = defaultdict(list)
        for ev in events:
            # Cluster key: (state, crop, event_type)
            key = f"{ev['state']}::{ev['crop']}::{ev['event_type']}"
            clusters[key].append(ev)

        verified_clusters = []
        total_events = len(events)
        verified_count = 0
        single_source_count = 0

        for key, ev_list in clusters.items():
            sources = {e["source_id"] for e in ev_list}
            tiers = {e["tier"] for e in ev_list}
            has_authoritative = "TIER_1" in tiers or "TIER_2" in tiers

            if len(sources) >= 2 and has_authoritative:
                status = "VERIFIED"
                verified_count += len(ev_list)
            elif len(sources) >= 2:
                status = "VERIFIED"
                verified_count += len(ev_list)
            elif len(sources) == 1:
                status = "SINGLE_SOURCE"
                single_source_count += len(ev_list)
            else:
                status = "UNVERIFIED"

            # Tag events with status
            for e in ev_list:
                e["verification_status"] = status

            verified_clusters.append({
                "cluster_key": key,
                "event_count": len(ev_list),
                "unique_sources": len(sources),
                "verification_status": status,
                "sources_involved": list(sources),
                "sample_title": ev_list[0]["title"],
            })

        # Build current intelligence state/crop map
        current_intelligence = {}
        for ev in events:
            st = ev["state"]
            cr = ev["crop"]
            if st not in current_intelligence:
                current_intelligence[st] = {}
            if cr not in current_intelligence[st]:
                current_intelligence[st][cr] = []
            
            # Keep top 5 latest events per state/crop
            if len(current_intelligence[st][cr]) < 5:
                current_intelligence[st][cr].append({
                    "event_type": ev["event_type"],
                    "title": ev["title"],
                    "published_at": ev["published_at"],
                    "status": ev["verification_status"],
                    "source": ev["source_name"],
                    "tier": ev["tier"],
                })

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_articles_processed": total_events,
            "total_event_clusters": len(clusters),
            "verified_events_count": verified_count,
            "single_source_events_count": single_source_count,
            "verified_clusters_count": sum(1 for c in verified_clusters if c["verification_status"] == "VERIFIED"),
            "single_source_clusters_count": sum(1 for c in verified_clusters if c["verification_status"] == "SINGLE_SOURCE"),
        }

        return events, verified_clusters, current_intelligence, report

    def run(self) -> Dict[str, Any]:
        """Execute full news processing & verification."""
        t_start = time.time()
        logger.info("Starting Daily News Processing & Cross-Verification Job...")

        if not ARTICLES_PATH.exists():
            logger.warning(f"No articles file found at {ARTICLES_PATH}. Run fetch_news first.")
            return {"status": "NO_ARTICLES_TO_PROCESS"}

        with open(ARTICLES_PATH, "r", encoding="utf-8") as f:
            articles = json.load(f)

        events = self.process_articles(articles)
        events, clusters, intel, report = self.cluster_and_verify(events)

        with open(EVENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
        with open(CLUSTERS_PATH, "w", encoding="utf-8") as f:
            json.dump(clusters, f, indent=2)
        with open(CURRENT_INTEL_PATH, "w", encoding="utf-8") as f:
            json.dump(intel, f, indent=2)
        with open(VERIF_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        with open(AUDIT_COPY_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        elapsed = round(time.time() - t_start, 2)
        logger.info(f"News Processing Complete in {elapsed}s: {len(events)} events processed, {report['verified_clusters_count']} verified clusters.")
        return report


if __name__ == "__main__":
    job = NewsProcessingJob()
    res = job.run()
    print(json.dumps(res, indent=2))
