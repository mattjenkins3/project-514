import { dayAdd, gap, STRENGTH } from "./model.js";

// A small, repeated exercise vocabulary supports skill and measurable progression.
export function strengthSession(profile, date, plan, plans) {
  const week = plan.week;
  const full = profile.strength === STRENGTH[1];
  const reduced = plan.strengthRecovery;
  const history = Object.entries(plans)
    .filter(([d, p]) => d < date && p.strength?.load === "main")
    .sort(([a], [b]) => a.localeCompare(b));
  const recent = history.filter(([d]) => gap(date, d) < 7);
  const consecutive = recent.some(([d]) => gap(date, d) < 2);
  const cardioBuild =
    ["Running", "Cycling", "Hiking"].includes(plan.kind) &&
    [5, 6, 9, 10].includes(week);
  const main = !reduced && !consecutive && recent.length < 2 && !cardioBuild;
  const phase =
    week <= 3 ? "Learn & establish" : week <= 7 ? "Build" : "Consolidate";
  const sets = week === 1 ? 1 : week >= 6 && week <= 7 ? 3 : 2;
  const reps = week >= 9 ? "6–8" : week === 3 || week === 7 ? "10–12" : "8–10";
  const nextClimb = profile.climbDays.includes(
    new Date(dayAdd(date, 1) + "T12:00:00Z").getUTCDay(),
  );
  const count = history.length;
  const variant = count % 2;
  const exercise = (name, dose, cue) => ({ name, dose, cue });
  const dose = (n = sets) => n + " set" + (n === 1 ? "" : "s") + " × " + reps;
  let exercises, title;
  if (main) {
    title =
      (full ? "Whole body" : "Upper body & core") +
      " · " +
      (variant ? "Hinge & stability" : "Squat & control");
    exercises = [
      exercise(
        variant ? "Dumbbell floor press" : "Incline push-up",
        dose(),
        "Use moderate dumbbells or an elevated surface. Keep shoulders comfortable and ribs steady.",
      ),
      exercise(
        "Supported dumbbell row",
        dose(nextClimb ? 1 : sets),
        "Support your free hand, draw the elbow toward your hip, and avoid gripping to exhaustion.",
      ),
      exercise(
        variant ? "Side plank" : "Dead bug",
        sets + " sets × " + (variant ? "15–25 sec/side" : "6–8/side"),
        variant
          ? "Stack ribs above hips. Use bent knees if needed."
          : "Extend opposite limbs slowly. Keep the lower back quiet.",
      ),
      exercise(
        variant ? "Hip hinge" : "Split squat",
        dose(full ? sets : 1) + (variant ? "" : " /leg"),
        variant
          ? "Use moderate dumbbells and move hips back with a long spine."
          : "No additional weight initially. Lower under control and keep the front foot planted.",
      ),
      ...(full
        ? [
            exercise(
              variant ? "Low step-up" : "Glute bridge",
              dose(),
              variant
                ? "Use a stable low step. Control the descent and keep the pelvis level."
                : "No additional weight. Pause briefly at the top without arching your back.",
            ),
            exercise(
              "Calf raise",
              sets + " sets × 12–15",
              "Use a wall for balance. Lower slowly through a comfortable range.",
            ),
          ]
        : []),
    ];
  } else {
    const rotation = (gap(date, "2020-01-01") + Math.floor((week - 1) / 4)) % 3;
    title = reduced
      ? "Recovery · easy movement"
      : "Support · " +
        ["Shoulders & trunk", "Hips & balance", "Control & resilience"][
          rotation
        ];
    const circuits = [
      [
        exercise(
          "Wall slide",
          "1–2 sets × 8",
          "No additional weight. Slide arms upward without shrugging.",
        ),
        exercise(
          "Bird dog",
          "1–2 sets × 6/side",
          "Reach long with opposite arm and leg. Keep your trunk level.",
        ),
        exercise(
          "Sit-to-stand",
          "1–2 sets × 8",
          "No additional weight. Stand smoothly from a stable chair.",
        ),
      ],
      [
        exercise(
          "Band external rotation",
          "1–2 sets × 10/side",
          "Use a light band. Keep elbows close to your sides.",
        ),
        exercise(
          "Side plank from knees",
          "1–2 sets × 15 sec/side",
          "Breathe normally and stop before your hips sag.",
        ),
        exercise(
          "Glute bridge",
          "1–2 sets × 10",
          "No additional weight. Press through your feet without arching.",
        ),
      ],
      [
        exercise(
          "Scapular push-up at wall",
          "1–2 sets × 8",
          "Keep elbows straight. Let shoulder blades move smoothly.",
        ),
        exercise(
          "Dead bug heel tap",
          "1–2 sets × 6/side",
          "Lower one heel at a time with an easy exhale.",
        ),
        exercise(
          "Supported single-leg balance",
          "1–2 sets × 20 sec/side",
          "No additional weight. Use a wall or chair as needed.",
        ),
      ],
    ];
    exercises = circuits[rotation];
    if (full)
      exercises.push(
        exercise(
          rotation === 1 ? "Calf raise" : "Low step-up",
          "1–2 sets × 8/side",
          "No additional weight. Use support and move easily through a comfortable range.",
        ),
      );
    if (reduced)
      exercises = exercises.map((e) => ({
        ...e,
        dose: e.dose.replace("1–2 sets", "1 set"),
      }));
  }
  return {
    load: main ? "main" : "support",
    title,
    phase,
    minutes: main ? (full ? 20 + sets * 7 : 15 + sets * 5) : 10,
    effort: main
      ? "Finish each set with 2–3 good repetitions still available. Rest 90–150 seconds between sets."
      : "Keep at least 4–5 repetitions in reserve. Rest 30–60 seconds. This should leave you feeling fresher.",
    progression: reduced
      ? "A lighter week reduces sets and effort. Resume your last comfortable variation after recovery."
      : main
        ? "Repeat these movements on the next matching session. First reach the top of the repetition range with control, then choose a slightly more challenging resistance or variation. Reduce a set if soreness affects climbing."
        : "Keep this circuit easy. It supports recovery between the more demanding strength sessions.",
    context: main
      ? nextClimb
        ? "Climbing tomorrow: pulling work is limited to one set."
        : "Warm up with five easy minutes and a rehearsal set."
      : cardioBuild
        ? "Your aerobic work is building this week, so strength stays light today."
        : consecutive
          ? "A demanding strength session was recent; today changes the stimulus and reduces fatigue."
          : "At most two demanding sessions in seven days; other days use easy support work.",
    exercises,
  };
}
