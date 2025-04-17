document.addEventListener('DOMContentLoaded', function() {
    const queryInput = document.getElementById('query');
    const submitBtn = document.getElementById('submitBtn');
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    const resultDiv = document.getElementById('result');
    const answerDiv = document.getElementById('answer');
    const logBox = document.getElementById('logBox');

    // Function to add a log message to the log box
    function addLogMessage(message, type = 'info') {
        const logMessage = document.createElement('div');
        logMessage.className = `log-message ${type}`;
        logMessage.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        logBox.appendChild(logMessage);
        logBox.scrollTop = logBox.scrollHeight;
    }

    // Function to handle the query submission
    async function handleQuery() {
        const question = queryInput.value.trim();
        if (!question) {
            addLogMessage('Please enter a question', 'warning');
            return;
        }

        // Show loading state
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading"></span> Processing...';
        resultDiv.classList.add('hidden');

        try {
            addLogMessage(`Processing question: ${question}`);
            
            const response = await fetch('/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question }),
            });

            const data = await response.json();

            if (response.ok) {
                answerDiv.textContent = data.answer;
                resultDiv.classList.remove('hidden');
                addLogMessage('Query processed successfully');
                // Display logs
                if (data.logs && Array.isArray(data.logs)) {
                    data.logs.forEach(log => addLogMessage(log, 'info'));
                }
            } else {
                addLogMessage(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            addLogMessage(`Error: ${error.message}`, 'error');
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Query';
        }
    }

    // Function to clear history
    async function clearHistory() {
        try {
            const response = await fetch('/clear_history', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            const data = await response.json();

            if (response.ok) {
                // Clear the log box
                logBox.innerHTML = '';
                // Clear the query input and result
                queryInput.value = '';
                answerDiv.textContent = '';
                resultDiv.classList.add('hidden');
                addLogMessage('History cleared successfully', 'info');
            } else {
                addLogMessage(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            addLogMessage(`Error: ${error.message}`, 'error');
        }
    }

    // Event listeners
    submitBtn.addEventListener('click', handleQuery);
    clearHistoryBtn.addEventListener('click', clearHistory);
    queryInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            handleQuery();
        }
    });

    // Initial log message
    addLogMessage('Application started. Ready to process queries.');
}); 