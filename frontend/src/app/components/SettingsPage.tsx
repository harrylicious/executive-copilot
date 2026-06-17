import { useState, useEffect, useRef } from "react";
import { User, Lock, Bell, Shield, Bot, Save, Eye, EyeOff, Plus, X, Loader2 } from "lucide-react";
import type { UserProfile } from "./Sidebar";
import type { ChatbotSettings } from "../App";
import { useSettings } from "../../hooks/useSettings";
import type { SettingsUpdate } from "../../api/settings";

function DeptKeywordEditor({ dept, keywords, onAdd, onRemove }: {
  dept: string;
  keywords: string[];
  onAdd: (kw: string) => void;
  onRemove: (kw: string) => void;
}) {
  const [input, setInput] = useState("");

  const handleAdd = () => {
    const kw = input.trim().toLowerCase();
    if (kw && !keywords.includes(kw)) { onAdd(kw); setInput(""); }
  };

  return (
    <div className="bg-input rounded-xl p-3 border border-border">
      <div className="text-secondary-foreground text-xs font-medium mb-2">{dept}</div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {keywords.map(kw => (
          <span key={kw} className="inline-flex items-center gap-1 text-xs text-secondary-foreground bg-card px-2 py-0.5 rounded">
            {kw}
            <button onClick={() => onRemove(kw)} className="text-muted-foreground hover:text-[#f85149]"><X size={10} /></button>
          </span>
        ))}
      </div>
      <div className="flex gap-1">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); handleAdd(); } }}
          placeholder="Tambah kata kunci..."
          className="flex-1 bg-card border border-border rounded-lg px-2 py-1 text-xs text-secondary-foreground focus:outline-none placeholder-muted-foreground" />
        <button onClick={handleAdd} disabled={!input.trim()}
          className="bg-primary text-primary-foreground rounded-lg px-2 py-1 disabled:opacity-40"><Plus size={12} /></button>
      </div>
    </div>
  );
}

interface Props { user: UserProfile; chatbotSettings: ChatbotSettings; onChatbotSettingsChange: (s: ChatbotSettings) => void; }

const NUANCE_LABELS: Record<ChatbotSettings["nuance"], string> = {
  formal: "Formal",
  santai: "Santai",
  profesional: "Profesional",
  ramah: "Ramah",
  tegas: "Tegas",
};

const NUANCE_DESC: Record<ChatbotSettings["nuance"], { id: string; en: string }> = {
  formal: { id: "Bahasa baku, struktur kalimat lengkap, sopan", en: "Standard language, complete sentences, polite" },
  santai: { id: "Bahasa sehari-hari, akrab, tidak kaku", en: "Everyday language, friendly, relaxed" },
  profesional: { id: "Fokus pada data, efisien, to-the-point", en: "Data-focused, efficient, to-the-point" },
  ramah: { id: "Hangat, mengundang dialog, suportif", en: "Warm, invites dialogue, supportive" },
  tegas: { id: "Langsung, jelas, tanpa basa-basi", en: "Direct, clear, no pleasantries" },
};

export function SettingsPage({ user, chatbotSettings, onChatbotSettingsChange }: Props) {
  // Default userId (UserProfile doesn't have id, so we use a hardcoded default)
  const userId = 1;
  const { settings, loading, error, saving, saveError, save } = useSettings(userId);

  const [tab, setTab] = useState("profile");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [saved, setSaved] = useState(false);
  const [notif, setNotif] = useState({ email: true, push: false, weekly: true, aiAlerts: true });
  const [profile, setProfile] = useState({ name: user.name, phone: "+62 812-3456-7890", bio: "" });
  const [local, setLocal] = useState<ChatbotSettings>(() => ({
    ...chatbotSettings,
    deptKeywords: Object.fromEntries(
      Object.entries(chatbotSettings.deptKeywords).map(([k, v]) => [k, [...v]])
    ),
  }));

  // Dirty state tracking: snapshot of last-saved form state
  const [savedSnapshot, setSavedSnapshot] = useState<string>("");
  const settingsApplied = useRef(false);
  const getFormSnapshot = () => JSON.stringify({ profile, notif, local });
  const isDirty = savedSnapshot !== "" && savedSnapshot !== getFormSnapshot();

  // Populate local form state when settings are loaded from API
  useEffect(() => {
    if (settings) {
      if (settings.profile) {
        setProfile(p => ({
          name: settings.profile?.name ?? p.name,
          phone: settings.profile?.phone ?? p.phone,
          bio: settings.profile?.bio ?? p.bio,
        }));
      }
      if (settings.notifications) {
        setNotif({
          email: settings.notifications.emailNotifications,
          push: settings.notifications.pushNotifications,
          weekly: settings.notifications.weeklyDigest,
          aiAlerts: true,
        });
      }
      if (settings.chatbot) {
        setLocal(prev => ({
          ...prev,
          language: settings.chatbot?.language ?? prev.language,
          nuance: (settings.chatbot?.nuance as ChatbotSettings["nuance"]) ?? prev.nuance,
          restrictCrossDept: settings.chatbot?.restrictCrossDept ?? prev.restrictCrossDept,
        }));
      }
      settingsApplied.current = true;
    }
  }, [settings]);

  // Capture snapshot after form state is synced from API
  useEffect(() => {
    if (settingsApplied.current) {
      setSavedSnapshot(getFormSnapshot());
      settingsApplied.current = false;
    }
  });

  const handleSave = async () => {
    const data: SettingsUpdate = {
      profile: {
        name: profile.name,
        phone: profile.phone,
        bio: profile.bio,
      },
      notifications: {
        emailNotifications: notif.email,
        pushNotifications: notif.push,
        weeklyDigest: notif.weekly,
      },
      chatbot: {
        language: local.language,
        nuance: local.nuance,
        restrictCrossDept: local.restrictCrossDept,
      },
    };

    try {
      await save(data);
      onChatbotSettingsChange(local);
      setSavedSnapshot(getFormSnapshot());
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // saveError from the hook will display the error
    }
  };

  const isAdmin = user.role === "admin";

  const TABS = [
    { id: "profile", label: "Profil", icon: User },
    { id: "security", label: "Keamanan", icon: Lock },
    { id: "notifications", label: "Notifikasi", icon: Bell },
    { id: "chatbot", label: "Chatbot", icon: Bot },
    { id: "privacy", label: "Privasi & Akses", icon: Shield },
  ];

  return (
    <div className="p-6 max-w-3xl">
      <div className="mb-6">
        <h1 className="text-foreground mb-1">Pengaturan</h1>
        <p className="text-muted-foreground text-sm">Kelola preferensi akun Anda.</p>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="flex gap-6 animate-pulse">
          <div className="w-44 shrink-0 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-10 bg-card rounded-lg" />
            ))}
          </div>
          <div className="flex-1 bg-card border border-border rounded-xl p-5 space-y-4">
            <div className="h-4 bg-input rounded w-1/3" />
            <div className="h-10 bg-input rounded" />
            <div className="h-10 bg-input rounded" />
            <div className="h-10 bg-input rounded w-2/3" />
          </div>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="p-4 bg-[rgba(248,81,73,0.1)] border border-[rgba(248,81,73,0.3)] rounded-xl text-[#f85149] text-sm">
          Gagal memuat pengaturan: {error}
        </div>
      )}

      {!loading && (
      <div className="flex gap-6">
        {/* Sidebar tabs */}
        <div className="w-44 shrink-0">
          <nav className="space-y-0.5">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-left transition-all ${
                  tab === t.id ? "bg-secondary text-[#10b981] border border-border" : "text-muted-foreground hover:text-secondary-foreground hover:bg-card"
                }`}>
                <t.icon size={14} />
                {t.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 bg-card border border-border rounded-xl p-5">
          {tab === "profile" && (
            <div className="space-y-5">
              <h3 className="text-foreground text-sm border-b border-border pb-3">Informasi Profil</h3>
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-full bg-[#059669] flex items-center justify-center text-white text-xl font-medium">
                  {user.avatar}
                </div>
                <div>
                  <button className="text-[#10b981] text-sm hover:underline">Ubah foto profil</button>
                  <div className="text-muted-foreground text-xs mt-0.5">JPG, PNG maks. 2MB</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">Nama Lengkap</label>
                  <input value={profile.name} onChange={e => setProfile(p => ({ ...p, name: e.target.value }))}
                    className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669]" />
                </div>
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">Email</label>
                  <input value={`${user.name.toLowerCase().replace(" ", ".")}@jembatanbaru.co.id`} disabled
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-muted-foreground text-sm cursor-not-allowed" />
                </div>
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">Departemen</label>
                  <input value={user.department} disabled
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-muted-foreground text-sm cursor-not-allowed" />
                </div>
                <div>
                  <label className="block text-secondary-foreground text-xs mb-1.5">No. Telepon</label>
                  <input value={profile.phone} onChange={e => setProfile(p => ({ ...p, phone: e.target.value }))}
                    className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669]" />
                </div>
              </div>
              <div>
                <label className="block text-secondary-foreground text-xs mb-1.5">Bio Singkat</label>
                <textarea value={profile.bio} onChange={e => setProfile(p => ({ ...p, bio: e.target.value }))} rows={3} placeholder="Perkenalkan diri Anda..."
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] resize-none placeholder-[#8b949e]" />
              </div>
            </div>
          )}

          {tab === "security" && (
            <div className="space-y-5">
              <h3 className="text-foreground text-sm border-b border-border pb-3">Keamanan Akun</h3>
              <div className="space-y-4">
                {[
                  { label: "Password Saat Ini", show: showCurrentPw, toggle: () => setShowCurrentPw(!showCurrentPw) },
                  { label: "Password Baru", show: showNewPw, toggle: () => setShowNewPw(!showNewPw) },
                ].map(f => (
                  <div key={f.label}>
                    <label className="block text-secondary-foreground text-xs mb-1.5">{f.label}</label>
                    <div className="relative">
                      <input type={f.show ? "text" : "password"} placeholder="••••••••"
                        className="w-full bg-input border border-border rounded-lg px-3 py-2 pr-10 text-secondary-foreground text-sm focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
                      <button onClick={f.toggle} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-secondary-foreground">
                        {f.show ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="p-4 bg-secondary rounded-xl border border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-secondary-foreground text-sm">Autentikasi Dua Faktor</div>
                    <div className="text-muted-foreground text-xs">Tambah lapisan keamanan ekstra</div>
                  </div>
                  <span className="text-xs text-muted-foreground bg-input px-2 py-1 rounded">Belum aktif</span>
                </div>
              </div>
            </div>
          )}

          {tab === "notifications" && (
            <div className="space-y-5">
              <h3 className="text-foreground text-sm border-b border-border pb-3">Preferensi Notifikasi</h3>
              <div className="space-y-3">
                {[
                  { key: "email" as const, label: "Notifikasi Email", desc: "Terima notifikasi penting via email" },
                  { key: "push" as const, label: "Push Notification", desc: "Notifikasi browser real-time" },
                  { key: "weekly" as const, label: "Laporan Mingguan", desc: "Ringkasan aktivitas setiap Senin pagi" },
                  { key: "aiAlerts" as const, label: "Alert AI", desc: "Notifikasi saat AI menemukan insight penting" },
                ].map(item => (
                  <div key={item.key} className="flex items-center justify-between p-3 bg-secondary rounded-xl">
                    <div>
                      <div className="text-secondary-foreground text-sm">{item.label}</div>
                      <div className="text-muted-foreground text-xs">{item.desc}</div>
                    </div>
                    <button onClick={() => setNotif(n => ({ ...n, [item.key]: !n[item.key] }))}
                      className={`w-10 h-5 rounded-full relative transition-colors ${notif[item.key] ? "bg-[#059669]" : "bg-[#30363d]"}`}>
                      <div className={`w-4 h-4 bg-white rounded-full absolute top-0.5 transition-all ${notif[item.key] ? "left-5" : "left-0.5"}`} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === "chatbot" && (
            <div className="space-y-5">
              <h3 className="text-foreground text-sm border-b border-border pb-3">Preferensi AI Copilot</h3>

              <div>
                <label className="block text-secondary-foreground text-xs mb-2">Bahasa</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: "id" as const, label: "Indonesia", flag: "🇮🇩" },
                    { value: "en" as const, label: "English", flag: "🇬🇧" },
                  ].map(opt => (
                    <button key={opt.value} onClick={() => setLocal(s => ({ ...s, language: opt.value }))}
                      className={`flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${
                        local.language === opt.value
                          ? "border-[rgba(5,150,105,0.4)] bg-secondary"
                          : "border-border bg-input hover:border-border"
                      }`}>
                      <span className="text-lg">{opt.flag}</span>
                      <span className="text-secondary-foreground text-sm">{opt.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-secondary-foreground text-xs mb-2">Nuansa AI</label>
                <div className="grid grid-cols-1 gap-2">
                  {(Object.keys(NUANCE_LABELS) as ChatbotSettings["nuance"][]).map(n => (
                    <button key={n} onClick={() => setLocal(s => ({ ...s, nuance: n }))}
                      className={`flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${
                        local.nuance === n
                          ? "border-[rgba(5,150,105,0.4)] bg-secondary"
                          : "border-border bg-input hover:border-border"
                      }`}>
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-medium ${
                        local.nuance === n ? "bg-[#059669] text-white" : "bg-card text-muted-foreground"
                      }`}>
                        {n === "formal" ? "F" : n === "santai" ? "S" : n === "profesional" ? "P" : n === "ramah" ? "R" : "T"}
                      </div>
                      <div>
                        <div className="text-secondary-foreground text-sm">{NUANCE_LABELS[n]}</div>
                        <div className="text-muted-foreground text-xs">{NUANCE_DESC[n][local.language]}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-4 bg-secondary rounded-xl border border-border">
                <div className="flex items-center gap-2 mb-1">
                  <Bot size={14} className="text-[#10b981]" />
                  <span className="text-secondary-foreground text-sm">Pratinjau</span>
                </div>
                <p className="text-muted-foreground text-xs leading-relaxed italic">
                  {local.language === "id"
                    ? `"Halo! ${local.nuance === "formal" ? "Berikut adalah laporan yang Anda minta." : local.nuance === "santai" ? "Ini dia data yang lo minta." : local.nuance === "profesional" ? "Laporan siap, berikut ringkasannya." : local.nuance === "ramah" ? "Tentu, dengan senang hati! Ini dia informasinya." : "Simak data berikut ini dengan saksama."}"`
                    : `"Hello! ${local.nuance === "formal" ? "Here is the report you requested." : local.nuance === "santai" ? "Here's the data you asked for." : local.nuance === "profesional" ? "Report ready — here is the summary." : local.nuance === "ramah" ? "Sure, happy to help! Here you go." : "Review the following data carefully."}"`}
                </p>
              </div>

              {/* Admin-only: cross-department restriction */}
              {isAdmin && (
                <div className="pt-4 border-t border-border space-y-4">
                  <div className="flex items-center justify-between p-4 bg-secondary rounded-xl border border-border">
                    <div className="flex items-start gap-3">
                      <Shield size={16} className="text-[#f59e0b] mt-0.5 shrink-0" />
                      <div>
                        <div className="text-secondary-foreground text-sm">Restriksi Akses Lintas Departemen</div>
                        <div className="text-muted-foreground text-xs mt-0.5">
                          Saat diaktifkan, Staff hanya bisa mengakses data departemen sendiri. Pertanyaan yang mengandung kata kunci dari departemen lain akan diblokir.
                        </div>
                      </div>
                    </div>
                    <button onClick={() => setLocal(s => ({ ...s, restrictCrossDept: !s.restrictCrossDept }))}
                      className={`w-11 h-6 rounded-full relative transition-colors shrink-0 ${local.restrictCrossDept ? "bg-primary" : "bg-switch-background"}`}>
                      <div className={`w-5 h-5 bg-white rounded-full absolute top-0.5 transition-all ${local.restrictCrossDept ? "left-5" : "left-0.5"}`} />
                    </button>
                  </div>

                  {local.restrictCrossDept && (
                    <div className="space-y-3">
                      <p className="text-muted-foreground text-xs">Kelola kata kunci per departemen (tambah/hapus):</p>
                      {Object.entries(local.deptKeywords).map(([dept, kws]) => (
                        <DeptKeywordEditor
                          key={dept}
                          dept={dept}
                          keywords={kws}
                          onAdd={(kw) => setLocal(s => ({
                            ...s,
                            deptKeywords: { ...s.deptKeywords, [dept]: [...(s.deptKeywords[dept] || []), kw] }
                          }))}
                          onRemove={(kw) => setLocal(s => ({
                            ...s,
                            deptKeywords: { ...s.deptKeywords, [dept]: (s.deptKeywords[dept] || []).filter(k => k !== kw) }
                          }))}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === "privacy" && (
            <div className="space-y-5">
              <h3 className="text-foreground text-sm border-b border-border pb-3">Privasi & Hak Akses</h3>
              <div className="p-4 bg-secondary rounded-xl border border-border">
                <div className="text-secondary-foreground text-xs mb-3">Akses Data Anda</div>
                <div className="space-y-2">
                  {[
                    { label: `Departemen ${user.department}`, access: true },
                    { label: "Departemen Lain", access: user.role === "executive" || user.role === "admin" },
                    { label: "Data Seluruh Perusahaan", access: user.role === "executive" || user.role === "admin" },
                    { label: "Panel Admin", access: user.role === "admin" },
                  ].map(r => (
                    <div key={r.label} className="flex items-center justify-between">
                      <span className="text-muted-foreground text-xs">{r.label}</span>
                      <span className={`text-xs px-2 py-0.5 rounded ${r.access ? "text-[#10b981] bg-[rgba(16,185,129,0.1)]" : "text-muted-foreground bg-input"}`}>
                        {r.access ? "Diizinkan" : "Dibatasi"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <p className="text-muted-foreground text-xs leading-relaxed">
                Hak akses ditentukan oleh role Anda dan dikonfigurasi oleh Administrator. Hubungi IT jika Anda memerlukan perubahan akses.
              </p>
            </div>
          )}

          <div className="mt-5 pt-4 border-t border-border flex flex-col items-end gap-2">
            {saveError && (
              <div className="text-[#f85149] text-xs">Gagal menyimpan: {saveError}</div>
            )}
            <button onClick={handleSave} disabled={saving || !isDirty}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm transition-all ${saved ? "bg-[#10b981] text-white" : saving || !isDirty ? "bg-[#059669]/70 text-white cursor-not-allowed" : "bg-[#059669] text-white hover:bg-[#047857]"}`}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              {saving ? "Menyimpan..." : saved ? "Tersimpan!" : "Simpan Perubahan"}
            </button>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
