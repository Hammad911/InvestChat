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
    if (s === "complete") return <CheckCircle size={14} style={{ color: "var(--color-emerald)" }} />;
    if (s === "failed") return <XCircle size={14} style={{ color: "var(--color-rose)" }} />;
    if (s === "pending") return <Clock size={14} style={{ color: "var(--color-text-muted)" }} />;
    return <Loader2 size={14} style={{ color: "var(--color-accent)", animation: "spin 1s linear infinite" }} />;
  };

  const tabs = [
    { id: "risks", label: "Risk Matrix", icon: Shield },
    { id: "growth", label: "Growth", icon: TrendingUp },
    { id: "financials", label: "Financials", icon: DollarSign },
    { id: "summary", label: "Summary", icon: BookOpen },
    { id: "chat", label: "Chat", icon: MessageSquare },
  ];

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Loader2 size={32} style={{ color: "var(--color-accent)", animation: "spin 1s linear infinite" }} />
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 24px", borderBottom: "1px solid var(--color-border)",
        background: "var(--color-bg-secondary)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button className="btn-ghost" onClick={() => router.push("/dashboard")} style={{ padding: "6px" }}>
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 style={{ fontSize: "16px", fontWeight: 700 }}>{activeProject?.name}</h1>
            <p style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
              {documents.length} documents • {activeProject?.status}
            </p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            display: "flex", alignItems: "center", gap: "6px", padding: "5px 12px",
            borderRadius: "20px", background: "var(--color-bg-card)", border: "1px solid var(--color-border)",
            fontSize: "12px", color: "var(--color-text-muted)",
          }}>
            <Zap size={12} style={{ color: "var(--color-accent)" }} />
            Local LLM
          </div>
        </div>
      </header>

      {/* Workspace */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* ── Left Panel: Documents ──────────────────────────────── */}
        <aside style={{
          width: "300px", borderRight: "1px solid var(--color-border)",
          background: "var(--color-bg-secondary)", display: "flex", flexDirection: "column",
          flexShrink: 0,
        }}>
          <div style={{ padding: "16px", borderBottom: "1px solid var(--color-border)" }}>
            <h3 style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-text-secondary)", marginBottom: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>
              Documents
            </h3>

            {/* Upload Zone */}
            <div
              {...getRootProps()}
              style={{
                border: `2px dashed ${isDragActive ? "var(--color-accent)" : "var(--color-border)"}`,
                borderRadius: "var(--radius-md)", padding: "20px", textAlign: "center",
                cursor: "pointer", background: isDragActive ? "var(--color-accent-dim)" : "transparent",
                transition: "all 0.2s ease",
              }}
              id="upload-zone"
            >
              <input {...getInputProps()} />
              <Upload size={20} style={{ color: "var(--color-text-muted)", margin: "0 auto 8px" }} />
              <p style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
                {uploading ? "Uploading..." : isDragActive ? "Drop files here" : "Drop files or click to upload"}
              </p>
            </div>

            <select
              value={docType} onChange={(e) => setDocType(e.target.value)}
              className="input-field" style={{ marginTop: "8px", fontSize: "12px", padding: "6px 10px" }}
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
          <div style={{ flex: 1, overflow: "auto", padding: "8px" }}>
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
                <FileText size={16} style={{ color: "var(--color-accent)", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: "13px", fontWeight: 500, whiteSpace: "nowrap",
                    overflow: "hidden", textOverflow: "ellipsis",
                  }}>
                    {doc.original_filename}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--color-text-muted)", display: "flex", gap: "8px", alignItems: "center" }}>
                    <span>{formatFileSize(doc.file_size)}</span>
                    <IngestionIcon s={doc.ingestion_status} />
                    <span>{doc.chunk_count > 0 ? `${doc.chunk_count} chunks` : doc.ingestion_status}</span>
                  </div>
                  
                  {/* Progress bar */}
                  {(doc.ingestion_status === "pending" || doc.ingestion_status === "processing") && (
                    <div style={{ height: "3px", width: "100%", background: "var(--color-bg-card)", borderRadius: "3px", overflow: "hidden", marginTop: "6px" }}>
                      <div className="animate-progress" style={{ height: "100%", width: "50%", background: "var(--color-accent)", borderRadius: "3px" }} />
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteDocument(projectId, doc.id).then(loadProject); }}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-text-muted)", padding: "4px" }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* ── Center Panel: Analysis ─────────────────────────────── */}
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Tab Navigation */}
          <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--color-border)" }}>
            <div className="tab-list" style={{ display: "inline-flex" }}>
              {tabs.map((t) => (
                <button
                  key={t.id}
                  className={`tab-item ${activeTab === t.id ? "active" : ""}`}
                  onClick={() => setActiveTab(t.id)}
                  id={`tab-${t.id}`}
                >
                  <t.icon size={14} style={{ marginRight: "6px", verticalAlign: "middle" }} />
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
                <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", gap: "16px", paddingBottom: "16px" }}>
                  {messages.length === 0 && !isStreaming && (
                    <div style={{ textAlign: "center", padding: "60px 20px" }}>
                      <MessageSquare size={40} style={{ color: "var(--color-text-muted)", margin: "0 auto 12px" }} />
                      <h3 style={{ fontSize: "16px", fontWeight: 600, marginBottom: "6px" }}>Ask anything about your documents</h3>
                      <p style={{ fontSize: "13px", color: "var(--color-text-muted)" }}>Your answers will include source citations.</p>
                    </div>
                  )}

                  {messages.map((m) => (
                    <div key={m.id} style={{
                      display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                    }}>
                      <div style={{
                        maxWidth: "75%", padding: "12px 16px", borderRadius: "var(--radius-md)",
                        background: m.role === "user" ? "var(--color-accent-dim)" : "var(--color-bg-card)",
                        border: `1px solid ${m.role === "user" ? "rgba(56,189,248,0.2)" : "var(--color-border)"}`,
                      }}>
                        <p style={{ fontSize: "14px", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{m.content}</p>
                        {m.citations && m.citations.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "8px" }}>
                            {m.citations.map((c: Citation, i: number) => (
                              <span key={i} className="citation-chip">
                                [{c.citation_index}] {c.doc_name?.substring(0, 20)}
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
                      <div style={{
                        maxWidth: "75%", padding: "12px 16px", borderRadius: "var(--radius-md)",
                        background: "var(--color-bg-card)", border: "1px solid var(--color-border)",
                      }}>
                        <p style={{ fontSize: "14px", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{streamContent}</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Input */}
                <div style={{ display: "flex", gap: "10px", padding: "12px 0" }}>
                  <input
                    className="input-field" placeholder="Ask about the documents..."
                    value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                    disabled={isStreaming}
                    id="chat-input"
                  />
                  <button className="btn-primary" onClick={handleSend} disabled={isStreaming || !chatInput.trim()} id="btn-send">
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
                    {analyzing ? <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> : <Zap size={16} />}
                    {analyzing ? "Analyzing..." : `Run ${tabs.find(t => t.id === activeTab)?.label} Analysis`}
                  </button>
                  {documents.length === 0 && (
                    <p style={{ fontSize: "12px", color: "var(--color-amber)", marginTop: "8px" }}>
                      <AlertTriangle size={12} style={{ verticalAlign: "middle", marginRight: "4px" }} />
                      Upload documents first to run analysis.
                    </p>
                  )}
                </div>

                {/* Results */}
                {analysisResult?.result && (
                  <div className="animate-fade-in">
                    {/* Risk Analysis */}
                    {activeTab === "risks" && (() => {
                      const r = analysisResult.result as RiskAnalysis;
                      return (
                        <div>
                          <div style={{ display: "flex", gap: "12px", marginBottom: "20px" }}>
                            <div className="glass-card" style={{ padding: "16px 20px", flex: 1 }}>
                              <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Overall Risk</div>
                              <div style={{ fontSize: "20px", fontWeight: 700 }} className={getSeverityColor(r.overall_risk_level || "medium")}>{r.overall_risk_level}</div>
                            </div>
                            <div className="glass-card" style={{ padding: "16px 20px", flex: 1 }}>
                              <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Risks Found</div>
                              <div style={{ fontSize: "20px", fontWeight: 700 }}>{r.risks?.length || 0}</div>
                            </div>
                          </div>

                          {r.summary && (
                            <div className="glass-card" style={{ padding: "16px 20px", marginBottom: "20px" }}>
                              <p style={{ fontSize: "14px", lineHeight: 1.7, color: "var(--color-text-secondary)" }}>{r.summary}</p>
                            </div>
                          )}

                          <div style={{ display: "grid", gap: "12px" }}>
                            {r.risks?.map((risk, i) => (
                              <div key={i} className="glass-card" style={{ padding: "20px" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
                                  <span className={`severity-dot ${risk.severity?.toLowerCase()}`} />
                                  <span className={`badge badge-${risk.severity === "High" ? "danger" : risk.severity === "Medium" ? "warning" : "success"}`}>
                                    {risk.severity}
                                  </span>
                                  <span style={{ fontSize: "13px", color: "var(--color-violet)", fontWeight: 600 }}>{risk.risk_category}</span>
                                </div>
                                <p style={{ fontSize: "14px", lineHeight: 1.7, marginBottom: "8px" }}>{risk.description}</p>
                                {risk.mitigation_notes && (
                                  <p style={{ fontSize: "13px", color: "var(--color-text-muted)", fontStyle: "italic" }}>
                                    💡 {risk.mitigation_notes}
                                  </p>
                                )}
                                {risk.source_citations?.length > 0 && (
                                  <div style={{ display: "flex", gap: "4px", marginTop: "8px" }}>
                                    {risk.source_citations.map((c) => {
                                      const cit = r.citations?.[c - 1];
                                      return <span key={c} className="citation-chip">[{c}] {cit?.doc_name?.substring(0, 18) || "Source"}</span>;
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
                            <div className="glass-card" style={{ padding: "16px 20px", marginBottom: "20px" }}>
                              <p style={{ fontSize: "14px", lineHeight: 1.7, color: "var(--color-text-secondary)" }}>{g.summary}</p>
                            </div>
                          )}
                          <div style={{ display: "grid", gap: "12px" }}>
                            {g.opportunities?.map((opp, i) => (
                              <div key={i} className="glass-card" style={{ padding: "20px" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                                  <h4 style={{ fontSize: "15px", fontWeight: 600, color: "var(--color-emerald)" }}>
                                    <TrendingUp size={14} style={{ verticalAlign: "middle", marginRight: "6px" }} />
                                    {opp.opportunity_title}
                                  </h4>
                                  <span className="badge badge-success">{Math.round((opp.confidence_score || 0) * 100)}% confidence</span>
                                </div>
                                <ul style={{ paddingLeft: "18px", margin: 0 }}>
                                  {opp.supporting_evidence?.map((ev, j) => (
                                    <li key={j} style={{ fontSize: "13px", lineHeight: 1.6, color: "var(--color-text-secondary)", marginBottom: "4px" }}>{ev}</li>
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
                          <div style={{ display: "flex", gap: "12px", marginBottom: "20px" }}>
                            <div className="glass-card" style={{ padding: "16px 20px", flex: 1 }}>
                              <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Financial Health</div>
                              <div style={{ fontSize: "20px", fontWeight: 700, color: f.financial_health === "Strong" ? "var(--color-emerald)" : "var(--color-amber)" }}>
                                {f.financial_health}
                              </div>
                            </div>
                            <div className="glass-card" style={{ padding: "16px 20px", flex: 1 }}>
                              <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Metrics Found</div>
                              <div style={{ fontSize: "20px", fontWeight: 700 }}>{f.metrics?.length || 0}</div>
                            </div>
                          </div>

                          {f.metrics?.length > 0 && (
                            <div className="glass-card" style={{ padding: "0", overflow: "hidden", marginBottom: "20px" }}>
                              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                                <thead>
                                  <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                                    {["Metric", "Value", "Period", "YoY Change"].map((h) => (
                                      <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                                        {h}
                                      </th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {f.metrics.map((m, i) => (
                                    <tr key={i} style={{ borderBottom: "1px solid var(--color-border)" }}>
                                      <td style={{ padding: "12px 16px", fontSize: "14px", fontWeight: 500 }}>{m.metric_name}</td>
                                      <td style={{ padding: "12px 16px", fontSize: "14px", fontFamily: "var(--font-mono)" }}>{m.value}</td>
                                      <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--color-text-muted)" }}>{m.period}</td>
                                      <td style={{ padding: "12px 16px", fontSize: "14px", fontWeight: 600, color: m.yoy_change?.startsWith("+") ? "var(--color-emerald)" : m.yoy_change?.startsWith("-") ? "var(--color-rose)" : "var(--color-text-secondary)" }}>
                                        {m.yoy_change}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {f.key_observations?.length > 0 && (
                            <div className="glass-card" style={{ padding: "16px 20px" }}>
                              <h4 style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-text-muted)", marginBottom: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>Key Observations</h4>
                              <ul style={{ paddingLeft: "18px", margin: 0 }}>
                                {f.key_observations.map((o, i) => (
                                  <li key={i} style={{ fontSize: "14px", lineHeight: 1.7, color: "var(--color-text-secondary)", marginBottom: "6px" }}>{o}</li>
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
                            <div className="glass-card animate-pulse-glow" style={{ padding: "20px 24px", marginBottom: "20px", borderColor: "rgba(56,189,248,0.2)" }}>
                              <p style={{ fontSize: "18px", fontWeight: 600, fontStyle: "italic", color: "var(--color-accent)" }}>"{s.one_liner}"</p>
                            </div>
                          )}

                          <div style={{ display: "grid", gap: "16px" }}>
                            {s.sections?.map((sec, i) => (
                              <div key={i} className="glass-card" style={{ padding: "24px" }}>
                                <h3 style={{ fontSize: "16px", fontWeight: 700, marginBottom: "12px", color: "var(--color-accent)" }}>
                                  {sec.title}
                                </h3>
                                <p style={{ fontSize: "14px", lineHeight: 1.8, color: "var(--color-text-secondary)", whiteSpace: "pre-wrap" }}>
                                  {sec.content}
                                </p>
                              </div>
                            ))}
                          </div>

                          {s.recommendation && (
                            <div className="glass-card" style={{ padding: "20px", marginTop: "16px", borderColor: "rgba(52,211,153,0.2)" }}>
                              <h4 style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-emerald)", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "1px" }}>
                                Recommendation
                              </h4>
                              <p style={{ fontSize: "14px", lineHeight: 1.7, color: "var(--color-text-secondary)" }}>{s.recommendation}</p>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* No results placeholder */}
                {!analysisResult && !analyzing && (
                  <div style={{ textAlign: "center", padding: "60px 20px" }}>
                    {tabs.find(t => t.id === activeTab)?.icon && (() => {
                      const Icon = tabs.find(t => t.id === activeTab)!.icon;
                      return <Icon size={40} style={{ color: "var(--color-text-muted)", margin: "0 auto 12px" }} />;
                    })()}
                    <h3 style={{ fontSize: "16px", fontWeight: 600, marginBottom: "6px" }}>
                      No analysis results yet
                    </h3>
                    <p style={{ fontSize: "13px", color: "var(--color-text-muted)" }}>
                      Click the button above to run {tabs.find(t => t.id === activeTab)?.label} analysis.
                    </p>
                  </div>
                )}

                {/* Loading */}
                {analyzing && (
                  <div style={{ textAlign: "center", padding: "60px 20px" }}>
                    <Loader2 size={32} style={{ color: "var(--color-accent)", animation: "spin 1s linear infinite", margin: "0 auto 16px" }} />
                    <h3 style={{ fontSize: "16px", fontWeight: 600, marginBottom: "6px" }}>Analyzing documents...</h3>
                    <p style={{ fontSize: "13px", color: "var(--color-text-muted)" }}>
                      This may take 30-60 seconds with local LLM inference.
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
