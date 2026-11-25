const themes = [
  "Establish a workload you can repeat comfortably.",
  "Make each move economical before adding time.",
  "Compare where you first feel pumped on a familiar route.",
  "Leave the wall and the trail feeling fresh.",
  "Rehearse one difficult sequence with enough rest to learn it.",
  "Repeat a familiar effort and aim for a similar finish.",
  "Spend longer moving at an effort you can sustain.",
  "Absorb the last build and revisit an easy benchmark.",
  "Read the route and identify rests before leaving the ground.",
  "Link your rehearsed moves while your footwork stays precise.",
  "Aim for consistency across attempts, rather than extra attempts.",
  "Repeat your benchmark under familiar conditions and record what changed.",
];
export function sessionBrief(plan) {
  const w = Math.max(0, Math.min(11, (plan.week || 1) - 1));
  const recovery = /Reduced workload|lighter week/.test(plan.reason || "");
  const warm = Math.min(12, Math.max(1, Math.floor(plan.minutes / 4)));
  const cool = Math.min(6, Math.floor(plan.minutes / 6));
  const main = plan.minutes - warm - cool;
  const phases =
    plan.kind === "Rest"
      ? []
      : [
          [warm, "Warm up"],
          [main, "Practice"],
          [cool, "Ease out"],
        ].filter(([n]) => n > 0);
  let session, cue;
  let warmup =
    plan.kind === "Climb"
      ? "Traverse on large holds and increase the reach gradually."
      : "Start on easy terrain and gradually find a comfortable rhythm.";
  const cooldown =
    plan.kind === "Climb"
      ? "Finish with relaxed movement on the easiest terrain of the session."
      : "Reduce your pace and let breathing settle.";
  if (plan.kind === "Rest") {
    session = plan.cue;
    cue = "Recall one movement that felt smooth in your last session.";
  } else if (plan.kind === "Climb") {
    if (plan.title.includes("Project") && !recovery) {
      session =
        "Rehearse a short crux sequence, then rest until your forearms feel fresh. End practice if pump exceeds 6 out of 10 or your feet start skating.";
      cue = "Look down and finish placing your foot before reaching past it.";
    } else {
      session = recovery
        ? "Traverse or repeat an easy route. Rest between laps until your breathing settles and keep forearm pump at 2 out of 10 or less."
        : w === 6
          ? "Link comfortable laps with deliberate shakeouts. Let pump reach 3 or 4 out of 10, then rest until your grip feels light again."
          : "Alternate familiar routes with equal time resting. Keep forearm pump at 2 to 4 out of 10 so every foot placement stays precise.";
      cue =
        "Set the inside edge of your toe, then shift weight over it before reaching.";
    }
    if (!recovery && plan.title === "Pacing on familiar routes") {
      session =
        "Repeat a familiar route. Notice which move first brings your pump to 3 out of 10. Rest fully, then repeat with a slower opening and compare.";
      cue = "Breathe out as you move past the hardest hold.";
    } else if (!recovery && plan.title === "Route reading practice") {
      session =
        "Preview a familiar route from the ground. Predict a rest and a tricky foot placement, then test both on the wall. Keep pump below 4 out of 10.";
      cue = "Choose the foothold that lets your hips stay close to the wall.";
    }
  } else {
    const detail = {
      Running: [
        "walk into a relaxed jog",
        "Keep your shoulders loose and shorten your stride on inclines.",
      ],
      Cycling: [
        "spin easily before settling into a steady cadence",
        "Relax your grip and shift early as the gradient changes.",
      ],
      Hiking: [
        "start on level ground before a sustained ascent",
        "Shorten your stride uphill and keep your breathing conversational.",
      ],
    }[plan.kind];
    if (detail) {
      const build = !recovery && [4, 5, 8, 9].includes(w) && main >= 18;
      warmup = detail[0][0].toUpperCase() + detail[0].slice(1) + ".";
      session = build
        ? "During the middle portion, try two three-minute brisk efforts separated by three easy minutes. You should still be able to speak in phrases."
        : "Hold an easy pace that lets you speak in sentences.";
      cue = detail[1];
      phases.forEach((row) => {
        if (row[1] === "Practice") row[1] = build ? "Steady + brisk" : "Steady";
      });
    } else {
      session = plan.work || plan.cue;
      cue = plan.cue;
    }
  }
  if (plan.kind === "Climb")
    session +=
      " Pick moves you can repeat with control. Stop the set when grip or foot placement deteriorates. Repeat with full recovery instead of adding tired attempts.";
  else if (plan.kind !== "Rest")
    session +=
      " Use the talk test to regulate effort on hills. Slow down or walk if you cannot speak comfortably, and finish with energy in reserve.";
  return { session, cue, theme: themes[w], phases, warmup, cooldown };
}
