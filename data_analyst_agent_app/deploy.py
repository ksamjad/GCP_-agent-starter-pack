"""Deployment helper for the WMT data analyst agent."""

from __future__ import annotations

import os
<<<<<<< HEAD
from pathlib import Path
from typing import Dict, Sequence
=======
import sys
from pathlib import Path
from typing import Dict, List, Sequence
>>>>>>> 053d79e5652e52b720dbaa5a481f0243cfa6415c

from absl import app, flags
from dotenv import load_dotenv

<<<<<<< HEAD
try:
    from data_analyst_agent_app.agent import root_agent
except ModuleNotFoundError:  # fallback for script execution
    from data_analyst_agent_app.agent import root_agent
=======
if __package__ is None:
    _current_dir = Path(__file__).resolve().parent
    _package_root = _current_dir.parent
    if str(_package_root) not in sys.path:
        sys.path.insert(0, str(_package_root))

try:
    from data_analyst_agent_app.agent import root_agent
except ModuleNotFoundError:  # pragma: no cover - fallback for script execution
    from agent import root_agent
>>>>>>> 053d79e5652e52b720dbaa5a481f0243cfa6415c

import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp


_APP_ROOT = Path(__file__).resolve().parent


<<<<<<< HEAD
def _default_extra_packages() -> list[str]:
    """Return the files that must ship with the remote deployment."""

    package_paths: list[Path] = [
=======
def _default_extra_packages() -> List[str]:
    """Return the files that must ship with the remote deployment."""

    package_paths: List[Path] = [
>>>>>>> 053d79e5652e52b720dbaa5a481f0243cfa6415c
        _APP_ROOT / "__init__.py",
        _APP_ROOT / "agent.py",
        _APP_ROOT / "metadata_utils.py",
    ]

    metadata_dir = _APP_ROOT / "metadata"
    if metadata_dir.exists():
        package_paths.append(metadata_dir)

    return [str(path) for path in package_paths if path.exists()]


def _requirements_path() -> str:
    """Return the path to the requirements file for the deployment."""
<<<<<<< HEAD
    return str(_APP_ROOT / "requirements.txt")


# ----------------------------------------------------------------------
# Flag Definitions
# ----------------------------------------------------------------------
=======

    requirements_path = _APP_ROOT / "requirements.txt"
    return str(requirements_path)

>>>>>>> 053d79e5652e52b720dbaa5a481f0243cfa6415c
FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCP bucket.")

flags.DEFINE_string("resource_id", None, "ReasoningEngine resource ID.")
flags.DEFINE_bool("create", False, "Creates a new deployment.")
flags.DEFINE_bool("quicktest", False, "Try a new deployment with one turn.")
flags.DEFINE_bool("delete", False, "Deletes an existing deployment.")
flags.DEFINE_bool("update", False, "Updates an existing deployment.")
flags.mark_bool_flags_as_mutual_exclusive(["create", "delete", "update", "quicktest"])
flags.DEFINE_string(
    "message",
    "What insights can you surface today?",
    "Message to send when running --quicktest.",
)


<<<<<<< HEAD
# ----------------------------------------------------------------------
# Environment & Deployment Logic
# ----------------------------------------------------------------------
def _resolve_env_vars() -> Dict[str, str]:
    """Populate deployment environment variables for the remote agent."""

    env_vars: Dict[str, str] = {}
=======
def _resolve_env_vars() -> Dict[str, str]:
    """Populate deployment environment variables for the remote agent."""

>>>>>>> 053d79e5652e52b720dbaa5a481f0243cfa6415c
    project_scope = os.getenv("DATA_ANALYST_PROJECT", "wmt-ade-agentspace-dev")
    location = os.getenv("BIGQUERY_LOCATION", "us")
    return {
        "DATA_ANALYST_PROJECT": project_scope,
        "BIGQUERY_LOCATION": location,
    }


def create(env_vars: Dict[str, str]) -> None:
    """Creates a new deployment."""

    app_definition = AdkApp(
        agent=root_agent,
        enable_tracing=True,
        env_vars=env_vars,
    )

    remote_agent = agent_engines.create(
        app_definition,
        requirements=_requirements_path(),
        extra_packages=_default_extra_packages(),
        display_name="WMT Data Analyst Agent",
        description="Metadata-aware analyst with British charm and dashboards.",
    )
    print(f"✅ Created remote agent: {remote_agent.resource_name}")


def update(env_vars: Dict[str, str], resource_id: str) -> None:
    """Updates an existing deployment in-place."""

    app_definition = AdkApp(
        agent=root_agent,
        enable_tracing=True,
        env_vars=env_vars,
    )

    agent_engines.update(
        resource_name=resource_id,
        agent_engine=app_definition,
        requirements=_requirements_path(),
        display_name="WMT Data Analyst Agent",
        description="Metadata-aware analyst with British charm and dashboards.",
        extra_packages=_default_extra_packages(),
    )

    print(f"✅ Updated remote agent: {resource_id}")


def delete(resource_id: str) -> None:
    """Deletes a remote deployment."""

    remote_agent = agent_engines.get(resource_id)
    remote_agent.delete(force=True)
    print(f"🗑️ Deleted remote agent: {resource_id}")


def _resolve_session_id(session: object) -> str:
    """Extract a session identifier from the object returned by create_session."""

    for candidate in ("session_id", "id", "name"):
        value = getattr(session, candidate, None)
        if value:
            return str(value)

    if isinstance(session, dict) and session.get("id"):
        return str(session["id"])

    raise ValueError("Unable to determine session identifier from create_session().")


def _print_event(event: object) -> None:
    """Pretty print a streaming event for debugging purposes."""

    event_type = getattr(event, "event_type", None)
    header = f"[{event_type}]" if event_type else "[event]"

    if hasattr(event, "text") and getattr(event, "text"):
        print(header, getattr(event, "text"))
        return

    if hasattr(event, "candidates") and getattr(event, "candidates"):
        candidates = getattr(event, "candidates")
        print(header, "candidates:")
        for idx, candidate in enumerate(candidates, start=1):
            text = getattr(candidate, "text", repr(candidate))
            print(f"  {idx}. {text}")
        return

    if hasattr(event, "to_dict"):
        print(header, event.to_dict())
        return

    print(header, repr(event))


def _resolve_session_id(session: object) -> str:
    """Extract a session identifier from the object returned by create_session."""

    # The SDK may return either a proto message, a dataclass, or a mapping depending
    # on the installed version. Try the common attributes first, then fall back to
    # dictionary-style access so the helper works across environments.
    for candidate in ("session_id", "id", "name"):
        value = getattr(session, candidate, None)
        if value:
            return str(value)

    if isinstance(session, dict) and session.get("id"):
        return str(session["id"])

    raise ValueError("Unable to determine session identifier from create_session().")


def _print_event(event: object) -> None:
    """Pretty print a streaming event for debugging purposes."""

    event_type = getattr(event, "event_type", None)
    header = f"[{event_type}]" if event_type else "[event]"

    # Many streaming events expose a `text` or `content` attribute. Attempt the
    # most descriptive representation we can find before falling back to repr().
    if hasattr(event, "text") and getattr(event, "text"):
        print(header, getattr(event, "text"))
        return

    if hasattr(event, "candidates") and getattr(event, "candidates"):
        candidates = getattr(event, "candidates")
        print(header, "candidates:")
        for idx, candidate in enumerate(candidates, start=1):
            text = getattr(candidate, "text", repr(candidate))
            print(f"  {idx}. {text}")
        return

    if hasattr(event, "to_dict"):
        print(header, event.to_dict())
        return

    print(header, repr(event))


def send_message(resource_id: str, message: str) -> None:
    """Send a message to the deployed agent."""

    remote_agent = agent_engines.get(resource_id)
<<<<<<< HEAD
    session = remote_agent.create_session(user_id="data-analyst-user")
    session_id = _resolve_session_id(session)

    print(f"🔍 Trying remote agent: {resource_id}")
=======
    session = remote_agent.create_session(
        user_id="data-analyst-user",
    )
    session_id = _resolve_session_id(session)
    print(f"Trying remote agent: {resource_id}")
>>>>>>> 053d79e5652e52b720dbaa5a481f0243cfa6415c
    for event in remote_agent.stream_query(
        user_id="data-analyst-user",
        session_id=session_id,
        message=message,
    ):
        _print_event(event)
<<<<<<< HEAD

    print("✅ Done.")


# ----------------------------------------------------------------------
# Main Entrypoint
# ----------------------------------------------------------------------
=======
    print("Done.")


>>>>>>> 053d79e5652e52b720dbaa5a481f0243cfa6415c
def main(argv: Sequence[str]) -> None:
    del argv

    load_dotenv()
    env_vars = _resolve_env_vars()

    project_id = FLAGS.project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = FLAGS.location or os.getenv("GOOGLE_CLOUD_LOCATION")
    bucket = FLAGS.bucket or os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

    print(f"PROJECT: {project_id}")
    print(f"LOCATION: {location}")
    print(f"BUCKET: {bucket}")

    if not project_id:
        print("❌ Missing required environment variable: GOOGLE_CLOUD_PROJECT")
        return
    if not location:
        print("❌ Missing required environment variable: GOOGLE_CLOUD_LOCATION")
        return
    if not bucket:
        print("❌ Missing required environment variable: GOOGLE_CLOUD_STORAGE_BUCKET")
        return

    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=f"gs://{bucket}",
    )

    if FLAGS.create:
        create(env_vars)
    elif FLAGS.delete:
        if not FLAGS.resource_id:
            print("❌ resource_id is required for delete")
            return
        delete(FLAGS.resource_id)
    elif FLAGS.update:
        if not FLAGS.resource_id:
            print("❌ resource_id is required for update")
            return
        update(env_vars, FLAGS.resource_id)
    elif FLAGS.quicktest:
        if not FLAGS.resource_id:
            print("❌ resource_id is required for quicktest")
            return
        send_message(FLAGS.resource_id, FLAGS.message)
    else:
        print("⚠️ Unknown command. Use --create, --update, --delete, or --quicktest.")


if __name__ == "__main__":
    app.run(main)
