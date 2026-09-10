"""
src/sovereign/models/scheduler.py
VRAM-aware model scheduler managing memory budgets, LRU eviction, and OOM avoidance.
"""
import logging
import threading
import time
from typing import Dict, List, Optional

from sovereign.audit.ledger import AuditLedger
from sovereign.models.adapter import BaseModelAdapter
from sovereign.models.registry import ModelRegistry

logger = logging.getLogger("sovereign.models.scheduler")


class VRAMExceededError(Exception):
    """Raised when requested model requirements exceed available or total VRAM budget."""
    pass


class VRAMScheduler:
    """
    Tracks and enforces GPU memory budgets on reference hardware (e.g. 24GB VRAM).
    Dynamically swaps models via LRU eviction to prevent CUDA Out-Of-Memory crashes.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        total_vram_mb: int = 24576,       # 24GB reference GPU
        reserve_headroom_mb: int = 2048,  # 2GB safety reserve for OS/CUDA context
        audit_ledger: Optional[AuditLedger] = None,
    ):
        self.registry = registry
        self.total_vram_mb = total_vram_mb
        self.reserve_headroom_mb = reserve_headroom_mb
        self.usable_vram_mb = max(0, total_vram_mb - reserve_headroom_mb)
        self.audit_ledger = audit_ledger
        self._lock = threading.Lock()

        # Map of model_id -> last_used_timestamp (float)
        self._loaded_models: Dict[str, float] = {}

    @property
    def current_allocated_mb(self) -> int:
        """Total estimated VRAM consumed by currently loaded models."""
        total = 0
        for model_id in self._loaded_models:
            manifest = self.registry.get_manifest(model_id)
            if manifest:
                total += manifest.vram_estimate_mb
        return total

    @property
    def available_vram_mb(self) -> int:
        """Remaining usable VRAM headroom before eviction is triggered."""
        return max(0, self.usable_vram_mb - self.current_allocated_mb)

    def is_loaded(self, model_id: str) -> bool:
        """Returns True if the model is currently active in memory."""
        return model_id in self._loaded_models

    def list_loaded_models(self) -> List[str]:
        """Returns list of all currently loaded model IDs."""
        with self._lock:
            return list(self._loaded_models.keys())

    def ensure_loaded(
        self,
        model_id: str,
        session_id: Optional[str] = None
    ) -> BaseModelAdapter:
        """
        Ensures the specified model is loaded in memory.
        If necessary, evicts inactive models in Least-Recently-Used (LRU) order
        until sufficient VRAM is available.
        """
        with self._lock:
            manifest = self.registry.get_manifest(model_id)
            if not manifest:
                raise KeyError(f"Model '{model_id}' is not registered in the catalog.")

            now = time.time()
            adapter = self.registry.get_adapter(model_id)

            # 1. If already loaded, update timestamp and return
            if model_id in self._loaded_models:
                self._loaded_models[model_id] = now
                if not adapter.is_loaded:
                    adapter.load()
                return adapter

            needed_mb = manifest.vram_estimate_mb
            # 2. Hard budget check: single model exceeds total usable envelope
            if needed_mb > self.usable_vram_mb:
                raise VRAMExceededError(
                    f"Model '{model_id}' requires {needed_mb}MB VRAM, which exceeds "
                    f"the total usable VRAM budget of {self.usable_vram_mb}MB "
                    f"(Total: {self.total_vram_mb}MB, Reserve: {self.reserve_headroom_mb}MB)."
                )

            # 3. Dynamic LRU eviction if headroom is insufficient
            evicted: List[str] = []
            while self.available_vram_mb < needed_mb and self._loaded_models:
                # Find oldest model by last-used timestamp
                oldest_model_id = min(self._loaded_models, key=self._loaded_models.get)
                evicted_adapter = self.registry.get_adapter(oldest_model_id)
                evicted_adapter.unload()
                del self._loaded_models[oldest_model_id]
                evicted.append(oldest_model_id)

                logger.info(f"VRAMScheduler: Evicted '{oldest_model_id}' to free VRAM.")

                if self.audit_ledger:
                    try:
                        self.audit_ledger.append_event(
                            session_id=session_id or "vram-scheduler",
                            event_type="MODEL_UNLOADED",
                            actor_role="vram-scheduler",
                            payload={
                                "unloaded_model_id": oldest_model_id,
                                "reason": f"Evicted to free VRAM for '{model_id}'",
                                "current_allocated_mb": self.current_allocated_mb,
                            }
                        )
                    except Exception as e:
                        logger.error(f"Audit log error during model eviction: {e}")

            if evicted and self.audit_ledger:
                try:
                    self.audit_ledger.append_event(
                        session_id=session_id or "vram-scheduler",
                        event_type="MODEL_SWAPPED",
                        actor_role="vram-scheduler",
                        payload={
                            "loaded_model_id": model_id,
                            "evicted_model_ids": evicted,
                            "current_allocated_mb": self.current_allocated_mb + needed_mb,
                        }
                    )
                except Exception as e:
                    logger.error(f"Audit log error during model swap: {e}")

            # 4. Load requested model
            adapter.load()
            self._loaded_models[model_id] = now
            logger.info(f"VRAMScheduler: Loaded '{model_id}' ({needed_mb}MB VRAM).")

            if self.audit_ledger:
                try:
                    self.audit_ledger.append_event(
                        session_id=session_id or "vram-scheduler",
                        event_type="MODEL_LOADED",
                        actor_role="vram-scheduler",
                        payload={
                            "loaded_model_id": model_id,
                            "vram_mb": needed_mb,
                            "current_allocated_mb": self.current_allocated_mb,
                            "available_vram_mb": self.available_vram_mb,
                        }
                    )
                except Exception as e:
                    logger.error(f"Audit log error during model load: {e}")

            return adapter

    def unload(self, model_id: str, session_id: Optional[str] = None) -> bool:
        """Unloads a single model and frees its allocated VRAM budget."""
        with self._lock:
            if model_id not in self._loaded_models:
                return False
            adapter = self.registry.get_adapter(model_id)
            adapter.unload()
            del self._loaded_models[model_id]

            if self.audit_ledger:
                try:
                    self.audit_ledger.append_event(
                        session_id=session_id or "vram-scheduler",
                        event_type="MODEL_UNLOADED",
                        actor_role="vram-scheduler",
                        payload={
                            "unloaded_model_id": model_id,
                            "reason": "Explicit user unload",
                            "current_allocated_mb": self.current_allocated_mb,
                        }
                    )
                except Exception as e:
                    logger.error(f"Audit log error during model unload: {e}")

            return True

    def unload_all(self, session_id: Optional[str] = None) -> None:
        """Unloads all active models."""
        with self._lock:
            for model_id in list(self._loaded_models.keys()):
                adapter = self.registry.get_adapter(model_id)
                adapter.unload()
                del self._loaded_models[model_id]
                if self.audit_ledger:
                    try:
                        self.audit_ledger.append_event(
                            session_id=session_id or "vram-scheduler",
                            event_type="MODEL_UNLOADED",
                            actor_role="vram-scheduler",
                            payload={
                                "unloaded_model_id": model_id,
                                "reason": "Unload all models",
                                "current_allocated_mb": self.current_allocated_mb,
                            }
                        )
                    except Exception as e:
                        logger.error(f"Audit log error during unload_all: {e}")
