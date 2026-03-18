import { Github, Linkedin, Mail } from 'lucide-react';

/**
 * Footer Component - Professional footer with developer contact information
 * 
 * Contains:
 * - GitHub, LinkedIn, Email links
 * - Copyright notice
 * - Clean, minimal design
 */

const Footer = () => {
  const currentYear = new Date().getFullYear();
  
  const links = [
    {
      name: 'GitHub',
      href: 'https://github.com/hamdan-ishfaq',
      icon: Github,
      ariaLabel: 'Visit GitHub profile',
    },
    {
      name: 'LinkedIn',
      href: 'https://www.linkedin.com/in/m-hamdan-ishfaq',
      icon: Linkedin,
      ariaLabel: 'Visit LinkedIn profile',
    },
    {
      name: 'Email',
      href: 'mailto:hamdanishfaq.2005@gmail.com',
      icon: Mail,
      ariaLabel: 'Send email',
    },
  ];
  
  return (
    <footer className="bg-white border-t border-neutral-200 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Copyright */}
          <div className="text-sm text-neutral-600">
            © {currentYear} BEWEIS. Built by{' '}
            <a
              href="https://github.com/hamdan-ishfaq"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-600 hover:text-primary-700 font-medium transition-colors duration-200"
            >
              Hamdan Ishfaq
            </a>
          </div>
          
          {/* Social Links */}
          <div className="flex items-center gap-4">
            {links.map((link) => {
              const Icon = link.icon;
              return (
                <a
                  key={link.name}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={link.ariaLabel}
                  className="text-neutral-600 hover:text-primary-600 transition-colors duration-200"
                >
                  <Icon className="h-5 w-5" />
                </a>
              );
            })}
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
