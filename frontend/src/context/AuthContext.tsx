'use client';

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  GoogleAuthProvider,
  User,
} from 'firebase/auth';
import { useRouter } from 'next/navigation';
import { firebaseAuth } from '@/lib/firebase';
import { apiLoginNoAuth } from '@/lib/api';
import type { Student } from '@/lib/types';

interface AuthContextValue {
  firebaseUser: User | null;
  student: Student | null;
  loading: boolean;
  isAdmin: boolean;
  signInWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
  setStudent: (s: Student) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [firebaseUser, setFirebaseUser] = useState<User | null>(null);
  const [student, setStudent] = useState<Student | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const bootstrapStudent = useCallback(async (user: User) => {
    try {
      const idToken = await user.getIdToken();
      const data = await apiLoginNoAuth(idToken, {
        display_name: user.displayName || '',
      });
      setStudent(data.student);
      if (data.needs_diagnostic) {
        router.push('/onboarding');
      }
    } catch {
      // student provisioning failed — stay on login
    }
  }, [router]);

  useEffect(() => {
    const auth = firebaseAuth();
    const unsub = onAuthStateChanged(auth, async (user) => {
      setFirebaseUser(user);
      if (user) {
        await bootstrapStudent(user);
      } else {
        setStudent(null);
      }
      setLoading(false);
    });
    return unsub;
  }, [bootstrapStudent]);

  const signInWithGoogle = async () => {
    const auth = firebaseAuth();
    const provider = new GoogleAuthProvider();
    const result = await signInWithPopup(auth, provider);
    await bootstrapStudent(result.user);
  };

  const logout = async () => {
    const auth = firebaseAuth();
    await signOut(auth);
    setStudent(null);
    router.push('/');
  };

  const isAdmin = student?.role === 'admin' || false;

  return (
    <AuthContext.Provider value={{ firebaseUser, student, loading, isAdmin, signInWithGoogle, logout, setStudent }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
