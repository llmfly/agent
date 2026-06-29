"use client";

import { LogOut, User } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

export function GlassHeader() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    fetch("/api/v1/auth/me", { credentials: "include" })
      .then((r) => {
        if (r.ok) setIsAuthenticated(true);
      })
      .catch(() => {});
  }, []);

  return (
    <header className="glass-header">
      <Link href="/" className="logo">
        <img src="/onto_favicon.png" alt="本体智能" className="logo-img" />
        <span className="logo-text">本体智能</span>
      </Link>
      <div className="header-actions">
        {isAuthenticated ? <UserMenu /> : <LoginButton />}
      </div>
    </header>
  );
}

function LoginButton() {
  return (
    <button
      type="button"
      className="login-btn"
      onClick={() => { window.location.href = "/login"; }}
    >
      登 录
    </button>
  );
}

function UserMenu() {
  const [open, setOpen] = useState(false);

  const handleLogout = async () => {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    window.location.href = "/";
  };

  return (
    <div className="user-menu" style={{ position: "relative" }}>
      <button
        type="button"
        className="user-avatar-btn"
        onClick={() => setOpen(!open)}
      >
        <User size={20} />
      </button>
      {open && (
        <>
          <div className="dropdown-backdrop" onClick={() => setOpen(false)} />
          <div className="user-dropdown">
            <button
              type="button"
              className="dropdown-item"
              onClick={handleLogout}
            >
              <LogOut size={16} />
              退出登录
            </button>
          </div>
        </>
      )}
    </div>
  );
}
