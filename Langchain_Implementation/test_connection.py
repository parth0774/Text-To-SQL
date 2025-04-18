from sqlalchemy import create_engine, text
import config
import time

def test_connection():    
    try:
        engine = create_engine(config.DB_CONNECTION_STRING)
        start_time = time.time()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("Connection successful!")
            print(f"Query execution time: {time.time() - start_time:.2f} seconds")
            
            print("\nTesting table access...")
            tables = conn.execute(text("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
            """))
            
            print("\nAvailable tables:")
            for table in tables:
                print(f"✓ {table[0]}")
            
            return True
            
    except Exception as e:
        print(f"✗ Connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_connection() 