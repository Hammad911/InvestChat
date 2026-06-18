"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, register } from "@/lib/api";
import { useAuthStore } from "@/stores";
import {
  Shield,
  ArrowRight,
  FileSearch,
  BarChart3,
  MessageSquare,
  TrendingUp,
} from "lucide-react";

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

  const features = [
    {
      icon: FileSearch,
      title: "Smart Ingestion",
      desc: "Upload SEC filings, financials & presentations — AI extracts and indexes everything.",
      num: "01",
    },
    {
      icon: Shield,
      title: "Risk Assessment",
      desc: "Automated risk matrix with severity scores and source citations.",
      num: "02",
    },
    {
      icon: BarChart3,
      title: "Financial Extraction",
      desc: "Key metrics extracted from tables with YoY comparisons.",
      num: "03",
    },
    {
      icon: MessageSquare,
      title: "Chat with Documents",
      desc: "Ask questions — get source-backed answers with inline citations.",
      num: "04",
    },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.1fr 0.9fr",
          maxWidth: "1080px",
          width: "100%",
          gap: "80px",
          alignItems: "center",
        }}
      >
        {/* Left — Branding */}
        <div>
          {/* Logo */}
          <div
            className="animate-fade-in stagger-1"
            style={{ opacity: 0, display: "flex", alignItems: "center", gap: "10px", marginBottom: "32px" }}
          >
            <div
              style={{
                width: "10px",
                height: "10px",
                borderRadius: "50%",
                background: "var(--color-accent)",
                boxShadow: "0 0 12px rgba(212, 168, 83, 0.4)",
              }}
            />
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                fontFamily: "var(--font-mono)",
                color: "var(--color-accent)",
                letterSpacing: "3px",
                textTransform: "uppercase",
              }}
            >
              InvestChat
            </span>
          </div>

          {/* Headline */}
          <h1
            className="animate-fade-in stagger-2"
            style={{
              opacity: 0,
              fontSize: "48px",
              fontWeight: 800,
              lineHeight: 1.08,
              marginBottom: "20px",
              letterSpacing: "-0.03em",
              color: "var(--color-text-primary)",
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
              lineHeight: 1.7,
              marginBottom: "40px",
              maxWidth: "400px",
            }}
          >
            Upload company documents and get AI-powered risk assessments,
            financial analysis, and executive summaries — powered by your
            own infrastructure.
          </p>

          {/* Feature List */}
          <div style={{ display: "grid", gap: "12px" }}>
            {features.map((f, i) => (
              <div
                key={i}
                className={`animate-fade-in stagger-${i + 4}`}
                style={{
                  opacity: 0,
                  display: "flex",
                  gap: "16px",
                  padding: "14px 18px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--color-bg-card)",
                  border: "1px solid var(--color-border)",
                  transition: "all 0.25s ease",
                  cursor: "default",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "rgba(212, 168, 83, 0.2)";
                  e.currentTarget.style.background = "var(--color-bg-elevated)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--color-border)";
                  e.currentTarget.style.background = "var(--color-bg-card)";
                }}
              >
                <span
                  style={{
                    fontSize: "11px",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                    color: "var(--color-accent)",
                    lineHeight: "20px",
                    flexShrink: 0,
                    opacity: 0.6,
                  }}
                >
                  {f.num}
                </span>
                <div>
                  <div
                    style={{
                      fontSize: "13.5px",
                      fontWeight: 600,
                      color: "var(--color-text-primary)",
                      marginBottom: "3px",
                    }}
                  >
                    {f.title}
                  </div>
                  <div style={{ fontSize: "12.5px", color: "var(--color-text-muted)", lineHeight: 1.5 }}>
                    {f.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right — Auth Form */}
        <div
          className="glass-card animate-slide-up"
          style={{
            padding: "44px",
            opacity: 0,
            animationDelay: "0.15s",
          }}
        >
          <div
            style={{
              width: "40px",
              height: "3px",
              borderRadius: "3px",
              background: "linear-gradient(90deg, var(--color-accent), transparent)",
              marginBottom: "28px",
            }}
          />

          <h2
            style={{
              fontSize: "22px",
              fontWeight: 700,
              marginBottom: "6px",
              color: "var(--color-text-primary)",
              letterSpacing: "-0.02em",
            }}
          >
            {isLogin ? "Welcome back" : "Create account"}
          </h2>
          <p
            style={{
              fontSize: "13.5px",
              color: "var(--color-text-muted)",
              marginBottom: "32px",
            }}
          >
            {isLogin
              ? "Sign in to access your due diligence projects"
              : "Start analyzing company documents in minutes"}
          </p>

          <form onSubmit={handleSubmit} style={{ display: "grid", gap: "18px" }}>
            {!isLogin && (
              <div>
                <label
                  style={{
                    fontSize: "11.5px",
                    fontWeight: 600,
                    fontFamily: "var(--font-mono)",
                    color: "var(--color-text-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "1px",
                    marginBottom: "8px",
                    display: "block",
                  }}
                >
                  Full Name
                </label>
                <input
                  className="input-field"
                  type="text"
                  placeholder="John Smith"
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
                  fontSize: "11.5px",
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
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
                  fontSize: "11.5px",
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
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
                  fontSize: "13px",
                  border: "1px solid rgba(248, 113, 113, 0.15)",
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
                fontSize: "14px",
                marginTop: "4px",
                opacity: loading ? 0.7 : 1,
              }}
              id="btn-submit"
            >
              {loading ? "Processing..." : isLogin ? "Sign In" : "Create Account"}
              {!loading && <ArrowRight size={15} />}
            </button>
          </form>

          <div
            style={{
              marginTop: "24px",
              textAlign: "center",
              fontSize: "13px",
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
                fontSize: "13px",
                fontFamily: "var(--font-heading)",
              }}
              id="btn-toggle-auth"
            >
              {isLogin ? "Sign up" : "Sign in"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
