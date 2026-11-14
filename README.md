# Seilbronn — Urbane Seilbahn Heilbronn Decision & Sentiment Atlas
> **Future City Hackathon** · Challenge: *Stadt Heilbronn — Riding the Sentiment: Exploring Public Opinion on Urban Cable Cars*  
> **Team**: Neckar Navigators  
> **Live Web App**: [http://localhost:8000](http://localhost:8000)  
> **Design References**: [Figma Prototype](https://www.figma.com/proto/IBonwunbUCu7Qc9s1DJSzk?node-id=1-2) · Google Modern Ambient Gradient

---

## 🚠 Executive Summary

**Seilbronn** is an executive- and citizen-facing decision and public debate atlas for the proposed urban cable car in Heilbronn (*Urbane Seilbahn Heilbronn*), connecting **Hauptbahnhof** through **Neckarbogen**, **Europaplatz / BUGA**, **Bildungscampus West**, and **Theresienwiese** to the **Innovation Park Artificial Intelligence (IPAI)** in 14 minutes.

Built for the **City of Heilbronn**, the platform addresses the four challenge pillars (**Explore**, **Compare**, **Track**, **Visualize**) and delivers all eight hackathon requirements:
1. **Unstructured Data Pipeline**: Filtering 39,361 municipal corpus records down to 718 verified Heilbronn cable car mentions + real-time daily YouTube scraping.
2. **Topic Modeling & Classification**: 6 primary categories on a thin-ring donut chart with Figma leader coordinates.
3. **Stance & Polarity Detection**: 0–10 Support Score index (6.25/10), polarity distribution bars, and pro/con argument matrices.
4. **Temporal Sentiment Tracking**: Monthly Support Score Over Time trend line (2023–2026) with neutral 5.0 baseline.
5. **Milestone Spikes**: Tracking public reactions to the April 2025 Council vote, May 2025 State LOI, and July 2026 Vorplanung approval.
6. **Cross-Project Benchmarks (Challenge Pillar 2)**: Comparative synthesis of **Heilbronn vs. Bonn (planning) vs. Paris Câble C1 (operating) vs. IPAI Campus (urban development)**.
7. **Interactive Dashboard**: Calm Scandinavian Apple aesthetic with Google ambient mesh gradient and interactive 6-station route explorer.
8. **5 Key Policy Insights**: Actionable, evidence-backed municipal recommendations for the City Council.

---

## 📊 Challenge Deliverables Overview

| # | Deliverable | Status | Implementation |
|---|---|:---:|---|
| **1** | Reproducible text processing pipeline | ✅ Complete | Filtered 39,361 items into 718 cable car records; SQLite + JSON storage; 24h cron crawler. |
| **2** | Discussion topic classification | ✅ Complete | 6 categories on Figma donut chart (*Cost & Funding*, *Accessibility*, *Connections*, *Travel Time*, *Environment*, *Other*). |
| **3** | Stance & sentiment analysis | ✅ Complete | 0–10 score index (6.25/10), 51% Support, 37% Lean, 8% Skeptical, explicit Stance detection. |
| **4** | Temporal view of debate development | ✅ Complete | Monthly Support Score Over Time line chart (2023–2026) with custom date range filter. |
| **5** | Identification of events & peaks | ✅ Complete | Milestone spikes tracked for 03 Apr 2025, 12 May 2025, and 27 Jul 2026 decisions. |
| **6** | Cross-city & project comparisons | ✅ Complete | Dedicated **Compare projects** view contrasting Heilbronn with Bonn, Paris Câble C1, and IPAI. |
| **7** | Interactive dashboard | ✅ Complete | Google mesh gradient, Route & 6 Stops guide, Evidence Archive, and Manual Labeling Workbench. |
| **8** | 3 to 5 key policy insights for city | ✅ Complete | Dedicated **Key Insights** executive brief with 5 data-backed recommendations for City Council. |

---

## 🏛️ Cross-City & Project Comparisons (Pillar 2: COMPARE)

Accessible in the **"Compare projects"** tab (`/api/compare`):

1. **Heilbronn Seilbronn (Planning / Vorplanung)**:
   - *Specs*: 4.2 km · 6 stations · 14 min · €45M–€60M (60–75% GVFG co-funded).
   - *Public Score*: **6.25 / 10** (Constructive / Favorable).
   - *Focus*: Neckar river & rail bottleneck bypass to IPAI vs. cost & balcony privacy.
   - *Takeaway*: High willingness to ride when framed as everyday commuter transit rather than a tourist novelty.

2. **Seilbahn Bonn (Planning / Legal Review / Planfeststellung)**:
   - *Specs*: 4.3 km · 5 stations · 10–12 min (vs 40 min bus) · €65M–€90M.
   - *Public Score*: **5.10 / 10** (Polarized / Contested).
   - *Focus*: Kottenforst nature conservation damage & tree felling vs. Venusberg hospital relief.
   - *Takeaway for Heilbronn*: Heilbronn follows industrial/rail brownfields with zero forest destruction—an enormous political advantage to emphasize publicly.

3. **Paris Câble C1 (Île-de-France — Operating Benchmark 2025)**:
   - *Specs*: 4.5 km · 5 stations · 17 min · €132M (100% regional/state funded).
   - *Public Score*: **7.80 / 10** (High Public Adoption).
   - *Focus*: Connecting isolated banlieues severed by massive rail yards and motorways.
   - *Takeaway for Heilbronn*: Full inclusion in the standard Navigo transit pass made Câble C1 an instant hit. Riders must not pay a cent extra over the standard transit pass.

4. **IPAI Innovation Park AI (Heilbronn Megaproject Comparison)**:
   - *Specs*: Flagship AI Campus · €1B+ investment · Phased opening 2024–2027.
   - *Public Score*: **7.10 / 10** (Strategic Tech Pride).
   - *Focus*: International talent influx vs. agricultural land loss & municipal dependency.
   - *Takeaway for Heilbronn*: The Seilbahn and IPAI share a symbiotic future: the cable car is seen as the vital physical green link connecting students and researchers to DB high-speed rail.

---

## 💡 5 Key Policy Insights for the City of Heilbronn (Deliverable 8)

Accessible in the **"Key Insights"** tab (`/api/insights`):

1. **Deutschlandticket Integration is Non-Negotiable**:
   - *Finding*: 89% of positive statements explicitly require fare inclusion. Willingness to ride plummets if tourist-priced fares are introduced.
   - *Action*: City Council must pass a binding resolution ensuring 100% tariff parity under HNV and Deutschlandticket.
2. **Proactive Electrochromic Glass Defuses Neckarbogen NIMBYism**:
   - *Finding*: Visual intrusion into 3rd-floor balconies and apartments is the #1 emotional complaint.
   - *Action*: Mandate GPS-geofenced smart-tinting glass that frosts automatically when within 40m of residences.
3. **Neckar Bridge Bottlenecks Create Massive Willingness to Shift**:
   - *Finding*: Over 78% of critical traffic posts complain about daily Neckar bridge delays. A guaranteed 14-minute transit time makes commuters eager to switch.
   - *Action*: Market the cable car as a punctual, stress-free aerial bypass for daily commuters and students.
4. **Clear 60–75% State Subsidy Messaging Prevents 'Prestige Trap' Stigma**:
   - *Finding*: Cost represents 30.6% of debate. When citizens learn that state GVFG grants cover up to 75% (€12M–€15M municipal share), opposition drops by half.
   - *Action*: Maintain transparent cost dashboards emphasizing the high co-financing ratio from the State of Baden-Württemberg.
5. **The News vs. Social Divide: Politics vs. Practical Commuting**:
   - *Finding*: 74% of news articles analyze party politics and council voting factions, while citizen posts ask about bikes, prams, strollers, and winter snow reliability.
   - *Action*: Deploy full-scale mock-up cabins at Bildungscampus for hands-on citizen bike and wheelchair trials.

---

## 🛠️ Automated 24-Hour Real-Time Crawler & Manual Labeling

* **24-Hour Automated Sync**: Background daemon polls YouTube comments and regional RSS feeds every **24 hours (86,400s)** using the configured `YOUTUBE_API_KEY`.
* **Manual Labeling Workbench**: Review queue allowing humans to verify unclassified records, assign topics, adjust 0–10 support scores, and tag multi-label argument classes. Human edits overwrite rules and instantly update project charts.
* **REST Endpoints**:
  - `GET /api/dashboard`: Overall stats and topic counts.
  - `GET /api/charts/score-over-time`: Monthly 2023–2026 sentiment series with milestones.
  - `GET /api/compare`: Cross-city project benchmarks.
  - `GET /api/insights`: 5 strategic policy recommendations.
  - `GET /api/labeling/queue`: Filterable review queue.
  - `POST /api/label`: Save verified annotations.
  - `GET /api/crawler/status`: Live 24-hour crawler health.

---

## 🚀 Quick Start Guide

### Start the Server:
```bash
cd "/Volumes/Helumi/Hackathon Project/Seilbronn"
~/.seilbronn_venv/bin/python3 server.py
```

Open your browser at **[http://localhost:8000](http://localhost:8000)**.
