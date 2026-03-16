'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Match { id: number; title: string; home_team: string; away_team: string; status: string; match_date: string; }
interface Event { id: number; event_type: string; frame_number: number; timestamp_s: number; player_id: number; team_id: number; }

function Sidebar({ active }: { active: string }) {
  const router = useRouter();
  const logout = () => { localStorage.clear(); router.push('/'); };
  const nav = [
    { label: '🏠 Dashboard', href: '/admin' },
    { label: '📋 Matches',   href: '/admin/matches' },
    { label: '📡 Live Feed', href: '#live' },
    { label: '⚑  Events',   href: '#events' },
  ];
  return (
    <div className="sidebar">
      <div className="sidebar-logo">⚽ FootAnalytics</div>
      {nav.map(n => (
        <a key={n.label} className={`nav-item${active === n.label ? ' active' : ''}`}
          href={n.href}>{n.label}</a>
      ))}
      <div style={{ marginTop: 'auto' }}>
        <button className="btn-danger" style={{ width: '100%' }} onClick={logout}>Sign Out</button>
      </div>
    </div>
  );
}

export default function AdminDashboard() {
  const router  = useRouter();
  const [matches, setMatches]         = useState<Match[]>([]);
  const [events,  setEvents]          = useState<Event[]>([]);
  const [selMatch, setSelMatch]       = useState<Match | null>(null);
  const [offsideAlert, setAlert]      = useState(false);
  const [alertMsg, setAlertMsg]       = useState('');
  const [streaming, setStreaming]     = useState(false);
  const [uploadFile, setUploadFile]   = useState<File | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : '';

  // Auth guard
  useEffect(() => {
    const role = localStorage.getItem('role');
    if (!role || role !== 'admin') router.push('/');
  }, [router]);

  // Load matches
  useEffect(() => {
    fetch(`${API}/matches`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(setMatches).catch(() => {});
  }, [token]);

  // Connect WebSocket when match selected
  useEffect(() => {
    wsRef.current?.close();
    if (!selMatch) return;
    const ws = new WebSocket(`ws://localhost:8000/ws/${selMatch.id}`);
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data);
      if (d.type === 'offside') {
        setAlert(true);
        setAlertMsg(`⚑ OFFSIDE! Player #${d.player_id} — Team ${d.team} @ ${d.timestamp.toFixed(1)}s`);
        setEvents(prev => [{ id: Date.now(), event_type: 'offside',
          frame_number: d.frame, timestamp_s: d.timestamp,
          player_id: d.player_id, team_id: d.team }, ...prev.slice(0,49)]);
        setTimeout(() => setAlert(false), 5000);
      }
    };
    wsRef.current = ws;
    // Also fetch existing events
    fetch(`${API}/matches/${selMatch.id}/events`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(d => Array.isArray(d) && setEvents(d.reverse().slice(0,50))).catch(()=>{});
    return () => ws.close();
  }, [selMatch, token]);

  async function uploadAndStream() {
    if (!selMatch || !uploadFile) return;
    const fd = new FormData();
    fd.append('video', uploadFile);
    await fetch(`${API}/matches/${selMatch.id}/upload`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd,
    });
    setStreaming(true);
  }

  const statsCards = [
    { label: 'Total Matches', value: matches.length },
    { label: 'Live Now',      value: matches.filter(m => m.status === 'processing').length },
    { label: 'Offside Events',value: events.filter(e => e.event_type === 'offside').length },
    { label: 'Completed',     value: matches.filter(m => m.status === 'done').length },
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar active="🏠 Dashboard" />

      <div style={{ flex: 1, padding: '32px 36px', overflow: 'auto' }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ margin: 0, fontSize: '1.7rem', fontWeight: 800 }}>Admin Dashboard</h1>
          <p style={{ margin: '4px 0 0', color: 'rgba(232,245,233,0.5)', fontSize: '0.88rem' }}>
            Real-time match intelligence & offside detection
          </p>
        </div>

        {/* Offside Alert */}
        {offsideAlert && (
          <div className="offside-banner" style={{ marginBottom: 24 }}>
            {alertMsg}
          </div>
        )}

        {/* Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 28 }}>
          {statsCards.map(s => (
            <div key={s.label} className="stat-card">
              <div className="stat-value">{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Matches list */}
          <div className="glass" style={{ padding: 24 }}>
            <h2 style={{ margin: '0 0 16px', fontSize: '1rem', fontWeight: 700 }}>⚽ Matches</h2>
            {matches.length === 0
              ? <p style={{ color: 'rgba(232,245,233,0.4)', fontSize: '0.85rem' }}>No matches yet.</p>
              : matches.map(m => (
                <div key={m.id} onClick={() => setSelMatch(m)}
                  style={{
                    padding: '12px 14px', borderRadius: 10, marginBottom: 8, cursor: 'pointer',
                    background: selMatch?.id === m.id ? 'rgba(0,230,118,0.12)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${selMatch?.id === m.id ? 'rgba(0,230,118,0.4)' : 'rgba(255,255,255,0.06)'}`,
                    transition: 'all 0.15s',
                  }}>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{m.title}</div>
                  <div style={{ fontSize: '0.78rem', color: 'rgba(232,245,233,0.5)', marginTop: 3 }}>
                    {m.home_team} vs {m.away_team}
                  </div>
                  <span className={`badge badge-${m.status === 'done' ? 'green' : m.status === 'processing' ? 'blue' : 'red'}`}
                    style={{ marginTop: 6, display: 'inline-block' }}>{m.status}</span>
                </div>
              ))
            }
          </div>

          {/* Live feed + upload */}
          <div className="glass" style={{ padding: 24 }}>
            <h2 style={{ margin: '0 0 16px', fontSize: '1rem', fontWeight: 700 }}>📡 Live Video Feed</h2>
            {selMatch ? (
              <>
                <p style={{ fontSize: '0.83rem', color: 'rgba(232,245,233,0.5)', marginBottom: 14 }}>
                  Selected: <strong style={{ color: '#00e676' }}>{selMatch.title}</strong>
                </p>
                {!streaming ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <input id="video-upload" type="file" accept="video/*"
                      onChange={e => setUploadFile(e.target.files?.[0] ?? null)}
                      style={{ color: 'rgba(232,245,233,0.7)', fontSize: '0.85rem' }} />
                    <button id="start-stream-btn" className="btn-primary" onClick={uploadAndStream}
                      disabled={!uploadFile}>
                      Upload & Start Processing
                    </button>
                  </div>
                ) : (
                  <>
                    <img
                      src={`${API}/stream/${selMatch.id}?token=${token}`}
                      alt="Live processed feed"
                      style={{ width: '100%', borderRadius: 10, border: '1px solid rgba(0,230,118,0.2)' }}
                    />
                    <button id="stop-stream-btn" className="btn-danger" onClick={() => setStreaming(false)}
                      style={{ width: '100%', marginTop: 10 }}>
                      Stop Feed
                    </button>
                  </>
                )}
              </>
            ) : (
              <p style={{ color: 'rgba(232,245,233,0.35)', fontSize: '0.85rem' }}>
                Select a match on the left to load its video feed.
              </p>
            )}
          </div>
        </div>

        {/* Events table */}
        <div className="glass" style={{ padding: 24, marginTop: 20 }}>
          <h2 style={{ margin: '0 0 16px', fontSize: '1rem', fontWeight: 700 }}>⚑ Offside Events Log</h2>
          {events.length === 0
            ? <p style={{ color: 'rgba(232,245,233,0.35)', fontSize: '0.85rem' }}>No events recorded yet.</p>
            : (
              <table className="data-table">
                <thead>
                  <tr><th>Type</th><th>Player #</th><th>Team</th><th>Timestamp</th><th>Frame</th></tr>
                </thead>
                <tbody>
                  {events.map(ev => (
                    <tr key={ev.id}>
                      <td><span className="badge badge-red">{ev.event_type}</span></td>
                      <td>#{ev.player_id}</td>
                      <td>Team {ev.team_id}</td>
                      <td>{ev.timestamp_s?.toFixed(2)}s</td>
                      <td>{ev.frame_number}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }
        </div>
      </div>
    </div>
  );
}
