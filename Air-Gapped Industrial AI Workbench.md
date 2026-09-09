# **Sovereign AI Architecture: Designing an Air-Gapped, Multimodal, and Agentic Workbench for Industrial Enclaves**

## **Introduction to the Industrial AI Context**

Refineries, public sector undertakings (PSUs), defense-linked manufacturing units, and highly regulated government offices generate an immense volume of routine but exceptionally sensitive knowledge work. The daily operational cadence requires the continuous processing of Piping and Instrumentation Diagrams (P\&IDs), vendor negotiations, board presentations, incident reports, standard operating procedures (SOPs), and complex engineering calculations. Public cloud AI assistants cannot be leveraged for these tasks because the underlying data represents highly confidential corporate strategy, unreleased designs, and critical infrastructure schematics. Company policies strictly enforce on-premises data residency, forcing personnel to either perform routine synthesis manually—sacrificing significant productivity gains—or risk unauthorized exfiltration by pasting proprietary materials into public APIs.  
The maturation of open-weight large reasoning models presents a viable solution to this paradox. It is now computationally feasible to construct an expert-level, self-hosted AI workbench that operates entirely on an organization's internal graphics processing unit (GPU) servers. However, deploying a generic chatbot interface is insufficient for industrial engineering workflows. The requirement is for a true agentic system: a multimodal, multi-model orchestration engine capable of iterating through complex plans, manipulating enterprise file formats, interpreting scanned technical drawings, executing code in isolated sandboxes, and proving its sovereign security posture through verifiable, cryptographic audit trails and real-time zero-egress network telemetry.  
This report comprehensively details the architectural blueprint for designing, deploying, and operating such a system within a strictly air-gapped environment.

## **1\. Air-Gapped Architecture and Logical Isolation**

In enterprise security vernacular, "isolated" and "air-gapped" are frequently conflated, yet they describe fundamentally different network postures. An isolated environment typically utilizes a Network Address Translation (NAT) gateway and an egress allowlist; traffic is controlled but present. A true air-gapped architecture is a stronger, absolute claim: there is no NAT gateway, no external Domain Name System (DNS) resolution, no public certificate authority (CA) chain, and no logical or physical route by which a packet can leave the enclave1.

### **Physical and Logical Network Design**

Operating in this vacuum requires profound infrastructural modifications. Deploying the workbench relies on a two-machine pattern. First, an internet-connected staging server downloads all requisite container images, Helm charts, Python dependencies (via PyPI mirrors), OS packages, and massive model weights into a centralized binary repository, such as JFrog Artifactory2. This mirror is then transferred via physical media or a temporary, heavily monitored localized LAN bridge to the isolated deployment machine. Once transferred, the staging machine is disconnected, and the deployment machine is sealed.  
At the operating system level, Linux networking parameters must be rigidly configured to enforce a default-deny posture. Firewall architectures utilizing iptables or nftables must be applied prior to deploying container runtimes2. Outbound routing (the OUTPUT chain) is explicitly restricted. Rules are inserted to allow stateful established connections, unrestricted loopback (lo) access for inter-process communication, and narrow access to the specific intranet subnet required for administrative Secure Shell (SSH) clients and cluster node communication. All other egress attempts are dropped at the kernel level2.

### **Container Networking and DNS**

Docker and Podman network namespaces must be explicitly configured to prevent bridging to external host interfaces. Containers operate on isolated virtual network bridges. DNS requests from the AI containers must resolve solely to the local enterprise DNS server or the internal Artifactory mirror; external resolution mechanisms (e.g., querying 8.8.8.8) are physically blocked and will time out.

## **2\. Zero-Egress Network Monitoring and Observability**

A sovereign deployment must not merely claim isolation; it must continuously prove it. Industrial compliance mandates a visible monitor demonstrating connection attempts and definitive allow/deny outcomes. Standard packet capture tools like tcpdump and conntrack tables are useful for retrospective forensics, but they lack the real-time, low-overhead process attribution required for a live dashboard.

### **eBPF-Powered Process Attribution**

To achieve zero-trust observability, the architecture leverages extended Berkeley Packet Filter (eBPF) technology, utilizing tools such as Cilium Tetragon3. eBPF allows the insertion of secure, sandboxed observability hooks directly into the Linux kernel without requiring kernel modules or restarts6. Tetragon hooks into critical system calls—specifically execve for process execution and tcp\_connect for network initialization5.  
This deep kernel visibility ensures that every network packet can be definitively attributed to a specific Process ID (PID), container namespace, and executable binary4. If a hallucinating AI agent attempts to execute Python code that queries an external URL, the eBPF monitor intercepts the sys\_enter\_connect syscall. The kernel-level firewall drops the packet, while the eBPF hook instantaneously logs the PID, the originating container (the code sandbox), the destination IP, and the "DENY" outcome. This telemetry is streamed via WebSockets to a dedicated Network Monitor Dashboard on the frontend, providing security auditors with a real-time, incontrovertible visualization of the system's zero-egress integrity3.

## **3\. Security, Supply-Chain Provenance, and Auditing**

The AI workbench operates as a highly privileged orchestrator of corporate knowledge, necessitating a defense-in-depth security paradigm.

### **Cryptographic Security Posture**

At the hardware layer, the deployment environment utilizes a Trusted Platform Module (TPM) and a Hardware Security Module (HSM) to manage encryption keys securely. Secure Boot ensures that the Linux kernel and initialization daemons have not been tampered with. Given the prevalence of supply-chain attacks in the machine learning ecosystem (e.g., malicious payload injection inside serialized model weights), signed binaries and strict model checksum verification are mandatory1. Models downloaded in the connected phase undergo SHA-256 checksum validation against published manifests before being cleared for transfer to the air-gapped registry. Furthermore, a comprehensive Software Bill of Materials (SBOM) and continuous offline dependency scanning evaluate the containerized environment for known Common Vulnerabilities and Exposures (CVEs).  
Data encryption at rest is enforced via LUKS (Linux Unified Key Setup) for all Non-Volatile Memory Express (NVMe) drives storing vector databases and model weights. File permissions follow the principle of least privilege; the AI agent process runs as a non-root user with read-only access to the model binaries and strict access control list (ACL) restrictions on temporary storage directories.

### **Event Sourcing and the Immutable Audit Trail**

Every interaction within the workbench—model selection, tool invocation, document retrieval, and code execution—must be traceable. The backend architecture replaces standard text logging with an event sourcing model. Every state change is recorded in an append-only PostgreSQL ledger as a structured JSON event8.  
To prevent tampering by malicious internal actors or compromised processes, these logs utilize cryptographic hash chaining. Each log entry calculates a hash that includes the SHA-256 hash of the immediate preceding entry, the user's authentication token, the exact prompt, the specific model weights checksum, the IDs of the retrieved RAG documents, and the output generated9. If an audit log entry is altered retroactively, the cryptographic chain breaks, immediately triggering an integrity alert. This system provides absolute artifact lineage; an auditor can take an AI-generated approval note and trace its exact provenance back to the specific scanned inspection report and the specific vision model used to process it.

## **4\. Hardware, Deployment, and Performance Architecture**

Operating 120-billion parameter models requires specialized infrastructure and meticulous deployment scripting.

### **GPU Orchestration and Hardware Requirements**

The host operating system is an Ubuntu Long Term Support (LTS) release, stripped of unnecessary daemons. The NVIDIA driver stack and Compute Unified Device Architecture (CUDA) toolkit are configured to allow GPU passthrough into the containerized services via the NVIDIA Container Toolkit10.  
Memory bandwidth and Video Random Access Memory (VRAM) capacity dictate performance. A 7B parameter model requires approximately a single 24GB GPU (e.g., RTX 4090 or L4), whereas a 70B-120B model requires 2 to 4 high-end GPUs (e.g., 80GB A100s or 96GB RTX 6000 Ada generations) operating with tensor parallelism across NVLink interconnects10. Because PCIe bandwidth severely bottlenecks model swapping, the system requires enterprise-grade NVMe solid-state storage arrays to load multi-gigabyte weight files into VRAM efficiently11.

### **Performance Benchmarking and Evaluation**

Continuous system evaluation is vital to ensure operational fluidity. The architecture incorporates automated benchmarking suites to monitor key performance indicators (KPIs) in real-time13.

> 1. **Time-to-First-Token (TTFT):** Measures the latency from the receipt of the prompt to the generation of the first token. This is heavily influenced by the prefill phase of the inference engine.  
> 2. **Tokens per Second (TPS):** Measures the decoding throughput of the model13.  
> 3. **VRAM and GPU Utilization:** Tracked via NVIDIA System Management Interface (nvidia-smi) and exposed through Prometheus metrics.

Systemic efficacy is evaluated through automated testing frameworks. OCR accuracy is benchmarked against ground-truth industrial datasets. RAG retrieval is evaluated using Mean Reciprocal Rank (MRR) and Normalized Discounted Cumulative Gain (NDCG). Crucially, agent success rates, code execution success rates, and the efficacy of the agent's self-correction loops are measured by feeding the system complex, multi-step engineering prompts and validating the generated artifacts.

## **5\. Core AI Foundation: Local LLMs and Quantization**

The sovereign workbench rejects reliance on a single monolithic architecture, instead adopting an ensemble of specialized open-weight models under permissive licenses.

### **Open-Weight Models for Industrial Use**

The Qwen3 family (Apache 2.0) serves as the backbone of the system. Qwen3 has demonstrated exceptional general reasoning, multilingual support, and coding proficiency14. The architecture dynamically selects from its sizing tiers: the 8B and 14B models are utilized for rapid classification, simple tool orchestration, and conversational summarization14. The 30B variant is invoked for complex RAG synthesis and code generation, while the massive 235B Mixture-of-Experts (MoE) variant is reserved for tasks demanding the highest levels of logical deduction, assuming the underlying multi-GPU infrastructure is available14.  
Alternatively, gpt-oss-20b and gpt-oss-120b (Apache 2.0) are utilized when deeply reasoned, frontier-class capabilities are required for analyzing complex engineering calculations or drafting high-stakes legal vendor correspondence14.

### **Quantization and Precision Engineering**

Loading models in pure FP16 (16-bit floating point) places immense strain on VRAM. A 70B model in FP16 consumes approximately 140GB of VRAM just for the weights11. To mitigate this, the deployment pipeline incorporates aggressive quantization techniques.

| Quantization Method | Mechanism and Advantages | Optimal Use Case |
| :---- | :---- | :---- |
| **GGUF** | Optimized for CPU and edge inference. Utilizes 4-bit to 8-bit integer quantization (INT4/INT8)7. | Single workstation deployments without high-end GPU arrays7. |
| **AWQ / GPTQ** | Activation-aware Weight Quantization and Generative Pre-trained Transformer Quantization. Maps weights to INT4/INT8 while retaining crucial activation outliers, maintaining high accuracy7. | Primary deployment on consumer or mid-range enterprise GPUs (e.g., RTX 6000\)10. |
| **FP8** | Native 8-bit floating-point precision supported natively by modern hardware architectures (Hopper, Blackwell). Halves memory usage while increasing throughput up to 1.6x with virtually zero quality loss10. | High-end datacenter deployments (H100, L40S)11. |

Furthermore, memory must be allocated for the Key-Value (KV) cache, which stores the internal state of the attention mechanism for previously processed tokens. The KV cache grows linearly with the context window size and batch size. By quantizing the KV cache itself to FP8, the system significantly expands the maximum concurrent context window, enabling the agent to ingest massive log files and multi-hundred-page manuals without encountering Out-Of-Memory (OOM) errors10.

## **6\. Inference Engines and Serving Architecture**

The efficiency of the AI workbench is entirely dependent on the underlying inference engine. The system integrates multiple backend technologies to support diverse workloads.

### **Comparison of Local Inference Engines**

| Engine | Architectural Advantages | Limitations | Target Workload |
| :---- | :---- | :---- | :---- |
| **vLLM** | Utilizes PagedAttention, managing the KV cache similarly to an OS managing virtual memory (in non-contiguous blocks). Prevents internal memory fragmentation and supports continuous batching for extreme throughput7. | Pre-allocates roughly 90% of GPU VRAM at startup, complicating multi-model sharing on a single GPU7. | High-concurrency enterprise endpoints with dedicated GPU assignments7. |
| **SGLang** | Employs RadixAttention to cache and reuse common prefixes (system prompts, tool schemas) across requests. Highly optimized for Vision-Language Models (VLMs) and structured JSON generation7. | Higher setup complexity and tighter hardware coupling7. | Agentic loops, iterative human-in-the-loop workflows, and RAG architectures7. |
| **llama.cpp / Ollama** | Highly portable, supports CPU/GPU hybrid execution via GGUF files. Extremely simple to script and deploy7. | Allocates KV cache contiguously per request; severely bottlenecks under concurrent load, resulting in request serialization7. | Edge computing or single-user, low-concurrency testing environments7. |
| **Triton Server** | Enterprise-grade multi-backend orchestration. Supports Python backends, TensorRT, and acts as a wrapper for vLLM16. | Significant operational overhead; designed for multi-node datacenter topologies10. | Massive organizational grids requiring dynamic model lifecycle management. |

For this sovereign workbench, **SGLang** is selected as the primary engine for the core agentic reasoning models. Agent loops iteratively query the model with the exact same system prompt and evolving conversation history. SGLang's RadixAttention algorithm recognizes this overlapping prefix, caches the computation tree, and prevents the recomputation of identical tokens. This drastically reduces the TTFT on iterative tool-calling loops7. **vLLM** is deployed alongside it to handle high-throughput embedding generation and parallel document summarization requests11.

## **7\. The VRAM-Aware Model Router**

The system's backend requires a highly intelligent Model Router to orchestrate the flow of requests across multiple loaded and unloaded models dynamically.

### **Capability and Context-Based Routing**

Routing is primarily capability-based. Incoming tasks are classified via a lightweight, rule-based heuristic or a highly efficient 8B model. If the task involves code generation, the router dynamically selects Qwen3-30B. If the request is a simple semantic search, it routes to a specialized embedding model.  
Routing also relies on a centralized Model Registry containing rigid Model Manifests. These manifests define the model's architecture, its quantization level, its maximum context window, and its minimum VRAM requirement18.

### **Dynamic Model Swapping**

On constrained hardware (e.g., a single workstation with 96GB VRAM), it is impossible to hold a 70B reasoning model, an 11B vision model, and an embedding model in active VRAM simultaneously10. The router utilizes dynamic model swapping architectures, such as Sardeenz, to virtualize GPU memory management13.  
When a vision task arrives, the router evaluates real-time VRAM availability. If insufficient, it commands vLLM or SGLang to place the currently active reasoning model into a "sleep mode." This mechanism rapidly offloads the model's tensor weights from the GPU into the host machine's system RAM, freeing up to 90% of the GPU footprint13. The vision model is loaded from NVMe storage, executes the task, and is subsequently unloaded, allowing the reasoning model to quickly wake back into VRAM from system memory. This VRAM-aware orchestration allows a single mid-range server to simulate the capabilities of a massive computing cluster13.

## **8\. Multimodal AI: OCR and Document Understanding**

Industrial workflows rely heavily on unstructured, complex visual data. P\&IDs, handwritten inspection sheets, and legacy scanned manuals must be rendered fully comprehensible to the agent.

### **Document Parsing and OCR Pipelines**

The ingestion of PDFs requires sophisticated layout analysis. The system eschews simple PyPDF extractors in favor of advanced visual layout detection pipelines.

| Parsing Technology | Core Architecture and Strengths | Trade-offs | Role in Workbench |
| :---- | :---- | :---- | :---- |
| **Docling (IBM)** | Employs deep learning (TableFormer) for precise layout analysis. Preserves multi-column reading order, detects complex tables, and outputs lossless structural JSON/Markdown with bounding box metadata20. | Slower processing speed (approx. 3.2 pages/sec); higher computational overhead21. | Primary ingestion layer for highly structured SOPs, engineering calculations, and tabular data21. |
| **Marker** | Utilizes a pipeline of specialized models (Surya suite) optimized for blistering speed and GPU acceleration. Excels at generating clean Markdown from standard text-heavy documents20. | Loses nuanced document hierarchy; struggles with highly complex tables containing merged cells20. | Rapid bulk ingestion of legacy text archives and standard manuals20. |
| **MinerU** | Leverages a compact vision-language model architecture specifically tuned for dense formulas, academic formatting, and complex tables22. | Requires dedicated GPU resources for optimal performance22. | Specialized processing for advanced scientific calculations and research papers22. |

When a user uploads a document, the system evaluates its structure. Clean, born-digital PDFs are routed to Marker for rapid processing. Complex, multi-column engineering documents with dense tables route to Docling to ensure the layout hierarchy is flawlessly preserved20. If the document is a poor-quality scanned PDF or contains handwriting, the system falls back to robust Optical Character Recognition (OCR) engines like Tesseract, evaluating OCR confidence scores. If confidence drops below a specified threshold, the system flags the document for human review via the HITL interface.

### **Vision-Language Models for Engineering Schematics**

To process images, the workbench deploys local Vision-Language Models (VLMs) such as Florence-2 and Qwen2.5-VL23.  
When an engineer uploads a P\&ID or an equipment photograph, Florence-2 is utilized for granular region detection. It excels at identifying the exact pixel coordinates of valves, text annotations, and piping junctions, generating precise bounding boxes24. These isolated regions and metadata are then passed to Qwen2.5-VL, which possesses the deep reasoning capability to interpret the schematic. The agent can successfully answer complex queries, such as tracing the flow path from a specific pump to a designated storage tank, identifying potential points of failure, or generating an annotated image overlaying analytical highlights directly onto the original drawing.

## **9\. Retrieval-Augmented Generation (RAG) Architecture**

To prevent hallucinations and ground the agent in the specific realities of the industrial facility, the architecture incorporates an advanced offline RAG pipeline.

### **Chunking and Embedding**

Following structural ingestion via Docling, the text is subjected to semantic chunking. Rather than splitting by an arbitrary token count, the system leverages Docling's hierarchical metadata to keep logical units intact—ensuring that a complex pump maintenance table is not severed halfway through its rows20.  
These chunks are embedded using local models such as bge-small or nomic-embed1. These embeddings are generated entirely on-premises, preserving the confidentiality of the proprietary manuals.

### **Vector Database Evaluation and Selection**

The vector database serves as the long-term memory of the enterprise.

| Vector Database | Architecture and Key Features | Operational Limitations |
| :---- | :---- | :---- |
| **Qdrant** | Rust-based engine engineered for large-scale filtered search. Executes metadata filtering natively within the HNSW graph traversal for extreme efficiency25. | Introduces an external infrastructural service requirement26. |
| **pgvector** | Native PostgreSQL extension. Consolidates vectors and relational metadata into a single ACID-compliant transactional database25. | Indexing and vacuuming performance degrades significantly beyond 2-5 million vectors26. |
| **Chroma** | Lightweight, highly embeddable database optimized for rapid local prototyping27. | Scaling limitations in heavy, multi-tenant enterprise production28. |
| **FAISS** | Open-source C++ library by Meta. Blisteringly fast dense vector similarity search, optimized for RAM and GPU execution27. | Operates as a library rather than a fully managed database system27. |

The workbench utilizes **Qdrant** as the primary vector store. Industrial data access is strictly governed by RBAC. When an agent queries the vector store, Qdrant applies hard metadata filters (e.g., clearance\_level \<= user\_level and document\_type \= incident\_report) dynamically during the vector search, ensuring access-controlled retrieval25.  
Qdrant is configured for hybrid search, combining dense vector embeddings (for semantic intent) with sparse BM25 indexing (for exact keyword matching of specific part numbers or serial codes)28. The retrieved candidate chunks are then passed through a local reranking model (e.g., bge-reranker), which cross-encodes the query and the documents to maximize contextual relevance before insertion into the LLM's context window. The agent is strictly prompted to utilize the source metadata to generate accurate inline citations in its final outputs, ensuring unbroken source attribution.

## **10\. The Agent System and Human-in-the-Loop Orchestration**

The defining characteristic of this workbench is its agentic architecture. Unlike a chatbot that merely responds to a prompt, an AI agent operates on the ReAct (Reasoning and Acting) paradigm. It analyzes a goal, decomposes the task into sequential steps, selects appropriate tools, observes the results of its actions, and iteratively re-plans until the objective is achieved.

### **LangGraph and the State Machine**

To orchestrate this complexity, the backend utilizes LangGraph. LangGraph structures the agent as a cyclical state machine. Nodes represent executable Python functions (e.g., the LLM reasoning step, or the execution of a specific tool), and edges represent conditional routing logic based on the LLM's output30.  
A centralized TypedDict maintains the agent state, accumulating the session memory, intermediate tool observations, and the conversation history8. LangGraph necessitates a persistence layer, known as a checkpointer (e.g., PostgresSaver). At every node transition, the entire state dictionary is serialized and saved to the database under a unique thread\_id8.  
This persistence enables advanced agent loops:

> 1. **Bounded Retries and Self-Correction:** If the agent generates a Python script that throws a syntax error, the tool node appends the error trace to the state. The graph loops back to the LLM node, allowing the agent to read the error, self-correct the code, and retry. The system enforces strict loop limits (e.g., maximum 5 iterations) to prevent infinite computational loops.  
> 2. **Agent Failure Handling:** If the agent exhausts its retries or fails to locate relevant data, the graph routes to a fallback node, gracefully pausing execution and requesting human clarification.

### **The interrupt() Paradigm for Human Verification**

In high-stakes industrial environments, autonomous action is prohibited for critical tasks. The system utilizes LangGraph's native Human-in-the-Loop (HITL) capabilities to enforce mandatory human approval processes.  
When the state machine reaches a critical node (e.g., immediately before executing a generated SQL query or finalizing a legal approval note), the code executes the interrupt(payload) function30. This command instantly suspends graph execution. The PostgresSaver freezes the entire multi-turn state, and the payload (e.g., the draft document or proposed command) is surfaced to the FastAPI backend without consuming any background compute threads30.  
The Next.js frontend displays this payload in the Approval Workflow dashboard. An engineer reviews the proposed action. Once the engineer clicks "Approve" (or edits the payload), the frontend sends an API request containing a Command(resume=value) object, specifying the unique thread\_id8. LangGraph retrieves the exact frozen state, injects the user's decision as the return value of the original interrupt() call, and resumes the graph traversal natively30. This fundamentally replicates the human-centric approval chains required in PSUs and refineries.

## **11\. Tool Orchestration and Document Generation**

An agent is only as capable as its toolset. Providing the LLM with unrestricted access to the host server's filesystem or network is a catastrophic security vulnerability.

### **Explicit Tool Schemas and the Registry**

The workbench employs a rigid Tool Registry. Every tool—whether a File-Read tool, a Document-Search tool, a Calculator, or a Spreadsheet automation tool—is defined by a strict JSON Schema detailing its required arguments, types, and expected return formats.  
During SGLang's prefix-caching prefill stage, these schemas are injected into the context window7. The agent does not execute code directly; it generates a structured JSON object requesting a tool call. The backend parses this JSON, validates it against the schema, enforces Tool Permissions (ensuring the user has RBAC clearance for that specific tool), and then securely executes the underlying Python function, returning the result to the agent state.

### **Generating Native Deliverables**

Outputs in industrial settings are rarely plain text. The workbench is equipped with specialized tools to generate native Microsoft Office deliverables programmatically.

* **Word (DOCX):** Utilizing python-docx, the agent injects extracted data, citations, and summaries into pre-approved, styled corporate Word templates, dynamically generating tables and managing header/footer logic33.  
* **Excel (XLSX):** Utilizing openpyxl, the system can output complex engineering calculations. It populates cells, injects mathematical formulas, establishes cell references, and automatically generates visualization charts33. Crucially, outputting raw formulas rather than just the final number allows human engineers to audit the calculation traces manually.  
* **PowerPoint (PPTX):** Utilizing python-pptx, the agent can summarize inspection reports into slide decks, placing text and charts into defined layout placeholders to match corporate branding33.

## **12\. The Secure Code Sandbox**

When the agent requires dynamic logic to process unique CSV formats or execute fluid engineering mathematics, it must write and execute custom Python scripts. To prevent sandbox escapes and host compromise, this execution environment is severely restricted.  
Standard Docker containers share the host kernel and are insufficient for untrusted multi-tenant code execution. The workbench implements a multi-layered, deeply isolated code sandbox.

> 1. **Network Namespaces and Zero-Egress:** The sandbox is instantiated within a completely isolated network namespace. No virtual ethernet (veth) interface is attached to the host bridge. The container contains only a loopback interface (lo). Generated code is physically incapable of initiating outbound network connections, blocking data exfiltration or external payload downloads2.  
> 2. **Resource Bounding:** Control groups (cgroups v2) enforce rigid limitations on CPU utilization and establish hard memory limits. If the agent generates an inefficient loop that causes a memory spike, the cgroup OOM-killer terminates the process instantly, preventing host degradation. Execution timeouts are strictly enforced (e.g., maximum 15 seconds runtime).  
> 3. **Filesystem Isolation:** The root filesystem is mounted entirely read-only. A highly restricted, ephemeral /tmp directory is mounted using tmpfs to capture specific outputs (e.g., a generated graph).  
> 4. **Capability Dropping and Seccomp:** The container drops all Linux root capabilities (--cap-drop=ALL). A strict Secure Computing (seccomp) profile is applied, blocking access to unnecessary kernel system calls, dramatically reducing the attack surface.  
> 5. **MicroVM Architecture:** For the absolute highest security clearance, the architecture can substitute containers for microVMs (e.g., Firecracker) or user-space kernels (e.g., gVisor), guaranteeing that even a kernel-level exploit generated by the LLM cannot compromise the underlying bare-metal GPU server.

## **13\. Backend Architecture and Frontend Visualization**

The connective tissue of the workbench is built for high concurrency and transparent observability.

### **Backend Orchestration**

The backend is developed utilizing asynchronous Python and the FastAPI framework. FastAPI exposes REST APIs for file uploads, model registry management, and session initialization. Because agentic operations are long-running and iterative, standard HTTP polling is inefficient.  
Instead, the backend utilizes bidirectional WebSockets34. As LangGraph executes a task, it emits streaming events at every node transition. The FastAPI backend captures these traces and pushes them over the WebSocket connection to the client36. Background jobs and task queues (managed via Redis and Celery or RQ) handle heavy asynchronous processing, such as batch document ingestion and vectorization, while SQLite or PostgreSQL manages persistent session states. The local service architecture is managed natively via systemd or orchestrated entirely through Docker Compose depending on the enclave's deployment standards.

### **Next.js Frontend and the Workbench UI**

The user interface is built using React and Next.js. It rejects the simplistic design of consumer chatbots, opting instead for a professional, multi-pane workbench layout.

* **Agent Execution Trace:** A live, streaming log visualizes the agent's thought process via the WebSocket feed, showing precisely which tool is being called and the raw output being evaluated34.  
* **Document Preview:** A dedicated pane allows users to view uploaded schematics or PDFs, visualizing the exact bounding boxes and tables the vision models have identified.  
* **Approval Workflow:** A dashboard lists all paused state-machine threads awaiting HITL verification, allowing engineers to batch-review proposed deliverables.  
* **Administrative Dashboards:** Authorized users can access real-time visualizations of model selection, VRAM utilization, and the eBPF network monitor dashboard, providing continuous visual proof of the system's air-gapped integrity.

## **14\. Conclusion**

The Sovereign AI Workbench fundamentally redefines the integration of artificial intelligence within highly regulated industrial sectors. By enforcing a rigid, air-gapped network perimeter monitored continuously via kernel-level eBPF telemetry, the system definitively guarantees the security of confidential intellectual property. The architectural synergy of VRAM-aware model routing, specialized multimodal ingestion pipelines, and deeply isolated code sandboxes enables the deployment of highly capable open-weight models on constrained localized hardware.  
Crucially, by grounding operations in a hybrid-search RAG pipeline and orchestrating tasks through the verifiable, human-in-the-loop state machine of LangGraph, the workbench transcends the limitations of generative chatbots. It emerges as a deterministic, auditable, and autonomous engineering assistant, capable of navigating the complex, multi-step workflows essential to the operations of modern refineries, public sector undertakings, and defense manufacturing facilities.

#### **Works cited**

> 1. Air-Gapped AI: Deploying LLMs in Defense & Regulated Finance, [https://www.truefoundry.com/blog/air-gapped-ai-deploying-enterprise-llms-in-highly-regulated-industries](https://www.truefoundry.com/blog/air-gapped-ai-deploying-enterprise-llms-in-highly-regulated-industries)  
> 2. Deploying Enterprise Inference in an Air-Gapped Datacenter, [https://infohub.delltechnologies.com/en-us/l/deploying-enterprise-inference-in-an-air-gapped-datacenter/deploying-enterprise-inference-in-an-air-gapped-datacenter/](https://infohub.delltechnologies.com/en-us/l/deploying-enterprise-inference-in-an-air-gapped-datacenter/deploying-enterprise-inference-in-an-air-gapped-datacenter/)  
> 3. Cilium Tetragon: eBPF-Powered Runtime Security for Kubernetes, [https://kubezilla.io/cilium-tetragon-ebpf-powered-runtime-security-for-kubernetes-and-docker/](https://kubezilla.io/cilium-tetragon-ebpf-powered-runtime-security-for-kubernetes-and-docker/)  
> 4. Kubernetes Runtime Security : The Guide \- Cilium, [https://cilium.io/blog/2026/06/07/kubernetes-runtime-security-the-guide/](https://cilium.io/blog/2026/06/07/kubernetes-runtime-security-the-guide/)  
> 5. Engineering Everything with eBPF \- Hamza Megahed, [https://ebpf.hamza-megahed.com/pdf/Engineering\_Everything\_with\_eBPF.pdf](https://ebpf.hamza-megahed.com/pdf/Engineering_Everything_with_eBPF.pdf)  
> 6. eBPF- The Linux Superpower That Shows What Your Dashboards, [https://dev.to/vladlevinas/ebpf-the-linux-superpower-that-shows-what-your-dashboards-miss-33na](https://dev.to/vladlevinas/ebpf-the-linux-superpower-that-shows-what-your-dashboards-miss-33na)  
> 7. 2026 Local Inference Engines: Key Decision \- Sesame Disk, [https://sesamedisk.com/llamacpp-vs-vllm-vs-sglang-vs-ollama-2026/](https://sesamedisk.com/llamacpp-vs-vllm-vs-sglang-vs-ollama-2026/)  
> 8. langgraph-human-in-the-loop | Claude Skills & Agent Skills Library, [https://mcpservers.org/agent-skills/langchain-ai/skills-benchmarks/langgraph-human-in-the-loop-2](https://mcpservers.org/agent-skills/langchain-ai/skills-benchmarks/langgraph-human-in-the-loop-2)  
> 9. Inside vLLM: Anatomy of a High-Throughput LLM Inference System, [https://vllm.ai/blog/2025-09-05-anatomy-of-vllm](https://vllm.ai/blog/2025-09-05-anatomy-of-vllm)  
> 10. \[Architectural Review\] RAG Blueprint for Air-Gapped Enterprise, [https://forums.developer.nvidia.com/t/architectural-review-rag-blueprint-for-air-gapped-enterprise-environment-on-rtx-6000-blackwell/357435](https://forums.developer.nvidia.com/t/architectural-review-rag-blueprint-for-air-gapped-enterprise-environment-on-rtx-6000-blackwell/357435)  
> 11. How I Get the Best Out of My GPU Using vLLM for Local LLM, [https://sammainah.com/blog/posts/vllm-gpu-inference-engine](https://sammainah.com/blog/posts/vllm-gpu-inference-engine)  
> 12. On-Prem LLM Deployment (2026): GPU Sizing, vLLM & Air-Gapped, [https://iternal.ai/how-to-deploy-llm-on-premise](https://iternal.ai/how-to-deploy-llm-on-premise)  
> 13. Running LLMs dynamically, in production, on limited resources, is, [https://www.redhat.com/en/blog/running-llms-dynamically-production-limited-resources-hard-we-think-theres-room-another-approach](https://www.redhat.com/en/blog/running-llms-dynamically-production-limited-resources-hard-we-think-theres-room-another-approach)  
> 14. The Best Open Source and Open-Weight LLM Models to Run, [https://huggingface.co/blog/daya-shankar/open-source-llm-models-to-run-locally](https://huggingface.co/blog/daya-shankar/open-source-llm-models-to-run-locally)  
> 15. Top 5 Local LLM Tools and Models in 2026 | Pinggy Blog, [https://pinggy.io/blog/top\_5\_local\_llm\_tools\_and\_models/](https://pinggy.io/blog/top_5_local_llm_tools_and_models/)  
> 16. NVIDIA Triton \- vLLM docs, [https://docs.vllm.ai/en/stable/deployment/frameworks/triton/](https://docs.vllm.ai/en/stable/deployment/frameworks/triton/)  
> 17. In-House LLM Serving at Netflix \- Netflix TechBlog, [https://netflixtechblog.com/in-house-llm-serving-at-netflix-a5a8e799ea2c](https://netflixtechblog.com/in-house-llm-serving-at-netflix-a5a8e799ea2c)  
> 18. vLLM vs SGLang vs TensorRT-LLM: Production Inference Engine, [https://neuralchainai.com/blog/vllm-vs-sglang-vs-tensorrt-llm-inference-engine-guide/](https://neuralchainai.com/blog/vllm-vs-sglang-vs-tensorrt-llm-inference-engine-guide/)  
> 19. Air-Gap Deployment — NVIDIA NIM for Large Language Models, [https://docs.nvidia.com/nim/large-language-models/latest/deploy-air-gap.html](https://docs.nvidia.com/nim/large-language-models/latest/deploy-air-gap.html)  
> 20. Docling vs Marker: Which Document Parser Works Better for RAG, [https://docs.bswen.com/blog/2026-04-16-docling-vs-marker-document-parsing/](https://docs.bswen.com/blog/2026-04-16-docling-vs-marker-document-parsing/)  
> 21. Docling vs Unstructured: PDF Accuracy Benchmark \- Ertas AI, [https://www.ertas.ai/blog/pdf-parsing-accuracy-benchmark-docling-unstructured](https://www.ertas.ai/blog/pdf-parsing-accuracy-benchmark-docling-unstructured)  
> 22. Docling vs Marker vs MinerU: The Ultimate Open-Source PDF, [https://adityamangal98.medium.com/docling-vs-marker-vs-mineru-the-ultimate-open-source-pdf-parser-benchmark-2026-which-is-best-a36ecbb6c6b1](https://adityamangal98.medium.com/docling-vs-marker-vs-mineru-the-ultimate-open-source-pdf-parser-benchmark-2026-which-is-best-a36ecbb6c6b1)  
> 23. Cosmos 3: Omnimodal World Models for Physical AI, [https://research.nvidia.com/labs/cosmos-lab/cosmos3/technical-report.pdf](https://research.nvidia.com/labs/cosmos-lab/cosmos3/technical-report.pdf)  
> 24. diagram-symbol-ai-research/docs/research-report.md at master, [https://github.com/EvanBatten/diagram-symbol-ai-research/blob/master/docs/research-report.md](https://github.com/EvanBatten/diagram-symbol-ai-research/blob/master/docs/research-report.md)  
> 25. Best Vector Databases in 2026: A Complete Comparison Guide, [https://www.firecrawl.dev/blog/best-vector-databases](https://www.firecrawl.dev/blog/best-vector-databases)  
> 26. pgvector vs Pinecone vs Qdrant vs Weaviate (2026) \- Kalvium Labs, [https://www.kalviumlabs.ai/blog/vector-databases-compared-pgvector-pinecone-qdrant-weaviate/](https://www.kalviumlabs.ai/blog/vector-databases-compared-pgvector-pinecone-qdrant-weaviate/)  
> 27. Best Vector Databases 2026: Pinecone, Chroma, Qdrant & More, [https://www.datacamp.com/blog/the-top-5-vector-databases](https://www.datacamp.com/blog/the-top-5-vector-databases)  
> 28. Best open source vector database software: Top 10 in 2026, [https://www.instaclustr.com/education/vector-database/best-open-source-vector-database-software-top-8-in-2026/](https://www.instaclustr.com/education/vector-database/best-open-source-vector-database-software-top-8-in-2026/)  
> 29. Top 5 Open Source Vector Databases for 2025 (Milvus vs. Qdrant, [https://medium.com/@fendylike/top-5-open-source-vector-search-engines-a-comprehensive-comparison-guide-for-2025-e10110b47aa3](https://medium.com/@fendylike/top-5-open-source-vector-search-engines-a-comprehensive-comparison-guide-for-2025-e10110b47aa3)  
> 30. LangGraph Human-in-the-Loop: Pausing, Reviewing ... \- Towards AI, [https://pub.towardsai.net/langgraph-human-in-the-loop-pausing-reviewing-and-rewinding-your-agent-4028bd05b049](https://pub.towardsai.net/langgraph-human-in-the-loop-pausing-reviewing-and-rewinding-your-agent-4028bd05b049)  
> 31. LangGraph Basics: Part 6 — Subgraphs & Human-in-the-Loop, [https://shafiqulai.github.io/blogs/blog\_13.html](https://shafiqulai.github.io/blogs/blog_13.html)  
> 32. Interrupts and Commands in LangGraph: Building Human-in-the, [https://dev.to/jamesbmour/interrupts-and-commands-in-langgraph-building-human-in-the-loop-workflows-4ngl](https://dev.to/jamesbmour/interrupts-and-commands-in-langgraph-building-human-in-the-loop-workflows-4ngl)  
> 33. Python DocX Charts \- Botched Deployments, [https://botched-deployments.com/posts/python-docx-charts](https://botched-deployments.com/posts/python-docx-charts)  
> 34. WebSocket with FastAPI: Async Connections & Scaling, [https://websocket.org/guides/frameworks/fastapi/](https://websocket.org/guides/frameworks/fastapi/)  
> 35. WebSockets \- FastAPI, [https://fastapi.tiangolo.com/advanced/websockets/](https://fastapi.tiangolo.com/advanced/websockets/)  
> 36. How to maintain the same Trace for Fast API and LangGraph, [https://github.com/langfuse/langfuse/issues/7838](https://github.com/langfuse/langfuse/issues/7838)