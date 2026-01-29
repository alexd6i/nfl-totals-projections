import csv
import os

def calculate_net_epa(off_epa, def_epa_allowed):
    """
    Applies the 1.6 predictive multiplier for offense vs defense.
    Offensive efficiency is more 'sticky' and predictive than defense.
    """
    return ((off_epa * 1.6) + (def_epa_allowed * 1.0)) / 2.6

def calculate_weighted_epa(season_epa, last_5_epa, games_played):
    """
    Weights season vs last 5 games EPA based on sample size and recency
    """
    if games_played <= 5:
        return season_epa
    elif games_played <= 10:
        return (season_epa * 0.65) + (last_5_epa * 0.35)
    elif games_played <= 14:
        return (season_epa * 0.50) + (last_5_epa * 0.50)
    else:
        return (season_epa * 0.40) + (last_5_epa * 0.60)

def calculate_expected_pass_rate(team_pass_rate, proe, def_pass_rate_against, league_avg_pass_rate, spread):
    """
    Calculates expected pass rate using team tendency, defense matchup, and game script
    All inputs should be decimals (0.62 = 62%)
    """
    team_tendency = team_pass_rate + proe
    defense_influence = def_pass_rate_against - league_avg_pass_rate
    base_expected = (team_tendency * 0.6) + ((team_pass_rate + defense_influence) * 0.4)

    # Spread adjustment
    spread_adjustment = 0.0
    if spread >= 7:
        spread_adjustment = 0.05
    elif spread >= 4:
        spread_adjustment = 0.03
    elif spread <= -7:
        spread_adjustment = -0.04
    elif spread <= -4:
        spread_adjustment = -0.02

    return base_expected + spread_adjustment

def calculate_expected_plays(team_pace, opp_pace, spread):
    """
    Calculates expected total plays per team based on pace and spread
    """
    base_plays = (team_pace + opp_pace) / 2

    pace_adjustment = 0.0
    if abs(spread) <= 3:
        pace_adjustment = 3.0
    elif abs(spread) >= 10:
        pace_adjustment = -4.0

    return base_plays + pace_adjustment

def calculate_weather_adjustment(wind_mph, temp_f, precipitation):
    """
    Returns points to subtract from total based on weather conditions
    """
    adjustment = 0.0

    if wind_mph >= 20:
        adjustment += 6.0
    elif wind_mph >= 15:
        adjustment += 3.0
    elif wind_mph >= 10:
        adjustment += 1.0

    if temp_f < 0:
        adjustment += 2.0

    precip_impact = {
        "heavy_rain": 3.0,
        "light_snow": 2.0,
        "heavy_snow": 4.0,
        "blizzard": 8.0
    }
    adjustment += precip_impact.get(precipitation, 0.0)

    return adjustment

def calculate_success_rate_adjustment(success_rate, league_avg=0.46, weight=55):
    """
    Adjusts projected score based on success rate.

    NOTE: With this formula, weight is "points per 1.00 (100%) SR differential".
    Example: +0.01 SR => +0.01 * 55 = +0.55 points (modest impact).
    """
    differential = success_rate - league_avg
    return differential * weight

def parse_value(value, is_percentage=False):
    """
    Safely parse numeric values, handling percentages and various formats
    Returns decimal value (e.g., 0.48 for 48%)
    """
    if value is None or value == '':
        return 0.0

    # If already a float/int, return it
    if isinstance(value, (int, float)):
        return float(value)

    # Convert string
    value = str(value).strip()

    # Handle empty strings
    if not value or value.lower() in ['na', 'n/a', '-', 'none']:
        return 0.0

    # Remove percentage sign if present
    if '%' in value:
        value = value.replace('%', '').strip()
        try:
            return float(value) / 100.0
        except ValueError:
            print(f"⚠️  Warning: Could not parse percentage '{value}', using 0.0")
            return 0.0

    # Try to convert to float
    try:
        result = float(value)
        # If marked as percentage but no % sign, assume it needs conversion
        if is_percentage and result > 1.0:
            return result / 100.0
        return result
    except ValueError:
        print(f"⚠️  Warning: Could not parse value '{value}', using 0.0")
        return 0.0

def load_team_tendencies(csv_file='NFL Team Tendenciesexport20251229.csv'):
    """
    Load pass rate and PROE from tendencies file
    All values standardized to decimals (0.62 = 62%)
    """
    tendencies = {}

    if not os.path.exists(csv_file):
        print(f"⚠️  '{csv_file}' not found")
        return None

    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Find team name
                team = None
                for col in ['Team', 'team', 'Abbr', 'abbr']:
                    if col in row and row[col]:
                        team = row[col].strip()
                        break

                if team:
                    tendencies[team] = {
                        'pass_rate': parse_value(row.get('Pass Rate', row.get('pass_rate', 0)), is_percentage=True),
                        'proe': parse_value(row.get('PROE', row.get('proe', 0)), is_percentage=True),
                        'pace': parse_value(row.get('Pace', row.get('pace', 0))),
                        'def_pass_rate_against': parse_value(
                            row.get('Opp Pass Rate', row.get('opp_pass_rate', row.get('Def Pass Rate Against', 0))),
                            is_percentage=True
                        )
                    }

        return tendencies

    except Exception as e:
        print(f"❌ Error loading tendencies: {e}")
        return None

def load_rbsdm_stats(csv_file):
    """
    Load EPA and success rate stats from rbsdm CSV files
    All values standardized to decimals (0.48 = 48% SR)
    """
    stats = {}

    if not os.path.exists(csv_file):
        print(f"⚠️  '{csv_file}' not found")
        return None

    # Define team aliases for consistent mapping
    team_aliases = {
        'LA': 'LAR',   # Map 'LA' to 'LAR'
        'WSH': 'WAS',  # Example for Washington
        # Add other aliases as needed
    }

    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Find team identifier
                team = None
                for team_col in ['Team', 'team', 'Abbr', 'abbr']:
                    if team_col in row and row[team_col]:
                        team = row[team_col].strip()
                        break

                # Apply alias if one exists
                if team in team_aliases:
                    team = team_aliases[team]

                if team and team != 'Team':  # Skip header rows
                    # Try multiple column name variations
                    dropback_epa = parse_value(
                        row.get('Dropback EPA') or row.get('dropback_epa') or row.get('Dropback') or row.get('dropback')
                    )

                    dropback_sr = parse_value(
                        row.get('Dropback SR') or row.get('dropback_sr') or row.get('Success R Dropback') or row.get('Dropback Success Rate'),
                        is_percentage=True
                    )

                    rush_epa = parse_value(
                        row.get('Rush EPA') or row.get('rush_epa') or row.get('Rush') or row.get('rush')
                    )

                    rush_sr = parse_value(
                        row.get('Rush SR') or row.get('rush_sr') or row.get('Rush Success Rate'),
                        is_percentage=True
                    )

                    stats[team] = {
                        'dropback_epa': dropback_epa,
                        'dropback_sr': dropback_sr,
                        'rush_epa': rush_epa,
                        'rush_sr': rush_sr
                    }

        return stats

    except Exception as e:
        print(f"❌ Error loading {csv_file}: {e}")
        return None

def merge_team_data(tendencies, off_season, off_l5, def_season, def_l5):
    """
    Merge all CSV data into unified team stats
    All values in decimal format
    """
    all_teams = {}

    if not all([tendencies, off_season, off_l5, def_season, def_l5]):
        print("❌ Error: Some CSV files failed to load")
        return None

    # Get all unique team names
    all_team_names = set(tendencies.keys())

    for team in all_team_names:
        # Find matching team in each CSV
        off_s = off_season.get(team, {})
        off_l = off_l5.get(team, {})
        def_s = def_season.get(team, {})
        def_l = def_l5.get(team, {})
        tend = tendencies.get(team, {})

        # Debug prints for selected teams
        if team in ['ATL', 'LAR']:
            print(f"\n--- Debugging Data for {team} ---")
            print(f"  Tendencies: {tend}")
            print(f"  Offense Season: {off_s}")
            print(f"  Offense Last 5: {off_l}")
            print(f"  Defense Season: {def_s}")
            print(f"  Defense Last 5: {def_l}")

        all_teams[team] = {
            # From tendencies (all decimals)
            'pass_rate': tend.get('pass_rate', 0.60),
            'proe': tend.get('proe', 0.0),
            'pace': tend.get('pace'),
            'def_pass_rate_against': tend.get('def_pass_rate_against'),

            # Offensive stats (all decimals)
            'season_pass_epa': off_s.get('dropback_epa', 0.0),
            'last5_pass_epa': off_l.get('dropback_epa', 0.0),
            'season_run_epa': off_s.get('rush_epa', 0.0),
            'last5_run_epa': off_l.get('rush_epa', 0.0),
            'season_pass_success': off_s.get('dropback_sr', 0.46),
            'last5_pass_success': off_l.get('dropback_sr', 0.46),
            'season_run_success': off_s.get('rush_sr', 0.43),
            'last5_run_success': off_l.get('rush_sr', 0.43),

            # Defensive stats (all decimals)
            'def_season_pass_epa': def_s.get('dropback_epa', 0.0),
            'def_last5_pass_epa': def_l.get('dropback_epa', 0.0),
            'def_season_run_epa': def_s.get('rush_epa', 0.0),
            'def_last5_run_epa': def_l.get('rush_epa', 0.0),
        }

        if team in ['ATL', 'LAR']:
            print(f"  Merged Data for {team}: {all_teams[team]}")

    return all_teams

# UPDATED: now takes team_games_played and opp_games_played separately
def project_team_score(team_stats, opp_stats, is_home, team_games_played, opp_games_played,
                       spread, qb_out, elite_wr_out, ol_missing, edge_missing,
                       pts_per_play_base, league_avg_pass_rate, home_strength="average",
                       pace_override=None, opp_pace_override=None, def_pass_rate_override=None):
    """
    Project team score using merged stats
    All percentage values in decimal format (0.48 = 48%)
    """

    # Use overrides if provided, otherwise use from stats
    team_pace = pace_override if pace_override is not None else team_stats.get('pace', 65.0)
    opp_pace = opp_pace_override if opp_pace_override is not None else opp_stats.get('pace', 65.0)
    def_pass_rate_against = def_pass_rate_override if def_pass_rate_override is not None else opp_stats.get('def_pass_rate_against', 0.60)

    # Safety check: ensure no zero pace
    if team_pace == 0 or team_pace is None:
        team_pace = 62.0
    if opp_pace == 0 or opp_pace is None:
        opp_pace = 62.0

    # Extract stats (all decimals)
    team_pass_rate = team_stats['pass_rate']
    proe = team_stats['proe']

    # Weight EPA:
    # - offense using TEAM games played
    # - defense using OPPONENT games played
    o_pass = calculate_weighted_epa(team_stats['season_pass_epa'], team_stats['last5_pass_epa'], team_games_played)
    o_run  = calculate_weighted_epa(team_stats['season_run_epa'],  team_stats['last5_run_epa'],  team_games_played)

    d_pass = calculate_weighted_epa(opp_stats['def_season_pass_epa'], opp_stats['def_last5_pass_epa'], opp_games_played)
    d_run  = calculate_weighted_epa(opp_stats['def_season_run_epa'],  opp_stats['def_last5_run_epa'],  opp_games_played)

    # Weight success rates (team only)
    pass_success = calculate_weighted_epa(team_stats['season_pass_success'], team_stats['last5_pass_success'], team_games_played)
    run_success  = calculate_weighted_epa(team_stats['season_run_success'],  team_stats['last5_run_success'],  team_games_played)

    # Calculate expected pass rate (decimal)
    expected_pass_rate = calculate_expected_pass_rate(
        team_pass_rate, proe, def_pass_rate_against,
        league_avg_pass_rate, spread
    )

    # Calculate expected plays
    expected_plays = calculate_expected_plays(team_pace, opp_pace, spread)

    # Apply injury adjustments
    if qb_out:
        o_pass -= 0.20
        expected_pass_rate -= 0.07
        expected_plays -= 3.0
        pass_success -= 0.05

    o_pass -= (elite_wr_out * 0.06)
    expected_pass_rate -= (elite_wr_out * 0.02)
    pass_success -= (elite_wr_out * 0.02)

    o_pass -= (ol_missing * 0.02)
    if ol_missing >= 2:
        expected_pass_rate -= 0.02
        pass_success -= 0.03

    if edge_missing >= 1:
        d_pass += 0.03
        o_pass += 0.03
        expected_pass_rate += 0.025

    # Home field adjustment
    home_adj = {"weak": 0.01, "average": 0.015, "strong": 0.025}
    if is_home:
        o_pass += home_adj[home_strength]
        o_run += home_adj[home_strength]
    else:
        o_pass -= home_adj[home_strength]
        o_run -= home_adj[home_strength]

    # Calculate efficiency
    net_pass_epa = calculate_net_epa(o_pass, d_pass)
    net_run_epa = calculate_net_epa(o_run, d_run)

    # Cap pass rate between 35% and 75%
    final_pass_rate = max(0.35, min(0.75, expected_pass_rate))
    final_run_rate = 1.0 - final_pass_rate

    total_matchup_epa = (final_pass_rate * net_pass_epa) + (final_run_rate * net_run_epa)
    expected_pass_attempts = final_pass_rate * expected_plays

    # Base score from EPA
    base_score = (pts_per_play_base + total_matchup_epa) * expected_plays

    # Success rate adjustments (weight = 55)
    blended_success = (final_pass_rate * pass_success) + (final_run_rate * run_success)
    success_adjustment = calculate_success_rate_adjustment(blended_success, weight=55)

    projected_score = base_score + success_adjustment

    return {
        'score': projected_score,
        'pass_rate': final_pass_rate,
        'plays': expected_plays,
        'pass_attempts': expected_pass_attempts,
        'matchup_epa': total_matchup_epa,
        'success_rate': blended_success,
        'success_adjustment': success_adjustment
    }

def get_game_projection():
    print("=" * 70)
    print("NFL GAME TOTAL PROJECTION MODEL v3.1 - STANDARDIZED DECIMALS")
    print("All percentages as decimals: 0.48 = 48%, 0.03 = 3%")
    print("Success Rate Weight: 55 (adjustable in code)")
    print("=" * 70)

    # Load all CSV files
    print("\n📁 Loading CSV files...")
    tendencies = load_team_tendencies('pass.csv')
    off_season = load_rbsdm_stats('oszn.csv')
    off_l5 = load_rbsdm_stats('ol5.csv')
    def_season = load_rbsdm_stats('dszn.csv')
    def_l5 = load_rbsdm_stats('dl5.csv')

    # Merge all data
    teams = merge_team_data(tendencies, off_season, off_l5, def_season, def_l5)

    if not teams:
        print("\n❌ Failed to load team data. Please check CSV files.")
        print("\n🔧 Debug: Run this code to diagnose:")
        print("  import os")
        print("  print(os.listdir())")
        return

    print(f"✅ Loaded stats for {len(teams)} teams\n")
    print("Available teams:")
    team_list = sorted(teams.keys())
    for i in range(0, len(team_list), 4):
        row = team_list[i:i+4]
        print("  ".join(f"{t:18}" for t in row))
    print()

    # Basic game info
    print("--- GAME SETUP ---")
    week = int(input("Current Week (1-18): "))
    team_a_name = input("Team A Name: ").strip()
    team_b_name = input("Team B Name: ").strip()

    if team_a_name not in teams or team_b_name not in teams:
        print(f"\n❌ Error: One or both teams not found in CSV")
        print(f"\nAvailable teams: {', '.join(sorted(teams.keys()))}")
        return

    # NEW: games played input for each team (used in weighting)
    print("\n--- GAMES PLAYED (used for weighting season vs last-5) ---")
    default_gp = max(0, min(17, week - 1))
    gp_a = int(input(f"{team_a_name} games played [default {default_gp}]: ") or str(default_gp))
    gp_b = int(input(f"{team_b_name} games played [default {default_gp}]: ") or str(default_gp))
    gp_a = max(0, min(17, gp_a))
    gp_b = max(0, min(17, gp_b))

    # Location
    print("\n--- LOCATION ---")
    location = input(f"Game location - 1: {team_a_name} home, 2: {team_b_name} home, 3: Neutral: ")
    team_a_home = (location == "1")
    team_b_home = (location == "2")

    venue_strength = "average"
    if team_a_home or team_b_home:
        venue_input = input("Home venue strength (1=Weak, 2=Average, 3=Strong) [2]: ") or "2"
        venue_map = {"1": "weak", "2": "average", "3": "strong"}
        venue_strength = venue_map.get(venue_input, "average")

    spread = float(input(f"\nPoint Spread (negative if {team_a_name} favored): "))

    # Manual inputs for missing data
    print("\n--- MANUAL INPUTS (if not in CSV) ---")

    # Pace
    a_pace = teams[team_a_name].get('pace')
    b_pace = teams[team_b_name].get('pace')

    if not a_pace or a_pace == 0:
        a_pace = parse_value(input(f"{team_a_name} Pace (plays per game): "))
    else:
        print(f"{team_a_name} Pace: {a_pace:.1f} (from CSV)")

    if not b_pace or b_pace == 0:
        b_pace = parse_value(input(f"{team_b_name} Pace (plays per game): "))
    else:
        print(f"{team_b_name} Pace: {b_pace:.1f} (from CSV)")

    # Defense pass rate against
    a_def_pass_rate = teams[team_a_name].get('def_pass_rate_against')
    b_def_pass_rate = teams[team_b_name].get('def_pass_rate_against')

    if not b_def_pass_rate or b_def_pass_rate == 0:
        b_def_input = input(f"{team_b_name} Defense Pass Rate Against (as decimal, e.g., 0.62): ")
        b_def_pass_rate = parse_value(b_def_input, is_percentage=True)
    else:
        print(f"{team_b_name} Def Pass Rate Against: {b_def_pass_rate:.3f} ({b_def_pass_rate*100:.1f}%) (from CSV)")

    if not a_def_pass_rate or a_def_pass_rate == 0:
        a_def_input = input(f"{team_a_name} Defense Pass Rate Against (as decimal, e.g., 0.58): ")
        a_def_pass_rate = parse_value(a_def_input, is_percentage=True)
    else:
        print(f"{team_a_name} Def Pass Rate Against: {a_def_pass_rate:.3f} ({a_def_pass_rate*100:.1f}%) (from CSV)")

    # Weather
    print("\n--- WEATHER ---")
    is_dome = input("Dome/Indoor game? (y/n): ").lower() == 'y'

    wind_mph = 0
    temp_f = 70
    precipitation = "none"

    if not is_dome:
        wind_mph = float(input("Wind speed (mph) [0]: ") or 0)
        temp_f = float(input("Temperature (°F) [70]: ") or 70)
        precip_input = input("Precipitation (1=None, 2=Light rain, 3=Heavy rain, 4=Snow, 5=Blizzard) [1]: ") or "1"
        precip_map = {"1": "none", "2": "light_rain", "3": "heavy_rain", "4": "light_snow", "5": "blizzard"}
        precipitation = precip_map.get(precip_input, "none")

    weather_adjustment = calculate_weather_adjustment(wind_mph, temp_f, precipitation)

    # Injuries
    print(f"\n--- INJURIES: {team_a_name.upper()} ---")
    a_qb_out = input("Starting QB out? (y/n) [n]: ").lower() == 'y'
    a_wr_out = int(input("Elite WRs/TEs out [0]: ") or 0)
    a_ol_out = int(input("Starting OL out [0]: ") or 0)
    b_edge_out = int(input(f"{team_b_name} EDGE out [0]: ") or 0)

    print(f"\n--- INJURIES: {team_b_name.upper()} ---")
    b_qb_out = input("Starting QB out? (y/n) [n]: ").lower() == 'y'
    b_wr_out = int(input("Elite WRs/TEs out [0]: ") or 0)
    b_ol_out = int(input("Starting OL out [0]: ") or 0)
    a_edge_out = int(input(f"{team_a_name} EDGE out [0]: ") or 0)

    # Project scores (UPDATED CALLS)
    team_a_proj = project_team_score(
        teams[team_a_name], teams[team_b_name],
        team_a_home, gp_a, gp_b,
        spread, a_qb_out, a_wr_out, a_ol_out, b_edge_out,
        0.365, 0.60, venue_strength,
        pace_override=a_pace,
        opp_pace_override=b_pace,
        def_pass_rate_override=b_def_pass_rate
    )

    team_b_proj = project_team_score(
        teams[team_b_name], teams[team_a_name],
        team_b_home, gp_b, gp_a,
        -spread, b_qb_out, b_wr_out, b_ol_out, a_edge_out,
        0.365, 0.60, venue_strength,
        pace_override=b_pace,
        opp_pace_override=a_pace,
        def_pass_rate_override=a_def_pass_rate
    )

    base_total = team_a_proj['score'] + team_b_proj['score']
    weather_adjusted_total = base_total - weather_adjustment

    # Output
    print("\n" + "=" * 70)
    print("FINAL PROJECTION")
    print("=" * 70)

    print(f"\n{team_a_name.upper()}: {team_a_proj['score']:.2f}")
    print(f"  Pass Rate: {team_a_proj['pass_rate']:.1%} | Plays: {team_a_proj['plays']:.1f} | Pass Att: {team_a_proj['pass_attempts']:.1f}")
    print(f"  Matchup EPA: {team_a_proj['matchup_epa']:.4f} | Success Rate: {team_a_proj['success_rate']:.1%} ({team_a_proj['success_adjustment']:+.2f} pts)")

    print(f"\n{team_b_name.upper()}: {team_b_proj['score']:.2f}")
    print(f"  Pass Rate: {team_b_proj['pass_rate']:.1%} | Plays: {team_b_proj['plays']:.1f} | Pass Att: {team_b_proj['pass_attempts']:.1f}")
    print(f"  Matchup EPA: {team_b_proj['matchup_epa']:.4f} | Success Rate: {team_b_proj['success_rate']:.1%} ({team_b_proj['success_adjustment']:+.2f} pts)")

    print(f"\n{'*' * 70}")
    if weather_adjustment > 0:
        print(f"BASE TOTAL: {base_total:.2f}")
        print(f"WEATHER ADJUSTMENT: -{weather_adjustment:.1f} pts")
        print(f"FINAL TOTAL: {weather_adjusted_total:.2f}")
    else:
        print(f"PROJECTED TOTAL: {weather_adjusted_total:.2f}")
    print(f"{'*' * 70}")

    # Betting insights
    print("\n--- BETTING INSIGHTS ---")
    if weather_adjusted_total >= 48:
        print("💡 HIGH-SCORING GAME - Consider OVER")
    elif weather_adjusted_total <= 40:
        print("💡 LOW-SCORING GAME - Consider UNDER")

    total_pass_attempts = team_a_proj['pass_attempts'] + team_b_proj['pass_attempts']
    if total_pass_attempts >= 80:
        print("💡 HIGH PASS VOLUME - Strong QB/WR prop environment")

    if weather_adjustment >= 3:
        print(f"⚠️  WEATHER IMPACT: Line dropped {weather_adjustment:.1f} pts - UNDER lean")

    avg_success = (team_a_proj['success_rate'] + team_b_proj['success_rate']) / 2
    if avg_success >= 0.48:
        print("💡 HIGH SUCCESS RATES - Both teams sustaining drives")
    elif avg_success <= 0.42:
        print("💡 LOW SUCCESS RATES - Lots of punts expected, favor UNDER")

if __name__ == "__main__":
    get_game_projection()
