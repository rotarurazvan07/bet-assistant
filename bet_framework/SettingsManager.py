import yaml


class SettingsManager:
    def __init__(self):
        self.settings = None

    def load_settings(self, config_file):
        with open(config_file, 'r') as f:
            self.settings = yaml.load(f, Loader=yaml.SafeLoader)

settings_manager = SettingsManager()
