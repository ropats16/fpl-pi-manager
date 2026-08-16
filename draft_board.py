import csv
from collections import defaultdict

def load(p):
    with open(p) as f:
        return list(csv.DictReader(f))

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0

players = load('data/players.csv')
teams = {int(t['id']): t for t in load('data/teams.csv')}
fixtures = load('data/fixtures.csv')
POS = {1:'GKP', 2:'DEF', 3:'MID', 4:'FWD'}

ticker = defaultdict(list)
for fx in fixtures:
    if fx['finished'] == 'True': continue
    ev = int(fx['event'] or 99)
    for side, tcol, dcol, ocol in (('h','team_h','team_h_difficulty','team_a'),
                                   ('a','team_a','team_a_difficulty','team_h')):
        t = int(fx[tcol])
        opp = teams[int(fx[ocol])]['short_name']
        ticker[t].append((ev, f"{opp}{side.upper()}({fx[dcol]})"))
print("FIXTURE TICKER - next 6 (FDR 1-5):")
for t in sorted(ticker, key=lambda t: teams[t]['short_name']):
    seq = sorted(ticker[t])[:6]
    print(f"{teams[t]['short_name']:<4} " + " ".join(x[1] for x in seq))

for pos in (1,2,3,4):
    pool = [p for p in players if int(p['element_type'])==pos and f(p['minutes'])>=900]
    pool.sort(key=lambda p: -f(p['total_points']))
    print(f"\n{POS[pos]} top 25 (last-season pts):  name / team / £m / pts / ppg / xGI / own% / epN / st")
    for p in pool[:25]:
        print(f"{p['web_name'][:16]:<16} {teams[int(p['team'])]['short_name']:<4} "
              f"{f(p['now_cost'])/10:>4.1f} {int(f(p['total_points'])):>4} {p['points_per_game']:>4} "
              f"{f(p['expected_goal_involvements']):>5.1f} {p['selected_by_percent']:>5} "
              f"{p['ep_next'] or '-':>4} {p['status']}")
