from db.db import create_tables, create_db_connection

conn = create_db_connection()
create_tables(conn)
conn.close()