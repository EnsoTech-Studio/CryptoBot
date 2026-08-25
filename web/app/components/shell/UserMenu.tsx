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
  const { user, login, logout } = useWorkspace();
  const [email, setEmail] = useState("researcher@example.com");
  const [password, setPassword] = useState("Research#2026");
  const [submitting, setSubmitting] = useState(false);

  return (
    <details className={styles.userMenu}>
      <summary>
        <span className={styles.avatar} aria-hidden="true">
          {user ? initials(user.display_name) : <Icon name="user" />}
        </span>
        <span className={styles.userIdentity}>
          <strong>{user?.display_name ?? "Đăng nhập"}</strong>
          <small>{user?.role.toLocaleLowerCase("vi") ?? "Research account"}</small>
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
            await login(email, password);
            setSubmitting(false);
          }}
        >
          <label>
            <span>Email</span>
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" required />
          </label>
          <label>
            <span>Mật khẩu</span>
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" required />
          </label>
          <button className="primary-action" type="submit" disabled={submitting}>
            {submitting ? "Đang đăng nhập…" : "Đăng nhập"}
          </button>
        </form>
      )}
    </details>
  );
}
