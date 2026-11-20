# Host your own Project 5.14

Each athlete gets one GitHub fork, one Streamlit app with a personal password, and one private database. The app generates the plan in Python on demand. The browser app runs without a ChatGPT subscription or an OpenAI API key.

## Deploy the beta

1. Sign in to GitHub and select **Fork → Create fork** on the Project 5.14 repository. If the beta is still on the `streamlit-beta` branch, **uncheck “Copy the main branch only”** when forking. In your fork, select the branch containing `streamlit_app.py`. Once the beta is merged, use `main`.
2. Create a **Free** organization and a dedicated project in [Supabase](https://supabase.com/dashboard). Generate a long database password and save it in your password manager. In **SQL Editor → New query**, paste the entire [database setup](database.sql) from the same branch and click **Run** once. This creates the private log and the optional, initially disabled phone import.
3. In Supabase click **Connect** and copy the **Session pooler** connection string (port 5432, IPv4 compatible). Replace the database password placeholder. A letters-and-digits generated password avoids URL escaping. If your password contains reserved characters, URL-encode just the password. Keep the database password separate from the app password.
4. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with GitHub. Select **Create app → Deploy a public app from GitHub** (or the repository deployment option shown). Select **your fork**, the branch from step 1, and **streamlit_app.py** for the entrypoint. Choose an available app URL. For a private pilot, grant Streamlit access only to the intended repository through GitHub.
5. Open **Advanced settings**, select **Python 3.12**, and paste the following into **Secrets**. Replace both values with your own. Use a unique password-manager-generated app password of at least 16 characters. Keep these values out of all GitHub files, including public forks.

   ```toml
   APP_PASSWORD = "YOUR-UNIQUE-APP-PASSWORD"
   DATABASE_URL = "postgresql://postgres.PROJECT_REF:YOUR_DB_PASSWORD@YOUR_SESSION_POOLER_HOST:5432/postgres"
   ```

6. Select **Deploy**, open the URL in a private browser window, unlock with the app password, and fill out the training profile. Copy your URL to your phone’s home screen. To change the password, update **App settings → Secrets**, save, and reboot the app.
7. Confirm persistence by closing the tab, reopening the app, unlocking it and checking **Profile**. Reboot from the Streamlit dashboard and repeat. Your profile and dated records live in Supabase. If the database sleeps, restore it from the Supabase dashboard and reopen the app. Keep the project on the free plan for a free deployment.

[Streamlit free hosting](https://docs.streamlit.io/deploy/streamlit-community-cloud) · [Community Cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) · [Supabase connections](https://supabase.com/docs/guides/database/connecting-to-postgres) · [Supabase free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)

## What happens each day

Day one opens directly to a workout. Starting the next local day, **Today** asks about yesterday. Report what you did or choose the easy fallback. Missing a week leads to one check-in about yesterday. An open, connected tab checks for a date change each minute. If the host or browser sleeps, reopen or refresh the app. The daily workout is saved under its calendar date and reopens across devices. No background email is sent by the beta.

The schedule repeats 12-week training blocks indefinitely. Climbing days and aerobic days are explicit. Other days are rest. A shorter week, a missed check-in, or an ambitious goal date never creates catch-up work. Goal review dates prompt reassessment. The most recent repeatable grade anchors route suggestions. Aerobic goals use conversational work. VO₂ max is an outcome you can track, and the beta does not prescribe maximal intervals. Height and weight are optional context. Fueling advice supports regular meals and recovery. You may enter personal energy and macro references under **Profile**.

Every 28 days, **Today** prompts for a matched route, grade, high point, attempts, final-third technique and optional measured VO₂ max. Open **Progress** to record a benchmark earlier or review trends. Sundays show the preceding seven days of saved plans and reported activity. **Profile** supports schedule edits, pause/resume, data export and [optional iPhone imports](apple-health.md). Use **Rest today** or correct yesterday’s feedback for an immediate change to today’s workout. Ordinary profile edits affect newly generated workouts.

## Personal data and backups

The log is in the private `project514.entry` table in your Supabase project. The database stores your profile, check-ins, dated workout snapshots, benchmarks, rest decisions, safety holds, and any imported summaries. The hosted app requires its database connection to open the log. Closing the tab clears the browser login when its session ends. Anyone with the app password can access this single-athlete log. The database project owner and hosting account owner control the service and credentials.

Use **Profile → Prepare private JSON export** for a readable personal copy. For a restorable database backup use Supabase’s [CLI backup guide](https://supabase.com/docs/guides/deployment/cli/backing-up-a-database). To erase training data, run `truncate table project514.entry;` yourself in the dedicated project’s SQL Editor. This also revokes the current phone token. Delete any exported copies separately. If you stop using the app, delete the Streamlit app and its dedicated database project from their respective dashboards.

## Try locally

Use Python 3.12. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell activate with `.venv\Scripts\Activate.ps1`. Create `.streamlit/secrets.toml` on your computer using the following settings and your own password:

```toml
APP_PASSWORD = "YOUR-UNIQUE-APP-PASSWORD"
LOCAL_SQLITE_PATH = ".local/training.sqlite3"
```

Run `python -m streamlit run streamlit_app.py` and open the local URL printed in the terminal. This explicit local mode persists on your computer. Use `DATABASE_URL` for Community Cloud because [local files there are ephemeral](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data). To test, run `python -m unittest discover -s tests` from the same environment.

## Publishing a forkable template

Deploy a private pilot from this branch now. Before switching the historical repository to public, review **its entire Git history**, including earlier single-athlete pilot files and training assumptions. A clean public template can be created from the reviewed release snapshot if the prior history should stay private. Distribute only source files and setup instructions. Keep athlete databases, exports, app secrets and phone tokens outside the repository.
