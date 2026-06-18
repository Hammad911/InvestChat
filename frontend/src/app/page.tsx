"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, register } from "@/lib/api";
import { useAuthStore } from "@/stores";
import { ArrowRight } from "lucide-react";

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { setAuthenticated } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register(email, password, fullName);
      }
      setAuthenticated(true);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        position: "relative",
      }}
    >
      {/* ── Left Panel: Brand Statement ──────────────────────────── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px 72px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Oversized background number — the "24-hour memory" element */}
        <div
          className="animate-fade-in stagger-1"
          style={{
            opacity: 0,
            position: "absolute",
            top: "50%",
            right: "-20px",
            transform: "translateY(-50%)",
            fontSize: "320px",
            fontWeight: 700,
            fontFamily: "var(--font-mono)",
            color: "rgba(207, 167, 78, 0.025)",
            lineHeight: 0.85,
            letterSpacing: "-0.05em",
            userSelect: "none",
            pointerEvents: "none",
          }}
        >
          DD
        </div>

        {/* Logo mark */}
        <div
          className="animate-fade-in stagger-1"
          style={{
            opacity: 0,
            display: "flex",
            alignItems: "center",
            gap: "12px",
            marginBottom: "56px",
          }}
        >
          <div
            style={{
              width: "28px",
              height: "2px",
              background: "linear-gradient(90deg, var(--color-accent), transparent)",
              borderRadius: "1px",
            }}
          />
          <span
            style={{
              fontSize: "11px",
              fontWeight: 700,
              fontFamily: "var(--font-mono)",
              color: "var(--color-accent)",
              letterSpacing: "4px",
              textTransform: "uppercase",
            }}
          >
            InvestChat
          </span>
        </div>

        {/* Headline — asymmetric, heavy */}
        <h1
          className="animate-type-reveal stagger-2"
          style={{
            opacity: 0,
            fontSize: "54px",
            fontWeight: 700,
            lineHeight: 1.04,
            marginBottom: "24px",
            letterSpacing: "-0.04em",
            color: "var(--color-text-primary)",
            maxWidth: "440px",
          }}
        >
          Due Diligence,
          <br />
          <span style={{ color: "var(--color-accent)" }}>Accelerated.</span>
        </h1>

        <p
          className="animate-fade-in stagger-3"
          style={{
            opacity: 0,
            fontSize: "15px",
            color: "var(--color-text-secondary)",
            lineHeight: 1.75,
            marginBottom: "52px",
            maxWidth: "380px",
          }}
        >
          Upload company filings and get AI-powered risk assessments,
          financial extraction, and executive summaries — entirely on
          your own infrastructure.
        </p>

        {/* Stats row — monospaced, asymmetric spacing */}
        <div
          className="animate-fade-in stagger-4"
          style={{
            opacity: 0,
            display: "flex",
            gap: "48px",
          }}
        >
          {[
            { value: "< 60s", label: "Analysis time" },
            { value: "100%", label: "Local / private" },
            { value: "5+", label: "Doc formats" },
          ].map((stat, i) => (
            <div key={i}>
              <div
                style={{
                  fontSize: "24px",
                  fontWeight: 700,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-primary)",
                  letterSpacing: "-0.03em",
                  marginBottom: "4px",
                }}
              >
                {stat.value}
              </div>
              <div
                style={{
                  fontSize: "10.5px",
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "1.5px",
                }}
              >
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* Bottom edge decoration */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: "72px",
            right: 0,
            height: "1px",
            background: "linear-gradient(90deg, var(--color-border-strong), transparent 80%)",
          }}
        />
      </div>

      {/* ── Right Panel: Auth Form ───────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "40px",
          borderLeft: "1px solid var(--color-border)",
          background: "var(--color-bg-secondary)",
          position: "relative",
        }}
      >
        {/* Subtle vertical accent bar */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: "25%",
            bottom: "25%",
            width: "1px",
            background: "linear-gradient(180deg, transparent, var(--color-accent), transparent)",
            opacity: 0.3,
          }}
        />

        <div
          className="animate-slide-up"
          style={{
            opacity: 0,
            width: "100%",
            maxWidth: "380px",
          }}
        >
          {/* Form header */}
          <div style={{ marginBottom: "36px" }}>
            <h2
              style={{
                fontSize: "22px",
                fontWeight: 700,
                marginBottom: "8px",
                color: "var(--color-text-primary)",
                letterSpacing: "-0.03em",
              }}
            >
              {isLogin ? "Welcome back" : "Create account"}
            </h2>
            <p
              style={{
                fontSize: "13px",
                color: "var(--color-text-muted)",
                lineHeight: 1.5,
              }}
            >
              {isLogin
                ? "Sign in to your due diligence workspace"
                : "Start analyzing company documents in minutes"}
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "grid", gap: "20px" }}>
            {!isLogin && (
              <div>
                <label
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                    color: "var(--color-text-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "1.5px",
                    marginBottom: "8px",
                    display: "block",
                  }}
                >
                  Full Name
                </label>
                <input
                  className="input-field"
                  type="text"
                  placeholder="Jane Smith"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required={!isLogin}
                  id="input-fullname"
                />
              </div>
            )}

            <div>
              <label
                style={{
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "1.5px",
                  marginBottom: "8px",
                  display: "block",
                }}
              >
                Email
              </label>
              <input
                className="input-field"
                type="email"
                placeholder="analyst@firm.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                id="input-email"
              />
            </div>

            <div>
              <label
                style={{
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "1.5px",
                  marginBottom: "8px",
                  display: "block",
                }}
              >
                Password
              </label>
              <input
                className="input-field"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                id="input-password"
              />
            </div>

            {error && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--color-rose-dim)",
                  color: "var(--color-rose)",
                  fontSize: "12.5px",
                  border: "1px solid rgba(229, 83, 75, 0.12)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
              style={{
                width: "100%",
                justifyContent: "center",
                padding: "13px",
                fontSize: "13.5px",
                marginTop: "4px",
              }}
              id="btn-submit"
            >
              {loading ? "Processing..." : isLogin ? "Sign In" : "Create Account"}
              {!loading && <ArrowRight size={14} />}
            </button>
          </form>

          {/* Toggle auth mode */}
          <div
            style={{
              marginTop: "28px",
              textAlign: "center",
              fontSize: "12.5px",
              color: "var(--color-text-muted)",
            }}
          >
            {isLogin ? "Don't have an account?" : "Already have an account?"}{" "}
            <button
              onClick={() => {
                setIsLogin(!isLogin);
                setError("");
              }}
              style={{
                background: "none",
                border: "none",
                color: "var(--color-accent)",
                cursor: "pointer",
                fontWeight: 600,
                fontSize: "12.5px",
                fontFamily: "var(--font-heading)",
                textDecoration: "none",
              }}
              id="btn-toggle-auth"
            >
              {isLogin ? "Sign up" : "Sign in"}
            </button>
          </div>

          {/* Bottom technical detail */}
          <div
            style={{
              marginTop: "48px",
              paddingTop: "20px",
              borderTop: "1px solid var(--color-border)",
              display: "flex",
              gap: "24px",
            }}
          >
            {["Gemini Flash", "Qdrant Vectors", "On-Premise"].map((tag) => (
              <span
                key={tag}
                style={{
                  fontSize: "9.5px",
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-ghost)",
                  textTransform: "uppercase",
                  letterSpacing: "1.5px",
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
