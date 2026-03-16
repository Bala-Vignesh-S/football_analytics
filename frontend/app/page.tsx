'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab]         = useState<'login' | 'register'>('login');
  const [username, setUser]   = useState('');
  const [password, setPass]   = useState('');
  const [email, setEmail]     = useState('');
  const [club, setClub]       = useState('');
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('username', username);
      fd.append('password', password);
      const res = await fetch(`${API}/auth/login`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');

      localStorage.setItem('token', data.access_token);
      localStorage.setItem('role',  data.role);
      localStorage.setItem('username', data.username);

      router.push(data.role === 'admin' ? '/admin' : '/manager');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password, club_name: club }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');
      setTab('login');
      setError('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(ellipse at 60% 40%, #0a3d20 0%, #06140f 70%)',
      padding: '24px',
    }}>
      {/* Decorative pitch lines */}
      <div style={{
        position: 'fixed', inset: 0, pointerEvents: 'none', overflow: 'hidden',
        opacity: 0.06,
      }}>
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
          width: 900, height: 560, border: '2px solid #00e676', borderRadius: 4 }} />
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
          width: 3, height: 560, background: '#00e676' }} />
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
          width: 140, height: 140, border: '2px solid #00e676', borderRadius: '50%' }} />
      </div>

      <div className="glass" style={{ width: '100%', maxWidth: 420, padding: '40px 36px' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: '2.5rem', marginBottom: 8 }}>⚽</div>
          <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800,
            background: 'linear-gradient(135deg,#00e676,#00bcd4)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Football Analytics
          </h1>
          <p style={{ margin: '6px 0 0', color: 'rgba(232,245,233,0.5)', fontSize: '0.85rem' }}>
            AI-Powered Match Intelligence
          </p>
        </div>

        {/* Tab switcher */}
        <div style={{ display: 'flex', background: 'rgba(255,255,255,0.05)',
          borderRadius: 10, padding: 4, marginBottom: 28 }}>
          {(['login','register'] as const).map(t => (
            <button key={t} onClick={() => { setTab(t); setError(''); }}
              style={{ flex: 1, padding: '9px', border: 'none', borderRadius: 8, cursor: 'pointer',
                fontWeight: 600, fontSize: '0.88rem',
                background: tab === t ? 'linear-gradient(135deg,#00e676,#00bcd4)' : 'transparent',
                color: tab === t ? '#06140f' : 'rgba(232,245,233,0.55)',
                transition: 'all 0.2s' }}>
              {t === 'login' ? 'Sign In' : 'Register'}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={tab === 'login' ? handleLogin : handleRegister}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            {tab === 'register' && (
              <input id="email-input" className="input-field" type="email"
                placeholder="Email address" value={email}
                onChange={e => setEmail(e.target.value)} required />
            )}

            <input id="username-input" className="input-field" type="text"
              placeholder="Username" value={username}
              onChange={e => setUser(e.target.value)} required />

            <input id="password-input" className="input-field" type="password"
              placeholder="Password" value={password}
              onChange={e => setPass(e.target.value)} required />

            {tab === 'register' && (
              <input id="club-input" className="input-field" type="text"
                placeholder="Club name (optional)" value={club}
                onChange={e => setClub(e.target.value)} />
            )}

            {error && (
              <div style={{ background: 'rgba(255,23,68,0.12)', border: '1px solid rgba(255,23,68,0.3)',
                borderRadius: 8, padding: '10px 14px', fontSize: '0.85rem', color: '#ff5252' }}>
                {error}
              </div>
            )}

            <button id="submit-btn" type="submit" className="btn-primary"
              disabled={loading} style={{ marginTop: 4 }}>
              {loading ? 'Please wait…' : (tab === 'login' ? 'Sign In' : 'Create Account')}
            </button>
          </div>
        </form>

        {tab === 'login' && (
          <p style={{ textAlign: 'center', marginTop: 20, fontSize: '0.8rem',
            color: 'rgba(232,245,233,0.4)' }}>
            Default admin: <code style={{ color: '#00e676' }}>admin</code> /&nbsp;
            <code style={{ color: '#00e676' }}>admin1234</code>
          </p>
        )}
      </div>
    </div>
  );
}
