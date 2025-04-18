from flask import Flask, render_template, request, jsonify
from Text_To_SQL_Langraph import run_query
import logging
from datetime import datetime
import os
from langsmith import Client
from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager

app = Flask(__name__)

LOG_FILE = 'sql_agent.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

client = Client(
    api_key=os.getenv("LANGSMITH_API_KEY"),
    api_url=os.getenv("LANGSMITH_ENDPOINT")
)

tracer = LangChainTracer(
    project_name=os.getenv("LANGSMITH_PROJECT")
)

callback_manager = CallbackManager([tracer])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def process_query():
    try:
        question = request.json.get('question')
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        logging.info(f"Processing question: {question}")
        answer, final_message, logs = run_query(question)
        
        return jsonify({
            'answer': answer,
            'status': 'success',
            'logs': logs
        })
    except Exception as e:
        logging.error(f"Error processing query: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/clear_history', methods=['POST'])
def clear_history():
    try:
        # Clear the log file by opening it in write mode
        with open(LOG_FILE, 'w') as log_file:
            log_file.write('')
        
        logging.info("Log history cleared.")
        return jsonify({
            'status': 'success',
            'message': 'Log history cleared successfully'
        }), 200
    except Exception as e:
        logging.error(f"Error clearing history: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 