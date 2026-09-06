import './styles.css';

type Player = { name: string; pos: string; club: string; points: number; captain?: boolean; vice?: boolean; bench?: number };
type Event = { minute: string; label: string; detail: string; tone: 'good' | 'warn' | 'muted' };
type Gameweek = { id: number; opponent: string; result: string; points: number; rank: string; captain: string; events: Event[] };

const squad: Player[] = [
  { name: 'Raya', pos: 'GKP', club: 'ARS', points: 6 }, { name: 'Gabriel', pos: 'DEF', club: 'ARS', points: 8 },
  { name: 'Mitchell', pos: 'DEF', club: 'CRY', points: 2 }, { name: 'Shaw', pos: 'DEF', club: 'MUN', points: 1 },
  { name: 'Bruno Fernandes', pos: 'MID', club: 'MUN', points: 12, vice: true }, { name: 'Mbeumo', pos: 'MID', club: 'MUN', points: 9 },
  { name: 'Szoboszlai', pos: 'MID', club: 'LIV', points: 5 }, { name: 'Yates', pos: 'MID', club: 'NFO', points: 3 },
  { name: 'Haaland', pos: 'FWD', club: 'MCI', points: 16, captain: true }, { name: 'Joao Pedro', pos: 'FWD', club: 'CHE', points: 7 },
  { name: 'Calvert-Lewin', pos: 'FWD', club: 'LEE', points: 2 }, { name: 'Palmer', pos: 'GKP', club: 'IPS', points: 0, bench: 1 },
  { name: 'Diop', pos: 'DEF', club: 'IPS', points: 1, bench: 2 }, { name: 'Hughes', pos: 'MID', club: 'CRY', points: 2, bench: 3 },
  { name: 'van Ewijk', pos: 'DEF', club: 'COV', points: 1, bench: 4 },
];

const gameweeks: Gameweek[] = [
  { id: 1, opponent: 'Coventry', result: 'W 3–0', points: 74, rank: '1.2m', captain: 'Haaland', events: [
    { minute: '18′', label: 'Clean sheet', detail: 'Raya + Gabriel · ARS 2–0 COV', tone: 'good' },
    { minute: '41′', label: 'Captain goal', detail: 'Haaland · 2× points secured', tone: 'good' },
    { minute: '72′', label: 'Late assist', detail: 'Bruno Fernandes · MUN 2–1 FUL', tone: 'good' },
    { minute: 'FT', label: 'Bench watch', detail: 'Hughes left 2 points unused', tone: 'warn' },
  ] },
  { id: 2, opponent: 'Fulham', result: 'D 1–1', points: 61, rank: '1.5m', captain: 'Bruno Fernandes', events: [
    { minute: '09′', label: 'Early booking', detail: 'Shaw · yellow card', tone: 'warn' },
    { minute: '55′', label: 'Assist', detail: 'Bruno Fernandes · set-piece delivery', tone: 'good' },
    { minute: 'FT', label: 'Rank drift', detail: '61 points · 8 below safety', tone: 'muted' },
  ] },
  { id: 3, opponent: 'Wolves', result: 'W 2–1', points: 69, rank: '1.1m', captain: 'Haaland', events: [
    { minute: '23′', label: 'Captain blank', detail: 'Haaland · 2 points', tone: 'warn' },
    { minute: '67′', label: 'Goal', detail: 'Mbeumo · inside the box', tone: 'good' },
    { minute: 'FT', label: 'Wild card', detail: 'No chip used · bank £0.0m', tone: 'muted' },
  ] },
];

let selected = 0;
const app = document.querySelector<HTMLDivElement>('#app')!;
const initials = (name: string) => name.split(' ').map((part) => part[0]).join('').slice(0, 2);
const scoreClass = (points: number) => points >= 10 ? 'score score--hot' : points <= 2 ? 'score score--quiet' : 'score';

function render(): void {
  const gw = gameweeks[selected];
  const starters = squad.filter((player) => !player.bench);
  const bench = squad.filter((player) => player.bench);
  app.innerHTML = `
    <main class="shell">
      <header class="topbar">
        <div class="brand"><span class="brand-mark">◆</span><div><p>FPL PI MANAGER</p><h1>Gaffer room</h1></div></div>
        <div class="status"><span class="live-dot"></span><span>Snapshot mode</span><span class="status-divider"></span><span>2026 / 27</span></div>
      </header>
      <section class="hero-grid">
        <div class="intro"><p class="eyebrow">THE SEASON ROOM</p><h2>Gameweek <em>${gw.id}</em><br />under the microscope.</h2><p class="lede">A quiet look at the calls, points and moments shaping the season.</p>
          <div class="metrics"><div><span>LAST GW</span><strong>${gw.points}</strong><small>points</small></div><div><span>OVERALL RANK</span><strong>${gw.rank}</strong><small>↑ 140k places</small></div><div><span>NEXT DEADLINE</span><strong>2d 04h</strong><small>Fri · 17:30 UTC</small></div></div>
        </div>
        <div class="room" aria-label="3D dugout scene with the gaffer, pitch board and helper desks">
          <div class="room-glow"></div><div class="back-wall"><span>GAFFER HQ</span></div><div class="desk desk--analyst"><i></i><b>SCOUT</b><small>watching fixtures</small></div><div class="desk desk--am"><i></i><b>AM</b><small>challenging plan</small></div>
          <div class="gaffer"><div class="head"></div><div class="body"></div><span>GAFFER</span></div>
          <div class="pitch-board"><div class="pitch-lines"></div><span>GW ${gw.id} · ${gw.result}</span><div class="pitch-dots"><i></i><i></i><i></i><i></i></div></div>
          <div class="room-floor"></div>
        </div>
      </section>
      <section class="workspace">
        <div class="squad-card panel"><div class="panel-head"><div><p class="eyebrow">FIELD NOTES</p><h3>Starting XI</h3></div><span class="formation">3–4–3</span></div><div class="pitch-list">${starters.map(playerCard).join('')}</div><div class="bench-label"><span>BENCH</span><span>4 players</span></div><div class="bench-list">${bench.map(playerCard).join('')}</div></div>
        <div class="events-card panel"><div class="panel-head"><div><p class="eyebrow">MATCH LOG · GW ${gw.id}</p><h3>What happened</h3></div><span class="result-badge">${gw.result}</span></div><div class="event-list">${gw.events.map(eventRow).join('')}</div><div class="callout"><span class="callout-icon">✦</span><div><b>Gaffer's read</b><p>${gw.id === 1 ? 'The armband paid off. A clean opening week with the spine delivering.' : gw.id === 2 ? 'A steady week, but the captaincy edge was left on the table.' : 'The points landed despite a quiet captain. Hold the nerve.'}</p></div></div></div>
      </section>
      <section class="history panel"><div class="panel-head"><div><p class="eyebrow">THE CAMPAIGN</p><h3>Gameweek performance</h3></div><span class="history-hint">Scroll to explore <span>→</span></span></div><div class="gw-strip" role="tablist" aria-label="Gameweek performance">${gameweeks.map((item, index) => `<button class="gw-tab ${index === selected ? 'is-selected' : ''}" role="tab" aria-selected="${index === selected}" data-gw="${index}"><span>GW ${item.id}</span><strong>${item.points}</strong><small>${item.result}</small><i style="height:${item.points}%"></i></button>`).join('')}</div><div class="carousel-controls"><button class="arrow" data-direction="-1" aria-label="Previous gameweek" ${selected === 0 ? 'disabled' : ''}>←</button><span>${selected + 1} / ${gameweeks.length}</span><button class="arrow" data-direction="1" aria-label="Next gameweek" ${selected === gameweeks.length - 1 ? 'disabled' : ''}>→</button></div></section>
      <footer><span>READ-ONLY SNAPSHOT</span><span>Last synced from season-state.json · 04 Sep 2026</span><span>Telegram remains the approval surface</span></footer>
    </main>`;
  app.querySelectorAll<HTMLButtonElement>('[data-gw]').forEach((button) => button.addEventListener('click', () => { selected = Number(button.dataset.gw); render(); }));
  app.querySelectorAll<HTMLButtonElement>('[data-direction]').forEach((button) => button.addEventListener('click', () => { selected = Math.max(0, Math.min(gameweeks.length - 1, selected + Number(button.dataset.direction))); render(); }));
}

function playerCard(player: Player): string { return `<div class="player ${player.bench ? 'player--bench' : ''}"><span class="avatar avatar--${player.pos.toLowerCase()}">${initials(player.name)}</span><span class="player-main"><b>${player.name}</b><small>${player.club} · ${player.pos}${player.captain ? ' · <mark>C</mark>' : player.vice ? ' · <mark>VC</mark>' : ''}</small></span><span class="${scoreClass(player.points)}">${player.points}</span></div>`; }
function eventRow(event: Event): string { return `<div class="event"><span class="event-time">${event.minute}</span><span class="event-marker event-marker--${event.tone}"></span><span class="event-copy"><b>${event.label}</b><small>${event.detail}</small></span></div>`; }

render();
