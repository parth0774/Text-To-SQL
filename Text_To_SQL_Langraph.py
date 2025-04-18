import os
import json
from datetime import datetime
from typing import Any, Union, Literal, Annotated
from typing_extensions import TypedDict
from langsmith import Client
from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.messages import ToolMessage, AIMessage, AnyMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from config import DB_CONNECTION_STRING, OPENAI_API_KEY, LANGSMITH_API_KEY, LANGSMITH_ENDPOINT, LANGSMITH_PROJECT

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = LANGSMITH_ENDPOINT
os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

SQL_LOG_FILE = 'sql_log.json'

client = Client(
    api_key=LANGSMITH_API_KEY,
    api_url=LANGSMITH_ENDPOINT
)

tracer = LangChainTracer(
    project_name=LANGSMITH_PROJECT
)

callback_manager = CallbackManager([tracer])

def log_to_json(question: str, sql_query: str, answer: str, timestamp: str = None):
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    
    log_entry = {
        "timestamp": timestamp,
        "question": question,
        "sql_query": sql_query,
        "answer": answer
    }
    
    try:
        with open(SQL_LOG_FILE, 'a') as f:
            json.dump(log_entry, f)
            f.write('\n')
    except Exception as e:
        print(f"Error writing to log file: {e}")

db = SQLDatabase.from_uri(DB_CONNECTION_STRING)

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

toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4", temperature=0.1))
tools = toolkit.get_tools()

list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

@tool
def db_query_tool(query: str) -> str:
    """
    Execute a SQL query against the database and return the raw result.
    If the query fails, return a detailed error message.
    """
    try:
        result = db.run_no_throw(query)
        if not result:
            return "Error: Query returned no results."
        return result
    except Exception as e:
        return f"SQL Error: {str(e)}"

def analyze_query_error(error_message: str) -> str:
    error_lower = error_message.lower()
    if "syntax" in error_lower:
        return "The query has a syntax error. Please check the SQL syntax and try again."
    elif "invalid column" in error_lower:
        return "One or more columns in the query don't exist. Please check the column names."
    elif "invalid object" in error_lower:
        return "One or more tables in the query don't exist. Please check the table names."
    elif "ambiguous column" in error_lower:
        return "There are ambiguous column names in the query. Please specify the table name for ambiguous columns."
    return "The query failed. Please check the query structure and try again."

def should_retry_query(error_message: str) -> bool:
    return "Error:" in error_message or "SQL Error:" in error_message

query_gen_system = """You are a SQL expert. Your ONLY task is to convert natural language questions into SQL Server queries.

You have access to the database schema. Use it to generate accurate SQL queries.

IMPORTANT:
1. You MUST output ONLY the SQL query
2. The query MUST start with SELECT
3. Do NOT add any explanations, comments, or formatting
4. Do NOT use any tools or function calls
5. Just output the raw SQL query

Rules for SQL generation:
1. Always use proper SQL Server syntax
2. Use table aliases in joins
3. Quote string literals with single quotes
4. Use proper column names from the schema
5. Include only necessary columns
6. Handle NULL values appropriately
7. Use proper data types in conditions

Remember:
- Output ONLY the SQL query
- Query MUST start with SELECT
- No explanations or formatting
- No tools or function calls"""

query_gen_prompt = ChatPromptTemplate.from_messages(
    [("system", query_gen_system), ("placeholder", "{messages}")]
)
query_gen = query_gen_prompt | ChatOpenAI(model="gpt-4", temperature=0)

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

workflow = StateGraph(State)

def first_tool_call(state: State) -> dict[str, list[AIMessage]]:
    schema = db.get_table_info()
    return {
        "messages": [
            AIMessage(content=f"Database Schema:\n{schema}\n\nPlease generate a SQL query for the user's question.")
        ]
    }

def query_gen_node(state: State):
    messages = state["messages"]
    user_question = messages[0].content if isinstance(messages[0], str) else messages[0].content
    schema_info = messages[1].content if len(messages) > 1 else ""
    response = query_gen.invoke({"messages": [
        ("system", f"Database Schema:\n{schema_info}"),
        ("user", user_question)
    ]})
    sql_query = response.content.strip()
    
    # Validate that it's a SQL query
    if not sql_query.upper().startswith('SELECT'):
        return {
            "messages": [
                AIMessage(content="Error: Generated response is not a valid SQL query. Please try again.")
            ]
        }
    
    return {"messages": [AIMessage(content=sql_query)]}

def should_continue(state: State) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    
    if last_message.content and last_message.content.strip().upper().startswith('SELECT'):
        return END
    
    if last_message.content and ("Error:" in last_message.content or "SQL Error:" in last_message.content):
        return "query_gen"
    
    return END

workflow.add_node("first_tool_call", first_tool_call)
workflow.add_node("query_gen", query_gen_node)

workflow.add_edge(START, "first_tool_call")
workflow.add_edge("first_tool_call", "query_gen")
workflow.add_conditional_edges("query_gen", should_continue)

app = workflow.compile()

def run_query(question: str, max_retries: int = 3):
    try:
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            messages = app.invoke({"messages": [("user", question)]})
            final_message = messages["messages"][-1]
            
            if not final_message.content:
                return "Error: Failed to generate SQL query", None, []
            
            sql_query = final_message.content.strip()
            
            if not sql_query.upper().startswith('SELECT'):
                return "Error: Generated response is not a valid SQL query", None, []
            
            result = db_query_tool.invoke(sql_query)
            
            if not should_retry_query(result):
                log_to_json(question, sql_query, result)
                
                formatted_response = f"""SQL Query:
{sql_query}

Results:
{result}"""
                return formatted_response, None, []
            
            last_error = analyze_query_error(result)
            retry_count += 1
            
            if retry_count < max_retries:
                question = f"{question}\nPrevious error: {last_error}\nPlease fix the SQL query and try again."
        
        error_message = f"Failed after {max_retries} attempts. Last error: {last_error}"
        log_to_json(question, sql_query, error_message)
        return error_message, None, [error_message]
        
    except Exception as e:
        error_message = f"Error processing query: {str(e)}"
        log_to_json(question, "", error_message)
        return error_message, None, [error_message]

if __name__ == "__main__":
    question = "provide me information on order details?"
    result, final_message, logs = run_query(question)
    print(result)