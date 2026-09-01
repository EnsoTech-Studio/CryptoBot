"use client";

import { useState } from "react";

import { useWorkspace } from "../../providers/workspace";
import { Icon } from "../ui/Icon";
import styles from "./shell.module.css";

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function UserMenu() {
  const { user, login, logout, register, dataMode } = useWorkspace();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  return (
    <details className={styles.userMenu}>
      <summary>
        <span className={styles.avatar} aria-hidden="true">
          {user ? initials(user.display_name) : <Icon name="user" />}
        </span>
        <span className={styles.userIdentity}>
          <strong>{user?.display_name ?? "Nguyễn Minh"}</strong>
          <small>{user?.email ?? "student@example.com"}</small>
        </span>
        <Icon className={styles.chevron} name="chevron-down" aria-hidden="true" />
      </summary>

      {user ? (
        <div className={styles.userPopover}>
          <p>{user.email}</p>
          <button type="button" onClick={() => void logout()}>Đăng xuất</button>
        </div>
      ) : (
        <form
          className={styles.loginForm}
          onSubmit={async (event) => {
            event.preventDefault();
            setSubmitting(true);
            if (mode === "register") await register(email, password, displayName);
            else await login(email, password);
            setSubmitting(false);
          }}
        >
          <p className={styles.mockDisclosure}>{mode === "register" ? "Mật khẩu cần tối thiểu 12 ký tự." : dataMode === "mock" ? "Dữ liệu màn hình là mock; đăng nhập để dùng tài khoản thật." : "Đăng nhập để chạy backtest và discovery."}</p>
          {mode === "register" ? <label>
            <span>Tên hiển thị</span>
            <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" />
          </label> : null}
          <label>
            <span>Email</span>
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" required />
          </label>
          <label>
            <span>Mật khẩu</span>
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} minLength={12} required />
          </label>
          <button className="primary-action" type="submit" disabled={submitting}>
            {submitting ? "Đang xử lý…" : mode === "register" ? "Tạo tài khoản" : "Đăng nhập"}
          </button>
          <button type="button" onClick={() => setMode((current) => current === "login" ? "register" : "login")}>
            {mode === "login" ? "Tạo tài khoản mới" : "Đã có tài khoản? Đăng nhập"}
          </button>
        </form>
      )}
    </details>
  );
}
