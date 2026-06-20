# SSO Setup — Phase 9C

JurisGuard V2 supports **OIDC**, **SAML 2.0**, and **SCIM 2.0** for enterprise IdP integration.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OIDC_ENABLED` | Enable OpenID Connect login |
| `OIDC_ISSUER_URL` | IdP issuer (Keycloak: `https://host/realms/juris`) |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | OAuth client credentials |
| `OIDC_REDIRECT_URI` | Frontend callback, e.g. `http://localhost:5173/auth/callback` |
| `SAML_ENABLED` | Enable SAML SP |
| `SAML_ENTITY_ID` | SP entity ID |
| `SAML_ACS_URL` | Assertion consumer URL (`/api/v1/auth/saml/acs`) |
| `SAML_IDP_SSO_URL` | IdP SSO URL |
| `SAML_IDP_X509_CERT` | IdP signing certificate (PEM or raw base64) |
| `SAML_SKIP_SIGNATURE_VERIFY` | **Dev/test only** — skip signature validation |
| `SCIM_ENABLED` | Enable SCIM provisioning API |

## Org settings (via `PATCH /api/v1/admin/org`)

```json
{
  "settings": {
    "password_login_disabled": true,
    "idp_group_role_map": {
      "Legal-Admins": "org_admin",
      "Legal-Users": "member"
    }
  }
}
```

Default group names: `jurisguard-admins`, `jurisguard-leads`, `jurisguard-users`.

## Keycloak (OIDC) quick start

1. Create realm `juris`, client `jurisguard` (confidential), redirect URI = `OIDC_REDIRECT_URI`.
2. Set `OIDC_ENABLED=true` and issuer URL.
3. Frontend: user clicks **Sign in with OIDC SSO** → callback at `/auth/callback` exchanges code via `POST /api/v1/auth/oidc/token`.

## SAML

1. Upload SP metadata from `GET /api/v1/auth/saml/metadata` to your IdP.
2. Configure IdP SSO URL and certificate in env.
3. Map IdP `email` attribute and optional `groups` attribute.

## SCIM

1. Set `SCIM_ENABLED=true`.
2. As org owner: **Admin → Generate SCIM token** (or `POST /api/v1/admin/scim-token`).
3. Provision users: `POST /scim/v2/Users` with `Authorization: Bearer <token>`.
4. Deprovision: `DELETE /scim/v2/Users/{id}` soft-disables account (401 on existing JWT).

## Session / logout

- OIDC RP logout: `GET /api/v1/auth/oidc/logout`
- SAML logout redirect: `GET /api/v1/auth/saml/logout`
- JWT TTL: `AUTH_TOKEN_EXPIRE_MINUTES` (default 60) — re-auth required after expiry.
