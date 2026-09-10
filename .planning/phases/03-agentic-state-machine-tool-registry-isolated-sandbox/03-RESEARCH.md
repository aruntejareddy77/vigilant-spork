# Phase 3: Agentic State Machine, Tool Registry & Isolated Sandbox - Technical Research

**Phase:** 03  
**Topic:** Agent State Machine, SQLite State Persistence, Tool Registry with JSON Schema & RBAC, Secure Isolated Code Sandbox, Bounded Self-Correction, and HITL Approval Gates  
**Author:** Antigravity Engineering (Chief Architect, AI Agent Architect, Security Engineer, Backend Engineer)  
**Date:** 2026-09-10  
**Status:** Approved  

---

## 1. Executive Summary

Phase 3 implements the cognitive orchestration core of the Sovereign AI Workbench. While Phase 1 provided the cryptographic audit ledger and network monitoring and Phase 2 provided the local model serving layer, Phase 3 transforms raw LLM/VLM inferences into an autonomous, multi-step agent capable of solving complex industrial workflows.

The system addresses four critical constraints of high-stakes industrial environments:
1. **Multi-Step Deterministic Orchestration:** Industrial workflows (e.g. equipment inspection analysis, calculation auditing) cannot be handled in a single conversational turn. The agent must decompose problems into discrete state graph transitions (planning, tool invocation, synthesis, review).
2. **Crash-Resilient State Persistence:** Long-running workflows must survive process restarts or system reboots. Intermediate artifacts and findings are persisted in a Write-Ahead Logged SQLite database (`agent_state.sqlite`).
3. **Strict Tool Fencing & RBAC:** Tools must never allow arbitrary host compromise or unauthorized actions. Every tool declares an explicit JSON Schema and RBAC clearance level, and filesystem tools enforce strict path containment within approved workspace boundaries.
4. **Deeply Isolated Code Execution:** Generating and running dynamic Python scripts requires an isolated sandbox. On Linux, network namespaces (`unshare -n`) and resource limits eliminate network access and prevent host degradation; on Windows local development, restricted subprocesses with strict timeouts, CPU/RAM constraints, and socket blocking provide deterministic cross-platform protection.
5. **Human-in-the-Loop (HITL) Verification:** High-consequence decisions (e.g. signing off on plant maintenance or finalizing legal approval notes) require mandatory human approval. The `interrupt()` primitive freezes execution cleanly and resumes only upon human authorization.

---

## 2. Requirements & Traceability Matrix

| Requirement | Description | Target Plan | Implementation Mechanism |
|:---|:---|:---|:---|
| **ORCH-01** | Multi-step planner and executor state machine decomposing requests into sequential tool and model invocations (FR-AO-1) | `03-01` | Native `StateGraph` engine with nodes, edges, conditional branches, and state schemas |
| **ORCH-02** | Session state persistence across multi-turn task iterations retaining intermediate findings without re-execution (FR-AO-4) | `03-01` | `SQLiteCheckpointer` managing `agent_state.sqlite` with thread checkpoints and step snapshots |
| **ORCH-03** | Bounded self-correction loop (default max 3 attempts) when tools or code execution produce runtime errors (FR-AO-5) | `03-01` | Conditional reflection edge in `StateGraph` injecting error tracebacks into model prompt context |
| **ORCH-04** | Human-in-the-Loop (HITL) approval gate pausing graph execution before final deliverable generation (FR-AO-6) | `03-01` | `interrupt(payload)` raising `GraphInterrupt`, saving `SUSPENDED` checkpoint, and resuming via API/CLI |
| **TOOL-01** | Tool registry defining explicit JSON Schema specifications for every available tool used for structured invocation (FR-AO-2) | `03-02` | `ToolRegistry` with Pydantic JSON Schema generation and RBAC role validation (Admin, Engineer, Auditor) |
| **TOOL-02** | Sandboxed Python execution environment enforcing zero network egress, resource limits, and execution timeouts (FR-AO-3) | `03-03` | `CodeSandbox` supporting Linux network namespaces (`unshare -n`) and Windows bounded subprocess isolation |
| **TOOL-03** | Built-in tools for file operations (fenced), structured document parsing, and engineering calculations with formula traces | `03-02` | Built-in tool library (`read_file`, `write_file`, `list_directory`, `parse_table`, `extract_text`, `execute_calculation`) |

---

## 3. Subsystem Deep-Dives & Architecture

### 3.1 The Native StateGraph Architecture

Rather than pulling in heavyweight external dependencies with deep dependency trees, the workbench implements a clean, robust, native `StateGraph` modeled after the proven LangGraph paradigm:

```
+-----------------------------------------------------------------------------------+
| StateGraph Runtime                                                                |
|                                                                                   |
|  [START] ---> (Plan / Reason Node)                                                |
|                     |                                                             |
|                     v                                                             |
|             (Select Tool Node)                                                    |
|                     |                                                             |
|                     +-------------> [Tool Execution Node]                         |
|                     |                       |                                     |
|             [Tool Error?]                   v                                     |
|               /       \            [Need Human Approval?]                         |
|            Yes         No                   /       \                             |
|            /             \               Yes         No                           |
|           v               \              /             \                          |
|  [Retries < 3?]            +------------+               v                         |
|    /         \             |            |      (Synthesize Output)                |
|  Yes          No           |            v               |                         |
|   |            \           |     [interrupt(payload)]   v                         |
|   v             v          |       (SUSPEND STATE)    [END]                       |
| (Reflect &   [Escalate     |                                                      |
|  Retry)       to Human]    |                                                      |
+-----------------------------------------------------------------------------------+
```

#### State Schema (`GraphState`)
```python
class GraphState(BaseModel):
    thread_id: str
    step_count: int = 0
    max_steps: int = 25
    messages: List[ChatMessage] = Field(default_factory=list)
    intermediate_steps: List[Dict[str, Any]] = Field(default_factory=list)
    tool_outputs: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    status: Literal["RUNNING", "SUSPENDED", "COMPLETED", "FAILED"] = "RUNNING"
    pending_approval: Optional[Dict[str, Any]] = None
```

#### The `interrupt(payload)` Mechanism
When an agent reaches a node requiring human validation:
1. The node calls `interrupt(payload={"action": "sign_approval_note", "document": "..."})`.
2. `interrupt()` raises a `GraphInterrupt(payload)` exception.
3. The graph executor catches `GraphInterrupt`, updates the state status to `SUSPENDED`, records `pending_approval=payload`, and checkpoints the entire state to `agent_state.sqlite`.
4. The executor logs an `APPROVAL_REQUIRED` event to the Phase 1 `AuditLedger`.
5. Execution halts cleanly without consuming CPU threads or active connections.
6. When the human approves via API or CLI (`sovereign workflow resume <thread_id> --decision approve`), the checkpointer loads the frozen state, injects the approval decision, updates status to `RUNNING`, and resumes graph traversal from the exact suspended node.

---

### 3.2 Tool Registry with Rigid JSON Schema & RBAC

Every tool exposed to the agent must be registered in the `ToolRegistry`:

```python
class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: Dict[str, Any]  # Valid JSON Schema
    return_schema: Optional[Dict[str, Any]] = None
    required_role: UserRole = UserRole.ENGINEER
    is_sandboxed: bool = False
```

#### Filesystem Path Fencing (Traversal Prevention)
All file-oriented tools (`read_file`, `write_file`, `list_directory`) accept relative paths and resolve them strictly against a configured workspace directory (`workspace_root`). If any path resolves outside the root (e.g. `../../etc/shadow` or `..\Windows\System32`), the tool throws a `PathSecurityViolation` before touching the filesystem.

#### Built-in Tool Specifications
1. `read_file(path: str, max_bytes: int = 65536) -> str`: Read text content with byte cap.
2. `write_file(path: str, content: str) -> Dict[str, Any]`: Write text content inside fenced workspace.
3. `list_directory(path: str = ".") -> List[Dict[str, Any]]`: List entries with file size and type.
4. `parse_table(csv_or_text: str, delimiter: str = ",") -> List[Dict[str, Any]]`: Extract structured tabular rows.
5. `extract_text(raw_data: str) -> str`: Clean and normalize text fragments.
6. `execute_calculation(formula: str, variables: Dict[str, float]) -> Dict[str, Any]`: Safely evaluate mathematical expressions using AST parser (preventing `eval()` injection) with intermediate step traces.

---

### 3.3 The Isolated Code Execution Sandbox

When the agent requires fluid code generation (e.g. processing unique CSV structures, engineering optimization loops), it executes custom Python scripts.

#### Security Threat Matrix
- **T-03-01 (Network Exfiltration):** Generated code attempts outbound network sockets (`socket.connect()`, `urllib.request`).
- **T-03-02 (Denial of Service):** Runaway `while True:` loop consuming 100% CPU.
- **T-03-03 (Host Memory Exhaustion):** Script allocates gigabytes of RAM causing OS crash.
- **T-03-04 (Filesystem Tampering):** Script attempts to delete or overwrite system files outside workspace.

#### Multi-Tier Sandbox Implementation
1. **Linux Production Environment:**
   - Spawns subprocess using `unshare -n` to create a new network namespace with no virtual interfaces attached except unconfigured loopback. Outbound network traffic is physically impossible.
   - Applies resource limits via `resource.setrlimit()`:
     - `RLIMIT_CPU`: 15 seconds.
     - `RLIMIT_AS`: 512 MB memory ceiling.
   - Ephemeral working directory mounted in `/tmp` using restricted permissions, deleted on completion.
2. **Windows Local Development & CI Fallback:**
   - Spawns isolated subprocess with `PYTHONUNBUFFERED=1` and minimal environment dictionary (strips credentials, tokens, network proxies).
   - Enforces execution timeout via `subprocess.run(timeout=15.0)` — terminates runaway processes immediately.
   - Enforces pre-execution static AST validation checking for forbidden network imports (`socket`, `requests`, `urllib`, `http.client`).
   - Ephemeral working directory created under project `scratch/sandbox/`, wiped immediately after execution.

---

## 4. Verification & Testing Architecture

### Test Matrix by Plan

| Test File | Target Plan | Requirements Tested | Core Scenarios |
|:---|:---|:---|:---|
| `test_state_graph.py` | `03-01` | `ORCH-01`, `ORCH-03` | Graph node execution, conditional edges, self-correction retry loop (max 3), error escalation. |
| `test_checkpointer.py` | `03-01` | `ORCH-02` | SQLite WAL persistence, state saving/restoration, step log querying, rollback. |
| `test_hitl_interrupt.py` | `03-01` | `ORCH-04` | `interrupt()` freezes execution, state saved as `SUSPENDED`, `resume()` continues graph traversal. |
| `test_tool_registry.py` | `03-02` | `TOOL-01` | JSON Schema generation, RBAC clearance enforcement, duplicate registration handling. |
| `test_builtin_tools.py` | `03-02` | `TOOL-03` | Fenced file I/O, path traversal prevention, tabular parsing, safe AST calculation engine. |
| `test_code_sandbox.py` | `03-03` | `TOOL-02` | Timeout termination, memory limits, network exfiltration blocking, clean scratchpad cleanup. |
| `test_workflow_cli.py` | `03-01`, `03-02` | `ORCH-01`, `TOOL-01` | CLI commands `sovereign workflow run/resume/list` and `sovereign tool list/inspect`. |

---

## 5. Conclusion

Phase 3 unites the local model capabilities with a verifiable, human-in-the-loop state machine and a strictly bounded code sandbox. This transforms the Sovereign AI Workbench into a full agentic platform capable of autonomous multi-step execution while guaranteeing mathematical containment, complete auditability, and zero network egress.
