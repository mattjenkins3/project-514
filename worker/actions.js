import {
  DAYS,
  YDS,
  SPORTS,
  HANG,
  STRENGTH,
  OUTCOMES,
  RECOVERY,
  defaults,
  fresh,
  dayAdd,
  todayIn,
  duePeriod,
  buildPlan,
} from "../web/model.js";

export class InputError extends Error {}
function requireValue(condition, message) {
  if (!condition) throw new InputError(message);
}
function choice(value, items) {
  requireValue(items.includes(value), "Choose one of the available options.");
  return value;
}
function string(value, max, required = false) {
  requireValue(
    typeof value === "string" &&
      value.length <= max &&
      (!required || value.trim()),
    "Check the text fields and your name.",
  );
  return value.trim();
}
function number(value, min, max, optional = true) {
  if (value == null && optional) return null;
  requireValue(
    Number.isFinite(value) && value >= min && value <= max,
    "A number is outside the field’s allowed range.",
  );
  return value;
}
function days(list) {
  requireValue(
    Array.isArray(list) && list.length <= 7,
    "Select valid training days.",
  );
  return [...new Set(list.map((x) => choice(x, [0, 1, 2, 3, 4, 5, 6])))].sort();
}
export function zoneName(zone) {
  try {
    new Intl.DateTimeFormat("en", { timeZone: zone }).format(0);
  } catch {
    throw new InputError("Choose a valid time zone.");
  }
  return zone;
}
export function profile(input) {
  const p = defaults();
  p.name = string(input.name, 80, true);
  p.units = choice(input.units, ["Metric", "Imperial"]);
  p.scale = choice(input.scale, ["Yosemite Decimal System", "French"]);
  p.zone =
    input.zone === "auto" ? "auto" : zoneName(string(input.zone, 80, true));
  for (const key of ["grade", "target"])
    p[key] = choice(
      input[key],
      YDS.map((_, i) => i),
    );
  requireValue(
    p.target >= p.grade,
    "Set the goal grade at or above your repeatable grade.",
  );
  p.height = number(input.height, 1, 300);
  p.weight = number(input.weight, 1, 650);
  p.climbMinutes = number(input.climbMinutes, 5, 240, false);
  p.climbDays = days(input.climbDays);
  p.sport = choice(input.sport, ["", ...SPORTS]);
  if (p.sport) {
    p.sportDays = days(input.sportDays);
    requireValue(
      p.sportDays.length && !p.sportDays.some((d) => p.climbDays.includes(d)),
      "Choose at least one additional training day, separate from your climbing days.",
    );
    p.sportMinutes = number(input.sportMinutes, 5, 720, false);
    for (const key of ["volume", "goalVolume"])
      p[key] = number(input[key], 0, 3000);
    for (const key of ["vo2", "goalVo2"]) p[key] = number(input[key], 1, 150);
    if (p.sport === SPORTS[0])
      for (const key of ["gain", "goalGain"])
        p[key] = number(input[key], 0, 30000);
  }
  p.hang = choice(input.hang, ["", ...HANG]);
  p.strength = choice(input.strength, ["", ...STRENGTH]);
  for (const [key, max] of [
    ["fuelCarbs", 3000],
    ["fuelProtein", 1000],
    ["fuelFat", 1000],
    ["fuelCalories", 20000],
  ])
    p[key] = number(input[key], 0, max);
  for (const key of ["climbGoalDate", "sportGoalDate"]) {
    const date = input[key] || "";
    requireValue(
      !date ||
        (/^\d{4}-\d{2}-\d{2}$/.test(date) &&
          Number.isFinite(Date.parse(date)) &&
          dayAdd(date, 0) === date),
      "Choose a valid goal date.",
    );
    p[key] = key === "sportGoalDate" && !p.sport ? "" : date;
  }
  return p;
}
export function apply(s, body, browserZone, now = new Date()) {
  const { action } = body;
  const p = s.profile;
  const zone = p?.zone && p.zone !== "auto" ? p.zone : browserZone;
  let day = todayIn(zone, now);
  if (action === "profile" || action === "review") {
    requireValue(action !== "review" || p, "Set up your profile first.");
    s.profile = profile(body.profile);
    day = todayIn(
      s.profile.zone === "auto" ? browserZone : s.profile.zone,
      now,
    );
    if (!s.baseline) s.baseline = { day, profile: { ...(p || s.profile) } };
    if (!s.start) s.start = dayAdd(day, 1);
    if (action === "review") {
      const route = string(body.route || "", 160),
        result = string(body.result || "", 300);
      s.reviews[day] = {
        route,
        result,
        grade: s.profile.grade,
        vo2: s.profile.vo2,
        profile: { ...s.profile },
      };
      s.reviewPeriod = duePeriod(s, day);
    }
  } else {
    requireValue(p, "Set up your profile first.");
    switch (action) {
      case "feedback": {
        requireValue(
          Object.hasOwn(s.plans, body.date) && body.date <= day,
          "Choose a current or past plan date.",
        );
        const report = {
          outcome: choice(body.outcome, OUTCOMES),
          recovery: choice(body.recovery, RECOVERY),
          minutes: number(body.minutes, 0, 1440),
          note: string(body.note || "", 300),
        };
        s.feedback[body.date] = report;
        if (report.recovery === RECOVERY[2]) s.hold = true;
        break;
      }
      case "dismissFeedback":
        s.promptedThrough = dayAdd(day, -1);
        return;
      case "dismissReview":
        s.reviewPeriod = duePeriod(s, day);
        return;
      case "pause":
        s.paused = !s.paused;
        if (!s.paused) s.reentryUntil = dayAdd(day, 6);
        break;
      case "resumeHold":
        s.hold = false;
        s.reentryUntil = dayAdd(day, 6);
        break;
      case "rest":
        requireValue(
          Object.hasOwn(s.plans, day),
          "Today is outside this training block.",
        );
        s.rest[day] = true;
        break;
      case "display":
        p.units = choice(body.units, ["Metric", "Imperial"]);
        p.scale = choice(body.scale, ["Yosemite Decimal System", "French"]);
        return;
      case "nextBlock":
        requireValue(
          day > dayAdd(s.start, 83),
          "Finish this training block first.",
        );
        // Keep completed blocks available in the log and export.
        s.start = dayAdd(day, 1);
        s.reviewPeriod = 0;
        break;
      default:
        throw new InputError("Unknown update.");
    }
  }
  buildPlan(s, day);
}

// Read the previous Streamlit export without changing the original log.
export function importBeta(data, day) {
  const old = data.profile?.[""];
  const s = fresh();
  if (!old) return s;
  const p = defaults(),
    ids = (list) =>
      (list || []).map((d) => DAYS.indexOf(d)).filter((d) => d >= 0);
  Object.assign(p, {
    name: old.name || "",
    zone: old.zone || "auto",
    grade: Math.max(0, YDS.indexOf(old.grade)),
    target: Math.max(0, YDS.indexOf(old.target)),
    climbMinutes: old.climb_minutes ?? 45,
    climbDays: ids(old.climb_days),
    height: old.height ?? null,
    weight: old.weight ?? null,
    strength: old.strength ? STRENGTH[0] : "",
    fuelRest: old.fuel_targets?.Rest || "",
    fuelModerate: old.fuel_targets?.Moderate || "",
    fuelHard: old.fuel_targets?.Hard || "",
  });
  if (old.run_days?.length)
    Object.assign(p, {
      sport: SPORTS[1],
      sportDays: ids(old.run_days),
      sportMinutes: old.run_minutes || 30,
    });
  Object.assign(s, {
    profile: p,
    start: old.start,
    paused: !!old.paused,
    hold: !!data.hold?.[""],
    rest: data.rest || {},
    reentryUntil: old.reentry_until,
  });
  for (const [d, r] of Object.entries(data.checkin || {})) {
    if (r.outcome === "Skipped") continue;
    s.feedback[d] = {
      outcome: OUTCOMES.includes(r.outcome)
        ? r.outcome
        : "Completed as planned",
      recovery:
        r.technique === "Unsafe movement" ||
        (r.symptoms && r.symptoms !== "None")
          ? RECOVERY[2]
          : r.recovery === "Recovered"
            ? RECOVERY[0]
            : RECOVERY[1],
      minutes: r.minutes ?? null,
      note: "",
      original: r,
    };
  }
  for (const [d, r] of Object.entries(data.plan || {})) {
    if (d < day)
      s.plans[d] = {
        ...r,
        route: null,
        extras: [r.secondary].filter(Boolean),
        cue: [r.work, r.cue].filter(Boolean).join(" "),
      };
  }
  for (const [d, r] of Object.entries(data.benchmark || {}))
    s.reviews[d] = {
      ...r,
      grade: Math.max(0, YDS.indexOf(r.grade)),
      result: r.high_point || "",
      vo2: r.vo2_max ?? null,
    };
  buildPlan(s, day);
  return s;
}
