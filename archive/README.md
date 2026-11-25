# Historical editions

`streamlit/` preserves the retired Python/Streamlit beta, its tests, branding, Supabase schema and Apple Health instructions. These files document the previous app and are not part of the deployed Cloudflare application. Apple Health imports are not supported in the current app.

The current app, deployment commands and setup instructions are in the [main README](../README.md).

## Recover an old log

The root `start_demo.py` launcher still reads an existing root `.streamlit/secrets.toml` and imports an existing local beta database into local D1. Keep that private configuration and database in place.

For a hosted beta, export your private JSON log from its Profile page. From the repository root, place the export in the ignored `.local/` directory and run these commands to seed an **empty** Cloudflare database.

```sh
node archive/streamlit/worker/import-beta.js < .local/beta-export.json > .local/import.sql
npx wrangler d1 execute DB --remote --file .local/import.sql
```

The import inserts only if the destination has no profile. Keep exports and generated SQL out of version control.

To inspect or run the historical beta independently, work from `archive/streamlit/`, install its `requirements.txt` in a separate virtual environment and use `streamlit run streamlit_app.py`. Its historical tests use `python -m unittest discover -s tests` from that directory. Historical documentation may describe services and features that are no longer maintained.
