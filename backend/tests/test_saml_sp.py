"""Phase 9C — SAML assertion parsing tests."""
from __future__ import annotations

import base64

import pytest

from services.saml_sp import build_sp_metadata_xml, parse_saml_response


SAMPLE_ASSERTION = """<?xml version="1.0"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
  xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
  <saml:Assertion>
    <saml:Subject><saml:NameID>sso-user@example.com</saml:NameID></saml:Subject>
    <saml:AttributeStatement>
      <saml:Attribute Name="email"><saml:AttributeValue>sso-user@example.com</saml:AttributeValue></saml:Attribute>
      <saml:Attribute Name="groups"><saml:AttributeValue>jurisguard-admins</saml:AttributeValue></saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>"""


def test_build_metadata_contains_entity_id(monkeypatch):
    monkeypatch.setenv("SAML_ENTITY_ID", "test-sp")
    from config import settings

    settings.saml_entity_id = "test-sp"
    xml = build_sp_metadata_xml()
    assert "test-sp" in xml


def test_parse_saml_response_skip_verify(monkeypatch):
    monkeypatch.setenv("SAML_SKIP_SIGNATURE_VERIFY", "true")
    from config import settings

    settings.saml_skip_signature_verify = True
    encoded = base64.b64encode(SAMPLE_ASSERTION.encode()).decode()
    profile = parse_saml_response(encoded)
    assert profile["email"] == "sso-user@example.com"
    assert "jurisguard-admins" in profile["groups"]
