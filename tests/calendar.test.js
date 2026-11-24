import test from "node:test";
import assert from "node:assert/strict";
import { apply, importBeta } from "../worker/actions.js";
import {
  fresh,
  defaults,
  SPORTS,
  HANG,
  STRENGTH,
  dayAdd,
  pending,
  duePeriod,
  unit,
  todayIn,
  gradeName,
} from "../web/model.js";

const sunday = "2026-11-01",
  monday = "2026-11-02",
  wed = "2026-11-04";
function change(s, day, body) {
  apply(s, body, "America/Denver", new Date(day + "T19:00:00Z"));
}
function setup(extra = {}) {
  const s = fresh();
  change(s, sunday, {
    action: "profile",
    profile: { ...defaults(), name: "Alex", ...extra },
  });
  return s;
}
test("Sunday setup yields 84 days starting Monday; missing activities are assumed and remain editable", () => {
  const s = setup();
  assert.equal(s.start, monday);
  assert.equal(Object.keys(s.plans).length, 84);
  assert.equal(Object.keys(s.plans).at(-1), "2027-01-24");
  assert.deepEqual(pending(s, wed), [monday, "2026-11-03"]);
  const snapshot = structuredClone(s.plans);
  change(s, wed, { action: "dismissFeedback" });
  assert.deepEqual(pending(s, wed), []);
  assert.deepEqual(s.feedback, {});
  assert.deepEqual(s.plans, snapshot);
  change(s, wed, {
    action: "feedback",
    date: monday,
    outcome: "Partial",
    minutes: 15,
    recovery: "Tired or sore",
  });
  assert.deepEqual(s.plans[monday], snapshot[monday]);
  assert.ok(s.plans[wed].minutes < snapshot[wed].minutes);
  change(s, wed, {
    action: "feedback",
    date: monday,
    outcome: "Completed as planned",
    minutes: 40,
    recovery: "Recovered",
  });
  assert.deepEqual(s.plans[wed], snapshot[wed]);
  assert.throws(() =>
    change(s, wed, { action: "feedback", date: "2026-12-01" }),
  );
});
test("two-week cadence, updated benchmarks, schedule changes, preserved history", () => {
  const s = setup(),
    d = dayAdd(monday, 14),
    prior = structuredClone(s.plans[monday]);
  assert.equal(duePeriod(s, dayAdd(d, -1)), 0);
  assert.equal(duePeriod(s, d), 1);
  change(s, d, {
    action: "review",
    profile: { ...s.profile, grade: 12, target: 14 },
    route: "Blue arete",
    result: "Sent",
  });
  assert.equal(s.reviews[d].result, "Sent");
  assert.equal(s.reviewPeriod, 1);
  assert.equal(s.plans[d].route, 10);
  assert.deepEqual(s.plans[monday], prior);
  const next = dayAdd(d, 14);
  change(s, next, { action: "dismissReview" });
  assert.equal(s.reviewPeriod, 2);
});
test("conditional disciplines, units, progression, grade display and supplemental training", () => {
  for (const sport of SPORTS) {
    const s = setup({
      sport,
      sportDays: [2, 4],
      volume: 20,
      goalVolume: 30,
      gain: 500,
      goalGain: 800,
      hang: HANG[2],
      strength: STRENGTH[1],
    });
    const a = s.plans["2026-11-03"];
    assert.ok(a.distance > 0);
    assert.ok(a.extras.some((x) => x.includes("split squats")));
    assert.equal(a.gain > 0, sport === SPORTS[0]);
    assert.ok(s.plans[monday].extras.some((x) => x.includes(HANG[0])));
    assert.ok(
      s.plans[dayAdd(monday, 7)].extras.some((x) => x.includes(HANG[1])),
    );
    const plans = structuredClone(s.plans);
    change(s, wed, { action: "display", units: "Imperial", scale: "French" });
    assert.deepEqual(s.plans, plans);
    assert.equal(unit("volume", s.profile)[0], "mi");
    assert.equal(gradeName(10, s.profile), "5c");
    change(s, wed, { action: "profile", profile: { ...s.profile, sport: "" } });
    assert.equal(s.profile.volume, null);
    assert.equal(s.plans["2026-11-05"].kind, "Rest");
  }
  assert.throws(() => setup({ sport: SPORTS[0], sportDays: [1] }));
});
test("device timezone, safety hold, explicit return and next block", () => {
  assert.equal(
    todayIn("America/Denver", new Date("2026-11-02T04:30:00Z")),
    sunday,
  );
  const s = setup();
  change(s, wed, {
    action: "feedback",
    date: monday,
    outcome: "Partial",
    recovery: "Pain or unsafe movement",
  });
  assert.equal(s.plans[wed].kind, "Rest");
  change(s, wed, { action: "resumeHold" });
  assert.equal(s.plans[wed].kind, "Climb");
  change(s, "2027-01-26", { action: "nextBlock" });
  assert.equal(s.start, "2027-01-27");
  assert.equal(Object.keys(s.plans).length, 168);
});
test("beta upgrade retains dated workouts, feedback, recovery, and grade", () => {
  const old = {
    start: monday,
    grade: "5.10a",
    target: "5.11a",
    climb_days: ["Monday"],
    run_days: ["Friday"],
    strength: true,
    zone: "America/Denver",
  };
  const s = importBeta(
    {
      profile: { "": old },
      hold: { "": { message: "Paused" } },
      plan: { [monday]: { title: "Original", minutes: 20, kind: "Climb" } },
      checkin: {
        [monday]: { outcome: "Partial", minutes: 10, recovery: "Recovered" },
      },
    },
    wed,
  );
  assert.equal(s.plans[monday].title, "Original");
  assert.equal(s.feedback[monday].minutes, 10);
  assert.equal(s.hold, true);
  assert.equal(s.profile.grade, 10);
  assert.equal(s.profile.sport, SPORTS[1]);
});
