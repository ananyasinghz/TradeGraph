/**
 * Admin / developer area: sources + ingestion + users/invites.
 */
import { useEffect, useState } from 'react';
import { SourcesView } from './SourcesView';
import { InfoTip } from '../components/InfoTip';
import { api, type AdminUser, type UserInvite } from '../services/api';
import { useAuth } from '../auth/AuthProvider';

const ROLES = ['viewer', 'operator', 'reviewer', 'admin'] as const;

const ROLE_SUMMARY: Record<(typeof ROLES)[number], string> = {
  viewer: 'Read-only clearance and library views',
  operator: 'Create/edit cases and documents; cannot publish rates',
  reviewer: 'Approve or reject rate batches (Make rates live)',
  admin: 'Users/invites plus reviewer powers',
};

function normalizeRole(role: string | null | undefined): (typeof ROLES)[number] {
  const r = (role || '').toLowerCase().trim();
  return (ROLES as readonly string[]).includes(r) ? (r as (typeof ROLES)[number]) : 'viewer';
}

export function AdminView() {
  const { whoami } = useAuth();
  const isAdmin = whoami?.role === 'admin';
  const demoSession = whoami != null && whoami.auth_enabled === false;
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [invites, setInvites] = useState<UserInvite[]>([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<(typeof ROLES)[number]>('viewer');
  const [error, setError] = useState<string | null>(null);

  const refreshAdmin = async () => {
    if (!isAdmin) return;
    setUsers(await api.listAdminUsers());
    setInvites(await api.listInvites());
  };

  useEffect(() => {
    void refreshAdmin().catch((err) =>
      setError(err instanceof Error ? err.message : 'Admin load failed'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  const sendInvite = async () => {
    if (!inviteEmail.trim()) return;
    setError(null);
    try {
      await api.createInvite({ email: inviteEmail.trim(), role: inviteRole });
      setInviteEmail('');
      await refreshAdmin();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invite failed');
    }
  };

  return (
    <section className="panel-view">
      <p className="hint">
        Admin tools: load official notices, review proposed rates, make them live. Day-to-day
        clearance work happens under Clearance cases. <InfoTip id="nav_sources" />
      </p>
      {demoSession ? (
        <p className="muted" data-testid="admin-demo-session">
          Demo session (auth off) — anonymous principal has admin powers locally.
        </p>
      ) : null}
      <SourcesView pendingOnlyDefault />
      {isAdmin ? (
        <div className="result-card" style={{ marginTop: 24 }} data-testid="admin-users-section">
          <h3>Users & invites</h3>
          {error && <p className="error-banner">{error}</p>}
          <div className="result-card" data-testid="admin-role-summary" style={{ marginBottom: 12 }}>
            <h4>Permission summary</h4>
            <ul className="list">
              {ROLES.map((r) => (
                <li key={r}>
                  <span className="chip" data-testid={`role-chip-${r}`}>
                    {r}
                  </span>{' '}
                  — {ROLE_SUMMARY[r]}
                </li>
              ))}
            </ul>
          </div>
          <h4>Users</h4>
          {users.length === 0 ? (
            <p className="muted">No users listed (or auth off — seeded demo users may appear).</p>
          ) : (
            <ul className="list">
              {users.map((u) => {
                const role = normalizeRole(u.role);
                return (
                  <li key={u.id} data-testid={`admin-user-row-${u.id}`}>
                    {u.email} · {u.name} ·{' '}
                    <span className="chip" data-testid={`admin-user-role-label-${u.id}`}>
                      {role}
                    </span>{' '}
                    <label className="muted">
                      Change role{' '}
                      <select
                        aria-label={`Role for ${u.email}`}
                        data-testid={`admin-user-role-select-${u.id}`}
                        value={role}
                        onChange={(e) =>
                          void api
                            .patchAdminUser(u.id, e.target.value)
                            .then(() => refreshAdmin())
                            .catch((err) =>
                              setError(err instanceof Error ? err.message : 'Role update failed'),
                            )
                        }
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          <h4>Invites</h4>
          <div className="toolbar">
            <input
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="email@company.com"
              data-testid="invite-email"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(normalizeRole(e.target.value))}
              data-testid="invite-role-select"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <button type="button" onClick={() => void sendInvite()}>
              Create invite
            </button>
          </div>
          <ul className="list">
            {invites.map((i) => (
              <li key={i.id}>
                {i.email} · {normalizeRole(i.role)} · {i.status}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
