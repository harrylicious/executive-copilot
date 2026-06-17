import { useState } from "react";
import { Eye, EyeOff, Building2, Shield } from "lucide-react";
import { login } from "../../api/auth";
import { ApiError } from "../../api/client";

interface LoginPageProps {
  onLogin: (user: { name: string; role: "staff" | "executive" | "admin"; department: string; avatar: string }) => void;
}

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

    try {
      const user = await login({ email, password });
      onLogin({
        name: user.name,
        role: user.role,
        department: user.department,
        avatar: user.avatar || user.name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase(),
      });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("Email atau password salah.");
        } else {
          setError("Terjadi kesalahan server. Silakan coba lagi.");
        }
      } else {
        setError("Tidak dapat terhubung ke server. Periksa koneksi Anda.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left brand panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden bg-gradient-to-br from-[#0a0f1e] via-[#0d1f3c] to-[#0a0f1e]">
        <div className="absolute inset-0 opacity-15"
          style={{ backgroundImage: "radial-gradient(circle at 25% 45%, #10b981 0%, transparent 55%), radial-gradient(circle at 75% 25%, #059669 0%, transparent 40%)" }} />
        <div className="absolute top-0 right-0 w-64 h-64 bg-[#10b981]/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-[#059669]/5 rounded-full blur-3xl" />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#10b981] to-[#059669] shadow-lg shadow-[#059669]/30 flex items-center justify-center">
              <Building2 size={20} className="text-white" />
            </div>
            <div>
              <div className="text-white font-bold tracking-wide text-sm">PT. JEMBATAN BARU</div>
              <div className="text-[#10b981] text-[10px] tracking-[0.25em] uppercase font-semibold">Executive Copilot</div>
            </div>
          </div>
        </div>
        <div className="relative z-10">
          <h1 className="text-4xl font-light text-white mb-5 leading-tight">
            Tanyakan apa saja.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#10b981] to-[#34d399]">Dapatkan jawaban</span><br />
            berbasis data.
          </h1>
          <p className="text-[#8b949e] text-sm leading-relaxed max-w-sm">
            Knowledge base AI untuk departemen Demand-Supply, Accounting Tax, Finance, dan Logistic. Unggah dokumen, tanya langsung, dapatkan jawaban yang dikutip dari sumber terpercaya.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-4">
            {[{ label: "Departemen", val: "4" }, { label: "Dokumen", val: "22" }, { label: "AI Model", val: "GPT-4o" }].map(s => (
              <div key={s.label} className="border border-white/10 bg-white/5 backdrop-blur-sm rounded-xl p-3.5 hover:bg-white/[0.07] transition-colors">
                <div className="text-[#10b981] text-xl font-light tabular-nums">{s.val}</div>
                <div className="text-muted-foreground text-xs mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="relative z-10 flex items-center gap-2 text-muted-foreground/60 text-xs">
          <Shield size={12} />
          <span>Data tersimpan aman dan terenkripsi. Akses berbasis peran.</span>
        </div>
      </div>

      {/* Right login panel */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 bg-gradient-to-br from-background via-background to-card/30">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8 justify-center">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#10b981] to-[#059669] shadow-lg shadow-[#059669]/20 flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <span className="text-foreground font-semibold text-sm">JB Executive Copilot</span>
          </div>

          <div className="mb-8">
            <h2 className="text-foreground text-xl font-semibold tracking-tight mb-1.5">Masuk ke Akun Anda</h2>
            <p className="text-muted-foreground text-sm">Gunakan kredensial perusahaan Anda</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-secondary-foreground text-xs font-medium mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="nama@jembatanbaru.co.id"
                className="w-full bg-input/70 border border-border/60 rounded-xl px-3.5 py-2.5 text-foreground placeholder-muted-foreground/60 focus:outline-none focus:border-[#059669]/50 focus:ring-1 focus:ring-[#059669]/20 transition-all text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-secondary-foreground text-xs font-medium mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-input/70 border border-border/60 rounded-xl px-3.5 py-2.5 pr-10 text-foreground placeholder-muted-foreground/60 focus:outline-none focus:border-[#059669]/50 focus:ring-1 focus:ring-[#059669]/20 transition-all text-sm"
                  required
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-secondary-foreground transition-colors">
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2.5 text-[#f85149] text-sm bg-[rgba(248,81,73,0.06)] border border-[rgba(248,81,73,0.15)] rounded-xl px-3.5 py-2.5">
                <div className="w-5 h-5 rounded-lg bg-[rgba(248,81,73,0.1)] flex items-center justify-center shrink-0">
                  <Shield size={10} />
                </div>
                <span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full bg-gradient-to-r from-[#059669] to-[#047857] hover:from-[#10b981] hover:to-[#059669] text-white rounded-xl py-2.5 transition-all disabled:opacity-60 flex items-center justify-center gap-2 text-sm font-medium shadow-lg shadow-[#059669]/20 hover:shadow-xl hover:shadow-[#059669]/30 active:scale-[0.98]">
              {loading ? <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Memproses...</> : "Masuk"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
