import { useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { api, AnalysisResult, DiseaseMatch } from "@/lib/api";
import AppLayout from "@/components/AppLayout";
import SeverityCalculator from "@/components/SeverityCalculator";
import PrescriptionModal from "@/components/PrescriptionModal";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Upload, Image, ArrowLeft, Check, Activity, Loader2, X, FileText } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function AnalysisPage() {
  const { patientId } = useParams();
  const { doctor } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedDisease, setSelectedDisease] = useState<DiseaseMatch | null>(null);
  const [showCalculator, setShowCalculator] = useState(false);
  const [showPrescription, setShowPrescription] = useState(false);
  const [severityData, setSeverityData] = useState<{ score: number; label: string } | null>(null);
  const [caseId, setCaseId] = useState<number | null>(null);
  const [caseInfo, setCaseInfo] = useState<{ doctorName: string; patientName: string } | null>(null);
  const [prefetchedScores, setPrefetchedScores] = useState<Record<string, Record<string, number>>>({});
  const [modelsLoading, setModelsLoading] = useState(false);
  const [showSuggestionsOverride, setShowSuggestionsOverride] = useState(false);

  const regionalCalculators = new Set(["PASI", "GAGS", "EASI"]);
  const diseaseKey = (name: string) => name.toLowerCase().replace(/[\s-]+/g, "_");

  const prefetchSeverity = async (imagePath: string, diseases: string[]) => {
    const unique = Array.from(new Set(diseases.map(diseaseKey))).slice(0, 4);
    if (!unique.length) return;

    await Promise.all(
      unique.map(async (key) => {
        const disease = diseases.find((d) => diseaseKey(d) === key) || key;
        try {
          const scored = await api.scoreDisease(imagePath, disease);
          if (scored.success && scored.metrics) {
            setPrefetchedScores((prev) => ({ ...prev, [key]: scored.metrics! }));
          }
        } catch {
          // Best effort prefetch; calculator still works with on-demand fallback.
        }
      }),
    );
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
    setShowSuggestionsOverride(false);
    setSelectedDisease(null);
    setSeverityData(null);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setAnalyzing(true);
    setModelsLoading(false);
    try {
      const health = await api.getModelsHealth();
      setModelsLoading(Boolean(health.loading && !health.ready));
      if (health.loading && !health.ready) {
        toast({
          title: "Clinical analysis engine is starting",
          description: "Please retry in about 30-60 seconds. You can continue other tasks meanwhile.",
        });
        return;
      }

      const res = await api.analyzeImage(file);
      if (!res.success) {
        throw new Error(res.error || (res.loading ? "Clinical analysis engine is still initializing. Please retry shortly." : "Analysis failed"));
      }
      setResult(res);
      setShowSuggestionsOverride(false);
      if (res.analysis_decision?.candidate_status === "no_disease_candidate") {
        toast({
          title: "No clear lesion detected",
          description: "Upload a clearer lesion-focused image, or review suggestions manually.",
        });
      } else if (res.analysis_decision?.candidate_status === "uncertain") {
        toast({
          title: "Low-confidence analysis",
          description: `Found ${res.cls_knn.length} possible conditions.`,
        });
      } else {
        toast({ title: "Clinical analysis complete", description: `Found ${res.cls_knn.length} likely conditions.` });
      }

      void prefetchSeverity(
        res.analyzed_image_path,
        res.cls_knn.map((m) => m.disease).filter((disease) => !regionalCalculators.has(getCalculatorType(disease))),
      );
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
    setAnalyzing(false);
  };

  const handleConfirmDisease = (d: DiseaseMatch) => {
    setSelectedDisease(d);
    setShowCalculator(true);
  };

  const handleSeverityComplete = async (score: number, label: string) => {
    setSeverityData({ score, label });
    setShowCalculator(false);

    if (!doctor || !patientId || !result || !selectedDisease) return;
    try {
      const caseRes = await api.createCase({
        doctor_id: doctor.id,
        patient_id: parseInt(patientId),
        image_path: result.analyzed_image_path,
        predicted_disease_name: result.cls_knn[0]?.disease || selectedDisease.disease,
        confirmed_disease_name: selectedDisease.disease,
        severity_json: { raw_text: label, numeric: score },
        ai_confidence: selectedDisease.confidence,
      });
      if (caseRes.success) {
        setCaseId(caseRes.case_id!);
        setCaseInfo({ doctorName: caseRes.doctor_name || doctor.name, patientName: caseRes.patient_name || "" });
        setShowPrescription(true);
      }
    } catch (e: any) {
      toast({ title: "Error creating case", description: e.message, variant: "destructive" });
    }
  };

  const calculatorMap: Record<string, string> = {
    psoriasis: "PASI", acne: "GAGS", acne_vulgaris: "GAGS",
    dermatitis: "EASI", eczema: "EASI", atopic_dermatitis: "EASI",
    vitiligo: "VASI",
    melanoma: "ABCDE", nevus: "ABCDE", mole: "ABCDE",
    alopecia: "SALT", alopecia_areata: "SALT",
  };

  const getCalculatorType = (disease: string) => {
    const d = disease.toLowerCase().replace(/[\s-]+/g, "_");
    for (const [key, val] of Object.entries(calculatorMap)) {
      if (d.includes(key)) return val;
    }
    return "GENERIC";
  };

  const selectedCalculatorType = selectedDisease ? getCalculatorType(selectedDisease.disease) : "GENERIC";

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(`/patient/${patientId}`)}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Image Analysis</h1>
            <p className="text-muted-foreground">Patient ID: {patientId}</p>
          </div>
        </div>

        {modelsLoading && (
          <div className="medical-card p-4 border-accent/30">
            <p className="text-sm text-muted-foreground">
              AI models are warming up in the background. You can continue documenting the case; severity scoring will be ready shortly.
            </p>
          </div>
        )}

        {/* Upload Area */}
        {!result && (
          <div className="medical-card p-8">
            <input ref={fileRef} type="file" accept="image/*" onChange={handleFile} className="hidden" />
            {!preview ? (
              <div onClick={() => fileRef.current?.click()} className="border-2 border-dashed border-border rounded-xl p-12 text-center cursor-pointer hover:border-accent/50 hover:bg-medical-highlight transition-all">
                <Upload className="w-12 h-12 text-muted-foreground/40 mx-auto mb-4" />
                <p className="text-lg font-medium text-foreground">Upload lesion photograph</p>
                <p className="text-sm text-muted-foreground mt-1">Click or drag to add a clinical dermatology image</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="relative max-w-md mx-auto">
                  <img src={preview} alt="Clinical" className="rounded-xl w-full object-cover max-h-80" />
                  <button onClick={() => { setPreview(null); setFile(null); }} className="absolute top-2 right-2 p-1.5 rounded-full bg-card/80 backdrop-blur-sm hover:bg-card">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex justify-center gap-3">
                  <Button variant="outline" onClick={() => fileRef.current?.click()}>Replace Image</Button>
                  <Button onClick={handleAnalyze} disabled={analyzing} className="medical-gradient text-primary-foreground gap-2">
                    {analyzing ? <><Loader2 className="w-4 h-4 animate-spin" />Running analysis...</> : <><Activity className="w-4 h-4" />Run Clinical Analysis</>}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Results */}
        <AnimatePresence>
          {result && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
              {(() => {
                const noDiseaseCandidate = result.analysis_decision?.candidate_status === "no_disease_candidate";
                const hideSuggestions = noDiseaseCandidate && !showSuggestionsOverride;

                return (
                  <>
              {result.analysis_decision?.candidate_status === "no_disease_candidate" && (
                <div className="medical-card p-4 border-amber-300/60 bg-amber-50/50">
                  <p className="text-sm font-medium text-amber-800">
                    No clear dermatologic lesion pattern was detected in this image.
                  </p>
                  <p className="text-xs text-amber-700 mt-1">
                    You can upload a clearer lesion-focused image, or continue with manual clinical judgment.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setResult(null);
                        setPreview(null);
                        setFile(null);
                        setSelectedDisease(null);
                        setShowSuggestionsOverride(false);
                        fileRef.current?.click();
                      }}
                    >
                      Upload Better Image
                    </Button>
                    <Button size="sm" onClick={() => setShowSuggestionsOverride(true)}>
                      Show Suggestions
                    </Button>
                  </div>
                </div>
              )}

              {result.analysis_decision?.candidate_status === "uncertain" && (
                <div className="medical-card p-4 border-blue-300/60 bg-blue-50/50">
                  <p className="text-sm font-medium text-blue-800">
                    Low-confidence image match. Suggested diagnoses may be less reliable.
                  </p>
                  <p className="text-xs text-blue-700 mt-1">
                    Consider uploading another image with better lesion focus and lighting.
                  </p>
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Uploaded Image */}
                <div className="medical-card p-4">
                  <h3 className="font-semibold text-foreground mb-3">Uploaded Image</h3>
                  <img src={preview || ""} alt="Uploaded" className="rounded-lg w-full object-cover" />
                  <Button variant="outline" onClick={() => { setResult(null); setPreview(null); setFile(null); setSelectedDisease(null); setShowSuggestionsOverride(false); }} className="w-full mt-3" size="sm">
                    Start New Case Image
                  </Button>
                </div>

                {/* Disease Matches */}
                <div className="lg:col-span-2 medical-card p-4">
                  <h3 className="font-semibold text-foreground mb-3">Differential Diagnosis Suggestions</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    {hideSuggestions
                      ? "Suggestions are hidden for this no-lesion candidate image."
                      : "Select and confirm the working diagnosis to continue with severity grading."}
                  </p>
                  {hideSuggestions ? (
                    <div className="rounded-lg border border-dashed border-amber-300/70 bg-amber-50/40 p-4">
                      <p className="text-sm text-amber-800">
                        Suggestions are intentionally hidden to reduce accidental diagnosis on likely non-disease images.
                      </p>
                    </div>
                  ) : (
                  <div className="space-y-2">
                    {result.cls_knn.slice(0, 10).map((d, i) => (
                      <motion.div key={i} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                        className={`flex items-center gap-4 p-3 rounded-lg border cursor-pointer transition-all ${
                          selectedDisease?.disease === d.disease ? "border-accent bg-medical-highlight" : "border-transparent hover:bg-muted"
                        }`}
                        onClick={() => setSelectedDisease(d)}>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-foreground">{d.disease.replace(/_/g, " ")}</p>
                            {selectedDisease?.disease === d.disease && <Check className="w-4 h-4 text-accent" />}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                              <div className="h-full rounded-full medical-gradient" style={{ width: `${d.confidence * 100}%` }} />
                            </div>
                            <span className="text-sm font-medium text-muted-foreground">{(d.confidence * 100).toFixed(1)}%</span>
                          </div>
                        </div>
                        <Button size="sm" variant={selectedDisease?.disease === d.disease ? "default" : "outline"} onClick={(e) => { e.stopPropagation(); handleConfirmDisease(d); }}
                          className={selectedDisease?.disease === d.disease ? "medical-gradient text-primary-foreground" : ""}>
                          Confirm & Grade Severity
                        </Button>
                      </motion.div>
                    ))}
                  </div>
                  )}
                </div>
              </div>
                  </>
                );
              })()}

              {/* Severity Result */}
              {severityData && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="medical-card p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-foreground">Assessment Complete</h3>
                      <p className="text-muted-foreground mt-1">
                        {selectedDisease?.disease.replace(/_/g, " ")} — Score: {severityData.score.toFixed(1)} ({severityData.label})
                      </p>
                    </div>
                    <Button onClick={() => setShowPrescription(true)} className="medical-gradient text-primary-foreground gap-2">
                      <FileText className="w-4 h-4" /> View Prescription
                    </Button>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Severity Calculator Modal */}
      <AnimatePresence>
        {showCalculator && selectedDisease && (
          <SeverityCalculator
            disease={selectedDisease.disease}
            calculatorType={selectedCalculatorType}
            imagePath={result?.analyzed_image_path || ""}
            initialMetrics={regionalCalculators.has(selectedCalculatorType) ? undefined : prefetchedScores[diseaseKey(selectedDisease.disease)]}
            onComplete={handleSeverityComplete}
            onClose={() => setShowCalculator(false)}
          />
        )}
      </AnimatePresence>

      {/* Prescription Modal */}
      <AnimatePresence>
        {showPrescription && caseId && selectedDisease && severityData && (
          <PrescriptionModal
            caseId={caseId}
            disease={selectedDisease.disease}
            severity={severityData.label}
            severityScore={severityData.score}
            doctorName={caseInfo?.doctorName || doctor?.name || ""}
            patientName={caseInfo?.patientName || ""}
            onClose={() => setShowPrescription(false)}
          />
        )}
      </AnimatePresence>
    </AppLayout>
  );
}
