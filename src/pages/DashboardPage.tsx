import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  PlusCircle, 
  FileText, 
  Trash2, 
  ChevronRight,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

import { getCases, deleteCase, type Case } from '@/api/client';

export function DashboardPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCases();
  }, []);

  const loadCases = async () => {
    try {
      setLoading(true);
      const response = await getCases();
      setCases(response.cases);
    } catch (error) {
      toast.error('Failed to load cases');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCase = async (caseId: string) => {
    if (!confirm('Are you sure you want to delete this case?')) {
      return;
    }

    try {
      await deleteCase(caseId);
      toast.success('Case deleted successfully');
      loadCases();
    } catch (error) {
      toast.error('Failed to delete case');
      console.error(error);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusBadge = (caseItem: Case) => {
    if (caseItem.is_complete) {
      return (
        <Badge className="bg-green-100 text-green-700 hover:bg-green-100">
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Complete
        </Badge>
      );
    }
    return (
      <Badge variant="secondary">
        <Clock className="h-3 w-3 mr-1" />
        In Progress
      </Badge>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-600 mt-1">
            Manage your clinical cases and track your progress
          </p>
        </div>
        <Link to="/new-case">
          <Button className="gap-2">
            <PlusCircle className="h-4 w-4" />
            New Case
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid md:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">Total Cases</p>
                <p className="text-3xl font-bold text-slate-900">{cases.length}</p>
              </div>
              <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
                <FileText className="h-6 w-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">Complete</p>
                <p className="text-3xl font-bold text-green-600">
                  {cases.filter(c => c.is_complete).length}
                </p>
              </div>
              <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle2 className="h-6 w-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">In Progress</p>
                <p className="text-3xl font-bold text-amber-600">
                  {cases.filter(c => !c.is_complete).length}
                </p>
              </div>
              <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
                <Clock className="h-6 w-6 text-amber-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">Rotations</p>
                <p className="text-3xl font-bold text-purple-600">
                  {new Set(cases.map(c => c.rotation)).size}
                </p>
              </div>
              <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center">
                <AlertCircle className="h-6 w-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Cases List */}
      <Card>
        <CardHeader>
          <CardTitle>Your Cases</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
            </div>
          ) : cases.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 text-slate-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 mb-2">No cases yet</h3>
              <p className="text-slate-600 mb-4">
                Start your first clinical case to get started
              </p>
              <Link to="/new-case">
                <Button>
                  <PlusCircle className="h-4 w-4 mr-2" />
                  Create New Case
                </Button>
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {cases.map((caseItem) => (
                <div 
                  key={caseItem.case_id}
                  className="py-4 flex items-center justify-between hover:bg-slate-50 transition-colors px-4 -mx-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                      <FileText className="h-5 w-5 text-blue-600" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-slate-900">
                          {caseItem.rotation.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                        </h4>
                        {getStatusBadge(caseItem)}
                      </div>
                      <div className="flex items-center gap-4 text-sm text-slate-500 mt-1">
                        <span>ID: {caseItem.case_id.slice(0, 8)}...</span>
                        <span>•</span>
                        <span>Created: {formatDate(caseItem.created_at)}</span>
                        {!caseItem.is_complete && (
                          <>
                            <span>•</span>
                            <span>Current: {caseItem.current_section.replace('_', ' ')}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Link to={`/case/${caseItem.case_id}`}>
                      <Button variant="ghost" size="sm" className="gap-1">
                        View
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => handleDeleteCase(caseItem.case_id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
