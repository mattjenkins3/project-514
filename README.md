# Project 5.14

![Project 5.14 climbing training log](assets/project-514.svg)

Build a personal 12-week climbing calendar around your grade, training days and current workload. Add hiking for mountaineering, running or cycling if you want aerobic training. Each athlete runs a separate password-protected app and database.

## Set up your own private training log

You need a GitHub account, a free Cloudflare account and Node.js 24 LTS with npm. The app runs on Cloudflare Workers. Cloudflare D1 holds the profile, plan, feedback and reviews. A public fork contains the app source. Anyone who has your app password can open your training log. [Node.js downloads](https://nodejs.org/en/download) · [Cloudflare signup](https://dash.cloudflare.com/sign-up) · [Workers Free plan](https://developers.cloudflare.com/workers/platform/pricing/) · [D1 free allowance](https://developers.cloudflare.com/d1/platform/pricing/)

1. **Fork this repository.** On GitHub select **Fork → Create fork**. On your fork select **Code → Local → HTTPS** and copy the clone URL. Open Terminal or PowerShell. Replace `YOUR-FORK-URL` below with the copied URL. Run the commands one at a time.

   ```sh
   git clone YOUR-FORK-URL project-514
   cd project-514
   npm ci
   ```

2. **Connect Cloudflare.** Sign into Cloudflare and stay on the Free plan. Open **Workers & Pages** and choose your account’s free `workers.dev` subdomain if prompted. From the same project directory, run the command below. Approve the browser login for your own Cloudflare account and return to the terminal. [Cloudflare subdomain setup](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/)

   ```sh
   npx wrangler login
   ```

3. **Create your database.** Run the command below. If Wrangler offers to add or update a configuration binding automatically, decline and use the next step. Copy the new database’s UUID from the output. You can also find it in the Cloudflare dashboard under **D1 SQL database → project-514**. [Cloudflare D1 setup](https://developers.cloudflare.com/d1/get-started/)

   ```sh
   npx wrangler d1 create project-514
   ```

4. **Connect your app to that database.** Open `wrangler.jsonc` in a text editor. In the existing `d1_databases` entry replace only `00000000-0000-0000-0000-000000000000` with your UUID and save. Keep the binding named `DB`. If your account already has a Worker or database called `project-514`, choose unused names first and use those names consistently in the configuration and creation command.

5. **Initialize and deploy.** Run both commands. Accept the migration prompt. The first creates the tables in your Cloudflare database. The second uploads the app and prints its HTTPS address.

   ```sh
   npx wrangler d1 migrations apply DB --remote
   npm run deploy
   ```

6. **Set your own password.** Use a password manager to generate and save a unique password of at least 16 characters. Run the command below, then paste the password at the hidden prompt. This stores an encrypted Worker secret. The app requires this secret before it will serve any training data. Repeat the command to change the password and invalidate existing sessions. [Cloudflare Worker secrets](https://developers.cloudflare.com/workers/configuration/secrets/)

   ```sh
   npx wrangler secret put APP_PASSWORD
   ```

7. **Open and bookmark your app.** Use the HTTPS URL printed by deploy, typically `https://project-514.YOUR-SUBDOMAIN.workers.dev`. Enter your password and select **Unlock**. Choose your units and grading system at the top, then complete **Your training profile → Create my 12-week plan**. On another device, the same URL and password open the saved log. A session cookie keeps the app unlocked across logo clicks, reloads, and new tabs in the same browser session. A fresh browser session or a different device requires the password. **Lock app** clears the session. Browsers configured to restore sessions may also restore session cookies.

## Using the calendar

Set optional climbing and cardio target dates in Profile. The goal outlook counts the 12-week training blocks to each target. With improving comparable benchmarks at least two weeks apart, it also estimates timing from your recorded pace. The daily brief includes session stages, technique and any scheduled finger or strength work. Open **Training research** in the footer for the evidence and the ten-minute no-hang routine.

**Personal fueling references are optional.** In Profile, enter any of four daily targets — carbohydrates (grams), protein (grams), fat (grams), and total calories (kcal). The calendar shows only the targets you enter. Leave all four blank to hide calendar fueling guidance, or clear them later to remove it. Older free-text meal reminders are replaced by these structured targets.

**Strength work runs on every non-climbing day** when selected, including cardio days. Up to two sessions in a rolling seven-day window are main strength sessions, separated by at least two calendar days. Other days use short, easy shoulder, trunk, hip and balance circuits. The main A/B sessions keep familiar movement patterns while sets and repetition ranges progress across the block. Recovery weeks and fatigue reports reduce demand; pulling is limited before a climbing day. Upper-body/core includes a small leg dose, while whole-body adds more lower-body work. The plan specifies effort, sets, repetitions, rest and equipment, leaving weights for you to choose. Pausing training, a pain-related hold, or choosing **Rest today** suspends added strength. Weekly climbing/cardio totals exclude strength and finger sessions.

**Explore weekly volume** by hovering over the Block volume chart or focusing a week with the keyboard. The tooltip shows climbing minutes, cardio minutes, the total and that week’s theme.

**Training research** includes 33 annotated sources, with links from strength sessions and the no-hang routine. The app distinguishes tested findings from its own coaching choices.

**Visuals and motion.** The interface uses yellow, blue, charcoal and coral with locally hosted fonts and artwork. The intro is a 1152 × 768 model-generated film of a tied oval climbing-rope bundle. It was generated locally with [LTX-2.3 via MLX](https://github.com/dgrauet/ltx-2-mlx), then background-matted frame by frame with [Matting Anything 2](https://github.com/ChenyiZhang007/Matting-Anything-2) and interpolated to 60 fps with [RIFE](https://github.com/hzwer/Practical-RIFE). Its transparent WebM and matching WebP poster are bundled with the app. The browser opens the rope film immediately on password submission and every refresh. The 60 fps film uses a matched-pose full rotation and a circular interpolated join. It loops until you click anywhere or press Enter/Space. Entry rapidly accelerates the rotation while fading into the loaded plan. Reduced-motion devices show the static rope and wait for the same entry action. No model downloads, external media services or rendering libraries are needed to run or deploy the app.

**Abrahamsson–Baar No Hangs** schedules two light ten-minute routines on each active day, including lighter weeks, with rest days excluded. Leave at least six hours between finger-loading sessions. The calendar links to the exact routine on **Training research**.

The first block starts the day after setup in your training time zone. Switch between **Week** and **12 weeks**. Select any calendar day for its workout. Profile changes and reports recalculate the remaining schedule. Past workout prescriptions stay in your log.

If you set up on Sunday, November 1, 2026, your plan starts Monday, November 2. When you return on Wednesday, November 4, you can report Monday and Tuesday separately or select **Continue with plan**. Blank days count as completed as directed. You can report or correct a past day later under **Progress**.

Every 14 days from the first training day, an optional review asks about your goals, current workload and a comparable climbing benchmark. Use **Progress → Update goals & benchmark** between reminders. After your block finishes, **Start next 12-week block** creates another calendar. **Profile → Export my training log** saves a private JSON copy.

## Updates and local use

To deploy a later version, sync your fork on GitHub, pull the changes into your local copy, verify the database UUID in `wrangler.jsonc`, then repeat `npm ci`, the remote migration command and `npm run deploy`. Reuse the same Worker name and D1 database to keep your URL and history. Keep credentials, exports and personal training databases outside Git.

For a Mac or PC preview, install Node.js 24 LTS and Python 3.12, then run `python3 start_demo.py` (Windows: `py -3.12 start_demo.py`). The launcher sets up a local Worker and D1 database, prints a loopback URL and saves the password in the ignored `.dev.vars` file. Open the URL in Chrome and leave the server running. On an existing local Streamlit beta installation, the launcher reuses the password and copies the profile and dated training records into the new database on first run. Add your name and confirm the imported profile. The original SQLite database remains available.

For a hosted Streamlit beta, export your log from its Profile page before moving. To seed an **empty** Cloudflare app, keep that private export in an ignored `.local` folder and use Bash to run `node worker/import-beta.js < .local/beta-export.json > .local/import.sql`, then `npx wrangler d1 execute DB --remote --file .local/import.sql`. The import only inserts a profile if the destination is empty. The Cloudflare edition uses manual performance and benchmark entries.

Run `npm test` for the calendar, review and migration regression tests. A local app uses local D1 storage. The deployed app uses the remote database configured in your fork.
