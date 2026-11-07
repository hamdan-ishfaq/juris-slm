"""Phase 9C — SAML 2.0 Service Provider helpers."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

from config import settings

NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
}


def build_sp_metadata_xml() -> str:
    entity_id = settings.saml_entity_id
    acs = settings.saml_acs_url
    return f"""<?xml version="1.0"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{entity_id}">
  <SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true"
    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</NameIDFormat>
    <AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
      Location="{acs}" index="1"/>
  </SPSSODescriptor>
</EntityDescriptor>"""


def build_authn_request_redirect_url() -> str:
    if not settings.saml_idp_sso_url:
        raise ValueError("SAML IdP SSO URL not configured")
    request_id = f"_{uuid.uuid4()}"
    issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    xml = f"""<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
      ID="{request_id}" Version="2.0" IssueInstant="{issue_instant}"
      Destination="{settings.saml_idp_sso_url}"
      AssertionConsumerServiceURL="{settings.saml_acs_url}"
      ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
      <saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">{settings.saml_entity_id}</saml:Issuer>
    </samlp:AuthnRequest>"""
    encoded = base64.b64encode(xml.encode("utf-8")).decode("ascii")
    sep = "&" if "?" in settings.saml_idp_sso_url else "?"
    return f"{settings.saml_idp_sso_url}{sep}SAMLRequest={encoded}"


def _findtext(root: ET.Element, path: str) -> str | None:
    el = root.find(path, NS)
    return el.text.strip() if el is not None and el.text else None


def parse_saml_response(saml_response_b64: str) -> dict[str, Any]:
    raw = base64.b64decode(saml_response_b64)
    root = ET.fromstring(raw)

    if not settings.saml_skip_signature_verify and settings.saml_idp_x509_cert:
        try:
            from signxml import XMLVerifier

            cert_pem = settings.saml_idp_x509_cert.strip()
            if "BEGIN CERTIFICATE" not in cert_pem:
                cert_pem = f"-----BEGIN CERTIFICATE-----\n{cert_pem}\n-----END CERTIFICATE-----"
            XMLVerifier().verify(raw, x509_cert=cert_pem.encode("utf-8"))
        except Exception as exc:
            raise ValueError(f"SAML signature verification failed: {exc}") from exc

    status = _findtext(root, ".//samlp:StatusCode")
    if status and "Success" not in status:
        raise ValueError(f"SAML status not success: {status}")

    email = (
        _findtext(root, ".//saml:Attribute[@Name='email']/saml:AttributeValue")
        or _findtext(root, ".//saml:NameID")
    )
    if not email:
        raise ValueError("SAML assertion missing email/NameID")

    external_id = _findtext(root, ".//saml:Subject/saml:NameID") or email
    groups: list[str] = []
    for attr in root.findall(".//saml:Attribute", NS):
        name = attr.get("Name") or ""
        if name.lower() in ("groups", "group", "member", "roles"):
            for val in attr.findall("saml:AttributeValue", NS):
                if val.text:
                    groups.append(val.text.strip())

    return {"email": email.lower(), "external_id": external_id, "groups": groups}
