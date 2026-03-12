import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Stethoscope, 
  ArrowRight, 
  Loader2,
  Baby,
  Scissors,
  HeartPulse,
  Baby as BabyIcon,
  Brain,
  Siren
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { toast } from 'sonner';

import { getRotations, createCase, type Rotation } from '@/api/client';

const rotationIcons: Record<string, React.ElementType> = {
  paediatrics: Baby,
  surgery: Scissors,
  internal_medicine: HeartPulse,
  obstetrics_gynaecology: BabyIcon,
  psychiatry: Brain,
  emergency_medicine: Siren,
};

const rotationColors: Record<string, string> = {
  paediatrics: 'bg-pink-100 text-pink-700 border-pink-200',
  surgery: 'bg-blue-100 text-blue-700 border-blue-200',
  internal_medicine: 'bg-green-100 text-green-700 border-green-200',
  obstetrics_gynaecology: 'bg-purple-100 text-purple-700 border-purple-200',
  psychiatry: 'bg-amber-100 text-amber-700 border-amber-200',
  emergency_medicine: 'bg-red-100 text-red-700 border-red-200',
};

export function NewCasePage() {
  const navigate = useNavigate();
  const [rotations, setRotations] = useState<Rotation[]>([]);
  const [selectedRotation, setSelectedRotation] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadRotations();
  }, []);

  const loadRotations = async () => {
    try {
      setLoading(true);
      const response = await getRotations();
      setRotations(response.rotations);
    } catch (error) {
      toast.error('Failed to load rotations');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCase = async () => {
    if (!selectedRotation) {
      toast.error('Please select a rotation');
      return;
    }

    try {
      setCreating(true);
      const response = await createCase(selectedRotation);
      toast.success('Case created successfully!');
      navigate(`/case/${response.case.case_id}`);
    } catch (error) {
      toast.error('Failed to create case');
      console.error(error);
      setCreating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-100 mb-4">
          <Stethoscope className="h-8 w-8 text-blue-600" />
        </div>
        <h1 className="text-3xl font-bold text-slate-900 mb-2">
          Start a New Case
        </h1>
        <p className="text-slate-600">
          Select your clinical rotation to begin documenting a new case
        </p>
      </div>

      {/* Rotation Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Select Rotation</CardTitle>
          <CardDescription>
            Choose the rotation that matches your current clinical placement
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
            </div>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {rotations.map((rotation) => {
                const Icon = rotationIcons[rotation.id] || Stethoscope;
                const isSelected = selectedRotation === rotation.id;
                
                return (
                  <button
                    key={rotation.id}
                    onClick={() => setSelectedRotation(rotation.id)}
                    className={`
                      relative p-6 rounded-xl border-2 text-left transition-all
                      ${isSelected 
                        ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200' 
                        : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50'
                      }
                    `}
                  >
                    <div className="flex items-start gap-4">
                      <div className={`
                        w-12 h-12 rounded-lg flex items-center justify-center
                        ${rotationColors[rotation.id] || 'bg-slate-100 text-slate-700'}
                      `}>
                        <Icon className="h-6 w-6" />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-slate-900">
                          {rotation.name}
                        </h3>
                        <p className="text-sm text-slate-500 mt-1">
                          {rotation.section_count} sections
                        </p>
                        <p className="text-xs text-slate-400 mt-1">
                          Version {rotation.version}
                        </p>
                      </div>
                      {isSelected && (
                        <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center">
                          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex justify-end gap-4 mt-6">
        <Button 
          variant="outline" 
          onClick={() => navigate('/dashboard')}
          disabled={creating}
        >
          Cancel
        </Button>
        <Button 
          onClick={handleCreateCase}
          disabled={!selectedRotation || creating}
          className="gap-2"
        >
          {creating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating...
            </>
          ) : (
            <>
              Create Case
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
