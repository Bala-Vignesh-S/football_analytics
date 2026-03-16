'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface PlayerStat {
  player_track_id: number;
  team_id: number;
  distance_m: number;
  avg_speed_ms: number;
  max_speed_ms: number;
  offside_count: number;
  frames_detected: number;
}
interface Match { id: number; title: string; home_team: string; away_team: string; status: string; }

export default function ManagerDashboard() {
  const router  = useRouter();
  const [matches,  setMatches]  = useState<Match[]>([]);
  const [selMatch, setSel]      = useState<Match | null>(null);
  const [stats,    setStats]    = useState<PlayerStat[]>([]);
  const [filterTeam, setFilter] = useState<number | 'all'>('all');
  const [loading, setLoading]   = useState(false);
  const token    = typeof window !== 'undefined' ? localStorage.getItem('token') : '';
  const username = typeof window !== 'undefined' ? localStorage.getItem('username') : 'Manager';

  // Auth guard
  useEffect(() => {
    const role = localStorage.getItem('role');
    if (!role) router.push('/');
  }, [router]);

  useEffect(() => {
    fetch(`${API}/matches`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(d => Array.isArray(d) && setMatches(d)).catch(() => {});
  }, [token]);

  async function loadStats(m: Match) {
    setSel(m);
    setLoading(true);
    try {
      const r = await fetch(`${API}/matches/${m.id}/stats`, { headers: { Authorization: `Bearer ${token}` } });
      const d = await r.json();
      setStats(Array.isArray(d) ? d : []);
    } catch { setStats([]); }
    setLoading(false);
  }

  const filtered = filterTeam === 'all' ? stats : stats.filter(s => s.team_id === filterTeam);
  const totalDist = filtered.reduce((a, s) => a + s.distance_m, 0);
  const avgSpeed  = filtered.length > 0 ? filtered.reduce((a,s) => a + s.avg_speed_ms, 0) / filtered.length : 0;
  const maxSpeed  = filtered.length > 0 ? Math.max(...filtered.map(s => s.max_speed_ms)) : 0;
  const offsides  = filtered.reduce((a,s) => a + s.offside_count, 0);

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-logo">⚽ FootAnalytics</div>
        <a className="nav-item" href="#">📊 My Stats</a>
        <a className="nav-item" href="#">📋 Matches</a>
        <div style={{ marginTop: 'auto' }}>
          <div style={{ fontSize: '0.78rem', color: 'rgba(232,245,233,0.4)', marginBottom: 10, textAlign: 'center' }}>
            Signed in as <span style={{ color: '#00e676' }}>{username}</span>
          </div>
          <button className="btn-danger" style={{ width: '100%' }}
            onClick={() => { localStorage.clear(); router.push('/'); }}>Sign Out</button>
        </div>
      </div>

      {/* Main */}
      <div style={{ flex: 1, padding: '32px 36px', overflow: 'auto' }}>
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ margin: 0, fontSize: '1.7rem', fontWeight: 800 }}>Club Manager Portal</h1>
          <p style={{ margin: '4px 0 0', color: 'rgba(232,245,233,0.5)', fontSize: '0.88rem' }}>
            Player performance analytics &amp; match statistics
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20 }}>
          {/* Match list */}
          <div className="glass" style={{ padding: 20, height: 'fit-content' }}>
            <h2 style={{ margin: '0 0 14px', fontSize: '0.95rem', fontWeight: 700 }}>⚽ Matches</h2>
            {matches.length === 0
              ? <p style={{ color: 'rgba(232,245,233,0.4)', fontSize: '0.83rem' }}>No matches available.</p>
              : matches.map(m => (
                <div key={m.id} onClick={() => loadStats(m)}
                  style={{
                    padding: '11px 13px', borderRadius: 10, marginBottom: 8, cursor: 'pointer',
                    background: selMatch?.id === m.id ? 'rgba(0,230,118,0.12)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${selMatch?.id === m.id ? '#00e676' : 'rgba(255,255,255,0.06)'}`,
                    transition: 'all 0.15s',
                  }}>
                  <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{m.title}</div>
                  <div style={{ fontSize: '0.75rem', color: 'rgba(232,245,233,0.5)', marginTop: 2 }}>
                    {m.home_team} vs {m.away_team}
                  </div>
                </div>
              ))
            }
          </div>

          {/* Stats panel */}
          <div>
            {selMatch ? (
              <>
                {/* Summary cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
                  {[
                    { label: 'Total Distance', value: totalDist.toFixed(0) + ' m' },
                    { label: 'Avg Speed',       value: avgSpeed.toFixed(2) + ' m/s' },
                    { label: 'Max Speed',        value: maxSpeed.toFixed(2) + ' m/s' },
                    { label: 'Offsides',         value: String(offsides) },
                  ].map(s => (
                    <div key={s.label} className="stat-card">
                      <div className="stat-value" style={{ fontSize: '1.6rem' }}>{s.value}</div>
                      <div className="stat-label">{s.label}</div>
                    </div>
                  ))}
                </div>

                {/* Team filter */}
                <div className="glass" style={{ padding: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                    <h2 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>
                      👥 Player Statistics — <span style={{ color: '#00e676' }}>{selMatch.title}</span>
                    </h2>
                    <div style={{ display: 'flex', gap: 8 }}>
                      {(['all', 1, 2] as const).map(t => (
                        <button key={t} id={`filter-${t}`}
                          onClick={() => setFilter(t)}
                          style={{
                            padding: '6px 14px', borderRadius: 8, border: 'none', cursor: 'pointer',
                            fontWeight: 600, fontSize: '0.78rem',
                            background: filterTeam === t ? 'linear-gradient(135deg,#00e676,#00bcd4)' : 'rgba(255,255,255,0.08)',
                            color: filterTeam === t ? '#06140f' : 'rgba(232,245,233,0.65)',
                          }}>
                          {t === 'all' ? 'All' : `Team ${t}`}
                        </button>
                      ))}
                    </div>
                  </div>

                  {loading
                    ? <p style={{ color: 'rgba(232,245,233,0.4)', fontSize: '0.85rem' }}>Loading stats…</p>
                    : filtered.length === 0
                      ? <p style={{ color: 'rgba(232,245,233,0.35)', fontSize: '0.85rem' }}>
                          No player stats yet. Process a video first.
                        </p>
                      : (
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Player #</th>
                              <th>Team</th>
                              <th>Distance (m)</th>
                              <th>Avg Speed (m/s)</th>
                              <th>Max Speed (m/s)</th>
                              <th>Offsides</th>
                              <th>Frames</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filtered.sort((a,b) => b.distance_m - a.distance_m).map(s => (
                              <tr key={s.player_track_id}>
                                <td style={{ fontWeight: 700 }}>#{s.player_track_id}</td>
                                <td>
                                  <span className={`badge badge-${s.team_id === 1 ? 'blue' : 'red'}`}>
                                    Team {s.team_id || '?'}
                                  </span>
                                </td>
                                <td>{s.distance_m.toFixed(1)}</td>
                                <td>{s.avg_speed_ms.toFixed(2)}</td>
                                <td>{s.max_speed_ms.toFixed(2)}</td>
                                <td>
                                  {s.offside_count > 0
                                    ? <span className="badge badge-red">{s.offside_count}</span>
                                    : <span style={{ color: 'rgba(232,245,233,0.3)' }}>—</span>
                                  }
                                </td>
                                <td style={{ color: 'rgba(232,245,233,0.5)' }}>{s.frames_detected}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )
                  }
                </div>
              </>
            ) : (
              <div className="glass" style={{ padding: 48, textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: 12 }}>📋</div>
                <p style={{ color: 'rgba(232,245,233,0.4)', fontSize: '0.9rem' }}>
                  Select a match from the left to view player statistics.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
