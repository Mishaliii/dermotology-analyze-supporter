import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Activity, Shield, UserPlus, LogIn, Eye, EyeOff } from "lucide-react";

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [form, setForm] = useState({
    name: "", email: "", password: "", specialization: "", license_number: "", district: "", address: "",
  });

  const update = (k: string, v: string) => setForm((p) => ({ ...p, [k]: v }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isLogin) {
        const res = await api.login(form.email, form.password);
        if (!res.success) throw new Error((res as any).error || "Login failed");
        if (res.approved === false) {
          toast({ title: "Pending Approval", description: "Your account is awaiting admin approval.", variant: "destructive" });
          return;
        }
        login({ id: res.doctor_id!, name: res.doctor_name!, email: form.email, isAdmin: res.is_admin ?? false });
        navigate(res.is_admin ? "/admin" : "/dashboard");
      } else {
        if (!form.name || !form.email || !form.password || !form.specialization || !form.license_number || !form.district || !form.address) {
          toast({ title: "Missing Fields", description: "Please fill all fields.", variant: "destructive" });
          return;
        }
        const res = await api.signup(form);
        if (!res.success) {
          const errMsg = (res as any).error || "Signup failed";
          const isPendingDuplicate = /pending approval|no need to request access again/i.test(errMsg);
          toast({
            title: isPendingDuplicate ? "Request Already Submitted" : "Error",
            description: errMsg,
            variant: isPendingDuplicate ? undefined : "destructive",
          });
          if (isPendingDuplicate) setIsLogin(true);
          return;
        }
        toast({ title: "Registration Submitted", description: "Your account request has been sent to the administrator for approval. You'll be notified once approved." });
        setIsLogin(true);
      }
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left: Branding */}
      <div className="hidden lg:flex lg:w-1/2 medical-gradient items-center justify-center p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="absolute rounded-full border border-primary-foreground/20"
              style={{ width: `${200 + i * 120}px`, height: `${200 + i * 120}px`, top: "50%", left: "50%", transform: "translate(-50%, -50%)" }} />
          ))}
        </div>
        <div className="relative z-10 text-center max-w-md">
          <div className="flex items-center justify-center mb-8">
            <div className="p-4 rounded-2xl bg-accent/20 backdrop-blur-sm">
              <Activity className="w-12 h-12 text-primary-foreground" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-primary-foreground mb-4">DermAI CDSS</h1>
          <p className="text-primary-foreground/80 text-lg leading-relaxed">
            AI-powered Clinical Decision Support System for dermatological diagnosis, severity assessment, and treatment planning.
          </p>
          <div className="mt-10 grid grid-cols-3 gap-4 text-primary-foreground/70 text-sm">
            <div className="p-3 rounded-lg bg-primary-foreground/5 backdrop-blur-sm">
              <Shield className="w-5 h-5 mx-auto mb-1 text-primary-foreground/80" />
              Secure
            </div>
            <div className="p-3 rounded-lg bg-primary-foreground/5 backdrop-blur-sm">
              <Activity className="w-5 h-5 mx-auto mb-1 text-primary-foreground/80" />
              AI-Powered
            </div>
            <div className="p-3 rounded-lg bg-primary-foreground/5 backdrop-blur-sm">
              <UserPlus className="w-5 h-5 mx-auto mb-1 text-primary-foreground/80" />
              Clinical
            </div>
          </div>
        </div>
      </div>

      {/* Right: Form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-background">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div className="p-2 rounded-xl medical-gradient">
              <Activity className="w-6 h-6 text-primary-foreground" />
            </div>
            <span className="text-2xl font-bold text-foreground">DermAI CDSS</span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-foreground">{isLogin ? "Welcome Back" : "Create Account"}</h2>
            <p className="text-muted-foreground mt-1">
              {isLogin ? "Sign in to access your dashboard" : "Register to join the clinical platform"}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <AnimatePresence mode="wait">
              {!isLogin && (
                <motion.div key="signup-fields" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="space-y-4 overflow-hidden">
                  <div>
                    <Label htmlFor="name">Full Name</Label>
                    <Input id="name" placeholder="Dr. John Smith" value={form.name} onChange={(e) => update("name", e.target.value)} className="mt-1" />
                  </div>
                  <div>
                    <Label htmlFor="specialization">Specialization</Label>
                    <Input id="specialization" placeholder="Dermatology" value={form.specialization} onChange={(e) => update("specialization", e.target.value)} className="mt-1" />
                  </div>
                  <div>
                    <Label htmlFor="license">License Number</Label>
                    <Input id="license" placeholder="MED-XXXXX" value={form.license_number} onChange={(e) => update("license_number", e.target.value)} className="mt-1" />
                  </div>
                  <div>
                    <Label htmlFor="district">District</Label>
                    <Input id="district" placeholder="Kottayam" value={form.district} onChange={(e) => update("district", e.target.value)} className="mt-1" />
                  </div>
                  <div>
                    <Label htmlFor="address">Address</Label>
                    <Input id="address" placeholder="Clinic or hospital address" value={form.address} onChange={(e) => update("address", e.target.value)} className="mt-1" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div>
              <Label htmlFor="email">Email Address</Label>
              <Input id="email" type="email" placeholder="doctor@hospital.com" value={form.email} onChange={(e) => update("email", e.target.value)} className="mt-1" />
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <div className="relative mt-1">
                <Input id="password" type={showPw ? "text" : "password"} placeholder="••••••••" value={form.password} onChange={(e) => update("password", e.target.value)} className="pr-10" />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <Button type="submit" className="w-full h-11 medical-gradient text-primary-foreground" disabled={loading}>
              {loading ? (
                <span className="flex items-center gap-2"><span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" /> Processing...</span>
              ) : isLogin ? (
                <span className="flex items-center gap-2"><LogIn className="w-4 h-4" /> Sign In</span>
              ) : (
                <span className="flex items-center gap-2"><UserPlus className="w-4 h-4" /> Register</span>
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground mt-6">
            {isLogin ? "Don't have an account?" : "Already registered?"}{" "}
            <button onClick={() => { setIsLogin(!isLogin); setForm({ name: "", email: "", password: "", specialization: "", license_number: "", district: "", address: "" }); }} className="text-accent font-medium hover:underline">
              {isLogin ? "Register here" : "Sign in"}
            </button>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
