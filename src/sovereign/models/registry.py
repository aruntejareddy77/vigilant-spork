"""
src/sovereign/models/registry.py
Model catalog and runtime discovery registry.
"""
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from sovereign.models.manifest import ModelCapability, ModelManifest, load_manifest

logger = logging.getLogger("sovereign.models.registry")


class ModelRegistry:
    """
    Central catalog of registered model manifests with capability indexing
    and hot-registration support without orchestrator restarts.
    """

    def __init__(self):
        self._manifests: Dict[str, ModelManifest] = {}

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

    def unregister(self, model_id: str) -> bool:
        """Unregisters a model manifest. Returns True if removed, False if not found."""
        if model_id in self._manifests:
            del self._manifests[model_id]
            logger.info(f"Unregistered model: {model_id}")
            return True
        return False

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
        """Clears all registered manifests."""
        self._manifests.clear()
