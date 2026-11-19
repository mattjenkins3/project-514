# Launch the private pilot on Render

This Blueprint creates one Starter web service and a 1 GB persistent disk. Render's listed prices are US$7/month for Starter and US$0.25/month for the disk, before tax or any additional usage. Use the dashboard total to approve the charge. [Render pricing](https://render.com/pricing)

1. Create a [Render account](https://dashboard.render.com/) and connect GitHub. If offered a repository selection, grant access to `mattjenkins3/project-514` only.
2. In the Render dashboard, choose **New → Blueprint** and select `mattjenkins3/project-514`, branch `main`. Use the root `render.yaml`.
3. Set `PROJECT514_PILOT_START` to your chosen rehearsal start as `YYYY-MM-DD` in America/Denver. This is separate from the official training start. Set `PROJECT514_PILOT_PASSWORD` to a new random password of at least 32 characters from your password manager. The Blueprint generates `PROJECT514_SESSION_KEY`. Render supplies `RENDER_EXTERNAL_URL`; leave the other values as specified.
4. Review the proposed Starter service and 1 GB disk, then approve **Deploy Blueprint** if the displayed charge is acceptable. The service starts the app once, checks `/healthz`, and serves HTTPS on its assigned `onrender.com` URL. Future commits do not automatically deploy.
5. Open the service URL and sign in with the pilot password. Open that day's **Check-in**, submit a synthetic entry and make a correction, then verify the **HTML** and **Text** previews. A future pilot start shows an empty history until that date. A browser restart can require signing in again.
6. Share the service URL if you want the hosted flow verified. Keep the password in your password manager. Backup and restore drills and the connected pilot are in [the pilot runbook](pilot.md).

The Gmail settings stay in the GitHub Actions `pilot` environment. This Blueprint contains no Gmail credentials, sends no email, and installs no scheduled job. Hosted check-in URLs contain the day and require sign-in. Keep this single-user pilot on synthetic data until data-handling and production requirements are approved. To stop Render charges, delete the service and confirm that the persistent disk has also been removed after exporting any needed pilot data.
