import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface Doctor {
  id: number;
  name: string;
  email: string;
  isAdmin: boolean;
}

interface AuthContextType {
  doctor: Doctor | null;
  login: (doctor: Doctor) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [doctor, setDoctor] = useState<Doctor | null>(() => {
    const stored = localStorage.getItem("derm_doctor");
    return stored ? JSON.parse(stored) : null;
  });

  const login = (doc: Doctor) => {
    setDoctor(doc);
    localStorage.setItem("derm_doctor", JSON.stringify(doc));
  };

  const logout = () => {
    setDoctor(null);
    localStorage.removeItem("derm_doctor");
  };

  return (
    <AuthContext.Provider value={{ doctor, login, logout, isAuthenticated: !!doctor, isAdmin: doctor?.isAdmin ?? false }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
