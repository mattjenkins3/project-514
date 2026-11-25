import { startIntro } from "./intro.js";
import { sessionBrief } from "./session.js";
import { outlook } from "./outlook.js";
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
  noticeTimer,
  introPending = false;
let defaultDisplay = defaults(),
  checkDay = "",
  displayEdits = {};
function toast(text) {
  $("#message").textContent = text;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => ($("#message").textContent = ""), 4200);
}
function lock() {
  fetch("/api/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  }).catch(() => {});
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
  $("#site-nav").innerHTML = "";
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
    credentials: "same-origin",
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
  if (view !== "Profile" && !introPending) prompts();
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
  $("#site-nav").innerHTML = nav;
  main.innerHTML =
    (view === "Profile"
      ? profileView()
      : view === "Progress"
        ? progressView()
        : calendarView()) + '<p class="error" role="alert"></p>';
}
function metric(key, val) {
  const [suffix, factor] = unit(key, state.profile);
  return Number((val / factor).toFixed(1)) + " " + suffix;
}
function brief(label, text) {
  return (
    "<section><h3>" + esc(label) + "</h3><p>" + esc(text) + "</p></section>"
  );
}
function workout(d) {
  const plan = state.plans[d],
    r = state.feedback[d];
  if (!plan) return "";
  const briefing = sessionBrief(plan);
  const tags = [
    plan.kind === "Rest" && plan.extras?.some((x) => x.startsWith("Strength"))
      ? "Strength"
      : plan.kind,
    plan.minutes + " min",
  ];
  if (plan.route != null)
    tags.push("Routes around " + gradeName(plan.route, state.profile));
  if (plan.distance != null) tags.push(metric("volume", plan.distance));
  if (plan.gain != null) tags.push(metric("gain", plan.gain) + " ascent");
  const actions =
    (d <= today
      ? btn(
          r ? "Edit feedback" : "Report performance",
          "report",
          "primary",
          "data-day=" + d,
        )
      : "") +
    (d === today && plan.kind !== "Rest"
      ? btn("Rest today", "rest", "quiet")
      : "");
  const descriptions = [briefing.warmup, briefing.session, briefing.cooldown];
  const stages = briefing.phases
    .map(
      ([minutes, label], i) =>
        '<li><div class="stage-heading"><strong>' +
        esc(label) +
        "</strong><span>" +
        minutes +
        " min</span></div><p>" +
        esc(descriptions[i]) +
        "</p></li>",
    )
    .join("");
  const extras = (plan.extras || [])
    .slice()
    .sort(
      (a, b) =>
        Number(b.startsWith("Strength")) - Number(a.startsWith("Strength")),
    )
    .map((x) => {
      if (x.startsWith("Strength")) {
        const strength = plan.strength;
        if (!strength)
          return (
            '<section class="training-extra"><h3>Strength</h3><p>' +
            esc(x.split(" · ").slice(1).join(" · ")) +
            "</p></section>"
          );
        return (
          '<section class="training-extra strength-plan"><div class="strength-heading"><h3>' +
          esc(strength.title) +
          "</h3><span>About " +
          strength.minutes +
          " min · " +
          esc(strength.phase) +
          "</span></div><p>" +
          esc(strength.context) +
          "</p><p>" +
          esc(strength.effort) +
          "</p><ul>" +
          strength.exercises
            .map(
              (e) =>
                "<li><strong>" +
                esc(e.name) +
                "</strong><span>" +
                esc(e.dose) +
                "</span><p>" +
                esc(e.cue) +
                "</p></li>",
            )
            .join("") +
          '</ul><p class="progression">' +
          esc(strength.progression) +
          '</p><a href="/research.html#strength">Why this session · strength evidence ↗</a></section>'
        );
      }
      return (
        '<section class="training-extra"><h3>' +
        esc(x.split(" · ")[0].replace("Abrahamson-Baar", "Abrahamsson–Baar")) +
        "</h3><p>" +
        esc(x.split(" · ").slice(1).join(" · ")) +
        "</p>" +
        (x.includes("No Hang")
          ? '<ul><li>Morning — 10 minutes of light, feet-supported pulls.</li><li>Evening — repeat the 10-minute routine, at least six hours later.</li><li>Each repetition is 10 seconds pulling, then 20 seconds off. Never add bodyweight hanging to this light routine.</li></ul><a href="/research.html#abrahangs">See the exact 10-minute sequence ↗</a>'
          : "") +
        "</section>"
      );
    })
    .join("");
  const fuelingTargets = [
    ["fuelCarbs", "Carbohydrates", "g"],
    ["fuelProtein", "Protein", "g"],
    ["fuelFat", "Fat", "g"],
    ["fuelCalories", "Total calories", "kcal"],
  ].filter(([key]) => state.profile[key] != null && state.profile[key] !== "");
  const fueling = fuelingTargets.length
    ? "<section><h3>Your daily fueling references</h3><ul>" +
      fuelingTargets
        .map(
          ([key, label, unit]) =>
            "<li>" +
            label +
            " · " +
            esc(state.profile[key]) +
            " " +
            unit +
            "</li>",
        )
        .join("") +
      "</ul><p>These are your daily targets, including meals and snacks.</p></section>"
    : "";
  return (
    '<article class="work session-first"><header class="work-heading"><p class="dateline">' +
    esc(dateLabel(d, { weekday: "long", month: "long", day: "numeric" })) +
    "</p><h2>" +
    esc(plan.title) +
    '</h2><p class="session-meta">' +
    tags.map(esc).join(" · ") +
    '</p></header><section class="session-plan"><h3>Session plan</h3>' +
    (stages
      ? '<ol class="session-stages">' + stages + "</ol>"
      : "<p>" + esc(briefing.session) + "</p>") +
    '<div class="actions">' +
    actions +
    '</div></section><aside class="session-guidance">' +
    brief("Today’s focus", briefing.cue) +
    brief("This week", briefing.theme) +
    fueling +
    '<p class="evidence-note">Work and rest intervals are coaching starting points. Adjust using your feedback.</p><a href="/research.html">Training research ↗</a></aside>' +
    (d < today || r
      ? '<p class="report-status">' +
        esc(r ? r.outcome : "Assumed completed as directed") +
        "</p>"
      : "") +
    (extras ? '<div class="session-extras">' + extras + "</div>" : "") +
    "</article>"
  );
}
function volumeChart(active) {
  const weeks = Array.from({ length: 12 }, (_, i) => {
    const days = Array.from(
      { length: 7 },
      (_, j) => state.plans[dayAdd(state.start, i * 7 + j)],
    );
    const climbing = days.reduce(
      (n, p) => n + (p.kind === "Climb" ? p.minutes : 0),
      0,
    );
    const cardio = days.reduce(
      (n, p) => n + (!["Rest", "Climb"].includes(p.kind) ? p.minutes : 0),
      0,
    );
    return { climbing, cardio, total: climbing + cardio, phase: days[0].phase };
  });
  const max = Math.max(1, ...weeks.map((w) => w.total)),
    width = 320,
    height = 150;
  const x = (i) => 24 + (i * 270) / 11,
    y = (n) => 111 - (n / max) * 83;
  const points = weeks.map((w, i) => x(i) + "," + y(w.total)).join(" ");
  const graph =
    '<svg viewBox="0 0 320 150" role="group" aria-label="Weekly climbing and cardio minutes">' +
    '<path d="M24 111H300" stroke="#b9c2bb" fill="none"/>' +
    '<polygon points="24,111 ' +
    points +
    ' 294,111" fill="url(#volume-fill)"/><defs><linearGradient id="volume-fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#f2cf1b" stop-opacity=".5"/><stop offset="1" stop-color="#f2cf1b" stop-opacity=".05"/></linearGradient></defs>' +
    '<polyline points="' +
    points +
    '" fill="none" stroke="#176379" stroke-width="2.5" stroke-linejoin="round"/>' +
    weeks
      .map(
        (w, i) =>
          '<g class="volume-point" tabindex="0" role="img" aria-label="Week ' +
          (i + 1) +
          ", " +
          esc(w.phase) +
          ", " +
          w.climbing +
          " climbing minutes, " +
          w.cardio +
          ' cardio minutes" data-volume-week="' +
          (i + 1) +
          '" data-phase="' +
          esc(w.phase) +
          '" data-climbing="' +
          w.climbing +
          '" data-cardio="' +
          w.cardio +
          '" data-x="' +
          x(i) +
          '" data-y="' +
          y(w.total) +
          '"><rect x="' +
          (x(i) - 12) +
          '" y="15" width="24" height="104" fill="transparent"/><circle cx="' +
          x(i) +
          '" cy="' +
          y(w.total) +
          '" r="' +
          (i === active - 1 ? 5 : 3) +
          '" fill="' +
          (i === active - 1 ? "#e74e35" : "#176379") +
          '"/><text x="' +
          x(i) +
          '" y="133" text-anchor="middle">' +
          (i + 1) +
          "</text></g>",
      )
      .join("") +
    '<line class="volume-crosshair" y1="18" y2="112" stroke="#176379" stroke-dasharray="3 4" visibility="hidden"/></svg>';
  return (
    '<figure class="volume"><figcaption>Block volume</figcaption><strong class="volume-total">' +
    weeks[active - 1].total +
    " <small>min this week</small></strong>" +
    graph +
    '<div class="volume-tooltip" role="status" aria-live="polite"></div><p class="chart-hint">Hover or focus a week to explore. Climbing + cardio only. <a href="/research.html#endurance-sources">Evidence ↗</a></p></figure>'
  );
}
function showVolume(point) {
  const figure = point.closest(".volume"),
    tip = figure.querySelector(".volume-tooltip");
  const { volumeWeek, phase, climbing, cardio, x } = point.dataset;
  figure
    .querySelectorAll(".volume-point")
    .forEach((p) => p.classList.toggle("hovered", p === point));
  const line = figure.querySelector(".volume-crosshair");
  line.setAttribute("x1", x);
  line.setAttribute("x2", x);
  line.setAttribute("visibility", "visible");
  tip.innerHTML =
    "<strong>Week " +
    volumeWeek +
    " · " +
    esc(phase) +
    "</strong><span>" +
    climbing +
    " min climbing</span><span>" +
    cardio +
    " min cardio</span><b>" +
    (Number(climbing) + Number(cardio)) +
    " min total</b>";
  tip.classList.add("visible");
}
document.addEventListener("pointerover", (e) => {
  const p = e.target.closest("[data-volume-week]");
  if (p) showVolume(p);
});
document.addEventListener("focusin", (e) => {
  const p = e.target.closest("[data-volume-week]");
  if (p) showVolume(p);
});
function hideVolume(figure) {
  figure.querySelector(".volume-tooltip")?.classList.remove("visible");
  figure
    .querySelectorAll(".hovered")
    .forEach((p) => p.classList.remove("hovered"));
  figure
    .querySelector(".volume-crosshair")
    ?.setAttribute("visibility", "hidden");
}
document.addEventListener("pointerout", (e) => {
  const f = e.target.closest(".volume");
  if (f && !f.contains(e.relatedTarget)) hideVolume(f);
});
document.addEventListener("focusout", (e) => {
  const f = e.target.closest(".volume");
  if (f && !f.contains(e.relatedTarget)) hideVolume(f);
});
function weekRow(w) {
  const start = dayAdd(state.start, w * 7);
  let climb = 0,
    cardio = 0;
  const cells = Array.from({ length: 7 }, (_, i) => {
    const d = dayAdd(start, i),
      p = state.plans[d];
    if (p.kind === "Climb") climb += p.minutes;
    else if (p.kind !== "Rest") cardio += p.minutes;
    return (
      '<button class="cell ' +
      (p.kind === "Rest" ? "rest" : p.kind === "Climb" ? "" : "aerobic") +
      '" data-act="day" data-day="' +
      d +
      '" aria-label="' +
      esc(dateLabel(d) + " · " + p.title) +
      '"' +
      (d === selected ? ' aria-pressed="true"' : "") +
      (d === today ? ' aria-current="date"' : "") +
      "><span>" +
      (d === today ? "Today" : DAYS[weekday(d)].slice(0, 3)) +
      "</span><strong>" +
      esc(Number(d.slice(-2))) +
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
    (mode === "12 weeks"
      ? esc(dateLabel(start, { month: "short", day: "numeric" }))
      : "") +
    (mode === "12 weeks"
      ? " – " +
        esc(dateLabel(dayAdd(start, 6), { month: "short", day: "numeric" })) +
        "　 /　"
      : "") +
    climb +
    " min climbing　·　" +
    cardio +
    ' min cardio</small></div><div class="days">' +
    cells +
    "</div></section>"
  );
}
function calendarView() {
  const end = dayAdd(state.start, 83),
    w = Math.floor(gap(withinBlock(selected), state.start) / 7);
  const path = outlook(state, today);
  const goalPanel =
    '<aside class="outlook"><strong>Goal outlook</strong>' +
    path.lines
      .map(
        (l) =>
          '<div class="goalrow">' +
          l
            .replace(" · Awaiting a benchmark trend", "")
            .split(" · ")
            .map((v, i) =>
              i === 0 ? "<b>" + esc(v) + "</b>" : "<span>" + esc(v) + "</span>",
            )
            .join("") +
          "</div>",
      )
      .join("") +
    (path.lines.some((l) => l.includes("Awaiting"))
      ? '<small class="trendnote">Target dates update with benchmark trends.</small>'
      : "") +
    "</aside>";
  const modes =
    '<div class="controls" aria-label="Calendar view">' +
    ["Week", "12 weeks"]
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
          "‹",
          "move",
          "",
          'aria-label="Previous" data-step=-' +
            step +
            ((mode === "Week" ? w === 0 : selected <= state.start)
              ? " disabled"
              : ""),
        ) +
        '<label class="jumpdate">' +
        (mode === "Week"
          ? dateLabel(dayAdd(state.start, w * 7), {
              month: "short",
              day: "numeric",
            }) +
            " – " +
            dateLabel(dayAdd(state.start, w * 7 + 6), {
              month: "short",
              day: "numeric",
            })
          : dateLabel(selected)) +
        '<input type="date" class="datepick" aria-label="Calendar date" name="calendarDate" min="' +
        state.start +
        '" max="' +
        end +
        '" value="' +
        selected +
        '"></label>' +
        btn(
          "›",
          "move",
          "",
          'aria-label="Next" data-step=' +
            step +
            ((mode === "Week" ? w === 11 : selected >= end) ? " disabled" : ""),
        ) +
        (selected === withinBlock(today) ? "" : btn("Today", "today")) +
        "</div>";
  const identity =
    '<div class="edition-head"><h1>' +
    esc(state.profile.name) +
    "’s calendar</h1><small>Training block " +
    path.block +
    " · " +
    dateLabel(state.start, { month: "short", day: "numeric" }) +
    " – " +
    dateLabel(end, { month: "short", day: "numeric", year: "numeric" }) +
    "</small></div>";
  const picker =
    '<div class="caltools">' +
    modes +
    (mode === "Week"
      ? '<b class="weekname">Week ' +
        (w + 1) +
        " · " +
        esc(state.plans[dayAdd(state.start, w * 7)].phase) +
        "</b>"
      : "") +
    controls +
    "</div>";
  const trainingStatus =
    state.hold || state.paused
      ? '<p class="panel">Training is ' +
        (state.hold
          ? "on hold. Review your recovery in Profile."
          : "paused. Resume in Profile when ready.") +
        "</p>"
      : "";
  const nav =
    '<aside class="weeknav">' +
    identity +
    picker +
    (mode === "Week" ? weekRow(w) + volumeChart(w + 1) : "") +
    "</aside>";
  const content =
    mode === "12 weeks"
      ? Array.from({ length: 12 }, (_, i) => weekRow(i)).join("")
      : workout(selected);
  return (
    trainingStatus +
    '<div class="edition ' +
    (mode === "Week" ? "weekmode" : "") +
    '">' +
    nav +
    '<div class="agenda">' +
    content +
    '</div><aside class="horizon">' +
    goalPanel +
    (mode === "Week" ? "" : volumeChart(w + 1)) +
    "</aside></div>" +
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
      introPending = true;
      const intro = startIntro();
      try {
        token = (await api("login", { password: data.get("password") })).token;
        await load();
        await intro.finish();
      } finally {
        intro.close();
        introPending = false;
      }
      if (view !== "Profile") prompts();
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
  if (e.target.closest(".brand") && state) {
    e.preventDefault();
    view = "Calendar";
    draft = null;
    render();
    return;
  }
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
      if (a === "day") mode = "Week";
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
async function restoreSession() {
  token = "browser-session";
  introPending = true;
  const intro = startIntro();
  try {
    await load();
    await intro.finish();
  } catch {
    token = "";
    loginView();
  } finally {
    intro.close();
    introPending = false;
  }
  if (state && view !== "Profile") prompts();
}
restoreSession();
