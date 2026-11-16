// KrishiMitra logo: a green seal with a gold ring, a young sprout (farming) and sound waves (voice),
// next to a two-line serif wordmark. Original artwork for this project, in the app's green & gold colours.
export function LogoMark({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="KrishiMitra logo" className="logo-mark">
      <defs>
        <linearGradient id="km-green" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2a8048" />
          <stop offset="1" stopColor="#123f23" />
        </linearGradient>
        <linearGradient id="km-gold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f8cf6a" />
          <stop offset="1" stopColor="#d98c0a" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="30" fill="url(#km-green)" stroke="url(#km-gold)" strokeWidth="3" />
      <circle cx="32" cy="32" r="24.5" fill="none" stroke="#f6c453" strokeOpacity="0.45" strokeWidth="1.2" strokeDasharray="2 2.6" />
      <path d="M19 45.5c4.3-2.2 8.6-3.2 13-3.2s8.7 1 13 3.2" fill="none" stroke="#f6c453" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M32 43V27" stroke="#f6c453" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M32 33c-1-6.3-5.6-9.8-12.2-9.8.3 6.6 4.6 10.6 12.2 9.8z" fill="url(#km-gold)" />
      <path d="M32 29c.8-6.8 5.6-10.6 12.6-10.6-.2 7-4.8 11.2-12.6 10.6z" fill="url(#km-gold)" />
      <path d="M13.5 28.5a8 8 0 0 0 0 9" fill="none" stroke="#f6c453" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M50.5 28.5a8 8 0 0 1 0 9" fill="none" stroke="#f6c453" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

export default function Logo({ size = 40, tagline = "Farming Assistant", tone = "dark" }) {
  return (
    <span className={`logo logo-${tone}`}>
      <LogoMark size={size} />
      <span className="logo-text">
        <span className="logo-name">KRISHIMITRA</span>
        {tagline && <span className="logo-tag">{tagline}</span>}
      </span>
    </span>
  );
}
