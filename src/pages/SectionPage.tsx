import { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  Loader2,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  SkipForward,
  ChevronRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
// Badge component not used in this page
import { toast } from 'sonner';

import { 
  getCase, 
  getSectionTemplate,
  getSection,
  submitSection,
  answerClarifications,
  skipSection,
  moveToNextSection,
  type SectionTemplate 
} from '@/api/client';

export function SectionPage() {
  const { caseId, sectionName } = useParams<{ caseId: string; sectionName: string }>();
  const navigate = useNavigate();
  
  // Case data is loaded but not directly used in this component
  const [template, setTemplate] = useState<SectionTemplate | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showClarifications, setShowClarifications] = useState(false);

  useEffect(() => {
    if (caseId && sectionName) {
      loadSectionData();
    }
  }, [caseId, sectionName]);

  const loadSectionData = async () => {
    try {
      setLoading(true);
      
      // Load case and section data
      const [caseResponse, sectionResponse] = await Promise.all([
        getCase(caseId!),
        getSection(caseId!, sectionName!),
      ]);
      
      setFormData(sectionResponse.data || {});
      
      // Load template
      const templateResponse = await getSectionTemplate(caseResponse.rotation, sectionName!);
      setTemplate(templateResponse);
      
      // Check if there are pending clarifications
      if (sectionResponse.pending_clarifications?.length > 0) {
        setClarifications(sectionResponse.pending_clarifications);
        setShowClarifications(true);
      }
    } catch (error) {
      toast.error('Failed to load section data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (fieldName: string, value: string) => {
    setFormData(prev => ({ ...prev, [fieldName]: value }));
  };

  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      
      const response = await submitSection(caseId!, sectionName!, formData);
      
      if (response.clarifications_needed && response.questions) {
        setClarifications(response.questions);
        setShowClarifications(true);
        toast.info('Please answer the clarification questions');
      } else {
        toast.success('Section submitted successfully!');
        // Move to next section or back to case page
        await moveToNextSection(caseId!);
        navigate(`/case/${caseId}`);
      }
    } catch (error) {
      toast.error('Failed to submit section');
      console.error(error);
    } finally {
      setSubmitting(false);
    }
  };

  const handleAnswerClarifications = async () => {
    try {
      setSubmitting(true);
      
      await answerClarifications(caseId!, sectionName!, clarificationAnswers);
      
      toast.success('Clarifications answered successfully!');
      await moveToNextSection(caseId!);
      navigate(`/case/${caseId}`);
    } catch (error) {
      toast.error('Failed to answer clarifications');
      console.error(error);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSkip = async () => {
    if (!confirm('Are you sure you want to skip this section?')) {
      return;
    }

    try {
      setSubmitting(true);
      await skipSection(caseId!, sectionName!);
      toast.success('Section skipped');
      navigate(`/case/${caseId}`);
    } catch (error) {
      toast.error('Failed to skip section');
      console.error(error);
    } finally {
      setSubmitting(false);
    }
  };

  const renderField = (field: { name: string; type: string; label: string; options?: string[] }) => {
    const value = formData[field.name] || '';
    
    switch (field.type) {
      case 'textarea':
        return (
          <Textarea
            id={field.name}
            value={value}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
            placeholder={`Enter ${field.label.toLowerCase()}...`}
            rows={4}
            className="resize-none"
          />
        );
      
      case 'select':
        return (
          <Select
            value={value}
            onValueChange={(val) => handleInputChange(field.name, val)}
          >
            <SelectTrigger>
              <SelectValue placeholder={`Select ${field.label.toLowerCase()}`} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      
      case 'number':
        return (
          <Input
            id={field.name}
            type="number"
            value={value}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
            placeholder={`Enter ${field.label.toLowerCase()}`}
          />
        );
      
      case 'date':
        return (
          <Input
            id={field.name}
            type="date"
            value={value}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
          />
        );
      
      default:
        return (
          <Input
            id={field.name}
            type="text"
            value={value}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
            placeholder={`Enter ${field.label.toLowerCase()}`}
          />
        );
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!template) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Section Not Found</h1>
        <Link to={`/case/${caseId}`}>
          <Button>Back to Case</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back Button */}
      <Link to={`/case/${caseId}`}>
        <Button variant="ghost" className="mb-4 gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Case
        </Button>
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">{template.title}</h1>
        <p className="text-slate-500 mt-1">
          Complete all fields below to document this section
        </p>
      </div>

      {/* Clarifications Panel */}
      {showClarifications && clarifications.length > 0 && (
        <Card className="mb-6 border-amber-200 bg-amber-50">
          <CardHeader>
            <div className="flex items-center gap-2">
              <HelpCircle className="h-5 w-5 text-amber-600" />
              <CardTitle className="text-amber-900">Clarification Questions</CardTitle>
            </div>
            <CardDescription className="text-amber-700">
              Please answer these questions to complete this section
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {clarifications.map((question, index) => (
              <div key={index}>
                <Label className="text-amber-900 mb-2 block">
                  {question}
                </Label>
                <Textarea
                  value={clarificationAnswers[`q${index}`] || ''}
                  onChange={(e) => 
                    setClarificationAnswers(prev => ({ 
                      ...prev, 
                      [`q${index}`]: e.target.value 
                    }))
                  }
                  placeholder="Your answer..."
                  rows={2}
                />
              </div>
            ))}
            <div className="flex justify-end gap-2 pt-2">
              <Button 
                variant="outline" 
                onClick={() => setShowClarifications(false)}
              >
                Cancel
              </Button>
              <Button 
                onClick={handleAnswerClarifications}
                disabled={submitting}
                className="gap-2"
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                Submit Answers
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Section Form */}
      <Card>
        <CardContent className="p-6">
          <div className="space-y-6">
            {template.fields.map((field: { name: string; type: string; label: string; options?: string[] }) => (
              <div key={field.name}>
                <Label htmlFor={field.name} className="mb-2 block">
                  {field.label}
                </Label>
                {renderField(field)}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex justify-between mt-6">
        <Button 
          variant="outline" 
          onClick={handleSkip}
          disabled={submitting}
          className="gap-2"
        >
          <SkipForward className="h-4 w-4" />
          Skip Section
        </Button>
        
        <div className="flex gap-2">
          <Button 
            variant="outline"
            onClick={() => navigate(`/case/${caseId}`)}
            disabled={submitting}
          >
            Save Draft
          </Button>
          <Button 
            onClick={handleSubmit}
            disabled={submitting}
            className="gap-2"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                Submit Section
                <ChevronRight className="h-4 w-4" />
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
