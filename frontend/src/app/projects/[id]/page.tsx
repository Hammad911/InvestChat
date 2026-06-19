"use client";

import { useEffect, useState, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import {
  getProject,
  getDocuments,
  uploadDocument,
  deleteDocument,
  runAnalysis,
  getChatHistory,
  sendChatMessage,
  isAuthenticated,
  logout,
} from "@/lib/api";
import { useProjectStore, useChatStore, useUIStore } from "@/stores";
import { formatFileSize, formatDate, getStatusColor, getSeverityColor } from "@/lib/utils";
import type {
  Document as DocType,
  RiskAnalysis,
  GrowthAnalysis,
  FinancialAnalysis,
  ExecutiveSummary,
  Citation,
  AnalysisRun,
} from "@/types";
import {
  Upload,
  FileText,
  Trash2,
  Shield,
  TrendingUp,
  DollarSign,
  BookOpen,
  MessageSquare,
  Send,
  ArrowLeft,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  ChevronRight,
  Zap,
  AlertTriangle,
} from "lucide-react";
import { useDropzone } from "react-dropzone";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ProjectWorkspace({ params }: PageProps) {
  const { id: projectId } = use(params);
  const router = useRouter();
  const { activeProject, setActiveProject, documents, setDocuments } = useProjectStore();
  const { messages, setMessages, isStreaming, streamContent, setStreaming, appendStreamContent, resetStream, addMessage } = useChatStore();
  const { activeTab, setActiveTab } = useUIStore();

  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [docType, setDocType] = useState("other");
  const [analysisResult, setAnalysisResult] = useState<AnalysisRun | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/"); return; }
    loadProject();
  }, [projectId]);

  // Polling for pending documents
  useEffect(() => {
    const hasPending = documents.some(
      (d) => d.ingestion_status === "pending" || d.ingestion_status === "processing"
    );
    if (!hasPending) return;
    
    const interval = setInterval(() => {
      getDocuments(projectId).then(res => setDocuments(res.documents)).catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [projectId, documents]);

  const loadProject = async () => {
    try {
      const [proj, docs, chatRes] = await Promise.all([
        getProject(projectId),
        getDocuments(projectId),
        getChatHistory(projectId).catch(() => ({ messages: [] })),
      ]);
      setActiveProject(proj);
      setDocuments(docs.documents);
      setMessages(chatRes.messages);
    } catch { /* error */ }
    finally { setLoading(false); }
  };

  // ── File Upload ─────────────────────────────────────────────────────
  const onDrop = useCallback(async (files: File[]) => {
    setUploading(true);
    for (const file of files) {
      try {
        const doc = await uploadDocument(projectId, file, docType);
        setDocuments([...documents, doc]);
      } catch { /* handle */ }
    }
    setUploading(false);
    loadProject();
  }, [projectId, docType, documents]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "text/plain": [".txt"],
    },
    maxSize: 200 * 1024 * 1024,
  });

  // ── Analysis ────────────────────────────────────────────────────────
  const handleAnalysis = async (type: string) => {
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const result = await runAnalysis(projectId, type);
      setAnalysisResult(result);
    } catch { /* handle */ }
    finally { setAnalyzing(false); }
  };

  // ── Chat ────────────────────────────────────────────────────────────
  const handleSend = () => {
    if (!chatInput.trim() || isStreaming) return;
    const msg = chatInput;
    setChatInput("");
    addMessage({ id: Date.now().toString(), role: "user", content: msg, citations: null, created_at: new Date().toISOString() });
    setStreaming(true);
    resetStream();

    sendChatMessage(
      projectId,
      msg,
      (token) => appendStreamContent(token),
      (cits) => setCitations(cits as Citation[]),
      () => {
        setStreaming(false);
        loadProject();
      }
    );
  };

  // ── Status Icons ────────────────────────────────────────────────────
  const IngestionIcon = ({ s }: { s: string }) => {
    if (s === "complete") return <CheckCircle size={12} style={{ color: "var(--color-emerald)" }} />;
    if (s === "failed") return <XCircle size={12} style={{ color: "var(--color-rose)" }} />;
    if (s === "pending") return <Clock size={12} style={{ color: "var(--color-text-muted)" }} />;
    return <Loader2 size={12} style={{ color: "var(--color-accent)", animation: "spin 1s linear infinite" }} />;
  };

  const tabs = [
    { id: "risks", label: "Risks", icon: Shield },
    { id: "growth", label: "Growth", icon: TrendingUp },
    { id: "financials", label: "Financials", icon: DollarSign },
    { id: "summary", label: "Summary", icon: BookOpen },
    { id: "chat", label: "Chat", icon: MessageSquare },
  ];

  if (loading) {
    return (
      <div style={{ padding: "40px", maxWidth: "1200px", margin: "0 auto" }}>
        <div style={{ display: "flex", gap: "20px", marginBottom: "30px" }}>
          <div className="skeleton" style={{ height: "40px", width: "40px", borderRadius: "8px" }} />
          <div className="skeleton" style={{ height: "40px", flex: 1, borderRadius: "8px" }} />
        </div>
        <div style={{ display: "flex", gap: "20px" }}>
          <div className="skeleton" style={{ height: "600px", width: "280px", borderRadius: "16px" }} />
          <div className="skeleton" style={{ height: "600px", flex: 1, borderRadius: "16px" }} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 20px", height: "50px", borderBottom: "1px solid var(--color-border)",
        background: "var(--color-bg-secondary)", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button
            className="btn-ghost"
            onClick={() => router.push("/dashboard")}
            style={{ padding: "5px", color: "var(--color-text-muted)" }}
            aria-label="Back to dashboard"
          >
            <ArrowLeft size={16} />
          </button>
          <div style={{ width: "1px", height: "20px", background: "var(--color-border)" }} />
          <div>
            <h1 style={{
              fontSize: "14px", fontWeight: 600, letterSpacing: "-0.01em",
            }}>{activeProject?.name}</h1>
            <p style={{
              fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)",
            }}>
              {documents.length} doc{documents.length !== 1 ? "s" : ""} · {activeProject?.status}
            </p>
          </div>
        </div>
        <div style={{
          display: "flex", alignItems: "center", gap: "5px", padding: "4px 10px",
          borderRadius: "14px", background: "var(--color-bg-card)", border: "1px solid var(--color-border-subtle)",
          fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)",
        }}>
          <div style={{
            width: "5px", height: "5px", borderRadius: "50%",
            background: "var(--color-emerald)", boxShadow: "0 0 6px rgba(74, 222, 128, 0.5)",
          }} />
          Gemini Flash
        </div>
      </header>

      {/* Workspace */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* ── Left Panel: Documents ──────────────────────────────── */}
        <aside style={{
          width: "280px", borderRight: "1px solid var(--color-border)",
          background: "var(--color-bg-secondary)", display: "flex", flexDirection: "column",
          flexShrink: 0,
        }}>
          <div style={{ padding: "16px", borderBottom: "1px solid var(--color-border)" }}>
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              marginBottom: "14px",
            }}>
              <span style={{
                fontSize: "11px", fontWeight: 600, fontFamily: "var(--font-mono)",
                color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "1.5px",
              }}>
                Documents
              </span>
              <span style={{
                fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)",
                background: "var(--color-bg-card)", padding: "2px 7px", borderRadius: "10px",
              }}>
                {documents.length}
              </span>
            </div>

            {/* Upload Zone */}
            <div
              {...getRootProps()}
              className={`upload-zone ${isDragActive ? "active" : ""}`}
              style={{
                padding: "18px",
                ...(isDragActive ? {} : {}),
              }}
              id="upload-zone"
            >
              <input {...getInputProps()} />
              <Upload
                size={18}
                style={{
                  color: isDragActive ? "var(--color-accent)" : "var(--color-text-muted)",
                  margin: "0 auto 8px",
                  display: "block",
                }}
              />
              <p style={{
                fontSize: "12px",
                color: isDragActive ? "var(--color-accent)" : "var(--color-text-muted)",
                margin: 0,
              }}>
                {uploading
                  ? "Uploading..."
                  : isDragActive
                  ? "Drop files here"
                  : "Drop or click to upload"}
              </p>
            </div>

            <select
              value={docType} onChange={(e) => setDocType(e.target.value)}
              className="input-field"
              style={{
                marginTop: "8px", fontSize: "11px", padding: "6px 10px",
                fontFamily: "var(--font-mono)",
              }}
              id="select-doctype"
            >
              <option value="other">Auto-detect type</option>
              <option value="filing">SEC Filing</option>
              <option value="financial">Financial Statement</option>
              <option value="presentation">Presentation</option>
              <option value="market_report">Market Report</option>
            </select>
          </div>

          {/* Document List */}
          <div style={{ flex: 1, overflow: "auto", padding: "6px" }}>
            {documents.map((doc) => (
              <div
                key={doc.id}
                style={{
                  display: "flex", alignItems: "center", gap: "10px", padding: "10px 12px",
                  borderRadius: "var(--radius-sm)", cursor: "pointer",
                  transition: "background 0.15s ease",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-bg-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <FileText size={14} style={{ color: "var(--color-accent)", flexShrink: 0, opacity: 0.7 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: "12.5px", fontWeight: 500, whiteSpace: "nowrap",
                    overflow: "hidden", textOverflow: "ellipsis",
                  }}>
                    {doc.original_filename}
                  </div>
                  <div style={{
                    fontSize: "10.5px", fontFamily: "var(--font-mono)",
                    color: "var(--color-text-muted)", display: "flex", gap: "6px", alignItems: "center",
                    marginTop: "2px",
                  }}>
                    <span>{formatFileSize(doc.file_size)}</span>
                    <IngestionIcon s={doc.ingestion_status} />
                    <span>{doc.chunk_count > 0 ? `${doc.chunk_count} chunks` : doc.ingestion_status}</span>
                  </div>
                  
                  {/* Progress bar */}
                  {(doc.ingestion_status === "pending" || doc.ingestion_status === "processing") && (
                    <div style={{
                      height: "2px", width: "100%", background: "var(--color-bg-card)",
                      borderRadius: "2px", overflow: "hidden", marginTop: "6px",
                    }}>
                      <div className="animate-progress" style={{
                        height: "100%", width: "40%",
                        background: "linear-gradient(90deg, var(--color-accent), transparent)",
                        borderRadius: "2px",
                      }} />
                    </div>
                  )}
                  {/* Error message */}
                  {doc.ingestion_status === "failed" && doc.error_message && (
                    <div style={{
                      fontSize: "10px", color: "var(--color-rose)", marginTop: "4px",
                      fontFamily: "var(--font-mono)", lineHeight: 1.2
                    }}>
                      Error: {doc.error_message}
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteDocument(projectId, doc.id).then(loadProject); }}
                  className="btn-ghost"
                  style={{
                    padding: "6px",
                  }}
                  aria-label={`Delete ${doc.original_filename}`}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* ── Center Panel: Analysis ─────────────────────────────── */}
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Tab Navigation */}
          <div style={{
            padding: "10px 20px", borderBottom: "1px solid var(--color-border)",
            background: "var(--color-bg-secondary)",
          }}>
            <div className="tab-list" style={{ display: "inline-flex" }}>
              {tabs.map((t) => (
                <button
                  key={t.id}
                  className={`tab-item ${activeTab === t.id ? "active" : ""}`}
                  onClick={() => setActiveTab(t.id)}
                  id={`tab-${t.id}`}
                >
                  <t.icon size={13} style={{ marginRight: "5px", verticalAlign: "middle" }} />
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tab Content */}
          <div style={{ flex: 1, overflow: "auto", padding: "24px" }}>
            {/* ── Chat Tab ──────────────────────────────────────── */}
            {activeTab === "chat" && (
              <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                {/* Messages */}
                <div style={{
                  flex: 1, overflow: "auto", display: "flex", flexDirection: "column",
                  gap: "14px", paddingBottom: "16px",
                }}>
                  {messages.length === 0 && !isStreaming && (
                    <div style={{ textAlign: "center", padding: "80px 20px" }}>
                      <div style={{
                        width: "52px", height: "52px", borderRadius: "var(--radius-lg)",
                        background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        margin: "0 auto 16px",
                      }}>
                        <MessageSquare size={22} style={{ color: "var(--color-text-muted)" }} />
                      </div>
                      <h3 style={{
                        fontSize: "15px", fontWeight: 600, marginBottom: "6px",
                        letterSpacing: "-0.01em",
                      }}>
                        Ask anything about your documents
                      </h3>
                      <p style={{
                        fontSize: "12px", color: "var(--color-text-muted)",
                        fontFamily: "var(--font-mono)",
                      }}>
                        Answers include source citations.
                      </p>
                    </div>
                  )}

                  {messages.map((m) => (
                    <div key={m.id} style={{
                      display: "flex",
                      justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                    }}>
                      <div
                        className={m.role === "user" ? "chat-msg-user" : "chat-msg-assistant"}
                        style={{
                          maxWidth: "72%", padding: "12px 16px",
                        }}
                      >
                        <p style={{
                          fontSize: "13.5px", lineHeight: 1.7, whiteSpace: "pre-wrap",
                          margin: 0,
                        }}>{m.content}</p>
                        {m.citations && m.citations.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "10px" }}>
                            {m.citations.map((c: Citation, i: number) => (
                              <span key={i} className="citation-chip">
                                [{c.citation_index}] {c.doc_name?.substring(0, 18)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Streaming */}
                  {isStreaming && streamContent && (
                    <div style={{ display: "flex", justifyContent: "flex-start" }}>
                      <div className="chat-msg-assistant" style={{ maxWidth: "72%", padding: "12px 16px" }}>
                        <p style={{
                          fontSize: "13.5px", lineHeight: 1.7, whiteSpace: "pre-wrap", margin: 0,
                        }}>{streamContent}</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Input */}
                <div style={{
                  display: "flex", gap: "8px", paddingTop: "12px",
                  borderTop: "1px solid var(--color-border)",
                }}>
                  <input
                    className="input-field"
                    placeholder="Ask about the documents..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                    disabled={isStreaming}
                    style={{ fontSize: "13.5px" }}
                    id="chat-input"
                  />
                  <button
                    className="btn-primary"
                    onClick={handleSend}
                    disabled={isStreaming || !chatInput.trim()}
                    style={{ padding: "12px 18px", flexShrink: 0 }}
                    id="btn-send"
                    aria-label="Send message"
                  >
                    <Send size={16} />
                  </button>
                </div>
              </div>
            )}

            {/* ── Analysis Tabs ──────────────────────────────────── */}
            {activeTab !== "chat" && (
              <div>
                {/* Run Button */}
                <div style={{ marginBottom: "24px" }}>
                  <button
                    className="btn-primary"
                    onClick={() => handleAnalysis(activeTab === "summary" ? "summary" : activeTab)}
                    disabled={analyzing || documents.length === 0}
                    style={{ opacity: analyzing ? 0.7 : 1 }}
                    id={`btn-run-${activeTab}`}
                  >
                    {analyzing
                      ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
                      : <Zap size={14} />
                    }
                    {analyzing ? "Analyzing..." : `Run ${tabs.find(t => t.id === activeTab)?.label} Analysis`}
                  </button>
                  {documents.length === 0 && (
                    <p style={{
                      fontSize: "12px", color: "var(--color-amber)",
                      marginTop: "8px", fontFamily: "var(--font-mono)",
                    }}>
                      <AlertTriangle size={11} style={{ verticalAlign: "middle", marginRight: "4px" }} />
                      Upload documents first to run analysis.
                    </p>
                  )}
                </div>

                {/* Results */}
                {analysisResult?.result && (
                  <div className="animate-fade-in" style={{ opacity: 0 }}>
                    {/* Risk Analysis */}
                    {activeTab === "risks" && (() => {
                      const r = analysisResult.result as RiskAnalysis;
                      return (
                        <div>
                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "20px" }}>
                            <div className="metric-card">
                              <div className="metric-label">Overall Risk</div>
                              <div
                                className="metric-value"
                                style={{
                                  color: r.overall_risk_level?.toLowerCase() === "high"
                                    ? "var(--color-rose)"
                                    : r.overall_risk_level?.toLowerCase() === "medium"
                                    ? "var(--color-amber)"
                                    : "var(--color-emerald)",
                                  textTransform: "uppercase",
                                }}
                              >
                                {r.overall_risk_level}
                              </div>
                            </div>
                            <div className="metric-card">
                              <div className="metric-label">Risks Found</div>
                              <div className="metric-value">{r.risks?.length || 0}</div>
                            </div>
                          </div>

                          {r.summary && (
                            <div className="glass-card" style={{ padding: "18px 22px", marginBottom: "20px" }}>
                              <p style={{
                                fontSize: "13.5px", lineHeight: 1.75, color: "var(--color-text-secondary)",
                                margin: 0,
                              }}>{r.summary}</p>
                            </div>
                          )}

                          <div style={{ display: "grid", gap: "10px" }}>
                            {r.risks?.map((risk, i) => (
                              <div
                                key={i}
                                className="glass-card"
                                style={{
                                  padding: "20px 22px",
                                  borderLeft: `3px solid ${
                                    risk.severity === "High" ? "var(--color-rose)"
                                    : risk.severity === "Medium" ? "var(--color-amber)"
                                    : "var(--color-emerald)"
                                  }`,
                                }}
                              >
                                <div style={{
                                  display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px",
                                }}>
                                  <span className={`badge badge-${
                                    risk.severity === "High" ? "danger"
                                    : risk.severity === "Medium" ? "warning"
                                    : "success"
                                  }`}>
                                    {risk.severity}
                                  </span>
                                  <span style={{
                                    fontSize: "12px", fontFamily: "var(--font-mono)",
                                    color: "var(--color-violet)", fontWeight: 600,
                                  }}>
                                    {risk.risk_category}
                                  </span>
                                </div>
                                <p style={{
                                  fontSize: "13.5px", lineHeight: 1.7, marginBottom: "8px", margin: 0,
                                }}>
                                  {risk.description}
                                </p>
                                {risk.mitigation_notes && (
                                  <p style={{
                                    fontSize: "12.5px", color: "var(--color-text-muted)",
                                    fontStyle: "italic", margin: "10px 0 0",
                                  }}>
                                    → {risk.mitigation_notes}
                                  </p>
                                )}
                                {risk.source_citations?.length > 0 && (
                                  <div style={{ display: "flex", gap: "4px", marginTop: "10px" }}>
                                    {risk.source_citations.map((c) => {
                                      const cit = r.citations?.[c - 1];
                                      return <span key={c} className="citation-chip">[{c}] {cit?.doc_name?.substring(0, 16) || "Source"}</span>;
                                    })}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })()}

                    {/* Growth Analysis */}
                    {activeTab === "growth" && (() => {
                      const g = analysisResult.result as GrowthAnalysis;
                      return (
                        <div>
                          {g.summary && (
                            <div className="glass-card" style={{ padding: "18px 22px", marginBottom: "20px" }}>
                              <p style={{
                                fontSize: "13.5px", lineHeight: 1.75, color: "var(--color-text-secondary)",
                                margin: 0,
                              }}>{g.summary}</p>
                            </div>
                          )}
                          <div style={{ display: "grid", gap: "10px" }}>
                            {g.opportunities?.map((opp, i) => (
                              <div
                                key={i}
                                className="glass-card"
                                style={{
                                  padding: "20px 22px",
                                  borderLeft: "3px solid var(--color-emerald)",
                                }}
                              >
                                <div style={{
                                  display: "flex", justifyContent: "space-between", alignItems: "center",
                                  marginBottom: "10px",
                                }}>
                                  <h4 style={{
                                    fontSize: "14px", fontWeight: 600, color: "var(--color-emerald)",
                                    margin: 0, display: "flex", alignItems: "center", gap: "6px",
                                  }}>
                                    <TrendingUp size={14} />
                                    {opp.opportunity_title}
                                  </h4>
                                  <span className="badge badge-success">
                                    {Math.round((opp.confidence_score || 0) * 100)}%
                                  </span>
                                </div>
                                <ul style={{ paddingLeft: "16px", margin: 0 }}>
                                  {opp.supporting_evidence?.map((ev, j) => (
                                    <li key={j} style={{
                                      fontSize: "13px", lineHeight: 1.65, color: "var(--color-text-secondary)",
                                      marginBottom: "3px",
                                    }}>{ev}</li>
                                  ))}
                                </ul>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })()}

                    {/* Financial Analysis */}
                    {activeTab === "financials" && (() => {
                      const f = analysisResult.result as FinancialAnalysis;
                      return (
                        <div>
                          <div style={{
                            display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "20px",
                          }}>
                            <div className="metric-card">
                              <div className="metric-label">Financial Health</div>
                              <div
                                className="metric-value"
                                style={{
                                  color: f.financial_health === "Strong"
                                    ? "var(--color-emerald)"
                                    : "var(--color-amber)",
                                }}
                              >
                                {f.financial_health}
                              </div>
                            </div>
                            <div className="metric-card">
                              <div className="metric-label">Metrics</div>
                              <div className="metric-value">{f.metrics?.length || 0}</div>
                            </div>
                          </div>

                          {f.metrics?.length > 0 && (
                            <div className="glass-card" style={{
                              padding: 0, overflow: "hidden", marginBottom: "20px",
                            }}>
                              <table className="data-table">
                                <thead>
                                  <tr>
                                    {["Metric", "Value", "Period", "YoY Change"].map((h) => (
                                      <th key={h}>{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {f.metrics.map((m, i) => (
                                    <tr key={i}>
                                      <td style={{ fontWeight: 500 }}>{m.metric_name}</td>
                                      <td className="mono">{m.value}</td>
                                      <td style={{ color: "var(--color-text-muted)", fontSize: "13px" }}>{m.period}</td>
                                      <td style={{
                                        fontWeight: 600, fontFamily: "var(--font-mono)", fontSize: "13px",
                                        color: m.yoy_change?.startsWith("+")
                                          ? "var(--color-emerald)"
                                          : m.yoy_change?.startsWith("-")
                                          ? "var(--color-rose)"
                                          : "var(--color-text-secondary)",
                                      }}>
                                        {m.yoy_change}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {f.key_observations?.length > 0 && (
                            <div className="glass-card" style={{ padding: "18px 22px" }}>
                              <h4 style={{
                                fontSize: "11px", fontWeight: 600, fontFamily: "var(--font-mono)",
                                color: "var(--color-text-muted)", marginBottom: "12px",
                                textTransform: "uppercase", letterSpacing: "1px",
                              }}>Key Observations</h4>
                              <ul style={{ paddingLeft: "16px", margin: 0 }}>
                                {f.key_observations.map((o, i) => (
                                  <li key={i} style={{
                                    fontSize: "13.5px", lineHeight: 1.7, color: "var(--color-text-secondary)",
                                    marginBottom: "5px",
                                  }}>{o}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {/* Executive Summary */}
                    {activeTab === "summary" && (() => {
                      const s = analysisResult.result as ExecutiveSummary;
                      return (
                        <div>
                          {s.one_liner && (
                            <div
                              className="glass-card"
                              style={{
                                padding: "22px 26px", marginBottom: "20px",
                                borderLeft: "3px solid var(--color-accent)",
                                background: "var(--color-accent-glow)",
                              }}
                            >
                              <p style={{
                                fontSize: "16px", fontWeight: 600, fontStyle: "italic",
                                color: "var(--color-accent)", lineHeight: 1.5, margin: 0,
                              }}>
                                &ldquo;{s.one_liner}&rdquo;
                              </p>
                            </div>
                          )}

                          <div style={{ display: "grid", gap: "12px" }}>
                            {s.sections?.map((sec, i) => (
                              <div key={i} className="glass-card" style={{ padding: "22px 24px" }}>
                                <h3 style={{
                                  fontSize: "14px", fontWeight: 700, marginBottom: "10px",
                                  color: "var(--color-accent)", letterSpacing: "-0.01em",
                                }}>
                                  {sec.title}
                                </h3>
                                <p style={{
                                  fontSize: "13.5px", lineHeight: 1.8, color: "var(--color-text-secondary)",
                                  whiteSpace: "pre-wrap", margin: 0,
                                }}>
                                  {sec.content}
                                </p>
                              </div>
                            ))}
                          </div>

                          {s.recommendation && (
                            <div
                              className="glass-card"
                              style={{
                                padding: "20px 22px", marginTop: "12px",
                                borderLeft: "3px solid var(--color-emerald)",
                              }}
                            >
                              <h4 style={{
                                fontSize: "11px", fontWeight: 600, fontFamily: "var(--font-mono)",
                                color: "var(--color-emerald)", marginBottom: "10px",
                                textTransform: "uppercase", letterSpacing: "1px",
                              }}>
                                Recommendation
                              </h4>
                              <p style={{
                                fontSize: "13.5px", lineHeight: 1.7, color: "var(--color-text-secondary)",
                                margin: 0,
                              }}>{s.recommendation}</p>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* No results placeholder */}
                {!analysisResult && !analyzing && (
                  <div style={{ textAlign: "center", padding: "80px 20px" }}>
                    {tabs.find(t => t.id === activeTab)?.icon && (() => {
                      const Icon = tabs.find(t => t.id === activeTab)!.icon;
                      return (
                        <div style={{
                          width: "52px", height: "52px", borderRadius: "var(--radius-lg)",
                          background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          margin: "0 auto 16px",
                        }}>
                          <Icon size={22} style={{ color: "var(--color-text-muted)" }} />
                        </div>
                      );
                    })()}
                    <h3 style={{
                      fontSize: "15px", fontWeight: 600, marginBottom: "6px",
                      letterSpacing: "-0.01em",
                    }}>
                      No analysis results yet
                    </h3>
                    <p style={{
                      fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)",
                    }}>
                      Run {tabs.find(t => t.id === activeTab)?.label} analysis to see results.
                    </p>
                  </div>
                )}

                {/* Loading */}
                {analyzing && (
                  <div style={{ textAlign: "center", padding: "80px 20px" }}>
                    <Loader2 size={28} style={{
                      color: "var(--color-accent)", animation: "spin 1s linear infinite",
                      margin: "0 auto 16px", display: "block",
                    }} />
                    <h3 style={{
                      fontSize: "15px", fontWeight: 600, marginBottom: "6px",
                      letterSpacing: "-0.01em",
                    }}>
                      Analyzing documents...
                    </h3>
                    <p style={{
                      fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)",
                    }}>
                      This may take 30–60 seconds.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
