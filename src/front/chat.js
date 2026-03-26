/**
 * 接口地址（相对路径）
 * 页面位于 /smart/edu/static/index.html，接口位于 /smart/edu/chat 和 /smart/edu/new-chat
 */
const API_URL      = '../chat';
const NEW_CHAT_URL = '../new-chat';

const messagesEl = document.getElementById('messages');
const inputEl    = document.getElementById('user-input');
const sendBtn    = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');

/** 是否正在等待 AI 响应（同一时刻只允许一条请求） */
let isLoading = false;

/* ============================================================
   工具函数
============================================================ */

/** 返回当前时间字符串 HH:MM */
const now = () => {
    const d = new Date();
    return d.getHours().toString().padStart(2, '0') + ':' +
        d.getMinutes().toString().padStart(2, '0');
};

/** 滚动消息列表到底部 */
const scrollBottom = () =>
    messagesEl.scrollTo({ top: messagesEl.scrollHeight, behavior: 'smooth' });

/**
 * 对用户输入进行 HTML 转义，防止 XSS
 * 同时将换行符转为 <br>
 */
const safeHtml = (text) => text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');

/** 设置输入区域可用 / 禁用状态 */
const setLoading = (loading) => {
    isLoading = loading;
    inputEl.disabled = loading;
    sendBtn.disabled = loading;
    if (!loading) inputEl.focus();
};

/* ============================================================
   Toast 通知
============================================================ */

const showToast = (msg) => {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = msg;
    document.body.appendChild(toast);
    // 双帧触发过渡动画
    requestAnimationFrame(() => {
        requestAnimationFrame(() => toast.classList.add('toast-show'));
    });
    setTimeout(() => {
        toast.classList.remove('toast-show');
        setTimeout(() => toast.remove(), 300);
    }, 2500);
};

/* ============================================================
   消息渲染
============================================================ */

/** 追加用户消息气泡 */
const appendUserMsg = (text) => {
    const el = document.createElement('div');
    el.className = 'message user';
    el.innerHTML = `
        <div class="msg-avatar">🐱</div>
        <div class="msg-body">
            <div class="msg-bubble">${safeHtml(text)}</div>
            <div class="msg-time">${now()}</div>
        </div>`;
    messagesEl.appendChild(el);
    scrollBottom();
};

/**
 * 追加 AI 消息气泡（初始为加载动画）
 * 返回 { bubble, timeEl } 用于后续写入流式内容
 */
const appendAssistantMsg = () => {
    const el = document.createElement('div');
    el.className = 'message assistant';
    el.innerHTML = `
        <div class="msg-avatar">🎓</div>
        <div class="msg-body">
            <div class="msg-bubble" id="_ai_bubble">
                <div class="loading-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
            <div class="msg-time" id="_ai_time"></div>
        </div>`;
    messagesEl.appendChild(el);
    scrollBottom();
    const bubble = el.querySelector('#_ai_bubble');
    const timeEl = el.querySelector('#_ai_time');
    bubble.removeAttribute('id');
    timeEl.removeAttribute('id');
    return { bubble, timeEl };
};

/** 在消息列表底部显示错误提示（4 秒后自动消失） */
const showError = (msg) => {
    const el = document.createElement('div');
    el.className = 'error-bar';
    el.textContent = '⚠ ' + msg;
    messagesEl.appendChild(el);
    scrollBottom();
    setTimeout(() => el.remove(), 4000);
};

/* ============================================================
   欢迎区块
============================================================ */

const renderWelcome = () => {
    messagesEl.innerHTML = `
        <div class="welcome-block">
            <div class="welcome-icon">📚</div>
            <h2>你好，我是智能教育助手</h2>
            <p>有关课程、知识点、老师、作业或考试的任何问题<br>都可以直接问我，我来帮你解答</p>
            <div class="quick-questions">
                <span class="quick-tag" data-q="有哪些课程可以学习？">有哪些课程？</span>
                <span class="quick-tag" data-q="有哪些任课老师？">有哪些任课老师？</span>
            </div>
        </div>`;
    messagesEl.querySelectorAll('.quick-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            if (isLoading) return;
            inputEl.value = tag.dataset.q;
            sendMessage();
        });
    });
};

/* ============================================================
   发送消息（核心逻辑）
============================================================ */

const sendMessage = async () => {
    const question = inputEl.value.trim();
    if (!question || isLoading) return;

    inputEl.value = '';
    inputEl.style.height = 'auto';
    setLoading(true);

    appendUserMsg(question);
    const { bubble, timeEl } = appendAssistantMsg();

    let accumulated = '';
    let firstChunk  = true;

    try {
        /**
         * credentials: 'same-origin'
         *   - 浏览器自动将 Starlette SessionMiddleware 写入的加密 session Cookie 附加到请求头
         *   - 服务器返回的 Set-Cookie 也会被浏览器自动存储，无需手动传递
         */
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ question }),
        });

        if (!response.ok) {
            let detail = `HTTP ${response.status}`;
            try { detail = (await response.json()).detail || detail; } catch (_) {}
            throw new Error(detail);
        }

        const reader  = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            accumulated += decoder.decode(value, { stream: true });

            if (firstChunk) {
                bubble.innerHTML = '';
                firstChunk = false;
            }
            bubble.innerHTML = safeHtml(accumulated) + '<span class="typing-cursor"></span>';
            scrollBottom();
        }

        bubble.innerHTML = safeHtml(accumulated);
        timeEl.textContent = now();

    } catch (err) {
        console.error('[SmartEdu] 请求失败:', err);
        if (firstChunk) {
            bubble.innerHTML = '<span style="color:#ef5350">抱歉，请求失败，请稍后重试</span>';
        }
        showError('网络请求失败：' + err.message);
    } finally {
        setLoading(false);
    }
};

/* ============================================================
   新建对话
============================================================ */

const startNewChat = async () => {
    if (isLoading) return;

    try {
        await fetch(NEW_CHAT_URL, { method: 'POST', credentials: 'same-origin' });
    } catch (_) {
        // 请求失败也继续重置 UI；后端在下次 /chat 时会自动生成新 session_id
    }

    renderWelcome();
    inputEl.value = '';
    inputEl.style.height = 'auto';
    inputEl.focus();
    showToast('新对话已开启');
};

/* ============================================================
   事件绑定 & 初始化
============================================================ */

sendBtn.addEventListener('click', sendMessage);
newChatBtn.addEventListener('click', startNewChat);

inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
});

renderWelcome();
inputEl.focus();
