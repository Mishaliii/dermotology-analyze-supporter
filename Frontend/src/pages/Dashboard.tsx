import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { api, Patient, DoctorCase, DoctorSummary } from "@/lib/api";
import AppLayout from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Users, FileText, Activity } from "lucide-react";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line } from "recharts";

type DateMode = "today" | "yesterday" | "custom";

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

function normalizeDiseaseName(name: string): string {
  if (!name) return "Unknown";
  return name
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function shortenLabel(value: string, maxLen = 16): string {
  if (!value) return "";
  return value.length > maxLen ? `${value.slice(0, maxLen - 1)}…` : value;
}

function parseYearMonth(value: string): { year: number; month: number } | null {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return { year: parsed.getFullYear(), month: parsed.getMonth() + 1 };
}

function compareYearMonth(a: { year: number; month: number }, b: { year: number; month: number }): number {
  if (a.year !== b.year) return a.year - b.year;
  return a.month - b.month;
}

function renderMonthTick(props: { x?: number; y?: number; payload?: { value?: string } }) {
  const { x = 0, y = 0, payload } = props;
  return (
    <g transform={`translate(${x},${y})`}>
      <text x={0} y={0} dy={16} textAnchor="end" fill="#6b7280" fontSize={11} transform="rotate(-18)">
        {payload?.value || ""}
      </text>
    </g>
  );
}

function parseDoctorProfile(clinicName?: string): { specialization: string; district: string; address: string } {
  const raw = (clinicName || "").trim();
  if (!raw) return { specialization: "", district: "Unspecified", address: "" };

  const parts = raw.split("|").map((part) => part.trim());
  let specialization = parts[0] || "";
  let district = "Unspecified";
  let address = "";

  parts.slice(1).forEach((part) => {
    const lower = part.toLowerCase();
    if (lower.startsWith("district:")) district = part.split(":").slice(1).join(":").trim() || "Unspecified";
    if (lower.startsWith("address:")) address = part.split(":").slice(1).join(":").trim();
  });

  return { specialization, district: district || "Unspecified", address };
}

export default function Dashboard() {
  const { doctor, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [cases, setCases] = useState<DoctorCase[]>([]);
  const [doctors, setDoctors] = useState<DoctorSummary[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [patientGraphYear, setPatientGraphYear] = useState<string>("all");
  const [patientGraphMonth, setPatientGraphMonth] = useState<string>("all");
  const [diseaseGraphYear, setDiseaseGraphYear] = useState<string>("all");
  const [diseaseGraphMonth, setDiseaseGraphMonth] = useState<string>("all");
  const [trendDiseaseFilter, setTrendDiseaseFilter] = useState<string>("all");
  const [districtFilter, setDistrictFilter] = useState<string>("all");
  const [doctorDiseaseYear, setDoctorDiseaseYear] = useState<string>("all");
  const [doctorDiseaseMonth, setDoctorDiseaseMonth] = useState<string>("all");
  const [doctorTrendDiseaseFilter, setDoctorTrendDiseaseFilter] = useState<string>("all");
  const [doctorSeverityYear, setDoctorSeverityYear] = useState<string>("all");
  const [doctorSeverityMonth, setDoctorSeverityMonth] = useState<string>("all");

  const [dateMode, setDateMode] = useState<DateMode>("today");
  const [selectedDate, setSelectedDate] = useState<string>(toYmd(new Date()));

  useEffect(() => {
    if (!doctor) return;
    Promise.all([
      api.searchPatients(doctor.id, "").catch(() => ({ success: false, patients: [] })),
      api.getDoctorCases(doctor.id).catch(() => ({ success: false, cases: [] })),
      isAdmin && typeof (api as any).getAllDoctors === "function"
        ? (api as any).getAllDoctors().catch(() => ({ success: false, doctors: [] }))
        : Promise.resolve({ success: false, doctors: [] }),
    ])
      .then(([pRes, cRes, dRes]) => {
        if (pRes.success) setPatients(pRes.patients);
        if (cRes.success) setCases(cRes.cases);
        if (dRes.success) setDoctors(dRes.doctors);
      })
      .finally(() => setLoading(false));
  }, [doctor, isAdmin]);

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

  const doctorScopedCases = useMemo(() => {
    if (isAdmin) return cases;
    return cases.filter((c) => parseCaseDate(c.date) === selectedDate);
  }, [cases, isAdmin, selectedDate]);

  const visiblePatients = useMemo(() => {
    const q = searchQuery.toLowerCase();
    if (isAdmin) {
      return patients.filter((p) => {
        const patientName = p.name.toLowerCase();
        const doctorName = (p.doctor_name || "").toLowerCase();
        return patientName.includes(q) || doctorName.includes(q);
      });
    }

    const patientIdsInDate = new Set(
      doctorScopedCases.map((c) => Number(c.patient_id || 0)).filter((id) => id > 0),
    );

    return patients
      .filter((p) => patientIdsInDate.has(p.id))
      .filter((p) => p.name.toLowerCase().includes(q));
  }, [isAdmin, patients, searchQuery, doctorScopedCases]);

  const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const availableYears = useMemo(() => {
    const years = new Set<number>();
    cases.forEach((item) => {
      const ym = parseYearMonth(item.date);
      if (ym) years.add(ym.year);
    });
    return Array.from(years).sort((a, b) => a - b);
  }, [cases]);

  const yearOptions = availableYears.length ? availableYears : [currentYear];

  const getMonthOptions = (yearValue: string) => {
    if (yearValue === "all") {
      return monthLabels.map((label, idx) => ({ label, value: String(idx + 1) }));
    }
    const y = Number(yearValue);
    const maxMonth = y === currentYear ? currentMonth : 12;
    return monthLabels.slice(0, maxMonth).map((label, idx) => ({ label, value: String(idx + 1) }));
  };

  const patientMonthOptions = getMonthOptions(patientGraphYear);
  const diseaseMonthOptions = getMonthOptions(diseaseGraphYear);

  useEffect(() => {
    if (patientGraphMonth === "all") return;
    if (!patientMonthOptions.some((option) => option.value === patientGraphMonth)) {
      setPatientGraphMonth("all");
    }
  }, [patientGraphYear, patientGraphMonth, patientMonthOptions]);

  useEffect(() => {
    if (diseaseGraphMonth === "all") return;
    if (!diseaseMonthOptions.some((option) => option.value === diseaseGraphMonth)) {
      setDiseaseGraphMonth("all");
    }
  }, [diseaseGraphYear, diseaseGraphMonth, diseaseMonthOptions]);

  const patientGraphCases = useMemo(() => {
    if (!isAdmin) return [] as DoctorCase[];
    return cases.filter((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return false;
      if (patientGraphYear !== "all" && ym.year !== Number(patientGraphYear)) return false;
      if (patientGraphMonth !== "all" && ym.month !== Number(patientGraphMonth)) return false;
      return true;
    });
  }, [cases, isAdmin, patientGraphYear, patientGraphMonth]);

  const diseaseGraphCases = useMemo(() => {
    if (!isAdmin) return [] as DoctorCase[];
    return cases.filter((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return false;
      if (diseaseGraphYear !== "all" && ym.year !== Number(diseaseGraphYear)) return false;
      if (diseaseGraphMonth !== "all" && ym.month !== Number(diseaseGraphMonth)) return false;
      return true;
    });
  }, [cases, isAdmin, diseaseGraphYear, diseaseGraphMonth]);

  const doctorDistrictMap = useMemo(() => {
    const map = new Map<string, string>();
    doctors.forEach((doc) => {
      const profile = parseDoctorProfile(doc.clinic_name);
      map.set(doc.name.trim().toLowerCase(), profile.district || "Unspecified");
    });
    return map;
  }, [doctors]);

  const doctorAdminMap = useMemo(() => {
    const map = new Map<string, boolean>();
    doctors.forEach((doc) => {
      map.set(doc.name.trim().toLowerCase(), Boolean(doc.is_admin));
    });
    return map;
  }, [doctors]);

  const patientCountPerDoctor = useMemo(() => {
    if (!isAdmin) return [] as Array<{ doctor: string; count: number }>;
    const allDoctorNames = new Set<string>();
    doctors.forEach((doc) => allDoctorNames.add((doc.name || "Unassigned").trim() || "Unassigned"));
    cases.forEach((item) => allDoctorNames.add((item.doctor_name || "Unassigned").trim() || "Unassigned"));

    const allTimePatientSetByDoctor = new Map<string, Set<string>>();
    cases.forEach((item) => {
      const doctorName = (item.doctor_name || "Unassigned").trim() || "Unassigned";
      const key = `${item.patient_id || 0}:${(item.patient_name || "").toLowerCase()}`;
      if (!allTimePatientSetByDoctor.has(doctorName)) allTimePatientSetByDoctor.set(doctorName, new Set<string>());
      allTimePatientSetByDoctor.get(doctorName)!.add(key);
    });

    const doctorOrder = Array.from(allDoctorNames).sort((a, b) => {
      const ac = allTimePatientSetByDoctor.get(a)?.size || 0;
      const bc = allTimePatientSetByDoctor.get(b)?.size || 0;
      return ac - bc || a.localeCompare(b);
    });

    const filteredPatientSetByDoctor = new Map<string, Set<string>>();
    patientGraphCases.forEach((item) => {
      const doctorName = (item.doctor_name || "Unassigned").trim() || "Unassigned";
      const key = `${item.patient_id || 0}:${(item.patient_name || "").toLowerCase()}`;
      if (!filteredPatientSetByDoctor.has(doctorName)) filteredPatientSetByDoctor.set(doctorName, new Set<string>());
      filteredPatientSetByDoctor.get(doctorName)!.add(key);
    });

    return doctorOrder.map((doctorName) => ({ doctor: doctorName, count: filteredPatientSetByDoctor.get(doctorName)?.size || 0 }));
  }, [patientGraphCases, isAdmin, doctors, cases]);

  const patientCountYAxisMax = useMemo(() => {
    const fromData = patientCountPerDoctor.reduce((max, row) => Math.max(max, row.count), 0);
    return Math.max(1, fromData);
  }, [patientCountPerDoctor]);
  const patientXAxisInterval = useMemo(() => {
    if (patientCountPerDoctor.length <= 6) return 0;
    return Math.ceil(patientCountPerDoctor.length / 6) - 1;
  }, [patientCountPerDoctor.length]);

  const diseaseCountData = useMemo(() => {
    if (!isAdmin) return [] as Array<{ disease: string; count: number }>;
    const baseCases = cases.filter((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return false;
      if (diseaseGraphYear !== "all" && ym.year !== Number(diseaseGraphYear)) return false;
      return true;
    });

    const baseCounts = new Map<string, number>();
    baseCases.forEach((item) => {
      const disease = normalizeDiseaseName(item.disease);
      baseCounts.set(disease, (baseCounts.get(disease) || 0) + 1);
    });

    const diseaseOrder = Array.from(baseCounts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 12)
      .map(([disease]) => disease);

    const filteredCounts = new Map<string, number>();
    diseaseGraphCases.forEach((item) => {
      const disease = normalizeDiseaseName(item.disease);
      filteredCounts.set(disease, (filteredCounts.get(disease) || 0) + 1);
    });

    return diseaseOrder.map((disease) => ({ disease, count: filteredCounts.get(disease) || 0 }));
  }, [cases, diseaseGraphCases, diseaseGraphYear, isAdmin]);

  const diseaseCountYAxisMax = useMemo(() => {
    const fromData = diseaseCountData.reduce((max, row) => Math.max(max, row.count), 0);
    return Math.max(1, fromData);
  }, [diseaseCountData]);

  const trendDiseaseOptions = useMemo(() => {
    const set = new Set<string>();
    cases.forEach((item) => set.add(normalizeDiseaseName(item.disease)));
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [cases]);

  const trendTimeline = useMemo(() => {
    if (!isAdmin) return [] as Array<{ key: string; label: string }>;

    let minYm: { year: number; month: number } | null = null;
    let maxYm: { year: number; month: number } | null = null;

    cases.forEach((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return;
      if (!minYm || compareYearMonth(ym, minYm) < 0) minYm = ym;
      if (!maxYm || compareYearMonth(ym, maxYm) > 0) maxYm = ym;
    });

    if (!minYm || !maxYm) return [] as Array<{ key: string; label: string }>;

    const timeline: Array<{ key: string; label: string }> = [];
    let y = minYm.year;
    let m = 1;
    let lastYear = -1;

    while (y < maxYm.year || (y === maxYm.year && m <= (y === currentYear ? currentMonth : 12))) {
      const key = `${y}-${String(m).padStart(2, "0")}`;
      const shortMonth = monthLabels[m - 1];
      const label = y !== lastYear ? `${y} ${shortMonth}` : shortMonth;
      timeline.push({ key, label });
      lastYear = y;
      m += 1;
      if (m > 12) {
        m = 1;
        y += 1;
      }
    }

    return timeline;
  }, [cases, isAdmin, monthLabels, currentYear, currentMonth]);

  const monthlyDiseaseTrend = useMemo(() => {
    if (!isAdmin) return [] as Array<{ month: string; count: number }>;
    if (!trendTimeline.length) return [] as Array<{ month: string; count: number }>;

    const monthCounts = new Map<string, number>();

    cases.forEach((item) => {
      if (trendDiseaseFilter !== "all" && normalizeDiseaseName(item.disease) !== trendDiseaseFilter) return;
      const ym = parseYearMonth(item.date);
      if (!ym) return;
      const key = `${ym.year}-${String(ym.month).padStart(2, "0")}`;
      monthCounts.set(key, (monthCounts.get(key) || 0) + 1);
    });

    return trendTimeline.map((item) => ({ month: item.label, count: monthCounts.get(item.key) || 0 }));
  }, [cases, isAdmin, trendDiseaseFilter, trendTimeline]);

  const districtOptions = useMemo(() => {
    const set = new Set<string>();
    doctors.filter((doc) => !doc.is_admin).forEach((doc) => {
      const district = parseDoctorProfile(doc.clinic_name).district || "Unspecified";
      set.add(district);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [doctors]);

  const districtDiseaseData = useMemo(() => {
    if (!isAdmin) return [] as Array<{ label: string; count: number }>;
    if (districtFilter === "all") {
      const districtCounts = new Map<string, number>();
      cases.forEach((item) => {
        const doctorKey = (item.doctor_name || "").trim().toLowerCase();
        const isAdminDoctor = doctorAdminMap.get(doctorKey) ?? /admin/i.test(doctorKey);
        if (isAdminDoctor) return;
        const district = doctorDistrictMap.get(doctorKey) || "Unspecified";
        districtCounts.set(district, (districtCounts.get(district) || 0) + 1);
      });

      const districtOrder = Array.from(new Set([...(districtOptions.length ? districtOptions : []), ...Array.from(districtCounts.keys())])).sort((a, b) =>
        a.localeCompare(b),
      );
      return districtOrder.slice(0, 12).map((label) => ({ label, count: districtCounts.get(label) || 0 }));
    }

    const baseCounts = new Map<string, number>();
    cases.forEach((item) => {
      const doctorKey = (item.doctor_name || "").trim().toLowerCase();
      const isAdminDoctor = doctorAdminMap.get(doctorKey) ?? /admin/i.test(doctorKey);
      if (isAdminDoctor) return;
      const district = doctorDistrictMap.get(doctorKey) || "Unspecified";
      if (district !== districtFilter) return;
      const disease = normalizeDiseaseName(item.disease);
      baseCounts.set(disease, (baseCounts.get(disease) || 0) + 1);
    });

    const diseaseOrder = Array.from(baseCounts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 12)
      .map(([disease]) => disease);

    return diseaseOrder.map((label) => ({ label, count: baseCounts.get(label) || 0 }));
  }, [cases, isAdmin, doctorDistrictMap, doctorAdminMap, districtFilter]);

  const doctorYearOptions = useMemo(() => {
    const years = new Set<number>();
    cases.forEach((item) => {
      const ym = parseYearMonth(item.date);
      if (ym) years.add(ym.year);
    });
    const arr = Array.from(years).sort((a, b) => a - b);
    return arr.length ? arr : [currentYear];
  }, [cases, currentYear]);

  const doctorDiseaseMonthOptions = useMemo(() => {
    if (doctorDiseaseYear === "all") {
      return monthLabels.map((label, idx) => ({ label, value: String(idx + 1) }));
    }
    const yearNum = Number(doctorDiseaseYear);
    const maxMonth = yearNum === currentYear ? currentMonth : 12;
    return monthLabels.slice(0, maxMonth).map((label, idx) => ({ label, value: String(idx + 1) }));
  }, [doctorDiseaseYear, monthLabels, currentYear, currentMonth]);

  useEffect(() => {
    if (doctorDiseaseMonth === "all") return;
    if (doctorDiseaseMonthOptions.some((option) => option.value === doctorDiseaseMonth)) return;
    setDoctorDiseaseMonth("all");
  }, [doctorDiseaseMonth, doctorDiseaseMonthOptions]);

  const doctorSeverityMonthOptions = useMemo(() => {
    if (doctorSeverityYear === "all") {
      return monthLabels.map((label, idx) => ({ label, value: String(idx + 1) }));
    }
    const yearNum = Number(doctorSeverityYear);
    const maxMonth = yearNum === currentYear ? currentMonth : 12;
    return monthLabels.slice(0, maxMonth).map((label, idx) => ({ label, value: String(idx + 1) }));
  }, [doctorSeverityYear, monthLabels, currentYear, currentMonth]);

  useEffect(() => {
    if (doctorSeverityMonth === "all") return;
    if (doctorSeverityMonthOptions.some((option) => option.value === doctorSeverityMonth)) return;
    setDoctorSeverityMonth("all");
  }, [doctorSeverityMonth, doctorSeverityMonthOptions]);

  const doctorPatientTrendData = useMemo(() => {
    if (isAdmin) return [] as Array<{ month: string; count: number }>;

    let minYm: { year: number; month: number } | null = null;
    let maxYm: { year: number; month: number } | null = null;
    const uniquePatientsByMonth = new Map<string, Set<string>>();

    cases.forEach((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return;
      if (!minYm || compareYearMonth(ym, minYm) < 0) minYm = ym;
      if (!maxYm || compareYearMonth(ym, maxYm) > 0) maxYm = ym;

      const key = `${ym.year}-${String(ym.month).padStart(2, "0")}`;
      const patientKey = `${item.patient_id || 0}:${(item.patient_name || "").toLowerCase()}`;
      if (!uniquePatientsByMonth.has(key)) uniquePatientsByMonth.set(key, new Set<string>());
      uniquePatientsByMonth.get(key)!.add(patientKey);
    });

    if (!minYm || !maxYm) return [] as Array<{ month: string; count: number }>;

    const rows: Array<{ month: string; count: number }> = [];
    let y = minYm.year;
    let m = 1;
    let lastYear = -1;

    while (y < maxYm.year || (y === maxYm.year && m <= (y === currentYear ? currentMonth : 12))) {
      const key = `${y}-${String(m).padStart(2, "0")}`;
      const shortMonth = monthLabels[m - 1];
      const label = y !== lastYear ? `${y} ${shortMonth}` : shortMonth;
      rows.push({ month: label, count: uniquePatientsByMonth.get(key)?.size || 0 });
      lastYear = y;
      m += 1;
      if (m > 12) {
        m = 1;
        y += 1;
      }
    }

    return rows;
  }, [cases, isAdmin, monthLabels, currentYear, currentMonth]);

  const doctorDiseaseGraphCases = useMemo(() => {
    if (isAdmin) return [] as DoctorCase[];
    return cases.filter((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return false;
      if (doctorDiseaseYear !== "all" && ym.year !== Number(doctorDiseaseYear)) return false;
      if (doctorDiseaseMonth !== "all" && ym.month !== Number(doctorDiseaseMonth)) return false;
      return true;
    });
  }, [cases, isAdmin, doctorDiseaseYear, doctorDiseaseMonth]);

  const doctorDiseaseCountData = useMemo(() => {
    if (isAdmin) return [] as Array<{ disease: string; count: number }>;
    const baseCases = cases.filter((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return false;
      if (doctorDiseaseYear !== "all" && ym.year !== Number(doctorDiseaseYear)) return false;
      return true;
    });

    const baseCounts = new Map<string, number>();
    baseCases.forEach((item) => {
      const disease = normalizeDiseaseName(item.disease);
      baseCounts.set(disease, (baseCounts.get(disease) || 0) + 1);
    });

    const diseaseOrder = Array.from(baseCounts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 10)
      .map(([disease]) => disease);

    const filteredCounts = new Map<string, number>();
    doctorDiseaseGraphCases.forEach((item) => {
      const disease = normalizeDiseaseName(item.disease);
      filteredCounts.set(disease, (filteredCounts.get(disease) || 0) + 1);
    });

    return diseaseOrder.map((disease) => ({ disease, count: filteredCounts.get(disease) || 0 }));
  }, [cases, isAdmin, doctorDiseaseYear, doctorDiseaseGraphCases]);

  const doctorDiseaseYAxisMax = useMemo(() => {
    const maxValue = doctorDiseaseCountData.reduce((max, row) => Math.max(max, row.count), 0);
    return Math.max(1, maxValue);
  }, [doctorDiseaseCountData]);

  const doctorTrendTimeline = useMemo(() => {
    if (isAdmin) return [] as Array<{ key: string; label: string }>;

    let minYm: { year: number; month: number } | null = null;
    let maxYm: { year: number; month: number } | null = null;

    cases.forEach((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return;
      if (!minYm || compareYearMonth(ym, minYm) < 0) minYm = ym;
      if (!maxYm || compareYearMonth(ym, maxYm) > 0) maxYm = ym;
    });
    if (!minYm || !maxYm) return [] as Array<{ key: string; label: string }>;

    const timeline: Array<{ key: string; label: string }> = [];
    let y = minYm.year;
    let m = 1;
    let lastYear = -1;

    while (y < maxYm.year || (y === maxYm.year && m <= (y === currentYear ? currentMonth : 12))) {
      const key = `${y}-${String(m).padStart(2, "0")}`;
      const shortMonth = monthLabels[m - 1];
      const label = y !== lastYear ? `${y} ${shortMonth}` : shortMonth;
      timeline.push({ key, label });
      lastYear = y;
      m += 1;
      if (m > 12) {
        m = 1;
        y += 1;
      }
    }

    return timeline;
  }, [cases, isAdmin, monthLabels, currentYear, currentMonth]);

  const doctorTrendDiseaseOptions = useMemo(() => {
    const set = new Set<string>();
    cases.forEach((item) => set.add(normalizeDiseaseName(item.disease)));
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [cases]);

  const doctorMonthlyDiseaseTrend = useMemo(() => {
    if (isAdmin) return [] as Array<{ month: string; count: number }>;
    if (!doctorTrendTimeline.length) return [] as Array<{ month: string; count: number }>;

    const monthCounts = new Map<string, number>();
    cases.forEach((item) => {
      if (doctorTrendDiseaseFilter !== "all" && normalizeDiseaseName(item.disease) !== doctorTrendDiseaseFilter) return;
      const ym = parseYearMonth(item.date);
      if (!ym) return;
      const key = `${ym.year}-${String(ym.month).padStart(2, "0")}`;
      monthCounts.set(key, (monthCounts.get(key) || 0) + 1);
    });

    return doctorTrendTimeline.map((item) => ({ month: item.label, count: monthCounts.get(item.key) || 0 }));
  }, [cases, isAdmin, doctorTrendDiseaseFilter, doctorTrendTimeline]);

  const doctorSeverityFilteredCases = useMemo(() => {
    if (isAdmin) return [] as DoctorCase[];
    return cases.filter((item) => {
      const ym = parseYearMonth(item.date);
      if (!ym) return false;
      if (doctorSeverityYear !== "all" && ym.year !== Number(doctorSeverityYear)) return false;
      if (doctorSeverityMonth !== "all" && ym.month !== Number(doctorSeverityMonth)) return false;
      return true;
    });
  }, [cases, isAdmin, doctorSeverityYear, doctorSeverityMonth]);

  const doctorSeverityDistribution = useMemo(() => {
    if (isAdmin) return [] as Array<{ label: string; count: number }>;
    const keys = ["Clear/None", "Mild", "Moderate", "Severe", "Other"];
    const counts = new Map<string, number>(keys.map((k) => [k, 0]));

    doctorSeverityFilteredCases.forEach((item) => {
      const s = (item.severity || "").toLowerCase();
      let bucket = "Other";
      if (s.includes("clear") || s.includes("none") || s.includes("minimal")) bucket = "Clear/None";
      else if (s.includes("mild")) bucket = "Mild";
      else if (s.includes("moderate")) bucket = "Moderate";
      else if (s.includes("severe") || s.includes("high")) bucket = "Severe";
      counts.set(bucket, (counts.get(bucket) || 0) + 1);
    });

    return keys.map((label) => ({ label, count: counts.get(label) || 0 }));
  }, [doctorSeverityFilteredCases, isAdmin]);

  const stats = isAdmin
    ? [
        { label: "Total Doctors", value: doctors.length, icon: Users, color: "text-accent" },
        { label: "Total Patients", value: patients.length, icon: Activity, color: "text-info" },
        { label: "Total Cases", value: cases.length, icon: FileText, color: "text-success" },
      ]
    : (() => {
        return [
          { label: "Bookings", value: "N/A", icon: FileText, color: "text-accent" },
          { label: "Patients", value: visiblePatients.length, icon: Users, color: "text-info" },
        ];
      })();

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Welcome, {doctor?.name}</h1>
            <p className="text-muted-foreground">
              {isAdmin ? "Administrative summary across all doctors" : `Clinical summary for ${selectedDate}`}
            </p>
          </div>
          {!isAdmin && (
            <Button onClick={() => navigate("/patients", { state: { openNewPatient: true } })} className="medical-gradient text-primary-foreground gap-2">
              <Plus className="w-4 h-4" /> New Patient
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

        <div className={`grid grid-cols-1 gap-4 ${isAdmin ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
          {stats.map((s, i) => (
            <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }} className="medical-card p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{s.label}</p>
                  <p className="text-3xl font-bold text-foreground mt-1">{loading ? "-" : s.value}</p>
                </div>
                <div className={`p-3 rounded-xl bg-muted ${s.color}`}>
                  <s.icon className="w-6 h-6" />
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {isAdmin ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="medical-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h2 className="text-lg font-semibold text-foreground">Patient Count Per Doctor</h2>
                <div className="flex items-center gap-2">
                  <select value={patientGraphYear} onChange={(e) => setPatientGraphYear(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                    <option value="all">All Years</option>
                    {yearOptions.map((year) => (
                      <option key={year} value={String(year)}>{year}</option>
                    ))}
                  </select>
                  <select value={patientGraphMonth} onChange={(e) => setPatientGraphMonth(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                    <option value="all">All Months</option>
                    {patientMonthOptions.map((month) => (
                      <option key={month.value} value={month.value}>{month.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              {patientCountPerDoctor.length === 0 ? (
                <div className="h-72 flex items-center justify-center text-sm text-muted-foreground border rounded-lg">
                  No doctor-patient data for selected period.
                </div>
              ) : (
                <div className="h-80 border rounded-lg p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={patientCountPerDoctor} margin={{ top: 8, right: 16, left: 0, bottom: 18 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis
                        dataKey="doctor"
                        tick={{ fontSize: 11 }}
                        interval={patientXAxisInterval}
                        tickFormatter={(value) => shortenLabel(String(value))}
                        angle={-18}
                        textAnchor="end"
                        height={62}
                      />
                      <YAxis allowDecimals={false} domain={[0, patientCountYAxisMax]} />
                      <Tooltip formatter={(value) => [value, "Patients"]} labelFormatter={(label) => `Doctor: ${label}`} />
                      <Bar dataKey="count" fill="#0d9488" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="medical-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h2 className="text-lg font-semibold text-foreground">Disease Count</h2>
                <div className="flex items-center gap-2">
                  <select value={diseaseGraphYear} onChange={(e) => setDiseaseGraphYear(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                    <option value="all">All Years</option>
                    {yearOptions.map((year) => (
                      <option key={year} value={String(year)}>{year}</option>
                    ))}
                  </select>
                  <select value={diseaseGraphMonth} onChange={(e) => setDiseaseGraphMonth(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                    <option value="all">All Months</option>
                    {diseaseMonthOptions.map((month) => (
                      <option key={month.value} value={month.value}>{month.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              {diseaseCountData.length === 0 ? (
                <div className="h-72 flex items-center justify-center text-sm text-muted-foreground border rounded-lg">
                  No disease data for selected period.
                </div>
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={diseaseCountData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="disease" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={56} />
                      <YAxis allowDecimals={false} domain={[0, diseaseCountYAxisMax]} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#2563eb" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="medical-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h2 className="text-lg font-semibold text-foreground">Monthly Disease Trend</h2>
                <select value={trendDiseaseFilter} onChange={(e) => setTrendDiseaseFilter(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                  <option value="all">All Diseases</option>
                  {trendDiseaseOptions.map((disease) => (
                    <option key={disease} value={disease}>{disease}</option>
                  ))}
                </select>
              </div>
              {monthlyDiseaseTrend.length === 0 ? (
                <div className="h-72 flex items-center justify-center text-sm text-muted-foreground border rounded-lg">
                  No monthly trend available for selected year.
                </div>
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={monthlyDiseaseTrend} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="month" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={56} />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Line type="monotone" dataKey="count" stroke="#16a34a" strokeWidth={3} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="medical-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h2 className="text-lg font-semibold text-foreground">District Wise Diseases</h2>
                <select value={districtFilter} onChange={(e) => setDistrictFilter(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                  <option value="all">All Districts</option>
                  {districtOptions.map((district) => (
                    <option key={district} value={district}>{district}</option>
                  ))}
                </select>
              </div>
              {districtDiseaseData.length === 0 ? (
                <div className="h-72 flex items-center justify-center text-sm text-muted-foreground border rounded-lg">
                  No district data available.
                </div>
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={districtDiseaseData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={56} />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#9333ea" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="medical-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h2 className="text-lg font-semibold text-foreground">Patient Count Per Year-Month</h2>
              </div>
              {doctorPatientTrendData.length === 0 ? (
                <div className="h-72 flex items-center justify-center text-sm text-muted-foreground border rounded-lg">
                  No patient trend data available.
                </div>
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={doctorPatientTrendData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="month" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={56} />
                      <YAxis allowDecimals={false} />
                      <Tooltip formatter={(value) => [value, "Patients"]} />
                      <Bar dataKey="count" fill="#0d9488" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="medical-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h2 className="text-lg font-semibold text-foreground">Disease Count</h2>
                <div className="flex items-center gap-2">
                  <select value={doctorDiseaseYear} onChange={(e) => setDoctorDiseaseYear(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                    <option value="all">All Years</option>
                    {doctorYearOptions.map((year) => (
                      <option key={year} value={String(year)}>{year}</option>
                    ))}
                  </select>
                  <select value={doctorDiseaseMonth} onChange={(e) => setDoctorDiseaseMonth(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                    <option value="all">All Months</option>
                    {doctorDiseaseMonthOptions.map((month) => (
                      <option key={month.value} value={month.value}>{month.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              {doctorDiseaseCountData.length === 0 ? (
                <div className="h-72 flex items-center justify-center text-sm text-muted-foreground border rounded-lg">
                  No disease data for selected period.
                </div>
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={doctorDiseaseCountData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="disease" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={56} />
                      <YAxis allowDecimals={false} domain={[0, doctorDiseaseYAxisMax]} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#2563eb" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="medical-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h2 className="text-lg font-semibold text-foreground">Disease Count Per Year-Month</h2>
                <select value={doctorTrendDiseaseFilter} onChange={(e) => setDoctorTrendDiseaseFilter(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                  <option value="all">All Diseases</option>
                  {doctorTrendDiseaseOptions.map((disease) => (
                    <option key={disease} value={disease}>{disease}</option>
                  ))}
                </select>
              </div>
              {doctorMonthlyDiseaseTrend.length === 0 ? (
                <div className="h-72 flex items-center justify-center text-sm text-muted-foreground border rounded-lg">
                  No monthly disease trend available.
                </div>
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={doctorMonthlyDiseaseTrend} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis
                        dataKey="month"
                        ticks={doctorMonthlyDiseaseTrend.map((item) => item.month)}
                        tick={renderMonthTick}
                        interval={0}
                        minTickGap={0}
                        allowDuplicatedCategory={false}
                        angle={-18}
                        textAnchor="end"
                        height={72}
                      />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Line type="monotone" dataKey="count" stroke="#16a34a" strokeWidth={3} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="medical-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h2 className="text-lg font-semibold text-foreground">Severity Distribution</h2>
                <div className="flex items-center gap-2">
                  <select value={doctorSeverityYear} onChange={(e) => setDoctorSeverityYear(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                    <option value="all">All Years</option>
                    {doctorYearOptions.map((year) => (
                      <option key={year} value={String(year)}>{year}</option>
                    ))}
                  </select>
                  <select value={doctorSeverityMonth} onChange={(e) => setDoctorSeverityMonth(e.target.value)} className="h-9 px-3 rounded-md border bg-background text-sm">
                    <option value="all">All Months</option>
                    {doctorSeverityMonthOptions.map((month) => (
                      <option key={month.value} value={month.value}>{month.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              {doctorSeverityDistribution.length === 0 ? (
                <div className="h-72 flex items-center justify-center text-sm text-muted-foreground border rounded-lg">
                  No severity distribution data available.
                </div>
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={doctorSeverityDistribution} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={56} />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#ef4444" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

    </AppLayout>
  );
}
