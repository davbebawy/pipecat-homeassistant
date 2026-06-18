const api = {
  config: "/api/assist/config",
  status: "/api/assist/status",
  mcp: "/api/assist/mcp/check",
};

const redacted = "__redacted__";
let config = null;
let selectedFlowId = null;

const $ = (id) => document.getElementById(id);

function setMessage(text, state = "") {
  const message = $("message");
  message.textContent = text;
  message.className = `message ${state}`.trim();
}

function csvToList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function listToCsv(items) {
  return (items || []).join(", ");
}

function currentFlow() {
  return config.flows.find((flow) => flow.id === selectedFlowId) || config.flows[0];
}

function renderFlowList() {
  const list = $("flow-list");
  list.innerHTML = "";
  config.flows.forEach((flow) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `flow-item ${flow.id === selectedFlowId ? "active" : ""}`;
    item.innerHTML = `<strong></strong><span></span>`;
    item.querySelector("strong").textContent = flow.name;
    item.querySelector("span").textContent = `${flow.model} / ${flow.voice}`;
    item.addEventListener("click", () => {
      saveFlowFromForm();
      selectedFlowId = flow.id;
      render();
    });
    list.appendChild(item);
  });
}

function fillGlobalForm() {
  $("openai_api_key").value = config.openai_api_key_configured ? redacted : "";
  $("text_model").value = config.text_model || "";
  $("ha_mcp_url").value = config.ha_mcp_url || "";
  $("longlived_token").value = config.longlived_token_configured ? redacted : "";
  $("runner_host").value = config.runner_host || "";
  $("runner_port").value = config.runner_port || 7860;
  $("esp32_mode").checked = Boolean(config.esp32_mode);
  $("runner_offer_url").value = config.runner_offer_url || "";
  $("satellite_shared_secret").value = config.satellite_shared_secret_configured ? redacted : "";
  $("log_level").value = config.log_level || "INFO";
}

function fillFlowForm() {
  const flow = currentFlow();
  $("flow-title").textContent = flow.name || "Flow";
  $("flow-subtitle").textContent = `${flow.model} / ${flow.voice}`;
  $("flow_name").value = flow.name || "";
  $("flow_id").value = flow.id || "";
  $("flow_model").value = flow.model || "";
  $("flow_voice").value = flow.voice || "";
  $("flow_speed").value = flow.speed || 1;
  $("flow_language").value = flow.language || "";
  $("flow_instructions").value = flow.instructions || "";
  $("flow_greeting").value = flow.greeting || "";
  $("flow_transcription_model").value = flow.transcription_model || "";
  $("flow_noise_reduction").value = flow.noise_reduction || "near_field";
  $("flow_vad_mode").value = flow.vad_mode || "semantic_vad";
  $("flow_vad_eagerness").value = flow.vad_eagerness || "low";
  $("flow_max_output_tokens").value = flow.max_output_tokens || "";
  $("flow_reasoning_effort").value = flow.reasoning_effort || "";
  $("flow_interrupt_response").checked = Boolean(flow.interrupt_response);
  $("flow_mcp_enabled").checked = Boolean(flow.mcp_enabled);
  $("flow_video_enabled").checked = Boolean(flow.video_enabled);
  $("flow_mcp_tool_allowlist").value = listToCsv(flow.mcp_tool_allowlist);
}

function saveFlowFromForm() {
  if (!config || !selectedFlowId) return;
  const flow = currentFlow();
  const oldId = flow.id;
  flow.name = $("flow_name").value.trim() || "Untitled flow";
  flow.id = $("flow_id").value.trim() || oldId;
  flow.model = $("flow_model").value.trim();
  flow.voice = $("flow_voice").value.trim();
  flow.speed = Number($("flow_speed").value || 1);
  flow.language = $("flow_language").value.trim() || null;
  flow.instructions = $("flow_instructions").value;
  flow.greeting = $("flow_greeting").value;
  flow.transcription_model = $("flow_transcription_model").value.trim();
  flow.noise_reduction = $("flow_noise_reduction").value;
  flow.vad_mode = $("flow_vad_mode").value;
  flow.vad_eagerness = $("flow_vad_eagerness").value;
  flow.max_output_tokens = $("flow_max_output_tokens").value
    ? Number($("flow_max_output_tokens").value)
    : null;
  flow.reasoning_effort = $("flow_reasoning_effort").value || null;
  flow.interrupt_response = $("flow_interrupt_response").checked;
  flow.mcp_enabled = $("flow_mcp_enabled").checked;
  flow.video_enabled = $("flow_video_enabled").checked;
  flow.mcp_tool_allowlist = csvToList($("flow_mcp_tool_allowlist").value);
  if (selectedFlowId === oldId) selectedFlowId = flow.id;
  config.selected_flow_id = selectedFlowId;
}

function collectConfig() {
  saveFlowFromForm();
  return {
    ...config,
    openai_api_key: $("openai_api_key").value,
    text_model: $("text_model").value.trim(),
    ha_mcp_url: $("ha_mcp_url").value.trim(),
    longlived_token: $("longlived_token").value,
    runner_host: $("runner_host").value.trim(),
    runner_port: Number($("runner_port").value || 7860),
    esp32_mode: $("esp32_mode").checked,
    satellite_shared_secret: $("satellite_shared_secret").value,
    log_level: $("log_level").value,
    selected_flow_id: selectedFlowId,
    flows: config.flows,
  };
}

function render() {
  fillGlobalForm();
  fillFlowForm();
  renderFlowList();
}

async function loadConfig() {
  const [configResponse, statusResponse] = await Promise.all([
    fetch(api.config),
    fetch(api.status),
  ]);
  config = await configResponse.json();
  const status = await statusResponse.json();
  selectedFlowId = config.selected_flow_id || config.flows[0].id;
  $("status-pill").textContent = status.ok ? "ready" : "offline";
  $("status-pill").className = `pill ${status.ok ? "ok" : ""}`.trim();
  render();
}

async function saveConfig() {
  setMessage("Saving...");
  const response = await fetch(api.config, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectConfig()),
  });
  if (!response.ok) {
    const detail = await response.text();
    setMessage(detail, "error");
    return;
  }
  config = await response.json();
  selectedFlowId = config.selected_flow_id;
  render();
  setMessage("Saved", "ok");
}

async function checkMcp() {
  setMessage("Checking MCP...");
  const response = await fetch(api.mcp, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ flow_id: selectedFlowId }),
  });
  const result = await response.json();
  if (result.ok) {
    setMessage(`MCP connected: ${result.tool_count} tools`, "ok");
  } else {
    setMessage(result.error || "MCP check failed", "error");
  }
}

function addFlow() {
  saveFlowFromForm();
  const id = `flow-${config.flows.length + 1}`;
  const base = currentFlow();
  const flow = structuredClone(base);
  flow.id = id;
  flow.name = "New flow";
  config.flows.push(flow);
  selectedFlowId = id;
  render();
}

async function copyUrl() {
  await navigator.clipboard.writeText($("runner_offer_url").value);
  setMessage("Copied", "ok");
}

$("save-config").addEventListener("click", saveConfig);
$("check-mcp").addEventListener("click", checkMcp);
$("add-flow").addEventListener("click", addFlow);
$("copy-url").addEventListener("click", copyUrl);

loadConfig().catch((err) => {
  $("status-pill").textContent = "error";
  $("status-pill").className = "pill";
  setMessage(String(err), "error");
});

