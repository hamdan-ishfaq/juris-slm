export const LAW_PROMPTS = [
  { label: 'GDPR lawful basis', text: 'What are the lawful bases for processing under GDPR Article 6?' },
  { label: 'Data subject rights', text: 'Summarize data subject rights under GDPR Chapter III.' },
  { label: 'Processor obligations', text: 'What are controller obligations when using a processor under Article 28?' },
  { label: 'BGB services', text: 'What does BGB say about termination of service contracts?' },
  { label: 'BDSG employment', text: 'What are key BDSG rules for employee data processing?' },
  { label: 'EU AI Act risk', text: 'Which AI systems are considered high-risk under the EU AI Act?' },
]

export const MATTER_PROMPTS = [
  { label: 'Confidentiality', text: 'Summarize confidentiality obligations and exceptions.' },
  { label: 'Liability cap', text: 'What liability limitations and caps apply?' },
  { label: 'Termination', text: 'What are the termination rights and notice periods?' },
  { label: 'Data protection', text: 'Review DPA clauses against GDPR requirements.' },
]

export const NAV_ITEMS = [
  { id: 'research', label: 'Research', desc: 'Law corpus Q&A', roles: 'all' },
  { id: 'matters', label: 'Matters', desc: 'Documents & analysis', roles: 'all' },
  { id: 'corpus', label: 'Corpus', desc: 'Indexed regulations', roles: 'admin' },
  { id: 'clauses', label: 'Clause bank', desc: 'Firm standard clauses', roles: 'all' },
  { id: 'graph', label: 'Graph', desc: 'Entity relationships', roles: 'all' },
  { id: 'audit', label: 'Audit', desc: 'Activity log', roles: 'admin' },
  { id: 'admin', label: 'Admin', desc: 'Users & roles', roles: 'admin' },
  { id: 'help', label: 'Help', desc: 'User guide', roles: 'all' },
  { id: 'system', label: 'System', desc: 'Models & health', roles: 'all' },
]

export const CONFIDENTIALITY_LEVELS = [
  { value: 'internal', label: 'Internal', minRole: 'member' },
  { value: 'restricted', label: 'Restricted', minRole: 'matter_lead' },
  { value: 'privileged', label: 'Privileged', minRole: 'org_admin' },
]

export const ROLE_RANK = { member: 0, matter_lead: 1, org_admin: 2, owner: 3 }

export function canSeeNavItem(itemId, role, isAdmin) {
  const item = NAV_ITEMS.find((n) => n.id === itemId)
  if (!item) return false
  if (item.roles === 'admin') return isAdmin
  return true
}

export function canUploadLevel(role, level) {
  const row = CONFIDENTIALITY_LEVELS.find((c) => c.value === level)
  if (!row) return false
  return (ROLE_RANK[role] ?? 0) >= (ROLE_RANK[row.minRole] ?? 0)
}
