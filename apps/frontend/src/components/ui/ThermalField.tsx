/** Decorative thermal flow study. It represents no experiment or measurement. */
export function ThermalField({ hero = false }: { hero?: boolean }) {
  return (
    <div className={`thermal-field${hero ? " thermal-field-hero" : ""}`} aria-hidden="true">
      <div className="thermal-halo thermal-halo-one" />
      <div className="thermal-halo thermal-halo-two" />
      <div className="thermal-core" />
      <svg className="thermal-lines" viewBox="0 0 600 600" fill="none" preserveAspectRatio="xMidYMid meet">
        <circle cx="300" cy="300" r="204" className="thermal-orbit orbit-outer" />
        <circle cx="300" cy="300" r="143" className="thermal-orbit orbit-inner" />
        <path className="thermal-stream stream-one" d="M44 384c88-96 128-31 190-91 54-51 74-179 151-187 43-5 78 24 156 2" />
        <path className="thermal-stream stream-two" d="M23 475c99-107 169-56 232-147 66-95 45-203 128-229 46-14 111 4 183-35" />
        <path className="thermal-stream stream-three" d="M61 522c91-49 190-67 241-168 54-106 12-186 78-243 54-48 116-35 175-73" />
        <path className="thermal-stream stream-four" d="M70 184c95 14 143 101 220 101 85 0 104-115 230-102" />
        <path className="thermal-cross" d="M300 56v39m0 410v39M56 300h39m410 0h39" />
      </svg>
      {hero && (
        <>
          <span className="thermal-caption thermal-caption-top">FIELD NOTES / MICROGRAVITY</span>
          <span className="thermal-caption thermal-caption-bottom">SOURCE → VALIDATE → INTERPRET</span>
          <span className="thermal-axis">O₂ / FLOW / MATERIAL</span>
        </>
      )}
    </div>
  );
}
