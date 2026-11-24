import {
  defaults,
  dayAdd,
  gap,
  weekday,
  DAYS,
  gradeName,
  unit,
  pending,
  duePeriod,
  OUTCOMES,
  RECOVERY,
} from "./model.js";
import { esc, field, select, profileFields, preferences } from "./forms.js";

const $ = (s) => document.querySelector(s),
  main = $("#app"),
  top = $("#preferences"),
  dialog = $("#dialog");
const browserZone = () =>
  Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const dateLabel = (
  d,
  opts = { weekday: "short", month: "short", day: "numeric" },
) =>
  new Date(d + "T12:00:00Z").toLocaleDateString(undefined, {
    ...opts,
    timeZone: "UTC",
  });
const btn = (text, cmd, style = "", attrs = "") =>
  '<button type="button" data-act="' +
  cmd +
  '" class="' +
  style +
  '" ' +
  attrs +
  ">" +
  esc(text) +
  "</button>";
let token = "",
  state,
  revision,
  today,
  draft,
  view = "Calendar",
  mode = "Week",
  selected = "",
  modal = "",
  editing = "",
  busy = false,
  noticeTimer;
let defaultDisplay = defaults(),
  checkDay = "",
  displayEdits = {};
function toast(text) {
  $("#message").textContent = text;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => ($("#message").textContent = ""), 4200);
}
function lock() {
  token = "";
  state = null;
  draft = null;
  revision = null;
  selected = "";
  checkDay = "";
  view = "Calendar";
  mode = "Week";
  defaultDisplay = defaults();
  displayEdits = {};
  closeModal();
  loginView();
}
function loginView() {
  top.innerHTML = preferences(defaultDisplay);
  main.innerHTML =
    '<section class="login panel"><img src="/project-514.svg" alt="Project 5.14 climbing training"><h1>Open your training log</h1><form id="login">' +
    field(
      "App password",
      '<input type="password" name="password" autocomplete="current-password" required>',
      "Enter the private password you chose during setup.",
    ) +
    '<p class="error" role="alert"></p><div class="actions"><button class="primary">Unlock</button></div></form></section>';
}
async function api(path, body) {
  const response = await fetch("/api/" + path, {
    method: body ? "POST" : "GET",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token,
      "X-Time-Zone": browserZone(),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && token) lock();
    if (response.status === 409) {
      closeModal();
      await load();
      toast("Loaded the latest plan. Reapply your edit.");
    }
    throw Error(data.error || "Couldn’t save. Please retry.");
  }
  return data;
}
function accept(data) {
  state = data.state;
  revision = data.revision;
  today = data.today;
}
async function load() {
  accept(await api("state"));
  if (state.profile && Object.keys(displayEdits).length) {
    await save({
      action: "display",
      units: state.profile.units,
      scale: state.profile.scale,
      ...displayEdits,
    });
  }
  displayEdits = {};
  startView();
}
function startView() {
  if (!state.profile?.name) {
    view = "Profile";
    draft = { ...(state.profile || defaultDisplay) };
  }
  if (!selected) selected = withinBlock(today);
  render();
  if (view !== "Profile") prompts();
}
function withinBlock(d) {
  return !state?.start
    ? d
    : d < state.start
      ? state.start
      : d > dayAdd(state.start, 83)
        ? dayAdd(state.start, 83)
        : d;
}
async function save(body) {
  accept(await api("state", { ...body, revision }));
}
function closeModal() {
  if (dialog.open) dialog.close();
  dialog.innerHTML = "";
  modal = "";
}
function showModal(kind, title, body) {
  modal = kind;
  dialog.innerHTML =
    '<div class="modalhead"><h2 id="dialog-title">' +
    esc(title) +
    "</h2></div>" +
    body +
    '<p class="error" role="alert"></p>';
  if (!dialog.open) dialog.showModal();
}
function profileForm(review = false) {
  return (
    '<form id="profile-form">' +
    (review ? '<div class="controls">' + preferences(draft) + "</div>" : "") +
    profileFields(draft, browserZone(), review) +
    '<p class="error" role="alert"></p><div class="actions"><button class="primary">' +
    (review
      ? "Save progress update"
      : state.profile
        ? "Save profile"
        : "Create my 12-week plan") +
    "</button>" +
    "</div></form>"
  );
}
function profileView() {
  if (!draft) draft = { ...(state.profile || defaultDisplay) };
  return (
    '<h1>Your training profile</h1><p class="intro">Allow a few minutes for this one-time setup. You can change any answer later in Profile.</p>' +
    profileForm() +
    (state.profile?.name
      ? '<section class="panel"><h2>Training log</h2><div class="actions">' +
        btn(state.paused ? "Resume training" : "Pause training", "pause") +
        (state.hold
          ? btn("I’ve addressed the concern · resume gently", "resumeHold")
          : "") +
        btn("Export my training log", "export") +
        "</div></section>"
      : "")
  );
}
function render() {
  const p =
    draft && (view === "Profile" || modal === "review")
      ? draft
      : state.profile || defaultDisplay;
  top.innerHTML = preferences(p);
  const has = !!state.profile?.name;
  const nav =
    '<nav aria-label="Training log">' +
    (has
      ? ["Calendar", "Progress", "Profile"]
          .map((v) => btn(v, "nav-" + v, v === view ? "active" : ""))
          .join("")
      : "") +
    btn("Lock app", "lock") +
    "</nav>";
  main.innerHTML =
    nav +
    (view === "Profile"
      ? profileView()
      : view === "Progress"
        ? progressView()
        : calendarView()) +
    '<p class="error" role="alert"></p>';
}
function metric(key, val) {
  const [suffix, factor] = unit(key, state.profile);
  return Number((val / factor).toFixed(1)) + " " + suffix;
}
function workout(d) {
  const plan = state.plans[d],
    r = state.feedback[d];
  if (!plan) return "";
  const tag = (s) => '<span class="tag">' + esc(s) + "</span>";
  const tags = [plan.kind, plan.minutes + " min", plan.phase];
  if (plan.route != null)
    tags.push("Routes around " + gradeName(plan.route, state.profile));
  if (plan.distance != null) tags.push(metric("volume", plan.distance));
  if (plan.gain != null) tags.push(metric("gain", plan.gain) + " ascent");
  return (
    '<article class="panel work"><p class="kicker">' +
    esc(dateLabel(d, { weekday: "long", month: "long", day: "numeric" })) +
    "</p><h2>" +
    esc(plan.title) +
    '</h2><div class="tags">' +
    tags.map(tag).join("") +
    "</div><p>" +
    esc(plan.cue) +
    "</p>" +
    (plan.extras || []).map((x) => "<p>" + esc(x) + "</p>").join("") +
    (plan.reason ? '<p class="muted">' + esc(plan.reason) + "</p>" : "") +
    (plan.fuel ? "<p>Fueling · " + esc(plan.fuel) + "</p>" : "") +
    (d < today || r
      ? "<p><strong>" +
        esc(r ? r.outcome : "Assumed completed as directed") +
        "</strong>" +
        esc(r?.note ? " · " + r.note : "") +
        "</p>"
      : "") +
    '<div class="actions">' +
    (d <= today
      ? btn(
          r ? "Edit feedback" : "Report performance",
          "report",
          "",
          "data-day=" + d,
        )
      : "") +
    (d === today && plan.kind !== "Rest" ? btn("Rest today", "rest") : "") +
    "</div></article>"
  );
}
function weekRow(w) {
  const start = dayAdd(state.start, w * 7);
  const cells = Array.from({ length: 7 }, (_, i) => {
    const d = dayAdd(start, i),
      p = state.plans[d];
    return (
      '<button class="cell ' +
      (p.kind === "Rest" ? "rest" : p.kind === "Climb" ? "" : "aerobic") +
      '" data-act="day" data-day="' +
      d +
      '" aria-label="' +
      esc(dateLabel(d) + " · " + p.title) +
      '"' +
      (d === today ? ' aria-current="date"' : "") +
      "><span>" +
      DAYS[weekday(d)].slice(0, 3) +
      "</span><strong>" +
      esc(dateLabel(d, { month: "short", day: "numeric" })) +
      "</strong><span>" +
      esc(p.kind) +
      (p.minutes ? " · " + p.minutes + "m" : "") +
      "</span></button>"
    );
  }).join("");
  return (
    '<section class="week"><div class="weekheading"><strong>Week ' +
    (w + 1) +
    " · " +
    esc(state.plans[start].phase) +
    "</strong><small>" +
    esc(dateLabel(start, { month: "short", day: "numeric" })) +
    " – " +
    esc(dateLabel(dayAdd(start, 6), { month: "short", day: "numeric" })) +
    '</small></div><div class="days">' +
    cells +
    "</div></section>"
  );
}
function calendarView() {
  const end = dayAdd(state.start, 83),
    w = Math.floor(gap(withinBlock(selected), state.start) / 7);
  const heading =
    "<h1>" +
    esc(state.profile.name) +
    '’s training calendar</h1><p class="intro">' +
    esc(dateLabel(state.start, { month: "long", day: "numeric" })) +
    " – " +
    esc(dateLabel(end, { month: "long", day: "numeric", year: "numeric" })) +
    "</p>";
  const modes =
    '<div class="controls" aria-label="Calendar view">' +
    ["Day", "Week", "12 weeks"]
      .map((v) =>
        btn(
          v,
          "mode",
          v === mode ? "active" : "",
          "data-mode=" + (v === "12 weeks" ? "block" : v),
        ),
      )
      .join("") +
    "</div>";
  const step = mode === "Week" ? 7 : 1;
  const controls =
    mode === "12 weeks"
      ? ""
      : '<div class="controls">' +
        btn(
          "Previous",
          "move",
          "",
          "data-step=-" +
            step +
            ((mode === "Week" ? w === 0 : selected <= state.start)
              ? " disabled"
              : ""),
        ) +
        '<input type="date" class="datepick" aria-label="Calendar date" name="calendarDate" min="' +
        state.start +
        '" max="' +
        end +
        '" value="' +
        selected +
        '">' +
        btn(
          "Next",
          "move",
          "",
          "data-step=" +
            step +
            ((mode === "Week" ? w === 11 : selected >= end) ? " disabled" : ""),
        ) +
        btn("Today", "today") +
        "</div>";
  return (
    heading +
    (state.hold || state.paused
      ? '<p class="panel">Training is ' +
        (state.hold
          ? "on hold. Review your recovery in Profile."
          : "paused. Resume in Profile when ready.") +
        "</p>"
      : "") +
    modes +
    controls +
    (mode === "12 weeks"
      ? Array.from({ length: 12 }, (_, i) => weekRow(i)).join("")
      : (mode === "Week" ? weekRow(w) : "") + workout(selected)) +
    (today > end ? btn("Start next 12-week block", "nextBlock", "primary") : "")
  );
}
function progressView() {
  const p = state.profile,
    dates = Object.keys(state.feedback).sort().reverse();
  return (
    '<h1>Progress</h1><p class="intro">Repeatable grade ' +
    esc(gradeName(p.grade, p)) +
    " · Goal " +
    esc(gradeName(p.target, p)) +
    '</p><section class="panel"><h2>Goal & benchmark reviews</h2><p>Every two weeks, revisit a familiar route and update your goals. These reviews are optional. Your answers improve the fit of the remaining workouts.</p>' +
    btn("Update goals & benchmark", "review", "primary") +
    Object.entries(state.reviews)
      .reverse()
      .map(
        ([d, r]) =>
          '<div class="reviewrow"><strong>' +
          esc(d) +
          "</strong> · " +
          esc(gradeName(r.grade, p)) +
          " " +
          esc(r.route) +
          " " +
          esc(r.result) +
          "</div>",
      )
      .join("") +
    '</section><section class="panel"><h2>Performance log</h2><p>Report or correct any previous plan day. Blank days count as completed as directed.</p><div class="controls"><select aria-label="Previous day" id="past-day">' +
    Object.keys(state.plans)
      .filter((d) => d <= today)
      .sort()
      .reverse()
      .map((d) => "<option>" + d + "</option>")
      .join("") +
    "</select>" +
    btn(
      "Open feedback",
      "past-report",
      "",
      Object.keys(state.plans).some((d) => d <= today) ? "" : "disabled",
    ) +
    "</div>" +
    dates
      .map(
        (d) =>
          '<div class="reviewrow">' +
          esc(dateLabel(d)) +
          " · " +
          esc(state.feedback[d].outcome) +
          " · " +
          esc(state.feedback[d].note) +
          "</div>",
      )
      .join("") +
    "</section>"
  );
}
function prompts() {
  if (dialog.open || !state.profile?.name) return;
  if (duePeriod(state, today) > state.reviewPeriod) {
    openReview();
    return;
  }
  const missing = pending(state, today);
  if (missing.length)
    showModal(
      "pending",
      "How did your training go?",
      '<p>Feedback is optional. Days you leave blank count as completed as directed. A report helps adjust your remaining workouts.</p><ul class="daylist">' +
        missing
          .map(
            (d) =>
              "<li><span>" +
              esc(dateLabel(d)) +
              "<small>" +
              esc(state.plans[d].title) +
              "</small></span>" +
              btn("Report", "report", "", "data-day=" + d) +
              "</li>",
          )
          .join("") +
        "</ul>" +
        btn("Continue with plan", "skip-feedback", "primary"),
    );
}
function openReview() {
  draft = { ...state.profile, route: "", result: "" };
  reviewForm();
}
function reviewForm() {
  showModal(
    "review",
    "Goal & benchmark review",
    "<p>This two-week update is optional. Updating your repeatable grade, recent volume or benchmark improves the fit of the rest of your plan. Keep any answers that still fit.</p>" +
      btn("Skip this review", "skip-review") +
      profileForm(true),
  );
}
function openReport(d) {
  editing = d;
  const r = state.feedback[d] || {};
  showModal(
    "report",
    "Performance · " + dateLabel(d),
    "<p>" +
      esc(state.plans[d].title) +
      " · " +
      state.plans[d].minutes +
      ' min planned. This report is optional.</p><form id="report"><div class="grid">' +
      field(
        "Outcome",
        select("outcome", OUTCOMES, r.outcome || OUTCOMES[0]),
        "Choose how the workout went, for example Partial if you stopped early.",
      ) +
      field(
        "Recovery",
        select("recovery", RECOVERY, r.recovery || RECOVERY[0]),
        "Choose how you felt afterward, for example Tired or sore.",
      ) +
      field(
        "Actual minutes (optional)",
        '<input type="number" min="0" max="1440" name="minutes" value="' +
          esc(r.minutes) +
          '">',
        "Enter the duration you completed, for example 25.",
      ) +
      field(
        "Notes (optional)",
        '<input name="note" maxlength="300" value="' + esc(r.note) + '">',
        "Record something to revisit, for example footwork faded near the top.",
      ) +
      '</div><div class="actions"><button class="primary">Save feedback</button>' +
      btn("Cancel", "cancel") +
      "</div></form>",
  );
}
function error(e) {
  const box = (dialog.open ? dialog : main).querySelector(".error");
  if (box) box.textContent = e.message;
  else toast(e.message);
}
async function guarded(fn) {
  if (busy) return;
  busy = true;
  try {
    await fn();
  } catch (e) {
    error(e);
  } finally {
    busy = false;
  }
}
document.addEventListener("submit", (e) => {
  e.preventDefault();
  const form = e.target;
  const data = new FormData(form);
  guarded(async () => {
    if (form.id === "login") {
      token = (await api("login", { password: data.get("password") })).token;
      await load();
      return;
    }
    if (form.id === "profile-form") {
      const review = modal === "review";
      await save({
        action: review ? "review" : "profile",
        profile: draft,
        route: draft.route,
        result: draft.result,
      });
      draft = null;
      closeModal();
      view = "Calendar";
      selected = withinBlock(today);
      render();
      toast(
        review
          ? "Progress saved. Remaining workouts updated."
          : "Your 12-week plan is ready.",
      );
      prompts();
    } else if (form.id === "report") {
      await save({
        action: "feedback",
        date: editing,
        outcome: data.get("outcome"),
        recovery: data.get("recovery"),
        minutes:
          data.get("minutes") === "" ? null : Number(data.get("minutes")),
        note: data.get("note"),
      });
      closeModal();
      render();
      toast("Feedback saved. Remaining workouts updated.");
      prompts();
    }
  });
});
function inputValue(e) {
  const el = e.target,
    k = el.name;
  if (
    !draft ||
    !el.closest("#profile-form") ||
    !k ||
    ["units", "scale"].includes(k)
  )
    return;
  if (el.type === "checkbox")
    draft[k] = Array.from(
      el.form.querySelectorAll('input[name="' + k + '"]:checked'),
      (i) => Number(i.value),
    );
  else if (el.type === "number")
    draft[k] =
      el.value === ""
        ? null
        : Number(el.value) * Number(el.dataset.factor || 1);
  else if (["grade", "target"].includes(k)) draft[k] = Number(el.value);
  else draft[k] = el.value;
}
document.addEventListener("input", inputValue);
document.addEventListener("change", (e) => {
  const el = e.target,
    k = el.name;
  if (k === "units" || k === "scale") {
    if (!token) {
      defaultDisplay[k] = el.value;
      displayEdits[k] = el.value;
      return;
    }
    if (draft) {
      draft[k] = el.value;
      if (modal === "review") reviewForm();
      else render();
    } else
      guarded(async () => {
        await save({
          action: "display",
          units: k === "units" ? el.value : state.profile.units,
          scale: k === "scale" ? el.value : state.profile.scale,
        });
        render();
      });
  } else if (k === "sport" && draft) {
    inputValue(e);
    if (modal === "review") reviewForm();
    else render();
  } else if (k === "calendarDate" && el.value) {
    selected = withinBlock(el.value);
    render();
  }
});
document.addEventListener("click", (e) => {
  const el = e.target.closest("button[data-act]");
  if (!el) return;
  guarded(async () => {
    const a = el.dataset.act;
    if (a === "lock") {
      lock();
      return;
    }
    if (a.startsWith("nav-")) {
      view = a.slice(4);
      draft = null;
      render();
      return;
    }
    if (a === "mode") {
      mode = el.dataset.mode === "block" ? "12 weeks" : el.dataset.mode;
      render();
      return;
    }
    if (a === "day" || a === "today" || a === "move") {
      selected =
        a === "day"
          ? el.dataset.day
          : a === "today"
            ? withinBlock(today)
            : withinBlock(dayAdd(selected, Number(el.dataset.step)));
      if (a === "day") mode = "Day";
      render();
      return;
    }
    if (a === "report" || a === "past-report") {
      openReport(a === "report" ? el.dataset.day : $("#past-day").value);
      return;
    }
    if (a === "review") {
      openReview();
      return;
    }
    if (a === "cancel") {
      closeModal();
      prompts();
      return;
    }
    if (a === "skip-review" || a === "skip-feedback") {
      await save({
        action: a === "skip-review" ? "dismissReview" : "dismissFeedback",
      });
      draft = null;
      closeModal();
      render();
      prompts();
      return;
    }
    if (a === "export") {
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(state, null, 2)], {
          type: "application/json",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "project-514-training.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return;
    }
    await save({ action: a });
    draft = null;
    if (a === "nextBlock") selected = state.start;
    render();
    toast("Training plan updated.");
  });
});
dialog.addEventListener("cancel", (e) => {
  e.preventDefault();
  dialog
    .querySelector(
      '[data-act="skip-review"],[data-act="skip-feedback"],[data-act="cancel"]',
    )
    ?.click();
});
async function rollover() {
  if (!token || busy || dialog.open || view === "Profile" || document.hidden)
    return;
  const zone =
    state.profile.zone === "auto" ? browserZone() : state.profile.zone;
  const date = new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  if (date !== today && date !== checkDay) {
    checkDay = date;
    await guarded(async () => {
      try {
        await load();
      } finally {
        checkDay = "";
      }
    });
  }
}
document.addEventListener("visibilitychange", rollover);
setInterval(rollover, 60000);
window.addEventListener("pagehide", () => {
  if (token) lock();
});
loginView();
