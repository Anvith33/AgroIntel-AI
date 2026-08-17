"""
fetch_news.py — Daily Multi-Tier RSS News Ingestion Job for AgroIntel.

Fetches agricultural news from 37 configured sources across 4 credibility tiers:
  - TIER 1: Official Government & Research (ICAR, PIB, DA&FW, IMD, MoES, KVKs, State Depts)
  - TIER 2: Agri-Research & Environment (Krishi Jagran, Rural Voice, AgroSpectrum, AgriWatch, FAO, etc.)
  - TIER 3: Business & Commodity Media (Economic Times, Business Standard, Financial Express, Reuters, etc.)
  - TIER 4: National & Regional Media (The Hindu, Indian Express, Times of India, etc.)
  - DISCOVERY: Google News RSS queries for targeted agricultural events.

Per-source runtime verification tracks HTTP status, article counts, and error diagnostics.
Never crashes on single-source failure.
"""

import hashlib
import json
import logging
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app.jobs.fetch_news")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
EXP_DIR = DATA_DIR / "experimental"
EXP_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR = BASE_DIR.parent / "audit" / "news"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

REGISTRY_PATH = EXP_DIR / "news_source_registry.json"
ARTICLES_JSON_PATH = EXP_DIR / "news_articles.json"
SOURCE_STATUS_PATH = EXP_DIR / "news_source_runtime_audit.json"
INGESTION_AUDIT_PATH = EXP_DIR / "news_ingestion_audit.json"
AUDIT_COPY_PATH = AUDIT_DIR / "news_source_runtime_audit.json"


class NewsIngestionJob:
    """Production Multi-Source News Ingestion Job."""

    def __init__(self):
        self.registry = self._load_registry()
        self.client_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AgroIntelBot/4.0; +https://github.com/Dhanushkumar4-ai/AgroIntel)"
        }

    def _load_registry(self) -> Dict[str, Any]:
        if not REGISTRY_PATH.exists():
            logger.warning(f"Source registry missing at {REGISTRY_PATH}. Using default source list.")
            return {}
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading source registry: {e}")
            return {}

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        if not raw_text:
            return ""
        clean = re.sub(r"<[^>]+>", " ", raw_text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def fetch_rss_feed(self, url: str, timeout: float = 8.0) -> Tuple[int, List[Dict[str, Any]], Optional[str]]:
        """Fetch and parse an RSS/Atom XML feed."""
        try:
            with httpx.Client(timeout=timeout, headers=self.client_headers, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return resp.status_code, [], f"HTTP {resp.status_code}"
                
                content = resp.text
                articles = self._parse_xml_feed(content, url)
                return 200, articles, None
        except httpx.TimeoutException:
            return 408, [], "Request Timeout (> 8.0s)"
        except Exception as e:
            return 500, [], str(e)

    def _parse_xml_feed(self, xml_content: str, source_url: str) -> List[Dict[str, Any]]:
        """Parse XML items into standardized article dictionaries."""
        articles = []
        try:
            root = ET.fromstring(xml_content)
            # Standard RSS channel -> item
            items = root.findall(".//item")
            if not items:
                # Atom feed entry
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for it in items:
                title = it.findtext("title") or it.findtext("{http://www.w3.org/2005/Atom}title") or ""
                desc = it.findtext("description") or it.findtext("summary") or it.findtext("{http://www.w3.org/2005/Atom}summary") or ""
                link = it.findtext("link") or ""
                if not link and it.find("{http://www.w3.org/2005/Atom}link") is not None:
                    link = it.find("{http://www.w3.org/2005/Atom}link").attrib.get("href", "")

                pub_date = it.findtext("pubDate") or it.findtext("published") or it.findtext("{http://www.w3.org/2005/Atom}published") or ""

                title_clean = self._clean_text(title)
                desc_clean = self._clean_text(desc)

                if title_clean:
                    art_id = "ART_" + hashlib.sha256((title_clean + link).encode("utf-8")).hexdigest()[:16]
                    articles.append({
                        "article_id": art_id,
                        "title": title_clean,
                        "description": desc_clean,
                        "link": link,
                        "pub_date": pub_date,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "source_url": source_url,
                    })
        except Exception as e:
            logger.debug(f"XML Parsing note for {source_url}: {e}")
        return articles

    def run(self) -> Dict[str, Any]:
        """Execute full news ingestion across all configured tiers."""
        t_start = time.time()
        logger.info("Starting Daily News RSS Ingestion Job...")

        source_runtime_audit = []
        all_articles = []
        seen_article_ids = set()

        # Load existing articles if present to preserve history
        if ARTICLES_JSON_PATH.exists():
            try:
                with open(ARTICLES_JSON_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        for a in existing:
                            aid = a.get("article_id")
                            if aid:
                                seen_article_ids.add(aid)
                                all_articles.append(a)
            except Exception as e:
                logger.warning(f"Could not load existing articles: {e}")

        initial_count = len(all_articles)

        # Iterate through tiers in registry
        tiers = self.registry.get("credibility_tiers", {})
        total_sources = 0

        for tier_key, tier_info in tiers.items():
            sources = tier_info.get("sources", [])
            for src in sources:
                total_sources += 1
                src_id = src.get("source_id", "unknown")
                src_name = src.get("source_name", "Unknown Source")
                tier_label = src.get("tier", "TIER_4")
                rss_url = src.get("rss_url")
                query = src.get("google_news_query")

                # Determine target URL (direct RSS or Google News discovery RSS)
                target_url = rss_url
                if not target_url and query:
                    encoded_q = urllib.parse.quote(query)
                    target_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-IN&gl=IN&ceid=IN:en"

                if not target_url:
                    source_runtime_audit.append({
                        "source_id": src_id,
                        "source_name": src_name,
                        "tier": tier_label,
                        "status": "NO_FEED_CONFIGURED",
                        "http_status": None,
                        "articles_fetched": 0,
                        "latest_date": None,
                        "error": "No RSS URL or Query configured"
                    })
                    continue

                http_code, fetched, err = self.fetch_rss_feed(target_url, timeout=5.0)

                new_for_src = 0
                latest_dt = None

                for item in fetched:
                    item["source_id"] = src_id
                    item["source_name"] = src_name
                    item["tier"] = tier_label
                    if item["article_id"] not in seen_article_ids:
                        seen_article_ids.add(item["article_id"])
                        all_articles.append(item)
                        new_for_src += 1
                    if not latest_dt and item.get("pub_date"):
                        latest_dt = item.get("pub_date")

                status_label = "SUCCESS" if http_code == 200 and fetched else ("EMPTY_OR_UNAVAILABLE" if http_code == 200 else "FAILED")

                source_runtime_audit.append({
                    "source_id": src_id,
                    "source_name": src_name,
                    "tier": tier_label,
                    "target_url": target_url,
                    "status": status_label,
                    "http_status": http_code,
                    "articles_fetched": len(fetched),
                    "new_articles_added": new_for_src,
                    "latest_date": latest_dt,
                    "error": err
                })

        new_total_added = len(all_articles) - initial_count

        # Save all articles (capped at latest 5000 to maintain high performance)
        all_articles = all_articles[-5000:]
        with open(ARTICLES_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(all_articles, f, indent=2)

        elapsed = round(time.time() - t_start, 2)

        audit_summary = {
            "job_name": "fetch_news",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_time_seconds": elapsed,
            "total_sources_audited": total_sources,
            "sources_active": sum(1 for s in source_runtime_audit if s["status"] == "SUCCESS"),
            "sources_failed": sum(1 for s in source_runtime_audit if s["status"] != "SUCCESS"),
            "new_articles_ingested": new_total_added,
            "total_stored_articles": len(all_articles),
            "sources_status": source_runtime_audit,
        }

        with open(SOURCE_STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump(source_runtime_audit, f, indent=2)
        with open(INGESTION_AUDIT_PATH, "w", encoding="utf-8") as f:
            json.dump(audit_summary, f, indent=2)
        with open(AUDIT_COPY_PATH, "w", encoding="utf-8") as f:
            json.dump(source_runtime_audit, f, indent=2)

        logger.info(f"News Ingestion Complete in {elapsed}s: {new_total_added} new articles from {total_sources} sources.")
        return audit_summary


if __name__ == "__main__":
    job = NewsIngestionJob()
    res = job.run()
    print(json.dumps({k: v for k, v in res.items() if k != "sources_status"}, indent=2))
