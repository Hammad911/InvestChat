/* ══════════════════════════════════════════════════════════════════════════════
   Type definitions for the Due Diligence Copilot
   ══════════════════════════════════════════════════════════════════════════════ */

export interface User {
  id: string;
  email: string;
  full_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  document_count: number;
}

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  doc_type: string;
  file_size: number;
  page_count: number | null;
  ingestion_status: string;
  chunk_count: number;
  error_message: string | null;
  uploaded_at: string;
  ingested_at: string | null;
}

export interface Citation {
  citation_index: number;
  doc_id: string;
  doc_name: string;
  doc_type: string;
  section: string;
  page_number: number | null;
  excerpt: string;
  relevance_score: number;
}

export interface Risk {
  risk_category: string;
  severity: "High" | "Medium" | "Low";
  description: string;
  mitigation_notes: string;
  source_citations: number[];
}

export interface RiskAnalysis {
  risks: Risk[];
  overall_risk_level: string;
  summary: string;
  citations: Citation[];
  model_used: string;
  analyzed_at: string;
}

export interface GrowthOpportunity {
  opportunity_title: string;
  supporting_evidence: string[];
  confidence_score: number;
  source_citations: number[];
}

export interface GrowthAnalysis {
  opportunities: GrowthOpportunity[];
  market_outlook: string;
  summary: string;
  citations: Citation[];
}

export interface FinancialMetric {
  metric_name: string;
  value: string;
  period: string;
  yoy_change: string;
  source_citations: number[];
}

export interface FinancialAnalysis {
  metrics: FinancialMetric[];
  financial_health: string;
  key_observations: string[];
  summary: string;
  citations: Citation[];
}

export interface SummarySection {
  title: string;
  content: string;
  source_citations: number[];
}

export interface ExecutiveSummary {
  sections: SummarySection[];
  one_liner: string;
  recommendation: string;
  citations: Citation[];
}

export interface AnalysisRun {
  id: string;
  run_type: string;
  status: string;
  result: RiskAnalysis | GrowthAnalysis | FinancialAnalysis | ExecutiveSummary | null;
  model_used: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

export interface ServiceStatus {
  name: string;
  status: "healthy" | "unhealthy" | "degraded";
  details: Record<string, unknown> | null;
}

export interface HealthResponse {
  status: string;
  services: ServiceStatus[];
  llm_model: string | null;
  embed_model: string | null;
}

export interface IngestionEvent {
  stage: string;
  status: string;
  message: string;
  timestamp: string | null;
  chunk_count?: number;
}
