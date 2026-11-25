import { gap, dayAdd, gradeName } from "./model.js";
export function outlook(s, day) {
  const p = s.profile,
    block = Math.max(1, Math.round(Object.keys(s.plans).length / 84));
  const records = [
    ...(s.baseline ? [[s.baseline.day, s.baseline.profile]] : []),
    ...Object.entries(s.reviews).map(([date, r]) => [date, r.profile]),
  ]
    .filter(([, v]) => v)
    .sort(([a], [b]) => a.localeCompare(b));
  function estimate(label, desired, metrics, sport = false) {
    const active = metrics.filter(
      ([key, goal]) => p[key] != null && goal != null,
    );
    if (active.length && active.every(([key, goal]) => p[key] >= goal))
      return label + " · Goal reached";
    const estimates = [];
    for (const [key, goal] of active.filter(([key, goal]) => goal > p[key])) {
      const rows = records.filter(
        ([, v]) => v[key] != null && (!sport || v.sport === p.sport),
      );
      const first = rows[0],
        last = rows.at(-1);
      if (
        !first ||
        gap(last[0], first[0]) < 14 ||
        last[1][key] <= first[1][key]
      )
        break;
      estimates.push(
        dayAdd(
          last[0],
          Math.min(
            36500,
            Math.ceil(
              ((goal - last[1][key]) * gap(last[0], first[0])) /
                (last[1][key] - first[1][key]),
            ),
          ),
        ),
      );
    }
    const needed = active.filter(([key, goal]) => goal > p[key]).length;
    const measured = needed > 0 && estimates.length === needed;
    const date = measured ? estimates.sort().at(-1) : desired;
    if (!date) return label + " · Set a goal date in Profile";
    const blocks = Math.max(0, Math.ceil((gap(date, s.start) + 1) / 84) - 1);
    return (
      label +
      " · " +
      (measured ? "Trend estimate " : "Target ") +
      new Date(date + "T12:00:00Z").toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      }) +
      " · " +
      (date < day
        ? "Review due"
        : blocks
          ? "Block " + block + " of " + (block + blocks)
          : "This block") +
      (measured ? "" : " · Awaiting a benchmark trend")
    );
  }
  return {
    block,
    lines: [
      estimate("Climb " + gradeName(p.target, p), p.climbGoalDate, [
        ["grade", p.target],
      ]),
      ...(p.sport
        ? [
            estimate(
              p.sport,
              p.sportGoalDate,
              [
                ["volume", p.goalVolume],
                ["vo2", p.goalVo2],
                ["gain", p.goalGain],
              ],
              true,
            ),
          ]
        : []),
    ],
  };
}
