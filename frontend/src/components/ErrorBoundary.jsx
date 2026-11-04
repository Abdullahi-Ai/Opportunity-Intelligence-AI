import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Diagnostic logging without leaking credentials or secrets
    console.error('Unhandled Application Render Exception caught by ErrorBoundary:', {
      name: error?.name,
      message: error?.message,
      componentStack: errorInfo?.componentStack
    });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (window.location) {
      window.location.reload();
    }
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null });
    if (window.location) {
      window.location.href = '/';
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-6 font-['Inter',sans-serif] text-slate-800">
          <div className="bg-white rounded-3xl p-8 sm:p-10 border border-slate-200/90 shadow-lg max-w-lg w-full text-center space-y-6">
            <div className="w-16 h-16 rounded-3xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto shadow-sm">
              <AlertTriangle className="w-8 h-8" />
            </div>

            <div className="space-y-2">
              <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                Temporary Display Issue
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 leading-relaxed">
                An unexpected interface error prevented this section from displaying properly. Your student profile and saved opportunities remain completely safe.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 text-left text-xs text-slate-600 space-y-1">
              <p className="font-semibold text-slate-700">What you can do:</p>
              <ul className="list-disc list-inside space-y-1 text-slate-500 text-[11px]">
                <li>Click <strong>Reload Interface</strong> to refresh the application state.</li>
                <li>Return to the home dashboard to browse curated opportunities.</li>
              </ul>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleReset}
                className="flex-1 py-3 px-4 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-xl shadow-md transition-colors flex items-center justify-center space-x-2"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Reload Interface</span>
              </button>
              <button
                type="button"
                onClick={this.handleGoHome}
                className="flex-1 py-3 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-colors flex items-center justify-center space-x-2"
              >
                <Home className="w-4 h-4" />
                <span>Go to Home</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
