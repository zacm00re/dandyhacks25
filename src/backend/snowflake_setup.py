from snowflake.snowpark import Session

def create_snowpark_session(connection_params):
    """
    Create a Snowpark session.
    """
    session = Session.builder.configs(connection_params).create()
    return session

def ensure_warehouse(session, warehouse_name="MY_WAREHOUSE"):
    """
    Ensure the warehouse exists and is set as the current warehouse.
    """
    session.sql(f"""
        CREATE WAREHOUSE IF NOT EXISTS {warehouse_name}
        WITH WAREHOUSE_SIZE = 'SMALL'
        AUTO_SUSPEND = 60
        AUTO_RESUME = TRUE
    """).collect()
    
    # Use this warehouse for the session
    session.sql(f"USE WAREHOUSE {warehouse_name}").collect()

def ensure_content_table(session, table_name="CONTENT_CHUNKS"):
    """
    Ensure the content table exists for storing chunks and embeddings.
    """
    session.sql(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            chunk_id INT AUTOINCREMENT PRIMARY KEY,
            file_title STRING,
            content STRING,
            embedding VECTOR
        )
    """).collect()
