import {
  DAYS,
  YDS,
  FRENCH,
  SPORTS,
  HANG,
  STRENGTH,
  discipline,
  gradeName,
  unit,
} from "./model.js";
export const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export function field(label, control, help, group = false) {
  const tag = group ? "div" : "label";
  return (
    "<" +
    tag +
    ' class="field">' +
    esc(label) +
    ' <span class="tip" aria-hidden="true">ⓘ</span>' +
    control +
    '<span class="hint" role="tooltip">' +
    esc(help) +
    "</span></" +
    tag +
    ">"
  );
}
export function select(key, values, value) {
  return (
    '<select name="' +
    esc(key) +
    '">' +
    values
      .map((item) => {
        const [v, label] = Array.isArray(item) ? item : [item, item];
        return (
          '<option value="' +
          esc(v) +
          '"' +
          (v === value ? " selected" : "") +
          ">" +
          esc(label) +
          "</option>"
        );
      })
      .join("") +
    "</select>"
  );
}
export function preferences(p) {
  return (
    field(
      "Units",
      select("units", ["Metric", "Imperial"], p.units),
      "Choose how measurements appear. For example, Imperial shows height in inches and distance in miles.",
    ) +
    field(
      "Climbing grades",
      select("scale", ["Yosemite Decimal System", "French"], p.scale),
      "Choose the scale used at your crag. For example, select French for routes marked 6a. Conversions are approximate.",
    )
  );
}
const section = (title, body) =>
  "<fieldset><legend>" +
  esc(title) +
  '</legend><div class="grid">' +
  body +
  "</div></fieldset>";
export function profileFields(p, browserZone, review = false) {
  const num = (
    key,
    label,
    example,
    min,
    max,
    measurement = false,
    required = false,
  ) => {
    const [suffix, factor] = measurement ? unit(key, p) : ["", 1];
    const val = p[key] == null ? "" : Number((p[key] / factor).toFixed(3));
    const hint = example.replaceAll("{unit}", suffix);
    return field(
      label + (suffix ? " · " + suffix : ""),
      '<input type="number" step="any" name="' +
        key +
        '" min="' +
        Number((min / factor).toFixed(4)) +
        '" max="' +
        Number((max / factor).toFixed(4)) +
        '" value="' +
        val +
        '"' +
        (required ? " required" : "") +
        ' data-factor="' +
        factor +
        '">',
      hint,
    );
  };
  const txt = (key, label, help, max, required = false) =>
    field(
      label,
      '<input name="' +
        key +
        '" maxlength="' +
        max +
        '" value="' +
        esc(p[key]) +
        '"' +
        (required ? " required" : "") +
        ">",
      help,
    );
  const grade = (key, label, help) => {
    const names = p.scale === "French" ? FRENCH : YDS;
    const opts = names
      .map((n, i) => [i, n])
      .filter(
        ([i, n]) =>
          p.scale !== "French" ||
          i === p[key] ||
          (!names.slice(0, i).includes(n) && names[p[key]] !== n),
      );
    return field(
      label,
      select(key, opts, p[key]),
      help + " For example, " + gradeName(key === "grade" ? 10 : 12, p) + ".",
    );
  };
  const weekdays = (key, label, help) =>
    field(
      label,
      '<div class="checks" role="group" aria-label="' +
        esc(label) +
        '">' +
        [1, 2, 3, 4, 5, 6, 0]
          .map(
            (i) =>
              '<label><input type="checkbox" name="' +
              key +
              '" value="' +
              i +
              '"' +
              (p[key].includes(i) ? " checked" : "") +
              ">" +
              DAYS[i].slice(0, 3) +
              "</label>",
          )
          .join("") +
        "</div>",
      help,
      true,
    );
  const opts = (key, label, items, empty, help) =>
    field(label, select(key, [["", empty], ...items], p[key]), help);
  const zoneList = [
    ...new Set([
      browserZone,
      "UTC",
      ...(p.zone === "auto" ? [] : [p.zone]),
      ...Intl.supportedValuesOf("timeZone"),
    ]),
  ];
  let html = section(
    "About you",
    txt(
      "name",
      "Name",
      "The name shown on your plan. A first name or nickname works, for example Alex.",
      80,
      true,
    ) +
      field(
        "Training time zone",
        select(
          "zone",
          [["auto", "Automatic · " + browserZone], ...zoneList],
          p.zone,
        ),
        "Automatic follows this device’s local time. Choose a fixed zone such as America/Denver to keep your home schedule while travelling.",
      ) +
      num(
        "height",
        "Height (optional)",
        p.units === "Metric"
          ? "Your height, for example 175 cm."
          : "Your height, for example 69 in.",
        1,
        300,
        true,
      ) +
      num(
        "weight",
        "Weight (optional)",
        p.units === "Metric"
          ? "Your current body weight, for example 70 kg."
          : "Your current body weight, for example 154 lb.",
        1,
        650,
        true,
      ),
  );
  const timeline = (key) =>
    field(
      "Goal timeline · preferred date",
      '<input type="date" name="' +
        key +
        '" value="' +
        esc(p[key] || "") +
        '">',
      "Choose a date to aim for. Your benchmark trend updates the estimate as you train.",
    );
  html += section(
    "Climbing",
    timeline("climbGoalDate") +
      grade(
        "grade",
        "Current repeatable route grade",
        "Choose a grade you can climb consistently.",
      ) +
      grade(
        "target",
        "Goal route grade",
        "Choose a grade you want to work toward.",
      ) +
      weekdays(
        "climbDays",
        "Climbing days",
        "Pick days you normally have wall access, for example Monday and Friday.",
      ) +
      num(
        "climbMinutes",
        "Comfortable climbing session · min",
        "A session duration you already tolerate, including rests. For example, 45 minutes.",
        5,
        240,
        false,
        true,
      ),
  );
  const sport = discipline(p.sport);
  let aerobic = opts(
    "sport",
    "Additional exercise goal (optional)",
    SPORTS,
    "None · climbing only",
    "Leave blank for a climbing-only plan. Choose Cycling and VO2 max to add bike sessions.",
  );
  if (sport) {
    aerobic +=
      timeline("sportGoalDate") +
      weekdays(
        "sportDays",
        sport + " days",
        "Choose days separate from climbing, for example Tuesday and Saturday.",
      ) +
      num(
        "sportMinutes",
        "Comfortable " + sport.toLowerCase() + " session · min",
        "Enter a comfortable outing length, for example 30 minutes.",
        5,
        720,
        false,
        true,
      ) +
      num(
        "volume",
        "Current weekly " + sport.toLowerCase() + " distance",
        "Typical total distance in a week, for example 15 {unit}.",
        0,
        3000,
        true,
      ) +
      num(
        "goalVolume",
        "Goal weekly " + sport.toLowerCase() + " distance",
        "Weekly distance you would like to build toward, for example 20 {unit}.",
        0,
        3000,
        true,
      );
    if (p.sport === SPORTS[0])
      aerobic +=
        num(
          "gain",
          "Current weekly ascent",
          "Total climbing on foot in a typical week, for example 800 {unit}.",
          0,
          30000,
          true,
        ) +
        num(
          "goalGain",
          "Goal weekly ascent",
          "Weekly uphill gain you would like to sustain, for example 1200 {unit}.",
          0,
          30000,
          true,
        );
    aerobic +=
      num(
        "vo2",
        "Current VO₂ max · mL/kg/min",
        "Optional measured or device-estimated value, for example 42. Leave blank if unknown.",
        1,
        150,
      ) +
      num(
        "goalVo2",
        "Goal VO₂ max · mL/kg/min",
        "Optional personal benchmark to track, for example 45.",
        1,
        150,
      );
  }
  html += section("Additional exercise", aerobic);
  html += section(
    "Supplemental training",
    opts(
      "hang",
      "Hangboarding (optional)",
      HANG,
      "None",
      "Choose a routine you already know. For example, Abrahamson-Baar No Hangs adds a low-load option.",
    ) +
      opts(
        "strength",
        "Strength work (optional)",
        STRENGTH,
        "None",
        "Both programs include leg work. Choose whole body for more lower-body strength and resilience.",
      ),
  );
  html +=
    '<p class="profile-evidence"><a href="/research.html#strength" target="_blank" rel="noopener">How strength progresses and balances recovery ↗</a></p>' +
    "<details><summary>Personal fueling references (optional)</summary>" +
    section(
      "Fueling references",
      "<p>Optional daily targets you choose yourself. Leave all four blank to hide fueling guidance from the calendar.</p>" +
        num(
          "fuelCarbs",
          "Carbohydrates · g/day",
          "Your daily carbohydrate target in grams, for example 250.",
          0,
          3000,
        ) +
        num(
          "fuelProtein",
          "Protein · g/day",
          "Your daily protein target in grams, for example 120.",
          0,
          1000,
        ) +
        num(
          "fuelFat",
          "Fat · g/day",
          "Your daily fat target in grams, for example 70.",
          0,
          1000,
        ) +
        num(
          "fuelCalories",
          "Total calories · kcal/day",
          "Your daily calorie target, for example 2400. This is a personal reference.",
          0,
          20000,
        ),
    ) +
    "</details>";
  if (review)
    html += section(
      "Benchmark update (optional)",
      txt(
        "route",
        "Benchmark route or wall",
        "Use a repeatable reference, for example Blue arete at the gym.",
        160,
      ) +
        txt(
          "result",
          "High point, attempts or movement quality",
          "Record an observation to compare next time, for example reached the final hold on attempt two.",
          300,
        ),
    );
  return html;
}
