<script setup>
import { computed, ref, watch } from "vue";

import InspectorPanel from "./components/InspectorPanel.vue";
import MessageTimeline from "./components/MessageTimeline.vue";
import SessionSidebar from "./components/SessionSidebar.vue";

const STORAGE_KEY = "game-intel-agent.sessions.v1";
const ACTIVE_SESSION_KEY = "game-intel-agent.active-session.v1";
const MAX_STORED_SESSIONS = 18;
const MAX_STORED_MESSAGES = 60;

const quickPrompts = [
  "最近腾讯游戏有哪些资讯动态",
  "哪些岗位要求 Unity 经验",
  "分析腾讯游戏近期研发布局，并结合招聘和资讯给出判断",
  "画出各企业岗位数量对比图",
];

const heroFacts = [
  { label: "Flow", value: "LangGraph" },
  { label: "State", value: "Session History + Local Save" },
  { label: "Run", value: "Vue + FastAPI" },
];

function safeId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function nowLabel() {
  return new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function createMessage(role, text, payload = null) {
  return {
    id: safeId(),
    role,
    text,
    payload,
    timestamp: nowLabel(),
  };
}

function createSession(title = "新会话") {
  const now = Date.now();
  return {
    id: safeId(),
    title,
    createdAt: now,
    updatedAt: now,
    draft: "",
    needChart: false,
    latestPayload: null,
    messages: [
      createMessage(
        "system",
        "欢迎来到 Vue 前端联调页。这里支持多会话、本地保存、证据面板和图表结果展示。"
      ),
    ],
  };
}

function shortenText(text, maxLength = 320) {
  const normalized = String(text || "").trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength)}...`;
}

function sanitizeDocs(docs) {
  return (docs || []).slice(0, 6).map((doc) => ({
    ...doc,
    snippet: shortenText(doc.snippet, 280),
  }));
}

function sanitizePayload(payload) {
  if (!payload) {
    return null;
  }

  const retrievedDocs = payload.retrieved_docs || {};
  const sqlResult = payload.sql_result || null;

  return {
    ...payload,
    answer: shortenText(payload.answer, 2400),
    sql_result: sqlResult
      ? {
          ...sqlResult,
          rows: Array.isArray(sqlResult.rows) ? sqlResult.rows.slice(0, 20) : [],
        }
      : null,
    retrieved_docs: {
      ...retrievedDocs,
      job_docs: sanitizeDocs(retrievedDocs.job_docs),
      news_docs: sanitizeDocs(retrievedDocs.news_docs),
    },
  };
}

function sanitizeSession(session) {
  return {
    ...session,
    draft: shortenText(session.draft, 600),
    latestPayload: sanitizePayload(session.latestPayload),
    messages: (session.messages || []).slice(-MAX_STORED_MESSAGES).map((message) => ({
      ...message,
      text: shortenText(message.text, 2400),
      payload: message.payload ? sanitizePayload(message.payload) : null,
    })),
  };
}

function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [createSession()];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || !parsed.length) {
      return [createSession()];
    }

    return parsed.map((session) => ({
      id: session.id || safeId(),
      title: session.title || "未命名会话",
      createdAt: Number(session.createdAt) || Date.now(),
      updatedAt: Number(session.updatedAt) || Date.now(),
      draft: session.draft || "",
      needChart: Boolean(session.needChart),
      latestPayload: session.latestPayload || null,
      messages:
        Array.isArray(session.messages) && session.messages.length
          ? session.messages
          : [createMessage("system", "已恢复本地会话。")],
    }));
  } catch (error) {
    return [createSession()];
  }
}

const sessions = ref(loadSessions());
const activeSessionId = ref(
  localStorage.getItem(ACTIVE_SESSION_KEY) || sessions.value[0].id
);
const loading = ref(false);
const storageNote = ref(
  "当前会话会自动保存到浏览器本地存储，刷新页面后可继续使用。"
);

const activeSession = computed(() => {
  return (
    sessions.value.find((session) => session.id === activeSessionId.value) ||
    sessions.value[0]
  );
});

const sortedSessions = computed(() => {
  return [...sessions.value].sort((left, right) => right.updatedAt - left.updatedAt);
});

const currentDraft = computed({
  get() {
    return activeSession.value?.draft || "";
  },
  set(value) {
    if (!activeSession.value) {
      return;
    }
    activeSession.value.draft = value;
  },
});

const currentNeedChart = computed({
  get() {
    return Boolean(activeSession.value?.needChart);
  },
  set(value) {
    if (!activeSession.value) {
      return;
    }
    activeSession.value.needChart = value;
  },
});

const currentPayload = computed(() => activeSession.value?.latestPayload || null);
const currentSessionMeta = computed(() => {
  if (!activeSession.value) {
    return "等待第一轮提问";
  }
  return `${new Date(activeSession.value.updatedAt).toLocaleString("zh-CN")} · ${
    activeSession.value.messages.length
  } 条消息`;
});

let persistTimer = null;

function schedulePersist() {
  if (persistTimer) {
    clearTimeout(persistTimer);
  }

  persistTimer = setTimeout(() => {
    try {
      const trimmed = sortedSessions.value
        .slice(0, MAX_STORED_SESSIONS)
        .map((session) => sanitizeSession(session));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
      localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId.value);
      storageNote.value = `本地已自动保存 · ${new Date().toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      })}`;
    } catch (error) {
      storageNote.value = "本地保存失败，请检查浏览器存储权限或清理旧会话。";
    }
  }, 160);
}

watch(sessions, schedulePersist, { deep: true });
watch(activeSessionId, schedulePersist);

function touchSession(session) {
  session.updatedAt = Date.now();
}

function deriveTitle(question) {
  const normalized = String(question || "").trim().replace(/\s+/g, " ");
  if (!normalized) {
    return "新会话";
  }
  return normalized.length > 28 ? `${normalized.slice(0, 28)}...` : normalized;
}

function appendMessage(role, text, payload = null) {
  if (!activeSession.value) {
    return;
  }

  activeSession.value.messages.push(
    createMessage(role, text, payload ? sanitizePayload(payload) : null)
  );
  touchSession(activeSession.value);
}

function createNewSession() {
  const session = createSession();
  sessions.value.unshift(session);
  activeSessionId.value = session.id;
}

function renameSession() {
  if (!activeSession.value) {
    return;
  }

  const nextName = window.prompt("输入新的会话名称", activeSession.value.title);
  if (!nextName) {
    return;
  }

  activeSession.value.title = nextName.trim() || activeSession.value.title;
  touchSession(activeSession.value);
}

function exportSession() {
  if (!activeSession.value) {
    return;
  }

  const fileName = `${
    activeSession.value.title.replace(/[^\w\u4e00-\u9fa5-]+/g, "_") || "session"
  }.json`;
  const blob = new Blob([JSON.stringify(sanitizeSession(activeSession.value), null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

function clearStorage() {
  if (!window.confirm("确定清空所有本地会话记录吗？")) {
    return;
  }

  const fresh = createSession();
  sessions.value = [fresh];
  activeSessionId.value = fresh.id;
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(ACTIVE_SESSION_KEY);
  storageNote.value = "本地会话记录已清空。";
}

function selectSession(sessionId) {
  activeSessionId.value = sessionId;
}

function deleteSession(sessionId) {
  const target = sessions.value.find((session) => session.id === sessionId);
  if (!target) {
    return;
  }

  if (!window.confirm(`确定删除会话“${target.title}”吗？`)) {
    return;
  }

  sessions.value = sessions.value.filter((session) => session.id !== sessionId);
  if (!sessions.value.length) {
    const fresh = createSession();
    sessions.value = [fresh];
    activeSessionId.value = fresh.id;
    return;
  }

  if (activeSessionId.value === sessionId) {
    activeSessionId.value = sessions.value[0].id;
  }
}

function normalizeErrorDetail(detail) {
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join(" | ");
  }
  if (typeof detail === "string") {
    return detail;
  }
  return "未知错误";
}

async function submitQuestion(questionOverride = "") {
  if (!activeSession.value || loading.value) {
    return;
  }

  const question = (questionOverride || activeSession.value.draft || "").trim();
  if (!question) {
    return;
  }

  appendMessage("user", question);
  activeSession.value.draft = "";
  if (activeSession.value.title === "新会话" || activeSession.value.messages.length <= 2) {
    activeSession.value.title = deriveTitle(question);
  }

  loading.value = true;
  try {
    const response = await fetch("/api/chat/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        need_chart: Boolean(activeSession.value.needChart),
        refresh_mode: "none",
      }),
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = null;
    }

    if (!response.ok) {
      throw new Error(normalizeErrorDetail(payload?.detail));
    }

    const normalizedPayload = sanitizePayload(payload);
    activeSession.value.latestPayload = normalizedPayload;
    appendMessage(
      "assistant",
      payload.answer || "本轮没有生成自然语言回答。",
      normalizedPayload
    );
  } catch (error) {
    appendMessage("assistant", `请求失败：${error.message || "未知错误"}`);
  } finally {
    loading.value = false;
  }
}

function runQuickPrompt(question) {
  currentDraft.value = question;
  submitQuestion(question);
}
</script>

<template>
  <div class="page-noise"></div>
  <div class="app-shell">
    <header class="hero hero-compact card">
      <div class="hero-main">
        <div>
          <p class="eyebrow">Game Intel Agent Console</p>
          <h1>招聘与资讯双库智能分析台</h1>
        </div>
        <p class="hero-text">
          面向正式联调的 Vue 控制台，支持多会话、本地保存、证据展示、图表区和执行轨迹面板。
        </p>
      </div>

      <div class="hero-facts">
        <div v-for="fact in heroFacts" :key="fact.label" class="metric-pill">
          <span class="metric-label">{{ fact.label }}</span>
          <strong>{{ fact.value }}</strong>
        </div>
      </div>
    </header>

    <main class="workspace">
      <SessionSidebar
        :sessions="sortedSessions"
        :active-session-id="activeSessionId"
        :storage-note="storageNote"
        @new-session="createNewSession"
        @rename-session="renameSession"
        @export-session="exportSession"
        @clear-storage="clearStorage"
        @select-session="selectSession"
        @delete-session="deleteSession"
      />

      <section class="chat-column">
        <div class="panel card chat-panel">
          <div class="panel-head">
            <div>
              <p class="panel-kicker">Conversation</p>
              <h2>{{ activeSession?.title || "新会话" }}</h2>
              <p class="session-meta">{{ currentSessionMeta }}</p>
            </div>
            <span class="status-pill" :class="{ 'loading-dot': loading }">
              {{ loading ? "Running" : "Ready" }}
            </span>
          </div>

          <div class="prompt-row">
            <button
              v-for="prompt in quickPrompts"
              :key="prompt"
              class="prompt-chip"
              type="button"
              @click="runQuickPrompt(prompt)"
            >
              {{ prompt }}
            </button>
          </div>

          <MessageTimeline :messages="activeSession?.messages || []" />

          <form class="composer" @submit.prevent="submitQuestion()">
            <label class="composer-label" for="questionInput">输入问题</label>
            <textarea
              id="questionInput"
              v-model="currentDraft"
              rows="4"
              placeholder="例如：分析腾讯游戏近期研发布局，并结合招聘和资讯给出判断"
              :disabled="loading"
              required
            ></textarea>

            <div class="composer-footer">
              <label class="toggle">
                <input v-model="currentNeedChart" type="checkbox" :disabled="loading" />
                <span>优先返回图表</span>
              </label>
              <span class="autosave-hint">输入内容和会话记录会自动本地保存</span>
              <button class="submit-button" type="submit" :disabled="loading">
                发送问题
              </button>
            </div>
          </form>
        </div>
      </section>

      <InspectorPanel :payload="currentPayload" />
    </main>
  </div>
</template>
