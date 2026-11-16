import { useCallback, useEffect, useState } from "react";
import { Search, Users } from "lucide-react";
import { errorMessage } from "../../api/client";
import { admin } from "../../api/endpoints";
import { Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { formatDate, formatDateTime } from "../../utils/format";

export default function AdminUsers() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [params, setParams] = useState({ search: "", role: "", page: 1, page_size: 20 });
  const [data, setData] = useState(null);
  const [searchText, setSearchText] = useState("");

  const load = useCallback(() => {
    const query = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== ""));
    admin.users(query).then(setData).catch((e) => toast.error(errorMessage(e)));
  }, [params, toast]);
  useEffect(load, [load]);

  const update = async (u, body, message) => {
    try {
      const updated = await admin.updateUser(u.id, body);
      setData((d) => ({ ...d, items: d.items.map((x) => (x.id === u.id ? updated : x)) }));
      toast.success(message);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div>
      <PageHeader title="User management" subtitle="Search, activate or disable accounts and manage admin roles." />
      <Card>
        <form
          className="search-row"
          onSubmit={(e) => {
            e.preventDefault();
            setParams({ ...params, search: searchText.trim(), page: 1 });
          }}
        >
          <input className="input" placeholder="Name, phone, email or district" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
          <select className="select" value={params.role} onChange={(e) => setParams({ ...params, role: e.target.value, page: 1 })} aria-label="Role">
            <option value="">All roles</option>
            <option value="farmer">Farmers</option>
            <option value="admin">Admins</option>
          </select>
          <button className="btn btn-primary">
            <Search size={18} /> Search
          </button>
        </form>
      </Card>

      <Card className="mt" title={data ? `${data.total} users` : "Users"} icon={Users}>
        {!data ? (
          <Spinner />
        ) : data.items.length === 0 ? (
          <EmptyState title="No users match" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Location</th>
                  <th>Lang</th>
                  <th>Questions</th>
                  <th>Joined</th>
                  <th>Last login</th>
                  <th>Role</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((u) => (
                  <tr key={u.id} className={u.is_active ? "" : "row-disabled"}>
                    <td>
                      {u.full_name}
                      {u.email && <div className="muted small">{u.email}</div>}
                    </td>
                    <td>{u.phone}</td>
                    <td>{[u.district, u.state].filter(Boolean).join(", ") || "—"}</td>
                    <td>{u.language_code.toUpperCase()}</td>
                    <td>{u.query_count}</td>
                    <td>{formatDate(u.created_at)}</td>
                    <td>{formatDateTime(u.last_login_at)}</td>
                    <td>
                      <select
                        className="select select-small"
                        value={u.role}
                        disabled={u.id === me.id}
                        onChange={(e) => update(u, { role: e.target.value }, `Role changed to ${e.target.value}`)}
                        aria-label={`Role of ${u.full_name}`}
                      >
                        <option value="farmer">Farmer</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td>
                      <button
                        className={`btn btn-small ${u.is_active ? "btn-danger-ghost" : "btn-ghost"}`}
                        disabled={u.id === me.id}
                        onClick={() => update(u, { is_active: !u.is_active }, u.is_active ? "Account disabled" : "Account activated")}
                      >
                        {u.is_active ? "Disable" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && pages > 1 && (
          <div className="pager">
            <button className="btn btn-small" disabled={params.page <= 1} onClick={() => setParams({ ...params, page: params.page - 1 })}>
              Previous
            </button>
            <span>
              Page {params.page} of {pages}
            </span>
            <button className="btn btn-small" disabled={params.page >= pages} onClick={() => setParams({ ...params, page: params.page + 1 })}>
              Next
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}
