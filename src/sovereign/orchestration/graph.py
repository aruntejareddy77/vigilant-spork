"""
src/sovereign/orchestration/graph.py
Deterministic StateGraph execution engine with conditional routing and checkpointing.
"""
from typing import Any, Callable, Dict, Optional, Tuple, Union
from sovereign.orchestration.state import GraphState


END = "__end__"


class GraphInterrupt(Exception):
    """
    Raised when a node requests a pause for human-in-the-loop review or external input.
    """
    def __init__(self, payload: Dict[str, Any]):
        super().__init__(f"Graph interrupted: {payload}")
        self.payload = payload


class CompiledGraph:
    """
    Compiled graph runtime executing multi-step state transitions deterministically.
    """

    def __init__(
        self,
        nodes: Dict[str, Callable[[GraphState], Union[Dict[str, Any], GraphState]]],
        edges: Dict[str, str],
        conditional_edges: Dict[str, Tuple[Callable[[GraphState], str], Dict[str, str]]],
        entry_point: str,
        checkpointer: Optional[Any] = None,
    ):
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges
        self.entry_point = entry_point
        self.checkpointer = checkpointer

    def invoke(
        self,
        initial_state: Union[GraphState, Dict[str, Any]],
        start_node: Optional[str] = None,
    ) -> GraphState:
        """
        Execute the graph from start_node (defaults to entry_point) until END or interruption.
        """
        if isinstance(initial_state, dict):
            state = GraphState(**initial_state)
        else:
            state = initial_state

        current_node = start_node or self.entry_point
        if not current_node or current_node not in self.nodes:
            state = state.copy_and_update(
                status="FAILED",
                last_error=f"Entry point '{current_node}' is not registered in graph nodes",
            )
            return state

        # If checkpointer is configured and this is initial step 0, save start state
        if self.checkpointer and state.step_count == 0:
            self.checkpointer.save_checkpoint(state.thread_id, "__start__", state)

        while current_node != END:
            # Check maximum execution steps to prevent runaway loops
            if state.step_count >= state.max_steps:
                state = state.copy_and_update(
                    status="FAILED",
                    last_error=f"Step count exceeded maximum allowed limit ({state.max_steps})",
                )
                if self.checkpointer:
                    self.checkpointer.save_checkpoint(state.thread_id, current_node, state)
                break

            # Execute the node function
            node_fn = self.nodes[current_node]
            try:
                result = node_fn(state)
            except GraphInterrupt as interrupt_exc:
                state = state.copy_and_update(
                    step_count=state.step_count + 1,
                    status="SUSPENDED",
                    pending_approval=interrupt_exc.payload,
                )
                if self.checkpointer:
                    self.checkpointer.save_checkpoint(state.thread_id, current_node, state)
                break
            except Exception as exc:
                state = state.copy_and_update(
                    step_count=state.step_count + 1,
                    status="FAILED",
                    last_error=f"Node '{current_node}' raised unhandled exception: {str(exc)}",
                )
                if self.checkpointer:
                    self.checkpointer.save_checkpoint(state.thread_id, current_node, state)
                break

            # Apply state updates
            if isinstance(result, GraphState):
                state = result.copy_and_update(step_count=state.step_count + 1)
            elif isinstance(result, dict):
                # Check if result includes a step_count override; otherwise increment
                new_step = result.pop("step_count", state.step_count + 1)
                state = state.copy_and_update(step_count=new_step, **result)
            else:
                state = state.copy_and_update(step_count=state.step_count + 1)

            # Persist checkpoint after node execution
            if self.checkpointer:
                self.checkpointer.save_checkpoint(state.thread_id, current_node, state)

            # Check if state transitioned to suspended or failed
            if state.status in ("SUSPENDED", "FAILED"):
                break

            # Route to next node
            if current_node in self.conditional_edges:
                router_fn, path_map = self.conditional_edges[current_node]
                branch_key = router_fn(state)
                if branch_key not in path_map:
                    state = state.copy_and_update(
                        status="FAILED",
                        last_error=f"Router returned unknown branch '{branch_key}'. Expected one of {list(path_map.keys())}",
                    )
                    if self.checkpointer:
                        self.checkpointer.save_checkpoint(state.thread_id, current_node, state)
                    break
                current_node = path_map[branch_key]
            elif current_node in self.edges:
                current_node = self.edges[current_node]
            else:
                current_node = END

        if current_node == END and state.status == "RUNNING":
            state = state.copy_and_update(status="COMPLETED")
            if self.checkpointer:
                self.checkpointer.save_checkpoint(state.thread_id, END, state)

        return state


class StateGraph:
    """
    Builder for deterministic state graphs.
    """

    def __init__(self):
        self.nodes: Dict[str, Callable[[GraphState], Union[Dict[str, Any], GraphState]]] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, Tuple[Callable[[GraphState], str], Dict[str, str]]] = {}
        self.entry_point: Optional[str] = None

    def add_node(
        self,
        name: str,
        func: Callable[[GraphState], Union[Dict[str, Any], GraphState]],
    ) -> "StateGraph":
        """Register a node with a name and execution callable."""
        if name in self.nodes:
            raise ValueError(f"Node '{name}' is already registered")
        self.nodes[name] = func
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        """Designate the entry point node for graph traversal."""
        self.entry_point = name
        return self

    def add_edge(self, from_node: str, to_node: str) -> "StateGraph":
        """Add a static direct edge from one node to another."""
        self.edges[from_node] = to_node
        return self

    def add_conditional_edges(
        self,
        from_node: str,
        router_func: Callable[[GraphState], str],
        path_map: Dict[str, str],
    ) -> "StateGraph":
        """Add a conditional edge branching based on router_func output."""
        self.conditional_edges[from_node] = (router_func, path_map)
        return self

    def compile(self, checkpointer: Optional[Any] = None) -> CompiledGraph:
        """Validate and compile into an executable CompiledGraph."""
        if not self.entry_point:
            raise ValueError("StateGraph entry point must be set before compiling")
        if self.entry_point not in self.nodes:
            raise ValueError(f"Entry point '{self.entry_point}' not found in registered nodes")

        return CompiledGraph(
            nodes=dict(self.nodes),
            edges=dict(self.edges),
            conditional_edges=dict(self.conditional_edges),
            entry_point=self.entry_point,
            checkpointer=checkpointer,
        )
