from __future__ import annotations

from typing import Callable

from enterprise_rag.models import PipelineState


class PipelineNode:
    """A named node that processes and mutates the pipeline state."""

    def __init__(self, name: str, func: Callable[[PipelineState], PipelineState]) -> None:
        self.name = name
        self.func = func

    def __call__(self, state: PipelineState) -> PipelineState:
        return self.func(state)


class PipelineEdge:
    """A directed edge between two nodes, optionally with a condition."""

    def __init__(
        self,
        from_node: str,
        to_node: str,
        condition: Callable[[PipelineState], bool] | None = None,
    ) -> None:
        self.from_node = from_node
        self.to_node = to_node
        self.condition = condition


class PipelineGraph:
    """A directed acyclic graph execution engine for the RAG pipeline."""

    def __init__(self) -> None:
        self.nodes: dict[str, PipelineNode] = {}
        self.edges: list[PipelineEdge] = []
        self.entry_point: str | None = None

    def add_node(self, name: str, func: Callable[[PipelineState], PipelineState]) -> None:
        self.nodes[name] = PipelineNode(name, func)

    def set_entry_point(self, name: str) -> None:
        if name not in self.nodes:
            raise ValueError(f"Entry point {name} not found in nodes.")
        self.entry_point = name

    def add_edge(self, from_node: str, to_node: str) -> None:
        if from_node not in self.nodes or to_node not in self.nodes:
            raise ValueError(f"Nodes must exist before adding an edge: {from_node} -> {to_node}")
        self.edges.append(PipelineEdge(from_node, to_node))

    def add_conditional_edge(
        self,
        from_node: str,
        to_node: str,
        condition: Callable[[PipelineState], bool],
    ) -> None:
        if from_node not in self.nodes or to_node not in self.nodes:
            raise ValueError(f"Nodes must exist before adding an edge: {from_node} -> {to_node}")
        self.edges.append(PipelineEdge(from_node, to_node, condition))

    def _get_next_node(self, current_node: str, state: PipelineState) -> str | None:
        # Find edges originating from the current_node
        candidate_edges = [edge for edge in self.edges if edge.from_node == current_node]
        
        # We process conditional edges first. If a condition is met, we take that branch.
        # If no condition is met (or there are no conditional edges), we look for a fallback unconditional edge.
        conditional_edges = [edge for edge in candidate_edges if edge.condition is not None]
        unconditional_edges = [edge for edge in candidate_edges if edge.condition is None]

        for edge in conditional_edges:
            assert edge.condition is not None
            if edge.condition(state):
                return edge.to_node

        if unconditional_edges:
            # Assumes at most one unconditional edge from a node.
            return unconditional_edges[0].to_node

        return None

    def execute(self, initial_state: PipelineState) -> PipelineState:
        if not self.entry_point:
            raise ValueError("Graph entry point is not set.")

        state = initial_state
        current_node_name: str | None = self.entry_point

        while current_node_name:
            node = self.nodes[current_node_name]
            state = node(state)
            
            # Short-circuiting pattern: if a node explicitly sets short_circuited, 
            # we halt execution immediately and return the state.
            if state.short_circuited:
                break
                
            current_node_name = self._get_next_node(current_node_name, state)

        return state
