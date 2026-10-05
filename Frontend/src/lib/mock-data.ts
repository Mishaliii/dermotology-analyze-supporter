import type { Patient, CaseHistory, DoctorCase, PendingDoctor, AnalysisResult, ScoringResult, MedicineSuggestion, PrescriptionView, Medicine } from "./api";

export const mockPatients: Patient[] = [
  { id: 1, name: "Sarah Johnson", age: 34, gender: "Female", contact: "+1-555-0101" },
  { id: 2, name: "Michael Chen", age: 45, gender: "Male", contact: "+1-555-0102" },
  { id: 3, name: "Emily Davis", age: 28, gender: "Female", contact: "+1-555-0103" },
  { id: 4, name: "Robert Wilson", age: 62, gender: "Male", contact: "+1-555-0104" },
  { id: 5, name: "Priya Sharma", age: 19, gender: "Female", contact: "+1-555-0105" },
];

export const mockCaseHistory: Record<number, CaseHistory[]> = {
  1: [
    { case_id: 101, disease: "Psoriasis", severity: "Moderate", date: "2026-03-15", has_prescription: true, ai_confidence: 0.89 },
    { case_id: 102, disease: "Eczema", severity: "Mild", date: "2026-02-20", has_prescription: true, ai_confidence: 0.92 },
  ],
  2: [
    { case_id: 103, disease: "Acne Vulgaris", severity: "Severe", date: "2026-03-28", has_prescription: true, ai_confidence: 0.85 },
  ],
  3: [
    { case_id: 104, disease: "Vitiligo", severity: "Moderate", date: "2026-03-10", has_prescription: false, ai_confidence: 0.78 },
  ],
  4: [],
  5: [
    { case_id: 105, disease: "Melanoma", severity: "High Risk", date: "2026-03-25", has_prescription: true, ai_confidence: 0.94 },
    { case_id: 106, disease: "Alopecia Areata", severity: "Mild (S1)", date: "2026-01-12", has_prescription: true, ai_confidence: 0.81 },
  ],
};

export const mockDoctorCases: DoctorCase[] = [
  { case_id: 101, patient_name: "Sarah Johnson", disease: "Psoriasis", severity: "Moderate", date: "2026-03-15", has_prescription: true },
  { case_id: 102, patient_name: "Sarah Johnson", disease: "Eczema", severity: "Mild", date: "2026-02-20", has_prescription: true },
  { case_id: 103, patient_name: "Michael Chen", disease: "Acne Vulgaris", severity: "Severe", date: "2026-03-28", has_prescription: true },
  { case_id: 104, patient_name: "Emily Davis", disease: "Vitiligo", severity: "Moderate", date: "2026-03-10", has_prescription: false },
  { case_id: 105, patient_name: "Priya Sharma", disease: "Melanoma", severity: "High Risk", date: "2026-03-25", has_prescription: true },
  { case_id: 106, patient_name: "Priya Sharma", disease: "Alopecia Areata", severity: "Mild (S1)", date: "2026-01-12", has_prescription: true },
];

export const mockPendingDoctors: PendingDoctor[] = [
  { id: 10, name: "Dr. Aisha Khan", email: "aisha.khan@hospital.com", specialization: "Dermatology", license_number: "MED-98765", created_at: "2026-03-30" },
  { id: 11, name: "Dr. James Lee", email: "james.lee@clinic.org", specialization: "Dermatopathology", license_number: "MED-54321", created_at: "2026-03-29" },
];

export const mockAnalysisResult: AnalysisResult = {
  success: true,
  cls_knn: [
    { disease: "Psoriasis", confidence: 0.87 },
    { disease: "Eczema", confidence: 0.72 },
    { disease: "Dermatitis", confidence: 0.58 },
    { disease: "Vitiligo", confidence: 0.31 },
    { disease: "Acne_Vulgaris", confidence: 0.22 },
  ],
  uploaded_image: "/temp/mock_upload.jpg",
  analyzed_image_path: "/temp/mock_analyzed.jpg",
};

export const mockScoringResult: ScoringResult = {
  success: true,
  severity_score: 14.2,
  confidence_score: 0.82,
  metrics: {
    head_erythema: 2, head_induration: 1, head_scaling: 2, head_area: 3,
    upper_limbs_erythema: 1, upper_limbs_induration: 1, upper_limbs_scaling: 1, upper_limbs_area: 2,
    trunk_erythema: 2, trunk_induration: 2, trunk_scaling: 1, trunk_area: 3,
    lower_limbs_erythema: 1, lower_limbs_induration: 1, lower_limbs_scaling: 1, lower_limbs_area: 2,
  },
  quality_flags: { blur: false, glare: false, underexposed: false },
};

export const mockMedicineSuggestions: MedicineSuggestion[] = [
  { medicine_id: 1, name: "Betamethasone Cream", form: "Topical", strength: "0.05%", dose: "Apply thin layer", duration: "2 weeks", line_of_therapy: "First-line" },
  { medicine_id: 2, name: "Calcipotriol Ointment", form: "Topical", strength: "50mcg/g", dose: "Apply twice daily", duration: "4 weeks", line_of_therapy: "First-line" },
  { medicine_id: 3, name: "Methotrexate", form: "Oral", strength: "2.5mg", dose: "7.5mg weekly", duration: "12 weeks", line_of_therapy: "Second-line" },
];

export const mockMedicines: Medicine[] = [
  { id: 1, name: "Betamethasone", form: "Cream", strength: "0.05%" },
  { id: 2, name: "Calcipotriol", form: "Ointment", strength: "50mcg/g" },
  { id: 3, name: "Methotrexate", form: "Tablet", strength: "2.5mg" },
  { id: 4, name: "Hydrocortisone", form: "Cream", strength: "1%" },
  { id: 5, name: "Tacrolimus", form: "Ointment", strength: "0.1%" },
  { id: 6, name: "Salicylic Acid", form: "Lotion", strength: "2%" },
  { id: 7, name: "Coal Tar", form: "Shampoo", strength: "5%" },
  { id: 8, name: "Adapalene", form: "Gel", strength: "0.1%" },
  { id: 9, name: "Clindamycin", form: "Gel", strength: "1%" },
  { id: 10, name: "Benzoyl Peroxide", form: "Wash", strength: "5%" },
];

export const mockPrescription: PrescriptionView = {
  success: true,
  prescription: {
    doctor: "Dr. Vishnu Kumar",
    patient: "Sarah Johnson (34F)",
    diagnosis: "Psoriasis — Moderate (PASI: 14.2)",
    date: "2026-03-15",
    notes: "Patient advised to avoid triggers. Follow-up in 4 weeks.",
    items: [
      { name: "Betamethasone Cream 0.05%", dose: "Apply thin layer", frequency: "Twice daily", duration: "2 weeks", instructions: "Apply to affected areas only" },
      { name: "Calcipotriol Ointment 50mcg/g", dose: "Apply once", frequency: "Once daily", duration: "4 weeks", instructions: "Apply after bathing" },
      { name: "Methotrexate 2.5mg", dose: "7.5mg", frequency: "Once weekly", duration: "12 weeks", instructions: "Take with folic acid supplement" },
    ],
  },
};

let nextPatientId = 100;
let nextCaseId = 200;
let nextPrescriptionId = 300;

export const mockApi = {
  signup: async (data: any) => {
    await delay(500);
    mockPendingDoctors.push({
      id: Math.floor(Math.random() * 1000) + 100,
      name: data.name,
      email: data.email,
      specialization: data.specialization,
      license_number: data.license_number,
      created_at: new Date().toISOString().split("T")[0],
    });
    return { success: true };
  },

  login: async (email: string, _password: string) => {
    await delay(500);
    if (email === "admin@admin.com") {
      return { success: true, doctor_id: 1, doctor_name: "Admin User", is_admin: true, approved: true };
    }
    return { success: true, doctor_id: 2, doctor_name: "Dr. Demo Doctor", is_admin: false, approved: true };
  },

  searchPatients: async (_doctorId: number, query: string) => {
    await delay(300);
    const filtered = query
      ? mockPatients.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
      : mockPatients;
    return { success: true, patients: filtered };
  },

  createPatient: async (data: any) => {
    await delay(400);
    const id = ++nextPatientId;
    mockPatients.push({ id, name: data.name, age: data.age, gender: data.gender, contact: data.contact });
    mockCaseHistory[id] = [];
    return { success: true, patient_id: id };
  },

  getPatientHistory: async (patientId: number) => {
    await delay(300);
    return { success: true, history: mockCaseHistory[patientId] || [] };
  },

  analyzeImage: async (_file: File) => {
    await delay(1500);
    return { ...mockAnalysisResult };
  },

  scoreDisease: async (_imagePath: string, _disease: string) => {
    await delay(800);
    return { ...mockScoringResult };
  },

  createCase: async (data: any) => {
    await delay(500);
    const id = ++nextCaseId;
    const patient = mockPatients.find((p) => p.id === data.patient_id);
    const newCase: DoctorCase = {
      case_id: id,
      patient_name: patient?.name || "Unknown",
      disease: data.confirmed_disease_name,
      severity: data.severity_json.raw_text,
      date: new Date().toISOString().split("T")[0],
      has_prescription: false,
    };
    mockDoctorCases.unshift(newCase);
    if (mockCaseHistory[data.patient_id]) {
      mockCaseHistory[data.patient_id].unshift({
        case_id: id,
        disease: data.confirmed_disease_name,
        severity: data.severity_json.raw_text,
        date: newCase.date,
        has_prescription: false,
        ai_confidence: data.ai_confidence,
      });
    }
    return { success: true, case_id: id, doctor_name: "Dr. Demo Doctor", patient_name: `${patient?.name || "Unknown"} (${patient?.age || ""}${patient?.gender?.[0] || ""})` };
  },

  generatePrescription: async (_caseId: number, _disease: string, _severity: string) => {
    await delay(700);
    return { success: true, suggestions: [...mockMedicineSuggestions] };
  },

  savePrescription: async (_data: any) => {
    await delay(500);
    const id = ++nextPrescriptionId;
    return { success: true, prescription_id: id };
  },

  searchMedicines: async (query: string, _disease?: string) => {
    await delay(300);
    const filtered = mockMedicines.filter((m) => m.name.toLowerCase().includes(query.toLowerCase()));
    return { success: true, medicines: filtered };
  },

  addMedicine: async (data: any) => {
    await delay(300);
    const id = mockMedicines.length + 1;
    mockMedicines.push({ id, name: data.name, form: data.form, strength: data.strength });
    return { success: true, medicine_id: id };
  },

  getCasePrescription: async (_caseId: number) => {
    await delay(400);
    return { ...mockPrescription };
  },

  getDoctorCases: async (_doctorId: number) => {
    await delay(300);
    return { success: true, cases: [...mockDoctorCases] };
  },

  getTreatmentSuggestions: async (_disease: string, _severity: string) => {
    await delay(500);
    return { success: true, suggestions: [...mockMedicineSuggestions] };
  },

  getPendingDoctors: async () => {
    await delay(400);
    return { success: true, doctors: [...mockPendingDoctors] };
  },

  approveDoctor: async (doctorId: number) => {
    await delay(400);
    const idx = mockPendingDoctors.findIndex((d) => d.id === doctorId);
    if (idx !== -1) mockPendingDoctors.splice(idx, 1);
    return { success: true };
  },

  rejectDoctor: async (doctorId: number) => {
    await delay(400);
    const idx = mockPendingDoctors.findIndex((d) => d.id === doctorId);
    if (idx !== -1) mockPendingDoctors.splice(idx, 1);
    return { success: true };
  },
};

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
