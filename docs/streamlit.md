# Moving from the Streamlit beta

The current training app runs on Cloudflare Workers with a private D1 database. Follow the [setup and migration instructions](../README.md) to create your own deployment or open the local version.

If you used the local Streamlit app, run the current local launcher from the same folder to reuse its password and copy its log. A hosted Streamlit user can download a private JSON export from the old Profile page and import it into an empty D1 deployment. Store personal exports outside version control.

The original Python entry point remains available for accessing and exporting an existing beta log. Use the Cloudflare edition for the current calendar, profile and two-week reviews.
