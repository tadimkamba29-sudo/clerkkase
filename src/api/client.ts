/**
 * API Client for ClerKase
 */

import type {
  Rotation,
  RotationDetail,
  SectionTemplate,
  Case,
  CaseDetail,
  CaseProgress,
  ClarificationResult,
  Contradiction,
  ParseResult,
  SocratesPain,
  ExportResult,
  SystemStatus
} from '@/types';

// Re-export types for use in other modules
export type {
  Rotation,
  RotationDetail,
  SectionTemplate,
  Case,
  CaseDetail,
  CaseProgress,
  ClarificationResult,
  Contradiction,
  ParseResult,
  SocratesPain,
  ExportResult,
  SystemStatus
};

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

class ApiError extends Error {
  status: number;
  
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new ApiError(response.status, error.error || error.message || 'Request failed');
  }

  return response.json();
}

// ============================================================================
// Health & Status
// ============================================================================

export const getHealth = () => fetchApi<{ status: string; timestamp: string; version: string }>('/health');

export const getSystemStatus = () => fetchApi<SystemStatus>('/status');

// ============================================================================
// Rotations
// ============================================================================

export const getRotations = () => fetchApi<{ rotations: Rotation[] }>('/rotations');

export const getRotationDetail = (rotationId: string) => 
  fetchApi<RotationDetail>(`/rotations/${rotationId}`);

export const getRotationTemplate = (rotationId: string) => 
  fetchApi<{ sections: SectionTemplate[] }>(`/rotations/${rotationId}/template`);

export const getSectionTemplate = (rotationId: string, sectionName: string) => 
  fetchApi<SectionTemplate>(`/rotations/${rotationId}/sections/${sectionName}`);

// ============================================================================
// Cases
// ============================================================================

export const createCase = (rotation: string) => 
  fetchApi<{ message: string; case: Case }>('/cases', {
    method: 'POST',
    body: JSON.stringify({ rotation }),
  });

export const getCases = () => fetchApi<{ cases: Case[]; total: number }>('/cases');

export const getCase = (caseId: string) => fetchApi<CaseDetail>(`/cases/${caseId}`);

export const deleteCase = (caseId: string) => 
  fetchApi<{ message: string; case_id: string }>(`/cases/${caseId}`, {
    method: 'DELETE',
  });

// ============================================================================
// Sections
// ============================================================================

export const getSection = (caseId: string, sectionName: string) => 
  fetchApi<{
    case_id: string;
    section_name: string;
    data: Record<string, string>;
    status: string;
    pending_clarifications: string[];
  }>(`/cases/${caseId}/sections/${sectionName}`);

export const updateSection = (
  caseId: string, 
  sectionName: string, 
  data: Record<string, string>,
  status?: string
) => 
  fetchApi<{ message: string; case_id: string; section_name: string; status: string }>(
    `/cases/${caseId}/sections/${sectionName}`,
    {
      method: 'PUT',
      body: JSON.stringify({ data, status }),
    }
  );

export const submitSection = (
  caseId: string, 
  sectionName: string, 
  data: Record<string, string>
) => 
  fetchApi<{
    message: string;
    case_id: string;
    section_name: string;
    clarifications_needed: boolean;
    questions?: string[];
    source?: string;
    confidence?: number;
    status?: string;
  }>(`/cases/${caseId}/sections/${sectionName}/submit`, {
    method: 'POST',
    body: JSON.stringify({ data }),
  });

export const answerClarifications = (
  caseId: string, 
  sectionName: string, 
  answers: Record<string, string>
) => 
  fetchApi<{ message: string; case_id: string; section_name: string; status: string }>(
    `/cases/${caseId}/sections/${sectionName}/clarifications`,
    {
      method: 'POST',
      body: JSON.stringify({ answers }),
    }
  );

export const skipSection = (caseId: string, sectionName: string) => 
  fetchApi<{ message: string; case_id: string; section_name: string; status: string }>(
    `/cases/${caseId}/sections/${sectionName}/skip`,
    {
      method: 'POST',
    }
  );

// ============================================================================
// Workflow
// ============================================================================

export const moveToNextSection = (caseId: string) => 
  fetchApi<{
    message: string;
    case_id: string;
    current_section: string;
    is_complete: boolean;
    completed_sections: string[];
  }>(`/cases/${caseId}/next`, {
    method: 'POST',
  });

export const getProgress = (caseId: string) => fetchApi<CaseProgress>(`/cases/${caseId}/progress`);

// ============================================================================
// Parsing
// ============================================================================

export const parseInput = (text: string, section: string = 'general') => 
  fetchApi<ParseResult>('/parse', {
    method: 'POST',
    body: JSON.stringify({ text, section }),
  });

export const parseSocrates = (text: string) => 
  fetchApi<SocratesPain>('/parse/socrates', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });

// ============================================================================
// Clarifications
// ============================================================================

export const generateClarifications = (
  sectionName: string,
  sectionData: Record<string, string>,
  rotation: string
) => 
  fetchApi<ClarificationResult>('/clarify', {
    method: 'POST',
    body: JSON.stringify({ section_name: sectionName, section_data: sectionData, rotation }),
  });

export const detectContradictions = (sections: Record<string, { data: Record<string, string> }>) => 
  fetchApi<{ contradictions_found: boolean; contradictions: Contradiction[] }>('/clarify/contradictions', {
    method: 'POST',
    body: JSON.stringify({ sections }),
  });

// ============================================================================
// Export
// ============================================================================

export const exportCase = (
  caseId: string,
  format: 'markdown' | 'word' = 'markdown',
  sections?: string[]
) => 
  fetchApi<ExportResult>(`/cases/${caseId}/export`, {
    method: 'POST',
    body: JSON.stringify({ format, sections }),
  });

export const downloadExport = (caseId: string, format: 'markdown' | 'word' = 'markdown') => {
  const url = `${API_BASE_URL}/cases/${caseId}/export/download?format=${format}`;
  window.open(url, '_blank');
};

export const getCaseSummary = (caseId: string) => 
  fetchApi<{ case_id: string; summary: string }>(`/cases/${caseId}/summary`);
