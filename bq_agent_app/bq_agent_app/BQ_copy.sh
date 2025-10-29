#!/bin/bash

# --- Configuration (Updated with your info) ---
SOURCE_PROJECT="wmt-ebs-ade-prod"
SOURCE_DATASET="ade_ms_api_vw"
DESTINATION_PROJECT="wmt-ade-agentspace-dev"
DESTINATION_DATASET="ms_graph"

# !!!--- UPDATE THIS ---!!!
# Find this from the BigQuery UI (e.g., "US", "EU", "us-central1")
LOCATION="US" 
# ---------------------------------------------

# Array of STANDARD TABLES
TABLES=(
    "o365_usage_reports"
    "o365_auditing"
    "o365_groups"
    "o365_sharepoint"
    "o365_teams"
    "o365_users"
    "azure_ad_users"
    "azure_ad_groups"
    "azure_ad_signins"
    "azure_ad_domains"
    "azure_ad_directory_audits"
)

# Array of VIEWS
VIEWS=(
    "ms_graph_365_userlicenses"
    "ms_graph_auditlogs"
    "ms_graph_directory_objects"
    "ms_graph_drives"
    "ms_graph_group_lifecycle_policies"
    "ms_graph_groups"
    "ms_graph_sites"
    "ms_graph_subscribed_skus"
    "ms_graph_users"
    "ms_graph_service_principals"
    "ms_graph_signins"
    "ms_graph_teams"
)

# Set the default project for the bq tool
gcloud config set project $DESTINATION_PROJECT

# 1. Copy all standard tables (with --location flag added)
echo "--- Copying Standard Tables ---"
for TABLE in "${TABLES[@]}"; do
    echo "Copying $TABLE..."
    bq cp \
        --location=$LOCATION \
        "$SOURCE_PROJECT:$SOURCE_DATASET.$TABLE" \
        "$DESTINATION_PROJECT:$DESTINATION_DATASET.$TABLE"
done

# 2. Create new tables from all views
echo "--- Creating Tables from Views ---"
for VIEW in "${VIEWS[@]}"; do
    echo "Creating table from $VIEW..."
    bq query \
        --use_legacy_sql=false \
        --destination_table "$DESTINATION_PROJECT:$DESTINATION_DATASET.$VIEW" \
        "SELECT * FROM \`$SOURCE_PROJECT.$SOURCE_DATASET.$VIEW\`"
done

echo "--- All operations complete. ---"