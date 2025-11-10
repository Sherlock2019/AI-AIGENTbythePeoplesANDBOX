"""Reusable embedded chat assistant panel shared across Streamlit workflows."""
from __future__ import annotations

import json
import os
from html import escape
from typing import Any, Dict, List, Optional

import streamlit.components.v1 as components


def _safe_json(data: Dict[str, Any]) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"error": "Failed to serialize context"})


def render_chat_assistant(
    page_id: str,
    context: Optional[Dict[str, Any]] = None,
    *,
    title: str = "Need chat bot assistant ?",
    default_open: bool = False,
    faq_questions: Optional[List[str]] = None,
) -> None:
    """
    Inject the floating chat drawer into the parent Streamlit document.
    Passing FAQ questions pre-populates quick actions until the backend
    returns its own faq_options payload.
    """
    if not page_id:
        raise ValueError("page_id is required for chat assistant.")

    context = context or {}
    faq_questions = faq_questions or []
    api_url = (
        os.getenv("CHAT_API_URL")
        or os.getenv("API_URL")
        or os.getenv("AGENT_API_URL")
        or "http://localhost:8090"
    )

    panel_id = f"chat-assistant-{page_id.replace(' ', '-').lower()}"
    storage_key = f"{panel_id}-history"
    open_state_key = f"{panel_id}-open"
    context_json = _safe_json(context)
    faq_json = json.dumps(faq_questions)
    default_open_str = "true" if default_open else "false"

    markup = f"""
<div id="{panel_id}" class="chat-assistant-shell">
  <button class="chat-toggle">{escape(title)}</button>
  <div class="chat-window">
    <div class="chat-header">
      <div class="chat-header-left">
        <span class="chat-mode">Assistant</span>
        <span class="chat-status">online</span>
      </div>
      <button class="chat-reset" title="Clear conversation">↺</button>
    </div>
    <div class="chat-context"></div>
    <div class="chat-faq"></div>
    <div class="chat-messages"></div>
    <div class="chat-input">
      <textarea placeholder="Ask anything about this workflow..." rows="2"></textarea>
      <button class="chat-send">Send</button>
    </div>
  </div>
</div>
""".strip()

    css = f"""
#{panel_id} ::-webkit-scrollbar {{
  width: 6px;
}}
.chat-assistant-shell {{
  position: fixed;
  right: 18px;
  bottom: 24px;
  width: 360px;
  max-width: 90vw;
  font-family: var(--font, "Inter", sans-serif);
  z-index: 9999;
}}
.chat-assistant-shell .chat-toggle {{
  width: 100%;
  padding: 10px 14px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  border: none;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(37,99,235,0.35);
  font-size: 0.95rem;
  cursor: pointer;
}}
.chat-assistant-shell .chat-window {{
  margin-top: 8px;
  background: rgba(15,23,42,0.92);
  color: #e2e8f0;
  border-radius: 14px;
  border: 1px solid rgba(148,163,184,0.35);
  box-shadow: 0 18px 30px rgba(15,23,42,0.45);
  display: none;
  flex-direction: column;
  height: 540px;
  backdrop-filter: blur(20px);
}}
.chat-assistant-shell.open .chat-window {{
  display: flex;
}}
.chat-header {{
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(148,163,184,0.3);
  font-weight: 600;
}}
.chat-status {{
  background: #10b981;
  color: #052e16;
  padding: 2px 10px;
  border-radius: 999px;
  margin-left: 10px;
  font-size: 0.75rem;
  text-transform: uppercase;
}}
.chat-status.offline {{
  background: #f87171;
  color: #450a0a;
}}
.chat-context {{
  padding: 10px 16px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 0.75rem;
  color: #94a3b8;
}}
.chat-context span {{
  background: rgba(15,23,42,0.6);
  border: 1px solid rgba(148,163,184,0.3);
  border-radius: 999px;
  padding: 2px 10px;
}}
.chat-faq {{
  display: none;
  padding: 8px 16px 0;
  flex-wrap: wrap;
  gap: 6px;
}}
.chat-faq button {{
  background: rgba(37,99,235,0.25);
  border: 1px solid rgba(59,130,246,0.45);
  color: #cbd5ff;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 0.78rem;
  cursor: pointer;
}}
.chat-messages {{
  flex: 1;
  padding: 12px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}}
.chat-message {{
  line-height: 1.4;
  font-size: 0.9rem;
  border-radius: 12px;
  padding: 10px 12px;
}}
.chat-message.user {{
  background: rgba(59,130,246,0.15);
  align-self: flex-end;
  border-bottom-right-radius: 4px;
}}
.chat-message.assistant {{
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.3);
  align-self: flex-start;
  border-bottom-left-radius: 4px;
}}
.chat-actions {{
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}}
.chat-actions button {{
  background: rgba(30,64,175,0.4);
  border: 1px solid rgba(59,130,246,0.4);
  color: #cbd5f5;
  border-radius: 999px;
  padding: 3px 10px;
  cursor: pointer;
  font-size: 0.78rem;
}}
.chat-input {{
  border-top: 1px solid rgba(148,163,184,0.3);
  padding: 10px 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}}
.chat-input textarea {{
  width: 100%;
  resize: none;
  border-radius: 10px;
  border: 1px solid rgba(148,163,184,0.3);
  background: rgba(15,23,42,0.8);
  color: inherit;
  padding: 8px;
}}
.chat-input button {{
  align-self: flex-end;
  background: #2563eb;
  color: #fff;
  border: none;
  padding: 8px 18px;
  border-radius: 999px;
  font-weight: 600;
  cursor: pointer;
}}
.chat-reset {{
  background: transparent;
  border: 1px solid rgba(148,163,184,0.4);
  color: inherit;
  border-radius: 999px;
  padding: 4px 10px;
  cursor: pointer;
}}
@media (max-width: 768px) {{
  .chat-assistant-shell {{
    width: calc(100vw - 32px);
    right: 16px;
    bottom: 16px;
  }}
  .chat-assistant-shell .chat-window {{
    height: 420px;
  }}
}}
""".strip()

    script = f"""
<script>
(function() {{
  const panelId = "{panel_id}";
  const styleId = panelId + "-style";
  const markup = {json.dumps(markup)};
  const css = {json.dumps(css)};
  const apiUrl = "{escape(api_url)}";
  const pageId = "{escape(page_id)}";
  const storageKey = "{storage_key}";
  const openKey = "{open_state_key}";
  const defaultOpen = {default_open_str};
  const contextData = {context_json};
  const initialFaq = {faq_json};

  const parentDoc = window.parent && window.parent.document ? window.parent.document : document;
  if (!parentDoc) return;
  const store = window.parent && window.parent.localStorage ? window.parent.localStorage : localStorage;

  if (!parentDoc.getElementById(styleId)) {{
    const styleEl = parentDoc.createElement("style");
    styleEl.id = styleId;
    styleEl.textContent = css;
    parentDoc.head.appendChild(styleEl);
  }}

  if (!parentDoc.getElementById(panelId)) {{
    const wrapper = parentDoc.createElement("div");
    wrapper.innerHTML = markup;
    parentDoc.body.appendChild(wrapper.firstElementChild);
  }}

  const shell = parentDoc.getElementById(panelId);
  if (!shell) return;

  const toggle = shell.querySelector(".chat-toggle");
  const resetButton = shell.querySelector(".chat-reset");
  const sendButton = shell.querySelector(".chat-send");
  const textarea = shell.querySelector("textarea");
  const messagesEl = shell.querySelector(".chat-messages");
  const statusEl = shell.querySelector(".chat-status");
  const modeEl = shell.querySelector(".chat-mode");
  const contextEl = shell.querySelector(".chat-context");
  const faqEl = shell.querySelector(".chat-faq");

  if (shell.__assistantInitialized) {{
    const state = shell.__assistantState;
    state.context = contextData;
    state.renderContext();
    state.setFAQs(initialFaq);
    return;
  }}

  const state = {{
    history: [],
    context: contextData,
    faq: initialFaq || [],
    renderContext: () => {{}},
    setFAQs: () => {{}},
  }};
  shell.__assistantState = state;

  const storedHistory = store.getItem(storageKey);
  try {{
    state.history = storedHistory ? JSON.parse(storedHistory) : [];
  }} catch (err) {{
    state.history = [];
  }}

  const saveHistory = () => {{
    state.history = state.history.slice(-50);
    store.setItem(storageKey, JSON.stringify(state.history));
  }};

  state.renderContext = () => {{
    const chips = [];
    Object.entries(state.context || {{}}).forEach(([key, value]) => {{
      if (value === null || value === undefined) return;
      const display = typeof value === "string" ? value : String(value);
      if (display.length < 60) {{
        chips.push(`<span>${{key}}: ${{display}}</span>`);
      }}
    }});
    contextEl.innerHTML = chips.slice(0, 5).join("");
  }};

  const renderMessages = () => {{
    messagesEl.innerHTML = state.history
      .map(msg => {{
        const actions = msg.actions && msg.actions.length
          ? '<div class="chat-actions">' + msg.actions.map(a => `<button data-command="${{a.command}}">${{a.label}}</button>`).join("") + "</div>"
          : "";
        return `<div class="chat-message ${{msg.role}}"><div>${{msg.content}}</div>${{actions}}</div>`;
      }}).join("");
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }};

  const renderFAQ = () => {{
    if (!faqEl) return;
    const items = (state.faq || []).slice(0, 6);
    if (!items.length) {{
      faqEl.style.display = "none";
      faqEl.innerHTML = "";
      return;
    }}
    faqEl.style.display = "flex";
    faqEl.innerHTML = items.map(q => `<button type="button" data-faq="${{q}}">${{q}}</button>`).join("");
  }};

  state.setFAQs = (faqList) => {{
    state.faq = Array.isArray(faqList) ? faqList : [];
    renderFAQ();
  }};

  state.renderContext();
  renderMessages();
  state.setFAQs(initialFaq);

  const setStatus = (label, isOffline = false) => {{
    statusEl.textContent = label;
    statusEl.classList.toggle("offline", isOffline);
  }};

  const appendMessage = (role, content, extra = {{}}) => {{
    state.history.push({{ role, content, actions: extra.actions || [] }});
    saveHistory();
    renderMessages();
  }};

  const sendMessage = (text) => {{
    if (!text.trim()) return;
    appendMessage("user", text);
    setStatus("thinking…");
    sendButton.disabled = true;
    fetch(apiUrl + "/v1/chat", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{
        message: text,
        page_id: pageId,
        context: state.context,
        history: state.history
      }})
    }})
      .then(resp => resp.json())
      .then(data => {{
        const reply = data.reply || "No reply.";
        appendMessage("assistant", reply, {{ actions: data.actions || [] }});
        modeEl.textContent = data.mode || "Assistant";
        if (data.faq_options) {{
          state.setFAQs(data.faq_options);
        }}
        setStatus("online");
      }})
      .catch(err => {{
        appendMessage("assistant", "⚠️ Assistant unavailable: " + err.message);
        setStatus("offline", true);
      }})
      .finally(() => {{
        sendButton.disabled = false;
      }});
  }};

  const storedOpen = store.getItem(openKey);
  const startOpen = storedOpen === null ? defaultOpen : storedOpen === "true";
  shell.classList.toggle("open", startOpen);

  toggle.onclick = () => {{
    const isOpen = !shell.classList.contains("open");
    shell.classList.toggle("open", isOpen);
    store.setItem(openKey, isOpen ? "true" : "false");
  }};

  sendButton.onclick = () => {{
    const text = textarea.value;
    textarea.value = "";
    sendMessage(text);
  }};

  textarea.addEventListener("keydown", (event) => {{
    if (event.key === "Enter" && !event.shiftKey) {{
      event.preventDefault();
      const text = textarea.value;
      textarea.value = "";
      sendMessage(text);
    }}
  }});

  resetButton.onclick = () => {{
    state.history = [];
    saveHistory();
    renderMessages();
    setStatus("online");
  }};

  messagesEl.addEventListener("click", (event) => {{
    const btn = event.target.closest("button[data-command]");
    if (!btn) return;
    const label = btn.textContent || "";
    sendMessage(`Action requested: ${{label}}`);
  }});

  faqEl.addEventListener("click", (event) => {{
    const btn = event.target.closest("button[data-faq]");
    if (!btn) return;
    const question = btn.getAttribute("data-faq") || "";
    sendMessage(question);
  }});

  shell.__assistantInitialized = true;
}})();
</script>
"""

    components.html(script, height=0, width=0)
