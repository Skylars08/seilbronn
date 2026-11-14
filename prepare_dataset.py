"""Data preparation pipeline for Seilbronn:
1. Extracts relevant Heilbronn Seilbahn records from FSI_Heilbronn_Medienbeiträge (1).json (39,361 records)
2. Ingests official milestones from Seilbronn-online-sources.json
3. Ingests real YouTube comments using YOUTUBE_API_KEY
4. Runs conservative multilingual keyword classification
5. Assigns topics, stances, argument categories, and station tags
6. Exports to data/heilbronn_seilbahn_dataset.json and data/annotations.sqlite3
"""

import json
import re
import os
import sqlite3
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FSI_PATH = Path("/Volumes/Helumi/Hackathon Project/FSI_Heilbronn_Medienbeiträge (1).json")
MILESTONES_PATH = Path("/Volumes/Helumi/Hackathon Project/Seilbronn-online-sources.json")
ENV_PATH = BASE_DIR / ".env"

# Read YouTube API Key
YOUTUBE_API_KEY = ""
if ENV_PATH.exists():
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith("YOUTUBE_API_KEY="):
                YOUTUBE_API_KEY = line.strip().split("=", 1)[1].strip("\"'")

CABLE_CAR_REGEX = re.compile(
    r"seilbahn|kabinenbahn|gondelbahn|luftseilbahn|seilschwebebahn|\bgondel\b|cable[\s-]?car|gondola|ropeway|aerial[\s-]?tram",
    re.IGNORECASE,
)
HEILBRONN_REGEX = re.compile(
    r"heilbronn|\bwartberg\b|\bbuga\b|neckarbogen|ipai|bildungscampus|theresienwiese",
    re.IGNORECASE,
)

# Station detectors
STATIONS = {
    "Hauptbahnhof": re.compile(r"hauptbahnhof|\bhbf\b|bahnhof|s-bahn|zuganschluss", re.I),
    "Neckarbogen": re.compile(r"neckarbogen|neckar\b|ufer|wohnquartier", re.I),
    "Europaplatz / BUGA": re.compile(r"europaplatz|buga|bundesgartenschau|park", re.I),
    "Bildungscampus West": re.compile(r"bildungscampus|hochschule|campus|student|dual\w* hochschule|dhbw", re.I),
    "Theresienwiese / Wohlgelegen": re.compile(r"theresienwiese|wohlgelegen|park[\s-]?and[\s-]?ride|p\+r|messe", re.I),
    "IPAI": re.compile(r"ipai|innovation park|künstliche intelligenz|ai campus|steinbeis", re.I),
}

# Topic keyword patterns
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

SUPPORT_TERMS = re.compile(
    r"große chance|zukunftsträchtig|innovativ|fortschritt|chancen|begrüßenswert|optimistisch|großer gewinn|entlastung|erfolgsmodell|visionär|nachhaltig|toll|begeistert|dafür|zustimm\w*|vorantreiben",
    re.I,
)
OPPOSE_TERMS = re.compile(
    r"prestigeprojekt|verschwendung|millionengrab|unsinn|unfug|dagegen|ablehn\w*|skeptisch|kritisch|überflüssig|sinnlos|kein mensch braucht|illusion|katastrophe|teurer luxus",
    re.I,
)

def determine_topic(title: str, text: str) -> str:
    combined = f"{title}\n{text}"
    scores = {}
    for topic, pat in TOPIC_PATTERNS.items():
        matches = pat.findall(combined)
        if matches:
            scores[topic] = len(matches)
    if not scores:
        return "Other & Unclassified"
    # Return topic with highest hit count
    return max(scores.items(), key=lambda x: x[1])[0]

def determine_stance_and_score(title: str, text: str, media_type: str) -> tuple[str, float]:
    combined = f"{title}\n{text}"
    pro_hits = len(SUPPORT_TERMS.findall(combined))
    con_hits = len(OPPOSE_TERMS.findall(combined))

    if media_type in ["press_release", "official_milestone"]:
        # Official city/state materials explain planning & support
        return "strongly_support", 8.8
    
    if pro_hits > con_hits:
        score = min(10.0, 7.0 + pro_hits * 0.6)
        stance = "strongly_support" if score >= 8.0 else "lean_support"
        return stance, round(score, 1)
    elif con_hits > pro_hits:
        score = max(0.5, 3.5 - con_hits * 0.6)
        stance = "strongly_oppose" if score <= 2.5 else "skeptical"
        return stance, round(score, 1)
    elif pro_hits > 0 and con_hits > 0:
        return "neutral", 5.0
    else:
        # News articles tend to report factually with slight optimistic council undertone
        if "beschließt" in combined.lower() or "vorplanung" in combined.lower() or "fördert" in combined.lower():
            return "lean_support", 6.8
        return "unclear", 5.5

def extract_station(title: str, text: str) -> str | None:
    combined = f"{title}\n{text}"
    for station, pat in STATIONS.items():
        if pat.search(combined):
            return station
    return None

def fetch_youtube_comments(api_key: str) -> list[dict]:
    if not api_key:
        print("No YouTube API Key provided.")
        return []
    print("Fetching YouTube Heilbronn Seilbahn comments...")
    results = []
    queries = ["Heilbronn Seilbahn", "Urbane Seilbahn Heilbronn", "IPAI Heilbronn Seilbahn"]
    video_ids = set()
    
    for q in queries:
        try:
            url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={urllib.parse.quote(q)}&type=video&key={api_key}&maxResults=8"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                for item in data.get("items", []):
                    vid = item["id"].get("videoId")
                    if vid:
                        video_ids.add((vid, item["snippet"]["title"], item["snippet"]["publishedAt"]))
        except Exception as e:
            print(f"Error searching YouTube for {q}: {e}")

    print(f"Found {len(video_ids)} relevant videos. Fetching comments...")
    for vid, vtitle, vdate in video_ids:
        try:
            url = f"https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId={vid}&key={api_key}&maxResults=20"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                for item in data.get("items", []):
                    c = item["snippet"]["topLevelComment"]["snippet"]
                    author = c.get("authorDisplayName", "Citizen")
                    text = c.get("textDisplay", "").replace("<br>", "\n").replace("&quot;", '"')
                    pub = c.get("publishedAt", vdate)
                    mention_id = f"yt:{c.get('id', hashlib.md5(text.encode()).hexdigest()[:12])}"
                    
                    topic = determine_topic(vtitle, text)
                    stance, score = determine_stance_and_score(vtitle, text, "social_comment")
                    station = extract_station(vtitle, text)
                    
                    results.append({
                        "mention_id": mention_id,
                        "title": f"YouTube Comment on: {vtitle}",
                        "content": text,
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
                    })
        except Exception as e:
            print(f"Error fetching comments for video {vid}: {e}")

    print(f"Extracted {len(results)} YouTube comments.")
    return results

def main():
    records = []
    seen_ids = set()

    # 1. Ingest official milestones
    if MILESTONES_PATH.exists():
        print("Ingesting verified official milestones...")
        with open(MILESTONES_PATH) as f:
            sources_data = json.load(f)
            for item in sources_data.get("records", []):
                mid = f"official:{item['id']}"
                event_date = item.get("event_date") or "2025-05-01"
                topic = "Cost & Funding" if "funding" in item["id"] else "Bus & Transit Connections"
                rec = {
                    "mention_id": mid,
                    "title": item.get("summary", ""),
                    "content": f"{item.get('summary', '')}\n\nPublisher: {item.get('publisher')}\nVerified official record for Heilbronn urban cable car planning.",
                    "source_name": item.get("publisher", "Stadt Heilbronn"),
                    "media_type_name": item.get("kind", "official_milestone"),
                    "url": item.get("url", ""),
                    "published_at": f"{event_date}T10:00:00+01:00",
                    "topic": topic,
                    "stance": "strongly_support",
                    "support_score": 9.2,
                    "mentioned_station": "Hauptbahnhof" if "transit" in item["id"] else "IPAI",
                    "is_official_milestone": True,
                }
                records.append(rec)
                seen_ids.add(mid)

    # 2. Ingest FSI Dataset (39,361 records)
    if FSI_PATH.exists():
        print(f"Scanning {FSI_PATH} for Heilbronn Seilbahn coverage...")
        with open(FSI_PATH, "r", encoding="utf-8") as f:
            fsi_data = json.load(f)
        
        fsi_matches = 0
        for item in fsi_data:
            content = str(item.get("content") or "")
            title = str(item.get("title") or "")
            combined = f"{title}\n{content}"

            # Filter for Cable car & Heilbronn
            if CABLE_CAR_REGEX.search(combined) and HEILBRONN_REGEX.search(combined):
                fsi_matches += 1
                base_id = str(item.get("mention_id") or f"fsi_{fsi_matches}")
                mid = f"fsi:{base_id}"
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)

                media_type = str(item.get("media_type_name") or "News")
                topic = determine_topic(title, content)
                stance, score = determine_stance_and_score(title, content, media_type)
                station = extract_station(title, content)

                pub = str(item.get("published_at") or "")
                rec = {
                    "mention_id": mid,
                    "title": title or content.split("\n\n")[0][:120],
                    "content": content,
                    "source_name": str(item.get("source_name") or "Media"),
                    "media_type_name": media_type,
                    "url": str(item.get("url") or ""),
                    "published_at": pub,
                    "topic": topic,
                    "stance": stance,
                    "support_score": score,
                    "mentioned_station": station,
                    "is_official_milestone": False,
                }
                records.append(rec)
        print(f"Extracted {fsi_matches} matching records from FSI dataset.")

    # 3. Ingest real YouTube comments
    yt_comments = fetch_youtube_comments(YOUTUBE_API_KEY)
    for c in yt_comments:
        if c["mention_id"] not in seen_ids:
            records.append(c)
            seen_ids.add(c["mention_id"])

    # Sort records by published_at
    records.sort(key=lambda r: r.get("published_at") or "", reverse=True)

    # Save to JSON
    out_json = DATA_DIR / "heilbronn_seilbahn_dataset.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(records)} records to {out_json}.")

    # Save to SQLite
    db_path = DATA_DIR / "annotations.sqlite3"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mentions (
            mention_id TEXT PRIMARY KEY,
            title TEXT,
            content TEXT,
            source_name TEXT,
            media_type_name TEXT,
            url TEXT,
            published_at TEXT,
            topic TEXT,
            stance TEXT,
            support_score REAL,
            mentioned_station TEXT,
            is_official INTEGER DEFAULT 0
        )
    """)
    cur.execute("DELETE FROM mentions")
    for r in records:
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
            1 if r.get("is_official_milestone") else 0
        ))
    conn.commit()
    conn.close()
    print(f"Populated SQLite database {db_path} successfully.")

if __name__ == "__main__":
    main()

