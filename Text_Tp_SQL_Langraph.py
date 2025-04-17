from langchain_community.utilities import SQLDatabase
from config import DB_CONNECTION_STRING, OPENAI_API_KEY
import os
import logging
from datetime import datetime
from typing import Any
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from typing import Annotated, Literal
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
logging.info("Initializing database connection...")
db = SQLDatabase.from_uri(DB_CONNECTION_STRING)
logging.info(f"Database dialect: {db.dialect}")
logging.info(f"Available tables: {db.get_usable_table_names()}")

toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4"))
tools = toolkit.get_tools()

list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )

def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

@tool
def db_query_tool(query: str) -> str:
    """
    Execute a SQL query against the database and get back the result.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    logging.info(f"Executing query: {query}")
    result = db.run_no_throw(query)
    if not result:
        logging.error("Query execution failed")
        return "Error: Query failed. Please rewrite your query and try again."
    logging.info("Query executed successfully")
    return result








