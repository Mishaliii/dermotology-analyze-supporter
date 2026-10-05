import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, CaseHistory } from "@/lib/api";
import AppLayout from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Upload, FileText, Calendar, Activity } from "lucide-react";

function formatCaseDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value || "";
  const year = parsed.getFullYear();
  const month = `${parsed.getMonth() + 1}`.padStart(2, "0");
  const day = `${parsed.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDiagnosis(value: string): string {
  const raw = (value || "").replace(/_/g, " ").trim();
  if (!raw) return "Unknown";

  let cleaned = raw
    .replace(/raw\s*text[:\-]?\s*/gi, "")
    .replace(/\bGAGS\s*Score\s*[:\-]?\s*/gi, "GAGS Score: ")
    .replace(/\(\s*Max\s*44\s*\)/gi, "")
    .replace(/\bMax\s*44\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();

  const gagsMatch = cleaned.match(/GAGS\s*Score\s*[:\-]?\s*\d+/i);
  if (gagsMatch) {
    cleaned = gagsMatch[0].replace(/\s+/g, " ").trim();
  }

  return cleaned;
}

function getCalculatorName(disease: string): string {
  const normalized = (disease || "").toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized.includes("acne")) return "GAGS";
  if (normalized.includes("psoriasis")) return "PASI";
  if (normalized.includes("eczema") || normalized.includes("dermatitis")) return "EASI";
  if (normalized.includes("vitiligo")) return "VASI";
  if (normalized.includes("melanoma") || normalized.includes("nevus") || normalized.includes("mole")) return "ABCDE";
  if (normalized.includes("alopecia")) return "SALT";
  return "Severity";
}

function formatSeverityResult(disease: string, severity: string): string {
  const calculator = getCalculatorName(disease);
  const raw = (severity || "").trim();

  const numericFromObject = raw.match(/["']numeric["']\s*:\s*(-?\d+(?:\.\d+)?)/i);
  if (numericFromObject?.[1]) {
    return `${calculator} Score: ${numericFromObject[1]}`;
  }

  const numericFromScoreText = raw.match(/\bscore\s*[:\-]?\s*(-?\d+(?:\.\d+)?)/i);
  if (numericFromScoreText?.[1]) {
    return `${calculator} Score: ${numericFromScoreText[1]}`;
  }

  const value = raw
    .replace(/raw\s*text[:\-]?\s*/gi, "")
    .replace(/\(\s*Max\s*44\s*\)/gi, "")
    .replace(/\bMax\s*44\b/gi, "")
    .trim();

  if (!value) return calculator;
  if (/^(mild|moderate|severe|clear|none|minimal)$/i.test(value)) return `${calculator}: ${value}`;
  return `${calculator} Score: ${value}`;
}

export default function PatientDetail() {
  const { id } = useParams();
  const { doctor } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state as any) || {};
  const [history, setHistory] = useState<CaseHistory[]>([]);
  const [loading, setLoading] = useState(true);

  const patientId = parseInt(id || "0");

  useEffect(() => {
    api.getPatientHistory(patientId)
      .then((res) => { if (res.success) setHistory(res.history); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [patientId]);

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              if (navState?.fromDashboard) {
                navigate("/dashboard");
                return;
              }
              navigate("/patients", { state: { returnContext: navState?.returnContext } });
            }}
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-foreground">Patient History</h1>
            <p className="text-muted-foreground">Patient ID: {patientId}</p>
          </div>
          <Button onClick={() => navigate(`/analyze/${patientId}`)} className="medical-gradient text-primary-foreground gap-2">
            <Upload className="w-4 h-4" /> New Clinical Review
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-12 text-muted-foreground">Loading...</div>
        ) : history.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground mb-3">No case history for this patient</p>
            <Button onClick={() => navigate(`/analyze/${patientId}`)} className="gap-2 medical-gradient text-primary-foreground">
              <Upload className="w-4 h-4" /> Start First Clinical Review
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {history.map((c) => (
              <div
                key={c.case_id}
                className="medical-card p-4 cursor-pointer hover:border-accent/30 transition-colors"
                onClick={() =>
                  navigate(`/case/${c.case_id}`, {
                    state: {
                      fromPatientDetail: true,
                      patientId,
                      returnContext: navState?.returnContext,
                    },
                  })
                }
              >
                <div className="flex items-center gap-4">
                  <div className="p-2.5 rounded-xl bg-medical-highlight">
                    <Activity className="w-5 h-5 text-accent" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-muted-foreground flex items-center gap-1">
                      <Calendar className="w-3 h-3" />{formatCaseDate(c.date)}
                    </p>
                    <div className="mt-1 space-y-1">
                      <p className="font-semibold text-foreground">Diagnosis: {formatDiagnosis(c.disease)}</p>
                      <p className="text-sm text-muted-foreground">{formatSeverityResult(c.disease, c.severity)}</p>
                      {c.has_prescription && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 border border-emerald-200">
                          Prescription Given
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
