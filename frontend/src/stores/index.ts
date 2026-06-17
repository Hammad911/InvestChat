/**
 * Zustand stores for global state management.
 */
import { create } from "zustand";
import type { Project, Document, ChatMessage, HealthResponse } from "@/types";

// ── Auth Store ──────────────────────────────────────────────────────────────

interface AuthState {
  isAuthenticated: boolean;
  setAuthenticated: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  setAuthenticated: (v) => set({ isAuthenticated: v }),
}));

// ── Project Store ───────────────────────────────────────────────────────────

interface ProjectState {
  projects: Project[];
  activeProject: Project | null;
  documents: Document[];
  setProjects: (p: Project[]) => void;
  setActiveProject: (p: Project | null) => void;
  setDocuments: (d: Document[]) => void;
  updateDocument: (d: Document) => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  projects: [],
  activeProject: null,
  documents: [],
  setProjects: (projects) => set({ projects }),
  setActiveProject: (activeProject) => set({ activeProject }),
  setDocuments: (documents) => set({ documents }),
  updateDocument: (doc) =>
    set((state) => ({
      documents: state.documents.map((d) => (d.id === doc.id ? doc : d)),
    })),
}));

// ── Chat Store ──────────────────────────────────────────────────────────────

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  streamContent: string;
  setMessages: (m: ChatMessage[]) => void;
  addMessage: (m: ChatMessage) => void;
  setStreaming: (v: boolean) => void;
  appendStreamContent: (c: string) => void;
  resetStream: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  streamContent: "",
  setMessages: (messages) => set({ messages }),
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  setStreaming: (isStreaming) => set({ isStreaming }),
  appendStreamContent: (c) => set((s) => ({ streamContent: s.streamContent + c })),
  resetStream: () => set({ streamContent: "", isStreaming: false }),
}));

// ── UI Store ────────────────────────────────────────────────────────────────

interface UIState {
  activeTab: string;
  sidebarOpen: boolean;
  viewerDoc: Document | null;
  viewerPage: number | null;
  health: HealthResponse | null;
  setActiveTab: (t: string) => void;
  toggleSidebar: () => void;
  openViewer: (doc: Document, page?: number) => void;
  closeViewer: () => void;
  setHealth: (h: HealthResponse) => void;
}

export const useUIStore = create<UIState>((set) => ({
  activeTab: "risks",
  sidebarOpen: true,
  viewerDoc: null,
  viewerPage: null,
  health: null,
  setActiveTab: (activeTab) => set({ activeTab }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  openViewer: (doc, page) => set({ viewerDoc: doc, viewerPage: page ?? 1 }),
  closeViewer: () => set({ viewerDoc: null, viewerPage: null }),
  setHealth: (health) => set({ health }),
}));
