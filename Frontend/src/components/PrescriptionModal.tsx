import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { api, MedicineSuggestion, PrescriptionItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { X, Plus, Trash2, Search, Pill, Save, Loader2, Check } from "lucide-react";

interface Props {
  caseId: number;
  disease: string;
  severity: string;
  severityScore: number;
  doctorName: string;
  patientName: string;
  onClose: () => void;
}

interface RxItem {
  medicine_id?: number;
  name: string;
  dose: string;
  frequency: string;
  duration: string;
  instructions: string;
}

export default function PrescriptionModal({ caseId, disease, severity, severityScore, doctorName, patientName, onClose }: Props) {
  const { toast } = useToast();
  const [items, setItems] = useState<RxItem[]>([]);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ id: number; name: string; form: string; strength: string }[]>([]);
  const [showSearch, setShowSearch] = useState(false);

  useEffect(() => {
    api.generatePrescription(caseId, disease, severityScore)
      .then((res) => {
        if (res.success && res.suggestions) {
          setItems(res.suggestions.map((s) => ({
            medicine_id: s.medicine_id,
            name: s.name,
            dose: s.dose || s.strength,
            frequency: "As directed",
            duration: s.duration || "As needed",
            instructions: "",
          })));
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [caseId, disease, severityScore]);

  const updateItem = (idx: number, field: keyof RxItem, value: string) => {
    setItems((prev) => prev.map((item, i) => i === idx ? { ...item, [field]: value } : item));
  };

  const removeItem = (idx: number) => setItems((prev) => prev.filter((_, i) => i !== idx));

  const addBlankItem = () => {
    setItems((prev) => [...prev, { name: "", dose: "", frequency: "", duration: "", instructions: "" }]);
  };

  const handleSearch = async (q: string) => {
    setSearchQuery(q);
    if (q.length < 2) { setSearchResults([]); return; }
    try {
      const res = await api.searchMedicines(q, disease);
      if (res.success) setSearchResults(res.medicines);
    } catch { }
  };

  const addFromSearch = (med: { id: number; name: string; form: string; strength: string }) => {
    setItems((prev) => [...prev, {
      medicine_id: med.id,
      name: `${med.name} (${med.form} ${med.strength})`,
      dose: med.strength,
      frequency: "As directed",
      duration: "As needed",
      instructions: "",
    }]);
    setShowSearch(false);
    setSearchQuery("");
    setSearchResults([]);
  };

  const handleSave = async () => {
    if (items.length === 0) {
      toast({ title: "No medicines", description: "Add at least one medicine.", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      const payload: PrescriptionItem[] = items.map((item) => ({
        medicine_id: item.medicine_id,
        name: item.name,
        dose: item.dose,
        frequency: item.frequency,
        duration: item.duration,
        instructions: item.instructions,
      }));
      const res = await api.savePrescription({ case_id: caseId, notes, items: payload });
      if (res.success) {
        setSaved(true);
        toast({ title: "Prescription Saved", description: `Prescription #${res.prescription_id} saved successfully.` });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
    setSaving(false);
  };

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 backdrop-blur-md p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <motion.div
        className="bg-white rounded-[1.25rem] border shadow-2xl w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden transform-gpu"
        initial={{ opacity: 0, y: 24, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 12, scale: 0.98 }}
        transition={{ type: "spring", stiffness: 260, damping: 24, mass: 0.9 }}
      >
        <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-4 border-b border-slate-200 bg-white">
          <div className="flex items-start gap-4">
            <div className="w-16 h-16 rounded-xl bg-medical-highlight flex items-center justify-center border border-slate-200">
              <Pill className="w-8 h-8 text-accent" />
            </div>
            <div className="space-y-1">
              <h2 className="text-2xl font-bold text-slate-900">Treatment Plan</h2>
              <p className="text-sm text-slate-600">{disease.replace(/_/g, " ")} • {severity} • Score {severityScore.toFixed(1)}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-slate-100 text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 px-5 py-4 border-b border-slate-200 bg-slate-50 text-sm">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Doctor</p>
            <p className="font-semibold text-slate-900">Dr. {doctorName}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Patient</p>
            <p className="font-semibold text-slate-900">{patientName}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Date</p>
            <p className="font-semibold text-slate-900">{new Date().toLocaleDateString()}</p>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 hide-scrollbar bg-[#fcfcfb]">
          {loading ? (
            <div className="text-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-accent mx-auto mb-2" />
              <p className="text-muted-foreground text-sm">Generating treatment suggestions...</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Diagnosis</p>
                  <p className="text-lg font-semibold text-slate-900 capitalize">{disease.replace(/_/g, " ")}</p>
                  <p className="text-sm text-slate-600 mt-1">Severity: {severity} • Score: {severityScore.toFixed(1)}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Review Notes</p>
                  <p className="text-sm text-slate-600">Use the table below to confirm medicines, doses, duration, and instructions before saving.</p>
                </div>
              </div>

              {/* Medicine items */}
              <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                <div className="grid grid-cols-[2.2fr_1fr_1fr_1fr_0.8fr] gap-0 text-xs font-semibold uppercase tracking-wide text-slate-500 bg-slate-100 px-4 py-3 border-b border-slate-200">
                  <div>Medicine Name</div>
                  <div>Dose</div>
                  <div>Frequency</div>
                  <div>Duration</div>
                  <div className="text-right">Action</div>
                </div>
                <div className="divide-y divide-slate-200">
                {items.map((item, idx) => (
                  <div key={idx} className="grid grid-cols-1 lg:grid-cols-[2.2fr_1fr_1fr_1fr_0.8fr] gap-3 px-4 py-4 items-center">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-accent w-6">{idx + 1}.</span>
                      <Input placeholder="Medicine name" value={item.name} onChange={(e) => updateItem(idx, "name", e.target.value)} className="text-sm h-9 bg-slate-50" />
                    </div>
                    <Input placeholder="Dose" value={item.dose} onChange={(e) => updateItem(idx, "dose", e.target.value)} className="text-sm h-9 bg-slate-50" />
                    <Input placeholder="Frequency" value={item.frequency} onChange={(e) => updateItem(idx, "frequency", e.target.value)} className="text-sm h-9 bg-slate-50" />
                    <Input placeholder="Duration" value={item.duration} onChange={(e) => updateItem(idx, "duration", e.target.value)} className="text-sm h-9 bg-slate-50" />
                    <div className="flex justify-end">
                      <Button variant="ghost" size="sm" onClick={() => removeItem(idx)} className="h-9 px-3 text-destructive hover:text-destructive gap-1">
                        <Trash2 className="w-3.5 h-3.5" /> Remove
                      </Button>
                    </div>
                  </div>
                ))}
                </div>
              </div>

              <div className="border rounded-xl bg-white p-4 shadow-sm">
                <Label className="text-sm font-medium text-slate-700">Special Instructions</Label>
                <Textarea placeholder="Additional instructions for the patient..." value={items[0]?.instructions || ""} onChange={(e) => setItems((prev) => prev.map((item, idx) => idx === 0 ? { ...item, instructions: e.target.value } : item))} className="mt-2 bg-slate-50 min-h-24" rows={4} />
              </div>

              {/* Add medicine actions */}
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={addBlankItem} className="gap-1">
                  <Plus className="w-3 h-3" /> Add Medicine
                </Button>
                <Button variant="outline" size="sm" onClick={() => setShowSearch(!showSearch)} className="gap-1">
                  <Search className="w-3 h-3" /> Search Database
                </Button>
              </div>

              {/* Medicine search */}
              {showSearch && (
                <div className="border rounded-xl p-3 bg-slate-50">
                  <Input placeholder="Search medicines..." value={searchQuery} onChange={(e) => handleSearch(e.target.value)} className="mb-2" />
                  <div className="max-h-32 overflow-y-auto space-y-1 hide-scrollbar">
                    {searchResults.map((m) => (
                      <button key={m.id} onClick={() => addFromSearch(m)} className="w-full text-left p-2 rounded hover:bg-card text-sm flex items-center justify-between">
                        <span>{m.name} ({m.form} {m.strength})</span>
                        <Plus className="w-3 h-3 text-accent" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div>
                <Label className="text-sm">Clinical Notes</Label>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Additional notes for this prescription..." className="mt-1 bg-white" rows={3} />
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 flex justify-end gap-3 bg-white">
          <Button variant="outline" onClick={onClose}>Close</Button>
          {!saved ? (
            <Button onClick={handleSave} disabled={saving || loading} className="medical-gradient text-primary-foreground gap-2">
              {saving ? <><Loader2 className="w-4 h-4 animate-spin" />Saving...</> : <><Save className="w-4 h-4" />Save Prescription</>}
            </Button>
          ) : (
            <Button disabled className="bg-success text-success-foreground gap-2">
              <Check className="w-4 h-4" /> Saved
            </Button>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
