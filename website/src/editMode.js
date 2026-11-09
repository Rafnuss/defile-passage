// Edit mode for the methods guide (dev server only, `?edit` in the URL): the prose becomes
// editable in place, and every edited block is saved through the dev server to
// logs/guide-edits.json (`guideEdits` in vite.config.js), from where it is carried back into the
// .vue templates. The source is never written from here.
//
// Review notes (logs/guide-notes.json, written by Claude) are shown under the passage they are
// about, each with a box for a reply, saved through the same dev server.
//
// A block is keyed by its original text (maths as TeX between ⟨ ⟩), so edits survive a reload:
// on load, a block whose original text has a saved edit gets the edited version back.

const ENDPOINT = "/__guide-edits";
const NOTES_ENDPOINT = "/__guide-notes";
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
const SKIP =
  ".readout, .widget .row, .day-breakdown, .validation-metrics, .eq, .contents, .review-note";
// Where a note goes: the first of these in its section whose text contains the note's `find`
const NOTE_ANCHORS = "h5, h6, p, li, figure, .callout, table, details";
const SAVE_DELAY = 800; // ms after the last keystroke

let edits = {}; // original text -> {original, edited, html, chapter, section}
let notes = []; // {id, section, find?, topic, note, reply}
let notesTimer = null;
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

// The block a note follows: in its section (an element id), the first anchor containing `find`,
// else the section's heading; a list item or table cell gives way to its list or table
function noteAnchor(note) {
  const section = document.getElementById(note.section);
  if (!section) return null;
  const all = [...section.querySelectorAll(NOTE_ANCHORS)].filter(
    (el) => !el.closest(".review-note"),
  );
  const hit = note.find ? all.find((el) => el.textContent.includes(note.find)) : null;
  // a section id may sit on a paragraph itself (`coverage-m-profile`)
  const el = hit ?? (section.matches(NOTE_ANCHORS) ? section : section.querySelector("h5, h6, h2"));
  return el?.closest("ol, ul, table, figure, .callout") ?? el;
}

function placeNotes() {
  for (const note of notes) {
    if (document.getElementById(`note-${note.id}`)) continue;
    const anchor = noteAnchor(note);
    if (!anchor) continue;
    const box = document.createElement("div");
    box.id = `note-${note.id}`;
    box.className = "review-note";
    box.contentEditable = "false";
    const head = document.createElement("div");
    head.className = "review-note-head";
    head.textContent = `Note ${note.id} · ${note.topic}`;
    const body = document.createElement("div");
    body.className = "review-note-body";
    body.textContent = note.note;
    const reply = document.createElement("textarea");
    reply.placeholder = "Your reply (saved as you type)";
    reply.value = note.reply ?? "";
    reply.rows = Math.max(2, reply.value.split("\n").length);
    reply.addEventListener("input", () => {
      note.reply = reply.value;
      count("unsaved");
      clearTimeout(notesTimer);
      notesTimer = setTimeout(saveNotes, SAVE_DELAY);
    });
    box.append(head, body, reply);
    anchor.after(box);
  }
}

async function saveNotes() {
  try {
    const response = await fetch(NOTES_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(notes, null, 2),
    });
    if (!response.ok) throw new Error(response.status);
    count("saved");
  } catch (e) {
    count(`not saved (${e.message}): is the dev server running?`);
  }
}

function count(state = "saved") {
  const n = Object.keys(edits).length;
  const replied = notes.filter((x) => x.reply?.trim()).length;
  status.textContent =
    `Edit mode · ${n} block${n === 1 ? "" : "s"} edited · ` +
    `${replied}/${notes.length} notes answered · ${state}`;
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
    .edit-changed { background: rgba(196, 128, 28, 0.12); }
    .review-note { margin: 0.6rem 0 1rem; padding: 0.6rem 0.8rem; border-left: 4px solid #3d6a8f;
      background: #eef3f8; border-radius: 4px; font: 14px/1.45 system-ui, sans-serif; }
    .review-note-head { font-weight: 600; color: #3d6a8f; margin-bottom: 0.25rem; }
    .review-note-body { white-space: pre-line; color: #24211d; }
    .review-note textarea { width: 100%; margin-top: 0.5rem; padding: 0.4rem; border: 1px solid #b3c7d8;
      border-radius: 4px; font: inherit; background: #fff; resize: vertical; }`;
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
  try {
    notes = await (await fetch(NOTES_ENDPOINT)).json();
  } catch {
    notes = [];
  }
  document.addEventListener("input", (e) => {
    if (e.target.closest?.(".review-note")) return; // a reply, saved with the notes
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
    prepare.timer = setTimeout(() => (prepare(), placeNotes()), 300);
  }).observe(document.body, { childList: true, subtree: true });
  prepare();
  placeNotes();
}
