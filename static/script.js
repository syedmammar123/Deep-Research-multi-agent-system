// DOM elements
const apiSection = document.getElementById('apiSection');
const researchSection = document.getElementById('researchSection');
const loadingSection = document.getElementById('loadingSection');
const resultsSection = document.getElementById('resultsSection');
const progressLog = document.getElementById('progressLog');
const resultsContainer = document.getElementById('resultsContainer');
const startBtn = document.getElementById('startBtn');
const intermediateResults = document.getElementById('intermediateResults');
const intermediateProgressLog = document.getElementById('intermediateProgressLog');
const intermediateAnswers = document.getElementById('intermediateAnswers');

// State management
let isResearching = false;
let intermediateData = {
    questions: [],
    answers: [],
    progress: []
};

// API Keys management
function setApiKeys() {
    const openaiKey = document.getElementById('openaiKey').value.trim();
    const tavilyKey = document.getElementById('tavilyKey').value.trim();
    
    if (!openaiKey || !tavilyKey) {
        showError('Please enter both API keys');
        return;
    }
    
    fetch('/set_api_keys', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            openai_api_key: openaiKey,
            tvly_api_key: tavilyKey
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess('API keys saved successfully!');
            showResearchSection();
        } else {
            showError(data.message);
        }
    })
    .catch(error => {
        showError('Failed to save API keys: ' + error.message);
    });
}

// Research management
function startResearch() {
    const topic = document.getElementById('researchTopic').value.trim();
    
    if (!topic) {
        showError('Please enter a research topic');
        return;
    }
    
    if (isResearching) {
        return;
    }
    
    // Reset state
    isResearching = true;
    progressLog.innerHTML = '';
    resultsContainer.innerHTML = '';
    intermediateData = { questions: [], answers: [], progress: [] };
    
    // Show loading section
    showLoadingSection();
    
    // Update button state
    updateButtonState();
    
    // Start research
    fetch('/start_research', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ topic: topic })
    })
    .then(response => response.json())
    .then(data => {
        isResearching = false;
        updateButtonState();
        
        if (data.success) {
            showResults(data.result, data.progress);
        } else {
            showError(data.message);
            showResearchSection();
        }
    })
    .catch(error => {
        isResearching = false;
        updateButtonState();
        showError('Research failed: ' + error.message);
        showResearchSection();
    });
}

// Simulate intermediate updates (since we can't get real-time updates with simple HTTP)
function simulateIntermediateUpdates() {
    const updateInterval = setInterval(() => {
        if (!isResearching) {
            clearInterval(updateInterval);
            return;
        }
        
        // Add some simulated progress
        const progressMessages = [
            "Generating research questions...",
            "Searching the web for information...",
            "Analyzing search results...",
            "Compiling research findings...",
            "Almost done..."
        ];
        
        const randomProgress = progressMessages[Math.floor(Math.random() * progressMessages.length)];
        addIntermediateProgress(randomProgress);
        
        // Show intermediate results section after a few updates
        if (intermediateData.progress.length >= 3) {
            showIntermediateResults();
        }
    }, 2000);
}

function addIntermediateProgress(message) {
    const timestamp = new Date().toLocaleTimeString();
    intermediateData.progress.push(`[${timestamp}] ${message}`);
    
    if (intermediateProgressLog) {
        intermediateProgressLog.innerHTML = intermediateData.progress.map(msg => 
            `<div class="log-entry"><div class="message">${msg}</div></div>`
        ).join('');
    }
}

function showIntermediateResults() {
    if (intermediateResults) {
        intermediateResults.style.display = 'block';
    }
}

function resetResearch() {
    // Reset all sections
    hideAllSections();
    showApiSection();
    
    // Clear form
    document.getElementById('researchTopic').value = '';
    
    // Reset state
    isResearching = false;
    updateButtonState();
}

// UI management
function showApiSection() {
    hideAllSections();
    apiSection.style.display = 'block';
}

function showResearchSection() {
    hideAllSections();
    researchSection.style.display = 'block';
}

function showLoadingSection() {
    hideAllSections();
    loadingSection.style.display = 'block';
    
    // Start simulating intermediate updates
    setTimeout(() => {
        if (isResearching) {
            simulateIntermediateUpdates();
        }
    }, 1000);
}

function showResultsSection() {
    hideAllSections();
    resultsSection.style.display = 'block';
}

function hideAllSections() {
    apiSection.style.display = 'none';
    researchSection.style.display = 'none';
    loadingSection.style.display = 'none';
    resultsSection.style.display = 'none';
}

function showResults(result, progress) {
    // Show progress log
    if (progress && progress.length > 0) {
        progressLog.innerHTML = progress.map(msg => 
            `<div class="log-entry"><div class="message">${msg}</div></div>`
        ).join('');
    }
    
    // Render markdown content
    if (marked) {
        resultsContainer.innerHTML = marked.parse(result);
    } else {
        resultsContainer.textContent = result;
    }
    
    showResultsSection();
}

function updateButtonState() {
    const btnText = startBtn.querySelector('.btn-text');
    const btnLoading = startBtn.querySelector('.btn-loading');
    
    if (isResearching) {
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        startBtn.disabled = true;
    } else {
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        startBtn.disabled = false;
    }
}

// Notification functions
function showSuccess(message) {
    showNotification(message, 'success');
}

function showError(message) {
    showNotification(message, 'error');
}

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    showApiSection();
}); 