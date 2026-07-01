import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const projectId = process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID;
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: projectId ? `${projectId}.firebaseapp.com` : undefined,
  projectId: projectId,
  storageBucket: projectId ? `${projectId}.appspot.com` : undefined,
};

// Lazy init — never called at module load time so SSR prerendering doesn't
// try to initialize Firebase with empty env vars.
let _auth: ReturnType<typeof getAuth> | null = null;

export function firebaseAuth() {
  if (!_auth) {
    const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
    _auth = getAuth(app);
  }
  return _auth;
}
