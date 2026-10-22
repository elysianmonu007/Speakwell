const input = document.getElementById("audio-input");
const dropzone = document.getElementById("dropzone");
const dropzoneText = document.getElementById("dropzone-text");
const preview = document.getElementById("preview");
const analyzeBtn = document.getElementById("analyze-btn");
const againBtn = document.getElementById("again-btn");
const statusEl = document.getElementById("status");
const uploadSection = document.getElementById("upload-section");
const results = document.getElementById("results");

let selectedFile = null;
let duration = 0;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.className = isError ? "error" : "";
}

function chooseFile(file) {
  if (!file) return;
  selectedFile = file;
  dropzoneText.textContent = file.name;
  setStatus("");

  // Show a player and read the audio length (used to calculate speaking pace)
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  preview.onloadedmetadata = () => { duration = preview.duration || 0; };
  analyzeBtn.disabled = false;
}

input.addEventListener("change", () => chooseFile(input.files[0]));

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("drag"); })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("drag"); })
);
dropzone.addEventListener("drop", (e) => chooseFile(e.dataTransfer.files[0]));

analyzeBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  const formData = new FormData();
  formData.append("audio", selectedFile);
  formData.append("duration", duration);

  analyzeBtn.disabled = true;
  setStatus("Listening to your recording. This can take up to a minute.");

  try {
    const response = await fetch("/api/analyze", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Something went wrong.");
    showResults(data);
  } catch (err) {
    setStatus(err.message, true);
    analyzeBtn.disabled = false;
  }
});

function fillList(id, items) {
  const list = document.getElementById(id);
  list.innerHTML = "";
  (items || []).forEach((text) => {
    const li = document.createElement("li");
    li.textContent = text; // textContent keeps AI output from injecting HTML
    list.appendChild(li);
  });
}

function addStat(container, value, label) {
  const div = document.createElement("div");
  div.className = "stat";
  const b = document.createElement("b");
  b.textContent = value;
  const span = document.createElement("span");
  span.textContent = label;
  div.append(b, span);
  container.appendChild(div);
}

function showResults(data) {
  document.getElementById("summary").textContent = data.summary || "";
  document.getElementById("transcript").textContent = data.transcript || "No speech was detected.";
  fillList("strengths", data.strengths);
  fillList("weaknesses", data.weaknesses);
  fillList("tips", data.tips);

  const statsBox = document.getElementById("stats");
  statsBox.innerHTML = "";
  const s = data.stats || {};
  addStat(statsBox, s.word_count ?? 0, "words");
  if (s.words_per_minute) addStat(statsBox, s.words_per_minute, "words per minute");
  const fillerTotal = Object.values(s.fillers || {}).reduce((a, b) => a + b, 0);
  const detail = Object.entries(s.fillers || {}).map(([w, n]) => `${w} ×${n}`).join(", ");
  addStat(statsBox, fillerTotal, detail ? `filler words (${detail})` : "filler words");

  uploadSection.hidden = true;
  results.hidden = false;
  window.scrollTo({ top: 0 });
}

againBtn.addEventListener("click", () => {
  selectedFile = null;
  input.value = "";
  preview.hidden = true;
  dropzoneText.textContent = "Choose an audio file or drop it here";
  analyzeBtn.disabled = true;
  setStatus("");
  results.hidden = true;
  uploadSection.hidden = false;
});