from google.cloud import bigquery
client = bigquery.Client()
datasets = list(client.list_datasets())
for d in datasets:
    print(d.dataset_id)
