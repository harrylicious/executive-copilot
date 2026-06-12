import { useState, useEffect } from "react";
import {
  Plus, Edit2, Trash2, Users, FileText, TrendingUp,
  Building2, X, Search, ChevronRight
} from "lucide-react";
import type { UserProfile } from "./Sidebar";
import { fetchDepartments, type TreeNode } from "../../api/departments";

interface Department {
  id: string;
  name: string;
  code: string;
  head: string;
  members: number;
  docs: number;
  queries: number;
  color: string;
  description: string;
  status: "active" | "inactive";
}

const PALETTE = ["#10b981", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899", "#84cc16"];

function countFiles(node: TreeNode): number {
  if (node.type === "file") return 1;
  let n = 0;
  if (node.children) for (const c of node.children) n += countFiles(c);
  return n;
}

function genCode(name: string): string {
  return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 4) || name.slice(0, 4).toUpperCase();
}

function treeToDepts(nodes: TreeNode[]): Department[] {
  return nodes
    .filter(n => n.type === "department")
    .map(n => ({
      id: n.id,
      name: n.name,
      code: genCode(n.name),
      head: "",
      members: 0,
      docs: countFiles(n),
      queries: 0,
      color: n.color || "#10b981",
      description: n.description || "",
      status: "active" as const,
    }));
}

interface Props { user: UserProfile; }

export function DepartmentsPage({ user }: Props) {
  const [depts, setDepts] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchDepartments()
      .then(nodes => setDepts(treeToDepts(nodes)))
      .catch(() => setDepts([]))
      .finally(() => setLoading(false));
  }, []);

  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Department | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingDept, setEditingDept] = useState<Department | null>(null);
  const [form, setForm] = useState({ name: "", code: "", head: "", description: "", color: PALETTE[0] });

  const isAdmin = user.role === "admin";
  const filtered = depts.filter(d => search ? d.name.toLowerCase().includes(search.toLowerCase()) : true);

  const openAdd = () => { setEditingDept(null); setForm({ name: "", code: "", head: "", description: "", color: PALETTE[0] }); setShowModal(true); };
  const openEdit = (d: Department) => { setEditingDept(d); setForm({ name: d.name, code: d.code, head: d.head, description: d.description, color: d.color }); setShowModal(true); };

  const handleSave = () => {
    if (editingDept) {
      setDepts(prev => prev.map(d => d.id === editingDept.id ? { ...d, ...form } : d));
      if (selected?.id === editingDept.id) setSelected(prev => prev ? { ...prev, ...form } : null);
    } else {
      setDepts(prev => [...prev, { id: Date.now().toString(), ...form, members: 0, docs: 0, queries: 0, status: "active" }]);
    }
    setShowModal(false);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-foreground mb-1">Departemen</h1>
          <p className="text-muted-foreground text-sm">Kelola struktur departemen dan visibilitas data.</p>
        </div>
        {isAdmin && (
          <button onClick={openAdd} className="flex items-center gap-2 bg-[#059669] hover:bg-[#047857] text-white rounded-lg px-4 py-2 text-sm transition-colors">
            <Plus size={15} /> Tambah Departemen
          </button>
        )}
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Total Dept", val: depts.length, color: "#10b981" },
          { label: "Total Anggota", val: depts.reduce((s, d) => s + d.members, 0), color: "#10b981" },
          { label: "Total Dokumen", val: depts.reduce((s, d) => s + d.docs, 0), color: "#f59e0b" },
        ].map(s => (
          <div key={s.label} className="bg-card border border-border rounded-xl p-4">
            <div className="text-xl font-light" style={{ color: s.color }}>{s.val}</div>
            <div className="text-muted-foreground text-xs">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-4">
        {/* Left: list */}
        <div className="flex-1 min-w-0">
          <div className="relative mb-3">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari departemen..."
              className="w-full bg-input border border-border text-secondary-foreground text-sm rounded-lg pl-9 pr-3 py-2 focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
          </div>
          <div className="space-y-2">
            {filtered.map(d => (
              <div key={d.id} onClick={() => setSelected(d)}
                className={`flex items-center gap-4 p-4 rounded-xl border cursor-pointer transition-all ${
                  selected?.id === d.id
                    ? "border-[rgba(5,150,105,0.4)] bg-secondary"
                    : "border-border bg-card hover:border-border"
                }`}>
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-semibold text-xs shrink-0"
                  style={{ background: d.color }}>
                  {d.code}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-secondary-foreground text-sm font-medium">{d.name}</span>
                    {d.status === "inactive" && <span className="text-muted-foreground text-[10px] bg-input px-1.5 py-0.5 rounded">Nonaktif</span>}
                  </div>
                  <div className="text-muted-foreground text-xs">{d.head} · {d.members} anggota</div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-center">
                    <div className="text-secondary-foreground text-sm">{d.docs}</div>
                    <div className="text-muted-foreground text-[10px]">Dok</div>
                  </div>
                  <div className="text-center">
                    <div className="text-secondary-foreground text-sm">{d.queries}</div>
                    <div className="text-muted-foreground text-[10px]">Query</div>
                  </div>
                  {isAdmin && (
                    <div className="flex gap-1">
                      <button onClick={e => { e.stopPropagation(); openEdit(d); }} className="text-muted-foreground hover:text-secondary-foreground p-1 rounded"><Edit2 size={13} /></button>
                      <button onClick={e => { e.stopPropagation(); setDepts(prev => prev.filter(x => x.id !== d.id)); if (selected?.id === d.id) setSelected(null); }}
                        className="text-muted-foreground hover:text-[#f85149] p-1 rounded"><Trash2 size={13} /></button>
                    </div>
                  )}
                  <ChevronRight size={14} className="text-muted-foreground" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: detail */}
        {selected && (
          <div className="w-72 shrink-0 bg-card border border-border rounded-xl p-5 h-fit">
            <div className="flex items-start justify-between mb-4">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-semibold text-sm"
                style={{ background: selected.color }}>
                {selected.code}
              </div>
              <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-secondary-foreground"><X size={14} /></button>
            </div>
            <h3 className="text-foreground text-sm mb-1">{selected.name}</h3>
            <p className="text-muted-foreground text-xs leading-relaxed mb-4">{selected.description}</p>
            <div className="space-y-3">
              {[
                { label: "Kepala Dept", val: selected.head, icon: Building2 },
                { label: "Anggota", val: `${selected.members} orang`, icon: Users },
                { label: "Dokumen", val: `${selected.docs} file`, icon: FileText },
                { label: "Query/minggu", val: `${selected.queries}`, icon: TrendingUp },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-lg bg-secondary flex items-center justify-center shrink-0">
                    <item.icon size={12} className="text-muted-foreground" />
                  </div>
                  <div>
                    <div className="text-muted-foreground text-[11px]">{item.label}</div>
                    <div className="text-secondary-foreground text-xs">{item.val}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-border">
              <div className="text-muted-foreground text-[11px] mb-2">Visibilitas Data</div>
              <div className="text-xs text-secondary-foreground leading-relaxed">
                Staff hanya dapat mengakses data departemen ini. Eksekutif dan Admin dapat melihat dari semua departemen.
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h3 className="text-foreground text-sm">{editingDept ? "Edit Departemen" : "Tambah Departemen"}</h3>
              <button onClick={() => setShowModal(false)} className="text-muted-foreground hover:text-secondary-foreground"><X size={16} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">Nama Departemen</label>
                  <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="cth: Marketing"
                    className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
                </div>
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">Kode</label>
                  <input value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase().slice(0, 4) }))} placeholder="cth: MKT"
                    className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
                </div>
              </div>
              <div>
                <label className="block text-secondary-foreground text-xs mb-1.5">Kepala Departemen</label>
                <input value={form.head} onChange={e => setForm(f => ({ ...f, head: e.target.value }))} placeholder="cth: Budi Santoso"
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
              </div>
              <div>
                <label className="block text-secondary-foreground text-xs mb-1.5">Deskripsi</label>
                <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2} placeholder="Fungsi dan tanggung jawab departemen"
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] resize-none placeholder-[#8b949e]" />
              </div>
              <div>
                <label className="block text-secondary-foreground text-xs mb-1.5">Warna</label>
                <div className="flex gap-2">
                  {PALETTE.map(c => (
                    <button key={c} onClick={() => setForm(f => ({ ...f, color: c }))}
                      className={`w-7 h-7 rounded-full transition-all ${form.color === c ? "ring-2 ring-white ring-offset-2 ring-offset-[#161b22]" : ""}`}
                      style={{ background: c }} />
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-3 px-5 pb-5">
              <button onClick={() => setShowModal(false)} className="flex-1 bg-input text-secondary-foreground rounded-lg py-2 text-sm hover:bg-[#30363d] transition-colors">Batal</button>
              <button onClick={handleSave} className="flex-1 bg-[#059669] text-white rounded-lg py-2 text-sm hover:bg-[#047857] transition-colors">
                {editingDept ? "Simpan" : "Buat Departemen"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
