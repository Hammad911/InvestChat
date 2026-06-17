/**
 * Tests for Zustand stores.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useProjectStore, useChatStore, useUIStore, useAuthStore } from "@/stores";

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ isAuthenticated: false });
  });

  it("starts unauthenticated", () => {
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("sets authenticated state", () => {
    useAuthStore.getState().setAuthenticated(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });
});

describe("useProjectStore", () => {
  beforeEach(() => {
    useProjectStore.setState({
      projects: [],
      activeProject: null,
      documents: [],
    });
  });

  it("sets projects", () => {
    const projects = [
      {
        id: "1",
        name: "Test Project",
        description: null,
        status: "active",
        created_at: "2023-01-01",
        updated_at: "2023-01-01",
        document_count: 0,
      },
    ];
    useProjectStore.getState().setProjects(projects);
    expect(useProjectStore.getState().projects).toEqual(projects);
  });

  it("sets active project", () => {
    const project = {
      id: "1",
      name: "Active",
      description: null,
      status: "active",
      created_at: "2023-01-01",
      updated_at: "2023-01-01",
      document_count: 0,
    };
    useProjectStore.getState().setActiveProject(project);
    expect(useProjectStore.getState().activeProject).toEqual(project);
  });

  it("updates a document", () => {
    const doc = {
      id: "d1",
      filename: "file",
      original_filename: "file.pdf",
      doc_type: "filing",
      file_size: 1000,
      page_count: 10,
      ingestion_status: "pending",
      chunk_count: 0,
      error_message: null,
      uploaded_at: "2023-01-01",
      ingested_at: null,
    };
    useProjectStore.getState().setDocuments([doc]);

    const updated = { ...doc, ingestion_status: "complete", chunk_count: 42 };
    useProjectStore.getState().updateDocument(updated);

    const result = useProjectStore.getState().documents[0];
    expect(result.ingestion_status).toBe("complete");
    expect(result.chunk_count).toBe(42);
  });
});

describe("useChatStore", () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      streamContent: "",
    });
  });

  it("adds a message", () => {
    const msg = {
      id: "1",
      role: "user" as const,
      content: "Hello",
      citations: null,
      created_at: "2023-01-01",
    };
    useChatStore.getState().addMessage(msg);
    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0].content).toBe("Hello");
  });

  it("appends stream content", () => {
    useChatStore.getState().appendStreamContent("Hello ");
    useChatStore.getState().appendStreamContent("World");
    expect(useChatStore.getState().streamContent).toBe("Hello World");
  });

  it("resets stream", () => {
    useChatStore.setState({ isStreaming: true, streamContent: "partial" });
    useChatStore.getState().resetStream();
    expect(useChatStore.getState().isStreaming).toBe(false);
    expect(useChatStore.getState().streamContent).toBe("");
  });
});

describe("useUIStore", () => {
  it("toggles sidebar", () => {
    const initial = useUIStore.getState().sidebarOpen;
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(!initial);
  });

  it("sets active tab", () => {
    useUIStore.getState().setActiveTab("growth");
    expect(useUIStore.getState().activeTab).toBe("growth");
  });

  it("opens and closes viewer", () => {
    const doc = {
      id: "d1",
      filename: "f",
      original_filename: "test.pdf",
      doc_type: "filing",
      file_size: 100,
      page_count: 5,
      ingestion_status: "complete",
      chunk_count: 10,
      error_message: null,
      uploaded_at: "2023-01-01",
      ingested_at: "2023-01-01",
    };
    useUIStore.getState().openViewer(doc, 3);
    expect(useUIStore.getState().viewerDoc).toEqual(doc);
    expect(useUIStore.getState().viewerPage).toBe(3);

    useUIStore.getState().closeViewer();
    expect(useUIStore.getState().viewerDoc).toBeNull();
  });
});
