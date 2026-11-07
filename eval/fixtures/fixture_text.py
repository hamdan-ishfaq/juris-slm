"""Minimal synthetic contract fixtures for Phase 3 contract eval (no client data)."""

NDA_STANDARD = """MUTUAL NON-DISCLOSURE AGREEMENT

Article 1 Definitions
The Disclosing Party means TechCorp Inc. The Receiving Party means LegalAI Solutions GmbH.
Confidential Information means all non-public business, technical, or legal information disclosed under this Agreement.

Article 2 Confidentiality Term
Confidentiality obligations survive for three (3) years from the Effective Date.

Article 3 Receiving Party Obligations
The Receiving Party shall not disclose Confidential Information to third parties except as required by law with prior notice.

Article 4 Permitted Disclosures
Disclosure is permitted when required by law, regulation, or court order.

Article 5 Return of Materials
Upon termination, the Receiving Party shall return or destroy all Confidential Information within thirty (30) days.
"""

MSA_SAAS = """MASTER SERVICES AGREEMENT — SaaS

Section 4.1 SLA Uptime
Provider shall maintain 99.9% monthly uptime for the hosted service.

Section 5.2 Liability Cap
Total aggregate liability shall not exceed the fees paid in the twelve (12) months preceding the claim.

Section 6 Data Processing
Customer personal data shall be processed per the Data Processing Addendum (DPA) attached as Schedule B.
Provider acts as processor under GDPR for Customer account data.

Section 7 Indemnification
Provider shall indemnify Customer against third-party IP infringement claims arising from the Service.

Section 8 Termination
Either party may terminate for convenience upon ninety (90) days written notice.
"""

DPA_TEMPLATE = """DATA PROCESSING ADDENDUM

1. Sub-processors
Authorized sub-processors are listed in Annex III and may be updated with thirty (30) days notice.

2. Breach Notification
Processor shall notify Controller without undue delay and within seventy-two (72) hours of becoming aware of a personal data breach.

3. Audit Rights
Controller may audit Processor compliance annually upon reasonable notice.

4. International Transfers
Transfers outside the EEA rely on Standard Contractual Clauses (SCCs) Module Two.
"""

EMPLOYMENT = """EMPLOYMENT AGREEMENT

Clause 8 Non-compete
Employee agrees not to compete in the same market for twelve (12) months post-termination within Germany.

Clause 9 Garden Leave
Employer may place Employee on garden leave during the notice period with full salary continuation.
"""

LICENSE = """SOFTWARE LICENSE AGREEMENT

Section 2 Grant
Licensor grants Licensee a non-exclusive, non-transferable license to use the Software internally.

Section 10 Termination
Either party may terminate for convenience with thirty (30) days notice after the initial term.
"""

SOW = """STATEMENT OF WORK

Deliverables:
1. API integration module delivered by March 31.
2. Security assessment report.

Acceptance Criteria:
Deliverables are accepted when passing UAT checklist signed by Customer project lead.
"""

NDA_MUTUAL = """MUTUAL CONFIDENTIALITY AGREEMENT

Both parties may disclose Confidential Information to each other under mutual confidentiality obligations.
This is a mutual NDA, not a one-way agreement.
"""

FIXTURES = {
    "nda_standard.txt": NDA_STANDARD,
    "msa_saas.txt": MSA_SAAS,
    "dpa_template.txt": DPA_TEMPLATE,
    "employment.txt": EMPLOYMENT,
    "license.txt": LICENSE,
    "sow.txt": SOW,
    "nda_mutual.txt": NDA_MUTUAL,
}
