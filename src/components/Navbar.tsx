import { Link, useLocation } from 'react-router-dom';
import { 
  Stethoscope, 
  LayoutDashboard, 
  PlusCircle, 
  Activity,
  Server
} from 'lucide-react';
import { Button } from '@/components/ui/button';

interface NavbarProps {
  apiStatus: 'checking' | 'online' | 'offline';
}

export function Navbar({ apiStatus }: NavbarProps) {
  const location = useLocation();
  
  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo */}
          <div className="flex items-center">
            <Link to="/" className="flex items-center gap-2">
              <div className="bg-blue-600 p-2 rounded-lg">
                <Stethoscope className="h-6 w-6 text-white" />
              </div>
              <span className="text-xl font-bold text-slate-900">ClerKase</span>
            </Link>
          </div>

          {/* Navigation Links */}
          <div className="flex items-center gap-1">
            <Link to="/">
              <Button 
                variant={isActive('/') ? 'default' : 'ghost'}
                className="gap-2"
              >
                <Activity className="h-4 w-4" />
                Home
              </Button>
            </Link>
            
            <Link to="/dashboard">
              <Button 
                variant={isActive('/dashboard') ? 'default' : 'ghost'}
                className="gap-2"
              >
                <LayoutDashboard className="h-4 w-4" />
                Dashboard
              </Button>
            </Link>
            
            <Link to="/new-case">
              <Button 
                variant={isActive('/new-case') ? 'default' : 'ghost'}
                className="gap-2"
              >
                <PlusCircle className="h-4 w-4" />
                New Case
              </Button>
            </Link>
          </div>

          {/* API Status */}
          <div className="flex items-center">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100">
              <Server className="h-4 w-4 text-slate-500" />
              <span className="text-sm text-slate-600">API:</span>
              {apiStatus === 'checking' && (
                <span className="text-sm text-amber-600">Checking...</span>
              )}
              {apiStatus === 'online' && (
                <span className="text-sm text-green-600 font-medium">Online</span>
              )}
              {apiStatus === 'offline' && (
                <span className="text-sm text-red-600 font-medium">Offline</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
