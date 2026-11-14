# 🔴 ALGOX: Mars Colony Emergency Response
### Autonomous Dual-Engine Hybrid Scheduler & Mission Control Dashboard

![Colony Safety Score](https://img.shields.io/badge/Efficiency-~76%25-brightgreen)
![Validation Status](https://img.shields.io/badge/Section%202%20Rules-100%25%20PASS-emerald)
![Reproducibility](https://img.shields.io/badge/Seed-Deterministic%20(42)-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Flask](https://img.shields.io/badge/Backend-Flask-orange)

An end-to-end incident response optimization platform for the Mars Colony Emergency Scheduling Challenge (ALGO-X). Combines a dual-engine metaheuristic solver with an interactive real-time mission control telemetry dashboard.

---

## 🚀 Features

- **Dual-Engine Hybrid Scheduler:**
  - **Engine A (Beam Search + Local 2-Opt):** Independent-crew beam search exploring multi-order permutations with task swaps and block insertions.
  - **Engine B (Dynamic Priority Dispatch + Simulated Annealing):** Urgency-driven decay rate dispatch with cross-crew load balancing and **Zero-Point Parking**.
  - **Auto-Max Selector:** Runs both engines and deterministically outputs the strictly highest-scoring schedule.
- **Strict Rule Compliance:** Automatically verifies all 7 Section 2 rules (no duplicates, no crew overlaps, correct $2\times$ non-matching duration, start $\ge$ arrival, strictly sorted by start time).
- **Mission Control Web Dashboard:**
  - Real-time telemetry metric cards (Total incidents, critical incidents $\ge 8$, colony safety score, average wait time, schedule makespan).
  - **Waiting vs. Points Earned Scatter Plot** with automated callout for largest losses.
  - **Crew Utilization Cards** with active working durations and animated capacity bars.
  - **Interactive Gantt Timeline** with time tick markers and instant hover cards.
  - **Live Search & Filter Table** with color-coded severity pills.
  - **One-Click JSON Export** producing judge-ready `submission.json`.
- **100% Deterministic Reproducibility:** Uses fixed random seed (`42`) as required by Rule 5.

---

## 📊 Benchmark Results

| Dataset | Total Incidents | Mathematical Limit (Wait=0) | Safety Score Achieved | Efficiency | Validation |
|---|---|---|---|---|---|
| **sample1.csv** | 400 | 1899 | **1,450.77** | **~76.4%** | ✅ PASS (0 errors) |
| **sample2.csv** | 400 | 1963 | **1,085.17** | **~55.3%** | ✅ PASS (0 errors) |
| **sample3.csv** | 400 | 1867 | **1,298.08** | **~69.5%** | ✅ PASS (0 errors) |

---

## 🛠️ Installation & Quickstart

### 1. Setup Virtual Environment & Dependencies
```bash
git clone https://github.com/yashwan7/mars-elementry.git
cd mars-elementry
pip install -r requirements.txt
```

### 2. Launch the Mission Control Web App
```bash
python app.py
```
Open **[http://localhost:5050](http://localhost:5050)** in your browser, drag and drop any incident CSV file, and click **"GENERATE OPTIMAL SCHEDULE"**.

### 3. Command Line Interface (CLI)
You can also run the solver directly in your terminal:
```bash
python solver.py data/sample1.csv submission.json 8000 --seed=42
```

---
![Uploading image.png…]()

## 📁 Repository Structure

```
├── app.py                  # Flask web server and REST API
├── solver.py               # Dual-Engine Hybrid Scheduler & Rule Validator
├── requirements.txt        # Python dependencies
├── VIVA_PREP_GUIDE.md      # Comprehensive Viva preparation script & Q&A
├── templates/
│   └── index.html          # Mission Control Web Dashboard (Chart.js + Gantt)
└── data/
    ├── sample1.csv         # Benchmark dataset 1 (400 incidents)
    ├── sample2.csv         # Benchmark dataset 2 (400 incidents)
    └── sample3.csv         # Benchmark dataset 3 (400 incidents)
```

---

## ⚖️ License
MIT License. Created for the ALGO-X Challenge.

