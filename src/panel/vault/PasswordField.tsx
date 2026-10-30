import { useState } from "react";

interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoFocus?: boolean;
  autoComplete?: string;
}

export function PasswordField({ label, value, onChange, autoFocus, autoComplete }: Props) {
  const [show, setShow] = useState(false);
  return (
    <label className="pw-field">
      {label}
      <span className="secret-input">
        <input
          type={show ? "text" : "password"}
          value={value}
          autoFocus={autoFocus}
          autoComplete={autoComplete}
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="button" className="mini" onClick={() => setShow((v) => !v)} tabIndex={-1}>
          {show ? "Hide" : "Show"}
        </button>
      </span>
    </label>
  );
}

/** Rough guide only (length + character variety); the hard rule is ≥ 8 characters. */
export function strength(pw: string): { score: 0 | 1 | 2 | 3; label: string } {
  if (pw.length < 8) return { score: 0, label: "too short" };
  const variety = [/[a-z]/, /[A-Z]/, /\d/, /[^\w\s]/, /\s/].filter((r) => r.test(pw)).length;
  const points = (pw.length >= 12 ? 1 : 0) + (pw.length >= 16 ? 1 : 0) + (variety >= 3 ? 1 : 0);
  return points >= 2 ? { score: 3, label: "strong" } : points === 1 ? { score: 2, label: "ok" } : { score: 1, label: "weak" };
}
