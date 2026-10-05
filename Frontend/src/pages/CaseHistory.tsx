import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, DoctorCase } from "@/lib/api";
import AppLayout from "@/components/AppLayout";
import { Input } from "@/components/ui/input";
import { Search, FileText, Calendar, Activity } from "lucide-react";

export default function CaseHistory() {
  const { doctor, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [cases, setCases] = useState<DoctorCase[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!doctor) return;
    api.getDoctorCases(doctor.id)
      .then((res) => { if (res.success) setCases(res.cases); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [doctor]);

  const filtered = cases.filter((c) =>
    c.patient_name.toLowerCase().includes(search.toLowerCase()) ||
    c.disease.toLowerCase().includes(search.toLowerCase())
  );

  const getSeverityClass = (s: string) => {
    const l = s.toLowerCase();
    if (l.includes("severe") || l.includes("high")) return "severity-badge-severe";
    if (l.includes("moderate")) return "severity-badge-moderate";
    return "severity-badge-low";
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-foreground">Case History</h1>
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input placeholder="Search cases..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>

        <div className="space-y-3">
          {loading ? (
            <p className="text-muted-foreground text-center py-8">Loading cases...</p>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-muted-foreground">No cases found</p>
            </div>
          ) : filtered.map((c) => (
            <div key={c.case_id} className="medical-card p-4 cursor-pointer hover:border-accent/30 transition-colors" onClick={() => navigate(`/case/${c.case_id}`)}>
              <div className="flex items-center gap-4">
                <div className="p-2.5 rounded-xl bg-medical-highlight">
                  <Activity className="w-5 h-5 text-accent" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-foreground">{c.patient_name}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className="text-sm text-muted-foreground">{c.disease.replace(/_/g, " ")}</span>
                    <span className={getSeverityClass(c.severity)}>{c.severity}</span>
                  </div>
                  {isAdmin && c.doctor_name && (
                    <p className="text-xs text-muted-foreground mt-1">Doctor: {c.doctor_name}</p>
                  )}
                  {c.image_path && (
                    <p className="text-xs text-muted-foreground mt-1 truncate">Image: {c.image_path}</p>
                  )}
                </div>
                <div className="text-right text-sm text-muted-foreground">
                  <div className="flex items-center gap-1"><Calendar className="w-3 h-3" />{c.date}</div>
                  {c.has_prescription && <span className="severity-badge-low mt-1 inline-block">Rx</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
