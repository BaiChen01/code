<script setup>
const props = defineProps({
  sessions: {
    type: Array,
    required: true,
  },
  activeSessionId: {
    type: String,
    required: true,
  },
  storageNote: {
    type: String,
    required: true,
  },
});

const emit = defineEmits([
  "new-session",
  "rename-session",
  "export-session",
  "clear-storage",
  "select-session",
  "delete-session",
]);

function formatUpdatedAt(updatedAt) {
  if (!updatedAt) {
    return "未知时间";
  }
  return new Date(updatedAt).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sessionSnippet(session) {
  const meaningful = [...(session.messages || [])]
    .reverse()
    .find((message) => message.role !== "system");
  if (!meaningful?.text) {
    return "等待第一轮提问";
  }
  return meaningful.text.length > 70
    ? `${meaningful.text.slice(0, 70)}...`
    : meaningful.text;
}
</script>

<template>
  <aside class="card session-rail">
    <div class="panel-head compact">
      <div>
        <p class="panel-kicker">Local Memory</p>
        <h2>会话历史</h2>
      </div>
    </div>

    <div class="rail-actions">
      <button class="ghost-button" type="button" @click="emit('new-session')">新建会话</button>
      <button class="ghost-button" type="button" @click="emit('rename-session')">重命名</button>
      <button class="ghost-button" type="button" @click="emit('export-session')">导出 JSON</button>
      <button class="ghost-button danger" type="button" @click="emit('clear-storage')">
        清空本地
      </button>
    </div>

    <div class="storage-note">{{ props.storageNote }}</div>

    <div class="session-list">
      <button
        v-for="session in props.sessions"
        :key="session.id"
        class="session-card"
        :class="{ active: session.id === props.activeSessionId }"
        type="button"
        @click="emit('select-session', session.id)"
      >
        <div class="session-card-head">
          <strong>{{ session.title }}</strong>
          <button
            class="delete-session-button"
            type="button"
            title="删除会话"
            @click.stop="emit('delete-session', session.id)"
          >
            ×
          </button>
        </div>
        <div class="session-card-meta">
          {{ formatUpdatedAt(session.updatedAt) }} · {{ session.messages.length }} 条消息
        </div>
        <div class="session-card-snippet">{{ sessionSnippet(session) }}</div>
      </button>
    </div>
  </aside>
</template>
