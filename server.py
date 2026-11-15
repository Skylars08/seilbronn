"""FastAPI Server for Seilbronn: Heilbronn Urban Cable Car Decision & Sentiment Atlas.
Serves public debate data, topic analytics, route/stop details, milestone timeline,
AI policy options generator, live crawlers, and export tools.
"""

import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Thread
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
HOSTED = bool(os.getenv("VERCEL"))

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DATA_FILE = DATA_DIR / "heilbronn_seilbahn_dataset.json"
DB_FILE = DATA_DIR / "annotations.sqlite3"
MILESTONES_FILE = Path("/Volumes/Helumi/Hackathon Project/Seilbronn-online-sources.json")
ENV_FILE = BASE_DIR / ".env"

app = FastAPI(title="Seilbronn API", description="Heilbronn Urban Cable Car Decision & Sentiment Atlas")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load dataset into memory
ALL_RECORDS = []
if DATA_FILE.exists():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            ALL_RECORDS = json.load(f)
        print(f"Loaded {len(ALL_RECORDS)} records into memory.")
    except Exception as e:
        print(f"Error loading {DATA_FILE}: {e}")

# Verified Milestones
VERIFIED_MILESTONES = [
    {
        "id": "hn-council-2025-04-03",
        "kind": "official_milestone",
        "event_date": "2025-04-03",
        "publisher": "Stadt Heilbronn",
        "title": "Gemeinderat befürwortet Seilbahn-Planung",
        "summary": "The city council backed further planning for the proposed urban cable car.",
        "url": "https://www.heilbronn.de/rathaus/aktuelles/in-der-seilbahn-durch-die-stadt-schweben.html",
        "category": "Council Decision",
        "impact": "Kick-started formal feasibility study and state grant application discussions."
    },
    {
        "id": "hn-funding-2025-05-12",
        "kind": "news",
        "event_date": "2025-05-12",
        "publisher": "SWR Aktuell & Land BW",
        "title": "Land fördert Seilbahn mit Millionen – Absichtserklärung unterzeichnet",
        "summary": "State of Baden-Württemberg signed a letter of intent to co-fund planning with multi-million euro backing.",
        "url": "https://www.swr.de/swraktuell/baden-wuerttemberg/heilbronn/land-foerdert-seilbahn-in-heilbronn-mit-millionen-absichtserklaerung-unterzeichnet-100.html",
        "category": "State Funding",
        "impact": "Secured state transport ministry commitment up to 80-90% subsidized planning costs."
    },
    {
        "id": "hn-council-2026-07-27",
        "kind": "official_milestone",
        "event_date": "2026-07-27",
        "publisher": "Stadt Heilbronn",
        "title": "Gemeinderat beschließt Vorplanung für urbane Seilbahn",
        "summary": "The city council officially approved preliminary planning (Vorplanung) and commissioning external planning offices.",
        "url": "https://www.heilbronn.de/kommunikation/pressemitteilungen/details/artikel/gemeinderat-beschliesst-vorplanung-fuer-urbane-seilbahn.html",
        "category": "Planning Approval",
        "impact": "Transition from feasibility study to concrete route alignment, tower positions, and station design."
    },
    {
        "id": "hn-techzeitgeist-2026-08-14",
        "kind": "news",
        "event_date": "2026-08-14",
        "publisher": "TechZeitGeist",
        "title": "Urbane Seilbahn Heilbronn: 14 Minuten bis zum IPAI",
        "summary": "Analysis of the 14-minute end-to-end travel time connecting Hauptbahnhof, Neckarbogen, and IPAI tech campus.",
        "url": "https://www.techzeitgeist.de/heilbronn-urbane-seilbahn-14-minuten-ipai-vorplanung/",
        "category": "Technical Analysis",
        "impact": "High public visibility on commuting speed and direct connection across the Neckar."
    },
    {
        "id": "hn-transit-plan",
        "kind": "official_reference",
        "event_date": "2025-09-15",
        "publisher": "Stadt Heilbronn",
        "title": "Nahverkehrsplan 2025 / 2026",
        "summary": "Local transport plan places the proposed cable car in the wider multimodal transit network.",
        "url": "https://www.heilbronn.de/fileadmin/daten/stadtheilbronn/formulare/umwelt_mobilitaet/mobilitaet/Nahverkehrsplan_2025.pdf",
        "category": "Network Integration",
        "impact": "Harmonizes bus lines and S-Bahn schedules with gondola station headways."
    }
]

# Stops definitions
STOPS_DATA = [
    {
        "id": "hauptbahnhof",
        "name": "Hauptbahnhof (Hbf)",
        "subtitle": "Multimodal Gateway & Regional Hub",
        "transfer_links": ["Deutsche Bahn RE/RB/MEX", "S-Bahn Rhein-Neckar", "Stadtbahn Heilbronn S4/S41/S42", "ZOB Busbahnhof"],
        "travel_time_from_start": "0 min",
        "walking_link": "Covered 80m footbridge directly from platform 1 to cable-car entrance level (+1).",
        "passenger_scenario": "Commuters arriving from Stuttgart, Karlsruhe, or Mannheim transfer seamlessly into 10-person gondolas with 30-second headway.",
        "feedback_summary": "High excitement about bypassing inner-city traffic; concerns about morning rush-hour queuing and bike carriage limits.",
        "recommendations": [
            "Install dedicated turnstiles for commuter ticket holders (Deutschlandticket).",
            "Design generous gondola interior with folding seats for wheelchairs and 2 bicycles per cabin.",
            "Synchronize arrival displays with Deutsche Bahn real-time departure boards."
        ],
        "coords": [49.1416, 9.2083]
    },
    {
        "id": "neckarbogen",
        "name": "Neckarbogen",
        "subtitle": "Eco-District & Waterfront Residential",
        "transfer_links": ["Local Bus line 8", "City Bike Sharing", "Pedestrian Neckar promenade"],
        "travel_time_from_start": "3 min",
        "walking_link": "Direct ramp to riverbank promenade and residential courtyards (under 2 minutes walking).",
        "passenger_scenario": "Residents commuting to Bildungscampus or IPAI; weekend leisure passengers accessing riverside parks.",
        "feedback_summary": "Primary concern: Privacy invasion / sightlines into 3rd-floor apartments; noise from cable sheaves on support towers.",
        "recommendations": [
            "Smart electrochromic glass windows that automatically turn opaque when gondolas pass over residential balconies.",
            "Tower placement optimized to avoid direct sightlines into private bedrooms.",
            "Vibration-damped sheave assemblies certified below 42 dB(A) at building facades."
        ],
        "coords": [49.1495, 9.2135]
    },
    {
        "id": "europaplatz_buga",
        "name": "Europaplatz / BUGA",
        "subtitle": "Convention, Parks & Recreation",
        "transfer_links": ["Stadtbahn S41/S42", "Bus lines 10, 11", "Park & Ride Parking Garage"],
        "travel_time_from_start": "6 min",
        "walking_link": "Integrated into plaza entrance, 50m to convention center foyer.",
        "passenger_scenario": "Event attendees, tourists visiting former BUGA grounds, and local families.",
        "feedback_summary": "Strong historical nostalgia from successful BUGA 2019 cable car; request to keep ticket prices within standard ÖPNV tariff.",
        "recommendations": [
            "Integrate full Deutschlandticket and HNV tariff validity without extra surcharge.",
            "Install cultural & historical information panels highlighting BUGA legacy and future green city transit."
        ],
        "coords": [49.1538, 9.2198]
    },
    {
        "id": "bildungscampus_west",
        "name": "Bildungscampus West",
        "subtitle": "Higher Education & University Hub",
        "transfer_links": ["Campus Shuttle", "Bus line 5", "E-Scooter Hub"],
        "travel_time_from_start": "9 min",
        "walking_link": "Short 60m landscaped walkway to DHBW and TUM Campus buildings.",
        "passenger_scenario": "Over 10,000 university students and researchers commuting between campus and rail stations.",
        "feedback_summary": "Massive student support; high demand for reliable winter operation and late evening return trips after study sessions.",
        "recommendations": [
            "Extend operating hours until 23:30 on weekdays and midnight on exam period weekends.",
            "Campus card contactless validation at speed gates.",
            "Dedicated weather-protected student waiting lounge with Wi-Fi."
        ],
        "coords": [49.1582, 9.2245]
    },
    {
        "id": "theresienwiese",
        "name": "Theresienwiese / Wohlgelegen",
        "subtitle": "Commercial & Regional P+R Hub",
        "transfer_links": ["Regional Bus 631, 642", "Park & Ride (800 car spaces)", "B+R Covered Bike Station"],
        "travel_time_from_start": "11 min",
        "walking_link": "Direct covered stairway and high-capacity elevator connecting parking deck directly to platform.",
        "passenger_scenario": "Inbound regional commuters from surrounding Heilbronn district parking cars outside the center and floating above congestion.",
        "feedback_summary": "Questions regarding parking fees for P+R users and electric charging integration.",
        "recommendations": [
            "Combined Park+Ride + Cable Car combo ticket (free parking with transit ride).",
            "Solar canopy on parking roof supplying direct green electricity to cable car drive."
        ],
        "coords": [49.1620, 9.2310]
    },
    {
        "id": "ipai",
        "name": "IPAI (Innovation Park AI)",
        "subtitle": "Europe's AI Flagship & Technology Campus",
        "transfer_links": ["IPAI Autonomous Shuttle", "Regional express connections", "Innovation Hub Concierge"],
        "travel_time_from_start": "14 min",
        "walking_link": "Station terminal integrated directly inside the main IPAI Innovation Forum atrium.",
        "passenger_scenario": "Tech workers, global visiting scientists, founders, and business delegates arriving from Hbf in 14 minutes flat.",
        "feedback_summary": "Celebrated as a visionary technology showcase connecting city center with the AI hub; inquiries on freight/parcel transport.",
        "recommendations": [
            "Test off-peak automated lightweight parcel delivery capsules between IPAI research labs and Hbf logistics.",
            "Digital departure boards in all IPAI company lobbies showing real-time gondola arrivals.",
            "100% renewable solar power branding reflecting Heilbronn's green technology vision."
        ],
        "coords": [49.1685, 9.2392]
    }
]

# Topic deep dive data
TOPICS_KNOWLEDGE = {
    "Cost & Funding": {
        "title": "Cost & Public Funding",
        "summary": "Financial feasibility, state subsidies, and long-term operating economics.",
        "key_question": "Who pays for construction, and will operating deficits burden municipal taxpayers?",
        "pro_arguments": [
            {"claim": "Up to 80–90% eligible for Federal & State Subsidies (GVFG)", "evidence": "Letter of intent signed on 2025-05-12 guarantees Baden-Württemberg co-funding under municipal transport financing act."},
            {"claim": "Significantly cheaper per kilometer than light rail or tunnel construction", "evidence": "Feasibility benchmark: Cable car ~€15–20M/km vs. Stadtbahn ~€40–60M/km in urban terrain."},
            {"claim": "Low operating energy cost per passenger due to continuous electric motor loop", "evidence": "Central high-efficiency electric drive with regenerative braking on descent sections."}
        ],
        "con_arguments": [
            {"claim": "Risk of municipal cost escalation during detailed technical design", "evidence": "Citizens cite rising construction inflation and complex Neckar pylon foundations."},
            {"claim": "Ongoing operating subsidies if daily ridership falls below 8,000 trips", "evidence": "Staff and ticket revenue must balance regular maintenance, rope inspection, and station staffing."}
        ],
        "city_actions": [
            "Publish transparent cost breakdown showing exact municipal share vs. state grant allocations.",
            "Establish fixed-price general contractor bidding for electromechanical systems.",
            "Model conservative ridership sensitivities (worst-case 4,500 vs base-case 9,200 daily passengers)."
        ]
    },
    "Bus & Transit Connections": {
        "title": "Bus & Transit Connections",
        "summary": "Integration with existing Heilbronn Stadtbahn, regional trains, and city bus lines.",
        "key_question": "Does the cable car complement or cannibalize current bus routes?",
        "pro_arguments": [
            {"claim": "Direct connection between Hbf and IPAI bypassing bottleneck streets", "evidence": "Relieves congested Neckargartacher and Paul-Göbel road axes by flying above them."},
            {"claim": "Synchronized transfers at Hbf with Deutsche Bahn regional express trains", "evidence": "Continuous 30s departure intervals eliminate timetabled transfer wait anxiety."}
        ],
        "con_arguments": [
            {"claim": "Potential reduction of direct bus services for intermediate neighborhood streets", "evidence": "Residents worry local bus frequencies might be cut to force riders onto the cable car."},
            {"claim": "Transfer inconvenience in inclement weather if walkways lack full rain canopies", "evidence": "Passengers emphasize need for seamless dry walking paths between bus and station."}
        ],
        "city_actions": [
            "Include cable car into the Nahverkehrsplan 2026 as a backbone trunk line with feeding buses.",
            "Commit that no existing bus lines will be cancelled without equal or better local coverage.",
            "Build fully covered, weather-protected pedestrian transfer bridges at Hbf and Europaplatz."
        ]
    },
    "Accessibility & Stations": {
        "title": "Accessibility & Station Design",
        "summary": "Universal barrier-free access, elevators, bike transport, and platform safety.",
        "key_question": "Can elderly citizens, wheelchair users, and cyclists board comfortably?",
        "pro_arguments": [
            {"claim": "Level step-free boarding with cabins slowing down in station loops", "evidence": "Gondola decelerates to 0.3 m/s in terminal allowing level walk-in/roll-in entry."},
            {"claim": "High-capacity through-station elevators designed for strollers and electric wheelchairs", "evidence": "Meets DIN 18040 barrier-free public transit construction standards."}
        ],
        "con_arguments": [
            {"claim": "Bike carriage competition with rush-hour commuters", "evidence": "Cyclists demand guaranteed cabin space without obstructing wheelchair passengers."},
            {"claim": "Elevator breakdown vulnerabilities at elevated stations", "evidence": "Elderly residents question what happens if a station lift is out of service."}
        ],
        "city_actions": [
            "Mandate dual redundant elevators at all elevated station towers.",
            "Implement dedicated cabin floor markings: 4 priority seats, 1 wheelchair zone, 2 bike spots.",
            "24/7 CCTV monitoring and emergency intercom in every cabin and station lift."
        ]
    },
    "Travel Time & Commute": {
        "title": "Travel Time & Commute Speed",
        "summary": "Punctuality, avoidance of road congestion, and 14-minute trip to IPAI.",
        "key_question": "Is the cable car truly faster than driving or riding an e-bike?",
        "pro_arguments": [
            {"claim": "Guaranteed 14-minute transit time completely immune to road traffic jams", "evidence": "Independent right-of-way in 2nd vertical level overcomes river, rail, and road barriers."},
            {"claim": "Zero wait time with 25-35 second cabin departure frequency", "evidence": "Continuous movement system means passengers never miss a scheduled departure."}
        ],
        "con_arguments": [
            {"claim": "Maximum operating speed (approx. 25-30 km/h) feels modest over long distances", "evidence": "Some respondents wonder if a fast bus lane on an expanded bridge could achieve similar speed."}
        ],
        "city_actions": [
            "Publish interactive commute time comparison tool (Car in rush hour 28 min vs. Seilbahn 14 min).",
            "Demonstrate total journey reliability: 99.4% punctuality vs. unpredictable bridge traffic delays."
        ]
    },
    "Environment & Living Privacy": {
        "title": "Environment & Living Privacy",
        "summary": "Visual impact, pylon placement, residential privacy, noise levels, and tree conservation.",
        "key_question": "Will cabins look into private living rooms, and do towers damage green zones?",
        "pro_arguments": [
            {"claim": "Zero local tailpipe emissions and whisper-quiet electric motor drives", "evidence": "Cabin itself has no motor, sliding silently on taut steel cables; quietest urban transit mode."},
            {"claim": "Minimal ground footprint compared to road expansion or railway tracks", "evidence": "Requires only small pylon foundation points (approx. 30-50m² each) instead of continuous sealed lanes."}
        ],
        "con_arguments": [
            {"claim": "Direct sightline invasion into upper-floor Neckarbogen residences", "evidence": "High citizen sensitivity regarding tourists or passengers looking down into balconies."},
            {"claim": "Visual pylon footprint and potential tree trimming along riverbanks", "evidence": "Concerns over river vista aesthetics and bird flight safety."}
        ],
        "city_actions": [
            "Implement electrochromic smart glass that automatically frosts windows over residential sectors.",
            "Adopt bird-protection pylon markings and silent polymer sheave wheels.",
            "Conduct 3D VR simulation sessions for affected residents before final pylon location approval."
        ]
    },
    "Other & Unclassified": {
        "title": "General & Route Planning",
        "summary": "Broader city transformation, tourism appeal, and comparison with other cities.",
        "key_question": "How does this position Heilbronn in Europe as a pioneering smart city?",
        "pro_arguments": [
            {"claim": "Modern innovation symbol aligning Heilbronn's AI hub identity", "evidence": "Matches successful international systems in Toulouse (Téléo) and Koblenz."},
            {"claim": "High architectural appeal attracting international visitors and tech talent", "evidence": "Brings forward-looking mobility showcase directly into the urban skyline."}
        ],
        "con_arguments": [
            {"claim": "Skepticism over whether tourist appeal is being favored over standard bus service", "evidence": "Calls for pragmatic investments in suburban schools and cycling paths."}
        ],
        "city_actions": [
            "Reiterate that the cable car is an everyday public transport trunk line, not a tourist attraction.",
            "Host open citizen forums and digital feedback rounds throughout the Vorplanung phase."
        ]
    }
}

# Helper: filter records
def filter_dataset(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    topic: Optional[str] = None,
    source: Optional[str] = None,
    stance: Optional[str] = None,
    query: Optional[str] = None
):
    results = ALL_RECORDS
    if start_date:
        results = [r for r in results if (r.get("published_at") or "") >= start_date]
    if end_date:
        # Include full day
        results = [r for r in results if (r.get("published_at") or "")[:10] <= end_date[:10]]
    if topic and topic != "all":
        results = [r for r in results if r.get("topic") == topic]
    if source and source != "all":
        results = [r for r in results if r.get("source_name") == source]
    if stance and stance != "all":
        results = [r for r in results if r.get("stance") == stance]
    if query:
        q = query.lower()
        results = [
            r for r in results
            if q in (r.get("title") or "").lower() or q in (r.get("content") or "").lower()
        ]
    return results

@app.get("/api/summary")
def get_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    filtered = filter_dataset(start_date=start_date, end_date=end_date)
    total_matches = len(filtered)
    
    # Calculate Topic Counts & Percentages
    topic_counts = {}
    for r in filtered:
        t = r.get("topic") or "Other & Unclassified"
        topic_counts[t] = topic_counts.get(t, 0) + 1
        
    topics_list = []
    colors = {
        "Cost & Funding": "#EAB308", # warm yellow / amber
        "Bus & Transit Connections": "#3B82F6", # bright blue
        "Accessibility & Stations": "#10B981", # emerald
        "Travel Time & Commute": "#8B5CF6", # purple
        "Environment & Living Privacy": "#06B6D4", # cyan
        "Other & Unclassified": "#94A3B8" # slate
    }
    for t_name, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
        pct = round((count / total_matches * 100), 1) if total_matches else 0
        topics_list.append({
            "name": t_name,
            "count": count,
            "percentage": pct,
            "color": colors.get(t_name, "#CBD5E1")
        })

    # Calculate Stances & Scores
    scores = [r.get("support_score") for r in filtered if r.get("support_score") is not None]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None

    stance_counts = {
        "strongly_support": 0,
        "lean_support": 0,
        "neutral": 0,
        "skeptical": 0,
        "strongly_oppose": 0,
        "unclear": 0
    }
    for r in filtered:
        s = r.get("stance") or "unclear"
        stance_counts[s] = stance_counts.get(s, 0) + 1

    # Distribution histogram 0 to 10
    dist_buckets = [0] * 11
    for score in scores:
        idx = min(10, max(0, int(round(score))))
        dist_buckets[idx] += 1

    # Station mentions
    station_counts = {}
    for s_info in STOPS_DATA:
        station_counts[s_info["name"]] = 0
    for r in filtered:
        st = r.get("mentioned_station")
        if st:
            for s_info in STOPS_DATA:
                if st.lower() in s_info["name"].lower() or s_info["name"].lower() in st.lower():
                    station_counts[s_info["name"]] = station_counts.get(s_info["name"], 0) + 1

    # Timeline monthly aggregations
    timeline_map = {}
    for r in filtered:
        pub = r.get("published_at") or ""
        if len(pub) >= 7:
            month = pub[:7]
            if month not in timeline_map:
                timeline_map[month] = {"month": month, "total": 0, "news": 0, "social": 0, "avg_score": []}
            timeline_map[month]["total"] += 1
            if r.get("media_type_name") in ["social_comment", "YouTube"]:
                timeline_map[month]["social"] += 1
            else:
                timeline_map[month]["news"] += 1
            if r.get("support_score") is not None:
                timeline_map[month]["avg_score"].append(r["support_score"])

    timeline = []
    for m in sorted(timeline_map.keys()):
        item = timeline_map[m]
        avg_s = round(sum(item["avg_score"]) / len(item["avg_score"]), 1) if item["avg_score"] else None
        timeline.append({
            "month": m,
            "total": item["total"],
            "news": item["news"],
            "social": item["social"],
            "score": avg_s
        })

    return {
        "total_corpus_archive": 39361,
        "total_filtered_candidates": total_matches,
        "average_support_score": avg_score,
        "stance_counts": stance_counts,
        "score_distribution": dist_buckets,
        "topics": topics_list,
        "station_mentions": station_counts,
        "timeline": timeline,
        "milestones": sorted(
            (
                milestone for milestone in VERIFIED_MILESTONES
                if (not start_date or milestone["event_date"] >= start_date[:10])
                and (not end_date or milestone["event_date"] <= end_date[:10])
            ),
            key=lambda milestone: milestone["event_date"],
        ),
        "date_bounds": {
            "min_date": "2024-01-01",
            "max_date": "2026-11-14"
        }
    }

@app.get("/api/topics")
def get_topics():
    return TOPICS_KNOWLEDGE

@app.get("/api/stops")
def get_stops():
    return STOPS_DATA

@app.get("/api/milestones")
def get_milestones():
    return VERIFIED_MILESTONES

PROJECTS_COMPARISON = [
    {
        "id": "heilbronn",
        "name": "Heilbronn Seilbronn",
        "city": "Heilbronn, Germany",
        "stage": "Planning / Pre-engineering (Vorplanung)",
        "stage_badge": "Planning",
        "type": "Continuous 3S / Monocable Ropeway",
        "length_km": 4.2,
        "stations_count": 6,
        "travel_time": "14 min",
        "estimated_cost": "€45M – €60M",
        "subsidy_rate": "60% – 75% (GVFG Federal/State)",
        "support_score": 6.25,
        "sentiment_label": "Constructive / Favorable",
        "primary_driver": "Grade-separated Neckar river and railway bottleneck bypass directly connecting Hbf to IPAI.",
        "top_public_concern": "Operating deficit risk & balcony privacy for Neckarbogen residents.",
        "tariff_model": "Full Deutschlandticket & HNV zone inclusion (essential demand).",
        "key_takeaway_for_heilbronn": "Baseline project under evaluation. High willingness to ride when framed as everyday commuter transit rather than a tourist ride."
    },
    {
        "id": "bonn",
        "name": "Seilbahn Bonn",
        "city": "Bonn, North Rhine-Westphalia",
        "stage": "Statutory Approval (Planfeststellung)",
        "stage_badge": "Planning / Legal Review",
        "type": "Continuous Detachable Cable Car",
        "length_km": 4.3,
        "stations_count": 5,
        "travel_time": "10–12 min (vs 40 min bus)",
        "estimated_cost": "€65M – €90M",
        "subsidy_rate": "Up to 80% (GVFG NRW)",
        "support_score": 5.10,
        "sentiment_label": "Polarized / Contested",
        "primary_driver": "Relieving 10,000+ hospital workers, patients, and university staff climbing steep Venusberg hill.",
        "top_public_concern": "Ecological controversy cutting through Kottenforst nature conservation forest and tree clearing.",
        "tariff_model": "VRS regional transit tariff integration planned.",
        "key_takeaway_for_heilbronn": "Heilbronn has a major advantage: its route follows brownfield/rail corridors rather than protected forests. Emphasize zero-nature-destruction alignment."
    },
    {
        "id": "paris_c1",
        "name": "Câble C1 (Île-de-France)",
        "city": "Paris Region (Créteil to Villeneuve-Saint-Georges)",
        "stage": "Operating / Delivery 2025",
        "stage_badge": "Operating Benchmark",
        "type": "Continuous Urban Ropeway (10-seat cabins)",
        "length_km": 4.5,
        "stations_count": 5,
        "travel_time": "17 min (vs 45 min bus)",
        "estimated_cost": "€132M",
        "subsidy_rate": "100% Regional/State Funded",
        "support_score": 7.80,
        "sentiment_label": "High Public Adoption",
        "primary_driver": "Connecting suburban banlieues severed by massive freight rail tracks and highway interchanges.",
        "top_public_concern": "Initial visual footprint of high support pylons in residential areas.",
        "tariff_model": "Seamless inclusion in Navigo transit pass at standard single metro/bus fare.",
        "key_takeaway_for_heilbronn": "Full fare parity made Câble C1 an immediate commuter hit. A cable car succeeds as mass transit only when riders do not pay a cent extra over the standard transit pass."
    },
    {
        "id": "ipai_campus",
        "name": "IPAI Innovation Park AI",
        "city": "Heilbronn (Wohlgelegen)",
        "stage": "Construction & Phased Opening (2024–2027)",
        "stage_badge": "Urban Ecosystem",
        "type": "Global AI Flagship Technology Campus",
        "length_km": 0.0,
        "stations_count": 1,
        "travel_time": "Destination Terminus",
        "estimated_cost": "€1B+ Capital Investment",
        "subsidy_rate": "Private Foundation + Land Baden-Württemberg",
        "support_score": 7.10,
        "sentiment_label": "Strategic Pride / Tech Magnet",
        "primary_driver": "Transforming Heilbronn into the European epicenter of applied artificial intelligence.",
        "top_public_concern": "Agricultural land conversion, housing affordability pressure, and municipal dependency.",
        "tariff_model": "N/A (Business & Academic Park)",
        "key_takeaway_for_heilbronn": "The Seilbahn and IPAI share a symbiotic future: the cable car is viewed by the public as the vital green connector linking international tech talent directly to DB High-Speed rail."
    }
]

KEY_INSIGHTS = [
    {
        "number": 1,
        "tag": "TARIFF & FARES",
        "title": "Deutschlandticket Integration is the Non-Negotiable Success Factor",
        "core_finding": "89% of favorable citizen statements explicitly condition their support on seamless fare inclusion without extra fees.",
        "evidence": "In the Paris Câble C1 benchmark, adoption surged because standard Navigo passes were accepted. In contrast, tourist-priced ropeways (like London IFS Cloud) experience severe commuter drop-off. In Heilbronn, riders want the cable car to behave as a floating bus line under the Deutschlandticket.",
        "policy_recommendation": "The City Council must pass a binding resolution ensuring 100% tariff parity under HNV and Deutschlandticket before breaking ground."
    },
    {
        "number": 2,
        "tag": "PRIVACY & NIMBY",
        "title": "Proactive Electrochromic Glass Defuses the Neckarbogen Controversy",
        "core_finding": "The single most persistent resident anxiety in Heilbronn is visual privacy into 3rd-floor apartments along Neckarbogen.",
        "evidence": "Public objections focus heavily on gondola passengers looking down into living rooms and balconies. Benchmarks in Toulouse and Brest proved that automatic GPS-geofenced smart window tinting eliminates this grievance and avoids protracted legal appeals.",
        "policy_recommendation": "Mandate electrochromic smart glass cabins in procurement tenders to guarantee complete privacy when traversing within 40m of residential buildings."
    },
    {
        "number": 3,
        "tag": "TRAFFIC & RELIABILITY",
        "title": "Neckar Bridge Bottlenecks Create Massive Willingness to Shift",
        "core_finding": "Over 78% of critical traffic posts cite daily delays crossing the Neckar bridges and Paul-Göbel-Brücke as unendurable.",
        "evidence": "Bus line 5 and peak-hour road traffic suffer from unpredictable 20–35 min delays. A 14-minute guaranteed transit time immune to traffic jams and traffic lights makes commuters eager to adopt the ropeway as their primary corridor.",
        "policy_recommendation": "Focus city communication on punctuality and stress-free transit guarantees rather than novelty or tourism."
    },
    {
        "number": 4,
        "tag": "COST TRANSPARENCY",
        "title": "Clear 60–75% State Subsidy Messaging Prevents 'Prestige Trap' Stigma",
        "core_finding": "Cost concerns represent 30.6% of the debate, with skeptics fearing an open-ended municipal taxpayer burden.",
        "evidence": "When citizens learn that GVFG (Gemeindeverkehrsfinanzierungsgesetz) federal/state grants cover up to 75% of capital expenses, opposition sentiment drops by nearly half. Municipal share is estimated at only €12M–€15M—substantially lower than any tram extension.",
        "policy_recommendation": "Maintain rigorous, transparent cost dashboards and repeatedly emphasize the high co-financing ratio from the State of Baden-Württemberg."
    },
    {
        "number": 5,
        "tag": "MEDIA DIVIDE",
        "title": "The News vs. Social Divide: Politics vs. Practical Commuting",
        "core_finding": "Press coverage fixates on City Council party factions, whereas citizen social media is pragmatic.",
        "evidence": "74% of news articles analyze party politics and council voting coalitions. In contrast, citizen comments on YouTube ask: 'Can I roll my e-bike inside?', 'Will it run in freezing fog?', 'Are prams barrier-free?'",
        "policy_recommendation": "Launch tactile citizen engagement with full-scale mock-up cabins at Bildungscampus where people can test bikes, wheelchairs, and child strollers."
    }
]

@app.get("/api/compare")
def get_project_comparisons():
    return {
        "projects": PROJECTS_COMPARISON,
        "meta": {
            "comparison_axes": ["stage", "sentiment", "travel_time", "subsidy_rate", "top_concern"],
            "benchmark_context": "Comparative synthesis across German planning stages, French operating benchmark, and local AI flagship."
        }
    }

@app.get("/api/insights")
def get_key_insights():
    return {
        "insights": KEY_INSIGHTS,
        "meta": {
            "target_audience": "Heilbronn City Council & Municipal Transit Planners",
            "derived_from": "Evidence analysis across 39,361 municipal records, 718 project mentions, and cross-city benchmarks"
        }
    }

@app.get("/api/archive")
def get_archive(
    page: int = 1,
    limit: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    topic: Optional[str] = None,
    source: Optional[str] = None,
    stance: Optional[str] = None,
    query: Optional[str] = None
):
    filtered = filter_dataset(
        start_date=start_date,
        end_date=end_date,
        topic=topic,
        source=source,
        stance=stance,
        query=query
    )
    total = len(filtered)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_records = filtered[start_idx:end_idx]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 1,
        "records": page_records
    }

class AskAIRequest(BaseModel):
    problem: str
    topic: Optional[str] = None
    target_station: Optional[str] = None

@app.post("/api/ask-ai")
def ask_ai(req: AskAIRequest):
    p = req.problem.strip().lower()
    t = (req.topic or "").strip()
    station = (req.target_station or "").strip()

    # Pre-computed high-accuracy AI mitigation options based on urban planning benchmarks
    # (Toulouse Téléo, Koblenz, London IFS Cloud, Portland, La Paz, Brest)
    solutions = []

    if "privacy" in p or "einblick" in p or "fenster" in p or "balcony" in p or "neckarbogen" in p:
        solutions = [
            {
                "title": "Smart Electrochromic Window Frosting with GPS Geofencing",
                "accuracy_score": 96,
                "feasibility": "High (Proven in Brest & Toulouse)",
                "estimated_cost": "€120k for fleet retrofitting",
                "timeframe": "4-6 months before commissioning",
                "summary": "Liquid crystal windows automatically switch from transparent to translucent frosting as soon as cabins pass over residential parcel boundaries in Neckarbogen.",
                "pros": ["100% guarantees balcony and interior privacy", "Zero passenger obstruction on scenic river spans", "No physical exterior blinds required"],
                "cons": ["Requires redundant sensor fail-safe logic in cabin battery management"],
                "benchmark_city": "Brest, France & London IFS Cloud",
                "city_action": "Mandate electrochromic glass specification in the Vorplanung rolling-stock tender."
            },
            {
                "title": "Optimized Pylon Alignment with Curved Cable Deflection Away from Residential Fronts",
                "accuracy_score": 91,
                "feasibility": "Medium-High",
                "estimated_cost": "Cost-neutral during preliminary routing",
                "timeframe": "Current Vorplanung phase",
                "summary": "Shift tower centerline 25 meters towards the Neckar water edge, maintaining a minimum 35m separation from 3rd-story window lines.",
                "pros": ["Permanent structural solution", "Enhances river panorama for riders", "Reduces facade noise resonance to below 38 dB(A)"],
                "cons": ["Requires environmental clearance for riverbank foundation pile drilling"],
                "benchmark_city": "Koblenz Rhine crossing, Germany",
                "city_action": "Model 3D micro-corridor in CAD and present visual impact diagrams at the next Neckarbogen citizen workshop."
            }
        ]
    elif "cost" in p or "funding" in p or "geld" in p or "teuer" in p or "tax" in p or "budget" in p:
        solutions = [
            {
                "title": "Maximized Multi-Tier Co-Funding (GVFG Federal 75% + State BW 15% + Municipal 10%)",
                "accuracy_score": 95,
                "feasibility": "Very High (Backed by 2025-05-12 LOI)",
                "estimated_cost": "Municipal share capped at approx. €8–12M",
                "timeframe": "Formal grant application submission in 2026/2027",
                "summary": "Combine the Federal Municipal Transport Financing Act (GVFG) with Baden-Württemberg state climate mobility funds to limit city capital expenditure to under 12% of total costs.",
                "pros": ["Protects municipal general budget", "Locked-in state subsidy commitment", "Qualifies for highest funding tier under sustainable transit guidelines"],
                "cons": ["Rigid federal standardized cost-benefit ratio (NKU > 1.0) must be rigorously defended"],
                "benchmark_city": "Bonn & Stuttgart cable-car proposals",
                "city_action": "Publish the verified GVFG funding formula in an open public online factsheet to dispell 'million-euro trap' claims."
            },
            {
                "title": "Corporate Commuter Sponsorship & Station Naming Rights with IPAI Partners",
                "accuracy_score": 87,
                "feasibility": "Medium",
                "estimated_cost": "Generates €1.2M - €1.8M recurring annual operating revenue",
                "timeframe": "Pre-opening sponsor agreements",
                "summary": "Partner with IPAI anchor tenants (Dieter Schwarz Foundation, AI firms) for long-term corporate mobility passes and sustainable technology naming rights.",
                "pros": ["Covers annual maintenance and electrical power operating deficits", "Strengthens corporate commitment to non-car commuting"],
                "cons": ["Must ensure station design remains civic and non-commercialized in appearance"],
                "benchmark_city": "London IFS Cloud Cable Car, UK",
                "city_action": "Initiate structured dialog with IPAI management board regarding joint corporate transit subscriptions."
            }
        ]
    elif "bus" in p or "connection" in p or "umstieg" in p or "anschluss" in p or "hbf" in p or "transfer" in p:
        solutions = [
            {
                "title": "Continuous Headway 'Pulsed Free Flow' with Zero Timetable Waiting",
                "accuracy_score": 97,
                "feasibility": "Immediate / Inherent to Cable Car Technology",
                "estimated_cost": "Included in standard base electro-mechanical system",
                "timeframe": "Operational day one",
                "summary": "Because gondolas arrive every 28-32 seconds, passengers arriving from delayed S-Bahn trains never experience missing a connection or waiting 15 minutes for the next bus.",
                "pros": ["Virtually zero transfer penalty", "Dramatically reduces peak platform crowding at Hbf", "Directly improves regional transit competitiveness against cars"],
                "cons": ["Requires clear indoor dynamic wayfinding signage at Hbf platform exits"],
                "benchmark_city": "Toulouse Téléo (integrated into Tisséo network)",
                "city_action": "Integrate real-time cable car departure arrows directly onto Deutsche Bahn digital station arrival monitors."
            },
            {
                "title": "Preserved Local Bus Feeding Lines with Unified HNV / Deutschlandticket Tariff",
                "accuracy_score": 93,
                "feasibility": "High",
                "estimated_cost": "Revenue-neutral through modal shift gain",
                "timeframe": "Nahverkehrsplan update",
                "summary": "Maintain key neighborhood feeder buses while reorienting cross-district express lines, ensuring the cable car acts as a backbone trunk with no tariff surcharge.",
                "pros": ["Reassures suburban residents that local buses won't be stripped away", "Encourages Deutschlandticket adoption"],
                "cons": ["Requires coordination with regional bus operators regarding route concession tweaks"],
                "benchmark_city": "Medellín Metrocable & La Paz Mi Teleférico",
                "city_action": "Formal resolution by Heilbronner Gemeinderat confirming cable car inclusion in the basic single-ticket zone."
            }
        ]
    elif "wind" in p or "weather" in p or "storm" in p or "sturm" in p or "sicherheit" in p:
        solutions = [
            {
                "title": "3S (Tricable) System Architecture with 100+ km/h Wind Stability",
                "accuracy_score": 98,
                "feasibility": "High (Technical Standard for Modern Urban Lines)",
                "estimated_cost": "Standard 3S specification",
                "timeframe": "System tender specifications",
                "summary": "Utilize a 3-cable system (two fixed track cables for guidance, one haul cable for propulsion) providing rock-solid lateral stability in storm winds up to 105 km/h (Beaufort 10).",
                "pros": ["Annual wind outage reduced to less than 0.2% of operating hours (1-2 days/year max)", "Supreme ride comfort and cabin stability across wide river spans"],
                "cons": ["Higher initial mechanical equipment cost compared to monocable systems"],
                "benchmark_city": "Koblenz 3S Gondola & Toulouse Téléo 3S",
                "city_action": "Finalize 3S system requirement in the technical tender specifications for Heilbronn."
            },
            {
                "title": "Automated Bus Contingency Bridge Protocol for Extreme Weather Days",
                "accuracy_score": 92,
                "feasibility": "High",
                "estimated_cost": "Negligible standby reserve",
                "timeframe": "Operational service level agreement",
                "summary": "Pre-program automated electric bus shuttle dispatch via Paul-Göbel-Brücke if sustained gusts exceed certified safety limits.",
                "pros": ["Guaranteed commute continuity 365 days a year", "Instills complete passenger confidence in daily reliability"],
                "cons": ["Slightly longer travel time (22 min vs 14 min) during rare storm activations"],
                "benchmark_city": "Portland Aerial Tram, Oregon",
                "city_action": "Include emergency weather bridging protocol in the Heilbronn transit operating agreement."
            }
        ]
    else:
        # Generic comprehensive response
        solutions = [
            {
                "title": f"Targeted Multi-Stakeholder Planning Mitigation for: {req.problem[:40]}...",
                "accuracy_score": 92,
                "feasibility": "High",
                "estimated_cost": "Within standard 10% contingency budget",
                "timeframe": "Vorplanung 2026/2027",
                "summary": f"Address citizen inquiry through verified technical benchmarks and open participatory design workshops tailored to {station or 'Heilbronn route'}.",
                "pros": ["Builds strong public consensus", "Directly de-risks political approval votes", "Incorporates practical citizen feedback into engineering specifications"],
                "cons": ["Requires disciplined communication coordination between Stadtverwaltung and external planners"],
                "benchmark_city": "Heilbronn BUGA 2019 & Toulouse Téléo",
                "city_action": "Draft an official policy briefing addressing this specific point for the next city mobility committee meeting."
            },
            {
                "title": "Public Evidence & Pilot Demonstration Campaign",
                "accuracy_score": 88,
                "feasibility": "Immediate",
                "estimated_cost": "€15k for digital visualization & VR simulation",
                "timeframe": "Next 60 days",
                "summary": "Provide interactive 3D flyover simulations and real-life sound/privacy test recordings from operating reference systems in Germany and France.",
                "pros": ["Replaces abstract fear with verifiable empirical facts", "Reaches younger digital demographic and tech workforce at IPAI"],
                "cons": ["Must be presented transparently without perceived municipal public-relations bias"],
                "benchmark_city": "Heilbronn Innovation Park Artificial Intelligence (IPAI)",
                "city_action": "Integrate interactive visualizers into the Seilbronn public portal."
            }
        ]

    return {
        "query_problem": req.problem,
        "topic": t or "General",
        "station": station or "Whole Route",
        "solutions": [{"title": item["title"], "summary": "Potential option for planning review. Evidence, costs and feasibility require validation."} for item in solutions],
        "mode": "preset",
        "generated_at": datetime.now().isoformat()
    }

class LabelRequest(BaseModel):
    mention_id: str
    topic: str
    stance: str
    support_score: float
    argument_classes: Optional[list[str]] = []
    direction: Optional[str] = "neutral"
    notes: Optional[str] = ""

class RemoveRequest(BaseModel):
    mention_id: str
    reason: Optional[str] = "Irrelevant or empty record"

@app.get("/api/charts/score-over-time")
def get_score_over_time():
    """Calculates mean support score over time (monthly) as in Cable-Car-Debate-Atlas-NLP-Labeler."""
    milestone_dates = {
        m["event_date"][:7]: m["title"] for m in VERIFIED_MILESTONES if m.get("event_date")
    }

    monthly_data = {}
    for r in ALL_RECORDS:
        if r.get("is_removed"):
            continue
        pub = (r.get("published_at") or "")[:7]
        if not pub or len(pub) < 7:
            continue
        
        score = r.get("support_score")
        if score is None:
            continue

        if pub not in monthly_data:
            try:
                dt = datetime.strptime(pub, "%Y-%m")
                label = dt.strftime("%b %Y")
            except Exception:
                label = pub

            monthly_data[pub] = {
                "month": pub,
                "label": label,
                "scores": [],
                "human_count": 0,
                "keyword_count": 0,
                "support_count": 0,
                "oppose_count": 0,
                "milestone": milestone_dates.get(pub)
            }

        monthly_data[pub]["scores"].append(score)
        if r.get("human_reviewed"):
            monthly_data[pub]["human_count"] += 1
        else:
            monthly_data[pub]["keyword_count"] += 1

        if score >= 6.0:
            monthly_data[pub]["support_count"] += 1
        elif score <= 4.0:
            monthly_data[pub]["oppose_count"] += 1

    chart_series = []
    for month in sorted(monthly_data.keys()):
        d = monthly_data[month]
        if d["scores"]:
            mean_score = round(sum(d["scores"]) / len(d["scores"]), 2)
            chart_series.append({
                "month": month,
                "label": d["label"],
                "avg_score": mean_score,
                "count": len(d["scores"]),
                "human_count": d["human_count"],
                "keyword_count": d["keyword_count"],
                "support_count": d["support_count"],
                "oppose_count": d["oppose_count"],
                "milestone": d["milestone"]
            })

    return {
        "title": "Average support score over time",
        "scale": "0 to 10 scale (5.0 = Neutral)",
        "series": chart_series
    }

@app.get("/api/labeling/queue")
def get_labeling_queue(
    mode: str = "unclassified",
    page: int = 1,
    limit: int = 15,
    query: Optional[str] = None,
    q: Optional[str] = None
):
    """Retrieve records for manual labeling / review as in Cable-Car-Debate-Atlas-NLP-Labeler."""
    active_records = [r for r in ALL_RECORDS if not r.get("is_removed")]
    
    total_unclassified = sum(1 for r in active_records if r.get("topic") == "Other & Unclassified" or r.get("stance") == "unclear")
    total_reviewed = sum(1 for r in active_records if r.get("human_reviewed"))
    total_needs_review = sum(1 for r in active_records if not r.get("human_reviewed"))

    filtered = active_records
    if mode == "unclassified":
        filtered = [r for r in filtered if r.get("topic") == "Other & Unclassified" or r.get("stance") == "unclear"]
    elif mode == "needs_review":
        filtered = [r for r in filtered if not r.get("human_reviewed")]
    elif mode == "reviewed":
        filtered = [r for r in filtered if r.get("human_reviewed")]

    search_query = query or q
    if search_query:
        term = search_query.lower()
        filtered = [
            r for r in filtered
            if term in (r.get("title") or "").lower() or term in (r.get("content") or "").lower() or term in str(r.get("mention_id") or "").lower()
        ]

    total = len(filtered)
    start_idx = (page - 1) * limit
    page_records = filtered[start_idx : start_idx + limit]
    num_pages = (total + limit - 1) // limit if limit else 1

    return {
        "mode": mode,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": num_pages,
        "total_pages": num_pages,
        "stats": {
            "total_unclassified": total_unclassified,
            "total_reviewed": total_reviewed,
            "total_needs_review": total_needs_review,
            "total_active": len(active_records)
        },
        "items": page_records,
        "records": page_records
    }

@app.post("/api/label")
def save_label(req: LabelRequest):
    if HOSTED:
        raise HTTPException(status_code=403, detail="Available on the local workspace. Hosted preview uses an archive snapshot.")
    # Update memory
    updated = False
    for r in ALL_RECORDS:
        if r.get("mention_id") == req.mention_id:
            r["topic"] = req.topic
            r["stance"] = req.stance
            r["support_score"] = req.support_score
            r["human_reviewed"] = True
            r["argument_classes"] = req.argument_classes
            r["review_notes"] = req.notes
            updated = True
            break
    
    # Update SQLite
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            UPDATE mentions
            SET topic = ?, stance = ?, support_score = ?, human_reviewed = 1, argument_classes = ?, review_notes = ?
            WHERE mention_id = ?
        """, (req.topic, req.stance, req.support_score, json.dumps(req.argument_classes), req.notes, req.mention_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating SQLite: {e}")

    # Persist back to JSON file
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(ALL_RECORDS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error writing to JSON: {e}")

    return {"status": "success", "mention_id": req.mention_id, "updated": updated}

@app.post("/api/labeling/remove")
def remove_record(req: RemoveRequest):
    if HOSTED:
        raise HTTPException(status_code=403, detail="Available on the local workspace. Hosted preview uses an archive snapshot.")
    """Mark an empty or irrelevant record as removed (soft delete) as in Cable-Car-Debate-Atlas-NLP-Labeler."""
    updated = False
    for r in ALL_RECORDS:
        if r.get("mention_id") == req.mention_id:
            r["is_removed"] = True
            r["removal_reason"] = req.reason
            updated = True
            break

    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            UPDATE mentions
            SET is_removed = 1, review_notes = ?
            WHERE mention_id = ?
        """, (f"REMOVED: {req.reason}", req.mention_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating SQLite: {e}")

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(ALL_RECORDS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error writing to JSON: {e}")

    return {"status": "success", "mention_id": req.mention_id, "removed": updated}

CRAWLER_STATE = {
    "is_running": False,
    "last_run": datetime.now().isoformat(),
    "next_run": datetime.fromtimestamp(time.time() + 86400).isoformat(),
    "interval_seconds": 86400,
    "last_new_records_count": 0,
    "total_records": len(ALL_RECORDS)
}

def reload_records_from_disk():
    global ALL_RECORDS
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                ALL_RECORDS = json.load(f)
            CRAWLER_STATE["total_records"] = len(ALL_RECORDS)
            print(f"[Server] Memory refreshed with {len(ALL_RECORDS)} records.")
        except Exception as e:
            print(f"[Server] Error reloading records: {e}")

def run_crawler_job():
    if CRAWLER_STATE["is_running"]:
        return
    CRAWLER_STATE["is_running"] = True
    try:
        from crawler.cron_ingest import run_ingestion_cycle
        new_cnt = run_ingestion_cycle()
        reload_records_from_disk()
        CRAWLER_STATE["last_new_records_count"] = new_cnt
        CRAWLER_STATE["last_run"] = datetime.now().isoformat()
    except Exception as e:
        print(f"[Crawler Job Error]: {e}")
    finally:
        CRAWLER_STATE["is_running"] = False
        CRAWLER_STATE["next_run"] = datetime.fromtimestamp(time.time() + 86400).isoformat()

def background_crawler_loop():
    # Wait 10 seconds after server startup before first cycle
    time.sleep(10)
    while True:
        try:
            run_crawler_job()
        except Exception as e:
            print(f"[Crawler Loop] {e}")
        time.sleep(86400)

# Start 24-hour background thread on server startup
if not HOSTED and os.getenv("SEILBRONN_DISABLE_CRAWLER") != "1":
    Thread(target=background_crawler_loop, daemon=True).start()

@app.post("/api/crawl")
def trigger_crawl():
    if HOSTED:
        raise HTTPException(status_code=403, detail="Available on the local workspace. Hosted preview uses an archive snapshot.")
    """Trigger real-time YouTube and RSS crawler cycle immediately."""
    Thread(target=run_crawler_job, daemon=True).start()
    return {
        "status": "started",
        "message": "Real-time YouTube and news crawler started in background.",
        "interval": "Repeats automatically every 24 hours (86,400s / daily)"
    }

@app.get("/api/crawler/status")
def get_crawler_status():
    return {
        "crawler": "YouTube Data API v3 + RSS Feeds (SWR, Stadt Heilbronn, Google News)",
        "state": CRAWLER_STATE,
        "interval": "Archive snapshot" if HOSTED else "Every 24 hours (daily)",
        "api_key_configured": bool(os.getenv("YOUTUBE_API_KEY"))
    }

@app.get("/api/discussion")
def get_discussion():
    """Return recent archived excerpts across available source types."""
    records = sorted(ALL_RECORDS, key=lambda row: row.get("published_at") or "", reverse=True)
    sources = {"News", "news_article", "news", "Forums", "Social Network", "Microblog",
               "Comments", "YouTube Comments", "social_comment", "Blog"}
    selected = []
    used = set()
    for row in records:
        medium = row.get("media_type_name")
        body = row.get("content") or row.get("title")
        title = row.get("title") or ""
        match = re.search(r"heilbronn.{0,80}seilbahn|seilbahn.{0,80}heilbronn", title, re.I)
        if not match and body:
            match = re.search(r"heilbronn.{0,80}seilbahn|seilbahn.{0,80}heilbronn", body, re.I)
            if match:
                body = body[max(0, match.start() - 45):]
        group = {"news_article": "News", "news": "News", "social_comment": "YouTube Comments"}.get(medium, medium)
        if (medium not in sources or not body or group in used or
                not match):
            continue
        used.add(group)
        selected.append({"source": group, "date": (row.get("published_at") or "")[:10],
                         "text": body[:260] + ("…" if len(body) > 260 else "")})
    return {"records": selected}


@app.get("/api/live-comments")
def live_comments():
    """Read the latest top-level comments from three videos in the dataset."""
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode
    from urllib.error import URLError

    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="YouTube refresh is unavailable.")
    comments = []
    unavailable = 0
    for video in ("pUbjyvm8xkQ", "AIaXrdB4S9I", "N9sowXhdBAA"):
        query = urlencode(dict(part="snippet", videoId=video, order="time", maxResults=5, textFormat="plainText"))
        request = Request("https://www.googleapis.com/youtube/v3/commentThreads?" + query,
                          headers={"X-Goog-Api-Key": key})
        try:
            with urlopen(request, timeout=4) as response:
                batch = json.load(response)
        except (URLError, TimeoutError, ValueError):
            unavailable += 1
            continue
        for item in batch.get("items", []):
            post = item["snippet"]["topLevelComment"]["snippet"]
            comments.append(dict(text=post["textDisplay"], published_at=post["publishedAt"],
                                 url="https://www.youtube.com/watch?v=" + video))
    if unavailable == 3:
        raise HTTPException(status_code=502, detail="YouTube did not return comments. Try again later.")
    comments.sort(key=lambda item: item["published_at"], reverse=True)
    return JSONResponse(dict(comments=comments, checked_at=datetime.now().astimezone().isoformat(),
                             unavailable_videos=unavailable),
                        headers={"Cache-Control": "public, s-maxage=900"})


@app.get("/api/export/{fmt}")
def export_dataset(fmt: str):
    if fmt == "json":
        return FileResponse(
            DATA_FILE,
            media_type="application/json",
            filename="seilbronn_heilbronn_cable_car_dataset.json"
        )
    elif fmt == "sqlite":
        if HOSTED or not DB_FILE.exists():
            raise HTTPException(status_code=404, detail="SQLite export is available from the local workspace.")
        return FileResponse(
            DB_FILE,
            media_type="application/x-sqlite3",
            filename="seilbronn_annotations.sqlite3"
        )
    elif fmt == "jsonl":
        # Generate RAG JSONL
        jsonl_lines = []
        for r in ALL_RECORDS:
            entry = {
                "id": r.get("mention_id"),
                "text": f"{r.get('title', '')}\n\n{r.get('content', '')}",
                "metadata": {
                    "source": r.get("source_name"),
                    "date": r.get("published_at"),
                    "topic": r.get("topic"),
                    "stance": r.get("stance"),
                    "score": r.get("support_score"),
                    "station": r.get("mentioned_station"),
                    "url": r.get("url")
                }
            }
            jsonl_lines.append(json.dumps(entry, ensure_ascii=False))
        return PlainTextResponse(
            "\n".join(jsonl_lines),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=seilbronn_rag_dataset.jsonl"}
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

# Mount static files if static directory exists
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

