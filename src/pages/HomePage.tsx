import { Link } from 'react-router-dom';
import { 
  Stethoscope, 
  ClipboardList, 
  Brain, 
  FileText, 
  ArrowRight,
  CheckCircle2,
  Sparkles,
  Users
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const features = [
  {
    icon: ClipboardList,
    title: 'Structured Clerking',
    description: 'Complete clinical documentation section-by-section with guided prompts and templates.',
  },
  {
    icon: Brain,
    title: 'AI-Powered Clarifications',
    description: 'Get intelligent questions to fill gaps and improve your clinical documentation.',
  },
  {
    icon: FileText,
    title: 'Professional Export',
    description: 'Export your cases as Markdown or Word documents ready for submission.',
  },
  {
    icon: CheckCircle2,
    title: 'Quality Assurance',
    description: 'Detect contradictions and missing critical information automatically.',
  },
];

const rotations = [
  { name: 'Paediatrics', sections: 18, color: 'bg-pink-100 text-pink-700' },
  { name: 'Surgery', sections: 17, color: 'bg-blue-100 text-blue-700' },
  { name: 'Internal Medicine', sections: 16, color: 'bg-green-100 text-green-700' },
  { name: 'Obstetrics & Gynaecology', sections: 15, color: 'bg-purple-100 text-purple-700' },
  { name: 'Psychiatry', sections: 20, color: 'bg-amber-100 text-amber-700' },
  { name: 'Emergency Medicine', sections: 9, color: 'bg-red-100 text-red-700' },
];

export function HomePage() {
  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="bg-gradient-to-b from-blue-50 to-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-100 text-blue-700 text-sm font-medium mb-6">
              <Sparkles className="h-4 w-4" />
              <span>AI-Powered Clinical Documentation</span>
            </div>
            
            <h1 className="text-5xl font-bold text-slate-900 mb-6 leading-tight">
              Master Clinical Clerking with{' '}
              <span className="text-blue-600">ClerKase</span>
            </h1>
            
            <p className="text-xl text-slate-600 mb-8 leading-relaxed">
              The intelligent assistant that guides medical students through complete, 
              professional clinical case documentation. Get real-time feedback, 
              AI-powered clarifications, and export-ready documents.
            </p>
            
            <div className="flex justify-center gap-4">
              <Link to="/new-case">
                <Button size="lg" className="gap-2">
                  <Stethoscope className="h-5 w-5" />
                  Start New Case
                  <ArrowRight className="h-5 w-5" />
                </Button>
              </Link>
              <Link to="/dashboard">
                <Button size="lg" variant="outline" className="gap-2">
                  <ClipboardList className="h-5 w-5" />
                  View Dashboard
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Everything You Need for Perfect Clerking
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              ClerKase combines intelligent guidance with professional templates 
              to help you create complete, accurate clinical documentation.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, index) => (
              <Card key={index} className="border-slate-200 hover:border-blue-300 transition-colors">
                <CardHeader>
                  <div className="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center mb-4">
                    <feature.icon className="h-6 w-6 text-blue-600" />
                  </div>
                  <CardTitle className="text-lg">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-slate-600">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Rotations Section */}
      <section className="py-20 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Supported Rotations
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              ClerKase supports all major clinical rotations with specialized templates 
              designed for each specialty's unique requirements.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {rotations.map((rotation, index) => (
              <Card key={index} className="border-slate-200">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-900">{rotation.name}</h3>
                      <p className="text-sm text-slate-500">
                        {rotation.sections} sections
                      </p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${rotation.color}`}>
                      Active
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              How It Works
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Complete your clinical clerking in four simple steps
            </p>
          </div>

          <div className="grid md:grid-cols-4 gap-8">
            {[
              { step: '1', title: 'Select Rotation', desc: 'Choose your clinical rotation and start a new case' },
              { step: '2', title: 'Fill Sections', desc: 'Complete each section with guided prompts' },
              { step: '3', title: 'Answer Questions', desc: 'Respond to AI-generated clarification questions' },
              { step: '4', title: 'Export Document', desc: 'Download your professional clerking document' },
            ].map((item, index) => (
              <div key={index} className="text-center">
                <div className="w-16 h-16 rounded-full bg-blue-600 text-white flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                  {item.step}
                </div>
                <h3 className="font-semibold text-slate-900 mb-2">{item.title}</h3>
                <p className="text-slate-600">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-blue-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Improve Your Clinical Documentation?
          </h2>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            Start using ClerKase today and take your clerking skills to the next level.
          </p>
          <div className="flex justify-center gap-4">
            <Link to="/new-case">
              <Button size="lg" variant="secondary" className="gap-2">
                <Stethoscope className="h-5 w-5" />
                Start Your First Case
              </Button>
            </Link>
            <Link to="/dashboard">
              <Button size="lg" variant="outline" className="gap-2 border-white text-white hover:bg-white hover:text-blue-600">
                <Users className="h-5 w-5" />
                View Dashboard
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
