import { Stethoscope, Heart } from 'lucide-react';

export function Footer() {
  return (
    <footer className="bg-white border-t border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          {/* Logo and tagline */}
          <div className="flex items-center gap-2">
            <Stethoscope className="h-5 w-5 text-blue-600" />
            <span className="font-semibold text-slate-900">ClerKase</span>
            <span className="text-slate-500">|</span>
            <span className="text-sm text-slate-600">AI-Powered Clinical Clerking Assistant</span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-6 text-sm text-slate-600">
            <a href="#" className="hover:text-blue-600 transition-colors">
              Documentation
            </a>
            <a href="#" className="hover:text-blue-600 transition-colors">
              Support
            </a>
            <a href="#" className="hover:text-blue-600 transition-colors">
              Privacy
            </a>
          </div>

          {/* Made with love */}
          <div className="flex items-center gap-1 text-sm text-slate-500">
            <span>Made with</span>
            <Heart className="h-4 w-4 text-red-500 fill-red-500" />
            <span>for medical students</span>
          </div>
        </div>

        {/* Copyright */}
        <div className="mt-4 pt-4 border-t border-slate-100 text-center text-sm text-slate-400">
          © {new Date().getFullYear()} ClerKase. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
