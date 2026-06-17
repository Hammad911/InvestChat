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
  Zap,
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
      title: "Smart Document Ingestion",
      desc: "Upload SEC filings, financials, and presentations — AI extracts and indexes everything.",
    },
    {
      icon: Shield,
      title: "Risk Assessment",
      desc: "Automated risk matrix with severity scores and source citations.",
    },
    {
      icon: BarChart3,
      title: "Financial Extraction",
      desc: "Key metrics extracted from tables with YoY comparisons.",
    },
    {
      icon: MessageSquare,
      title: "Chat with Documents",
      desc: "Ask questions — get source-backed answers with inline citations.",
    },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          maxWidth: "1100px",
          width: "100%",
          gap: "60px",
          alignItems: "center",
        }}
      >
        {/* Left — Branding */}
        <div className="animate-fade-in">
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, var(--color-accent), #60a5fa)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Zap size={22} color="#0a0e1a" />
            </div>
            <span
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--color-accent)",
                letterSpacing: "2px",
                textTransform: "uppercase",
              }}
            >
              InvestChat
            </span>
          </div>
          <h1
            style={{
              fontSize: "42px",
              fontWeight: 800,
              lineHeight: 1.15,
              marginBottom: "16px",
              background: "linear-gradient(135deg, #f1f5f9, #94a3b8)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            AI Due Diligence
            <br />
            Copilot
          </h1>
          <p
            style={{
              fontSize: "16px",
              color: "var(--color-text-secondary)",
              lineHeight: 1.7,
              marginBottom: "36px",
              maxWidth: "420px",
            }}
          >
            Upload company documents and get instant AI-powered risk assessments,
            financial analysis, and executive summaries — all running locally with
            zero API costs.
          </p>

          <div style={{ display: "grid", gap: "16px" }}>
            {features.map((f, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: "14px",
                  padding: "12px 16px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--color-bg-card)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <f.icon
                  size={20}
                  style={{ color: "var(--color-accent)", flexShrink: 0, marginTop: "2px" }}
                />
                <div>
                  <div
                    style={{
                      fontSize: "14px",
                      fontWeight: 600,
                      color: "var(--color-text-primary)",
                      marginBottom: "2px",
                    }}
                  >
                    {f.title}
                  </div>
                  <div style={{ fontSize: "13px", color: "var(--color-text-muted)" }}>
                    {f.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right — Auth Form */}
        <div className="glass-card animate-slide-up" style={{ padding: "40px" }}>
          <h2
            style={{
              fontSize: "24px",
              fontWeight: 700,
              marginBottom: "8px",
              color: "var(--color-text-primary)",
            }}
          >
            {isLogin ? "Welcome back" : "Create account"}
          </h2>
          <p
            style={{
              fontSize: "14px",
              color: "var(--color-text-muted)",
              marginBottom: "28px",
            }}
          >
            {isLogin
              ? "Sign in to access your due diligence projects"
              : "Start analyzing company documents in minutes"}
          </p>

          <form onSubmit={handleSubmit} style={{ display: "grid", gap: "16px" }}>
            {!isLogin && (
              <div>
                <label
                  style={{
                    fontSize: "13px",
                    fontWeight: 500,
                    color: "var(--color-text-secondary)",
                    marginBottom: "6px",
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
                  fontSize: "13px",
                  fontWeight: 500,
                  color: "var(--color-text-secondary)",
                  marginBottom: "6px",
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
                  fontSize: "13px",
                  fontWeight: 500,
                  color: "var(--color-text-secondary)",
                  marginBottom: "6px",
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
                padding: "12px",
                fontSize: "15px",
                marginTop: "4px",
                opacity: loading ? 0.7 : 1,
              }}
              id="btn-submit"
            >
              {loading ? "Processing..." : isLogin ? "Sign In" : "Create Account"}
              {!loading && <ArrowRight size={16} />}
            </button>
          </form>

          <div
            style={{
              marginTop: "20px",
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
