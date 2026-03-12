import React from 'react';

const CornerBrackets: React.FC<{ color?: string; size?: number }> = ({
  color = '#1a2332',
  size = 10
}) => {
  const style = { borderColor: color, width: size, height: size };
  return (
    <>
      <span className="absolute top-0 left-0 border-t border-l pointer-events-none" style={style} />
      <span className="absolute top-0 right-0 border-t border-r pointer-events-none" style={style} />
      <span className="absolute bottom-0 left-0 border-b border-l pointer-events-none" style={style} />
      <span className="absolute bottom-0 right-0 border-b border-r pointer-events-none" style={style} />
    </>
  );
};
export default CornerBrackets;
