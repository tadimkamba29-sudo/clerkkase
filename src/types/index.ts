/**
 * Type definitions for ClerKase
 */

// ============================================================================
// Rotation Types
// ============================================================================

export interface Rotation {
  id: string;
  name: string;
  section_count: number;
  version: string;
}

export interface RotationDetail extends Rotation {
  sections: SectionInfo[];
}

export interface SectionInfo {
  name: string;
  title: string;
  order: number;
  required: boolean;
  field_count: number;
}

export interface SectionTemplate {
  name: string;
  title: string;
  order: number;
  required: boolean;
  fields: FieldTemplate[];
  field_count?: number;
  clarification_rules?: Record<string, ClarificationRule>;
}

export interface FieldTemplate {
  name: string;
  type: 'text' | 'number' | 'date' | 'select' | 'textarea';
  label: string;
  options?: string[];
}

export interface ClarificationRule {
  missing: string;
  invalid?: string;
}

// ============================================================================
// Case Types
// ============================================================================

export interface Case {
  case_id: string;
  rotation: string;
  current_section: string;
  created_at: string;
  last_updated: string;
  is_complete: boolean;
  completed_at?: string;
}

export interface CaseDetail extends Case {
  template_version: string;
  completed_sections: string[];
  section_status: Record<string, SectionStatus>;
  sections: Record<string, SectionData>;
}

export type SectionStatus = 'not_started' | 'in_progress' | 'pending_clarification' | 'complete';

export interface SectionData {
  section_name: string;
  data: Record<string, string>;
  status: SectionStatus;
  pending_clarifications: string[];
}

// ============================================================================
// Progress Types
// ============================================================================

export interface CaseProgress {
  case_id: string;
  rotation: string;
  total_sections: number;
  completed_sections: number;
  completion_percentage: number;
  current_section: string;
  is_complete: boolean;
  pending_clarifications: number;
  section_breakdown: Record<string, SectionProgress>;
}

export interface SectionProgress {
  status: SectionStatus;
  has_clarifications: boolean;
}

// ============================================================================
// Clarification Types
// ============================================================================

export interface ClarificationResult {
  questions: string[];
  source: 'rules' | 'ai' | 'hybrid';
  confidence: number;
  reasoning: string;
}

export interface Contradiction {
  type: string;
  message: string;
  severity: 'high' | 'medium' | 'low';
}

// ============================================================================
// Parsing Types
// ============================================================================

export interface ParsedEntity {
  entity_type: string;
  value: string | number;
  confidence: number;
  position: [number, number];
}

export interface ParseResult {
  original_text: string;
  section: string;
  entities: ParsedEntity[];
  parsed_at: string;
  symptoms?: Symptom[];
  duration?: DurationInfo;
  age?: AgeInfo;
  severity?: SeverityInfo;
  socrates_pain?: SocratesPain;
}

export interface Symptom {
  symptom: string;
  position: [number, number];
  context: string;
}

export interface DurationInfo {
  value: string;
  position: [number, number];
}

export interface AgeInfo {
  value: number;
  position: [number, number];
}

export interface SeverityInfo {
  value: string;
  position: [number, number];
}

export interface SocratesPain {
  site: string | null;
  onset: string | null;
  character: string | null;
  radiation: string | null;
  associations: string | null;
  time_course: string | null;
  exacerbating: string | null;
  relieving: string | null;
  severity: string | null;
  is_complete: boolean;
}

// ============================================================================
// Export Types
// ============================================================================

export interface ExportResult {
  message: string;
  case_id: string;
  format: 'markdown' | 'word';
  file_path: string;
  content?: string;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
}

export interface SystemStatus {
  status: string;
  timestamp: string;
  components: {
    state_manager: string;
    input_parser: string;
    clarification_engine: string;
    ai_clarifier: {
      available: boolean;
      reason: string;
    };
    document_compiler: string;
  };
  available_rotations: string[];
}
