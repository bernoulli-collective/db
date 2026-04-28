import duckdb

def inspect_database(con):
    tables = con.execute("SHOW TABLES").fetchall()
    for table in tables:
        print(table[0])
        con.execute(f"SELECT * FROM {table[0]} LIMIT 10")
        print(con.fetchall())
