## bq_agent_app (Winsights)

- Place your `gt_wf_dataset_metadata.json` and `ms_graph_dataset_metadata.json` in `bq_agent_app/metadata/`.
- Verify locally: `python verify_package.py`
- Create agent: `python deploy.py --create --project_id=<GCP_PROJECT> --location=us-central1 --bucket=<STAGING_BUCKET>`
- Update agent: `python deploy.py --update --resource_id=<RESOURCE_ID> --project_id=...`
- Quicktest: `python deploy.py --quicktest --resource_id=<RESOURCE_ID> --message "Show attrition"`
