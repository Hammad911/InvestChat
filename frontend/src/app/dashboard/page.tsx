"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getProjects,
  createProject,
  deleteProject,
  getSystemHealth,
  logout,
  isAuthenticated,
} from "@/lib/api";
import { useProjectStore, useUIStore } from "@/stores";
import { formatDate } from "@/lib/utils";
import type { HealthResponse } from "@/types";
import {
  Plus,
  FolderOpen,
  FileText,
  Trash2,
  LogOut,
  CheckCircle,
  XCircle,
  AlertCircle,
  ChevronRight,
  Briefcase,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { projects, setProjects } = useProjectStore();
  const { health, setHealth } = useUIStore();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/");
      return;
    }
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [projRes, healthRes] = await Promise.all([
        getProjects(),
        getSystemHealth().catch(() => null),
      ]);
      setProjects(projRes.projects);
      if (healthRes) setHealth(healthRes);
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    const project = await createProject(newName, newDesc || undefined);
    setProjects([project, ...projects]);
    setShowCreate(false);
    setNewName("");
    setNewDesc("");
  };

  const handleDelete = async (id: string) => {
    await deleteProject(id);
    setProjects(projects.filter((p) => p.id !== id));
  };

  const StatusIcon = ({ s }: { s: string }) => {
    if (s === "healthy") return <CheckCircle size={11} style={{ color: "var(--color-emerald)" }} />;
    if (s === "unhealthy") return <XCircle size={11} style={{ color: "var(--color-rose)" }} />;
    return <AlertCircle size={11} style={{ color: "var(--color-amber)" }} />;
  };

  return (
    <div style={{ minHeight: "100vh" }}>
      {/* ── Header Bar ──────────────────────────────────────────── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 32px",
          height: "52px",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-bg-secondary)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "20px",
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
              letterSpacing: "3px",
              textTransform: "uppercase",
              color: "var(--color-text-secondary)",
            }}
          >
            InvestChat
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {/* Service indicators */}
          {health && (
            <div style={{ display: "flex", gap: "4px" }}>
              {health.services.map((s) => (
                <div
                  key={s.name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "5px",
                    padding: "3px 9px",
                    borderRadius: "3px",
                    background: "var(--color-bg-card)",
                    border: "1px solid var(--color-border-subtle)",
                    fontSize: "10px",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                  }}
                >
                  <StatusIcon s={s.status} />
                  <span style={{ color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    {s.name}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div style={{ width: "1px", height: "18px", background: "var(--color-border)" }} />

          <button
            className="btn-ghost"
            onClick={() => logout()}
            id="btn-logout"
            style={{ fontSize: "11px", gap: "5px" }}
            aria-label="Sign out"
          >
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </header>

      {/* ── Main Content ────────────────────────────────────────── */}
      <main style={{ maxWidth: "1060px", margin: "0 auto", padding: "44px 32px" }}>
        {/* Title section — asymmetric */}
        <div
          className="animate-fade-in"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            marginBottom: "40px",
            opacity: 0,
          }}
        >
          <div>
            <h1
              style={{
                fontSize: "28px",
                fontWeight: 700,
                marginBottom: "6px",
                letterSpacing: "-0.03em",
              }}
            >
              Projects
            </h1>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-muted)",
                  letterSpacing: "0.5px",
                }}
              >
                {projects.length} project{projects.length !== 1 ? "s" : ""}
              </span>
              <span style={{ color: "var(--color-text-ghost)" }}>·</span>
              <span
                style={{
                  fontSize: "11px",
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-ghost)",
                }}
              >
                {projects.reduce((a, p) => a + p.document_count, 0)} documents
              </span>
            </div>
          </div>
          <button
            className="btn-primary"
            onClick={() => setShowCreate(true)}
            id="btn-new-project"
          >
            <Plus size={14} /> New Project
          </button>
        </div>

        {/* Create project inline form */}
        {showCreate && (
          <div
            className="glass-card animate-slide-up"
            style={{
              padding: "28px",
              marginBottom: "28px",
              opacity: 0,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--color-accent-dim)",
                  border: "1px solid rgba(207, 167, 78, 0.1)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Briefcase size={15} style={{ color: "var(--color-accent)" }} />
              </div>
              <h3 style={{ fontSize: "15px", fontWeight: 600 }}>New Project</h3>
            </div>
            <div style={{ display: "grid", gap: "12px" }}>
              <input
                className="input-field"
                placeholder="Project name (e.g., Acme Corp Series B)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
                id="input-project-name"
              />
              <input
                className="input-field"
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                id="input-project-desc"
              />
              <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                <button className="btn-primary" onClick={handleCreate} id="btn-create-project">
                  Create
                </button>
                <button className="btn-secondary" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Projects grid */}
        {loading ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "14px" }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton" style={{ height: "155px" }} />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div
            className="glass-card animate-fade-in"
            style={{
              padding: "100px 40px",
              textAlign: "center",
              opacity: 0,
            }}
          >
            <div
              style={{
                width: "52px",
                height: "52px",
                borderRadius: "var(--radius-lg)",
                background: "var(--color-bg-elevated)",
                border: "1px solid var(--color-border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 20px",
              }}
            >
              <FolderOpen size={22} style={{ color: "var(--color-text-muted)" }} />
            </div>
            <h3
              style={{
                fontSize: "16px",
                fontWeight: 600,
                marginBottom: "8px",
                letterSpacing: "-0.02em",
              }}
            >
              No projects yet
            </h3>
            <p
              style={{
                color: "var(--color-text-muted)",
                fontSize: "13px",
                marginBottom: "28px",
                maxWidth: "300px",
                margin: "0 auto 28px",
                lineHeight: 1.65,
              }}
            >
              Create your first due diligence project to start analyzing company documents.
            </p>
            <button className="btn-primary" onClick={() => setShowCreate(true)}>
              <Plus size={14} /> Create Project
            </button>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))",
              gap: "14px",
            }}
          >
            {projects.map((p, i) => (
              <div
                key={p.id}
                className={`glass-card card-accent animate-fade-in stagger-${Math.min(i + 1, 8)}`}
                style={{
                  padding: "22px 24px",
                  cursor: "pointer",
                  opacity: 0,
                  display: "flex",
                  flexDirection: "column",
                }}
                onClick={() => router.push(`/projects/${p.id}`)}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "8px",
                  }}
                >
                  <h3
                    style={{
                      fontSize: "14.5px",
                      fontWeight: 600,
                      lineHeight: 1.4,
                      flex: 1,
                      letterSpacing: "-0.015em",
                    }}
                  >
                    {p.name}
                  </h3>
                  <button
                    className="btn-ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(p.id);
                    }}
                    style={{
                      padding: "4px",
                      color: "var(--color-text-muted)",
                      opacity: 0.3,
                      transition: "opacity 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.8")}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.3")}
                    aria-label={`Delete project ${p.name}`}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>

                {p.description && (
                  <p
                    style={{
                      fontSize: "12.5px",
                      color: "var(--color-text-muted)",
                      marginBottom: "auto",
                      lineHeight: 1.55,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                    }}
                  >
                    {p.description}
                  </p>
                )}

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    paddingTop: "14px",
                    marginTop: "14px",
                    borderTop: "1px solid var(--color-border-subtle)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "5px",
                      fontSize: "11px",
                      fontFamily: "var(--font-mono)",
                      color: "var(--color-text-muted)",
                      fontWeight: 500,
                    }}
                  >
                    <FileText size={11} />
                    {p.document_count} doc{p.document_count !== 1 ? "s" : ""}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                    <span
                      style={{
                        fontSize: "10px",
                        fontFamily: "var(--font-mono)",
                        color: "var(--color-text-ghost)",
                        letterSpacing: "0.3px",
                      }}
                    >
                      {formatDate(p.updated_at)}
                    </span>
                    <ChevronRight size={11} style={{ color: "var(--color-text-ghost)" }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
