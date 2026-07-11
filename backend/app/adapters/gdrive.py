"""Google Drive — the system of record for approved documents.

Approved artifacts are pushed as Google Docs so business users read them where they
already live. The Drive file id is stored on the ArtifactVersion, so the link is
version-pinned rather than pointing at a mutable 'latest'.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

from app.core.logging import log


class DriveAdapter:
    def __init__(self, sa_json: str, root_folder_id: str) -> None:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            sa_json, scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.root = root_folder_id

    def upload_markdown(self, *, folder, name, markdown) -> dict[str, Any]:
        from googleapiclient.http import MediaIoBaseUpload

        parent = self._ensure_folder(folder)
        media = MediaIoBaseUpload(
            io.BytesIO(markdown.encode()), mimetype="text/markdown", resumable=False
        )
        f = self.svc.files().create(
            body={
                "name": name,
                "parents": [parent],
                "mimeType": "application/vnd.google-apps.document",  # convert md → Google Doc
            },
            media_body=media,
            fields="id, webViewLink",
        ).execute()
        return {"file_id": f["id"], "url": f["webViewLink"]}

    def _ensure_folder(self, name: str) -> str:
        q = (
            f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
            f"and '{self.root}' in parents and trashed = false"
        )
        found = self.svc.files().list(q=q, fields="files(id)").execute().get("files", [])
        if found:
            return found[0]["id"]
        f = self.svc.files().create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [self.root],
            },
            fields="id",
        ).execute()
        return f["id"]


class MockDriveAdapter:
    files: list[dict[str, Any]] = []

    def upload_markdown(self, *, folder, name, markdown) -> dict[str, Any]:
        fid = uuid.uuid4().hex[:20]
        rec = {"file_id": fid, "folder": folder, "name": name,
               "url": f"https://docs.google.com/document/d/{fid}/edit", "bytes": len(markdown)}
        MockDriveAdapter.files.append(rec)
        log.info("drive.mock.upload", name=name, folder=folder)
        return {"file_id": fid, "url": rec["url"]}
