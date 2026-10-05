import { useState, useEffect } from "react";
import { api, PendingDoctor, DoctorSummary, ReviewQueueItem } from "@/lib/api";
import AppLayout from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Shield, Check, X, User, Mail, Award, Plus, Pencil, Trash2, Save } from "lucide-react";
import { useNavigate } from "react-router-dom";

function parseClinicProfile(clinicName?: string): { specialization: string; district: string; address: string } {
  const raw = (clinicName || "").trim();
  if (!raw) return { specialization: "", district: "", address: "" };
  const parts = raw.split("|").map((part) => part.trim());
  let specialization = parts[0] || "";
  let district = "";
  let address = "";

  parts.slice(1).forEach((part) => {
    const lower = part.toLowerCase();
    if (lower.startsWith("district:")) district = part.split(":").slice(1).join(":").trim();
    if (lower.startsWith("address:")) address = part.split(":").slice(1).join(":").trim();
  });

  return { specialization, district, address };
}

function encodeClinicProfile(specialization: string, district: string, address: string): string {
  const parts = [(specialization || "").trim() || "General"];
  if ((district || "").trim()) parts.push(`District: ${district.trim()}`);
  if ((address || "").trim()) parts.push(`Address: ${address.trim()}`);
  return parts.join(" | ");
}

export default function AdminDashboard() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [pending, setPending] = useState<PendingDoctor[]>([]);
  const [doctors, setDoctors] = useState<DoctorSummary[]>([]);
  const [doctorPatients, setDoctorPatients] = useState<any[]>([]);
  const [selectedDoctorId, setSelectedDoctorId] = useState<number | null>(null);
  const [reviewQueue, setReviewQueue] = useState<ReviewQueueItem[]>([]);
  const [reviewDisease, setReviewDisease] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const [newDoctor, setNewDoctor] = useState({
    name: "",
    email: "",
    password: "",
    license_number: "",
    specialization: "",
    district: "",
    address: "",
    is_admin: false,
    approved: true,
  });

  const [editDoctor, setEditDoctor] = useState({
    name: "",
    email: "",
    password: "",
    license_number: "",
    specialization: "",
    district: "",
    address: "",
    is_admin: false,
    approved: true,
  });

  const fetchPending = () => {
    api.getPendingDoctors()
      .then((res) => { if (res.success) setPending(res.doctors); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  const fetchDoctors = () => {
    api.getAllDoctors()
      .then((res) => { if (res.success) setDoctors(res.doctors); })
      .catch(() => {});
  };

  const fetchDoctorPatients = (doctorId: number) => {
    setSelectedDoctorId(doctorId);
    api.getDoctorPatientsByAdmin(doctorId)
      .then((res) => {
        if (res.success) setDoctorPatients(res.patients || []);
        else setDoctorPatients([]);
      })
      .catch(() => setDoctorPatients([]));
  };

  const fetchReviewQueue = () => {
    api.getReviewQueue()
      .then((res) => {
        if (res.success) {
          const rank = (item: ReviewQueueItem) => {
            if (item.status === "pending" && !item.is_existing) return 0;
            if (item.status === "known" || item.is_existing) return 1;
            if (item.status === "approved") return 2;
            if (item.status === "rejected") return 3;
            return 4;
          };

          const sortedItems = [...res.items].sort((a, b) => {
            const byRank = rank(a) - rank(b);
            if (byRank !== 0) return byRank;
            return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
          });

          setReviewQueue(sortedItems);
          const next: Record<number, string> = {};
          sortedItems.forEach((i) => {
            next[i.id] = i.suggested_disease || "";
          });
          setReviewDisease(next);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchPending();
    fetchDoctors();
    fetchReviewQueue();
  }, []);

  const handleAction = async (id: number, action: "approve" | "reject") => {
    try {
      const res = action === "approve" ? await api.approveDoctor(id) : await api.rejectDoctor(id);
      if (res.success) {
        toast({ title: `Doctor ${action === "approve" ? "Approved" : "Rejected"}` });
        fetchPending();
        fetchDoctors();
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  const handleCreateDoctor = async () => {
    if (!newDoctor.name || !newDoctor.email || !newDoctor.password) {
      toast({ title: "Missing fields", description: "Name, email, and password are required.", variant: "destructive" });
      return;
    }

    setSaving(true);
    try {
      const res = await api.createDoctorByAdmin({
        ...newDoctor,
        clinic_name: encodeClinicProfile(newDoctor.specialization, newDoctor.district, newDoctor.address),
      });
      if (res.success) {
        toast({ title: "Doctor created" });
        setNewDoctor({
          name: "",
          email: "",
          password: "",
          license_number: "",
          specialization: "",
          district: "",
          address: "",
          is_admin: false,
          approved: true,
        });
        fetchDoctors();
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
    setSaving(false);
  };

  const startEdit = (doc: DoctorSummary) => {
    const profile = parseClinicProfile(doc.clinic_name);
    setEditingId(doc.id);
    setEditDoctor({
      name: doc.name,
      email: doc.email,
      password: "",
      license_number: doc.license_number || "",
      specialization: profile.specialization,
      district: profile.district,
      address: profile.address,
      is_admin: doc.is_admin,
      approved: doc.approved,
    });
  };

  const handleUpdateDoctor = async (doctorId: number) => {
    setSaving(true);
    try {
      const res = await api.updateDoctorByAdmin(doctorId, {
        ...editDoctor,
        clinic_name: encodeClinicProfile(editDoctor.specialization, editDoctor.district, editDoctor.address),
      });
      if (res.success) {
        toast({ title: "Doctor updated" });
        setEditingId(null);
        fetchDoctors();
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
    setSaving(false);
  };

  const handleDeleteDoctor = async (doctorId: number) => {
    if (!confirm("Delete this doctor account?")) return;

    try {
      const res = await api.deleteDoctorByAdmin(doctorId);
      if (res.success) {
        toast({ title: "Doctor removed" });
        fetchDoctors();
        fetchPending();
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-medical-highlight">
            <Shield className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Admin Dashboard</h1>
            <p className="text-muted-foreground">Manage doctor registrations</p>
          </div>
        </div>

        <div className="medical-card p-5">
          <h2 className="text-lg font-semibold text-foreground mb-4">Pending Registrations ({pending.length})</h2>
          {loading ? (
            <p className="text-muted-foreground text-center py-8">Loading...</p>
          ) : pending.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">No pending registrations</p>
          ) : (
            <div className="space-y-3">
              {pending.map((doc) => (
                <div key={doc.id} className="border rounded-lg p-4 hover:bg-muted/50 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-full bg-secondary">
                        <User className="w-5 h-5 text-secondary-foreground" />
                      </div>
                      <div>
                        <p className="font-semibold text-foreground">{doc.name}</p>
                        <div className="flex flex-wrap items-center gap-3 mt-1 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{doc.email}</span>
                          <span className="flex items-center gap-1"><Award className="w-3 h-3" />{doc.specialization}</span>
                          <span>License: {doc.license_number}</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Applied: {doc.created_at}</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => handleAction(doc.id, "approve")} className="bg-success text-success-foreground hover:bg-success/90 gap-1">
                        <Check className="w-3 h-3" /> Approve
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleAction(doc.id, "reject")} className="text-destructive hover:text-destructive gap-1">
                        <X className="w-3 h-3" /> Reject
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="medical-card p-5 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Image Review Queue</h2>
          {reviewQueue.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recent images in review queue.</p>
          ) : (
            <div className="space-y-3">
              {reviewQueue.map((item) => (
                <div key={item.id} className="border rounded-lg p-3 space-y-2">
                  <div className="flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
                    <div>
                      <p className="text-sm font-medium text-foreground">Suggested: {item.suggested_disease || "Unknown"}</p>
                      <p className="text-xs text-muted-foreground">Confidence: {(item.confidence * 100).toFixed(1)}% • {item.reason}</p>
                      <p className={`text-xs font-semibold ${item.is_existing ? "text-green-600" : "text-amber-600"}`}>
                        {item.is_existing ? "Present in system" : "New image requires approval"}
                      </p>
                      <p className="text-xs text-muted-foreground break-all">Image: {item.image_path}</p>
                    </div>
                    {item.image_path && (
                      <a href={item.image_path} target="_blank" rel="noreferrer" className="text-sm text-accent underline">View Image</a>
                    )}
                  </div>
                  {!item.is_existing && item.status === "pending" && (
                    <div className="flex flex-col md:flex-row gap-2">
                    <Input
                      placeholder="Confirm disease folder name"
                      value={reviewDisease[item.id] || ""}
                      onChange={(e) => setReviewDisease((p) => ({ ...p, [item.id]: e.target.value }))}
                    />
                    <Button
                      size="sm"
                      onClick={async () => {
                        try {
                          const disease = (reviewDisease[item.id] || "").trim();
                          if (!disease) {
                            toast({ title: "Disease required", variant: "destructive" });
                            return;
                          }
                          const res = await api.approveReviewImage(item.id, disease);
                          if (res.success) {
                            toast({ title: "Image approved and routed" });
                            fetchReviewQueue();
                          }
                        } catch (e: any) {
                          toast({ title: "Error", description: e.message, variant: "destructive" });
                        }
                      }}
                    >
                      Approve & Save
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        try {
                          const res = await api.rejectReviewImage(item.id);
                          if (res.success) {
                            toast({ title: "Image review rejected" });
                            fetchReviewQueue();
                          }
                        } catch (e: any) {
                          toast({ title: "Error", description: e.message, variant: "destructive" });
                        }
                      }}
                    >
                      Reject
                    </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="medical-card p-5 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Doctors and Their Patients</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2 max-h-80 overflow-y-auto border rounded-lg p-3">
              {doctors.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => fetchDoctorPatients(doc.id)}
                  className={`w-full text-left p-2 rounded ${selectedDoctorId === doc.id ? "bg-medical-highlight border border-accent/30" : "hover:bg-muted"}`}
                >
                  <p className="text-sm font-medium text-foreground">{doc.name}{doc.is_admin ? " (Admin)" : ""}</p>
                  <p className="text-xs text-muted-foreground">{doc.email}</p>
                </button>
              ))}
            </div>
            <div className="space-y-2 max-h-80 overflow-y-auto border rounded-lg p-3">
              {selectedDoctorId == null ? (
                <p className="text-sm text-muted-foreground">Select a doctor to view patients.</p>
              ) : doctorPatients.length === 0 ? (
                <p className="text-sm text-muted-foreground">No patients mapped to this doctor.</p>
              ) : (
                doctorPatients.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => navigate(`/patient/${p.id}`, { state: { fromDashboard: true } })}
                    className="w-full text-left p-2 rounded hover:bg-muted"
                  >
                    <p className="text-sm font-medium text-foreground">{p.name}</p>
                    <p className="text-xs text-muted-foreground">{p.age}y • {p.gender}</p>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="medical-card p-5 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Doctor Management</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <Label>Name</Label>
              <Input value={newDoctor.name} onChange={(e) => setNewDoctor((p) => ({ ...p, name: e.target.value }))} />
            </div>
            <div>
              <Label>Email</Label>
              <Input value={newDoctor.email} onChange={(e) => setNewDoctor((p) => ({ ...p, email: e.target.value }))} />
            </div>
            <div>
              <Label>Password</Label>
              <Input type="password" value={newDoctor.password} onChange={(e) => setNewDoctor((p) => ({ ...p, password: e.target.value }))} />
            </div>
            <div>
              <Label>License</Label>
              <Input value={newDoctor.license_number} onChange={(e) => setNewDoctor((p) => ({ ...p, license_number: e.target.value }))} />
            </div>
            <div>
              <Label>Specialization</Label>
              <Input value={newDoctor.specialization} onChange={(e) => setNewDoctor((p) => ({ ...p, specialization: e.target.value }))} />
            </div>
            <div>
              <Label>District</Label>
              <Input value={newDoctor.district} onChange={(e) => setNewDoctor((p) => ({ ...p, district: e.target.value }))} />
            </div>
            <div>
              <Label>Address</Label>
              <Input value={newDoctor.address} onChange={(e) => setNewDoctor((p) => ({ ...p, address: e.target.value }))} />
            </div>
            <div className="flex items-end gap-4 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={newDoctor.is_admin} onChange={(e) => setNewDoctor((p) => ({ ...p, is_admin: e.target.checked }))} /> Admin</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={newDoctor.approved} onChange={(e) => setNewDoctor((p) => ({ ...p, approved: e.target.checked }))} /> Approved</label>
            </div>
          </div>

          <Button onClick={handleCreateDoctor} disabled={saving} className="gap-2">
            <Plus className="w-4 h-4" /> Add Doctor
          </Button>

          <div className="space-y-2">
            {doctors.map((doc) => (
              <div key={doc.id} className="border rounded-lg p-3">
                {editingId === doc.id ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <Input value={editDoctor.name} onChange={(e) => setEditDoctor((p) => ({ ...p, name: e.target.value }))} />
                    <Input value={editDoctor.email} onChange={(e) => setEditDoctor((p) => ({ ...p, email: e.target.value }))} />
                    <Input placeholder="New password (optional)" type="password" value={editDoctor.password} onChange={(e) => setEditDoctor((p) => ({ ...p, password: e.target.value }))} />
                    <Input value={editDoctor.license_number} onChange={(e) => setEditDoctor((p) => ({ ...p, license_number: e.target.value }))} />
                    <Input value={editDoctor.specialization} onChange={(e) => setEditDoctor((p) => ({ ...p, specialization: e.target.value }))} />
                    <Input value={editDoctor.district} onChange={(e) => setEditDoctor((p) => ({ ...p, district: e.target.value }))} />
                    <Input value={editDoctor.address} onChange={(e) => setEditDoctor((p) => ({ ...p, address: e.target.value }))} />
                    <div className="flex items-center gap-4 text-sm">
                      <label className="flex items-center gap-2"><input type="checkbox" checked={editDoctor.is_admin} onChange={(e) => setEditDoctor((p) => ({ ...p, is_admin: e.target.checked }))} /> Admin</label>
                      <label className="flex items-center gap-2"><input type="checkbox" checked={editDoctor.approved} onChange={(e) => setEditDoctor((p) => ({ ...p, approved: e.target.checked }))} /> Approved</label>
                    </div>
                    <div className="flex gap-2 md:col-span-3">
                      <Button size="sm" onClick={() => handleUpdateDoctor(doc.id)} className="gap-1"><Save className="w-3 h-3" /> Save</Button>
                      <Button size="sm" variant="outline" onClick={() => setEditingId(null)}>Cancel</Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      {(() => {
                        const profile = parseClinicProfile(doc.clinic_name);
                        return (
                          <>
                      <p className="font-medium text-foreground">{doc.name} {doc.is_admin && <span className="text-xs text-accent">(Admin)</span>}</p>
                      <p className="text-sm text-muted-foreground">{doc.email}</p>
                            <p className="text-xs text-muted-foreground">{profile.specialization || "-"} • {doc.license_number || "-"} • {doc.approved ? "Approved" : "Pending"}</p>
                            <p className="text-xs text-muted-foreground">{profile.district || "-"} • {profile.address || "-"}</p>
                          </>
                        );
                      })()}
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => startEdit(doc)} className="gap-1"><Pencil className="w-3 h-3" /> Edit</Button>
                      {doc.is_admin ? (
                        <Button size="sm" variant="outline" disabled className="gap-1">
                          Protected Admin
                        </Button>
                      ) : (
                        <Button size="sm" variant="outline" onClick={() => handleDeleteDoctor(doc.id)} className="gap-1 text-destructive"><Trash2 className="w-3 h-3" /> Remove</Button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
