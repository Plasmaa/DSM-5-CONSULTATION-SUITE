// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const sourcesList = document.getElementById('sources-list');
const sourceCount = document.getElementById('source-count');
const pineconeStatus = document.getElementById('pinecone-status');
const ollamaStatus = document.getElementById('ollama-status');
const statChunks = document.getElementById('stat-chunks');
const statModel = document.getElementById('stat-model');

// Dynamic API Base URL resolver (fallback to local backend if running on Vercel)
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? ''
    : 'http://localhost:8000';

// Chat State
let chatHistory = [];
let isGenerating = false;
let currentSources = [];

// Initialize Page
window.addEventListener('DOMContentLoaded', () => {
    checkSystemStatus();
    setupEventListeners();
});

// Setup Listeners
function setupEventListeners() {
    // Submit query
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        submitMessage();
    });

    // Enter key submits form, Shift+Enter makes newline
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Quick Inquiry Selectors
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (isGenerating) return;
            userInput.value = btn.dataset.query;
            userInput.focus();
            submitMessage();
        });
    });
}

// Fetch System Status
async function checkSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const data = await response.json();

        // Update Stats
        statChunks.textContent = data.sqlite_count || 0;

        // Update Pinecone Status Indicator
        if (data.pinecone_ready) {
            updateStatusDot(pineconeStatus, 'green', `Pinecone: Ready (${data.pinecone_vector_count} vectors)`);
        } else {
            updateStatusDot(pineconeStatus, 'red', 'Pinecone: Error/Offline');
        }

        // Update Ollama Status Indicator
        if (data.ollama_running) {
            const allModels = data.ollama_models || [];
            // Filter out embedding-only models
            const chatModels = allModels.filter(m => !m.includes('bge') && !m.includes('embed') && !m.includes('nomic'));

            // Look for qwen first, or fallback to any generative chat model
            const qwenModel = chatModels.find(m => m.toLowerCase().includes('qwen'));
            const chosenModel = qwenModel || (chatModels.length > 0 ? chatModels[0] : null);

            if (chosenModel) {
                updateStatusDot(ollamaStatus, 'green', `Ollama: Ready (${chosenModel})`);
                statModel.textContent = chosenModel;
            } else if (allModels.length > 0) {
                updateStatusDot(ollamaStatus, 'red', 'Ollama: No Chat Model (Only Embedding Models Found)');
                statModel.textContent = "qwen3:8b";
            } else {
                updateStatusDot(ollamaStatus, 'red', 'Ollama: Connected (No Models)');
                statModel.textContent = "No Models";
            }
        } else {
            updateStatusDot(ollamaStatus, 'red', 'Ollama: Offline');
            statModel.textContent = "Offline";
        }
    } catch (error) {
        console.error("Failed to check status:", error);
        updateStatusDot(pineconeStatus, 'red', 'System Offline');
        updateStatusDot(ollamaStatus, 'red', 'System Offline');
    }
}

function updateStatusDot(element, color, text) {
    const dot = element.querySelector('.status-dot');
    const label = element.querySelector('.status-label');

    dot.className = 'status-dot ' + color;
    label.textContent = text;
}

// Format markdown-like elements and bracketed citations
function formatContent(text) {
    if (!text) return "";

    let html = text;

    // Escape HTML tags to prevent injections
    html = html
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Replace double newlines with double breaks, single newlines with single break
    html = html.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');

    // Format bold markers (**text**)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Format bullet points starting with - or *
    html = html.replace(/(?:^|<br>)\s*-\s+([^<]+)/g, (match, p1) => {
        return `<br><span class="bullet-item">• ${p1}</span>`;
    });

    // Format bracketed citations e.g. [Attention-Deficit/Hyperactivity Disorder, 315.02, Page 60]
    // Matches [Disorder, Code, Page X]
    html = html.replace(/\[([^\]]+)\]/g, (match, p1) => {
        // Find if citation matches any of our active sources
        let idAttr = "";
        const parts = p1.toLowerCase();

        // Try to locate source index in currentSources to link it
        const matchedIndex = currentSources.findIndex(src => {
            const disorderClean = src.disorder_name.toLowerCase();
            return parts.includes(disorderClean) || disorderClean.includes(parts.split(',')[0].trim());
        });

        if (matchedIndex !== -1) {
            idAttr = `data-source-index="${matchedIndex}"`;
        }

        return `<span class="citation" ${idAttr} onclick="scrollToSourceCard(this)"><i class="fa-solid fa-file-waveform"></i> ${p1}</span>`;
    });

    return html;
}

// Click callback to scroll to right side card
window.scrollToSourceCard = function (element) {
    const idx = element.getAttribute('data-source-index');
    if (idx === null) return;

    const card = document.getElementById(`source-card-${idx}`);
    if (card) {
        // Expand card if collapsed
        card.classList.add('expanded');

        // Remove highlight from others
        document.querySelectorAll('.source-card').forEach(c => c.classList.remove('highlighted'));

        // Highlight and scroll into view
        card.classList.add('highlighted');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
};

// Handle Message Submission
async function submitMessage() {
    const text = userInput.value.trim();
    if (!text || isGenerating) return;

    isGenerating = true;
    userInput.value = "";
    userInput.disabled = true;
    sendButton.disabled = true;

    // Append User Message to UI
    appendMessage("user", "You", text);
    chatHistory.push({ role: "user", content: text });

    // Append Waiting Indicator
    const waitingId = appendWaitingIndicator();
    scrollToBottom();

    // Prepare API request
    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                messages: chatHistory,
                model: statModel.textContent || "qwen3:8b"
            })
        });

        if (!response.ok) {
            throw new Error(`Server responded with status ${response.status}`);
        }

        // Read Streaming Response
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        // Create bot message container placeholder
        removeWaitingIndicator(waitingId);
        const botMessageId = appendMessagePlaceholder("system", "Chief of Psychiatry");
        const botContentDiv = document.querySelector(`#${botMessageId} .message-content-text`);

        let botTextAccumulator = "";
        currentSources = [];

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop(); // Keep last partial chunk

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const dataStr = line.slice(6).trim();
                    if (!dataStr) continue;

                    try {
                        const event = JSON.parse(dataStr);
                        if (event.type === "sources") {
                            // Update sidebar sources
                            renderSources(event.sources);
                        } else if (event.type === "content") {
                            botTextAccumulator += event.delta;
                            botContentDiv.innerHTML = formatContent(botTextAccumulator);
                            scrollToBottom();
                        } else if (event.type === "error") {
                            botContentDiv.innerHTML += `<br><span style="color:var(--red-status)"><i class="fa-solid fa-triangle-exclamation"></i> Error: ${event.error}</span>`;
                        }
                    } catch (e) {
                        console.error("Error parsing stream line:", e, line);
                    }
                }
            }
        }

        // Finalize message history
        chatHistory.push({ role: "assistant", content: botTextAccumulator });

    } catch (error) {
        console.error("Chat error:", error);
        removeWaitingIndicator(waitingId);
        appendMessage("system", "System Diagnostics", `Error executing consultation: ${error.message}. Please verify local API keys and ensure Ollama model server is running.`, true);
    } finally {
        isGenerating = false;
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
        checkSystemStatus(); // Refresh status counts
    }
}

// Append a standard message bubble
function appendMessage(role, sender, text, isError = false) {
    const msgId = 'msg-' + Date.now();
    const isUser = role === "user";

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'system-message'}`;
    messageDiv.id = msgId;

    const avatarIcon = isUser ? 'fa-user' : (isError ? 'fa-triangle-exclamation' : 'fa-user-doctor');

    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fa-solid ${avatarIcon}"></i>
        </div>
        <div class="message-content">
            <h4>${sender}</h4>
            <div class="message-content-text">${formatContent(text)}</div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    return msgId;
}

// Append a placeholder bubble to stream into
function appendMessagePlaceholder(role, sender) {
    const msgId = 'msg-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system-message';
    messageDiv.id = msgId;

    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fa-solid fa-user-doctor"></i>
        </div>
        <div class="message-content">
            <h4>${sender}</h4>
            <div class="message-content-text"></div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    return msgId;
}

// Waiting dot wave
function appendWaitingIndicator() {
    const id = 'wait-' + Date.now();
    const indicatorDiv = document.createElement('div');
    indicatorDiv.className = 'waiting-indicator';
    indicatorDiv.id = id;
    indicatorDiv.innerHTML = `
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
    `;
    chatMessages.appendChild(indicatorDiv);
    return id;
}

function removeWaitingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// Scroll to bottom of Chat panel
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Render referenced sources on right sidebar
function renderSources(sources) {
    currentSources = sources;
    sourcesList.innerHTML = "";
    sourceCount.textContent = `${sources.length} Chunks`;

    if (sources.length === 0) {
        sourcesList.innerHTML = `
            <div class="sources-empty">
                <i class="fa-solid fa-receipt"></i>
                <p>No reference documents found for the last query.</p>
            </div>
        `;
        return;
    }

    sources.forEach((src, index) => {
        const card = document.createElement('div');
        card.className = 'source-card';
        card.id = `source-card-${index}`;

        // Calculate similarity percentage
        const similarityPct = Math.round(src.score * 100);

        card.innerHTML = `
            <div class="source-card-header">
                <div class="source-title">${src.disorder_name}</div>
                <div class="source-score">${similarityPct}% Match</div>
            </div>
            <div class="source-meta">
                <span><i class="fa-solid fa-barcode"></i> ${src.code || 'N/A'}</span>
                <span><i class="fa-solid fa-file-lines"></i> Page ${src.page_number}</span>
                <span><i class="fa-solid fa-folder"></i> ${src.section_type}</span>
            </div>
            <div class="source-snippet">${src.content}</div>
        `;

        // Toggle card expansion on click
        card.addEventListener('click', (e) => {
            // If text is selected, don't collapse/expand
            if (window.getSelection().toString()) return;
            card.classList.toggle('expanded');
        });

        sourcesList.appendChild(card);
    });
}
