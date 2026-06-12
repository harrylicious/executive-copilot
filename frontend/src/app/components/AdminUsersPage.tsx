import { useState } from "react";
import {
  Plus, Search, Edit2, Trash2, Shield, UserCheck, Users,
  X, Mail, Building2, Key, Loader2, AlertCircle
} from "lucide-react";
import { useUsers } from "../../hooks/useUsers";
import type { UserResponse } from "../../api/users";

const ROLE_LABELS: Record<string, string> = { staff: "Staff", executive: "Eksekutif", admin: "Admin" };
const ROLE_COLORS: Record<string, string> = { staff: "#10b981", executive: "#f59e0b", admin: "#059669" };
const DEPTS = ["Accounting Tax", "Demand Supply", "Finance", "Logistic", "Board"];

interface FormData { name: string; email: string; role: "staff" | "executive" | "admin"; department: string; password: string; }

function getInitials(name: string): string {
  return name.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase();
}

function formatLastLogin(dateStr?: string): string {
  if (!dateStr) return "Belum pernah";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "Baru saja";
  if (diffMin < 60) return `${diffMin} menit lalu`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} jam lalu`;
  const diffDays = Math.floor(diffHr / 24);
  return `${diffDays} hari lalu`;
}

export function AdminUsersPage() {
  const {
    users, loading, error, fetchUsers,
    handleCreate, handleUpdate, handleDelete: hookDelete,
    operationLoading, operationError
  } = useUsers();

  const [search, setSearch] = useState("");
  const [filterRole, setFilterRole] = useState("all");
  const [filterDept, setFilterDept] = useState("all");
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<UserResponse | null>(null);
  const [form, setForm] = useState<FormData>({ name: "", email: "", role: "staff", department: "Finance", password: "" });

  const filtered = users.filter(u => {
    if (filterRole !== "all" && u.role !== filterRole) return false;
    if (filterDept !== "all" && u.department !== filterDept) return false;
    if (search && !u.name.toLowerCase().includes(search.toLowerCase()) && !u.email.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const openAdd = () => { setEditingUser(null); setForm({ name: "", email: "", role: "staff", department: "Finance", password: "" }); setShowModal(true); };
  const openEdit = (u: UserResponse) => { setEditingUser(u); setForm({ name: u.name, email: u.email, role: u.role as FormData["role"], department: u.department, password: "" }); setShowModal(true); };

  const handleSave = async () => {
    if (editingUser) {
      await handleUpdate(editingUser.id, { name: form.name, email: form.email, role: form.role, department: form.department });
    } else {
      await handleCreate({ name: form.name, email: form.email, role: form.role, department: form.department, password: form.password });
    }
    setShowModal(false);
  };

  const onDelete = async (id: number) => {
    await hookDelete(id);
  };

  const toggleStatus = async (u: UserResponse) => {
    const newStatus = u.status === "active" ? "inactive" : "active";
    await handleUpdate(u.id, { status: newStatus });
  };

  if (loading) {
    return (
      <div className="p-6 flex flex-col items-center justify-center min-h-[400px] gap-3">
        <Loader2 size={24} className="animate-spin text-[#059669]" />
        <p className="text-muted-foreground text-sm">Memuat data pengguna...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 flex flex-col items-center justify-center min-h-[400px] gap-3">
        <AlertCircle size={24} className="text-[#f85149]" />
        <p className="text-[#f85149] text-sm">Gagal memuat data pengguna</p>
        <p className="text-muted-foreground text-xs">{error}</p>
        <button onClick={() => fetchUsers()} className="mt-2 bg-[#059669] hover:bg-[#047857] text-white rounded-lg px-4 py-2 text-sm transition-colors">
          Coba Lagi
        </button>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-foreground mb-1">Manajemen User</h1>
          <p className="text-muted-foreground text-sm">Kelola akun pengguna dan hak akses.</p>
        </div>
        <button onClick={openAdd} className="flex items-center gap-2 bg-[#059669] hover:bg-[#047857] text-white rounded-lg px-4 py-2 text-sm transition-colors">
          <Plus size={15} /> Tambah User
        </button>
      </div>

      {/* Operation error banner */}
      {operationError && (
        <div className="mb-4 bg-[rgba(248,81,73,0.1)] border border-[#f85149] rounded-lg p-3 flex items-center gap-2">
          <AlertCircle size={14} className="text-[#f85149] shrink-0" />
          <p className="text-[#f85149] text-xs">{operationError}</p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Total User", val: users.length, icon: Users, color: "#10b981" },
          { label: "Aktif", val: users.filter(u => u.status === "active").length, icon: UserCheck, color: "#10b981" },
          { label: "Admin/Exec", val: users.filter(u => u.role !== "staff").length, icon: Shield, color: "#f59e0b" },
        ].map(s => (
          <div key={s.label} className="bg-card border border-border rounded-xl p-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${s.color}18` }}>
              <s.icon size={16} style={{ color: s.color }} />
            </div>
            <div>
              <div className="text-foreground text-xl font-light">{s.val}</div>
              <div className="text-muted-foreground text-xs">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari nama atau email..."
            className="w-full bg-input border border-border text-secondary-foreground text-sm rounded-lg pl-9 pr-3 py-2 focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
        </div>
        <select value={filterRole} onChange={e => setFilterRole(e.target.value)}
          className="bg-input border border-border text-secondary-foreground text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-[#059669]">
          <option value="all">Semua Role</option>
          <option value="staff">Staff</option>
          <option value="executive">Eksekutif</option>
          <option value="admin">Admin</option>
        </select>
        <select value={filterDept} onChange={e => setFilterDept(e.target.value)}
          className="bg-input border border-border text-secondary-foreground text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-[#059669]">
          <option value="all">Semua Dept</option>
          {DEPTS.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              {["Pengguna", "Departemen", "Role", "Status", "Login Terakhir", "Aksi"].map(h => (
                <th key={h} className="px-4 py-3 text-left text-muted-foreground text-xs">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(u => (
              <tr key={u.id} className="border-b border-border last:border-0 hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#059669] flex items-center justify-center text-white text-xs font-medium shrink-0">
                      {u.avatar || getInitials(u.name)}
                    </div>
                    <div>
                      <div className="text-secondary-foreground text-xs font-medium">{u.name}</div>
                      <div className="text-muted-foreground text-[11px]">{u.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-xs">{u.department}</td>
                <td className="px-4 py-3">
                  <span className="text-xs px-2 py-0.5 rounded" style={{ color: ROLE_COLORS[u.role] || "#10b981", background: `${ROLE_COLORS[u.role] || "#10b981"}18` }}>
                    {ROLE_LABELS[u.role] || u.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => toggleStatus(u)} disabled={operationLoading}
                    className={`text-xs px-2 py-0.5 rounded transition-colors ${u.status === "active" ? "text-[#10b981] bg-[rgba(16,185,129,0.1)]" : "text-muted-foreground bg-input"}`}>
                    {u.status === "active" ? "Aktif" : "Nonaktif"}
                  </button>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-xs">{formatLastLogin(u.lastLoginAt)}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(u)} className="text-muted-foreground hover:text-secondary-foreground p-1 rounded"><Edit2 size={13} /></button>
                    <button onClick={() => onDelete(u.id)} disabled={operationLoading} className="text-muted-foreground hover:text-[#f85149] p-1 rounded"><Trash2 size={13} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h3 className="text-foreground text-sm">{editingUser ? "Edit User" : "Tambah User Baru"}</h3>
              <button onClick={() => setShowModal(false)} className="text-muted-foreground hover:text-secondary-foreground"><X size={16} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-secondary-foreground text-xs mb-1.5">Nama Lengkap</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="cth: Budi Santoso"
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
              </div>
              <div>
                <label className="block text-secondary-foreground text-xs mb-1.5">Email</label>
                <div className="relative">
                  <Mail size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="nama@jembatanbaru.co.id"
                    className="w-full bg-input border border-border rounded-lg pl-9 pr-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">Role</label>
                  <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value as FormData["role"] }))}
                    className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669]">
                    <option value="staff">Staff</option>
                    <option value="executive">Eksekutif</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">Departemen</label>
                  <select value={form.department} onChange={e => setForm(f => ({ ...f, department: e.target.value }))}
                    className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669]">
                    {DEPTS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              </div>
              {!editingUser && (
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">Password Awal</label>
                  <div className="relative">
                    <Key size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} placeholder="Min. 8 karakter"
                      className="w-full bg-input border border-border rounded-lg pl-9 pr-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-3 px-5 pb-5">
              <button onClick={() => setShowModal(false)} className="flex-1 bg-input text-secondary-foreground rounded-lg py-2 text-sm hover:bg-[#30363d] transition-colors">
                Batal
              </button>
              <button onClick={handleSave} disabled={operationLoading} className="flex-1 bg-[#059669] text-white rounded-lg py-2 text-sm hover:bg-[#047857] transition-colors disabled:opacity-50">
                {operationLoading ? "Menyimpan..." : editingUser ? "Simpan Perubahan" : "Buat User"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
