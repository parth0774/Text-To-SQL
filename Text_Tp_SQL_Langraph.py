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










