import { describe, it, expect } from 'vitest';
import { parseRolesFromToken } from './parse-roles';

describe('parseRolesFromToken', () => {
  // -- custom:roles preferred over cognito:groups --

  it('should prefer custom:roles over cognito:groups', () => {
    const roles = parseRolesFromToken({
      'cognito:groups': ['us-west-2_Pool_ms-entra-id'],
      'custom:roles': 'admin,editor',
    });
    expect(roles).toEqual(['admin', 'editor']);
  });

  it('should prefer custom:roles JSON array over cognito:groups', () => {
    const roles = parseRolesFromToken({
      'cognito:groups': ['us-west-2_Pool_ms-entra-id'],
      'custom:roles': '["DotNetDevelopers","Staff"]',
    });
    expect(roles).toEqual(['DotNetDevelopers', 'Staff']);
  });

  // -- JSON array parsing --

  it('should parse JSON array string (Entra ID format)', () => {
    const roles = parseRolesFromToken({
      'custom:roles': '["DotNetDevelopers","All-Employees Entra Sync","Staff"]',
    });
    expect(roles).toEqual(['DotNetDevelopers', 'All-Employees Entra Sync', 'Staff']);
  });

  it('should parse single-element JSON array', () => {
    const roles = parseRolesFromToken({ 'custom:roles': '["Admin"]' });
    expect(roles).toEqual(['Admin']);
  });

  it('should return empty array for empty JSON array', () => {
    const roles = parseRolesFromToken({ 'custom:roles': '[]' });
    expect(roles).toEqual([]);
  });

  it('should trim whitespace in JSON array elements', () => {
    const roles = parseRolesFromToken({
      'custom:roles': '["  Admin  ", " Staff "]',
    });
    expect(roles).toEqual(['Admin', 'Staff']);
  });

  it('should filter out empty strings from JSON array', () => {
    const roles = parseRolesFromToken({
      'custom:roles': '["Admin", "", "Staff"]',
    });
    expect(roles).toEqual(['Admin', 'Staff']);
  });

  // -- comma-separated fallback --

  it('should parse comma-separated string', () => {
    const roles = parseRolesFromToken({ 'custom:roles': 'admin,editor' });
    expect(roles).toEqual(['admin', 'editor']);
  });

  it('should trim spaces in comma-separated roles', () => {
    const roles = parseRolesFromToken({
      'custom:roles': ' admin , editor , viewer ',
    });
    expect(roles).toEqual(['admin', 'editor', 'viewer']);
  });

  it('should handle single comma-separated role', () => {
    const roles = parseRolesFromToken({ 'custom:roles': 'admin' });
    expect(roles).toEqual(['admin']);
  });

  // -- cognito:groups fallback --

  it('should fall back to cognito:groups when custom:roles is absent', () => {
    const roles = parseRolesFromToken({
      'cognito:groups': ['admin', 'editor'],
    });
    expect(roles).toEqual(['admin', 'editor']);
  });

  it('should fall back to cognito:groups when custom:roles is empty string', () => {
    const roles = parseRolesFromToken({
      'custom:roles': '',
      'cognito:groups': ['admin'],
    });
    expect(roles).toEqual(['admin']);
  });

  it('should fall back to cognito:groups when custom:roles is whitespace', () => {
    const roles = parseRolesFromToken({
      'custom:roles': '   ',
      'cognito:groups': ['admin'],
    });
    expect(roles).toEqual(['admin']);
  });

  // -- generic roles claim fallback --

  it('should fall back to roles claim when no Cognito claims present', () => {
    const roles = parseRolesFromToken({ roles: ['Admin'] });
    expect(roles).toEqual(['Admin']);
  });

  // -- no roles at all --

  it('should return empty array when no role claims present', () => {
    const roles = parseRolesFromToken({});
    expect(roles).toEqual([]);
  });

  it('should return empty array when custom:roles is null', () => {
    const roles = parseRolesFromToken({ 'custom:roles': null });
    expect(roles).toEqual([]);
  });
});
