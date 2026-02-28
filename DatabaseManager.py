import pandas as pd

class DatabaseManager:
    def __init__(self, db_file):
        # Load entire database into a pandas DataFrame
        self.df = pd.read_csv(db_file)
        self.changes = []  # Store changes to be committed later

    def add_record(self, record):
        self.changes.append(('add', record))
        # No immediate changes to the DataFrame

    def update_record(self, index, new_data):
        self.changes.append(('update', index, new_data))
        # No immediate changes to the DataFrame

    def delete_record(self, index):
        self.changes.append(('delete', index))
        # No immediate changes to the DataFrame

    def commit(self):
        for change in self.changes:
            if change[0] == 'add':
                self.df = self.df.append(change[1], ignore_index=True)
            elif change[0] == 'update':
                self.df.loc[change[1]] = change[2]
            elif change[0] == 'delete':
                self.df = self.df.drop(change[1])
        self.changes = []  # Clear changes after committing

    def save_to_csv(self, output_file):
        self.df.to_csv(output_file, index=False)