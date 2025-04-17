from langchain_community.utilities import SQLDatabase
from config import DB_CONNECTION_STRING, OPENAI_API_KEY
import os
import logging
from datetime import datetime

# Configure logging with a single log file
LOG_FILE = 'sql_agent.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Set OpenAI API key
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Initialize SQL Database connection
logging.info("Initializing database connection...")
db = SQLDatabase.from_uri(DB_CONNECTION_STRING)
logging.info(f"Database dialect: {db.dialect}")
logging.info(f"Available tables: {db.get_usable_table_names()}")

from typing import Any, Union, Literal
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode


def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    """
    Create a ToolNode with a fallback to handle errors and surface them to the agent.
    """
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

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI

# Initialize the toolkit with MS SQL Server
toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4"))
tools = toolkit.get_tools()

list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

from langchain_core.tools import tool


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


from langchain_core.prompts import ChatPromptTemplate

query_check_system = """You are a SQL expert with a strong attention to detail.
Double check the SQL Server query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins
- Using proper SQL Server syntax (e.g., TOP instead of LIMIT)

If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.

You will call the appropriate tool to execute the query after running this check."""

query_check_prompt = ChatPromptTemplate.from_messages(
    [("system", query_check_system), ("placeholder", "{messages}")]
)
query_check = query_check_prompt | ChatOpenAI(model="gpt-4", temperature=0).bind_tools(
    [db_query_tool], tool_choice="required"
)

from typing import Annotated
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages


# Define the state for the agent
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# Define a new graph
workflow = StateGraph(State)


# Add a node for the first tool call
def first_tool_call(state: State) -> dict[str, list[AIMessage]]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sql_db_list_tables",
                        "args": {},
                        "id": "tool_abcd123",
                    }
                ],
            )
        ]
    }


def model_check_query(state: State) -> dict[str, list[AIMessage]]:
    """
    Use this tool to double-check if your query is correct before executing it.
    """
    logging.info("Validating query...")
    result = query_check.invoke({"messages": [state["messages"][-1]]})
    logging.info(f"Query validation result: {result}")
    return {"messages": [result]}


workflow.add_node("first_tool_call", first_tool_call)

# Add nodes for the first two tools
workflow.add_node(
    "list_tables_tool", create_tool_node_with_fallback([list_tables_tool])
)
workflow.add_node("get_schema_tool", create_tool_node_with_fallback([get_schema_tool]))

# Add a node for a model to choose the relevant tables based on the question and available tables
model_get_schema = ChatOpenAI(model="gpt-4", temperature=0).bind_tools(
    [get_schema_tool]
)
workflow.add_node(
    "model_get_schema",
    lambda state: {
        "messages": [model_get_schema.invoke(state["messages"])],
    },
)


# Describe a tool to represent the end state
class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""

    final_answer: str = Field(..., description="The final answer to the user")


# Add a node for a model to generate a query based on the question and schema
query_gen_system = """You are a SQL expert with a strong attention to detail.

Given an input question, output a syntactically correct SQL Server query to run, then look at the results of the query and return the answer.

DO NOT call any tool besides SubmitFinalAnswer to submit the final answer.

When generating the query:

Output the SQL query that answers the input question without a tool call.

Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results using TOP.
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for the relevant columns given the question.

If you get an error while executing a query, rewrite the query and try again.

If you get an empty result set, you should try to rewrite the query to get a non-empty result set. 
NEVER make stuff up if you don't have enough information to answer the query... just say you don't have enough information.

If you have enough information to answer the input question, simply invoke the appropriate tool to submit the final answer to the user.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database."""
query_gen_prompt = ChatPromptTemplate.from_messages(
    [("system", query_gen_system), ("placeholder", "{messages}")]
)
query_gen = query_gen_prompt | ChatOpenAI(model="gpt-4", temperature=0).bind_tools(
    [SubmitFinalAnswer]
)


def query_gen_node(state: State):
    message = query_gen.invoke(state)

    # Sometimes, the LLM will hallucinate and call the wrong tool. We need to catch this and return an error message.
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: The wrong tool was called: {tc['name']}. Please fix your mistakes. Remember to only call SubmitFinalAnswer to submit the final answer. Generated queries should be outputted WITHOUT a tool call.",
                        tool_call_id=tc["id"],
                    )
                )
    else:
        tool_messages = []
    return {"messages": [message] + tool_messages}


workflow.add_node("query_gen", query_gen_node)

# Add a node for the model to check the query before executing it
workflow.add_node("correct_query", model_check_query)

# Add node for executing the query
workflow.add_node("execute_query", create_tool_node_with_fallback([db_query_tool]))


# Define a conditional edge to decide whether to continue or end the workflow
def should_continue(state: State) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    # If there is a tool call, then we finish
    if getattr(last_message, "tool_calls", None):
        return END
    if last_message.content.startswith("Error:"):
        return "query_gen"
    else:
        return "correct_query"


# Specify the edges between the nodes
workflow.add_edge(START, "first_tool_call")
workflow.add_edge("first_tool_call", "list_tables_tool")
workflow.add_edge("list_tables_tool", "model_get_schema")
workflow.add_edge("model_get_schema", "get_schema_tool")
workflow.add_edge("get_schema_tool", "query_gen")
workflow.add_conditional_edges(
    "query_gen",
    should_continue,
)
workflow.add_edge("correct_query", "execute_query")
workflow.add_edge("execute_query", "query_gen")

# Compile the workflow into a runnable
app = workflow.compile()

def run_query(question: str):
    """
    Run a query against the SQL Server database and return the results.
    
    Args:
        question (str): The natural language question to convert to SQL and execute
        
    Returns:
        tuple: (answer, final_message, logs) - The answer to the question, the final message, and the logs
    """
    # Create a list to store logs
    logs = []
    
    try:
        logging.info(f"Processing question: {question}")
        messages = app.invoke({"messages": [("user", question)]})
        
        # Log the final message content
        final_message = messages["messages"][-1]
        logging.info(f"Final message content: {final_message.content}")
        
        # Initialize variables for answer and SQL query
        answer = None
        sql_query = None

        if final_message.tool_calls:
            logging.info("Tool calls found in final message")
            answer = final_message.tool_calls[0]["args"]["final_answer"]
        else:
            logging.info("No tool calls found, returning content directly")
            answer = final_message.content
        
        # Extract SQL query from logs
        for msg in messages["messages"]:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for call in msg.tool_calls:
                    if call["name"] == 'db_query_tool':
                        sql_query = call["args"]["query"]
                        break
        
        # Format the answer to include the SQL query
        formatted_answer = f"Answer: {answer}\n\nSQL Query:\n{sql_query}"
        
        # Read the logs from the log file
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r') as log_file:
                    logs = log_file.readlines()
            else:
                logging.warning(f"Log file {LOG_FILE} not found")
        except Exception as e:
            logging.error(f"Error reading log file: {str(e)}")
            logs = [f"Error reading log file: {str(e)}"]
        
        return formatted_answer, final_message, logs
    except Exception as e:
        error_message = f"Error processing query: {str(e)}"
        logging.error(error_message)
        logs.append(error_message)
        return error_message, None, logs

if __name__ == "__main__":
    # Example usage
    question = "provide me information on order details?"
    logging.info(f"Starting query execution for question: {question}")
    result = run_query(question)
    logging.info("Query execution completed")