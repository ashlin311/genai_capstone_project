/**
 * PrepAI - Frontend Application Logic
 * Pure JavaScript, handles API integrations, UI state, and document generation.
 */

// --- Global App State ---
const state = {
    currentTab: 'dashboard',
    isConnected: false,
    isVectorStoreLoaded: false,
    lastExtractedGuide: '',
    lastExtractedMeta: null
};

// --- Initial Setup & Lifecycle ---
document.addEventListener('DOMContentLoaded', () => {
    // Restore Saved Theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    document.getElementById('theme-toggle-btn').innerText = savedTheme === 'dark' ? '☀️' : '🌙';

    // Start Backend Health Polling
    pollSystemStatus();
    setInterval(pollSystemStatus, 8000);

    // Setup drag-and-drop event preventions
    const dropZone = document.getElementById('drop-zone-element');
    if (dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });
    }
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

// --- Theme Management ---
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    const themeBtn = document.getElementById('theme-toggle-btn');
    themeBtn.innerText = newTheme === 'dark' ? '☀️' : '🌙';
    showToast(`Switched to ${newTheme} theme`, 'success');
}

// --- Navigation Tabs ---
function switchTab(tabId) {
    if (tabId === state.currentTab) return;

    // Toggle Tab Panels
    document.querySelectorAll('.tab-view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`view-${tabId}`).classList.add('active');

    // Toggle Nav Buttons
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('active');
    });
    
    let btnId = `nav-btn-${tabId}`;
    if (tabId === 'chat') btnId = 'nav-btn-chat';
    else if (tabId === 'planner') btnId = 'nav-btn-planner';
    else btnId = 'nav-btn-dashboard';
    
    document.getElementById(btnId).classList.add('active');

    // Update Header Text
    const titleMap = {
        'dashboard': 'Dashboard Overview',
        'chat': 'RAG Preparation Chatbot',
        'planner': 'Job Description Prep Planner'
    };
    document.getElementById('current-view-title').innerText = titleMap[tabId] || 'Placement Assistant';
    
    state.currentTab = tabId;
}

// --- System Status Monitoring ---
async function pollSystemStatus() {
    try {
        const response = await fetch('/health', {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });
        
        if (!response.ok) {
            throw new Error(`Server returned code ${response.status}`);
        }

        const data = await response.json();
        
        // Update Connection Status
        updateIndicator('backend', 'green', 'Online');
        state.isConnected = true;

        // Update Vectorstore Status
        if (data.vectorstore_loaded) {
            updateIndicator('vector', 'green', 'Loaded');
            state.isVectorStoreLoaded = true;
        } else {
            updateIndicator('vector', 'orange', 'Unloaded');
            state.isVectorStoreLoaded = false;
        }
    } catch (err) {
        console.warn('Status check failed:', err);
        updateIndicator('backend', 'red', 'Offline');
        updateIndicator('vector', 'red', 'Unavailable');
        state.isConnected = false;
        state.isVectorStoreLoaded = false;
    }
}

function updateIndicator(prefix, color, text) {
    const dot = document.getElementById(`${prefix}-status-dot`);
    const val = document.getElementById(`${prefix}-status-text`);
    if (dot && val) {
        dot.className = `status-dot ${color}`;
        val.innerText = text;
    }
}

// --- Quick Presets & Suggestion Chips ---
function injectPresetQuery(queryText) {
    switchTab('chat');
    const input = document.getElementById('chat-input-text');
    if (input) {
        input.value = queryText;
        input.focus();
    }
}

// --- RAG Chatbot Integration ---
async function handleChatSubmit(e) {
    e.preventDefault();
    
    const inputElement = document.getElementById('chat-input-text');
    const query = inputElement.value.trim();
    if (!query) return;

    if (!state.isConnected) {
        showToast('Cannot send message: Server is offline', 'error');
        return;
    }

    if (!state.isVectorStoreLoaded) {
        showToast('Warning: RAG Vector Store is not loaded. Generating answer might fail.', 'warning');
    }

    // Append User Message bubble
    appendChatMessage('user', query);
    inputElement.value = '';

    // Append Typing Indicator
    const typingIndicatorId = appendTypingIndicator();
    scrollToBottom('chat-messages-box');

    // Build the request payload, adding JD context if available in state
    const payload = { query: query };
    if (state.lastExtractedMeta && state.lastExtractedMeta.raw_text) {
        payload.jd_context = state.lastExtractedMeta.raw_text;
    }

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        // Remove Typing Indicator
        removeChatMessage(typingIndicatorId);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const errMsg = errData.detail || `Server returned error ${response.status}`;
            appendChatMessage('system', `⚠️ **Error processing query:** ${errMsg}`);
            showToast('Chat query failed', 'error');
            return;
        }

        const data = await response.json();
        appendChatMessage('system', data.answer, data.sources);
    } catch (err) {
        console.error('Chat error:', err);
        removeChatMessage(typingIndicatorId);
        appendChatMessage('system', '⚠️ **Network connection error.** Please verify the FastAPI backend is running.');
        showToast('Connection failed', 'error');
    }
    
    scrollToBottom('chat-messages-box');
}

function appendChatMessage(sender, content, sources = []) {
    const chatBox = document.getElementById('chat-messages-box');
    const msgId = 'msg-' + Date.now() + '-' + Math.floor(Math.random() * 1000);
    
    const messageDiv = document.createElement('div');
    messageDiv.id = msgId;
    messageDiv.className = `message ${sender}-msg`;
    
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerText = sender === 'user' ? '👤' : '🤖';
    
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    
    // Parse formatting into HTML
    bubble.innerHTML = formatMarkdown(content);
    
    // Append sources if available
    if (sources && sources.length > 0) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'msg-sources-list';
        sourcesDiv.innerHTML = '<span class="status-title" style="font-size: 10px; display: block; margin-bottom: 2px;">Sources:</span>';
        
        sources.forEach(src => {
            const badge = document.createElement('span');
            badge.className = 'source-badge';
            badge.innerText = src;
            sourcesDiv.appendChild(badge);
        });
        bubble.appendChild(sourcesDiv);
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    chatBox.appendChild(messageDiv);
    
    return msgId;
}

function appendTypingIndicator() {
    const chatBox = document.getElementById('chat-messages-box');
    const msgId = 'msg-typing-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.id = msgId;
    messageDiv.className = 'message system-msg';
    
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerText = '🤖';
    
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    
    bubble.appendChild(indicator);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    chatBox.appendChild(messageDiv);
    
    return msgId;
}

function removeChatMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function clearChatHistory() {
    const chatBox = document.getElementById('chat-messages-box');
    chatBox.innerHTML = `
        <div class="message system-msg">
            <div class="msg-avatar">🤖</div>
            <div class="msg-bubble">
                <p>Hello! I am your placement preparation assistant. I can answer questions about placements using our curated knowledge base. What would you like to prepare for today?</p>
            </div>
        </div>
    `;
    showToast('Chat history cleared', 'success');
}

// --- JD Prep Planner Integration ---
function triggerFileInput() {
    document.getElementById('jd-file-input').click();
}

function handleDragOver(e) {
    const dropZone = document.getElementById('jd-upload-card');
    dropZone.classList.add('drag-over');
}

function handleDragLeave(e) {
    const dropZone = document.getElementById('jd-upload-card');
    dropZone.classList.remove('drag-over');
}

function handleDrop(e) {
    const dropZone = document.getElementById('jd-upload-card');
    dropZone.classList.remove('drag-over');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        processUploadedJDFile(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        processUploadedJDFile(files[0]);
    }
}

async function processUploadedJDFile(file) {
    // Valdation
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast('Invalid file format. Please upload a PDF.', 'error');
        return;
    }
    
    if (file.size > 10 * 1024 * 1024) { // 10MB limit
        showToast('File is too large. Max limit is 10MB.', 'error');
        return;
    }

    if (!state.isConnected) {
        showToast('Cannot upload: Server is offline', 'error');
        return;
    }

    if (!state.isVectorStoreLoaded) {
        showToast('Warning: RAG vector store is unloaded. Prep guide cannot fetch matching resources.', 'warning');
    }

    // Toggle panels to show loading screen
    document.getElementById('jd-upload-card').classList.add('hidden');
    document.getElementById('jd-loading-card').classList.remove('hidden');
    document.getElementById('jd-progress-bar').style.animationPlayState = 'running';
    
    const loadingText = document.getElementById('loading-state-text');
    loadingText.innerText = "Extracting PDF and Parsing Skills...";

    const formData = new FormData();
    formData.append('file', file);

    try {
        loadingText.innerText = "Querying RAG Knowledge base & generating Study Guide...";
        
        const response = await fetch('/prepare', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server error code ${response.status}`);
        }

        const data = await response.json();
        
        // Save to global state
        state.lastExtractedGuide = data.answer;
        state.lastExtractedMeta = {
            company: data.company,
            role: data.role,
            required_skills: data.required_skills,
            preferred_skills: data.preferred_skills,
            keywords: data.keywords,
            search_query: data.search_query,
            sources: data.sources,
            raw_text: data.raw_text
        };

        // Render Results
        renderJDResults(data);
        showToast('Placement preparation guide generated successfully!', 'success');

    } catch (err) {
        console.error('JD Pipeline processing failed:', err);
        showToast(`Pipeline failed: ${err.message}`, 'error');
        resetPlanner();
    }
}

function renderJDResults(data) {
    // Hide loading
    document.getElementById('jd-loading-card').classList.add('hidden');
    
    // Show results
    const resultsContainer = document.getElementById('jd-results-container');
    resultsContainer.classList.remove('hidden');

    // Render left panel (insights)
    document.getElementById('result-company-name').innerText = data.company || 'Unknown Company';
    document.getElementById('result-role-title').innerText = data.role || 'Job Description';
    
    renderSkillsTags('result-required-skills', data.required_skills, 'No critical skills parsed');
    renderSkillsTags('result-preferred-skills', data.preferred_skills, 'No preferred skills parsed');
    renderSkillsTags('result-keywords', data.keywords, 'No soft-skills keywords parsed');
    
    document.getElementById('result-search-query').innerText = data.search_query || '';

    // Render right panel (ai guide)
    const guideBox = document.getElementById('result-ai-guide');
    guideBox.innerHTML = formatMarkdown(data.answer);

    // Render sources
    const sourcesBox = document.getElementById('result-guide-sources');
    sourcesBox.innerHTML = '';
    if (data.sources && data.sources.length > 0) {
        data.sources.forEach(src => {
            const badge = document.createElement('span');
            badge.className = 'source-badge';
            badge.innerText = src;
            sourcesBox.appendChild(badge);
        });
    } else {
        sourcesBox.innerHTML = '<span class="status-val" style="color: var(--text-muted)">No sources matched. General knowledge used.</span>';
    }
}

function renderSkillsTags(elementId, list, fallbackText) {
    const container = document.getElementById(elementId);
    container.innerHTML = '';
    
    if (list && list.length > 0) {
        list.forEach(skill => {
            const span = document.createElement('span');
            span.className = 'skill-tag';
            span.innerText = skill;
            container.appendChild(span);
        });
    } else {
        container.innerHTML = `<span style="font-size: 12px; color: var(--text-muted); font-style: italic;">${fallbackText}</span>`;
    }
}

function resetPlanner() {
    // Reset file input
    document.getElementById('jd-file-input').value = '';
    
    // Toggle Panels
    document.getElementById('jd-results-container').classList.add('hidden');
    document.getElementById('jd-loading-card').classList.add('hidden');
    document.getElementById('jd-upload-card').classList.remove('hidden');
    
    // Reset state variables
    state.lastExtractedGuide = '';
    state.lastExtractedMeta = null;
}

// --- Clipboard & Document Exporting ---
function copyPrepGuide() {
    if (!state.lastExtractedGuide) {
        showToast('No content to copy!', 'warning');
        return;
    }
    
    navigator.clipboard.writeText(state.lastExtractedGuide)
        .then(() => {
            showToast('Study guide copied to clipboard!', 'success');
        })
        .catch(err => {
            console.error('Failed to copy: ', err);
            showToast('Failed to copy to clipboard', 'error');
        });
}

function downloadPrepGuide() {
    if (!state.lastExtractedGuide || !state.lastExtractedMeta) {
        showToast('No report to download!', 'warning');
        return;
    }

    const meta = state.lastExtractedMeta;
    const guideHtml = formatMarkdown(state.lastExtractedGuide);
    
    const requiredSkillsHtml = meta.required_skills.map(s => `<li>${s}</li>`).join('') || '<li>None parsed</li>';
    const preferredSkillsHtml = meta.preferred_skills.map(s => `<li>${s}</li>`).join('') || '<li>None parsed</li>';
    const keywordsHtml = meta.keywords.map(s => `<li>${s}</li>`).join('') || '<li>None parsed</li>';
    const sourcesHtml = meta.sources.map(s => `<li>${s}</li>`).join('') || '<li>No matching data files</li>';

    // Build standalone HTML report document with clean styles
    const fullDocumentHtml = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Placement Prep Report: ${meta.company} - ${meta.role}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 40px auto; padding: 0 20px; }
        h1 { border-bottom: 2px solid #6366f1; padding-bottom: 12px; color: #1e1b4b; font-size: 28px; }
        h2 { color: #4338ca; margin-top: 30px; border-bottom: 1px solid #e0e7ff; padding-bottom: 6px; }
        h3 { color: #4f46e5; margin-top: 20px; }
        .meta-container { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 30px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .meta-column h4 { margin: 0 0 10px 0; color: #475569; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
        .meta-column ul { margin: 0; padding-left: 20px; }
        .prep-guide-content { background: #ffffff; padding: 10px 0; }
        blockquote { border-left: 4px solid #6366f1; background: #f5f3ff; padding: 10px 20px; margin: 20px 0; border-radius: 0 8px 8px 0; }
        .sources-footer { background: #f1f5f9; padding: 15px 20px; border-radius: 8px; font-size: 13px; margin-top: 40px; }
        .sources-footer h4 { margin: 0 0 8px 0; color: #64748b; text-transform: uppercase; font-size: 11px; }
        .sources-footer ul { margin: 0; padding-left: 20px; }
        .footer-stamp { text-align: center; font-size: 11px; color: #94a3b8; margin-top: 60px; border-top: 1px solid #e2e8f0; padding-top: 12px; }
    </style>
</head>
<body>
    <h1>Placement Prep Report: ${meta.company}</h1>
    <div style="font-size: 16px; font-weight: bold; color: #6366f1; margin-top: -10px; margin-bottom: 24px;">Role: ${meta.role}</div>

    <div class="meta-container">
        <div class="meta-column">
            <h4>Required Skills</h4>
            <ul>${requiredSkillsHtml}</ul>
        </div>
        <div class="meta-column">
            <h4>Preferred & Keywords</h4>
            <ul>
                ${preferredSkillsHtml}
                ${keywordsHtml}
            </ul>
        </div>
    </div>

    <h2>Preparation & Study Guide</h2>
    <div class="prep-guide-content">
        ${guideHtml}
    </div>

    <div class="sources-footer">
        <h4>Retrieved Experience Databases</h4>
        <ul>${sourcesHtml}</ul>
    </div>

    <div class="footer-stamp">
        Generated by PrepAI - Placement Preparation AI Assistant on ${new Date().toLocaleDateString()}
    </div>
</body>
</html>`;

    // Download flow using Blob
    const blob = new Blob([fullDocumentHtml], { type: 'text/html' });
    const link = document.createElement('a');
    const filename = `${meta.company.replace(/[^a-z0-9]/gi, '_')}_${meta.role.replace(/[^a-z0-9]/gi, '_')}_prep_guide.html`.toLowerCase();
    
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast('Report downloaded successfully!', 'success');
}

// --- Helper Functions ---

// Simple, fast client-side markdown formatter for study guides
function formatMarkdown(markdown) {
    if (!markdown) return '';
    
    let html = markdown;

    // Escaping HTML tag symbols to prevent markup injection
    html = html
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Headings
    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');

    // Blockquotes
    html = html.replace(/^&gt;\s(.*?)$/gm, '<blockquote>$1</blockquote>');

    // Unordered lists (handling lines starting with *, -, or +)
    // First, bundle groups of list items
    html = html.replace(/^[\*\-\+]\s+(.*?)$/gm, '<li>$1</li>');
    // Wrap consecutive list items in <ul>. Simple regex approach:
    html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
    // Remove nested <ul> wraps if any (cleanup for split items)
    html = html.replace(/<\/ul>\s*<ul>/g, '');

    // Bold text (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Inline Code (`code`)
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');

    // Line breaks for loose text
    html = html.replace(/\n\n/g, '<p></p>');
    html = html.replace(/\n/g, '<br>');

    // Cleanup empty paragraphs
    html = html.replace(/<p><\/p>/g, '');

    return html;
}

function scrollToBottom(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.scrollTop = el.scrollHeight;
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-notifications-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const iconMap = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️'
    };
    
    toast.innerHTML = `<span class="toast-icon">${iconMap[type] || 'ℹ️'}</span> <span class="toast-text">${message}</span>`;
    container.appendChild(toast);

    // Fade out and remove
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.style.transition = 'all 0.5s ease';
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}
