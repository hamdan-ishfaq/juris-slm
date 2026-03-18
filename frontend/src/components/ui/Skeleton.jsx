/**
 * Skeleton Component - Loading placeholders for better UX
 * 
 * Variants: text, circle, rectangle
 * Sizes: sm, md, lg, full
 */

const Skeleton = ({
  variant = 'rectangle',
  size = 'md',
  className = '',
  ...props
}) => {
  // Base animation styles
  const baseStyles = 'animate-pulse bg-neutral-200 rounded';
  
  // Variant styles
  const variants = {
    text: 'h-4 w-full rounded',
    circle: 'rounded-full',
    rectangle: 'rounded-md',
  };
  
  // Size styles (for circle/rectangle)
  const sizes = {
    sm: variant === 'circle' ? 'h-8 w-8' : 'h-16',
    md: variant === 'circle' ? 'h-12 w-12' : 'h-24',
    lg: variant === 'circle' ? 'h-16 w-16' : 'h-32',
    full: 'h-full w-full',
  };
  
  return (
    <div
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    />
  );
};

// Pre-composed skeleton patterns for common use cases
export const SkeletonText = ({ lines = 3, className = '' }) => (
  <div className={`space-y-2 ${className}`}>
    {Array.from({ length: lines }).map((_, i) => (
      <Skeleton
        key={i}
        variant="text"
        className={i === lines - 1 ? 'w-3/4' : 'w-full'}
      />
    ))}
  </div>
);

export const SkeletonCard = ({ className = '' }) => (
  <div className={`bg-white border border-neutral-200 rounded-lg p-6 space-y-4 ${className}`}>
    <Skeleton variant="rectangle" size="sm" className="w-2/3" />
    <SkeletonText lines={3} />
  </div>
);

export const SkeletonAvatar = ({ size = 'md', className = '' }) => (
  <Skeleton variant="circle" size={size} className={className} />
);

export const SkeletonTable = ({ rows = 5, cols = 4, className = '' }) => (
  <div className={`space-y-3 ${className}`}>
    {Array.from({ length: rows }).map((_, rowIndex) => (
      <div key={rowIndex} className="flex gap-4">
        {Array.from({ length: cols }).map((_, colIndex) => (
          <Skeleton key={colIndex} variant="text" className="flex-1" />
        ))}
      </div>
    ))}
  </div>
);

export default Skeleton;
