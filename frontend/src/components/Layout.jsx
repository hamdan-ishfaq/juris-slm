import { Outlet } from 'react-router-dom';
import Navbar from './Navbar';
import Footer from './Footer';

/**
 * Layout Component - Consistent page structure across all routes
 * 
 * Features:
 * - Fixed navbar at top
 * - Main content area
 * - Footer at bottom
 * - Consistent spacing and styling
 */

const Layout = ({ children, showNavbar = true, showFooter = true, maxWidth = true }) => {
  return (
    <div className="min-h-screen flex flex-col bg-neutral-50">
      {/* Navbar */}
      {showNavbar && <Navbar />}
      
      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        {maxWidth ? (
          <div className="max-w-7xl w-full mx-auto px-4 md:px-6 py-6">
            {children || <Outlet />}
          </div>
        ) : (
          <>{children || <Outlet />}</>
        )}
      </main>
      
      {/* Footer */}
      {showFooter && <Footer />}
    </div>
  );
};

export default Layout;
