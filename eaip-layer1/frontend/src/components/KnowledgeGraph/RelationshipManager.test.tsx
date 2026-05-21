import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import RelationshipManager from "./RelationshipManager";
import type { GraphNode, GraphEdge } from "../../types";

afterEach(() => {
  cleanup();
});

const mockNodes: GraphNode[] = [
  {
    id: "node-1",
    data: { label: "budget_2024.xlsx", department: "Finance", fileId: 1 },
    position: { x: 0, y: 0 },
  },
  {
    id: "node-2",
    data: { label: "policy_handbook.docx", department: "HR", fileId: 2 },
    position: { x: 100, y: 0 },
  },
  {
    id: "node-3",
    data: { label: "vendor_list.json", department: "Supply_Chain", fileId: 3 },
    position: { x: 200, y: 0 },
  },
];

const mockEdge: GraphEdge = {
  id: "5",
  source: "node-1",
  target: "node-2",
  label: "references",
};

describe("RelationshipManager", () => {
  it("renders the create relationship form with selects and input", () => {
    render(
      <RelationshipManager
        nodes={mockNodes}
        onCreateRelationship={vi.fn()}
        onDeleteRelationship={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Source File")).toBeDefined();
    expect(screen.getByLabelText("Target File")).toBeDefined();
    expect(screen.getByLabelText("Relationship Type")).toBeDefined();
    expect(screen.getByRole("button", { name: "Create Relationship" })).toBeDefined();
  });

  it("disables create button when form is incomplete", () => {
    render(
      <RelationshipManager
        nodes={mockNodes}
        onCreateRelationship={vi.fn()}
        onDeleteRelationship={vi.fn()}
      />
    );

    const createBtn = screen.getByRole("button", { name: "Create Relationship" });
    expect((createBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows delete button when an edge is selected", () => {
    render(
      <RelationshipManager
        nodes={mockNodes}
        onCreateRelationship={vi.fn()}
        onDeleteRelationship={vi.fn()}
        selectedEdge={mockEdge}
      />
    );

    expect(screen.getByRole("button", { name: "Delete Relationship" })).toBeDefined();
    expect(screen.getByText(/references/)).toBeDefined();
  });

  it("does not show delete section when no edge is selected", () => {
    render(
      <RelationshipManager
        nodes={mockNodes}
        onCreateRelationship={vi.fn()}
        onDeleteRelationship={vi.fn()}
        selectedEdge={null}
      />
    );

    expect(screen.queryByRole("button", { name: "Delete Relationship" })).toBeNull();
  });

  it("shows confirmation dialog on delete click", async () => {
    render(
      <RelationshipManager
        nodes={mockNodes}
        onCreateRelationship={vi.fn()}
        onDeleteRelationship={vi.fn()}
        selectedEdge={mockEdge}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete Relationship" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Confirm" })).toBeDefined();
      expect(screen.getByRole("button", { name: "Cancel" })).toBeDefined();
    });
  });

  it("calls onDeleteRelationship with edge id on confirm", async () => {
    const onDeleteRelationship = vi.fn().mockResolvedValue(undefined);
    const onEdgeDismiss = vi.fn();

    render(
      <RelationshipManager
        nodes={mockNodes}
        onCreateRelationship={vi.fn()}
        onDeleteRelationship={onDeleteRelationship}
        selectedEdge={mockEdge}
        onEdgeDismiss={onEdgeDismiss}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete Relationship" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Confirm" })).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() => {
      expect(onDeleteRelationship).toHaveBeenCalledWith(5);
      expect(onEdgeDismiss).toHaveBeenCalled();
    });
  });

  it("hides confirmation dialog on cancel", async () => {
    render(
      <RelationshipManager
        nodes={mockNodes}
        onCreateRelationship={vi.fn()}
        onDeleteRelationship={vi.fn()}
        selectedEdge={mockEdge}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete Relationship" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Cancel" })).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
    });

    expect(screen.getByRole("button", { name: "Delete Relationship" })).toBeDefined();
  });

  it("renders source and target select triggers with placeholder text", () => {
    render(
      <RelationshipManager
        nodes={mockNodes}
        onCreateRelationship={vi.fn()}
        onDeleteRelationship={vi.fn()}
      />
    );

    expect(screen.getByText("Select source...")).toBeDefined();
    expect(screen.getByText("Select target...")).toBeDefined();
  });
});
