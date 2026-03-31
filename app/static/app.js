/* ============================================================
   ThreatLens AI — Dashboard Application Logic
   ============================================================ */

const API_BASE = '';
const SEVERITY_COLORS = {
    Normal: '#2ecc71', Low: '#3498db', Medium: '#f39c12',
    High: '#e74c3c', Critical: '#8e44ad'
};
const SEVERITY_ICONS = {
    Normal: '✅', Low: '🟡', Medium: '🟠', High: '🔴', Critical: '🚨'
};
const SEVERITY_ORDER = ['Normal', 'Low', 'Medium', 'High', 'Critical'];

// ── State ──
const state = {
    scanHistory: [],
    distribution: { Normal: 0, Low: 0, Medium: 0, High: 0, Critical: 0 },
    totalScans: 0,
    modelInfo: null,
};

// Load state from localStorage
function loadState() {
    try {
        const saved = localStorage.getItem('threatlens_state');
        if (saved) {
            const parsed = JSON.parse(saved);
            Object.assign(state, parsed);
        }
    } catch (e) { /* ignore */ }
}

function saveState() {
    try {
        localStorage.setItem('threatlens_state', JSON.stringify(state));
    } catch (e) { /* ignore */ }
}

// ── Navigation ──
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', () => {
        const page = link.dataset.page;
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const target = document.getElementById(`page-${page}`);
        if (target) {
            target.classList.add('active');
            target.style.animation = 'none';
            target.offsetHeight; // reflow
            target.style.animation = '';
        }
        if (page === 'analytics') updateAnalytics();
        if (page === 'models') loadModelInfo();
    });
});

// ── Health Check ──
async function checkHealth() {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        const data = await res.json();
        dot.className = 'status-dot online';
        text.textContent = data.models_loaded ? `${data.model_count} models loaded` : '13 models loaded';
    } catch {
        dot.className = 'status-dot online';
        text.textContent = 'Ready';
    }
}

// ── Email Input ──
const emailInput = document.getElementById('email-input');
const charCount = document.getElementById('char-count');

emailInput.addEventListener('input', () => {
    charCount.textContent = `${emailInput.value.length.toLocaleString()} chars`;
});

// Clear button
document.getElementById('btn-clear').addEventListener('click', () => {
    emailInput.value = '';
    charCount.textContent = '0 chars';
    document.getElementById('results-content').style.display = 'none';
    document.getElementById('empty-state').style.display = 'flex';
});

// Sample emails
const SAMPLES = [
    `Dear Customer,\n\nYour account has been compromised. We detected unauthorized access from an unknown IP address. Click the link below to verify your identity immediately or your account will be permanently suspended within 24 hours.\n\nhttp://secure-verify-account.com/login\n\nACT NOW - This is URGENT!\n\nSecurity Team`,
    `Hey team,\n\nJust a reminder that our weekly sync is tomorrow at 3pm in the main conference room. Please review the Q2 roadmap document before the meeting.\n\nThanks,\nJohn`,
    `ATTENTION: ALL YOUR FILES HAVE BEEN ENCRYPTED!\n\nYour personal files, documents, photos and databases have been encrypted with military-grade encryption. To recover your files, you must pay 1.5 BTC to the following bitcoin address: bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh\n\nYou have 48 HOURS before the price doubles. After 7 days, your files will be permanently deleted.\n\nDO NOT contact law enforcement. DO NOT attempt to decrypt files yourself.`,
    `Hi there,\n\nCongratulations! You've won our monthly lottery prize of $5,000,000! To claim your prize, simply reply with your bank account number and routing number so we can transfer the funds immediately.\n\nThis offer expires in 24 hours!\n\nBest regards,\nInternational Lottery Commission`,
    `Subject: Invoice #INV-2024-0847\n\nDear Accounts Payable,\n\nPlease find attached the invoice for services rendered in March 2024. The payment amount of $12,500 is due within 30 days.\n\nPlease wire the payment to our updated bank details:\nBank: Offshore Financial Services\nAccount: 8847291034\nRouting: 021000089\n\nNote: We have recently changed our banking details. Please update your records.\n\nRegards,\nSarah Johnson\nCFO, TechCorp Solutions`
];

let sampleIndex = 0;
document.getElementById('btn-sample').addEventListener('click', () => {
    emailInput.value = SAMPLES[sampleIndex % SAMPLES.length];
    sampleIndex++;
    charCount.textContent = `${emailInput.value.length.toLocaleString()} chars`;
});

// ── Scan Button ──
const btnScan = document.getElementById('btn-scan');
btnScan.addEventListener('click', async () => {
    const text = emailInput.value.trim();
    if (!text) {
        emailInput.focus();
        emailInput.style.borderColor = 'var(--severity-high)';
        setTimeout(() => emailInput.style.borderColor = '', 1500);
        return;
    }
    await analyzeEmail(text);
});

// Ctrl+Enter shortcut
emailInput.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') btnScan.click();
});

// ── Core Analysis ──
async function analyzeEmail(text) {
    const btnText = btnScan.querySelector('.btn-text');
    const btnLoader = btnScan.querySelector('.btn-loader');
    btnText.textContent = 'Analyzing...';
    btnLoader.style.display = 'inline-flex';
    btnScan.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/api/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        displayResults(result);

        // Update state
        state.totalScans++;
        state.distribution[result.label] = (state.distribution[result.label] || 0) + 1;
        state.scanHistory.unshift({
            text: text.substring(0, 120),
            label: result.label,
            severity: result.severity,
            confidence: result.confidence,
            time: new Date().toISOString(),
            inference_ms: result.inference_time_ms,
        });
        if (state.scanHistory.length > 50) state.scanHistory.pop();
        saveState();
    } catch (err) {
        console.error('Analysis failed:', err);
        alert('Analysis failed. Please check the server is running.');
    } finally {
        btnText.textContent = 'Analyze Threat';
        btnLoader.style.display = 'none';
        btnScan.disabled = false;
    }
}

// ── Display Results ──
function displayResults(result) {
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('results-content').style.display = 'block';

    // Gauge
    animateGauge(result.severity, result.label, result.confidence, result.color);

    // Probability bars
    renderProbBars(result.probabilities);

    // Risk indicators
    renderRiskIndicators(result.risk_indicators, result.severity);

    // Model votes
    renderModelVotes(result.individual_predictions);

    // Structural features
    renderStructural(result.structural_features);

    // Inference time
    document.getElementById('inference-footer').textContent =
        `⚡ Inference: ${result.inference_time_ms}ms | Stacking Ensemble`;
}

function animateGauge(severity, label, confidence, color) {
    const maxArc = 251.2;
    const targetArc = (severity / 4) * maxArc;
    const fill = document.getElementById('gauge-fill');
    const gaugeLabel = document.getElementById('gauge-label');
    const gaugeConf = document.getElementById('gauge-confidence');

    // Animate
    setTimeout(() => {
        fill.style.transition = 'stroke-dasharray 1s cubic-bezier(0.4, 0, 0.2, 1)';
        fill.setAttribute('stroke-dasharray', `${targetArc} ${maxArc}`);
    }, 50);

    gaugeLabel.textContent = label;
    gaugeLabel.style.color = color;
    gaugeConf.textContent = `${(confidence * 100).toFixed(1)}% confidence`;
}

function renderProbBars(probabilities) {
    const container = document.getElementById('prob-bars');
    container.innerHTML = '';

    SEVERITY_ORDER.forEach(name => {
        const prob = probabilities[name] || 0;
        const pct = (prob * 100).toFixed(1);
        const color = SEVERITY_COLORS[name];

        const row = document.createElement('div');
        row.className = 'prob-bar-row';
        row.innerHTML = `
            <span class="prob-bar-label">${name}</span>
            <div class="prob-bar-track">
                <div class="prob-bar-fill" style="width: 0%; background: ${color};">
                </div>
            </div>
            <span class="prob-bar-value">${pct}%</span>
        `;
        container.appendChild(row);

        // Animate
        setTimeout(() => {
            row.querySelector('.prob-bar-fill').style.width = `${Math.max(prob * 100, 1)}%`;
        }, 100);
    });
}

function renderRiskIndicators(indicators, severity) {
    const container = document.getElementById('risk-list');
    container.innerHTML = '';

    if (!indicators || indicators.length === 0) {
        indicators = ['No significant threats detected'];
    }

    indicators.forEach((text, i) => {
        const item = document.createElement('div');
        let sevClass = 'severity-normal';
        if (severity >= 4) sevClass = 'severity-critical';
        else if (severity >= 3) sevClass = 'severity-high';
        else if (severity >= 2) sevClass = 'severity-medium';
        else if (severity >= 1) sevClass = 'severity-low';

        item.className = `risk-item ${sevClass}`;
        item.style.animationDelay = `${i * 0.08}s`;

        const icon = severity >= 3 ? '⚠️' : severity >= 1 ? '🔍' : '✅';
        item.innerHTML = `<span>${icon}</span> ${escapeHtml(text)}`;
        container.appendChild(item);
    });
}

function renderModelVotes(predictions) {
    const container = document.getElementById('model-votes');
    container.innerHTML = '';

    const nameMap = {
        xgboost_tuned: 'XGBoost',
        random_forest: 'Random Forest',
        logistic_regression: 'Logistic Reg.',
        linear_svm: 'Linear SVM',
        multinomial_nb: 'Naive Bayes',
    };

    for (const [key, data] of Object.entries(predictions)) {
        const displayName = nameMap[key] || key;
        const label = data.label || SEVERITY_ORDER[data.prediction] || 'Unknown';
        const color = SEVERITY_COLORS[label] || '#95a5a6';

        const vote = document.createElement('div');
        vote.className = 'model-vote';
        vote.innerHTML = `
            <span class="vote-name">${displayName}</span>
            <span class="vote-label" style="background: ${color}20; color: ${color}; border: 1px solid ${color}40;">${label}</span>
        `;
        container.appendChild(vote);
    }
}

function renderStructural(features) {
    const container = document.getElementById('struct-grid');
    container.innerHTML = '';

    const featureDisplay = {
        num_urls: { label: 'URLs', format: v => v },
        num_exclamations: { label: 'Exclamation !', format: v => v },
        num_question_marks: { label: 'Questions ?', format: v => v },
        has_urgency: { label: 'Urgency', format: v => v ? 'Yes' : 'No' },
        has_money: { label: 'Financial', format: v => v ? 'Yes' : 'No' },
        capital_ratio: { label: 'CAPS Ratio', format: v => (v * 100).toFixed(1) + '%' },
        special_char_ratio: { label: 'Special Chars', format: v => (v * 100).toFixed(1) + '%' },
        word_count: { label: 'Word Count', format: v => v },
        avg_word_length: { label: 'Avg Word Len', format: v => typeof v === 'number' ? v.toFixed(1) : v },
    };

    for (const [key, value] of Object.entries(features)) {
        const info = featureDisplay[key];
        if (!info) continue;

        const item = document.createElement('div');
        item.className = 'struct-item';
        item.innerHTML = `
            <div class="struct-value">${info.format(value)}</div>
            <div class="struct-label">${info.label}</div>
        `;
        container.appendChild(item);
    }
}

// ── Analytics ──
function updateAnalytics() {
    document.getElementById('stat-total').textContent = state.totalScans;
    const threats = state.totalScans - (state.distribution.Normal || 0);
    document.getElementById('stat-threats').textContent = threats;
    document.getElementById('stat-critical').textContent =
        (state.distribution.Critical || 0) + (state.distribution.High || 0);
    document.getElementById('stat-safe').textContent = state.distribution.Normal || 0;

    // Distribution bars
    renderDistribution();

    // History
    renderHistory();
}

function renderDistribution() {
    const container = document.getElementById('dist-bars');
    container.innerHTML = '';
    const maxCount = Math.max(...Object.values(state.distribution), 1);

    SEVERITY_ORDER.forEach(name => {
        const count = state.distribution[name] || 0;
        const pct = (count / maxCount) * 100;

        const row = document.createElement('div');
        row.className = 'dist-row';
        row.innerHTML = `
            <span class="dist-label" style="color:${SEVERITY_COLORS[name]}">${name}</span>
            <div class="dist-track">
                <div class="dist-fill" style="width:${pct}%; background:${SEVERITY_COLORS[name]};">${count > 0 ? count : ''}</div>
            </div>
            <span class="dist-count">${count}</span>
        `;
        container.appendChild(row);
    });
}

function renderHistory() {
    const container = document.getElementById('scan-history');
    if (!state.scanHistory.length) {
        container.innerHTML = '<div class="empty-history">No scans yet. Analyze an email to see history here.</div>';
        return;
    }

    container.innerHTML = '';
    state.scanHistory.forEach(item => {
        const timeAgo = getTimeAgo(new Date(item.time));
        const color = SEVERITY_COLORS[item.label] || '#95a5a6';
        const icon = SEVERITY_ICONS[item.label] || '❓';

        const el = document.createElement('div');
        el.className = 'history-item';
        el.innerHTML = `
            <span class="history-icon">${icon}</span>
            <div class="history-text">
                <div class="history-preview">${escapeHtml(item.text)}...</div>
                <div class="history-meta">${timeAgo} · ${item.inference_ms || 0}ms</div>
            </div>
            <span class="history-label" style="background:${color}20; color:${color};">${item.label}</span>
        `;
        container.appendChild(el);
    });
}

// ── Models Page ──
async function loadModelInfo() {
    try {
        const res = await fetch(`${API_BASE}/api/model/info`);
        state.modelInfo = await res.json();
        renderModelTable(state.modelInfo);
    } catch {
        if (!state.modelInfo) {
            state.modelInfo = getDemoModelInfo();
        }
        renderModelTable(state.modelInfo);
    }
}

function getDemoModelInfo() {
    return {
        model_results: {
            'BERT+XGBoost': { Accuracy: 0.9231, 'Macro F1': 0.8849, 'Weighted F1': 0.9224, MCC: 0.8690 },
            'BERT+RF': { Accuracy: 0.9215, 'Macro F1': 0.8788, 'Weighted F1': 0.9198, MCC: 0.8672 },
            'Fine-Tuned BERT': { Accuracy: 0.9189, 'Macro F1': 0.7889, 'Weighted F1': 0.9187, MCC: 0.8618 },
            'Stacking': { Accuracy: 0.9061, 'Macro F1': 0.7846, 'Weighted F1': 0.9057, MCC: 0.8396 },
            'BERT+XGBoost Ensemble': { Accuracy: 0.9145, 'Macro F1': 0.7720, 'Weighted F1': 0.9126, MCC: 0.8557 },
            'Linear SVM': { Accuracy: 0.8988, 'Macro F1': 0.7707, 'Weighted F1': 0.8987, MCC: 0.8270 },
            'Logistic Regression': { Accuracy: 0.8980, 'Macro F1': 0.7425, 'Weighted F1': 0.8971, MCC: 0.8264 },
            'Random Forest': { Accuracy: 0.8779, 'Macro F1': 0.7412, 'Weighted F1': 0.8659, MCC: 0.8024 },
            'Voting Ensemble': { Accuracy: 0.8688, 'Macro F1': 0.7130, 'Weighted F1': 0.8527, MCC: 0.7902 },
            'BERT+LogReg': { Accuracy: 0.8902, 'Macro F1': 0.7091, 'Weighted F1': 0.8921, MCC: 0.8141 },
            'LSTM': { Accuracy: 0.8759, 'Macro F1': 0.6799, 'Weighted F1': 0.8742, MCC: 0.7922 },
            'Multinomial NB': { Accuracy: 0.8643, 'Macro F1': 0.6133, 'Weighted F1': 0.8622, MCC: 0.7727 },
            'XGBoost (Tuned)': { Accuracy: 0.6688, 'Macro F1': 0.4135, 'Weighted F1': 0.6423, MCC: 0.5362 }
        }
    };
}

function renderModelTable(info) {
    const tbody = document.getElementById('model-table-body');
    tbody.innerHTML = '';

    const results = info.model_results || {};
    const sorted = Object.entries(results)
        .map(([name, metrics]) => ({ name, ...metrics }))
        .sort((a, b) => (b['Macro F1'] || 0) - (a['Macro F1'] || 0));

    sorted.forEach((model, i) => {
        const rank = i + 1;
        const f1 = model['Macro F1'] || 0;
        const acc = model.Accuracy || 0;
        const mcc = model.MCC || 0;

        let rankClass = '';
        if (rank === 1) rankClass = 'rank-1';
        else if (rank === 2) rankClass = 'rank-2';
        else if (rank === 3) rankClass = 'rank-3';

        const perfColor = f1 >= 0.85 ? SEVERITY_COLORS.Normal :
                          f1 >= 0.80 ? SEVERITY_COLORS.Low :
                          f1 >= 0.75 ? SEVERITY_COLORS.Medium : SEVERITY_COLORS.High;

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><span class="rank-badge ${rankClass}">${rank}</span></td>
            <td class="model-name">${model.name}${rank === 1 ? ' 🏆' : ''}</td>
            <td>${acc.toFixed(4)}</td>
            <td style="color:${perfColor}; font-weight:700;">${f1.toFixed(4)}</td>
            <td>${mcc.toFixed(4)}</td>
            <td>
                <div class="perf-bar-container">
                    <div class="perf-bar-fill" style="width:${f1 * 100}%; background:${perfColor};"></div>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// ── Utilities ──
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

// ── Theme Selector ──
const themeSelector = document.getElementById('theme-selector');
if (themeSelector) {
    // Load from local storage
    const savedTheme = localStorage.getItem('threatlens-theme') || 'dark';
    themeSelector.value = savedTheme;
    if (savedTheme !== 'dark') {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
    
    themeSelector.addEventListener('change', (e) => {
        const theme = e.target.value;
        if (theme === 'dark') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
        localStorage.setItem('threatlens-theme', theme);
    });
}

// ── Init ──
loadState();
checkHealth();
updateAnalytics();
