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

LANGSMITH_API_KEY="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"
LANGSMITH_TRACING="true"
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_PROJECT="Text-SQL-Agent" 

SCHEMA_INFO = """
The database contains the following tables:

1. Categories
- CategoryID (int, NOT NULL)
- CategoryName (nvarchar, NOT NULL)
- Description (ntext, NULL)
- Picture (image, NULL)

2. Customers
- CustomerID (nchar, NOT NULL)
- CompanyName (nvarchar, NOT NULL)
- ContactName (nvarchar, NULL)
- ContactTitle (nvarchar, NULL)
- Address (nvarchar, NULL)
- City (nvarchar, NULL)
- Region (nvarchar, NULL)
- PostalCode (nvarchar, NULL)
- Country (nvarchar, NULL)
- Phone (nvarchar, NULL)
- Fax (nvarchar, NULL)

3. Order Details
- OrderID (int, NOT NULL)
- ProductID (int, NOT NULL)
- UnitPrice (money, NOT NULL, default: 0)
- Quantity (smallint, NOT NULL, default: 1)
- Discount (real, NOT NULL, default: 0)

4. Orders
- OrderID (int, NOT NULL)
- CustomerID (nchar, NULL)
- EmployeeID (int, NULL)
- OrderDate (datetime, NULL)
- RequiredDate (datetime, NULL)
- ShippedDate (datetime, NULL)
- ShipVia (int, NULL)
- Freight (money, NULL, default: 0)
- ShipName (nvarchar, NULL)
- ShipAddress (nvarchar, NULL)
- ShipCity (nvarchar, NULL)
- ShipRegion (nvarchar, NULL)
- ShipPostalCode (nvarchar, NULL)
- ShipCountry (nvarchar, NULL)

5. Products
- ProductID (int, NOT NULL)
- ProductName (nvarchar, NOT NULL)
- SupplierID (int, NULL)
- CategoryID (int, NULL)
- QuantityPerUnit (nvarchar, NULL)
- UnitPrice (money, NULL, default: 0)
- UnitsInStock (smallint, NULL, default: 0)
- UnitsOnOrder (smallint, NULL, default: 0)
- ReorderLevel (smallint, NULL, default: 0)
- Discontinued (bit, NOT NULL, default: 0)
"""
