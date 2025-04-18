DB_CONFIG = {
    'username': 'add-your-username-here', 
    'password': 'add-password-here',
    'host': 'add-your-host-here',
    'database': 'add-your-database-name-here',
}

OPENAI_API_KEY = "add-your-openai-api-key-here"
DB_CONNECTION_STRING = f"mssql+pymssql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"

LANGSMITH_API_KEY="add-your-langsith-api-key-here"
LANGSMITH_TRACING="true"
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_PROJECT="add-your-project-name-here" 

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
