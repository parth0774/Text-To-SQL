# Database configuration
DB_CONFIG = {
    'username': 'admin', 
    'password': 'UPZLcrTX3n9XVb3&',
    'host': 'northwind.cfamiqo2obcc.us-east-2.rds.amazonaws.com',
    'database': 'Northwind'
}

# OpenAI configuration
OPENAI_API_KEY = "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"

# Database connection string
DB_CONNECTION_STRING = f"mssql+pymssql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"

