// Convert a private beta JSON export on stdin to a single insert-only D1 statement.
import { readFileSync } from "node:fs";
import { importBeta } from "../../../worker/actions.js";
import { todayIn } from "../../../web/model.js";
const data = JSON.parse(readFileSync(0, "utf8"));
const zone =
  data.profile?.[""]?.zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
const s = importBeta(data, todayIn(zone));
if (s.profile)
  process.stdout.write(
    "INSERT OR IGNORE INTO athlete(id,revision,payload) VALUES (1,1,'" +
      JSON.stringify(s).replaceAll("'", "''") +
      "');\n",
  );
