/**
 * Parse roles from Cognito JWT token claims.
 *
 * Priority:
 * 1. `custom:roles` – IdP roles mapped via Cognito attribute mapping.
 *    May be a JSON array string (e.g. Entra ID: '["Admin","Staff"]')
 *    or a comma-separated string.
 * 2. `cognito:groups` – Cognito User Pool Groups. For federated users
 *    this typically contains the provider group name, not IdP roles.
 * 3. `roles` – Generic OIDC roles claim.
 *
 * @param payload Decoded JWT payload object
 * @returns Array of role strings
 */
export function parseRolesFromToken(payload: Record<string, unknown>): string[] {
  const customRolesRaw = payload['custom:roles'];

  if (typeof customRolesRaw === 'string' && customRolesRaw.trim()) {
    try {
      const parsed = JSON.parse(customRolesRaw);
      if (Array.isArray(parsed)) {
        return parsed.map((r: unknown) => String(r).trim()).filter(Boolean);
      }
      // Parsed but not an array — treat as comma-separated
      return customRolesRaw.split(',').map(r => r.trim()).filter(Boolean);
    } catch {
      // Not valid JSON — fall back to comma-separated
      return customRolesRaw.split(',').map(r => r.trim()).filter(Boolean);
    }
  }

  if (Array.isArray(customRolesRaw)) {
    return customRolesRaw;
  }

  // Fallback: cognito:groups, then generic roles claim
  const groups = payload['cognito:groups'];
  if (Array.isArray(groups)) return groups;

  const roles = payload['roles'];
  if (Array.isArray(roles)) return roles;

  return [];
}
