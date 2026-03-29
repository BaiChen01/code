<script setup>
import { computed } from "vue";

import ChartRenderer from "./ChartRenderer.vue";

const props = defineProps({
  payload: {
    type: Object,
    default: null,
  },
});

const trace = computed(() => props.payload?.trace || {});
const analysis = computed(() => props.payload?.analysis_result || null);
const retrievedDocs = computed(
  () => props.payload?.retrieved_docs || { job_docs: [], news_docs: [], total_count: 0 }
);
const sqlResult = computed(() => props.payload?.sql_result || null);
const chartResult = computed(() => props.payload?.chart_result || null);

const overviewItems = computed(() => [
  ["Intent", props.payload?.intent_type || "none"],
  ["Scope", trace.value.retrieval_scope || "none"],
  ["Success", props.payload?.success ? "Yes" : "No"],
  ["Plan", (trace.value.plan_steps || []).join(" -> ") || "N/A"],
  ["Job Docs", String((retrievedDocs.value.job_docs || []).length)],
  ["News Docs", String((retrievedDocs.value.news_docs || []).length)],
]);

const traceItems = computed(() => {
  const items = [
    ["Intent Type", trace.value.intent_type || "none"],
    ["Need SQL", String(Boolean(trace.value.need_sql))],
    ["Need RAG", String(Boolean(trace.value.need_rag))],
    ["Need Chart", String(Boolean(trace.value.need_chart))],
    ["Analysis Mode", trace.value.analysis_mode || "none"],
    ["Retrieval Scope", trace.value.retrieval_scope || "none"],
    ["Plan Steps", (trace.value.plan_steps || []).join(" -> ") || "none"],
  ];
  if (sqlResult.value?.summary) {
    items.push(["SQL Summary", sqlResult.value.summary]);
  }
  if (props.payload?.error_message) {
    items.push(["Workflow Error", props.payload.error_message]);
  }
  if (sqlResult.value?.error) {
    items.push(["SQL Error", sqlResult.value.error]);
  }
  return items;
});

const jobDocCount = computed(() => (retrievedDocs.value.job_docs || []).length);
const newsDocCount = computed(() => (retrievedDocs.value.news_docs || []).length);
const findingCount = computed(() =>
  Array.isArray(analysis.value?.key_findings) ? analysis.value.key_findings.length : 0
);

const chartMeta = computed(() => {
  if (!chartResult.value?.chart_needed) {
    return "待生成";
  }
  return chartResult.value.chart_type || "chart";
});

function docTitle(doc, type) {
  if (type === "job") {
    return `${doc.company_name || "未知企业"} · ${doc.job_title || "未知岗位"}`;
  }
  return `${doc.company_name || "未知企业"} · ${doc.title || "未知资讯"}`;
}
</script>

<template>
  <aside class="inspector-column">
    <section class="card inspector-sidebar">
      <div class="panel-head compact inspector-sidebar-head">
        <div>
          <p class="panel-kicker">Sidebar</p>
          <h2>情报边栏</h2>
        </div>
      </div>

      <details class="inspector-drawer" open>
        <summary class="inspector-drawer-summary">
          <div>
            <p class="panel-kicker">Overview</p>
            <h2>本轮概览</h2>
          </div>
          <span class="drawer-meta">{{ props.payload?.intent_type || "待输入" }}</span>
        </summary>
        <div class="drawer-body">
          <div class="overview-grid">
            <div v-for="[label, value] in overviewItems" :key="label" class="overview-item">
              <span>{{ label }}</span>
              <strong>{{ value }}</strong>
            </div>
          </div>
          <div class="answer-preview">
            {{ props.payload?.answer || "等待第一条问题。这里会展示最新一轮回答摘要。" }}
          </div>
        </div>
      </details>

      <details class="inspector-drawer" :open="Boolean(analysis)">
        <summary class="inspector-drawer-summary">
          <div>
            <p class="panel-kicker">Analysis</p>
            <h2>分析要点</h2>
          </div>
          <span class="drawer-meta">{{ findingCount }} 条要点</span>
        </summary>
        <div class="drawer-body">
          <div class="analysis-block">
            <div v-if="!analysis" class="empty-state">分析结果会在这里拆分展示。</div>

            <template v-else>
              <section v-if="analysis.question_summary" class="analysis-card">
                <h3>问题摘要</h3>
                <p>{{ analysis.question_summary }}</p>
              </section>

              <section v-if="analysis.intelligence_judgment" class="analysis-card">
                <h3>核心判断</h3>
                <p>{{ analysis.intelligence_judgment }}</p>
              </section>

              <section v-if="analysis.chart_explanation" class="analysis-card">
                <h3>图表解释</h3>
                <p>{{ analysis.chart_explanation }}</p>
              </section>

              <section
                v-if="Array.isArray(analysis.key_findings) && analysis.key_findings.length"
                class="analysis-card"
              >
                <h3>Key Findings</h3>
                <ul>
                  <li v-for="item in analysis.key_findings" :key="item">{{ item }}</li>
                </ul>
              </section>
            </template>
          </div>
        </div>
      </details>

      <details class="inspector-drawer" :open="Boolean(chartResult?.chart_needed)">
        <summary class="inspector-drawer-summary">
          <div>
            <p class="panel-kicker">Chart</p>
            <h2>图表区</h2>
          </div>
          <span class="drawer-meta">{{ chartMeta }}</span>
        </summary>
        <div class="drawer-body">
          <div class="chart-mount">
            <ChartRenderer :chart-result="chartResult || null" />
          </div>
          <p class="chart-summary">
            {{ chartResult?.chart_summary || "等待图表请求。" }}
          </p>
        </div>
      </details>

      <details class="inspector-drawer">
        <summary class="inspector-drawer-summary">
          <div>
            <p class="panel-kicker">Job Evidence</p>
            <h2>招聘证据</h2>
          </div>
          <span class="drawer-meta">{{ jobDocCount }} 条</span>
        </summary>
        <div class="drawer-body">
          <div class="evidence-list">
            <div v-if="!jobDocCount" class="empty-state">当前没有招聘证据。</div>
            <article
              v-for="doc in (retrievedDocs.job_docs || []).slice(0, 4)"
              :key="`${doc.source_type}-${doc.job_post_id}-${doc.text_type}`"
              class="evidence-card"
            >
              <strong>{{ docTitle(doc, "job") }}</strong>
              <p>{{ doc.snippet || "没有可展示的片段。" }}</p>
              <a v-if="doc.source_url" :href="doc.source_url" target="_blank" rel="noreferrer">
                打开来源
              </a>
            </article>
          </div>
        </div>
      </details>

      <details class="inspector-drawer">
        <summary class="inspector-drawer-summary">
          <div>
            <p class="panel-kicker">News Evidence</p>
            <h2>资讯证据</h2>
          </div>
          <span class="drawer-meta">{{ newsDocCount }} 条</span>
        </summary>
        <div class="drawer-body">
          <div class="evidence-list">
            <div v-if="!newsDocCount" class="empty-state">当前没有资讯证据。</div>
            <article
              v-for="doc in (retrievedDocs.news_docs || []).slice(0, 4)"
              :key="`${doc.source_type}-${doc.doc_id || doc.title}`"
              class="evidence-card"
            >
              <strong>{{ docTitle(doc, "news") }}</strong>
              <p>{{ doc.snippet || "没有可展示的片段。" }}</p>
              <a v-if="doc.source_url" :href="doc.source_url" target="_blank" rel="noreferrer">
                打开来源
              </a>
            </article>
          </div>
        </div>
      </details>

      <details class="inspector-drawer">
        <summary class="inspector-drawer-summary">
          <div>
            <p class="panel-kicker">Trace</p>
            <h2>执行轨迹</h2>
          </div>
          <span class="drawer-meta">{{ traceItems.length }} 项</span>
        </summary>
        <div class="drawer-body">
          <div class="trace-list">
            <div v-for="[label, value] in traceItems" :key="label" class="trace-item">
              <strong>{{ label }}</strong>
              <p>{{ value }}</p>
            </div>
          </div>
        </div>
      </details>
    </section>
  </aside>
</template>
