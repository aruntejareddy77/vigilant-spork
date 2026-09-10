"""
src/sovereign/models/registry.py
Model catalog and runtime discovery registry.
"""
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from sovereign.models.adapter import BaseModelAdapter
from sovereign.models.factory import create_adapter
from sovereign.models.manifest import ModelCapability, ModelManifest, load_manifest

logger = logging.getLogger("sovereign.models.registry")


class ModelRegistry:
    """
    Central catalog of registered model manifests with capability indexing,
    adapter instance caching, and hot-registration support without orchestrator restarts.
    """

    def __init__(self):
        self._manifests: Dict[str, ModelManifest] = {}
        self._adapters: Dict[str, BaseModelAdapter] = {}

    def register_manifest(self, manifest: ModelManifest) -> None:
        """Registers or updates a validated ModelManifest."""
        self._manifests[manifest.model_id] = manifest
        logger.info(f"Registered model manifest: {manifest.model_id} ({manifest.name})")

    def register_from_file(self, manifest_path: Union[str, Path]) -> ModelManifest:
        """Loads and registers a model manifest from a file path."""
        manifest = load_manifest(manifest_path)
        self.register_manifest(manifest)
        return manifest

    def get_manifest(self, model_id: str) -> Optional[ModelManifest]:
        """Retrieves a manifest by model_id, or None if not registered."""
        return self._manifests.get(model_id)

    def list_manifests(self) -> List[ModelManifest]:
        """Returns a list of all currently registered model manifests."""
        return list(self._manifests.values())

    def find_by_capability(
        self, capability: Union[ModelCapability, str]
    ) -> List[ModelManifest]:
        """Finds all registered models that declare the specified capability."""
        return [m for m in self._manifests.values() if m.has_capability(capability)]

    def get_adapter(self, model_id: str) -> BaseModelAdapter:
        """
        Retrieves or instantiates the cached adapter for the specified model_id.
        Raises KeyError if the model_id is not registered.
        """
        if model_id in self._adapters:
            return self._adapters[model_id]

        manifest = self.get_manifest(model_id)
        if not manifest:
            raise KeyError(f"Model '{model_id}' is not registered in the catalog.")

        adapter = create_adapter(manifest)
        self._adapters[model_id] = adapter
        return adapter

    def unregister(self, model_id: str) -> bool:
        """Unregisters a model manifest and unloads its adapter if active."""
        if model_id in self._adapters:
            try:
                self._adapters[model_id].unload()
            except Exception as e:
                logger.warning(f"Error unloading adapter for {model_id}: {e}")
            del self._adapters[model_id]

        if model_id in self._manifests:
            del self._manifests[model_id]
            logger.info(f"Unregistered model: {model_id}")
            return True
        return False

    def unload_all(self) -> None:
        """Unloads all currently active model adapters."""
        for model_id, adapter in list(self._adapters.items()):
            try:
                adapter.unload()
            except Exception as e:
                logger.warning(f"Error unloading adapter {model_id}: {e}")
        self._adapters.clear()

    def discover_models(self, directory_path: Union[str, Path]) -> int:
        """
        Recursively discovers and registers all valid model manifests (.yaml, .yml, .json)
        found in the specified directory. Returns count of successfully loaded models.
        """
        dir_path = Path(directory_path).resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            return 0

        count = 0
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith((".yaml", ".yml", ".json")):
                    fpath = Path(root) / file
                    try:
                        self.register_from_file(fpath)
                        count += 1
                    except Exception as e:
                        logger.debug(f"Skipping non-manifest file {fpath}: {e}")

        logger.info(f"Discovered and registered {count} models from {dir_path}")
        return count

    def clear(self) -> None:
        """Clears all registered manifests and unloads all cached adapters."""
        self.unload_all()
        self._manifests.clear()
