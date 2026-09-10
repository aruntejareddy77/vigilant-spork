# Phase 2: Local Model Management, Adapters & VRAM Scheduler - Technical Research

**Phase:** 02  
**Topic:** Model Manager Interface, Pluggable Inference Adapters, Task Routing, and VRAM-Aware Scheduling  
**Author:** Antigravity Engineering (Chief Architect, AI Orchestrator Engineer, ML Engineer)  
**Date:** 2026-09-10  
**Status:** Approved  

---

## 1. Executive Summary

Phase 2 builds the local model serving and management foundation for the Sovereign AI Workbench. Operating strictly inside an air-gapped industrial enclave (0 external network egress), the workbench must manage multiple open-weight LLMs and VLMs (such as Qwen 2.5/3, DeepSeek, and Florence-2) across diverse local runtime engines (SGLang, vLLM, Ollama, llama.cpp), while guaranteeing deterministic fallback on hardware lacking discrete GPUs.

The primary engineering challenge is operating enterprise-grade agentic capabilities within a reference 24GB VRAM GPU envelope (or multi-model environments). Holding reasoning, coding, vision, and embedding models in GPU VRAM simultaneously is physically impossible without dynamic orchestration. Phase 2 introduces:
1. **A uniform model adapter interface and declarative manifest catalog** allowing hot-registration of models without changing orchestrator code.
2. **Pluggable inference adapters** providing a standardized abstraction over local SGLang, vLLM, Ollama, llama.cpp, and a deterministic Mock adapter.
3. **A heuristic and capability-based task auto-router** that parses incoming intents and binds them to the optimal registered model.
4. **A VRAM-aware model scheduler** with dynamic memory accounting, LRU swapping, and fail-safe out-of-memory guards.

---

## 2. Requirements & Traceability Matrix

| Requirement | Description | Target Plan | Implementation Mechanism |
|:---|:---|:---|:---|
| **MODL-01** | Pluggable adapter interface supporting local open-weight model registration via YAML/JSON manifest without modifying orchestrator code (FR-MM-1) | `02-01` | `BaseModelAdapter` ABC + `ModelManifest` Pydantic schema + `ModelRegistry` catalog |
| **MODL-02** | Task-to-model auto-routing based on task classification (text drafting, code, multimodal, calculation) (FR-MM-2) | `02-03` | `TaskRouter` with deterministic keyword heuristics, capability matching, and CLI manual override (`--model`) |
| **MODL-03** | GPU memory-aware scheduling preventing OOM crashes on single 24GB-class GPU via dynamic loading/unloading (FR-MM-3) | `02-03` | `VRAMScheduler` tracking allocated VRAM, memory threshold guards, and LRU eviction |
| **MODL-04** | Deterministic test/mock model adapter allowing full end-to-end verification without discrete GPU hardware | `02-02` | `MockModelAdapter` with canned responses, structured JSON generators, and simulated VRAM budgets |

---

## 3. Technology Stack & Local Engine Comparison

### 3.1 Local Inference Engines

In sovereign air-gapped industrial enclaves, external API providers (OpenAI, Anthropic) are strictly forbidden. All inference runs locally via one of the following engines:

```
+------------------+----------------------------------+----------------------------------+------------------------------+
| Inference Engine | Core Architecture & Advantages   | Limitations & Memory Model       | Target Workbench Workload    |
+------------------+----------------------------------+----------------------------------+------------------------------+
| SGLang           | RadixAttention prefix caching,   | Tighter hardware coupling,       | Core multi-turn agent loops, |
|                  | high throughput for VLMs and    | complex setup for multi-model    | structured JSON tool calls,  |
|                  | constrained JSON schema output.  | co-location.                     | visual schematic reasoning.  |
+------------------+----------------------------------+----------------------------------+------------------------------+
| vLLM             | PagedAttention, continuous       | Pre-allocates ~90% VRAM by       | High-throughput RAG chunk    |
|                  | batching, OpenAI-compatible      | default unless gpu_memory_util   | embeddings & bulk document   |
|                  | HTTP server.                     | is constrained.                  | summarization.               |
+------------------+----------------------------------+----------------------------------+------------------------------+
| Ollama           | Extremely simple deployment,     | Serializes concurrent requests   | Lightweight edge nodes and   |
|                  | unified REST API, automated GGUF | per model, limited prefix cache. | rapid local development.     |
|                  | management.                      |                                  |                              |
+------------------+----------------------------------+----------------------------------+------------------------------+
| llama.cpp        | Direct GGUF execution, minimal   | Slower batched throughput,       | CPU-only fallback and low-   |
|                  | overhead, CPU/GPU offloading.    | contiguous KV cache allocation.  | VRAM ruggedized laptops.     |
+------------------+----------------------------------+----------------------------------+------------------------------+
| Mock Adapter     | 100% in-memory Python mock,      | Synthetic/canned responses only. | CI/CD testing, air-gapped    |
|                  | deterministic latency/memory.    |                                  | developer environments.      |
+------------------+----------------------------------+----------------------------------+------------------------------+
```

### 3.2 Standardization Strategy: OpenAI-Compatible Protocol vs Direct Python Process
Modern local inference runtimes (SGLang, vLLM, Ollama, llama-server) universally expose HTTP endpoints conforming to the OpenAI Chat Completion API (`/v1/chat/completions`) and Embedding API (`/v1/embeddings`) with local-specific extensions:
- SGLang exposes `/v1/chat/completions` and `/generate` on `127.0.0.1:30000`.
- vLLM exposes `/v1/chat/completions` on `127.0.0.1:8000`.
- Ollama exposes `/api/chat` and `/v1/chat/completions` on `127.0.0.1:11434`.
- llama-server exposes `/v1/chat/completions` on `127.0.0.1:8080`.

**Architectural Decision:** Rather than tightly coupling Python code to multiple conflicting C++/CUDA shared libraries (`torch`, `vllm`, `sglang` in the same Python process), `sovereign` adopts a **Unified Local HTTP/Process Adapter Pattern**:
- Local engines run as loopback-bound localhost child processes or pre-deployed local daemons.
- The `BaseModelAdapter` issues local HTTP calls (strictly to `127.0.0.1`, permitted under Phase 1's loopback network policy).
- The `MockModelAdapter` executes directly in-memory without starting external processes.

---

## 4. Key Architectural Patterns & Schemas

### 4.1 Declarative Model Manifest Schema (`model_manifest.yaml`)

Each registered model is declared via a standard YAML/JSON manifest:

```yaml
schema_version: "1.0.0"
model_id: "qwen-2.5-14b-instruct"
name: "Qwen 2.5 14B Instruct"
family: "qwen"
capabilities:
  - "text_drafting"
  - "reasoning"
  - "code_generation"
  - "calculation"
context_window: 32768
quantization: "AWQ"
vram_estimate_mb: 10240
engine:
  type: "sglang"  # sglang | vllm | ollama | llamacpp | mock
  endpoint_url: "http://127.0.0.1:30000/v1"
  model_name: "Qwen/Qwen2.5-14B-Instruct-AWQ"
  api_key: null
  parameters:
    temperature: 0.2
    top_p: 0.95
    max_tokens: 4096
integrity:
  weights_path: "models/qwen2.5-14b-awq/"
  weights_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
```

### 4.2 Uniform Model Adapter Architecture (`BaseModelAdapter`)

```python
class BaseModelAdapter(ABC):
    """Uniform abstract interface for all local model backends."""
    
    @abstractmethod
    def load(self) -> bool:
        """Loads model into memory or establishes endpoint connection."""
        pass

    @abstractmethod
    def unload(self) -> bool:
        """Unloads model from VRAM/memory."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> ModelResponse:
        """Executes text generation / reasoning."""
        pass

    @abstractmethod
    def generate_chat(self, messages: List[ChatMessage], **kwargs) -> ModelResponse:
        """Executes multi-turn chat completion."""
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generates dense vector embeddings."""
        pass

    @abstractmethod
    def vision_infer(self, image_bytes: bytes, prompt: str, **kwargs) -> ModelResponse:
        """Executes vision-language reasoning over an image."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Checks if the backend is responsive."""
        pass

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Returns True if the model is currently active."""
        pass
```

### 4.3 Task Classification & Auto-Routing

Routing follows a three-stage decision pipeline:
1. **Explicit Override Check:** If `--model <id>` or `model_override` is passed by the caller, bypass classifier and use the specified model directly (FR-MM-6).
2. **Capability Classification:** Classify the user prompt / task payload into required capabilities:
   - `vision_multimodal`: Prompt contains image data, or requests inspection/drawing comparison.
   - `code_generation`: Prompt requests Python, shell script, SQL, or computational code execution.
   - `calculation`: Prompt requests engineering formulas, thermodynamics, mass balances, or stress calculations.
   - `text_drafting`: Prompt requests formal inspection reports, memos, or approval notes.
   - `embedding`: Payload is an array of text snippets for RAG vector indexing.
3. **Model Selection & Scoring:** Match required capabilities against registered models in `ModelRegistry`. If multiple models match, rank by optimal tier (e.g. specialized code model > general model for code tasks).
4. **Audit Logging:** Emit `MODEL_ROUTED` audit event to `AuditLedger` logging session ID, task type, selected model ID, and routing rationale.

### 4.4 VRAM-Aware Scheduling & Dynamic Memory Swapping

```
+-------------------------------------------------------------------------------+
| Total VRAM Budget: 24,576 MB (24GB Reference GPU)                             |
| Safety Headroom Reserve: 2,048 MB (OS, display, CUDA context overhead)       |
| Usable VRAM Budget: 22,528 MB                                                 |
+-------------------------------------------------------------------------------+
  Active Models:
  - Qwen-14B (Reasoning): 10,240 MB  [LOADED]
  - BGE-Large (Embedding): 2,048 MB  [LOADED]
  Total Allocated: 12,288 MB (54.5% utilized) -> Remaining: 10,240 MB

  Incoming Task: Vision Inspection -> Florence-2 / Qwen-VL requires 14,336 MB
  Required (14,336) > Available (10,240) -> VRAM OOM Threat!

  Scheduler Action:
  1. Identify eviction candidate via LRU (Least Recently Used): Qwen-14B (idle).
  2. Evict Qwen-14B: call adapter.unload() -> frees 10,240 MB.
  3. Re-evaluate VRAM: 10,240 + 10,240 = 20,480 MB available.
  4. Load Vision Model: call vision_adapter.load() -> consumes 14,336 MB.
  5. Execute Vision Task -> Return result.
  6. Emit MODEL_SWAPPED event to AuditLedger.
+-------------------------------------------------------------------------------+
```

---

## 5. Potential Hazards, Pitfalls & Countermeasures

### Pitfall 1: VRAM Fragmentation & CUDA Context Leaks
- **Hazard:** Calling `torch.cuda.empty_cache()` or unloading models does not always free all GPU memory if child subprocesses or lingering tensor references remain in memory, leading to silent VRAM creep and eventual OOM.
- **Countermeasure:** Model engines run as separate child processes or HTTP daemons. Terminating or pausing the engine process returns 100% of physical VRAM to the host kernel instantly. `VRAMScheduler` verifies actual GPU free memory using `nvidia-smi` / `pynvml` before confirming a load operation.

### Pitfall 2: Localhost Port Conflicts & Binding Collisions
- **Hazard:** Multiple inference engines attempting to bind to hardcoded port `8000` or `11434`.
- **Countermeasure:** `model_manifest.yaml` allows declaring explicit custom loopback endpoints (`127.0.0.1:30000`, `127.0.0.1:30001`). Adapters verify socket availability before starting subprocesses.

### Pitfall 3: Mock Model Divergence from Real Outputs
- **Hazard:** If the mock adapter produces unrealistic plain strings, downstream agent state machines and deliverable generators fail when tested against real models (e.g. missing JSON keys or wrong types).
- **Countermeasure:** `MockModelAdapter` supports schema-guided generation: when given tool definitions or Pydantic output schemas, it returns syntactically valid JSON conforming to the requested schema.

### Pitfall 4: Concurrent Swapping Race Conditions
- **Hazard:** Two asynchronous tasks concurrently request different unloaded models, causing simultaneous unload/load thrashing.
- **Countermeasure:** `VRAMScheduler` enforces an `asyncio.Lock` / thread mutex across all state transitions (`load`, `unload`, `swap`), ensuring atomic scheduling operations.

---

## 6. Security & ASVS / STRIDE Alignment

### 6.1 Threat Modeling (STRIDE)

- **T-02-01 (Tampering):** Corrupted model weights or backdoored GGUF/binaries are loaded into memory.
  - *Mitigation:* `ModelManifest` contains `weights_sha256`. At load time, the adapter validates the SHA-256 hash against Phase 1's `AttestationGuard`. If mismatched, it refuses to load and writes a security alert to `AuditLedger`.
- **T-02-02 (Denial of Service):** A rogue or unoptimized prompt requests huge `max_tokens` or massive concurrent tasks causing VRAM exhaustion and host server freezing.
  - *Mitigation:* `VRAMScheduler` bounds maximum active allocations. Manifest defines `context_window` ceiling and `max_tokens` cap. Any request exceeding capacity is rejected before scheduling.
- **T-02-03 (Elevation of Privilege):** Subprocess injection via untrusted model paths or malicious engine arguments.
  - *Mitigation:* Manifest file paths are strictly resolved against configured model directories. Executable arguments are passed as explicit token lists, never through shell interpolation (`shell=False`).

---

## 7. Validation & Testing Architecture

### 7.1 Testing Constraints
- 100% offline air-gapped test execution with zero external network connectivity.
- All unit and integration tests must run and pass on CPU-only machines (using `MockModelAdapter` and CPU accounting).
- GPU-dependent tests (if GPU is present) are gated via `@pytest.mark.skipif(not torch.cuda.is_available(), ...)`.

### 7.2 Test Matrix by Plan

| Test File | Target Plan | Requirements Tested | Core Scenarios |
|:---|:---|:---|:---|
| `test_model_manifest.py` | `02-01` | `MODL-01` | Valid YAML manifest parsing, missing fields validation, weights SHA-256 verification. |
| `test_model_registry.py` | `02-01` | `MODL-01` | Registering multiple models, capability filtering, dynamic hot-registration without reboot. |
| `test_mock_adapter.py` | `02-02` | `MODL-04` | Deterministic text, chat, JSON, and embedding responses; simulated latency and simulated VRAM. |
| `test_local_adapters.py` | `02-02` | `MODL-01`, `MODL-04` | Unified HTTP protocol adapter, error handling on engine timeout/refusal. |
| `test_task_router.py` | `02-03` | `MODL-02` | Heuristic classification (text vs code vs vision), model capability matching, manual `--model` override. |
| `test_vram_scheduler.py` | `02-03` | `MODL-03` | VRAM budget tracking, LRU eviction on simulated budget limit, sequential model swapping without OOM. |
| `test_model_cli.py` | `02-01`, `02-03` | `MODL-01`, `MODL-02` | CLI commands: `sovereign model list`, `sovereign model register`, `sovereign model route`. |

---

## 8. Conclusion

Phase 2 establishes a rock-solid, model-agnostic inference layer designed specifically for air-gapped industrial constraints. By abstracting engines behind uniform manifests, implementing deterministic mock adapters for GPU-less environments, and introducing an intelligent VRAM scheduler, the Sovereign AI Workbench can reliably operate multi-model workflows on constrained on-premises hardware.
