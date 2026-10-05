import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { api, ScoringResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { X, RotateCcw, Calculator, Loader2 } from "lucide-react";

interface Props {
  disease: string;
  calculatorType: string;
  imagePath: string;
  initialMetrics?: Record<string, number>;
  onComplete: (score: number, label: string) => void;
  onClose: () => void;
}

interface SliderField {
  key: string;
  label: string;
  min: number;
  max: number;
  step?: number;
}

interface Region {
  name: string;
  fields: SliderField[];
}

const REGIONAL_CALCULATORS = new Set(["PASI", "GAGS", "EASI"]);

export default function SeverityCalculator({ disease, calculatorType, imagePath, initialMetrics, onComplete, onClose }: Props) {
  const { toast } = useToast();
  const normalizedCalculatorType = (calculatorType || "").toUpperCase();
  const aiEnabled = !REGIONAL_CALCULATORS.has(normalizedCalculatorType);
  const mappedInitialMetrics = aiEnabled && initialMetrics ? mapAiMetricsToCalculator(normalizedCalculatorType, initialMetrics) : {};
  const [values, setValues] = useState<Record<string, number>>(() => mappedInitialMetrics);
  const [aiValues, setAiValues] = useState<Record<string, number>>(() => mappedInitialMetrics);
  const [loading, setLoading] = useState(!Object.keys(mappedInitialMetrics).length);
  const [aiUnavailable, setAiUnavailable] = useState(false);
  const [score, setScore] = useState(0);
  const [label, setLabel] = useState("");

  // Fetch AI scoring
  useEffect(() => {
    if (!aiEnabled) {
      setValues({});
      setAiValues({});
      setAiUnavailable(false);
      setLoading(false);
      return;
    }

    const mapped = initialMetrics ? mapAiMetricsToCalculator(normalizedCalculatorType, initialMetrics) : {};

    if (Object.keys(mapped).length) {
      setAiValues(mapped);
      setValues(mapped);
      setAiUnavailable(false);
      setLoading(false);
      return;
    }

    let cancelled = false;

    const fetchScoring = async () => {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          const res: ScoringResult = await api.scoreDisease(imagePath, disease);
          if (cancelled) return;

          if (res.success && res.metrics) {
            const mapped = mapAiMetricsToCalculator(normalizedCalculatorType, res.metrics);
            if (!Object.keys(mapped).length) {
              setAiUnavailable(true);
              toast({
                title: "Severity assessment unavailable",
                description: "AI severity could not prefill this calculator. Please score manually.",
                variant: "destructive",
              });
              return;
            }
            setAiUnavailable(false);
            setAiValues(mapped);
            setValues(mapped);
            return;
          }

          if (res.loading && attempt < 2) {
            await new Promise((resolve) => setTimeout(resolve, 2500 + attempt * 1500));
            continue;
          }

          if (!res.success && res.error) {
            setAiUnavailable(true);
            toast({ title: "Severity assessment unavailable", description: res.error, variant: "destructive" });
          }
          return;
        } catch {
          if (cancelled) return;
          if (attempt === 1) {
            setAiUnavailable(true);
            toast({
              title: "Severity assessment unavailable",
              description: "Please retry in a moment.",
              variant: "destructive",
            });
          }
        }
      }
    };

    fetchScoring().finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [imagePath, disease, initialMetrics, normalizedCalculatorType, aiEnabled]);

  // Recalculate on value change
  useEffect(() => {
    const { s, l } = calculate(normalizedCalculatorType, values);
    setScore(s);
    setLabel(l);
  }, [values, normalizedCalculatorType]);

  const setVal = (key: string, val: number) => setValues((prev) => ({ ...prev, [key]: val }));
  const reset = () => setValues({ ...aiValues });
  const adjust = (key: string, delta: number, min: number, max: number, step: number) => {
    const current = values[key] ?? min;
    const next = Math.max(min, Math.min(max, current + delta * step));
    setVal(key, Number(next.toFixed(4)));
  };

  const config = getCalculatorConfig(normalizedCalculatorType);
  const aiFieldCount = Object.keys(aiValues).length;

  if (loading) {
    return (
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
      >
        <motion.div
          className="medical-card p-8 text-center"
          initial={{ opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
        >
          <Loader2 className="w-8 h-8 animate-spin text-accent mx-auto mb-3" />
          <p className="text-foreground font-medium">Loading AI severity assessment...</p>
        </motion.div>
      </motion.div>
    );
  }

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 backdrop-blur-sm p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      <motion.div
        className="bg-card rounded-2xl border shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden"
        initial={{ opacity: 0, y: 18, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.985 }}
        transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/60 bg-background/40 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-medical-highlight">
              <Calculator className="w-5 h-5 text-accent" />
            </div>
            <div>
              <h2 className="font-bold text-foreground">{config.title}</h2>
              <p className="text-sm text-muted-foreground">{disease.replace(/_/g, " ")}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={reset} className="gap-1">
              <RotateCcw className="w-3 h-3" /> {aiEnabled ? "Reset AI" : "Reset"}
            </Button>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {aiUnavailable && (
          <div className="px-4 py-2 border-b bg-amber-50 text-amber-900 text-sm">
            AI severity assessment was unavailable for this image. Please continue with manual scoring.
          </div>
        )}

        {/* Score Display */}
        <div className="px-4 py-3 bg-medical-highlight border-b border-white/50">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm text-muted-foreground">Calculated Score</span>
              <div className="flex items-center gap-2">
                <span className="text-3xl font-bold text-foreground">{score.toFixed(1)}</span>
                <span className={`text-sm font-medium px-2 py-0.5 rounded-full ${getSeverityBadgeClass(label)}`}>{label}</span>
              </div>
            </div>
            <span className="text-xs text-muted-foreground">{config.maxInfo}</span>
          </div>
        </div>

        {/* Calculator Body */}
        <div className="flex-1 overflow-y-auto p-4 hide-scrollbar">
          {config.regions.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {config.regions.map((region) => (
                <div key={region.name} className="border rounded-lg p-3">
                  <h4 className="font-semibold text-foreground text-sm mb-2">{region.name}</h4>
                  <div className="space-y-3">
                    {region.fields.map((f) => {
                      const key = `${region.name}_${f.key}`.replace(/\s+/g, "_").toLowerCase();
                      const val = values[key] ?? f.min;
                      return (
                        <div key={key} className="space-y-1">
                          <div className="flex items-center justify-between">
                            <Label className="text-xs">{f.label}</Label>
                            <span className="text-xs font-mono font-bold text-accent">{val}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => adjust(key, -1, f.min, f.max, f.step || 1)}
                            >
                              -
                            </Button>
                            <Slider
                              min={f.min}
                              max={f.max}
                              step={f.step || 1}
                              value={[val]}
                              onValueChange={([v]) => setVal(key, v)}
                            />
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => adjust(key, 1, f.min, f.max, f.step || 1)}
                            >
                              +
                            </Button>
                          </div>
                          <div className="flex justify-between text-[10px] text-muted-foreground">
                            <span>{f.min}</span>
                            <span>{f.max}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {config.fields.map((f) => {
                const val = values[f.key] ?? f.min;
                return (
                  <div key={f.key} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <Label className="text-sm">{f.label}</Label>
                      <span className="text-sm font-mono font-bold text-accent">{val}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => adjust(f.key, -1, f.min, f.max, f.step || 1)}
                      >
                        -
                      </Button>
                      <Slider min={f.min} max={f.max} step={f.step || 1} value={[val]} onValueChange={([v]) => setVal(f.key, v)} />
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => adjust(f.key, 1, f.min, f.max, f.step || 1)}
                      >
                        +
                      </Button>
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                      <span>{f.min}</span>
                      <span>{f.max}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/60 flex justify-end gap-3 bg-background/30 backdrop-blur-sm">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onComplete(score, label)} className="medical-gradient text-primary-foreground gap-2">
            <Calculator className="w-4 h-4" /> Confirm & Generate Treatment
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function getSeverityBadgeClass(label: string) {
  const l = label.toLowerCase();
  if (l.includes("severe") || l.includes("high")) return "severity-badge-severe";
  if (l.includes("moderate")) return "severity-badge-moderate";
  if (l.includes("mild") || l.includes("low")) return "severity-badge-low";
  return "severity-badge-moderate";
}

function sliderKey(regionName: string, fieldKey: string): string {
  return `${regionName}_${fieldKey}`.replace(/\s+/g, "_").toLowerCase();
}

function clampNumber(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

function mapAiMetricsToCalculator(type: string, metrics: Record<string, any>): Record<string, number> {
  const out: Record<string, number> = {};
  const m = metrics || {};

  if (type === "PASI") {
    const e = clampNumber(Number(m.erythema ?? 0), 0, 4);
    const i = clampNumber(Number(m.thickness ?? m.induration ?? 0), 0, 4);
    const sc = clampNumber(Number(m.scaling ?? 0), 0, 4);
    const area = clampNumber(Number(m.area_score ?? 0), 0, 6);
    ["Head", "Upper Limbs", "Trunk", "Lower Limbs"].forEach((r) => {
      out[sliderKey(r, "erythema")] = e;
      out[sliderKey(r, "induration")] = i;
      out[sliderKey(r, "scaling")] = sc;
      out[sliderKey(r, "area")] = area;
    });
    return out;
  }

  if (type === "GAGS") {
    const rs = (m.regional_scores || {}) as Record<string, number>;
    const fallback = clampNumber(Number(m.max_severity_grade ?? 0), 0, 4);
    out[sliderKey("Forehead (×2)", "severity")] = clampNumber(Number(rs.fh ?? fallback), 0, 4);
    out[sliderKey("Right Cheek (×2)", "severity")] = clampNumber(Number(rs.rc ?? fallback), 0, 4);
    out[sliderKey("Left Cheek (×2)", "severity")] = clampNumber(Number(rs.lc ?? fallback), 0, 4);
    out[sliderKey("Nose (×1)", "severity")] = clampNumber(Number(rs.no ?? fallback), 0, 4);
    out[sliderKey("Chin (×1)", "severity")] = clampNumber(Number(rs.ch ?? fallback), 0, 4);
    out[sliderKey("Chest/Back (×3)", "severity")] = clampNumber(Number(rs.cb ?? fallback), 0, 4);
    return out;
  }

  if (type === "EASI") {
    const erythema = clampNumber(Number(m.erythema ?? 0), 0, 3);
    const edema = clampNumber(Number(m.edema ?? m.thickness ?? 0), 0, 3);
    const exc = clampNumber(Number(m.excoriation ?? 0), 0, 3);
    const lich = clampNumber(Number(m.lichenification ?? m.scaling ?? 0), 0, 3);
    const area = clampNumber(Number(m.area_score ?? 0), 0, 6);
    ["Head/Neck", "Upper Limbs", "Trunk", "Lower Limbs"].forEach((r) => {
      out[sliderKey(r, "erythema")] = erythema;
      out[sliderKey(r, "edema")] = edema;
      out[sliderKey(r, "excoriation")] = exc;
      out[sliderKey(r, "lichenification")] = lich;
      out[sliderKey(r, "area")] = area;
    });
    return out;
  }

  if (type === "VASI") {
    const dep = clampNumber(Number(m.depigmentation_pct ?? m.depigmentation ?? 0), 0, 100);
    out.depigmentation = dep;
    out.hand_units = clampNumber(Number(m.hand_units ?? dep), 0, 100);
    return out;
  }

  if (type === "ABCDE") {
    out.asymmetry = clampNumber(Number(m.asymmetry ?? 0), 0, 2);
    out.border = clampNumber(Number(m.border ?? 0), 0, 2);
    out.color = clampNumber(Number(m.color ?? 0), 0, 2);
    out.diameter = clampNumber(Number(m.diameter ?? 0), 0, 1);
    out.evolution = clampNumber(Number(m.evolution ?? 0), 0, 3);
    return out;
  }

  if (type === "SALT") {
    const hairLoss = clampNumber(Number(m.hair_loss_pct ?? 0), 0, 100);
    out.top = hairLoss;
    out.back = hairLoss;
    out.left = hairLoss;
    out.right = hairLoss;
    return out;
  }

  out.severity = clampNumber(Number(m.severity ?? m.max_severity_grade ?? 0), 0, 10);
  return out;
}

interface CalcConfig {
  title: string;
  maxInfo: string;
  regions: Region[];
  fields: SliderField[];
}

function getCalculatorConfig(type: string): CalcConfig {
  switch (type) {
    case "PASI":
      return {
        title: "PASI Calculator",
        maxInfo: "Max: 72",
        fields: [],
        regions: ["Head", "Upper Limbs", "Trunk", "Lower Limbs"].map((r) => ({
          name: r,
          fields: [
            { key: "erythema", label: "Erythema", min: 0, max: 4 },
            { key: "induration", label: "Induration", min: 0, max: 4 },
            { key: "scaling", label: "Scaling", min: 0, max: 4 },
            { key: "area", label: "Area Score", min: 0, max: 6 },
          ],
        })),
      };
    case "GAGS":
      return {
        title: "GAGS Calculator",
        maxInfo: "Max: 44",
        fields: [],
        regions: [
          { name: "Forehead", factor: 2 },
          { name: "Right Cheek", factor: 2 },
          { name: "Left Cheek", factor: 2 },
          { name: "Nose", factor: 1 },
          { name: "Chin", factor: 1 },
          { name: "Chest/Back", factor: 3 },
        ].map((r) => ({
          name: `${r.name} (×${r.factor})`,
          fields: [{ key: "severity", label: "Severity (0=Clear, 4=Nodules)", min: 0, max: 4 }],
        })),
      };
    case "EASI":
      return {
        title: "EASI Calculator",
        maxInfo: "Max: 72",
        fields: [],
        regions: ["Head/Neck", "Upper Limbs", "Trunk", "Lower Limbs"].map((r) => ({
          name: r,
          fields: [
            { key: "erythema", label: "Erythema", min: 0, max: 3 },
            { key: "edema", label: "Edema/Papules", min: 0, max: 3 },
            { key: "excoriation", label: "Excoriation", min: 0, max: 3 },
            { key: "lichenification", label: "Lichenification", min: 0, max: 3 },
            { key: "area", label: "Area", min: 0, max: 6 },
          ],
        })),
      };
    case "VASI":
      return {
        title: "VASI Calculator",
        maxInfo: "Max: 100",
        regions: [],
        fields: [
          { key: "depigmentation", label: "Depigmentation (%)", min: 0, max: 100, step: 5 },
          { key: "hand_units", label: "Hand Units", min: 0, max: 100, step: 1 },
        ],
      };
    case "ABCDE":
      return {
        title: "ABCDE Risk Assessment",
        maxInfo: "Max: 10",
        regions: [],
        fields: [
          { key: "asymmetry", label: "Asymmetry (A)", min: 0, max: 2 },
          { key: "border", label: "Border Irregularity (B)", min: 0, max: 2 },
          { key: "color", label: "Color Variation (C)", min: 0, max: 2 },
          { key: "diameter", label: "Diameter >6mm (D)", min: 0, max: 1 },
          { key: "evolution", label: "Evolution (E)", min: 0, max: 3 },
        ],
      };
    case "SALT":
      return {
        title: "SALT Calculator",
        maxInfo: "Max: 100%",
        regions: [],
        fields: [
          { key: "top", label: "Top (40%)", min: 0, max: 100, step: 5 },
          { key: "back", label: "Back (24%)", min: 0, max: 100, step: 5 },
          { key: "left", label: "Left Side (18%)", min: 0, max: 100, step: 5 },
          { key: "right", label: "Right Side (18%)", min: 0, max: 100, step: 5 },
        ],
      };
    default:
      return {
        title: "Severity Assessment",
        maxInfo: "Scale: 0-10",
        regions: [],
        fields: [{ key: "severity", label: "Visual Severity", min: 0, max: 10, step: 1 }],
      };
  }
}

function calculate(type: string, values: Record<string, number>): { s: number; l: string } {
  const v = (key: string) => values[key] ?? 0;

  switch (type) {
    case "PASI": {
      const regionScore = (prefix: string) => {
        const e = v(`${prefix}_erythema`);
        const i = v(`${prefix}_induration`);
        const sc = v(`${prefix}_scaling`);
        const a = v(`${prefix}_area`);
        return (e + i + sc) * a;
      };
      const s = 0.1 * regionScore("head") + 0.2 * regionScore("upper_limbs") + 0.3 * regionScore("trunk") + 0.4 * regionScore("lower_limbs");
      return { s, l: s >= 20 ? "Severe" : s >= 10 ? "Moderate" : s >= 5 ? "Mild" : "Clear/Minimal" };
    }
    case "GAGS": {
      const factors = [
        { region: "forehead_(×2)", factor: 2 },
        { region: "right_cheek_(×2)", factor: 2 },
        { region: "left_cheek_(×2)", factor: 2 },
        { region: "nose_(×1)", factor: 1 },
        { region: "chin_(×1)", factor: 1 },
        { region: "chest/back_(×3)", factor: 3 },
      ];
      const s = factors.reduce((sum, f) => sum + v(`${f.region}_severity`) * f.factor, 0);
      return { s, l: s >= 31 ? "Severe" : s >= 19 ? "Moderate" : s >= 1 ? "Mild" : "None" };
    }
    case "EASI": {
      const regionScore = (prefix: string) => {
        const e = v(`${prefix}_erythema`);
        const ed = v(`${prefix}_edema`);
        const ex = v(`${prefix}_excoriation`);
        const li = v(`${prefix}_lichenification`);
        const a = v(`${prefix}_area`);
        return (e + ed + ex + li) * a;
      };
      const s = 0.1 * regionScore("head/neck") + 0.2 * regionScore("upper_limbs") + 0.3 * regionScore("trunk") + 0.4 * regionScore("lower_limbs");
      return { s, l: s >= 21 ? "Severe" : s >= 7 ? "Moderate" : s >= 1 ? "Mild" : "Clear" };
    }
    case "VASI": {
      const s = v("hand_units") * (v("depigmentation") / 100);
      return { s, l: s >= 50 ? "Severe" : s >= 25 ? "Moderate" : s >= 1 ? "Mild" : "Minimal" };
    }
    case "ABCDE": {
      const s = v("asymmetry") + v("border") + v("color") + v("diameter") + v("evolution");
      return { s, l: s >= 7 ? "High Risk" : s >= 4 ? "Moderate Risk" : "Low Risk" };
    }
    case "SALT": {
      const s = 0.40 * v("top") + 0.24 * v("back") + 0.18 * v("left") + 0.18 * v("right");
      return { s, l: s >= 75 ? "Severe (S4-S5)" : s >= 50 ? "Moderate-Severe (S3)" : s >= 25 ? "Moderate (S2)" : "Mild (S1)" };
    }
    default: {
      const s = v("severity");
      return { s, l: s >= 7 ? "Severe" : s >= 4 ? "Moderate" : "Mild" };
    }
  }
}
