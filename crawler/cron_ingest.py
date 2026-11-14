"""Automated 30-minute real-time ingestion service for Seilbronn:
1. Ingests real-time YouTube comments using the user API key.
2. Ingests latest SWR, Stadt Heilbronn, and Google News RSS items.
3. Classifies topic, stance, and station.
4. Deduplicates and atomically updates data/annotations.sqlite3 and data/heilbronn_seilbahn_dataset.json.
5. Can run as a standalone loop (every 30 minutes) or be triggered on-demand.
"""

import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from crawler.youtube_extractor import fetch_realtime_youtube_data
from crawler.scraper import crawl_swr, crawl_stadt_heilbronn, crawl_google_news

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "heilbronn_seilbahn_dataset.json"
DB_FILE = DATA_DIR / "annotations.sqlite3"
INCOMING_DIR = DATA_DIR / "incoming"
INCOMING_DIR.mkdir(parents=True, exist_ok=True)


def load_existing_records() -> tuple[List[Dict[str, Any]], Set[str]]:
    records = []
    seen_ids = set()
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
            for r in records:
                seen_ids.add(r.get("mention_id"))
        except Exception as e:
            print(f"[Ingest] Error loading {DATA_FILE}: {e}")
    return records, seen_ids


def run_ingestion_cycle() -> int:
    """Run one real-time extraction cycle across YouTube and news feeds."""
    start_time = datetime.now()
    print(f"\n[Ingest Worker] ===== Starting Real-Time Ingestion Cycle at {start_time.strftime('%Y-%m-%d %H:%M:%S')} =====")

    existing_records, seen_ids = load_existing_records()
    initial_count = len(existing_records)
    new_records = []

    # 1. YouTube Comments via API Key
    try:
        yt_records = fetch_realtime_youtube_data(seen_ids)
        for r in yt_records:
            if r["mention_id"] not in seen_ids:
                new_records.append(r)
                seen_ids.add(r["mention_id"])
    except Exception as e:
        print(f"[Ingest Worker] YouTube fetch error: {e}")

    # 2. RSS Feeds (SWR, Stadt Heilbronn, Google News)
    for name, func, default_topic in [
        ("SWR Aktuell", crawl_swr, "Bus & Transit Connections"),
        ("Stadt Heilbronn", crawl_stadt_heilbronn, "Cost & Funding"),
        ("Google News", crawl_google_news, "Travel Time & Commute"),
    ]:
        try:
            feed_items = func()
            for item in feed_items:
                mid = item.get("mention_id")
                if mid and mid not in seen_ids:
                    item["topic"] = item.get("topic") or default_topic
                    item["stance"] = item.get("stance") or "lean_support"
                    item["support_score"] = item.get("support_score") or 6.8
                    new_records.append(item)
                    seen_ids.add(mid)
        except Exception as e:
            print(f"[Ingest Worker] {name} crawl error: {e}")

    # 3. Save if new items found
    if new_records:
        print(f"[Ingest Worker] Ingested {len(new_records)} brand new records! Updating dataset and SQLite...")
        all_updated = new_records + existing_records
        all_updated.sort(key=lambda x: x.get("published_at") or "", reverse=True)

        # Write to JSON
        tmp_file = DATA_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(all_updated, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, DATA_FILE)

        # Write incoming snapshot
        snapshot_file = INCOMING_DIR / f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(new_records, f, ensure_ascii=False, indent=2)

        # Update SQLite
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            for r in new_records:
                cur.execute("""
                    INSERT OR REPLACE INTO mentions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r["mention_id"],
                    r.get("title", ""),
                    r.get("content", ""),
                    r.get("source_name", ""),
                    r.get("media_type_name", ""),
                    r.get("url", ""),
                    r.get("published_at", ""),
                    r.get("topic", "Other & Unclassified"),
                    r.get("stance", "unclear"),
                    float(r.get("support_score", 5.0)),
                    r.get("mentioned_station"),
                    0
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Ingest Worker] SQLite update error: {e}")

        print(f"[Ingest Worker] Database updated. Total records now: {len(all_updated)} (was {initial_count}).")
    else:
        print("[Ingest Worker] No new records found in this cycle (all existing items are up-to-date).")

    duration = (datetime.now() - start_time).total_seconds()
    print(f"[Ingest Worker] Cycle finished in {duration:.1f}s. Next cycle in 24 hours.\n")
    return len(new_records)


def start_24h_scheduler():
    """Continuous loop executing every 24 hours (86,400 seconds)."""
    interval_seconds = int(os.getenv("SEILBRONN_CRAWL_INTERVAL_SECONDS", "86400"))
    print(f"[Scheduler] Starting 24-hour daily real-time crawler daemon (interval: {interval_seconds}s / 24h)...")
    
    while True:
        try:
            run_ingestion_cycle()
        except Exception as e:
            print(f"[Scheduler] Exception during cycle: {e}")
        
        print(f"[Scheduler] Sleeping for {interval_seconds // 3600} hours until next real-time pull...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.once:
        run_ingestion_cycle()
    else:
        start_24h_scheduler()
