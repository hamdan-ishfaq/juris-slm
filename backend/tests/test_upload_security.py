"""Upload security helpers."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.upload_security import safe_upload_filename


def test_safe_upload_rejects_traversal():
    with pytest.raises(HTTPException) as exc:
        safe_upload_filename("../../etc/passwd")
    assert exc.value.status_code == 400


def test_safe_upload_accepts_txt():
    assert safe_upload_filename("nda_standard.txt") == "nda_standard.txt"


def test_safe_upload_rejects_bad_extension():
    with pytest.raises(HTTPException):
        safe_upload_filename("malware.exe")
