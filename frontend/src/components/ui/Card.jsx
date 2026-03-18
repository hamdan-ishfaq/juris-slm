import { forwardRef } from 'react';

/**
 * Card Component - Standardized container for content sections
 * 
 * Features:
 * - Consistent padding, shadow, and border-radius
 * - Optional hover state
 * - Variants for different contexts
 */

const Card = forwardRef(({
  children,
  variant = 'default',
  hoverable = false,
  className = '',
  ...props
}, ref) => {
  // Base styles
  const baseStyles = 'bg-white rounded-lg transition-all duration-200 ease-in-out';
  
  // Variant styles
  const variants = {
    default: 'border border-neutral-200 shadow-sm',
    elevated: 'shadow-md',
    outline: 'border-2 border-neutral-300',
    ghost: 'border border-transparent',
  };
  
  // Hover effect
  const hoverStyles = hoverable
    ? 'hover:shadow-lg hover:border-neutral-300 cursor-pointer'
    : '';
  
  return (
    <div
      ref={ref}
      className={`${baseStyles} ${variants[variant]} ${hoverStyles} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

// Card sub-components for consistent structure
export const CardHeader = ({ children, className = '', ...props }) => (
  <div className={`p-6 border-b border-neutral-200 ${className}`} {...props}>
    {children}
  </div>
);

export const CardBody = ({ children, className = '', ...props }) => (
  <div className={`p-6 ${className}`} {...props}>
    {children}
  </div>
);

export const CardFooter = ({ children, className = '', ...props }) => (
  <div className={`p-6 border-t border-neutral-200 ${className}`} {...props}>
    {children}
  </div>
);

export default Card;
