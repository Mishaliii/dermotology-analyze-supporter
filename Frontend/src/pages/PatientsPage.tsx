import { useState, useEffect, useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, Patient, DoctorCase } from "@/lib/api";
import AppLayout from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Search, Plus, User, ChevronRight } from "lucide-react";

type DateMode = "today" | "yesterday" | "custom";
const PATIENT_FILTERS_STORAGE_KEY = "patients_filters_v1";

function getSavedPatientFilters(): { dateMode: DateMode; selectedDate: string; search: string } {
  try {
    const raw = sessionStorage.getItem(PATIENT_FILTERS_STORAGE_KEY);
    if (!raw) {
      return { dateMode: "today", selectedDate: toYmd(new Date()), search: "" };
    }

    const parsed = JSON.parse(raw);
    const mode = parsed?.dateMode;
    const dateMode: DateMode = mode === "today" || mode === "yesterday" || mode === "custom" ? mode : "today";
    const selectedDate = typeof parsed?.selectedDate === "string" && parsed.selectedDate ? parsed.selectedDate : toYmd(new Date());
    const search = typeof parsed?.search === "string" ? parsed.search : "";
    return { dateMode, selectedDate, search };
  } catch {
    return { dateMode: "today", selectedDate: toYmd(new Date()), search: "" };
  }
}

function toYmd(date: Date): string {
  const y = date.getFullYear();
  const m = `${date.getMonth() + 1}`.padStart(2, "0");
  const d = `${date.getDate()}`.padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function parseCaseDate(value: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return toYmd(parsed);
}

function groupPatientsByDoctor(items: Patient[]): Array<{ doctor: string; patients: Patient[] }> {
  const map = new Map<string, Patient[]>();
  items.forEach((p) => {
    const key = (p.doctor_name || "Unassigned").trim() || "Unassigned";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(p);
  });
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([doctor, patients]) => ({ doctor, patients }));
}

export default function PatientsPage() {
  const { doctor, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  const [patients, setPatients] = useState<Patient[]>([]);
  const [cases, setCases] = useState<DoctorCase[]>([]);
  const savedFilters = getSavedPatientFilters();
  const [search, setSearch] = useState(savedFilters.search);
  const [loading, setLoading] = useState(true);

  const [dateMode, setDateMode] = useState<DateMode>(savedFilters.dateMode);
  const [selectedDate, setSelectedDate] = useState<string>(savedFilters.selectedDate);

  const [showNew, setShowNew] = useState(Boolean((location.state as any)?.openNewPatient));
  const [newPatient, setNewPatient] = useState({ name: "", age: "", gender: "Male", contact: "" });
  const [saving, setSaving] = useState(false);

  const applyFilters = (payload: any) => {
    if (!payload) return;

    const nextMode = payload.dateMode;
    if (nextMode === "today" || nextMode === "yesterday" || nextMode === "custom") {
      setDateMode(nextMode);
    }

    if (typeof payload.selectedDate === "string" && payload.selectedDate) {
      setSelectedDate(payload.selectedDate);
    }

    if (typeof payload.search === "string") {
      setSearch(payload.search);
    }
  };

  const fetchData = async () => {
    if (!doctor) return;
    setLoading(true);
    try {
      const [pRes, cRes] = await Promise.all([
        api.searchPatients(doctor.id, ""),
        api.getDoctorCases(doctor.id),
      ]);
      if (pRes.success) setPatients(pRes.patients);
      if (cRes.success) setCases(cRes.cases);
    } catch {
      // Keep UI available.
    }
    setLoading(false);
  };

  useEffect(() => {
    void fetchData();
  }, [doctor]);

  useEffect(() => {
    if ((location.state as any)?.openNewPatient) {
      setShowNew(true);
      navigate("/patients", { replace: true, state: null });
    }
  }, [location.state, navigate]);

  useEffect(() => {
    const restore = (location.state as any)?.returnContext;
    if (!restore || isAdmin) return;
    applyFilters(restore);
  }, [location.state, isAdmin]);

  useEffect(() => {
    if (isAdmin) return;
    if (dateMode === "today") {
      setSelectedDate(toYmd(new Date()));
      return;
    }
    if (dateMode === "yesterday") {
      const d = new Date();
      d.setDate(d.getDate() - 1);
      setSelectedDate(toYmd(d));
    }
  }, [dateMode, isAdmin]);

  useEffect(() => {
    if (isAdmin) return;
    try {
      sessionStorage.setItem(
        PATIENT_FILTERS_STORAGE_KEY,
        JSON.stringify({ dateMode, selectedDate, search }),
      );
    } catch {
      // Ignore storage write errors.
    }
  }, [dateMode, selectedDate, search, isAdmin]);

  const visiblePatients = useMemo(() => {
    const q = search.toLowerCase();

    if (isAdmin) {
      return patients.filter((p) => p.name.toLowerCase().includes(q));
    }

    const filteredCases = cases.filter((c) => parseCaseDate(c.date) === selectedDate);
    const patientIdsInDate = new Set(filteredCases.map((c) => Number(c.patient_id || 0)).filter((id) => id > 0));

    return patients
      .filter((p) => patientIdsInDate.has(p.id))
      .filter((p) => p.name.toLowerCase().includes(q));
  }, [isAdmin, patients, cases, selectedDate, search]);

  const groupedPatients = useMemo(() => groupPatientsByDoctor(visiblePatients), [visiblePatients]);

  const handleCreate = async () => {
    if (!doctor || !newPatient.name || !newPatient.age) {
      toast({ title: "Missing Info", description: "Name and age are required.", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      const res = await api.createPatient({
        name: newPatient.name,
        age: parseInt(newPatient.age),
        gender: newPatient.gender,
        contact: newPatient.contact || undefined,
        doctor_id: doctor.id,
      });
      if (res.success) {
        toast({ title: "Patient Created" });
        setShowNew(false);
        setNewPatient({ name: "", age: "", gender: "Male", contact: "" });
        await fetchData();
      } else if ("duplicate" in res && res.duplicate && "patient_id" in res && res.patient_id) {
        toast({
          title: "Possible Duplicate",
          description: "This patient already exists for this doctor. Opening existing profile.",
        });
        setShowNew(false);
        navigate(`/patient/${res.patient_id}`);
      } else {
        const errorMessage = "error" in res ? res.error : undefined;
        toast({
          title: "Unable to Create Patient",
          description: errorMessage || "Please verify patient details and try again.",
          variant: "destructive",
        });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
    setSaving(false);
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Patients</h1>
            <p className="text-sm text-muted-foreground">
              {isAdmin ? "Grouped by doctor" : `Showing patients with cases on ${selectedDate}`}
            </p>
          </div>
          {!isAdmin && (
            <Button onClick={() => setShowNew(true)} className="medical-gradient text-primary-foreground gap-2">
              <Plus className="w-4 h-4" /> Add Patient
            </Button>
          )}
        </div>

        {!isAdmin && (
          <div className="medical-card p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant={dateMode === "today" ? "secondary" : "outline"} onClick={() => setDateMode("today")}>Today</Button>
              <Button size="sm" variant={dateMode === "yesterday" ? "secondary" : "outline"} onClick={() => setDateMode("yesterday")}>Yesterday</Button>
              <input
                type="date"
                max={toYmd(new Date())}
                value={selectedDate}
                onFocus={() => setDateMode("custom")}
                onChange={(e) => {
                  const today = toYmd(new Date());
                  const nextDate = e.target.value > today ? today : e.target.value;
                  setDateMode("custom");
                  setSelectedDate(nextDate);
                }}
                aria-label="Select date"
                className={`h-9 rounded-md border px-3 text-sm transition-colors ${
                  dateMode === "custom"
                    ? "bg-secondary/80 text-secondary-foreground border-transparent"
                    : "border-input bg-background/80"
                }`}
              />
            </div>
          </div>
        )}

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder={isAdmin ? "Search patients..." : "Search patients in selected date..."}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 max-w-md"
          />
        </div>

        <div className="space-y-5">
          {visiblePatients.length > 0 && isAdmin && groupedPatients.map((group) => (
            <div key={group.doctor} className="space-y-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Doctor: {group.doctor}</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {group.patients.map((p) => (
                  <div key={p.id} onClick={() => navigate(`/patient/${p.id}`, { state: { fromPatients: true, returnContext: { dateMode, selectedDate, search } } })} className="medical-card p-4 cursor-pointer group">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-full bg-secondary group-hover:bg-accent/10 transition-colors">
                        <User className="w-5 h-5 text-secondary-foreground" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-foreground truncate">{p.name}</p>
                        <p className="text-sm text-muted-foreground">{p.age} years • {p.gender}</p>
                        {p.contact && <p className="text-xs text-muted-foreground mt-0.5">{p.contact}</p>}
                      </div>
                      <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-accent transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {!isAdmin && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {visiblePatients.map((p) => (
                <div key={p.id} onClick={() => navigate(`/patient/${p.id}`, { state: { fromPatients: true, returnContext: { dateMode, selectedDate, search } } })} className="medical-card p-4 cursor-pointer group">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-full bg-secondary group-hover:bg-accent/10 transition-colors">
                      <User className="w-5 h-5 text-secondary-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-foreground truncate">{p.name}</p>
                      <p className="text-sm text-muted-foreground">{p.age} years • {p.gender}</p>
                      {p.contact && <p className="text-xs text-muted-foreground mt-0.5">{p.contact}</p>}
                    </div>
                    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-accent transition-colors" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && visiblePatients.length === 0 && (
            <div className="text-center py-12">
              <User className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-muted-foreground">{isAdmin ? "No patients found" : "No patients found for selected date"}</p>
              {!isAdmin && (
                <Button variant="outline" onClick={() => setShowNew(true)} className="mt-3 gap-2">
                  <Plus className="w-4 h-4" /> Add Patient
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      <Dialog open={!isAdmin && showNew} onOpenChange={setShowNew}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Patient</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div><Label>Full Name *</Label><Input value={newPatient.name} onChange={(e) => setNewPatient({ ...newPatient, name: e.target.value })} className="mt-1" /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Age *</Label><Input type="number" value={newPatient.age} onChange={(e) => setNewPatient({ ...newPatient, age: e.target.value })} className="mt-1" /></div>
              <div>
                <Label>Gender</Label>
                <Select value={newPatient.gender} onValueChange={(v) => setNewPatient({ ...newPatient, gender: v })}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Male">Male</SelectItem>
                    <SelectItem value="Female">Female</SelectItem>
                    <SelectItem value="Other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div><Label>Contact</Label><Input value={newPatient.contact} onChange={(e) => setNewPatient({ ...newPatient, contact: e.target.value })} className="mt-1" /></div>
            <Button onClick={handleCreate} disabled={saving} className="w-full medical-gradient text-primary-foreground">
              {saving ? "Creating..." : "Create Patient"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
