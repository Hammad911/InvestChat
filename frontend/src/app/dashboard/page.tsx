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
  Zap,
  CheckCircle,
  XCircle,
  AlertCircle,
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
    if (s === "healthy") return <CheckCircle size={14} style={{ color: "var(--color-emerald)" }} />;
    if (s === "unhealthy") return <XCircle size={14} style={{ color: "var(--color-rose)" }} />;
    return <AlertCircle size={14} style={{ color: "var(--color-amber)" }} />;
  };

  return (
    <div style={{ minHeight: "100vh" }}>
      {/* Header */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 32px",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-bg-secondary)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, var(--color-accent), #60a5fa)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Zap size={18} color="#0a0e1a" />
          </div>
          <span style={{ fontSize: "16px", fontWeight: 700 }}>InvestChat</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          {/* Model Status */}
          {health && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 14px",
                borderRadius: "20px",
                background: "var(--color-bg-card)",
                border: "1px solid var(--color-border)",
                fontSize: "12px",
              }}
            >
              <Activity size={14} style={{ color: "var(--color-accent)" }} />
              <span style={{ color: "var(--color-text-muted)" }}>
                {health.ollama_model || "No model"}
              </span>
              <StatusIcon s={health.status} />
            </div>
          )}
          <button className="btn-ghost" onClick={() => logout()} id="btn-logout">
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </header>

      {/* Main */}
      <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "40px 32px" }}>
        {/* Title Row */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "32px",
          }}
        >
          <div>
            <h1 style={{ fontSize: "28px", fontWeight: 700, marginBottom: "6px" }}>
              Due Diligence Projects
            </h1>
            <p style={{ color: "var(--color-text-muted)", fontSize: "14px" }}>
              {projects.length} project{projects.length !== 1 ? "s" : ""}
            </p>
          </div>
          <button
            className="btn-primary"
            onClick={() => setShowCreate(true)}
            id="btn-new-project"
          >
            <Plus size={16} /> New Project
          </button>
        </div>

        {/* Create Modal */}
        {showCreate && (
          <div
            className="glass-card animate-fade-in"
            style={{ padding: "28px", marginBottom: "28px" }}
          >
            <h3 style={{ fontSize: "18px", fontWeight: 600, marginBottom: "18px" }}>
              Create New Project
            </h3>
            <div style={{ display: "grid", gap: "14px" }}>
              <input
                className="input-field"
                placeholder="Project name (e.g., Acme Corp Series B)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                id="input-project-name"
              />
              <input
                className="input-field"
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                id="input-project-desc"
              />
              <div style={{ display: "flex", gap: "10px" }}>
                <button className="btn-primary" onClick={handleCreate} id="btn-create-project">
                  Create Project
                </button>
                <button className="btn-secondary" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Health Status */}
        {health && (
          <div
            style={{
              display: "flex",
              gap: "10px",
              marginBottom: "28px",
              flexWrap: "wrap",
            }}
          >
            {health.services.map((s) => (
              <div
                key={s.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "5px 12px",
                  borderRadius: "20px",
                  background: "var(--color-bg-card)",
                  border: "1px solid var(--color-border)",
                  fontSize: "12px",
                  fontWeight: 500,
                }}
              >
                <StatusIcon s={s.status} />
                <span style={{ textTransform: "capitalize", color: "var(--color-text-secondary)" }}>
                  {s.name}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Projects Grid */}
        {loading ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "20px" }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton" style={{ height: "180px" }} />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div
            className="glass-card"
            style={{
              padding: "60px 40px",
              textAlign: "center",
            }}
          >
            <FolderOpen
              size={48}
              style={{ color: "var(--color-text-muted)", marginBottom: "16px" }}
            />
            <h3 style={{ fontSize: "18px", fontWeight: 600, marginBottom: "8px" }}>
              No projects yet
            </h3>
            <p style={{ color: "var(--color-text-muted)", fontSize: "14px", marginBottom: "20px" }}>
              Create your first due diligence project to get started.
            </p>
            <button className="btn-primary" onClick={() => setShowCreate(true)}>
              <Plus size={16} /> Create Project
            </button>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "20px" }}>
            {projects.map((p, i) => (
              <div
                key={p.id}
                className="glass-card animate-fade-in"
                style={{
                  padding: "24px",
                  cursor: "pointer",
                  animationDelay: `${i * 0.05}s`,
                  opacity: 0,
                }}
                onClick={() => router.push(`/projects/${p.id}`)}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "14px",
                  }}
                >
                  <h3 style={{ fontSize: "16px", fontWeight: 600, lineHeight: 1.4, flex: 1 }}>
                    {p.name}
                  </h3>
                  <button
                    className="btn-ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(p.id);
                    }}
                    style={{ padding: "6px", color: "var(--color-text-muted)" }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>

                {p.description && (
                  <p
                    style={{
                      fontSize: "13px",
                      color: "var(--color-text-muted)",
                      marginBottom: "16px",
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
                    borderTop: "1px solid var(--color-border)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      fontSize: "13px",
                      color: "var(--color-text-muted)",
                    }}
                  >
                    <FileText size={14} />
                    {p.document_count} document{p.document_count !== 1 ? "s" : ""}
                  </div>
                  <span style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
                    {formatDate(p.updated_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
