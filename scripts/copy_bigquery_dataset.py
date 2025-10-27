"""Copy all tables from one BigQuery dataset to another.

This script automates copying tables (including views) from a source
BigQuery dataset to a destination dataset, potentially across projects.

Usage:
    python scripts/copy_bigquery_dataset.py [--overwrite]

By default, the script copies the ``ade_ms_api_vw`` dataset from the
``wmt-ebs-ade-prod`` project into the ``ms_graph`` dataset in the
``wmt-ade-agentspace-dev`` project. Override the defaults by passing the
corresponding CLI flags.

The authenticated user/service account must have BigQuery Admin (or the
combination of permissions required for listing tables in the source and
creating tables in the destination project).
"""

from __future__ import annotations

import argparse
import logging
from typing import Iterable

from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from google.cloud.bigquery import CopyJobConfig


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-project",
        default="wmt-ebs-ade-prod",
        help=(
            "ID of the project that owns the source dataset (default: "
            "wmt-ebs-ade-prod)."
        ),
    )
    parser.add_argument(
        "--source-dataset",
        default="ade_ms_api_vw",
        help=(
            "ID of the dataset that contains the tables to copy (default: "
            "ade_ms_api_vw)."
        ),
    )
    parser.add_argument(
        "--destination-project",
        default="wmt-ade-agentspace-dev",
        help=(
            "ID of the project that should receive the copied tables (default: "
            "wmt-ade-agentspace-dev)."
        ),
    )
    parser.add_argument(
        "--destination-dataset",
        default="ms_graph",
        help=(
            "ID of the dataset that should receive the copied tables (default: "
            "ms_graph)."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help=(
            "Overwrite existing tables in the destination dataset. Without this flag,"
            " existing tables are left untouched."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Set the logging verbosity (default: INFO).",
    )
    return parser.parse_args()


def ensure_destination_dataset(
    client: bigquery.Client, dataset_id: str, location: str
) -> bigquery.Dataset:
    """Ensure the destination dataset exists, creating it if necessary.

    Args:
        client: BigQuery client bound to the destination project.
        dataset_id: Fully-qualified dataset ID (<project>.<dataset>).
        location: Region of the source dataset. The destination dataset must
            either already exist in the same region or will be created there.
    """

    try:
        dataset = client.get_dataset(dataset_id)
        LOGGER.info("Found destination dataset %s", dataset_id)
        if dataset.location != location:
            raise ValueError(
                "Destination dataset %s is in location %s but source dataset is in %s"
                % (dataset_id, dataset.location, location)
            )
        return dataset
    except NotFound:
        LOGGER.info("Destination dataset %s not found; creating it.", dataset_id)
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = location
        return client.create_dataset(dataset)


def list_tables(client: bigquery.Client, dataset_id: str) -> Iterable[bigquery.TableListItem]:
    """List tables in a dataset, raising a clear error if none exist."""
    tables = list(client.list_tables(dataset_id))
    if not tables:
        LOGGER.warning("No tables found in dataset %s", dataset_id)
    return tables


def copy_table(
    source_client: bigquery.Client,
    source_table_id: str,
    destination_client: bigquery.Client,
    destination_table_id: str,
    overwrite: bool,
) -> None:
    """Trigger a table-to-table copy job and wait for completion."""
    LOGGER.info("Copying %s -> %s", source_table_id, destination_table_id)

    job_config = CopyJobConfig()
    if overwrite:
        job_config.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE
    else:
        job_config.write_disposition = bigquery.WriteDisposition.WRITE_EMPTY

    copy_job = source_client.copy_table(
        source_table_id,
        destination_table_id,
        job_config=job_config,
    )
    copy_job.result()
    LOGGER.info("Finished copying %s", source_table_id)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    LOGGER.info(
        "Copying dataset %s.%s -> %s.%s",
        args.source_project,
        args.source_dataset,
        args.destination_project,
        args.destination_dataset,
    )

    source_client = bigquery.Client(project=args.source_project)
    destination_client = bigquery.Client(project=args.destination_project)

    source_dataset_ref = f"{args.source_project}.{args.source_dataset}"
    destination_dataset_ref = f"{args.destination_project}.{args.destination_dataset}"

    source_dataset = source_client.get_dataset(source_dataset_ref)
    ensure_destination_dataset(
        destination_client, destination_dataset_ref, source_dataset.location
    )

    for table in list_tables(source_client, source_dataset_ref):
        source_table_id = f"{source_dataset_ref}.{table.table_id}"
        destination_table_id = f"{destination_dataset_ref}.{table.table_id}"
        try:
            copy_table(
                source_client,
                source_table_id,
                destination_client,
                destination_table_id,
                overwrite=args.overwrite,
            )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error(
                "Failed to copy table %s to %s: %s",
                source_table_id,
                destination_table_id,
                exc,
            )
            raise

    LOGGER.info("All tables copied successfully")


if __name__ == "__main__":
    main()
