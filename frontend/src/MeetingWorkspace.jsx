import React, { useCallback, useEffect, useMemo, useState } from "react";

const API = "http://127.0.0.1:8000";

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  return body;
}

function dateLabel(value) {
  if (!value) return "No deadline set";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.notifications)) return value.notifications;
  return [];
}

function SummaryList({ title, items }) {
  if (!Array.isArray(items) || items.length === 0) return null;
  return <div className="meeting-summary-block"><strong>{title}</strong><ul>{items.map((item, i) => <li key={`${title}-${i}`}>{typeof item === "string" ? item : item?.text || item?.question || JSON.stringify(item)}</li>)}</ul></div>;
}

function localInputValue(date) {
  const pad = value => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Only suggest a date when the AI extracted an explicit deadline phrase.
// Never infer dates from unrelated words in the task description or source quote.
function suggestDeadline(item) {
  const phrase = String(item.deadline_text || "").trim().toLowerCase();
  if (!phrase) return "";

  const now = new Date();
  const target = new Date(now);
  target.setSeconds(0, 0);
  let matched = false;

  // Handle relative calendar phrases before weekday matching ("end of next week"
  // contains "Friday" in some transcripts and must not be interpreted as this Friday).
  if (/\btoday\b/.test(phrase)) {
    matched = true;
  } else if (/\btomorrow\b/.test(phrase)) {
    target.setDate(target.getDate() + 1);
    matched = true;
  } else if (/\bend of next week\b|\bby the end of next week\b/.test(phrase)) {
    const daysUntilMonday = (8 - now.getDay()) % 7 || 7;
    target.setDate(target.getDate() + daysUntilMonday + 4); // Friday of next week
    matched = true;
  } else {
    const weekdays = [
      ["sunday", 0], ["monday", 1], ["tuesday", 2], ["wednesday", 3],
      ["thursday", 4], ["friday", 5], ["saturday", 6],
    ];
    const found = weekdays.find(([day]) => new RegExp(`\\b${day}\\b`).test(phrase));
    if (found) {
      const delta = (found[1] - now.getDay() + 7) % 7 || 7;
      target.setDate(target.getDate() + delta);
      if (/\bnext\s+(week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/.test(phrase) && delta < 7) {
        target.setDate(target.getDate() + 7);
      }
      matched = true;
    }
  }

  if (!matched) return "";

  // Preserve explicit times such as 10 AM, 12:30 PM, or 3 p.m.
  const timeMatch = phrase.match(/\b(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b/i);
  if (timeMatch) {
    let hour = Number(timeMatch[1]);
    const minute = Number(timeMatch[2] || 0);
    const meridiem = timeMatch[3].replace(/\./g, "").toLowerCase();
    if (hour < 1 || hour > 12 || minute > 59) return "";
    if (meridiem === "am") hour = hour === 12 ? 0 : hour;
    else hour = hour === 12 ? 12 : hour + 12;
    target.setHours(hour, minute, 0, 0);
  } else if (/\bnoon\b/.test(phrase)) {
    target.setHours(12, 0, 0, 0);
  } else if (/\bmidnight\b/.test(phrase)) {
    target.setHours(0, 0, 0, 0);
  } else if (/\bmorning\b/.test(phrase)) {
    target.setHours(9, 0, 0, 0);
  } else if (/\bafternoon\b/.test(phrase)) {
    target.setHours(15, 0, 0, 0);
  } else if (/\bevening\b|\btonight\b/.test(phrase)) {
    target.setHours(17, 0, 0, 0);
  } else {
    target.setHours(17, 0, 0, 0);
  }

  // Do not silently move a past "today at 10 AM" deadline to another day/week.
  // Leave the field blank so the user must choose the intended date/time.
  if (target <= now) return "";
  return localInputValue(target);
}

function ActionCard({ item, onConfirm, onStatus, busy }) {
  const [deadline, setDeadline] = useState("");
  const needsConfirmation = Boolean(item.needs_confirmation);
  const status = String(item.status || "pending").toLowerCase();
  const deadlineValue = item.due_at ? localInputValue(new Date(item.due_at)) : "";
  const suggestedValue = suggestDeadline(item);
  const selectedDeadline = deadline || deadlineValue || suggestedValue;
  return (
    <article className="meeting-item">
      <div className="meeting-item-head">
        <div><h3>{item.action_text || "Follow-up action"}</h3><p>Deadline: {dateLabel(item.due_at)}</p></div>
        <span className={`meeting-tag ${status}`}>{status}</span>
      </div>
      {item.source_quote && <p><strong>Source:</strong> “{item.source_quote}”</p>}
      {needsConfirmation && status === "pending" && (
        <div className="meeting-deadline">
          <label className="meeting-field" style={{ margin: 0 }}>Confirm deadline{suggestedValue && !deadlineValue && <small className="deadline-suggestion">Suggested from transcript — verify before confirming</small>}<input type="datetime-local" value={selectedDeadline} onChange={e => setDeadline(e.target.value)} /></label>
          <button className="meeting-button primary" disabled={busy || !selectedDeadline} onClick={() => onConfirm(item.id, new Date(selectedDeadline).toISOString())}>Confirm date</button>
        </div>
      )}
      <div className="meeting-actions" style={{ marginTop: 10 }}>
        {status !== "completed" && <button className="meeting-button" disabled={busy} onClick={() => onStatus(item.id, "completed")}>Mark completed</button>}
        {status !== "cancelled" && status !== "completed" && <button className="meeting-button" disabled={busy} onClick={() => onStatus(item.id, "cancelled")}>Cancel task</button>}
        {status !== "pending" && <button className="meeting-button" disabled={busy} onClick={() => onStatus(item.id, "pending")}>Reopen</button>}
      </div>
    </article>
  );
}

export default function MeetingWorkspace() {
  const [title, setTitle] = useState("");
  const [transcript, setTranscript] = useState("");
  const [consent, setConsent] = useState(false);
  const [notes, setNotes] = useState([]);
  const [items, setItems] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [filter, setFilter] = useState("pending");
  const [selectedMeeting, setSelectedMeeting] = useState("all");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [notesData, itemData, notificationData] = await Promise.all([
        api("/meeting-notes"), api("/meeting-action-items"), api("/notifications?unread_only=false"),
      ]);
      setNotes(asArray(notesData));
      setItems(asArray(itemData));
      setNotifications(asArray(notificationData));
      setError("");
    } catch (e) {
      setError(`${e.message}. Check that the DealPilot backend is running at ${API}.`);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const visibleItems = useMemo(() => items.filter(item =>
    (filter === "all" || String(item.status || "pending").toLowerCase() === filter) &&
    (selectedMeeting === "all" || String(item.meeting_note_id) === selectedMeeting)
  ), [items, filter, selectedMeeting]);

  // Keep each meeting's tasks in its own title group instead of one long mixed list.
  const groupedItems = useMemo(() => {
    const noteById = new Map(notes.map(note => [String(note.id), note]));
    const groups = new Map();
    for (const item of visibleItems) {
      const id = String(item.meeting_note_id ?? "unknown");
      const note = noteById.get(id);
      const group = groups.get(id) || {
        id,
        title: note?.title || `Meeting #${id}`,
        created_at: note?.created_at || null,
        items: [],
      };
      group.items.push(item);
      groups.set(id, group);
    }
    return [...groups.values()].sort((a, b) => {
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return dateB - dateA || a.title.localeCompare(b.title);
    });
  }, [visibleItems, notes]);
  const unreadCount = notifications.filter(n => !n.is_read).length;

  async function analyze() {
    if (!transcript.trim()) { setError("Paste a meeting transcript before analyzing."); return; }
    if (!consent) { setError("Confirm that you have permission to process this meeting transcript."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await api("/meeting-notes/analyze", { method: "POST", body: JSON.stringify({ transcript: transcript.trim() }) });
      setAnalysis(result);
      setMessage("Analysis complete. Review the extracted information, then save the meeting to keep it.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function saveMeeting() {
    if (!title.trim()) { setError("Enter a meeting title before saving."); return; }
    if (!transcript.trim()) { setError("Paste a meeting transcript before saving."); return; }
    if (!consent) { setError("Confirm that you have permission to process this meeting transcript."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await api("/meeting-notes", { method: "POST", body: JSON.stringify({ title: title.trim(), transcript: transcript.trim(), consent_confirmed: true }) });
      setAnalysis(result.analysis || null);
      setMessage(`${result.already_saved ? `“${result.title || title.trim()}” was already saved; no duplicate tasks were created.` : `Saved “${result.title || title.trim()}” and created ${result.action_items_created ?? result.action_items?.length ?? 0} follow-up task(s).`}`);
      setTitle(""); setTranscript(""); setConsent(false);
      await refresh();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function confirmDeadline(id, dueAt) {
    setBusy(true); setError(""); setMessage("");
    try {
      await api(`/meeting-action-items/${id}/confirm`, { method: "PATCH", body: JSON.stringify({ due_at: dueAt }) });
      setMessage("Deadline confirmed. The backend has scheduled any applicable in-app reminders.");
      await refresh();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function changeStatus(id, status) {
    setBusy(true); setError(""); setMessage("");
    try {
      await api(`/meeting-action-items/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
      setMessage(`Task marked ${status}.`); await refresh();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function markRead(notification) {
    try { await api(`/notifications/${notification.id}/read`, { method: "PATCH" }); await refresh(); }
    catch (e) { setError(e.message); }
  }

  const keyPoints = analysis?.key_points || analysis?.keyPoints || analysis?.summary_points || [];
  const questions = analysis?.follow_up_questions || analysis?.followup_questions || analysis?.questions || [];
  const commitments = analysis?.commitments || [];
  const summary = analysis?.summary || analysis?.meeting_summary || analysis?.overview;

  return (
    <div className="meeting-workspace">
      {error && <div className="meeting-alert error">{error}</div>}
      {message && <div className="meeting-alert success">{message}</div>}
      <div className="meeting-grid">
        <section className="meeting-panel">
          <h2>Analyze a meeting</h2>
          <p className="meeting-muted">Paste notes or a transcript. AI extracts a summary and possible commitments; review them before relying on them.</p>
          <label className="meeting-field">Meeting title<input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Acme renewal discussion" maxLength={240} /></label>
          <label className="meeting-field">Transcript<textarea value={transcript} onChange={e => setTranscript(e.target.value)} placeholder="Paste the meeting transcript here…" maxLength={30000} /></label>
          <label className="meeting-consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span>I have permission to process and store this transcript, and any sensitive information has been handled appropriately.</span></label>
          <div className="meeting-actions">
            <button className="meeting-button" disabled={busy} onClick={analyze}>{busy ? "Working…" : "Analyze transcript"}</button>
            <button className="meeting-button primary" disabled={busy} onClick={saveMeeting}>{busy ? "Saving…" : "Analyze & save meeting"}</button>
          </div>
          <p className="meeting-muted" style={{ marginTop: 12, marginBottom: 0 }}>Transcript limit: 30,000 characters. Saving runs analysis again and stores the meeting plus extracted follow-up tasks.</p>
        </section>
        <section className="meeting-panel">
          <h2>AI analysis preview</h2>
          <p className="meeting-muted">This preview is not saved until you choose “Analyze & save meeting”. Verify names, commitments and dates.</p>
          {!analysis ? <div className="meeting-empty">Run an analysis to see the summary, key points and follow-up questions.</div> : (
            <div className="meeting-summary">
              {summary && <div className="meeting-summary-block"><strong>Summary</strong><p className="meeting-muted" style={{ margin: 0 }}>{summary}</p></div>}
              <SummaryList title="Key points" items={keyPoints} />
              <SummaryList title="Commitments detected" items={commitments.map(c => typeof c === "string" ? c : `${c.owner && c.owner !== "Unknown" ? `${c.owner}: ` : ""}${c.action || c.commitment || "Possible commitment"}${c.deadline_text ? ` — ${c.deadline_text}` : ""}`)} />
              <SummaryList title="Suggested follow-up questions" items={questions} />
              {!summary && !keyPoints.length && !commitments.length && !questions.length && <pre style={{ whiteSpace: "pre-wrap", color: "#aebbd2", fontSize: 12 }}>{JSON.stringify(analysis, null, 2)}</pre>}
            </div>
          )}
        </section>
      </div>

      <section className="meeting-panel">
        <div className="meeting-item-head"><div><h2>Follow-up tasks by meeting</h2><p className="meeting-muted" style={{ margin: "5px 0 0" }}>Tasks are grouped under their meeting title. Start with Pending to see only work that still needs attention. Confirm a deadline only after checking it; mark a task completed when the work is done.</p></div><span className="meeting-tag">{visibleItems.length} shown · {items.length} total</span></div>
        <label className="meeting-field" style={{ maxWidth: 420, marginTop: 14 }}>Meeting title
          <select value={selectedMeeting} onChange={e => setSelectedMeeting(e.target.value)}>
            <option value="all">All meeting titles</option>
            {notes.map(note => <option key={note.id} value={String(note.id)}>{note.title || `Meeting #${note.id}`} — #{note.id}</option>)}
          </select>
        </label>
        <div className="meeting-filter" style={{ marginTop: 15 }}>
          {[['pending','Pending'],['all','All tasks'],['completed','Completed'],['cancelled','Cancelled']].map(([value,label]) => <button key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{label}</button>)}
        </div>
        {loading ? <div className="meeting-empty">Loading meeting tasks…</div> : groupedItems.length === 0 ? <div className="meeting-empty">No {filter === "all" ? "tasks" : filter + " tasks"} found for this view. Choose another status or save a meeting transcript.</div> : (
          <div className="meeting-list" style={{ marginTop: 14 }}>
            {groupedItems.map(group => (
              <details className="meeting-group" key={group.id} open={selectedMeeting !== "all" || groupedItems.length === 1} style={{ border: "1px solid var(--meeting-border, #d8dee9)", borderRadius: 12, padding: 12 }}>
                <summary style={{ cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, listStylePosition: "inside" }}>
                  <span><strong>{group.title}</strong><small style={{ display: "block", margin: "5px 0 0 22px", opacity: 0.72 }}>{group.created_at ? dateLabel(group.created_at) : `Meeting #${group.id}`} · {group.items.length} {filter === "pending" ? "pending" : "matching"} task(s)</small></span>
                  <span className="meeting-tag">#{group.id}</span>
                </summary>
                <div className="meeting-list" style={{ marginTop: 12 }}>
                  {group.items.map(item => <ActionCard key={item.id} item={item} onConfirm={confirmDeadline} onStatus={changeStatus} busy={busy} />)}
                </div>
              </details>
            ))}
          </div>
        )}
      </section>

      <div className="meeting-grid">
        <section className="meeting-panel">
          <div className="meeting-item-head"><div><h2>In-app reminders</h2><p className="meeting-muted" style={{ margin: "5px 0 0" }}>Scheduled reminders appear here when the backend processor creates them.</p></div><span className="meeting-tag">{unreadCount} unread</span></div>
          <div className="meeting-list" style={{ marginTop: 14 }}>
            {notifications.length === 0 ? <div className="meeting-empty">No reminder records found.</div> : notifications.map(n => <article className="meeting-item meeting-notification" key={n.id}><div className={!n.is_read ? "unread" : ""}><h3>{n.reminder_type === "24_hours" ? "24-hour reminder" : n.reminder_type === "30_minutes" ? "30-minute reminder" : (n.reminder_type || "Reminder")}</h3><p>Scheduled: {dateLabel(n.scheduled_for)}</p><p>{n.action_item?.action_text || n.action_text || `Action item #${n.action_item_id}`}</p></div>{!n.is_read && <button className="meeting-button" onClick={() => markRead(n)}>Mark read</button>}</article>)}
          </div>
        </section>
        <section className="meeting-panel">
          <div className="meeting-item-head"><div><h2>Saved meetings</h2><p className="meeting-muted" style={{ margin: "5px 0 0" }}>Stored transcripts and AI analysis in your existing database.</p></div><span className="meeting-tag">{notes.length} saved</span></div>
          <div className="meeting-list" style={{ marginTop: 14 }}>
            {notes.length === 0 ? <div className="meeting-empty">No saved meetings yet.</div> : notes.map(note => <article className="meeting-item" key={note.id}><div className="meeting-item-head"><div><h3>{note.title || `Meeting #${note.id}`}</h3><p>{dateLabel(note.created_at)}</p></div><span className="meeting-tag">#{note.id}</span></div>{note.analysis?.summary && <p>{note.analysis.summary}</p>}<button className="meeting-button" onClick={() => { setTitle(note.title || ""); setTranscript(note.transcript || ""); setAnalysis(note.analysis || null); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Load into editor</button></article>)}
          </div>
          <div className="meeting-actions" style={{ marginTop: 13 }}><button className="meeting-button" disabled={loading || busy} onClick={refresh}>Refresh data</button></div>
        </section>
      </div>
    </div>
  );
}
