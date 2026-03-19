import { forwardRef } from 'react';

const Card = forwardRef(({
  children,
  variant   = 'default',
  hoverable = false,
  className = '',
  ...props
}, ref) => {
  const base = 'bg-surface rounded-sm transition-all duration-150';

  const variants = {
    default:  'border border-stroke',
    elevated: 'border border-stroke bg-elevated',
    outline:  'border border-stroke-strong',
    ghost:    'border border-transparent',
  };

  const hover = hoverable ? 'hover:border-stroke-strong cursor-pointer' : '';

  return (
    <div
      ref={ref}
      className={`${base} ${variants[variant]} ${hover} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

export const CardHeader = ({ children, className = '', ...props }) => (
  <div className={`p-4 border-b border-stroke ${className}`} {...props}>
    {children}
  </div>
);

export const CardBody = ({ children, className = '', ...props }) => (
  <div className={`p-4 ${className}`} {...props}>
    {children}
  </div>
);

export const CardFooter = ({ children, className = '', ...props }) => (
  <div className={`p-4 border-t border-stroke ${className}`} {...props}>
    {children}
  </div>
);

export default Card;
