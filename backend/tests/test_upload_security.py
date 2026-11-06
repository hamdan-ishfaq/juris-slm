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


def test_common_contract_filename_characters_are_allowed():
    name = "Seller's Agreement, Smith & Co (2024).pdf"
    assert safe_upload_filename(name) == name


def test_characters_unsafe_in_headers_stay_rejected():
    for name in ('bad".pdf', "bad;.pdf", "bad\r\n.pdf", "bad<x>.pdf"):
        with pytest.raises(HTTPException):
            safe_upload_filename(name)
