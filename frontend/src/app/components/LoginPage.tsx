import { useState } from "react";
import { Eye, EyeOff, Building2, Shield } from "lucide-react";

interface LoginPageProps {
  onLogin: (user: { name: string; role: "staff" | "executive" | "admin"; department: string; avatar: string }) => void;
}

const DEMO_USERS = [
  { email: "admin@jembatanbaru.co.id", password: "admin123", name: "Ahmad Rizki", role: "admin" as const, department: "Accounting Tax", avatar: "AR" },
  { email: "director@jembatanbaru.co.id", password: "exec123", name: "Siti Rahayu", role: "executive" as const, department: "Board", avatar: "SR" },
  { email: "demand@jembatanbaru.co.id", password: "demand123", name: "Budi Santoso", role: "staff" as const, department: "Demand Supply", avatar: "BS" },
  { email: "finance@jembatanbaru.co.id", password: "finance123", name: "Dewi Kusuma", role: "staff" as const, department: "Finance", avatar: "DK" },
];

export function LoginPage({ onLogin }: LoginPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    await new Promise(r => setTimeout(r, 800));
    const user = DEMO_USERS.find(u => u.email === email && u.password === password);
    if (user) {
      onLogin(user);
    } else {
      setError("Email atau password salah. Coba akun demo di bawah.");
    }
    setLoading(false);
  };

  const fillDemo = (u: typeof DEMO_USERS[0]) => {
    setEmail(u.email);
    setPassword(u.password);
    setError("");
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left brand panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: "linear-gradient(135deg, #0a0f1e 0%, #0d1f3c 50%, #0a0f1e 100%)" }}>
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: "radial-gradient(circle at 30% 50%, #059669 0%, transparent 60%), radial-gradient(circle at 80% 20%, #047857 0%, transparent 40%)" }} />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-[#059669] flex items-center justify-center">
              <Building2 size={22} className="text-white" />
            </div>
            <div>
              <div className="text-white font-semibold tracking-wide text-sm">PT. JEMBATAN BARU</div>
              <div className="text-[#10b981] text-xs tracking-widest">EXECUTIVE COPILOT</div>
            </div>
          </div>
        </div>
        <div className="relative z-10">
          <h1 className="text-4xl font-light text-white mb-4 leading-tight">
            Tanyakan apa saja.<br />
            <span className="text-[#10b981]">Dapatkan jawaban</span><br />
            berbasis data.
          </h1>
          <p className="text-muted-foreground text-sm leading-relaxed max-w-sm">
            Platform AI perusahaan yang menghubungkan seluruh departemen. Unggah data, tanya langsung, dapatkan insight yang dikutip dari sumber terpercaya.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-4">
            {[{ label: "Departemen", val: "12" }, { label: "Dokumen", val: "3.4K" }, { label: "Query/hari", val: "840" }].map(s => (
              <div key={s.label} className="border border-border rounded-lg p-3">
                <div className="text-[#10b981] text-xl font-light">{s.val}</div>
                <div className="text-muted-foreground text-xs mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="relative z-10 flex items-center gap-2 text-muted-foreground text-xs">
          <Shield size={12} />
          <span>Data tersimpan aman dan terenkripsi. Akses berbasis peran.</span>
        </div>
      </div>

      {/* Right login panel */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8 justify-center">
            <div className="w-8 h-8 rounded-lg bg-[#059669] flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <span className="text-white font-semibold text-sm">JB Executive Copilot</span>
          </div>

          <h2 className="text-foreground mb-1">Masuk ke Akun Anda</h2>
          <p className="text-muted-foreground text-sm mb-8">Gunakan kredensial perusahaan Anda</p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-secondary-foreground text-sm mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="nama@jembatanbaru.co.id"
                className="w-full bg-input border border-border rounded-lg px-3 py-2.5 text-foreground placeholder-[#8b949e] focus:outline-none focus:border-[#059669] transition-colors text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-secondary-foreground text-sm mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-input border border-border rounded-lg px-3 py-2.5 pr-10 text-foreground placeholder-[#8b949e] focus:outline-none focus:border-[#059669] transition-colors text-sm"
                  required
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-secondary-foreground">
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-[#f85149] text-sm bg-[rgba(248,81,73,0.1)] border border-[rgba(248,81,73,0.2)] rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full bg-[#059669] hover:bg-[#047857] text-white rounded-lg py-2.5 transition-colors disabled:opacity-60 flex items-center justify-center gap-2 text-sm">
              {loading ? <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Memproses...</> : "Masuk"}
            </button>
          </form>

          {/* Demo accounts */}
          <div className="mt-8 border-t border-border pt-6">
            <p className="text-muted-foreground text-xs mb-3 text-center">Akun Demo</p>
            <div className="space-y-2">
              {DEMO_USERS.map(u => (
                <button key={u.email} onClick={() => fillDemo(u)}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg bg-card hover:bg-secondary border border-border transition-colors text-left">
                  <div className="w-7 h-7 rounded-full bg-[#059669] flex items-center justify-center text-white text-xs font-medium shrink-0">
                    {u.avatar}
                  </div>
                  <div className="min-w-0">
                    <div className="text-secondary-foreground text-xs font-medium">{u.name}</div>
                    <div className="text-muted-foreground text-xs">{u.department} · {u.role === "admin" ? "Admin" : u.role === "executive" ? "Eksekutif" : "Staff"}</div>
                  </div>
                  <span className="ml-auto text-[#10b981] text-xs shrink-0">Gunakan →</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
