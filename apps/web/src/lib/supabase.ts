import { createClient, type Session, type SupabaseClient } from '@supabase/supabase-js';
import { SUPABASE_ANON_KEY, SUPABASE_URL, USE_LIVE_API_ITEMS, USE_LIVE_API_UPLOAD } from './config';

let supabaseClient: SupabaseClient | null = null;

export const isSupabaseAuthConfigured = Boolean(
  SUPABASE_URL && SUPABASE_ANON_KEY && (USE_LIVE_API_ITEMS || USE_LIVE_API_UPLOAD)
);

export const getSupabaseClient = (): SupabaseClient | null => {
  if (!isSupabaseAuthConfigured) {
    return null;
  }

  if (!supabaseClient) {
    supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        autoRefreshToken: true,
        persistSession: true
      }
    });
  }

  return supabaseClient;
};

export const getSupabaseSession = async (): Promise<Session | null> => {
  const client = getSupabaseClient();
  if (!client) {
    return null;
  }

  const {
    data: { session },
    error
  } = await client.auth.getSession();

  if (error) {
    throw error;
  }

  return session;
};

export const getAccessToken = async (): Promise<string | null> => {
  const session = await getSupabaseSession();
  return session?.access_token ?? null;
};
