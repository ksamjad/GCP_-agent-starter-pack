import os
import pandas as pd
from google.cloud import bigquery, storage
import plotly.express as px
from io import BytesIO
from .base_agent import BaseAgent
from .base_agent_config import BaseAgentConfig
from .events.event import Event
from .invocation_context import InvocationContext

MAX_IN_MEMORY_ROWS = 10000  # You can tweak this per your requirements

class BigQueryDataAnalyzerAgentConfig(BaseAgentConfig):
    project_id: str = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("DEFAULT_PROJECT_ID")
    default_dataset: str = os.getenv("BQ_DEFAULT_DATASET", "your_default_dataset")
    credentials_type: str = os.getenv("CREDENTIALS_TYPE", "ADC")
    output_gcs_path: str = os.getenv("OUTPUT_GCS_PATH")
    google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    storage_bucket: str = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

class BigQueryDataAnalyzerAgent(BaseAgent):
    config_type = BigQueryDataAnalyzerAgentConfig

    project_id: str
    default_dataset: str
    credentials_type: str
    output_gcs_path: str
    google_cloud_location: str
    storage_bucket: str

    async def _run_async_impl(self, ctx: InvocationContext):
        user_query = ctx.latest_user_utterance
        
        sql, viz_type = self._parse_user_query(user_query)
        client = bigquery.Client(project=self.project_id)
        df = client.query(sql).to_dataframe()
        
        # Large datasets: Use GCS to avoid OOM/row-limit
        if len(df) > MAX_IN_MEMORY_ROWS:
            report_url = self._export_bigquery_to_gcs(sql)
        else:
            report_bytes = self._dataframe_to_csv_bytes(df)
            report_url = None

        # Visualization
        fig_bytes = self._generate_visualization(df, viz_type) if viz_type else None
        
        # Build Event with result(s)
        result_attachments = []
        if fig_bytes:
            result_attachments.append(('dashboard.png', fig_bytes))
        if report_url:
            event_content = f"Report is ready [Download]({report_url})"
        else:
            event_content = "Download full report attached."
            result_attachments.append(('report.csv', report_bytes))
        
        yield Event(
            content=event_content,
            attachments=result_attachments
        )

    def _run_bigquery_sql(self, sql: str):
        client = bigquery.Client(project=self.project_id)
        return client.query(sql).to_dataframe()

    def _generate_visualization(self, df: pd.DataFrame, viz_type: str) -> bytes:
        if viz_type == "bar":
            fig = px.bar(df)
        elif viz_type == "line":
            fig = px.line(df)
        else:
            fig = px.scatter(df)
        buf = BytesIO()
        fig.write_image(buf, format="png")
        buf.seek(0)
        return buf.read()

    def _dataframe_to_csv_bytes(self, df: pd.DataFrame) -> bytes:
        buf = BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return buf.read()

    def _export_bigquery_to_gcs(self, sql: str) -> str:
        client = bigquery.Client(project=self.project_id)
        bucket_name = self.storage_bucket
        destination_blob = f"bigquery-results/{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}_report.csv"
        gcs_uri = f"gs://{bucket_name}/{destination_blob}"

        # Create or get a temp table
        job = client.query(sql)
        job.result()
        temp_table = job.destination

        # Extract to GCS
        extract_job = client.extract_table(
            temp_table,
            gcs_uri,
            location=self.google_cloud_location,
        )
        extract_job.result()

        # Build public/shared URL
        return f"https://storage.cloud.google.com/{bucket_name}/{destination_blob}"

    def _parse_user_query(self, user_query: str):
        """ Naive parser – expand with NLP/LLM or templates as needed. """
        q = user_query.lower()
        if "sales by month" in q:
            sql = f"SELECT month, SUM(sales) as total_sales FROM `{self.default_dataset}.sales` GROUP BY month ORDER BY month"
            viz_type = "line"
        elif "download all orders" in q:
            sql = f"SELECT * FROM `{self.default_dataset}.orders`"
            viz_type = None
        elif "top customers" in q:
            sql = f"SELECT customer_id, SUM(purchase) as total_purchase FROM `{self.default_dataset}.orders` GROUP BY customer_id ORDER BY total_purchase DESC LIMIT 20"
            viz_type = "bar"
        else:
            raise ValueError("I couldn't understand your query. Please specify your analytics request.")
        return sql, viz_type