# NFL Totals Projections

A command-line NFL game total projection model that estimates each team’s score and the combined game total using:
- **EPA (season + last 5)**
- **Success Rate (SR) adjustment**
- **Pass rate tendency + PROE + defensive matchup**
- **Pace-driven plays projection**
- **Spread-based game script tweaks**
- **Weather penalty**
- **Basic injury modifiers**

All percentages are handled as **decimals** (e.g., `0.48 = 48%`, `0.03 = 3%`).

---

## Features

- **Team score projection** using blended offensive/defensive EPA and expected play volume
- **Weighted recency**: season vs last-5 EPA/SR is weighted by games played
- **Expected pass rate** driven by:
  - team pass rate + PROE
  - opponent pass rate allowed vs league average
  - spread-based script adjustment
- **Expected plays** driven by both teams’ pace and spread magnitude
- **Weather adjustment** subtracts points for wind/temp/precipitation
- **Injury knobs** for QB, elite pass-catchers, OL, and EDGE defenders
- **Input overrides** if CSV data is missing (pace, def pass rate allowed)

---

## Requirements

- Python 3.9+ (any recent Python 3 should work)
- No external libraries (uses only the standard library)

---

## Data Files (CSV Inputs)

Place these files in the **same folder** as the script (or update filenames in code):

### 1) Team Tendencies
- **`pass.csv`** (loaded by `load_team_tendencies`)
- Expected columns (flexible names supported):
  - Team identifier: `Team` / `team` / `Abbr` / `abbr`
  - Pass rate: `Pass Rate` or `pass_rate`
  - PROE: `PROE` or `proe`
  - Pace: `Pace` or `pace` (plays per game)
  - Defensive pass rate allowed: `Opp Pass Rate` / `opp_pass_rate` / `Def Pass Rate Against`

> Pass Rate / PROE / Opp Pass Rate can be `%` strings or decimals; parser will normalize.

### 2) RBSDM-style EPA + Success Rate
Loaded by `load_rbsdm_stats` for each file:

- **`oszn.csv`** = offense season
- **`ol5.csv`** = offense last 5
- **`dszn.csv`** = defense season
- **`dl5.csv`** = defense last 5

Expected columns (multiple aliases supported):
- Team identifier: `Team` / `team` / `Abbr` / `abbr`
- Dropback EPA: `Dropback EPA` / `dropback_epa` / `Dropback` / `dropback`
- Dropback SR: `Dropback SR` / `dropback_sr` / `Success R Dropback` / `Dropback Success Rate`
- Rush EPA: `Rush EPA` / `rush_epa` / `Rush` / `rush`
- Rush SR: `Rush SR` / `rush_sr` / `Rush Success Rate`

---

## How It Works (High Level)

1. **Load + normalize CSVs**
   - `parse_value()` converts numbers like `48%` → `0.48`, handles blanks/NA safely.
2. **Merge all team data**
   - `merge_team_data()` creates one unified dict per team.
3. **Project each team score**
   - `project_team_score()`:
     - weights offense EPA by **team games played**
     - weights defense EPA by **opponent games played**
     - computes expected pass rate and plays
     - applies injury + home/away adjustments
     - converts EPA + play volume into points
     - adds SR-based points adjustment
4. **Project total**
   - team A score + team B score − weather adjustment

---

## Key Model Components

### Net EPA (offense vs defense)
```python
((off_epa * 1.6) + (def_epa_allowed * 1.0)) / 2.6
