import { useState } from 'react';
import { supabase } from '../supabase';
import './Login.css';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState('login'); // 'login' or 'reset'
  const [message, setMessage] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);

    try {
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (authError) {
        setError(authError.message);
      } else if (data.session) {
        onLogin(data.session);
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);

    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });

      if (resetError) {
        setError(resetError.message);
      } else {
        setMessage('Check your email for the password reset link.');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1 className="login-title">AI Council</h1>
        <p className="login-subtitle">Multi-model AI deliberation platform</p>

        {mode === 'login' ? (
          <form onSubmit={handleLogin} className="login-form">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="login-input"
              autoFocus
              disabled={loading}
              required
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="login-input"
              disabled={loading}
              required
            />

            {error && <div className="login-error">{error}</div>}

            <button
              type="submit"
              className="login-button"
              disabled={loading || !email || !password}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>

            <button
              type="button"
              className="login-link"
              onClick={() => setMode('reset')}
            >
              Forgot password?
            </button>
          </form>
        ) : (
          <form onSubmit={handleResetPassword} className="login-form">
            <p className="login-hint">
              Enter your email to receive a password reset link.
            </p>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="login-input"
              autoFocus
              disabled={loading}
              required
            />

            {error && <div className="login-error">{error}</div>}
            {message && <div className="login-success">{message}</div>}

            <button
              type="submit"
              className="login-button"
              disabled={loading || !email}
            >
              {loading ? 'Sending...' : 'Send Reset Link'}
            </button>

            <button
              type="button"
              className="login-link"
              onClick={() => {
                setMode('login');
                setMessage('');
                setError('');
              }}
            >
              Back to sign in
            </button>
          </form>
        )}

        <p className="login-footer">
          Contact your administrator if you need an account.
        </p>
      </div>
    </div>
  );
}
