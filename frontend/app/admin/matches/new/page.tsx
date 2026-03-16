'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export default function NewMatchPage() {
  const router = useRouter();
  const [title,    setTitle]    = useState('');
  const [home,     setHome]     = useState('');
  const [away,     setAway]     = useState('');
  const [date,     setDate]     = useState('');
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);
  const [success,  setSuccess]  = useState(false);
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : '';

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API}/matches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title, home_team: home, away_team: away, match_date: date || undefined }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create match');
      setSuccess(true);
      setTimeout(() => router.push('/admin'), 1500);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'radial-gradient(ellipse at 40% 60%, #0a3d20 0%, #06140f 70%)', padding: 24,
    }}>
      <div className="glass" style={{ width: '100%', maxWidth: 460, padding: '40px 36px' }}>
        <button onClick={() => router.push('/admin')}
          style={{ background: 'none', border: 'none', color: 'rgba(232,245,233,0.5)',
            cursor: 'pointer', fontSize: '0.85rem', marginBottom: 20, padding: 0 }}>
          ← Back to Dashboard
        </button>

        <h1 style={{ margin: '0 0 6px', fontSize: '1.5rem', fontWeight: 800 }}>Create Match</h1>
        <p style={{ margin: '0 0 28px', color: 'rgba(232,245,233,0.5)', fontSize: '0.85rem' }}>
          Add a new match to start processing video.
        </p>

        {success ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: 10 }}>✅</div>
            <p style={{ color: '#00e676', fontWeight: 700 }}>Match created! Redirecting…</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <input id="match-title" className="input-field" placeholder="Match title (e.g. El Clásico)"
                value={title} onChange={e => setTitle(e.target.value)} required />
              <input id="home-team" className="input-field" placeholder="Home team"
                value={home} onChange={e => setHome(e.target.value)} required />
              <input id="away-team" className="input-field" placeholder="Away team"
                value={away} onChange={e => setAway(e.target.value)} required />
              <input id="match-date" className="input-field" type="datetime-local"
                value={date} onChange={e => setDate(e.target.value)} />

              {error && (
                <div style={{ background: 'rgba(255,23,68,0.12)', border: '1px solid rgba(255,23,68,0.3)',
                  borderRadius: 8, padding: '10px 14px', fontSize: '0.85rem', color: '#ff5252' }}>
                  {error}
                </div>
              )}

              <button id="create-match-btn" type="submit" className="btn-primary" disabled={loading}>
                {loading ? 'Creating…' : '⚽ Create Match'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
