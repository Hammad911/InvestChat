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
import { formatDate, getStatusColor } from "@/lib/utils";
import type { HealthResponse } from "@/types";
import {
  Plus,
  FolderOpen,
  FileText,
  Trash2,
  Activity,
  LogOut,
  CheckCircle,
  XCircle,
  AlertCircle,
  ChevronRight,
  Briefcase,
  Search,
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
    if (s === "healthy") return <CheckCircle size={12} style={{ color: "var(--color-emerald)" }} />;
    if (s === "unhealthy") return <XCircle size={12} style={{ color: "var(--color-rose)" }} />;
    return <AlertCircle size={12} style={{ color: "var(--color-amber)" }} />;
  };

  return (
    <div style={{ minHeight: "100vh" }}>
      {/* Header */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 32px",
          height: "56px",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-bg-secondary)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: "var(--color-accent)",
              boxShadow: "0 0 8px rgba(212, 168, 83, 0.4)",
            }}
          />
          <span
            style={{
              fontSize: "13px",
              fontWeight: 700,
              fontFamily: "var(--font-mono)",
              letterSpacing: "2px",
              textTransform: "uppercase",
            }}
          >
            InvestChat
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Service Status */}
          {health && (
            <div style={{ display: "flex", gap: "6px" }}>
              {health.services.map((s) => (
                <div
                  key={s.name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "5px",
                    padding: "4px 10px",
                    borderRadius: "16px",
                    background: "var(--color-bg-card)",
                    border: "1px solid var(--color-border-subtle)",
                    fontSize: "11px",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 500,
                  }}
                >
                  <StatusIcon s={s.status} />
                  <span style={{ color: "var(--color-text-muted)", textTransform: "capitalize" }}>
                    {s.name}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div style={{ width: "1px", height: "20px", background: "var(--color-border)" }} />

          <button
            className="btn-ghost"
            onClick={() => logout()}
            id="btn-logout"
            style={{ fontSize: "12px" }}
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </header>

      {/* Main */}
      <main style={{ maxWidth: "1100px", margin: "0 auto", padding: "40px 32px" }}>
        {/* Title Row */}
        <div
          className="animate-fade-in"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            marginBottom: "36px",
            opacity: 0,
          }}
        >
          <div>
            <h1
              style={{
                fontSize: "26px",
                fontWeight: 700,
                marginBottom: "6px",
                letterSpacing: "-0.02em",
              }}
            >
              Projects
            </h1>
            <p
              style={{
                color: "var(--color-text-muted)",
                fontSize: "13px",
                fontFamily: "var(--font-mono)",
              }}
            >
              {projects.length} project{projects.length !== 1 ? "s" : ""} ·{" "}
              {projects.reduce((a, p) => a + p.document_count, 0)} documents
            </p>
          </div>
          <button
            className="btn-primary"
            onClick={() => setShowCreate(true)}
            id="btn-new-project"
          >
            <Plus size={15} /> New Project
          </button>
        </div>

        {/* Create Modal */}
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
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Briefcase size={16} style={{ color: "var(--color-accent)" }} />
              </div>
              <h3 style={{ fontSize: "16px", fontWeight: 600 }}>New Project</h3>
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

        {/* Projects Grid */}
        {loading ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px" }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton" style={{ height: "160px" }} />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div
            className="glass-card animate-fade-in"
            style={{
              padding: "80px 40px",
              textAlign: "center",
              opacity: 0,
            }}
          >
            <div
              style={{
                width: "56px",
                height: "56px",
                borderRadius: "var(--radius-lg)",
                background: "var(--color-bg-elevated)",
                border: "1px solid var(--color-border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 20px",
              }}
            >
              <FolderOpen size={24} style={{ color: "var(--color-text-muted)" }} />
            </div>
            <h3
              style={{
                fontSize: "17px",
                fontWeight: 600,
                marginBottom: "8px",
                letterSpacing: "-0.01em",
              }}
            >
              No projects yet
            </h3>
            <p
              style={{
                color: "var(--color-text-muted)",
                fontSize: "13.5px",
                marginBottom: "24px",
                maxWidth: "320px",
                margin: "0 auto 24px",
                lineHeight: 1.6,
              }}
            >
              Create your first due diligence project to begin analyzing documents.
            </p>
            <button className="btn-primary" onClick={() => setShowCreate(true)}>
              <Plus size={15} /> Create Project
            </button>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
              gap: "16px",
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
                    marginBottom: "10px",
                  }}
                >
                  <h3
                    style={{
                      fontSize: "15px",
                      fontWeight: 600,
                      lineHeight: 1.4,
                      flex: 1,
                      letterSpacing: "-0.01em",
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
                      padding: "5px",
                      color: "var(--color-text-muted)",
                      opacity: 0.4,
                      transition: "opacity 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.4")}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>

                {p.description && (
                  <p
                    style={{
                      fontSize: "13px",
                      color: "var(--color-text-muted)",
                      marginBottom: "auto",
                      lineHeight: 1.5,
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
                      gap: "6px",
                      fontSize: "12px",
                      fontFamily: "var(--font-mono)",
                      color: "var(--color-text-muted)",
                    }}
                  >
                    <FileText size={12} />
                    {p.document_count} doc{p.document_count !== 1 ? "s" : ""}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                    <span
                      style={{
                        fontSize: "11px",
                        fontFamily: "var(--font-mono)",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      {formatDate(p.updated_at)}
                    </span>
                    <ChevronRight size={12} style={{ color: "var(--color-text-muted)", opacity: 0.5 }} />
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
