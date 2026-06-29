"use client";

import { Eye, EyeOff, Lock, User } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/core/auth/AuthProvider";

function validateNextParam(next: string | null): string | null {
  if (!next) return null;
  if (!next.startsWith("/")) return null;
  if (next.startsWith("//") || next.startsWith("http://") || next.startsWith("https://")) return null;
  if (next.includes(":") && !next.startsWith("/")) return null;
  return next;
}

export default function LoginPage() {
  const searchParams = useSearchParams();
  const { isAuthenticated } = useAuth();

  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const nextParam = searchParams.get("next");
  const redirectPath = validateNextParam(nextParam) ?? "/workspace";

  useEffect(() => {
    if (isAuthenticated) {
      window.location.href = redirectPath;
    }
  }, [isAuthenticated, redirectPath]);

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/v1/auth/setup-status")
      .then((r) => r.json())
      .then((data: { needs_setup?: boolean }) => {
        if (!cancelled && data.needs_setup) {
          window.location.href = "/setup";
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const body = `username=${encodeURIComponent(account)}&password=${encodeURIComponent(password)}`;
      const res = await fetch("/api/v1/auth/login/local", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
        credentials: "include",
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data?.detail?.message || "登录失败，请检查账号和密码");
        return;
      }

      window.location.href = redirectPath;
    } catch {
      setError("网络错误，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-view">
      <nav className="login-navbar">
        <div className="navbar-content">
          <Link href="/" className="brand-container">
            <img src="/onto_favicon.png" alt="logo" className="brand-logo" />
            <h1 className="brand-text">
              <span className="brand-org">本体智能</span>
            </h1>
          </Link>
        </div>
      </nav>

      <main className="login-main">
        <div className="login-card">
          <div className="card-side is-image">
            <img src="/onto_login-bg.jpg" alt="登录背景" className="login-bg-image" />
          </div>
          <div className="card-side is-form">
            <div className="login-form-wrapper">
              <header className="login-form-header">
                <p className="welcome-text">欢迎登录</p>
              </header>
              <form onSubmit={handleSubmit} className="login-form-body">
                <div className="login-form-group">
                  <label htmlFor="account">账号</label>
                  <div className="login-input-wrapper">
                    <span className="input-icon"><User size={18} /></span>
                    <input
                      id="account"
                      type="text"
                      value={account}
                      onChange={(e) => setAccount(e.target.value)}
                      placeholder="用户ID或手机号"
                      required
                    />
                  </div>
                </div>
                <div className="login-form-group">
                  <label htmlFor="password2">密码</label>
                  <div className="login-input-wrapper">
                    <span className="input-icon"><Lock size={18} /></span>
                    <input
                      id="password2"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••"
                      required
                    />
                    <button type="button" className="password-toggle" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}>
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                {error && <div className="login-error">{error}</div>}

                <button type="submit" className="login-submit-btn" disabled={loading}>
                  {loading ? "请稍候..." : "登录"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </main>

      <div className="login-footer">
        © 数据空间研究院 {new Date().getFullYear()} v0.1.0
      </div>
    </div>
  );
}
