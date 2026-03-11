import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { getSupabaseClient, getSupabaseSession, isSupabaseAuthConfigured } from '../lib/supabase';

type AuthStatus = 'disabled' | 'loading' | 'authenticated' | 'unauthenticated';

interface SignUpResult {
  needsEmailConfirmation: boolean;
}

interface AuthContextValue {
  isConfigured: boolean;
  status: AuthStatus;
  session: Session | null;
  user: User | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<SignUpResult>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider = ({ children }: PropsWithChildren) => {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>(isSupabaseAuthConfigured ? 'loading' : 'disabled');

  useEffect(() => {
    const client = getSupabaseClient();
    if (!client) {
      setSession(null);
      setStatus('disabled');
      return;
    }

    let isMounted = true;

    getSupabaseSession()
      .then((nextSession) => {
        if (!isMounted) {
          return;
        }
        setSession(nextSession);
        setStatus(nextSession ? 'authenticated' : 'unauthenticated');
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setSession(null);
        setStatus('unauthenticated');
      });

    const {
      data: { subscription }
    } = client.auth.onAuthStateChange((_event, nextSession) => {
      if (!isMounted) {
        return;
      }
      setSession(nextSession);
      setStatus(nextSession ? 'authenticated' : 'unauthenticated');
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const value: AuthContextValue = {
    isConfigured: isSupabaseAuthConfigured,
    status,
    session,
    user: session?.user ?? null,
    async signIn(email: string, password: string) {
      const client = getSupabaseClient();
      if (!client) {
        throw new Error('Supabase Auth is not configured');
      }

      const { error } = await client.auth.signInWithPassword({ email, password });
      if (error) {
        throw error;
      }
    },
    async signUp(email: string, password: string) {
      const client = getSupabaseClient();
      if (!client) {
        throw new Error('Supabase Auth is not configured');
      }

      const { data, error } = await client.auth.signUp({ email, password });
      if (error) {
        throw error;
      }

      return {
        needsEmailConfirmation: data.session === null
      };
    },
    async signOut() {
      const client = getSupabaseClient();
      if (!client) {
        return;
      }

      const { error } = await client.auth.signOut();
      if (error) {
        throw error;
      }
    }
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return value;
};
