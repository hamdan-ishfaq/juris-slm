export default function HelpView() {
  return (
    <div className="help-layout animate-fade">
      <header className="view-header">
        <div>
          <h2>User guide</h2>
          <p className="muted">How Research vs Matters work, RBAC, and example questions.</p>
        </div>
      </header>

      <div className="card">
        <h3>Two modes</h3>
        <table className="audit-table">
          <thead><tr><th>Mode</th><th>Where</th><th>Upload?</th><th>Corpus searched</th></tr></thead>
          <tbody>
            <tr><td>Law research</td><td>Research tab</td><td>No — run <code>make ingest-law</code></td><td>GDPR, BGB, BDSG, EU AI Act</td></tr>
            <tr><td>Contract Q&A</td><td>Matters → Analyze</td><td>Yes — wait for <strong>processed</strong></td><td>That document only</td></tr>
            <tr><td>Regulatory compare</td><td>Matters → Compare</td><td>Same</td><td>Document + law baseline</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Example research questions</h3>
        <ul>
          <li>What is lawful processing under GDPR Article 6?</li>
          <li>What are processor obligations under Article 28?</li>
          <li>What is the right to erasure under Article 17?</li>
          <li>What is a purchase contract under BGB Section 433?</li>
          <li>When is consent valid under Article 7?</li>
        </ul>
        <p className="muted">Refusals: query too short (&quot;law&quot;), unknown articles, prompt injection attempts.</p>
      </div>

      <div className="card">
        <h3>RBAC — org roles</h3>
        <table className="audit-table">
          <thead><tr><th>Role</th><th>Read docs</th><th>Upload</th><th>Admin / audit</th></tr></thead>
          <tbody>
            <tr><td>member</td><td>internal</td><td>internal</td><td>No</td></tr>
            <tr><td>matter_lead</td><td>+ restricted</td><td>+ restricted</td><td>No</td></tr>
            <tr><td>org_admin</td><td>+ privileged</td><td>+ privileged</td><td>Yes</td></tr>
            <tr><td>owner</td><td>all</td><td>all</td><td>Yes + user mgmt</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Legal hold vs confidentiality</h3>
        <p>
          <strong>Confidentiality tiers</strong> control who can read or upload documents by role.
          <strong> Legal hold</strong> blocks deletion (matter or document) while an investigation or
          eDiscovery request is active — org admins place and release holds from the Matters workspace.
        </p>
        <p className="muted">Hold actions are recorded in the audit trail as <code>legal_hold_place</code> / <code>legal_hold_release</code>.</p>
      </div>

      <div className="card">
        <h3>Organization boundary</h3>
        <p>
          Each user belongs to one organization. Matters, documents, chat threads, and audit logs
          are scoped to that organization — users in Org A cannot access Org B data (404, not 403).
        </p>
        <p className="muted">
          Org admins can view organization settings under Administration. Cross-org matter invites
          are rejected at the API layer.
        </p>
      </div>

      <div className="card">
        <h3>Matter workflow</h3>
        <ol>
          <li>Create or select a matter</li>
          <li>Upload PDF, DOCX, TXT, or zip — choose confidentiality tier</li>
          <li>Poll until status is <strong>processed</strong></li>
          <li>Run Analyze or Compare</li>
          <li>Export audit pack (PDF / markdown)</li>
        </ol>
      </div>
    </div>
  )
}
