$env:TEMP = "C:\Temp"
$env:TMP = "C:\Temp"
adk deploy agent_engine `
  --project=wmt-ade-agentspace-dev `
  --region=us-central1 `
  --staging_bucket=gs://apex-agentengine-staging `
  --display_name=BQToolsOAUTHAgentTEST1 `
  ./bq_agent_app
