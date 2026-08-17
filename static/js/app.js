let isResearching = false;
let workingStatusDiv = null;
let lastReportMarkdown = '';

function addMessage(content, type) {
    const emptyState = document.getElementById('emptyState');
    if (emptyState) {
        emptyState.remove();
    }

    const messagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = type === 'user' ? 'YOU' : 'AI';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (type === 'assistant' && typeof marked !== 'undefined') {
        contentDiv.innerHTML = marked.parse(content);
        contentDiv.classList.add('report');
        contentDiv.querySelectorAll('a[href]').forEach(link => {
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            if (/^\[\d+\]$/.test(link.textContent.trim())) {
                link.classList.add('citation');
                link.title = link.href;
            }
        });
    } else {
        contentDiv.textContent = content;
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    return messageDiv;
}

function showWorkingStatus() {
    const messagesDiv = document.getElementById('chatMessages');
    workingStatusDiv = document.createElement('div');
    workingStatusDiv.className = 'working-status';
    workingStatusDiv.innerHTML = `
        <div class="working-header">
            <div class="working-spinner"></div>
            <div class="working-title">Researching</div>
        </div>
        <div id="progressSteps"></div>
    `;
    messagesDiv.appendChild(workingStatusDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function addProgressStep(title, icon, details = null, isComplete = false, key = null) {
    if (!workingStatusDiv) return;

    const stepsContainer = workingStatusDiv.querySelector('#progressSteps');
    const stepId = `step-${Date.now()}-${stepsContainer.children.length}`;

    const stepDiv = document.createElement('div');
    stepDiv.className = isComplete ? 'progress-section complete' : 'progress-section';
    // Keyed, not indexed: parallel branches finish out of order.
    if (key) stepDiv.dataset.key = key;
    stepDiv.innerHTML = `
        <div class="progress-header" onclick="toggleStep('${stepId}')">
            <div class="progress-header-left">
                <span class="progress-label">${title}</span>
            </div>
            <span class="step-badge">${isComplete ? 'Done' : 'Working'}</span>
            <span class="progress-toggle" id="${stepId}-toggle"></span>
        </div>
        <div class="progress-content" id="${stepId}-content">
            <div class="progress-details">${details || 'Processing...'}</div>
        </div>
    `;

    stepsContainer.appendChild(stepDiv);

    const messagesDiv = document.getElementById('chatMessages');
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function updateProgressStepByKey(key, details, isComplete = false, badge = null) {
    if (!workingStatusDiv) return;

    const step = workingStatusDiv.querySelector(`.progress-section[data-key="${key}"]`);
    if (!step) return;

    if (details !== null) {
        step.querySelector('.progress-details').innerHTML = details;
    }
    if (badge) {
        step.querySelector('.step-badge').textContent = badge;
    }
    if (isComplete) {
        step.classList.add('complete');
        if (!badge) step.querySelector('.step-badge').textContent = 'Done';
    }
}

function toggleStep(stepId) {
    const content = document.getElementById(`${stepId}-content`);
    const toggle = document.getElementById(`${stepId}-toggle`);

    if (content.classList.contains('open')) {
        content.classList.remove('open');
        toggle.classList.remove('open');
    } else {
        content.classList.add('open');
        toggle.classList.add('open');
    }
}

function completeWorkingStatus() {
    if (!workingStatusDiv) return;

    const header = workingStatusDiv.querySelector('.working-header');
    header.innerHTML = `
        <span class="working-node"></span>
        <div class="working-title">Research complete</div>
    `;
}

function setStatus(active) {
    document.getElementById('statusBadge').classList.toggle('active', active);
    document.getElementById('statusBadge').lastChild.textContent = active ? 'Researching' : 'Ready';
}

function setTopic(topic) {
    document.getElementById('researchInput').value = topic;
    document.getElementById('researchInput').focus();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function questionDetails(index, questionText, status) {
    return `<div><strong>Question ${index}</strong> — ${escapeHtml(questionText || '')}</div><div>${status}</div>`;
}

function showReport(markdown) {
    lastReportMarkdown = markdown;
    addMessage(markdown, 'assistant');

    const messagesDiv = document.getElementById('chatMessages');
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'action-buttons';
    actionsDiv.innerHTML = `
        <button class="action-btn" onclick="copyReport(this)">Copy report</button>
        <button class="action-btn" onclick="newResearch()">New research</button>
    `;
    messagesDiv.appendChild(actionsDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}


function handleResearchEvent(event, questionText) {
    if (event.type === 'stage' && event.key === 'questions') {
        if (event.status === 'start') {
            updateProgressStepByKey('init', null, true);
            addProgressStep('Generating research questions', '', 'Asking the model what to investigate…', false, 'questions');
        } else {
            const questions = event.questions || [];
            updateProgressStepByKey('questions', `Generated ${questions.length} questions`, true);
            questions.forEach((question, idx) => {
                const index = idx + 1;
                questionText[index] = question;
                addProgressStep(`Question ${index}`, '', questionDetails(index, question, 'Queued…'), false, `q-${index}`);
            });
        }
    } else if (event.type === 'question') {
        const index = event.index;
        if (event.question) questionText[index] = event.question;

        if (event.status === 'searching') {
            updateProgressStepByKey(`q-${index}`, questionDetails(index, questionText[index], 'Searching the web…'), false, 'Searching');
        } else if (event.status === 'answering') {
            updateProgressStepByKey(`q-${index}`, questionDetails(index, questionText[index], `Writing answer from ${event.sources} sources…`), false, 'Answering');
        } else if (event.status === 'done') {
            let summary;
            if (!event.found) {
                summary = 'Answered without sources — the search returned nothing';
            } else if (!event.sources) {
                summary = `Answered from ${event.found} sources, but cited none`;
            } else {
                summary = `Answered, citing ${event.sources} of ${event.found} sources`;
            }
            updateProgressStepByKey(`q-${index}`, questionDetails(index, questionText[index], summary), true);
        } else if (event.status === 'error') {
            updateProgressStepByKey(`q-${index}`, questionDetails(index, questionText[index], `Failed: ${escapeHtml(event.message)}`), true, 'Failed');
        }
    } else if (event.type === 'stage' && event.key === 'report') {
        addProgressStep('Writing report', '', 'Combining every answer into the final report…', false, 'report');
    } else if (event.type === 'done') {
        updateProgressStepByKey('report', 'Report complete', true);
        completeWorkingStatus();
        showReport(event.report);
    } else if (event.type === 'error') {
        if (workingStatusDiv) workingStatusDiv.remove();
        addMessage(`**Research failed.** ${event.message}`, 'assistant');
    }
}

async function startResearch() {
    const input = document.getElementById('researchInput');
    const topic = input.value.trim();

    if (!topic || isResearching) return;

    isResearching = true;
    document.getElementById('sendBtn').disabled = true;
    document.getElementById('sendBtn').textContent = 'Researching';
    setStatus(true);

    addMessage(topic, 'user');
    input.value = '';

    showWorkingStatus();
    addProgressStep('Initializing agents', '', 'Starting research on: ' + escapeHtml(topic), false, 'init');

    const questionText = {};

    try {
        const response = await fetch('/start_research', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });

        if (!(response.headers.get('content-type') || '').includes('text/event-stream')) {
            const data = await response.json();
            throw new Error(data.message || 'Unexpected response from server');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });


            const frames = buffer.split('\n\n');
            buffer = frames.pop();

            for (const frame of frames) {
                const line = frame.trim();
                if (!line.startsWith('data:')) continue;
                handleResearchEvent(JSON.parse(line.slice(5).trim()), questionText);
            }
        }
    } catch (error) {
        if (workingStatusDiv) workingStatusDiv.remove();
        addMessage(`**Research failed.** ${error.message}`, 'assistant');
    } finally {
        isResearching = false;
        document.getElementById('sendBtn').disabled = false;
        document.getElementById('sendBtn').textContent = 'Research';
        setStatus(false);
        input.focus();
    }
}

function copyReport(btn) {

    if (!lastReportMarkdown) return;
    navigator.clipboard.writeText(lastReportMarkdown);
    if (btn) {
        btn.textContent = 'Copied';
        setTimeout(() => { btn.textContent = 'Copy report'; }, 2000);
    }
}

function newResearch() {
    document.getElementById('researchInput').focus();
}

// Enter key to submit
document.getElementById('researchInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !isResearching) {
        startResearch();
    }
});
