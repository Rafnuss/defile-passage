// Edit mode for the methods guide (dev server only, `?edit` in the URL): the prose becomes
// editable in place, and every edited block is saved through the dev server to
// logs/guide-edits.json (`guideEdits` in vite.config.js), from where it is carried back into the
// .vue templates. The source is never written from here.
//
// A block is keyed by its original text (maths as TeX between ⟨ ⟩), so edits survive a reload:
// on load, a block whose original text has a saved edit gets the edited version back.

const ENDPOINT = "/__guide-edits";
const BLOCKS = [
  ".hero .lead",
  ".chapter-head p",
  "article.method h5",
  "article.method h6",
  "article.method p",
  "article.method li",
  "article.method figcaption",
  "article.method td",
  "article.method summary",
  "article.method .callout",
].join(", ");
// Live widgets redraw their text; their blocks are not editable
const SKIP = ".readout, .widget .row, .day-breakdown, .validation-metrics, .eq, .contents";
const SAVE_DELAY = 800; // ms after the last keystroke

let edits = {}; // original text -> {original, edited, html, chapter, section}
let timer = null;
let status = null;

// Text of a block with each KaTeX formula as its TeX source
function text(el) {
  const c = el.cloneNode(true);
  c.querySelectorAll(".sec-n").forEach((n) => n.replaceChildren());
  c.querySelectorAll(".katex").forEach((k) => {
    const tex = k.querySelector("annotation")?.textContent.trim() ?? "";
    k.replaceWith(` ⟨${tex}⟩ `);
  });
  return c.textContent
    .replace(/\s+/g, " ")
    .replace(/ ([,.;:)])/g, "$1")
    .trim();
}

function blocks() {
  return [...document.querySelectorAll(BLOCKS)].filter(
    (el) =>
      !el.closest(SKIP) &&
      // the innermost block owns its text: a list item with a nested list is edited item by item
      !el.querySelector(":scope > p, :scope > ol, :scope > ul") &&
      !(el.matches("p") && el.parentElement.closest("li, figcaption, .callout, td")),
  );
}

function prepare() {
  for (const el of blocks()) {
    if (el.dataset.editOriginal !== undefined) continue;
    const original = text(el);
    if (!original) continue;
    el.dataset.editOriginal = original;
    el.contentEditable = "true";
    el.spellcheck = true;
    el.querySelectorAll(".katex, .katex-display, a, .sec-n").forEach(
      (k) => (k.contentEditable = "false"),
    );
    const saved = edits[original];
    if (saved) {
      el.innerHTML = saved.html;
      el.classList.add("edit-changed");
    }
  }
  count();
}

function record(el) {
  const original = el.dataset.editOriginal;
  const edited = text(el);
  if (edited === original) {
    delete edits[original];
    el.classList.remove("edit-changed");
  } else {
    edits[original] = {
      chapter: el.closest(".chapter")?.id ?? "hero",
      section: el.closest("section[id]:not(.chapter)")?.id ?? null,
      original,
      edited,
      html: el.innerHTML,
    };
    el.classList.add("edit-changed");
  }
  count("unsaved");
  clearTimeout(timer);
  timer = setTimeout(save, SAVE_DELAY);
}

async function save() {
  try {
    const response = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.values(edits), null, 2),
    });
    if (!response.ok) throw new Error(response.status);
    count("saved");
  } catch (e) {
    count(`not saved (${e.message}): is the dev server running?`);
  }
}

function count(state = "saved") {
  const n = Object.keys(edits).length;
  status.textContent = `Edit mode · ${n} block${n === 1 ? "" : "s"} edited · ${state}`;
}

function toolbar() {
  status = document.createElement("div");
  status.className = "edit-bar";
  status.setAttribute("role", "status");
  document.body.append(status);
  const style = document.createElement("style");
  style.textContent = `
    .edit-bar { position: fixed; right: 16px; bottom: 16px; z-index: 1000; padding: 6px 12px;
      border-radius: 6px; background: var(--dv-ink, #2a2723); color: var(--dv-bg, #faf8f3);
      font: 13px system-ui, sans-serif; }
    [data-edit-original] { outline: 1px dashed transparent; border-radius: 2px; }
    [data-edit-original]:hover { outline-color: rgba(196, 128, 28, 0.5); }
    [data-edit-original]:focus { outline: 2px solid #c4801c; }
    .edit-changed { background: rgba(196, 128, 28, 0.12); }`;
  document.head.append(style);
}

export async function startEditMode() {
  toolbar();
  try {
    const saved = await (await fetch(ENDPOINT)).json();
    edits = Object.fromEntries(saved.map((e) => [e.original, e]));
  } catch {
    edits = {};
  }
  document.addEventListener("input", (e) => {
    const el = e.target.closest?.("[data-edit-original]");
    if (el) record(el);
  });
  // Paste plain text only, so no styling from elsewhere enters the blocks
  document.addEventListener("paste", (e) => {
    if (!e.target.closest?.("[data-edit-original]")) return;
    e.preventDefault();
    document.execCommand("insertText", false, e.clipboardData.getData("text/plain"));
  });
  // Content arrives asynchronously (species data, lazy figures): prepare new blocks as they appear
  new MutationObserver(() => {
    clearTimeout(prepare.timer);
    prepare.timer = setTimeout(prepare, 300);
  }).observe(document.body, { childList: true, subtree: true });
  prepare();
}
