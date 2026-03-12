import { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  ChevronRight,
  Loader2,
  CheckCircle2,
  Clock,
  AlertCircle,
  Download,
  Trash2,
  RotateCcw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';

import { 
  getCase, 
  getProgress, 
  deleteCase,
  getRotationTemplate,
  type CaseDetail, 
  type CaseProgress,
  type SectionTemplate 
} from '@/api/client';

export function CasePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [progress, setProgress] = useState<CaseProgress | null>(null);
  const [template, setTemplate] = useState<{ sections: SectionTemplate[] } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (caseId) {
      loadCaseData();
    }
  }, [caseId]);

  const loadCaseData = async () => {
    try {
      setLoading(true);
      const [caseResponse, progressResponse] = await Promise.all([
        getCase(caseId!),
        getProgress(caseId!),
      ]);
      
      setCaseData(caseResponse);
      setProgress(progressResponse);
      
      // Load template for section titles
      const templateResponse = await getRotationTemplate(caseResponse.rotation);
      setTemplate(templateResponse);
    } catch (error) {
      toast.error('Failed to load case data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCase = async () => {
    if (!confirm('Are you sure you want to delete this case? This action cannot be undone.')) {
      return;
    }

    try {
      await deleteCase(caseId!);
      toast.success('Case deleted successfully');
      navigate('/dashboard');
    } catch (error) {
      toast.error('Failed to delete case');
      console.error(error);
    }
  };

  const handleExport = () => {
    navigate(`/case/${caseId}/export`);
  };

  const getSectionStatusIcon = (status: string, hasClarifications: boolean) => {
    if (status === 'complete') {
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    }
    if (hasClarifications) {
      return <AlertCircle className="h-5 w-5 text-amber-500" />;
    }
    if (status === 'in_progress') {
      return <RotateCcw className="h-5 w-5 text-blue-500" />;
    }
    return <Clock className="h-5 w-5 text-slate-400" />;
  };

  const getSectionStatusBadge = (status: string, hasClarifications: boolean) => {
    if (status === 'complete') {
      return <Badge className="bg-green-100 text-green-700">Complete</Badge>;
    }
    if (hasClarifications) {
      return <Badge className="bg-amber-100 text-amber-700">Needs Clarification</Badge>;
    }
    if (status === 'in_progress') {
      return <Badge variant="secondary">In Progress</Badge>;
    }
    return <Badge variant="outline" className="text-slate-400">Not Started</Badge>;
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!caseData || !progress) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Case Not Found</h1>
        <p className="text-slate-600 mb-4">The case you're looking for doesn't exist.</p>
        <Link to="/dashboard">
          <Button>Back to Dashboard</Button>
        </Link>
      </div>
    );
  }

  const sections = template?.sections?.sort((a, b) => a.order - b.order) || [];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back Button */}
      <Link to="/dashboard">
        <Button variant="ghost" className="mb-4 gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Button>
      </Link>

      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-slate-900">
              {caseData.rotation.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
            </h1>
            {caseData.is_complete ? (
              <Badge className="bg-green-100 text-green-700">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Complete
              </Badge>
            ) : (
              <Badge variant="secondary">In Progress</Badge>
            )}
          </div>
          <p className="text-slate-500">
            Case ID: {caseData.case_id}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport} className="gap-2">
            <Download className="h-4 w-4" />
            Export
          </Button>
          <Button 
            variant="outline" 
            className="text-red-600 hover:text-red-700 hover:bg-red-50"
            onClick={handleDeleteCase}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Progress Card */}
      <Card className="mb-6">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-slate-900">Overall Progress</h3>
              <p className="text-sm text-slate-500">
                {progress.completed_sections} of {progress.total_sections} sections completed
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold text-blue-600">
                {progress.completion_percentage}%
              </span>
            </div>
          </div>
          <Progress value={progress.completion_percentage} className="h-2" />
          
          {progress.pending_clarifications > 0 && (
            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-amber-600" />
              <span className="text-sm text-amber-800">
                {progress.pending_clarifications} section(s) need clarification
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Sections List */}
      <Card>
        <CardHeader>
          <CardTitle>Sections</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {sections.map((section) => {
              const sectionProgress = progress.section_breakdown[section.name];
              const isCurrent = caseData.current_section === section.name;
              
              return (
                <Link 
                  key={section.name}
                  to={`/case/${caseId}/section/${section.name}`}
                >
                  <div 
                    className={`
                      flex items-center justify-between p-4 rounded-lg border transition-all
                      ${isCurrent 
                        ? 'border-blue-500 bg-blue-50' 
                        : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50'
                      }
                    `}
                  >
                    <div className="flex items-center gap-4">
                      {getSectionStatusIcon(
                        sectionProgress?.status || 'not_started',
                        sectionProgress?.has_clarifications || false
                      )}
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-slate-900">
                            {section.title}
                          </h4>
                          {isCurrent && (
                            <Badge className="bg-blue-100 text-blue-700">Current</Badge>
                          )}
                        </div>
                        <p className="text-sm text-slate-500">
                          {section.field_count} fields
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {getSectionStatusBadge(
                        sectionProgress?.status || 'not_started',
                        sectionProgress?.has_clarifications || false
                      )}
                      <ChevronRight className="h-5 w-5 text-slate-400" />
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
