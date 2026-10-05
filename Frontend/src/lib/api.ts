const API_BASE = ((import.meta as any).env?.VITE_API_BASE_URL as string) || "http://localhost:8000";

function getCurrentDoctorId(): number {
  try {
    const raw = localStorage.getItem("derm_doctor");
    if (!raw) return 0;
    const parsed = JSON.parse(raw);
    return Number(parsed?.id || 0);
  } catch {
    return 0;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || data.detail || "Request failed");
  return data;
}

function normalizeDiseaseMatches(clsKnn: any): DiseaseMatch[] {
  if (!clsKnn) return [];

  if (Array.isArray(clsKnn)) {
    return clsKnn.map((item) => ({
      disease: item?.disease || "Unknown",
      confidence: Number(item?.confidence ?? 0),
      similar_images: item?.similar_images || [],
    }));
  }

  const similarCases = Array.isArray(clsKnn.similar_cases) ? clsKnn.similar_cases : [];
  const byDisease = new Map<string, number>();

  similarCases.forEach((c: any) => {
    const disease = c?.disease || "Unknown";
    const similarity = Number(c?.similarity ?? 0);
    const prev = byDisease.get(disease) ?? 0;
    if (similarity > prev) byDisease.set(disease, similarity);
  });

  return Array.from(byDisease.entries())
    .map(([disease, confidence]) => ({ disease, confidence }))
    .sort((a, b) => b.confidence - a.confidence);
}

function encodeClinicProfile(specialization: string, district?: string, address?: string): string {
  const spec = (specialization || "").trim();
  const dist = (district || "").trim();
  const addr = (address || "").trim();
  const parts = [spec || "General"];
  if (dist) parts.push(`District: ${dist}`);
  if (addr) parts.push(`Address: ${addr}`);
  return parts.join(" | ");
}

function formRequest<T>(path: string, body: FormData): Promise<T> {
  return fetch(`${API_BASE}${path}`, { method: "POST", body }).then(async (r) => {
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "Request failed");
    return d;
  });
}

// Backend connection enabled
const USE_MOCK = false;

// Auth
export const realApi = {
  signup: (data: { name: string; email: string; password: string; specialization: string; license_number: string; district?: string; address?: string }) =>
    request<{ success: boolean; doctor_id?: number; error?: string; pending?: boolean }>("/signup", {
      method: "POST",
      body: JSON.stringify({
        name: data.name,
        email: data.email,
        password: data.password,
        license_number: data.license_number,
        clinic_name: encodeClinicProfile(data.specialization, data.district, data.address),
      }),
    }),

  login: (email: string, password: string) =>
    request<{ success: boolean; doctor_id?: number; doctor_name?: string; is_admin?: boolean; approved?: boolean; error?: string }>("/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  // Patients
  searchPatients: (doctorId: number, query: string) =>
    request<{ success: boolean; patients: Patient[] }>(`/patients/search?doctor_id=${doctorId}&q=${encodeURIComponent(query)}`),

  createPatient: (data: { name: string; age: number; gender: string; contact?: string; doctor_id: number }) =>
    request<{ success: boolean; patient_id?: number; duplicate?: boolean; error?: string }>("/patients/create", {
      method: "POST",
      body: JSON.stringify({
        doctor_id: data.doctor_id,
        name: data.name,
        age: data.age,
        gender: data.gender,
        medical_history: data.contact || "",
      }),
    }),

  getPatientHistory: (patientId: number) =>
    request<{ success: boolean; history: CaseHistory[] }>(`/patients/history?patient_id=${patientId}&doctor_id=${getCurrentDoctorId()}`),

  // Analysis
  getModelsHealth: () =>
    request<{ success: boolean; ready: boolean; loading: boolean; error?: string }>("/health/models"),

  analyzeImage: async (file: File): Promise<AnalysisResult> => {
    const fd = new FormData();
    fd.append("file", file);
    const raw = await formRequest<any>("/analyze", fd);
    return {
      success: !raw?.error,
      loading: Boolean(raw?.loading),
      error: raw?.error || undefined,
      cls_knn: normalizeDiseaseMatches(raw?.cls_knn),
      uploaded_image: raw?.uploaded_image || "",
      analyzed_image_path: raw?.analyzed_image_path || raw?.uploaded_image || "",
      analysis_decision: raw?.analysis_decision,
    };
  },

  scoreDisease: (imagePath: string, disease: string) =>
    request<ScoringResult>("/score_disease", {
      method: "POST",
      body: JSON.stringify({ image_path: imagePath, disease_name: disease }),
    }),

  // Cases & Prescription
  createCase: (data: CreateCasePayload) =>
    request<{ success: boolean; case_id?: number; doctor_name?: string; patient_name?: string }>("/create_case", { method: "POST", body: JSON.stringify(data) }),

  generatePrescription: (_caseId: number, disease: string, severityScore: number | string) =>
    request<{ success: boolean; suggestions?: MedicineSuggestion[] }>("/generate_prescription", {
      method: "POST",
      body: JSON.stringify({
        disease_name: disease,
        severity_score: Number(severityScore) || 0,
      }),
    }),

  savePrescription: (data: { case_id: number; notes: string; items: PrescriptionItem[] }) =>
    request<{ success: boolean; prescription_id?: number; error?: string }>("/save_prescription", {
      method: "POST",
      body: JSON.stringify({
        doctor_id: getCurrentDoctorId(),
        case_id: data.case_id,
        notes: data.notes,
        items: data.items,
      }),
    }),

  searchMedicines: async (query: string, disease?: string) => {
    const items = await request<Medicine[]>(`/medicines?search=${encodeURIComponent(query)}${disease ? `&disease=${encodeURIComponent(disease)}` : ""}`);
    return { success: true, medicines: items };
  },

  addMedicine: (data: { name: string; form: string; strength: string }) =>
    request<{ success: boolean; medicine_id?: number }>("/medicine/add", {
      method: "POST",
      body: JSON.stringify({
        name: data.name,
        generic_name: "",
        category: "Custom",
        form: data.form,
        strength: data.strength,
      }),
    }),

  getCasePrescription: async (caseId: number): Promise<PrescriptionView> => {
    const raw = await request<any>(`/case/${caseId}/prescription?doctor_id=${getCurrentDoctorId()}`);
    if (!raw?.success || !raw?.prescription) {
      return { success: false, prescription: null as any };
    }

    const p = raw.prescription;
    return {
      success: true,
      prescription: {
        doctor: p.doctor_name || "",
        patient: p.patient_age ? `${p.patient_name} (${p.patient_age} y/o)` : (p.patient_name || ""),
        diagnosis: p.diagnosis || "",
        date: p.date || "",
        notes: p.notes || "",
        items: (p.items || []).map((i: any) => ({
          name: i.medicine || "",
          dose: i.dosage || "",
          frequency: i.frequency || "",
          duration: i.duration || "",
          instructions: i.instructions || "",
        })),
      },
    };
  },

  getDoctorCases: async (doctorId: number) => {
    const rows = await request<any[]>(`/doctor_cases/${doctorId}`);
    const cases: DoctorCase[] = (rows || []).map((r: any) => ({
      case_id: r.case_id ?? r.id,
      patient_id: Number(r.patient_id || 0),
      patient_name: r.patient_name || "Unknown",
      disease: r.disease || "Unknown",
      severity: r.severity || "N/A",
      date: r.date || "",
      has_prescription: Boolean(r.has_prescription),
      doctor_name: r.doctor_name || "",
      image_path: r.image_path || "",
    }));
    return { success: true, cases };
  },

  getTreatmentSuggestions: (disease: string, severity: string) =>
    request<{ success: boolean; suggestions: MedicineSuggestion[] }>(`/treatment_suggestions?disease=${encodeURIComponent(disease)}&severity=${encodeURIComponent(String(Number(severity) || 0))}`),

  // Admin
  getPendingDoctors: async () => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false, doctors: [] as PendingDoctor[] };
    return request<{ success: boolean; doctors: PendingDoctor[]; error?: string }>(
      `/admin/pending_doctors?admin_doctor_id=${adminDoctorId}`
    );
  },

  approveDoctor: async (doctorId: number) => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false };
    return request<{ success: boolean; error?: string }>("/admin/approve_doctor", {
      method: "POST",
      body: JSON.stringify({ admin_doctor_id: adminDoctorId, doctor_id: doctorId }),
    });
  },

  rejectDoctor: async (doctorId: number) => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false };
    return request<{ success: boolean; error?: string }>("/admin/reject_doctor", {
      method: "POST",
      body: JSON.stringify({ admin_doctor_id: adminDoctorId, doctor_id: doctorId }),
    });
  },

  getAllDoctors: async () => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false, doctors: [] as DoctorSummary[] };
    return request<{ success: boolean; doctors: DoctorSummary[]; error?: string }>(
      `/admin/doctors?admin_doctor_id=${adminDoctorId}`
    );
  },

  getDoctorPatientsByAdmin: async (doctorId: number) => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false, patients: [] as Patient[] };
    return request<{ success: boolean; patients: Patient[]; error?: string }>(
      `/admin/doctors/${doctorId}/patients?admin_doctor_id=${adminDoctorId}`
    );
  },

  createDoctorByAdmin: async (data: {
    name: string;
    email: string;
    password: string;
    license_number?: string;
    clinic_name?: string;
    is_admin?: boolean;
    approved?: boolean;
  }) => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false };
    return request<{ success: boolean; doctor_id?: number; error?: string }>("/admin/doctors", {
      method: "POST",
      body: JSON.stringify({
        admin_doctor_id: adminDoctorId,
        name: data.name,
        email: data.email,
        password: data.password,
        license_number: data.license_number || "",
        clinic_name: data.clinic_name || "",
        is_admin: Boolean(data.is_admin),
        approved: data.approved !== false,
      }),
    });
  },

  updateDoctorByAdmin: async (
    doctorId: number,
    data: {
      name: string;
      email: string;
      license_number?: string;
      clinic_name?: string;
      is_admin?: boolean;
      approved?: boolean;
      password?: string;
    }
  ) => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false };
    return request<{ success: boolean; error?: string }>(`/admin/doctors/${doctorId}`, {
      method: "PUT",
      body: JSON.stringify({
        admin_doctor_id: adminDoctorId,
        name: data.name,
        email: data.email,
        license_number: data.license_number || "",
        clinic_name: data.clinic_name || "",
        is_admin: Boolean(data.is_admin),
        approved: data.approved !== false,
        password: data.password || "",
      }),
    });
  },

  deleteDoctorByAdmin: async (doctorId: number) => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false };
    return request<{ success: boolean; error?: string }>(
      `/admin/doctors/${doctorId}?admin_doctor_id=${adminDoctorId}`,
      { method: "DELETE" }
    );
  },

  getReviewQueue: async () => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false, items: [] as ReviewQueueItem[] };
    return request<{ success: boolean; items: ReviewQueueItem[]; error?: string }>(
      `/admin/review_queue?admin_doctor_id=${adminDoctorId}`
    );
  },

  approveReviewImage: async (reviewId: number, diseaseName: string) => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false };
    return request<{ success: boolean; saved_path?: string; error?: string }>(
      `/admin/review_queue/${reviewId}/approve`,
      {
        method: "POST",
        body: JSON.stringify({ admin_doctor_id: adminDoctorId, disease_name: diseaseName }),
      }
    );
  },

  rejectReviewImage: async (reviewId: number, notes = "") => {
    const adminDoctorId = getCurrentDoctorId();
    if (!adminDoctorId) return { success: false };
    return request<{ success: boolean; error?: string }>(
      `/admin/review_queue/${reviewId}/reject`,
      {
        method: "POST",
        body: JSON.stringify({ admin_doctor_id: adminDoctorId, notes }),
      }
    );
  },
};

import { mockApi } from "./mock-data";
export const api = USE_MOCK ? mockApi : realApi;

// Types
export interface Patient {
  id: number;
  name: string;
  age: number;
  gender: string;
  contact?: string;
  doctor_name?: string;
}

export interface CaseHistory {
  case_id: number;
  disease: string;
  severity: string;
  date: string;
  has_prescription: boolean;
  ai_confidence?: number;
  image_path?: string;
}

export interface AnalysisResult {
  success: boolean;
  loading?: boolean;
  error?: string;
  cls_knn: DiseaseMatch[];
  uploaded_image: string;
  analyzed_image_path: string;
  analysis_decision?: {
    candidate_status?: "likely_disease" | "uncertain" | "no_disease_candidate";
    decision_confidence?: number;
    reject_reasons?: string[];
    signals?: {
      top1_similarity?: number;
      top2_similarity?: number;
      avg_top3_similarity?: number;
      top1_top2_gap?: number;
    };
  };
}

export interface DiseaseMatch {
  disease: string;
  confidence: number;
  similar_images?: string[];
}

export interface ScoringResult {
  success: boolean;
  loading?: boolean;
  error?: string;
  severity_score?: number;
  metrics?: Record<string, number>;
  confidence_score?: number;
  quality_flags?: Record<string, boolean>;
}

export interface CreateCasePayload {
  doctor_id: number;
  patient_id: number;
  image_path: string;
  predicted_disease_name: string;
  confirmed_disease_name: string;
  severity_json: { raw_text: string; numeric: number };
  ai_confidence: number;
}

export interface MedicineSuggestion {
  medicine_id: number;
  name: string;
  form: string;
  line_of_therapy?: string;
  strength: string;
  dose: string;
  duration: string;
}

export interface PrescriptionItem {
  medicine_id?: number;
  name?: string;
  dose: string;
  frequency: string;
  duration: string;
  instructions: string;
}

export interface Medicine {
  id: number;
  name: string;
  form: string;
  strength: string;
}

export interface PrescriptionView {
  success: boolean;
  prescription: {
    doctor: string;
    patient: string;
    diagnosis: string;
    date: string;
    notes: string;
    items: Array<{ name: string; dose: string; frequency: string; duration: string; instructions: string }>;
  } | null;
}

export interface DoctorCase {
  case_id: number;
  patient_id?: number;
  patient_name: string;
  disease: string;
  severity: string;
  date: string;
  has_prescription: boolean;
  doctor_name?: string;
  image_path?: string;
}

export interface PendingDoctor {
  id: number;
  name: string;
  email: string;
  specialization: string;
  license_number: string;
  created_at: string;
}

export interface DoctorSummary {
  id: number;
  name: string;
  email: string;
  license_number: string;
  clinic_name: string;
  is_admin: boolean;
  approved: boolean;
  created_at: string;
}

export interface ReviewQueueItem {
  id: number;
  image_path: string;
  suggested_disease: string;
  confidence: number;
  reason: string;
  status: string;
  confirmed_disease?: string;
  resolved_path?: string;
  notes?: string;
  created_at: string;
  reviewed_at?: string;
  image_hash?: string;
  is_existing?: boolean;
}
