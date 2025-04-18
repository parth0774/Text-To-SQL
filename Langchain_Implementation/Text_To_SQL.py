from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain.agents.agent_types import AgentType
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
import config
import os

def init_sql_agent():
    os.environ["OPENAI_API_KEY"] = config.OPENAI_API_KEY
    
    db_engine = create_engine(config.DB_CONNECTION_STRING)
    db = SQLDatabase(db_engine)
    
    llm = ChatOpenAI(temperature=0.0, model="gpt-4")
    
    sql_toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    agent = create_sql_agent(
        llm=llm,
        toolkit=sql_toolkit,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )
    
    return agent

def run_query(question):
    try:
        agent = init_sql_agent()
        result = agent.invoke(question)
        return result
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    questions = [
        "How many entries we have in Customers table?",
    ]
    
    for question in questions:
        print(f"\nQuestion: {question}")
        result = run_query(question)
        print(f"Answer: {result}") 