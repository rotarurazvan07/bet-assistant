import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class SettingsManager:
    """Central settings manager that can load multiple YAML configs into memory.

    Usage:
      sm = SettingsManager()
      sm.load_settings('config')                # loads all .yaml in config/ dir
      sm.load_settings('config/main.yaml')      # loads main and any referenced yaml files
      sm.get_config('tip_templates')
    """

    def __init__(self):
        self.settings: Dict[str, Any] = {}
        self.configs: Dict[str, Any] = {}

    def load_settings(self, path: str) -> None:
        """Load settings from a path. If path is a directory, load all .yaml files inside.

        If path is a YAML file and it contains keys referencing other YAML files, those
        referenced files are loaded as well.
        """
        p = Path(path)
        if p.is_dir():
            for child in sorted(p.glob('*.yaml')):
                try:
                    content = yaml.safe_load(child.read_text())
                    key = child.stem
                    self.configs[key] = content
                except Exception as e:
                    # store error under configs for debugging
                    self.configs[child.stem] = {'_load_error': str(e)}
        elif p.is_file():
            try:
                main = yaml.safe_load(p.read_text()) or {}
                # store main settings under 'main'
                self.settings = main
                # if main contains file paths, attempt to load them
                base_dir = p.parent
                for k, v in main.items():
                    if isinstance(v, str) and v.lower().endswith(('.yml', '.yaml')):
                        ref_path = (base_dir / v).resolve()
                        if ref_path.exists():
                            try:
                                content = yaml.safe_load(ref_path.read_text())
                                self.configs[ref_path.stem] = content
                            except Exception as e:
                                self.configs[ref_path.stem] = {'_load_error': str(e)}
            except Exception as e:
                self.settings = {'_load_error': str(e)}
        else:
            raise FileNotFoundError(f"Settings path not found: {path}")

    def get_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a preloaded config by file stem/name."""
        return self.configs.get(name, None)


settings_manager = SettingsManager()
