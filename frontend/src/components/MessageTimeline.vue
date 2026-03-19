<script setup>
const props = defineProps({
  messages: {
    type: Array,
    required: true,
  },
});

function chipsFor(message) {
  const payload = message.payload || {};
  const trace = payload.trace || {};
  const retrievedDocs = payload.retrieved_docs || {};
  const chips = [
    `intent: ${payload.intent_type || "unknown"}`,
    `scope: ${trace.retrieval_scope || "none"}`,
    `job docs: ${(retrievedDocs.job_docs || []).length}`,
    `news docs: ${(retrievedDocs.news_docs || []).length}`,
  ];
  if (trace.need_chart) {
    chips.push("chart requested");
  }
  return chips;
}
</script>

<template>
  <div class="timeline">
    <article
      v-for="message in props.messages"
      :key="message.id"
      class="message"
      :class="message.role"
    >
      <div class="message-meta">
        <span>
          {{
            message.role === "user"
              ? "User"
              : message.role === "assistant"
                ? "Assistant"
                : "System"
          }}
        </span>
        <span>{{ message.timestamp }}</span>
      </div>

      <div class="message-text">{{ message.text }}</div>

      <div
        v-if="message.payload && message.role === 'assistant'"
        class="message-chips"
      >
        <span v-for="chip in chipsFor(message)" :key="chip" class="data-chip">
          {{ chip }}
        </span>
      </div>
    </article>
  </div>
</template>
