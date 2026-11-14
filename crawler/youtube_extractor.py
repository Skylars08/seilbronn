"""Real-time YouTube comments and video extractor for Heilbronn Cable Car debate.
Uses the provided YouTube Data API v3 key to search for new videos, shorts, and discussions,
and extracts top-level comments and replies.
"""

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

TOPIC_PATTERNS = {
    "Cost & Funding": re.compile(
        r"kost(?:en\w*|et|spielig)|finanzier\w*|budget\w*|förder\w*|zuschuss|subvention|zuschüsse|million\w*|steuergeld\w*|teuer|fahrpreis\w*|betriebskost\w*|wirtschaftlich\w*",
        re.I,
    ),
    "Bus & Transit Connections": re.compile(
        r"umstieg\w*|anschluss\w*|busnetz|busse|s-bahn|stadtbahn|netzwerk|takt\w*|anbindung\w*|verknüpfung|nahverkehrsplan",
        re.I,
    ),
    "Accessibility & Stations": re.compile(
        r"barrierefrei\w*|rollstuhl\w*|aufzug\w*|kinderwagen|fahrrad\w*|zugang\w*|haltestelle\w*|station\w*|ein- und ausstieg",
        re.I,
    ),
    "Travel Time & Commute": re.compile(
        r"fahrzeit\w*|14\s*minut\w*|zeiterspar\w*|schnell\w*|stau\w*|pendler\w*|berufsverkehr|direktverbindung|überwindung",
        re.I,
    ),
    "Environment & Living Privacy": re.compile(
        r"privatsphäre|sichtschutz|einblick\w*|fenster|wohngebiet|lärm\w*|geräusch\w*|baumfäll\w*|bäume|naturschutz|ökolog\w*|klima\w*|co2|schall",
        re.I,
    ),
}

STATIONS = {
    "Hauptbahnhof": re.compile(r"hauptbahnhof|\bhbf\b|bahnhof|s-bahn|zuganschluss", re.I),
    "Neckarbogen": re.compile(r"neckarbogen|neckar\b|ufer|wohnquartier", re.I),
    "Europaplatz / BUGA": re.compile(r"europaplatz|buga|bundesgartenschau|park", re.I),
    "Bildungscampus West": re.compile(r"bildungscampus|hochschule|campus|student|dhbw|tum", re.I),
    "Theresienwiese / Wohlgelegen": re.compile(r"theresienwiese|wohlgelegen|p\+r|messe", re.I),
    "IPAI": re.compile(r"ipai|innovation park|künstliche intelligenz|ai campus", re.I),
}

SUPPORT_TERMS = re.compile(
    r"große chance|zukunftsträchtig|innovativ|fortschritt|chancen|begrüßenswert|optimistisch|großer gewinn|entlastung|erfolgsmodell|visionär|nachhaltig|toll|begeistert|dafür|zustimm\w*|vorantreiben|cool|super|gute idee",
    re.I,
)
OPPOSE_TERMS = re.compile(
    r"prestigeprojekt|verschwendung|millionengrab|unsinn|unfug|dagegen|ablehn\w*|skeptisch|kritisch|überflüssig|sinnlos|kein mensch braucht|illusion|katastrophe|teurer luxus|geldverbrennung|steuerverschwendung",
    re.I,
)


def get_api_key() -> str:
    key = os.getenv("YOUTUBE_API_KEY", "")
    if not key and ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                if line.startswith("YOUTUBE_API_KEY="):
                    key = line.strip().split("=", 1)[1].strip("\"'")
    return key


def classify_topic(text: str) -> str:
    scores = {}
    for topic, pat in TOPIC_PATTERNS.items():
        hits = pat.findall(text)
        if hits:
            scores[topic] = len(hits)
    if not scores:
        return "Other & Unclassified"
    return max(scores.items(), key=lambda x: x[1])[0]


def classify_stance(text: str) -> tuple[str, float]:
    pro = len(SUPPORT_TERMS.findall(text))
    con = len(OPPOSE_TERMS.findall(text))
    if pro > con:
        score = min(10.0, 7.0 + pro * 0.6)
        stance = "strongly_support" if score >= 8.0 else "lean_support"
        return stance, round(score, 1)
    elif con > pro:
        score = max(0.5, 3.5 - con * 0.6)
        stance = "strongly_oppose" if score <= 2.5 else "skeptical"
        return stance, round(score, 1)
    elif pro > 0 and con > 0:
        return "neutral", 5.0
    return "unclear", 5.5


def extract_station(text: str) -> str | None:
    for st_name, pat in STATIONS.items():
        if pat.search(text):
            return st_name
    return None


def fetch_realtime_youtube_data(existing_ids: Set[str] = None) -> List[Dict[str, Any]]:
    """Extract real-time Heilbronn Seilbahn comments and video discussions from YouTube."""
    if existing_ids is None:
        existing_ids = set()

    api_key = get_api_key()
    if not api_key:
        print("[YouTube Crawler] No API key found. Skipping.")
        return []

    print(f"[YouTube Crawler] Running real-time extraction at {datetime.now().isoformat()}...")
    queries = [
        "Heilbronn Seilbahn",
        "Urbane Seilbahn Heilbronn",
        "Seilbahn Heilbronn IPAI",
        "STIMMEtv Seilbahn",
        "L-TV Seilbahn Heilbronn",
        "Heilbronn Gondelbahn"
    ]

    videos = {}
    for q in queries:
        try:
            url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={urllib.parse.quote(q)}&type=video&key={api_key}&maxResults=10&order=date"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
                for item in data.get("items", []):
                    vid = item["id"].get("videoId")
                    if vid and vid not in videos:
                        videos[vid] = {
                            "videoId": vid,
                            "title": item["snippet"]["title"],
                            "publishedAt": item["snippet"]["publishedAt"],
                            "channel": item["snippet"]["channelTitle"]
                        }
        except Exception as e:
            print(f"[YouTube Crawler] Query error for '{q}': {e}")

    print(f"[YouTube Crawler] Found {len(videos)} relevant videos. Fetching comments...")
    new_records = []

    for vid, vinfo in videos.items():
        vtitle = vinfo["title"]
        try:
            url = f"https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId={vid}&key={api_key}&maxResults=25"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
                for item in data.get("items", []):
                    top = item["snippet"]["topLevelComment"]["snippet"]
                    cid = item["id"]
                    mid = f"yt:{cid}"

                    if mid in existing_ids:
                        continue

                    raw_text = top.get("textDisplay", "").replace("<br>", "\n").replace("&quot;", '"')
                    author = top.get("authorDisplayName", "Citizen")
                    pub = top.get("publishedAt", vinfo["publishedAt"])

                    topic = classify_topic(f"{vtitle}\n{raw_text}")
                    stance, score = classify_stance(f"{vtitle}\n{raw_text}")
                    station = extract_station(f"{vtitle}\n{raw_text}")

                    rec = {
                        "mention_id": mid,
                        "title": f"YouTube Comment by {author} on: {vtitle}",
                        "content": raw_text,
                        "source_name": "YouTube",
                        "media_type_name": "social_comment",
                        "author": author,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "published_at": pub,
                        "topic": topic,
                        "stance": stance,
                        "support_score": score,
                        "mentioned_station": station,
                        "video_title": vtitle,
                        "extracted_at": datetime.now().isoformat()
                    }
                    new_records.append(rec)
                    existing_ids.add(mid)

        except Exception as e:
            # comments might be disabled on some videos
            pass

    print(f"[YouTube Crawler] Extracted {len(new_records)} fresh comments.")
    return new_records


if __name__ == "__main__":
    records = fetch_realtime_youtube_data()
    print(f"Test run completed. Retrieved {len(records)} records.")

