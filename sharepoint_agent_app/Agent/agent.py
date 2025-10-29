"""SharePoint delegated access agent definition.

This module defines a Vertex AI Agent Builder agent that can answer questions about
Microsoft SharePoint Online content. It authenticates against Microsoft Graph using
delegated permissions for the signed-in user and exposes a single tool that runs
keyword searches scoped to a SharePoint site.
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import msal
import requests
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.tools.function_tool import FunctionTool

load_dotenv()

DEFAULT_SCOPES = [scope.strip() for scope in os.getenv("GRAPH_SCOPES", "Sites.Read.All Files.Read.All").split() if scope.strip()]


@dataclass(slots=True)
class SharePointSearchResult:
  """Serializable representation of a SharePoint search hit."""

  name: Optional[str]
  url: Optional[str]
  summary: Optional[str]
  last_modified: Optional[str]
  resource_type: Optional[str]

  def as_dict(self) -> Dict[str, Optional[str]]:
    return {
        "name": self.name,
        "url": self.url,
        "summary": self.summary,
        "last_modified": self.last_modified,
        "resource_type": self.resource_type,
    }


class DelegatedGraphAuthenticator:
  """Handles device-code delegated authentication for Microsoft Graph."""

  def __init__(
      self,
      client_id: str,
      tenant_id: str,
      scopes: Optional[List[str]] = None,
      cache_path: Optional[pathlib.Path] = None,
  ) -> None:
    if not client_id or not tenant_id:
      raise ValueError("GRAPH_CLIENT_ID and GRAPH_TENANT_ID must be configured.")

    self._authority = f"https://login.microsoftonline.com/{tenant_id}"
    self._scopes = scopes or DEFAULT_SCOPES
    self._cache = msal.SerializableTokenCache()
    self._cache_path = cache_path or pathlib.Path(os.getenv("GRAPH_TOKEN_CACHE", "~/.graph_sharepoint_cache.json")).expanduser()

    if self._cache_path.exists():
      try:
        self._cache.deserialize(self._cache_path.read_text(encoding="utf-8"))
      except Exception:
        # Corrupt cache – delete and continue with a clean one.
        self._cache = msal.SerializableTokenCache()
        self._cache_path.unlink(missing_ok=True)

    self._app = msal.PublicClientApplication(
        client_id=client_id,
        authority=self._authority,
        token_cache=self._cache,
    )

  def _persist_cache(self) -> None:
    if self._cache.has_state_changed:
      self._cache_path.parent.mkdir(parents=True, exist_ok=True)
      self._cache_path.write_text(self._cache.serialize(), encoding="utf-8")

  def acquire_token(self) -> str:
    accounts = self._app.get_accounts()
    if accounts:
      result = self._app.acquire_token_silent(self._scopes, account=accounts[0])
      if result and "access_token" in result:
        self._persist_cache()
        return result["access_token"]

    flow = self._app.initiate_device_flow(scopes=self._scopes)
    if "user_code" not in flow:
      raise RuntimeError("Failed to initiate device flow for Microsoft Graph authentication.")

    print(flow.get("message"))
    result = self._app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
      error_detail = result.get("error_description") or result
      raise RuntimeError(f"Failed to acquire delegated Microsoft Graph token: {error_detail}")

    self._persist_cache()
    return result["access_token"]


class SharePointSearchClient:
  """Thin wrapper around the Microsoft Graph search endpoint for SharePoint."""

  def __init__(self, authenticator: DelegatedGraphAuthenticator) -> None:
    self._authenticator = authenticator

  def search(
      self,
      site_hostname: str,
      query_text: str,
      *,
      site_path: str = "",
      top: int = 5,
      fields: Optional[List[str]] = None,
  ) -> Dict[str, Any]:
    if not site_hostname:
      raise ValueError("site_hostname is required.")
    if not query_text:
      raise ValueError("query_text is required.")

    access_token = self._authenticator.acquire_token()
    endpoint = "https://graph.microsoft.com/v1.0/search/query"
    entity_types = ["driveItem", "listItem", "list", "site"]

    if site_path:
      query_string = f"site:\"{site_hostname}:{site_path.lstrip('/')}\" {query_text}".strip()
    else:
      query_string = f"site:\"{site_hostname}\" {query_text}".strip()

    request_body: Dict[str, Any] = {
        "requests": [
            {
                "entityTypes": entity_types,
                "query": {"queryString": query_string},
                "from": 0,
                "size": max(1, min(top, 25)),
                "fields": fields or ["name", "webUrl", "lastModifiedDateTime", "fileExtension"],
            }
        ]
    }

    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=request_body,
        timeout=float(os.getenv("GRAPH_HTTP_TIMEOUT", "30")),
    )
    response.raise_for_status()

    payload = response.json()
    hits_containers = payload.get("value", [{}])[0].get("hitsContainers", [])
    hits = hits_containers[0].get("hits", []) if hits_containers else []

    results: List[SharePointSearchResult] = []
    for hit in hits:
      resource = hit.get("resource", {})
      results.append(
          SharePointSearchResult(
              name=resource.get("name") or resource.get("title"),
              url=resource.get("webUrl"),
              summary=hit.get("summary"),
              last_modified=resource.get("lastModifiedDateTime"),
              resource_type=resource.get("resourceVisualization", {}).get("type"),
          )
      )

    return {
        "query": query_string,
        "count": len(results),
        "results": [result.as_dict() for result in results],
        "raw_response": hits,
    }


_AUTHENTICATOR: Optional[DelegatedGraphAuthenticator] = None


def _get_authenticator() -> DelegatedGraphAuthenticator:
  global _AUTHENTICATOR
  if _AUTHENTICATOR is None:
    client_id = os.getenv("GRAPH_CLIENT_ID")
    tenant_id = os.getenv("GRAPH_TENANT_ID")
    if not client_id or not tenant_id:
      raise RuntimeError(
          "GRAPH_CLIENT_ID and GRAPH_TENANT_ID environment variables must be set before using the SharePoint tool."
      )
    cache_path = pathlib.Path(os.getenv("GRAPH_TOKEN_CACHE", "~/.graph_sharepoint_cache.json")).expanduser()
    scopes = [scope.strip() for scope in os.getenv("GRAPH_SCOPES", "Sites.Read.All Files.Read.All").split() if scope.strip()]
    _AUTHENTICATOR = DelegatedGraphAuthenticator(
        client_id=client_id,
        tenant_id=tenant_id,
        scopes=scopes,
        cache_path=cache_path,
    )
  return _AUTHENTICATOR


def _build_sharepoint_tool() -> FunctionTool:
  def query_sharepoint(
      site_hostname: str,
      query_text: str,
      site_path: str = "",
      top: int = 5,
  ) -> Dict[str, Any]:
    """Run a keyword search against a SharePoint Online site using Microsoft Graph.

    Args:
      site_hostname: The hostname of the SharePoint site (e.g. "contoso.sharepoint.com").
      query_text: The keywords or KQL expression to search for.
      site_path: Optional path segment for the site (e.g. "sites/Finance").
      top: Maximum number of results to return (1-25).

    Returns:
      A dictionary containing the normalized results and the raw Graph hits payload.
    """

    client = SharePointSearchClient(_get_authenticator())
    return client.search(
        site_hostname=site_hostname,
        site_path=site_path,
        query_text=query_text,
        top=top,
    )

  return FunctionTool(query_sharepoint)


sharepoint_tool = _build_sharepoint_tool()

root_agent = Agent(
    model=os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
    name="sharepoint_research_agent",
    description=(
        "Agent that answers enterprise questions by searching SharePoint Online with "
        "the signed-in user's permissions."
    ),
    instruction="""
You are a knowledge assistant that finds answers inside the organization's SharePoint
Online sites. Always invoke the query_sharepoint tool to gather factual evidence before
responding. Combine the retrieved SharePoint documents with your reasoning to craft
helpful, citation-rich answers. If a search returns no results, ask the user to clarify or
narrow the request.
""",
    tools=[sharepoint_tool],
)