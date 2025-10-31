# BigQuery Agent App (Winsights Edition)

This package bundles a British-flavoured analytical agent that operates against
BigQuery datasets in the `wmt-ade-agentspace-dev` project. The agent prefers the
`ms_graph` dataset for Microsoft 365 and mailbox style queries, and the `gt_wf`
dataset for workforce analytics. Dataset metadata is cached locally for fast
prompt grounding, while a sandboxed Python tool supports rich dashboard
creation.

## Project layout

```
bq_agent_app/
├── README.md
├── bq_agent_app/
│   ├── __init__.py
│   ├── agent.py
│   ├── metadata_utils.py
│   ├── metadata/
│   │   ├── gt_wf_dataset_metadata.json
│   │   └── ms_graph_dataset_metadata.json
│   └── requirements.txt
└── deploy.py
```

## Configuration

The agent reads optional environment variables from a `.env` file or the
process environment:

- `BQ_AGENT_PROJECT` (defaults to `wmt-ade-agentspace-dev`)
- `BQ_AGENT_LOCATION` (defaults to `us-central1`)
- `BQ_AGENT_CREDENTIALS` (`ADC`, `OAUTH2`, or `SERVICE_ACCOUNT`; defaults to
  `ADC`)
- `BQ_AGENT_METADATA_DIR` to override the metadata directory

Authentication follows the Google ADK BigQuery tool conventions. By default the
agent relies on Application Default Credentials. For service accounts, store a
key file as `service_account_key.json` alongside the agent code.

## Dashboarding workflow

1. Ask the agent to investigate a question. It will route to the appropriate
dataset using the metadata heuristics.
2. Use the `run_python_analysis` tool for bespoke analysis, data wrangling, and
   chart authoring. Assign the final table to a variable named `result` to share
   tabular output.
3. Leverage the `compose_dashboard` helper (available within the Python tool) or
   call the `plan_dashboard` function tool to design multi-chart layouts quickly.
4. Generated charts are returned as base64-encoded PNG payloads that can be
   embedded in web dashboards or notebook experiences.

## Deployment

The `deploy.py` script continues to manage packaging for remote execution. Set
`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and
`GOOGLE_CLOUD_STORAGE_BUCKET` before running the script with the desired flag
(`--create`, `--update`, etc.).
