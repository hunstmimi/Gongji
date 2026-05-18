import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getMe, login, logout, register, setAccessToken } from "../services/api";

const TOKEN_KEY = "compute_rental_access_token";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setAccessToken(token);
    if (!token) {
      setUser(null);
      setReady(true);
      return;
    }

    let active = true;
    getMe()
      .then((payload) => {
        if (active) {
          setUser(payload.user);
        }
      })
      .catch(() => {
        if (active) {
          localStorage.removeItem(TOKEN_KEY);
          setAccessToken("");
          setToken("");
          setUser(null);
        }
      })
      .finally(() => {
        if (active) {
          setReady(true);
        }
      });

    return () => {
      active = false;
    };
  }, [token]);

  async function loginAction(form) {
    const payload = await login(form);
    localStorage.setItem(TOKEN_KEY, payload.access_token);
    setAccessToken(payload.access_token);
    setToken(payload.access_token);
    setUser(payload.user);
    return payload;
  }

  async function registerAction(form) {
    const payload = await register(form);
    localStorage.setItem(TOKEN_KEY, payload.access_token);
    setAccessToken(payload.access_token);
    setToken(payload.access_token);
    setUser(payload.user);
    return payload;
  }

  async function logoutAction() {
    try {
      await logout();
    } catch {
      // Keep logout resilient even if the token is already invalid.
    }
    localStorage.removeItem(TOKEN_KEY);
    setAccessToken("");
    setToken("");
    setUser(null);
  }

  const value = useMemo(
    () => ({
      token,
      user,
      ready,
      isAuthenticated: Boolean(token && user),
      setUser,
      login: loginAction,
      register: registerAction,
      logout: logoutAction
    }),
    [ready, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
