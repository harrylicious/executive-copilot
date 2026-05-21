import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useGraph } from "./useGraph";
import * as client from "../api/client";
import type { GraphData, Relationship } from "../types";

vi.mock("../api/client", () => ({
  getGraphData: vi.fn(),
  createRelationship: vi.fn(),
  deleteRelationship: vi.fn(),
}));

const mockGraphData: GraphData = {
  nodes: [
    {
      id: "1",
      data: { label: "file1.pdf", department: "Finance", fileId: 1 },
      position: { x: 0, y: 0 },
    },
    {
      id: "2",
      data: { label: "file2.xlsx", department: "HR", fileId: 2 },
      position: { x: 100, y: 100 },
    },
  ],
  edges: [
    { id: "e1", source: "1", target: "2", label: "tag" },
  ],
};

const mockRelationship: Relationship = {
  id: 10,
  sourceFileId: 1,
  targetFileId: 2,
  relationshipType: "manual",
  isManual: true,
};

describe("useGraph", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches graph data on mount", async () => {
    vi.mocked(client.getGraphData).mockResolvedValue(mockGraphData);

    const { result } = renderHook(() => useGraph());

    expect(result.current.loading).toBe(true);
    expect(result.current.graphData).toBeNull();

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.graphData).toEqual(mockGraphData);
    expect(result.current.error).toBeNull();
    expect(client.getGraphData).toHaveBeenCalledOnce();
  });

  it("sets error when fetch fails", async () => {
    vi.mocked(client.getGraphData).mockRejectedValue(
      new Error("Network error")
    );

    const { result } = renderHook(() => useGraph());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.graphData).toBeNull();
    expect(result.current.error).toBe("Network error");
  });

  it("addRelationship creates relationship and refreshes graph", async () => {
    vi.mocked(client.getGraphData).mockResolvedValue(mockGraphData);
    vi.mocked(client.createRelationship).mockResolvedValue(mockRelationship);

    const { result } = renderHook(() => useGraph());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.addRelationship(1, 2, "manual");
    });

    expect(client.createRelationship).toHaveBeenCalledWith(1, 2, "manual");
    // fetchGraph is called once on mount + once after addRelationship
    expect(client.getGraphData).toHaveBeenCalledTimes(2);
  });

  it("removeRelationship deletes relationship and refreshes graph", async () => {
    vi.mocked(client.getGraphData).mockResolvedValue(mockGraphData);
    vi.mocked(client.deleteRelationship).mockResolvedValue(undefined);

    const { result } = renderHook(() => useGraph());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.removeRelationship(10);
    });

    expect(client.deleteRelationship).toHaveBeenCalledWith(10);
    // fetchGraph is called once on mount + once after removeRelationship
    expect(client.getGraphData).toHaveBeenCalledTimes(2);
  });

  it("sets error when addRelationship fails", async () => {
    vi.mocked(client.getGraphData).mockResolvedValue(mockGraphData);
    vi.mocked(client.createRelationship).mockRejectedValue(
      new Error("Conflict")
    );

    const { result } = renderHook(() => useGraph());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.addRelationship(1, 2, "manual");
    });

    expect(result.current.error).toBe("Conflict");
  });

  it("sets error when removeRelationship fails", async () => {
    vi.mocked(client.getGraphData).mockResolvedValue(mockGraphData);
    vi.mocked(client.deleteRelationship).mockRejectedValue(
      new Error("Not found")
    );

    const { result } = renderHook(() => useGraph());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.removeRelationship(99);
    });

    expect(result.current.error).toBe("Not found");
  });
});
