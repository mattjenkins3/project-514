import { strengthSession } from "./strength.js";
export const DAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];
export const YDS = [
  ...Array.from({ length: 10 }, (_, i) => "5." + i),
  ...[10, 11, 12, 13, 14, 15].flatMap((n) =>
    [..."abcd"].map((c) => "5." + n + c),
  ),
];
// Route grade equivalents are approximate. Store the index so toggling never changes a grade.
export const FRENCH = [
  "1",
  "1",
  "1",
  "2",
  "3",
  "4a",
  "4b",
  "4c",
  "5a",
  "5b",
  "5c",
  "6a",
  "6a+",
  "6b",
  "6b+",
  "6c",
  "6c+",
  "7a",
  "7a+",
  "7b",
  "7b+",
  "7c",
  "7c+",
  "8a",
  "8a+",
  "8b",
  "8b+",
  "8c",
  "8c+",
  "9a",
  "9a+",
  "9b",
  "9b+",
  "9c",
];
export const SPORTS = [
  "Mountaineering",
  "Running and VO2 max",
  "Cycling and VO2 max",
];
export const HANG = [
  "Abrahamson-Baar No Hangs",
  "Max Hang program",
  "Combined No Hang and Max Hang program",
];
export const STRENGTH = [
  "Climber optimized upper body and core",
  "Climber optimized whole body strength and resilience",
];
export const OUTCOMES = [
  "Completed as planned",
  "Felt easy",
  "Harder than planned",
  "Partial",
  "Missed",
];
export const RECOVERY = [
  "Recovered",
  "Tired or sore",
  "Pain or unsafe movement",
];
export function discipline(sport) {
  return (
    { [SPORTS[0]]: "Hiking", [SPORTS[1]]: "Running", [SPORTS[2]]: "Cycling" }[
      sport
    ] || ""
  );
}
export function defaults() {
  return {
    name: "",
    units: "Metric",
    scale: "Yosemite Decimal System",
    zone: "auto",
    grade: 9,
    target: 10,
    height: null,
    weight: null,
    climbDays: [1, 3, 5],
    climbMinutes: 45,
    sport: "",
    sportDays: [],
    sportMinutes: 30,
    volume: null,
    goalVolume: null,
    gain: null,
    goalGain: null,
    vo2: null,
    goalVo2: null,
    hang: "",
    strength: "",
    fuelCarbs: null,
    fuelProtein: null,
    fuelFat: null,
    fuelCalories: null,
  };
}
export const dayAdd = (day, n) =>
  new Date(Date.parse(day + "T12:00:00Z") + n * 86400000)
    .toISOString()
    .slice(0, 10);
export const gap = (a, b) =>
  Math.round((Date.parse(a) - Date.parse(b)) / 86400000);
export const weekday = (day) => new Date(day + "T12:00:00Z").getUTCDay();
export function todayIn(zone, now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}
export function unit(key, p) {
  const metric = p.units === "Metric";
  if (key === "height") return metric ? ["cm", 1] : ["in", 2.54];
  if (key === "weight") return metric ? ["kg", 1] : ["lb", 0.45359237];
  if (["gain", "goalGain"].includes(key))
    return metric ? ["m", 1] : ["ft", 0.3048];
  return metric ? ["km", 1] : ["mi", 1.609344];
}
export const gradeName = (index, p) =>
  (p.scale === "French" ? FRENCH : YDS)[index];
export function fresh() {
  return {
    profile: null,
    start: null,
    plans: {},
    feedback: {},
    reviews: {},
    rest: {},
    paused: false,
    hold: false,
    promptedThrough: null,
    reviewPeriod: 0,
  };
}
export function duePeriod(s, day) {
  return s.start
    ? Math.max(0, Math.min(6, Math.floor(gap(day, s.start) / 14)))
    : 0;
}
export function pending(s, day) {
  return Object.keys(s.plans)
    .sort()
    .filter((d) => d < day && d > (s.promptedThrough || "") && !s.feedback[d]);
}
const phases = [
  "Foundation",
  "Movement economy",
  "Pacing",
  "Recovery",
  "Route practice",
  "Repeatability",
  "Endurance",
  "Recovery",
  "Route reading",
  "Project practice",
  "Consistency",
  "Assessment",
];
const cues = [
  "Climb a familiar route and place each foot quietly.",
  "Repeat easy laps with relaxed hands.",
  "Choose a deliberate rest before the final third.",
  "Use easy terrain and leave plenty in reserve.",
  "Read a familiar sequence before leaving the ground.",
  "Repeat a sequence with consistent footwork.",
  "Link comfortable moves with controlled breathing.",
  "Practice smooth movement on easy ground.",
  "Identify a secure rest before the crux.",
  "Practice a short sequence with full rests.",
  "Repeat a familiar route and compare your pacing.",
  "Revisit your benchmark under similar conditions.",
];
export function buildPlan(s, from) {
  s.plannerVersion = 6;
  const p = s.profile;
  const reports = Object.entries(s.feedback).sort(([a], [b]) =>
    b.localeCompare(a),
  );
  for (let i = 0; i < 84; i++) {
    const day = dayAdd(s.start, i);
    if (day < from && s.plans[day]) continue;
    const w = Math.floor(i / 7),
      wd = weekday(day);
    const kind = p.climbDays.includes(wd)
      ? "Climb"
      : p.sport && p.sportDays.includes(wd)
        ? discipline(p.sport)
        : "Rest";
    const recent = reports.filter(([d]) => d < day && gap(day, d) <= 14);
    const tough = recent.filter(
      ([, r]) =>
        ["Partial", "Harder than planned", "Missed"].includes(r.outcome) ||
        r.recovery === "Tired or sore",
    );
    const exceeded = recent.some(
      ([d, r]) =>
        gap(day, d) <= 3 &&
        r.minutes > 0 &&
        s.plans[d]?.minutes > 0 &&
        r.minutes > s.plans[d].minutes * 1.25,
    );
    const ease = tough.length > 0 || exceeded;
    const positive = recent.filter(
      ([d, r]) =>
        r.outcome === "Felt easy" &&
        r.recovery === "Recovered" &&
        s.plans[d]?.kind === kind,
    ).length;
    const reentry = s.reentryUntil && day <= s.reentryUntil;
    const recovering = ease || reentry;
    const deload = [3, 7, 11].includes(w);
    const scale = [
      0.9, 0.97, 1.03, 0.72, 0.98, 1.04, 1.12, 0.77, 1.02, 1.08, 1.02, 0.82,
    ][w];
    const plan = {
      kind,
      week: w + 1,
      phase: phases[w],
      minutes: 0,
      title: "Recovery day",
      cue: "Rest and prepare for your next session.",
      extras: [],
      route: null,
    };
    if (kind === "Rest" || s.paused || s.hold || s.rest[day]) {
      plan.kind = "Rest";
      if (s.hold)
        plan.cue = "Training is on hold. Review your recovery before resuming.";
      else if (s.paused) plan.cue = "Training is paused.";
    } else {
      let minutes = kind === "Climb" ? p.climbMinutes : p.sportMinutes;
      const last = recent.find(
        ([d, r]) =>
          r.minutes > 0 && s.plans[d]?.kind === kind && r.outcome === "Partial",
      );
      if (last) minutes = Math.min(minutes, last[1].minutes + 5);
      const load =
        scale * (recovering ? 0.75 : positive >= 2 && !deload ? 1.05 : 1);
      plan.minutes = Math.max(1, Math.round(minutes * load));
      plan.reason = recovering
        ? "Reduced workload for recovery."
        : deload
          ? "A lighter week for recovery."
          : positive >= 2
            ? "A small progression after two comfortable reports."
            : "Based on your usual session and this week’s focus.";
      if (kind === "Climb") {
        const practice =
          !recovering &&
          !deload &&
          w >= 4 &&
          p.target > p.grade &&
          wd === Math.max(...p.climbDays);
        plan.title = practice
          ? "Project sequence practice"
          : deload || recovering
            ? "Easy recovery laps"
            : [
                "Footwork & easy laps",
                "Pacing on familiar routes",
                "Route reading practice",
              ][
                p.climbDays
                  .slice()
                  .sort((a, b) => a - b)
                  .indexOf(wd) % 3
              ];
        plan.route = practice ? p.grade : Math.max(0, p.grade - 2);
        plan.cue =
          cues[w] +
          " Warm up gradually, alternate movement with rests, and finish with easy climbing.";
        if (
          p.hang &&
          p.hang !== HANG[0] &&
          !recovering &&
          !deload &&
          (p.hang !== HANG[1] || wd === Math.min(...p.climbDays))
        ) {
          const label =
            p.hang === HANG[2]
              ? wd === Math.min(...p.climbDays) && w > 0
                ? HANG[1]
                : HANG[0]
              : p.hang;
          plan.extras.push(
            label +
              (label === HANG[0]
                ? " · Optional 10 minutes, feet supported, light finger tension. Separate from climbing or another finger session by at least six hours. Skip sore days."
                : " · For experienced hangboarders: after warming up, three controlled 7–10 second efforts on a familiar edge, with three minutes of rest. Replace hard route attempts that day. Stop before grip form slips."),
          );
        }
      } else {
        plan.title = {
          Hiking: "Uphill endurance hike",
          Running: "Conversational run / walk",
          Cycling: "Easy endurance ride",
        }[kind];
        plan.cue = {
          Hiking:
            "Choose a sustainable uphill pace and allow time for the descent.",
          Running:
            "Start with a walk, alternate easy running and walking, then cool down.",
          Cycling:
            "Spin easily to warm up, ride at a conversational pace, then ease off.",
        }[kind];
        // Advance gradually toward the athlete's own weekly target.
        function perSession(base, goal) {
          if (base == null) return null;
          const factor = Math.min(w / 11, 1);
          const target = goal == null ? base : Math.min(goal, base * 1.25);
          return (
            Math.round(
              (((base + (target - base) * factor) * load) /
                p.sportDays.length) *
                10,
            ) / 10
          );
        }
        plan.distance = perSession(p.volume, p.goalVolume);
        if (kind === "Hiking") plan.gain = perSession(p.gain, p.goalGain);
        if (p.vo2 && p.goalVo2 && p.goalVo2 > p.vo2 && !recovering && !deload)
          plan.cue +=
            " Track how the same comfortable pace feels at your next aerobic benchmark.";
      }
      if (p.hang === HANG[0]) {
        plan.extras.push(
          HANG[0] +
            " · Two 10-minute sessions today, at least six hours apart and separated from climbing or heavy finger training by six hours. Keep feet supported and tension light. Skip if fingers hurt or remain sore.",
        );
      }
    }
    if (
      p.strength &&
      kind !== "Climb" &&
      !s.paused &&
      !s.hold &&
      !s.rest[day]
    ) {
      plan.strengthRecovery = recovering || deload;
      plan.strength = strengthSession(p, day, plan, s.plans);
      plan.extras.push(
        p.strength === STRENGTH[0]
          ? "Strength · Rows, push-ups and dead bugs, then one easy set of split squats."
          : "Strength · Include rows and side planks. Spend the larger share on split squats, hip hinges, step-ups and calf raises.",
      );
      if (plan.kind === "Rest") {
        plan.title = "Strength & recovery";
        plan.cue =
          "Complete the strength work below, then recover. No climbing or cardio is scheduled.";
      }
    }
    s.plans[day] = plan;
  }
}
