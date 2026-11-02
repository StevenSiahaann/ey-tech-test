import React from 'react';

interface EyLogoProps extends React.SVGProps<SVGSVGElement> {
  size?: number | string;
  className?: string;
}

export const EyLogo: React.FC<EyLogoProps> = ({
  size,
  className = "w-6 h-6",
  style,
  ...props
}) => {
  const dimensionStyle = size ? { width: size, height: size, ...style } : style;

  return (
    <svg
      viewBox="0 0 44 44"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={dimensionStyle}
      aria-label="EY Logo"
      role="img"
      {...props}
    >
      {/* Dark charcoal base with 4px border radius */}
      <rect width="44" height="44" rx="4" fill="#1F1F24" />
      
      {/* Signature EY Yellow beam triangle at top-right, clipped smoothly to the 4px rounded corner */}
      <path d="M26 0H40C42.2091 0 44 1.79086 44 4V18L26 0Z" fill="#FFE600" />
      
      {/* Bold White EY typography matching architecture branding */}
      <text
        x="9"
        y="32"
        fontSize="22"
        fontWeight="800"
        fill="#FFFFFF"
        letterSpacing="-1"
        fontFamily="'Plus Jakarta Sans', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
      >
        EY
      </text>
    </svg>
  );
};

export default EyLogo;

