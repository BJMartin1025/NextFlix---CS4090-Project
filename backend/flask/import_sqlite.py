import pandas as pd
from sqlalchemy import create_engine

df = pd.read_csv('movie_dataset.csv', sep=None, engine='python')  # auto-detects delim
df = df.fillna('')  # optional cleaning
engine = create_engine('sqlite:///movies.db')   # creates movies.db in current folder
df.to_sql('movies_flat', engine, if_exists='replace', index=False)
print("Imported", len(df), "rows into movies.db -> movies_flat")