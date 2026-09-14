import { Player } from '@remotion/player';
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

function CareerSignalFilm() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entrance = spring({ frame, fps, config: { damping: 18, stiffness: 95 } });
  const score = Math.round(interpolate(frame, [20, 105], [0, 86], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }));
  const pulse = interpolate(frame % 90, [0, 45, 90], [0.88, 1.05, 0.88], { easing: Easing.inOut(Easing.sin) });
  const scan = interpolate(frame % 150, [0, 150], [-15, 115]);
  return <AbsoluteFill style={{ background: 'linear-gradient(145deg,#194732,#0d261b)', color: '#fff', fontFamily: 'Manrope, sans-serif', overflow: 'hidden' }}>
    <div style={{ position: 'absolute', width: 520, height: 520, borderRadius: '50%', background: 'radial-gradient(circle,#d4ff4c 0%,rgba(201,255,54,.12) 40%,transparent 68%)', left: -210, top: -260, opacity: .65, scale: pulse }}/>
    <div style={{ position: 'absolute', inset: 30, border: '1px solid rgba(220,242,211,.18)', borderRadius: 30 }}/>
    <div style={{ position: 'absolute', left: 57, top: 48, fontSize: 12, letterSpacing: 2.2, color: '#d4e5cf', opacity: entrance }}>JOBPILOT / AGENT</div>
    <div style={{ position: 'absolute', right: 57, top: 48, fontSize: 12, color: '#c9ff36' }}>LIVE</div>
    <div style={{ position: 'absolute', left: 72, top: 155, width: 315, height: 305, borderRadius: 24, background: '#f8f8f3', color: '#17271e', padding: 33, boxShadow: '25px 29px 0 #28533d', translate: `0 ${interpolate(entrance,[0,1],[55,0])}px`, rotate: `${interpolate(entrance,[0,1],[-12,-5])}deg`, opacity: entrance }}>
      <div style={{ fontSize: 11, letterSpacing: 2, color: '#849284' }}>PROFILE SIGNAL</div>
      <div style={{ fontFamily: 'Georgia,serif', fontSize: 38, lineHeight: 1.05, marginTop: 37, letterSpacing: -1.5 }}>让每一份投递，<br/>都有可靠的依据。</div>
      <div style={{ position: 'absolute', bottom: 30, fontSize: 10, letterSpacing: 1.3, color: '#768377' }}>RESUME → ROLE → PROOF</div>
      <div style={{ position: 'absolute', left: 0, right: 0, height: 2, top: `${scan}%`, background: 'linear-gradient(90deg,transparent,#9fd229,transparent)', boxShadow: '0 0 20px #c9ff36' }}/>
    </div>
    <div style={{ position: 'absolute', right: 70, bottom: 86, width: 178, height: 178, borderRadius: '50%', border: '1px solid #a8d95c', display: 'grid', placeItems: 'center', scale: pulse }}>
      <div style={{ position: 'absolute', inset: 20, border: '1px solid rgba(168,217,92,.4)', borderRadius: '50%' }}/><div style={{ position: 'absolute', inset: 41, border: '1px solid rgba(168,217,92,.25)', borderRadius: '50%' }}/>
      <div style={{ fontFamily: 'Georgia,serif', color: '#c9ff36', fontSize: 66, letterSpacing: -5 }}>{score}</div>
    </div>
    <div style={{ position: 'absolute', left: 57, bottom: 48, fontSize: 11, color: '#bbceb8' }}>正在理解你的职业故事</div><div style={{ position: 'absolute', right: 57, bottom: 48, fontSize: 11, color: '#bbceb8' }}>01—04</div>
  </AbsoluteFill>;
}

export function HeroMotion() {
  return <div className="remotion-hero" aria-label="JobPilot AI 分析动画"><Player component={CareerSignalFilm} durationInFrames={180} compositionWidth={720} compositionHeight={720} fps={30} autoPlay loop controls={false} style={{ width: '100%', height: '100%' }} /></div>;
}
