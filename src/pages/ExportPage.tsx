import { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { 
  ArrowLeft, 
  FileText, 
  FileSpreadsheet,
  Download,
  Loader2,
  Copy
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';

import { 
  getCase, 
  exportCase, 
  getCaseSummary,
  downloadExport,
  type CaseDetail 
} from '@/api/client';

export function ExportPage() {
  const { caseId } = useParams<{ caseId: string }>();
  
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [summary, setSummary] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<'markdown' | 'word' | null>(null);

  useEffect(() => {
    if (caseId) {
      loadData();
    }
  }, [caseId]);

  const loadData = async () => {
    try {
      setLoading(true);
      
      const [caseResponse, summaryResponse] = await Promise.all([
        getCase(caseId!),
        getCaseSummary(caseId!),
      ]);
      
      setCaseData(caseResponse);
      setSummary(summaryResponse.summary);
      
      // Generate markdown preview
      const markdownResponse = await exportCase(caseId!, 'markdown');
      if (markdownResponse.content) {
        setMarkdownContent(markdownResponse.content);
      }
    } catch (error) {
      toast.error('Failed to load export data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleExportMarkdown = async () => {
    try {
      setExporting('markdown');
      await exportCase(caseId!, 'markdown');
      downloadExport(caseId!, 'markdown');
      toast.success('Markdown document downloaded');
    } catch (error) {
      toast.error('Failed to export markdown');
      console.error(error);
    } finally {
      setExporting(null);
    }
  };

  const handleExportWord = async () => {
    try {
      setExporting('word');
      await exportCase(caseId!, 'word');
      downloadExport(caseId!, 'word');
      toast.success('Word document downloaded');
    } catch (error) {
      toast.error('Failed to export Word document');
      console.error(error);
    } finally {
      setExporting(null);
    }
  };

  const handleCopyMarkdown = () => {
    navigator.clipboard.writeText(markdownContent);
    toast.success('Markdown copied to clipboard');
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Case Not Found</h1>
        <Link to="/dashboard">
          <Button>Back to Dashboard</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back Button */}
      <Link to={`/case/${caseId}`}>
        <Button variant="ghost" className="mb-4 gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Case
        </Button>
      </Link>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">
          Export Case
        </h1>
        <p className="text-slate-600">
          Download your case documentation in your preferred format
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Export Options */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Export Options</CardTitle>
              <CardDescription>
                Choose your preferred export format
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Markdown Export */}
              <div className="p-4 border rounded-lg hover:border-blue-300 transition-colors">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
                    <FileText className="h-5 w-5 text-slate-600" />
                  </div>
                  <div>
                    <h4 className="font-medium text-slate-900">Markdown</h4>
                    <p className="text-sm text-slate-500">.md file</p>
                  </div>
                </div>
                <Button 
                  onClick={handleExportMarkdown}
                  disabled={exporting === 'markdown'}
                  className="w-full gap-2"
                  variant="outline"
                >
                  {exporting === 'markdown' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Download Markdown
                </Button>
              </div>

              {/* Word Export */}
              <div className="p-4 border rounded-lg hover:border-blue-300 transition-colors">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                    <FileSpreadsheet className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h4 className="font-medium text-slate-900">Word Document</h4>
                    <p className="text-sm text-slate-500">.docx file</p>
                  </div>
                </div>
                <Button 
                  onClick={handleExportWord}
                  disabled={exporting === 'word'}
                  className="w-full gap-2"
                >
                  {exporting === 'word' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Download Word
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Case Info */}
          <Card>
            <CardHeader>
              <CardTitle>Case Information</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Rotation:</span>
                  <span className="font-medium">
                    {caseData.rotation.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Status:</span>
                  <Badge className={caseData.is_complete ? 'bg-green-100 text-green-700' : ''}>
                    {caseData.is_complete ? 'Complete' : 'In Progress'}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Created:</span>
                  <span>{new Date(caseData.created_at).toLocaleDateString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Sections:</span>
                  <span>{caseData.completed_sections.length} completed</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Preview */}
        <div className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Preview</CardTitle>
                <CardDescription>
                  Preview your case documentation before exporting
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={handleCopyMarkdown}
                  className="gap-2"
                >
                  <Copy className="h-4 w-4" />
                  Copy
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="full" className="w-full">
                <TabsList className="mb-4">
                  <TabsTrigger value="full">Full Document</TabsTrigger>
                  <TabsTrigger value="summary">Summary</TabsTrigger>
                </TabsList>
                
                <TabsContent value="full">
                  <div className="bg-slate-50 rounded-lg p-4 overflow-auto max-h-[600px]">
                    <pre className="text-sm text-slate-700 whitespace-pre-wrap font-mono">
                      {markdownContent || 'Loading preview...'}
                    </pre>
                  </div>
                </TabsContent>
                
                <TabsContent value="summary">
                  <div className="bg-slate-50 rounded-lg p-4 overflow-auto max-h-[600px]">
                    <pre className="text-sm text-slate-700 whitespace-pre-wrap font-mono">
                      {summary || 'Loading summary...'}
                    </pre>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
