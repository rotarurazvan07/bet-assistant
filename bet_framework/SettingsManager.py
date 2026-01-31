import yaml
from pathlib import Path
from typing import Any, Optional, Dict

class SettingsManager:

    def __init__(self, directory: str):
        self._directory = Path(directory)
        self.settings: Dict[str, Any] = {}
        # print("Settings directory: ", self._directory.resolve())
        self._load()

    def _load(self) -> None:
        """Reload all .yaml files from the directory tree into self.settings."""
        self.settings = {}
        for yaml_file in sorted(self._directory.rglob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text()) or {}
            except Exception as e:
                data = {"_load_error": str(e)}

            node = self.settings
            for part in yaml_file.relative_to(self._directory.parent).parts[:-1]:
                node = node.setdefault(part, {})
            node[yaml_file.stem] = data

    def get(self, *keys: str) -> Optional[Any]:
        self._load()

        node = self.settings
        for key in keys:
            if not isinstance(node, dict):
                break
            node = node.get(key)
        else:
            if node is not None:
                return node

        def _search(d: dict, target: str) -> Optional[Any]:
            if target in d:
                return d[target]
            for v in d.values():
                if isinstance(v, dict):
                    result = _search(v, target)
                    if result is not None:
                        return result
            return None

        return _search(self.settings, keys[-1])

    def write(self, directory: str, name: str, data: Dict[str, Any]) -> bool:
        try:
            p = Path(directory) / f"{name}.yaml"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(yaml.dump(data))
            return True
        except Exception as e:
            print(f"[SettingsManager] write failed for {name}: {e}")
            return False

    def delete(self, directory: str, name: str) -> bool:
        try:
            p = Path(directory) / f"{name}.yaml"
            if p.exists():
                p.unlink()
            return True
        except Exception as e:
            print(f"[SettingsManager] delete failed for {name}: {e}")
            return False
