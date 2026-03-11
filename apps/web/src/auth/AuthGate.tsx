import { useState, type FormEvent, type PropsWithChildren } from 'react';
import Button from '../components/Button';
import { useAuth } from './AuthProvider';

const AuthScreen = () => {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<'sign-in' | 'sign-up'>('sign-in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);

    try {
      if (mode === 'sign-in') {
        await signIn(email, password);
      } else {
        const result = await signUp(email, password);
        setNotice(
          result.needsEmailConfirmation
            ? 'Account created. Confirm your email, then sign in.'
            : 'Account created. You can start using StyleUs now.'
        );
        if (result.needsEmailConfirmation) {
          setMode('sign-in');
        }
      }
    } catch (submissionError) {
      const message = submissionError instanceof Error ? submissionError.message : 'Unable to continue';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4 py-10">
      <div className="w-full max-w-md rounded-3xl border border-neutral-200 bg-white p-8 shadow-sm">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-neutral-400">StyleUs</p>
          <h1 className="text-2xl font-semibold text-neutral-900">
            {mode === 'sign-in' ? 'Sign in to your wardrobe' : 'Create your account'}
          </h1>
          <p className="text-sm text-neutral-500">
            Your session comes from Supabase Auth. The API still owns wardrobe data and authorization.
          </p>
        </div>

        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <label className="block space-y-2 text-sm font-medium text-neutral-700">
            <span>Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm text-neutral-900 outline-none transition focus:border-accent-600 focus:ring-2 focus:ring-accent-100"
            />
          </label>

          <label className="block space-y-2 text-sm font-medium text-neutral-700">
            <span>Password</span>
            <input
              type="password"
              required
              minLength={6}
              autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm text-neutral-900 outline-none transition focus:border-accent-600 focus:ring-2 focus:ring-accent-100"
            />
          </label>

          {error ? <p className="text-sm text-danger-600">{error}</p> : null}
          {notice ? <p className="text-sm text-emerald-600">{notice}</p> : null}

          <Button className="w-full" type="submit" disabled={submitting}>
            {submitting
              ? mode === 'sign-in'
                ? 'Signing in...'
                : 'Creating account...'
              : mode === 'sign-in'
                ? 'Sign in'
                : 'Create account'}
          </Button>
        </form>

        <div className="mt-6 flex items-center justify-between gap-3 border-t border-neutral-100 pt-4 text-sm text-neutral-500">
          <span>{mode === 'sign-in' ? 'Need an account?' : 'Already have an account?'}</span>
          <button
            type="button"
            className="font-medium text-neutral-900 underline decoration-neutral-300 underline-offset-4"
            onClick={() => {
              setMode((current) => (current === 'sign-in' ? 'sign-up' : 'sign-in'));
              setError(null);
              setNotice(null);
            }}
          >
            {mode === 'sign-in' ? 'Create one' : 'Sign in'}
          </button>
        </div>
      </div>
    </div>
  );
};

const LoadingScreen = () => (
  <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4 py-10">
    <div className="rounded-2xl border border-neutral-200 bg-white px-5 py-4 text-sm text-neutral-500 shadow-sm">
      Restoring your session...
    </div>
  </div>
);

const AuthGate = ({ children }: PropsWithChildren) => {
  const { isConfigured, status } = useAuth();

  if (!isConfigured || status === 'disabled' || status === 'authenticated') {
    return <>{children}</>;
  }

  if (status === 'loading') {
    return <LoadingScreen />;
  }

  return <AuthScreen />;
};

export default AuthGate;
