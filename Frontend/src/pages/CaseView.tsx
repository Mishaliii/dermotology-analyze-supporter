import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { api, PrescriptionView } from "@/lib/api";
import AppLayout from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Pill, Printer, FileText } from "lucide-react";

export default function CaseView() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state as any) || {};
  const [rx, setRx] = useState<PrescriptionView["prescription"] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!caseId) return;
    api.getCasePrescription(parseInt(caseId))
      .then((res) => { if (res.success) setRx(res.prescription); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [caseId]);

  return (
    <AppLayout>
      <div className="space-y-6 max-w-3xl mx-auto">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              if (navState?.fromPatientDetail && navState?.patientId) {
                navigate(`/patient/${navState.patientId}`, {
                  state: { fromPatients: true, returnContext: navState?.returnContext },
                });
                return;
              }
              if (navState?.fromDashboard) {
                navigate("/dashboard");
                return;
              }
              navigate("/history");
            }}
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <h1 className="text-2xl font-bold text-foreground">Case #{caseId}</h1>
          {rx && (
            <Button variant="outline" size="sm" className="ml-auto gap-1" onClick={() => window.print()}>
              <Printer className="w-4 h-4" /> Print
            </Button>
          )}
        </div>

        {loading ? (
          <p className="text-muted-foreground text-center py-12">Loading...</p>
        ) : !rx ? (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground">No prescription found for this case</p>
          </div>
        ) : (
          <div className="medical-card p-6 print:shadow-none print:border-0">
            {/* Prescription Header */}
            <div className="border-b pb-4 mb-4">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-medical-highlight">
                  <Pill className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground">Prescription</h2>
                  <p className="text-sm text-muted-foreground">{rx.date}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Doctor:</span>
                  <p className="font-medium text-foreground">{rx.doctor}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Patient:</span>
                  <p className="font-medium text-foreground">{rx.patient}</p>
                </div>
                <div className="col-span-2">
                  <span className="text-muted-foreground">Diagnosis:</span>
                  <p className="font-medium text-foreground">{rx.diagnosis}</p>
                </div>
              </div>
            </div>

            {/* Medicines */}
            <div className="mb-4">
              <h3 className="font-semibold text-foreground mb-3">Prescribed Medicines</h3>
              <div className="space-y-2">
                {rx.items.map((item, i) => (
                  <div key={i} className="border rounded-lg p-3 bg-muted/30">
                    <div className="flex items-start gap-2">
                      <span className="text-xs font-bold text-accent mt-0.5">{i + 1}.</span>
                      <div className="flex-1">
                        <p className="font-medium text-foreground">{item.name}</p>
                        <div className="flex flex-wrap gap-3 mt-1 text-sm text-muted-foreground">
                          {item.dose && <span>Dose: {item.dose}</span>}
                          {item.frequency && <span>Freq: {item.frequency}</span>}
                          {item.duration && <span>Duration: {item.duration}</span>}
                        </div>
                        {item.instructions && <p className="text-sm text-muted-foreground mt-1 italic">{item.instructions}</p>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Notes */}
            {rx.notes && (
              <div className="border-t pt-4">
                <h3 className="font-semibold text-foreground mb-1">Notes</h3>
                <p className="text-sm text-muted-foreground">{rx.notes}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
