export const pages = [
  ['overview','Mission Overview','▦','One mission path. Satellite preparation to ground-side trust decisions.'],
  ['satellite','Satellite Operations','⚙','Simulated Raspberry Pi sender, capture preparation and original preservation.'],
  ['camera','Camera & Payload','▣','Capture workspace and protected trusted-original records. No genuine camera imagery is supplied.'],
  ['transmission','Image Transmission','⇄','Direct TCP image delivery, complete byte accounting, queue state, and acknowledgement evidence.'],
  ['ground','Ground Station Operations','♧','Received payloads, receiver state and ground-side verification handoff.'],
  ['defense','Defense Engine','⬡','Explicit trust gates and final disposition. Detection evidence is not a disposition.'],
  ['alerts','Security Alerts','⚠','Security findings, disposition and review of simulated detection evidence.'],
  ['forensics','Image Forensics','⌗','Compare provenance and integrity evidence without inventing image pixels.'],
  ['timeline','Mission Timeline','☷','End-to-end mission event chronology and direct transport architecture.'],
  ['analytics','Analytics & Reports','▥','Derived measurements from four simulated transfers. No live analytics or invented trends.'],
  ['diagnostics','System Diagnostics','∿','Honest live integration state. No repositories, backend, adapters, or hardware connections have been provided.'],
  ['settings','Settings','☷','Environment configuration, operator access, and the explicit boundary between demo and live integration.'],
];

export const images = [
  {id:'IMG-041', cor:'BP-0041', seq:41, captured:'14:20:00', started:'14:20:02', received:'14:20:06', verification:180, disposition:'REJECTED', finding:'Invalid signature', severity:'CRITICAL', source:'SAT-PI-01'},
  {id:'IMG-042', cor:'BP-0042', seq:42, captured:'14:22:00', started:'14:22:02', received:'14:22:06', verification:120, disposition:'REJECTED', finding:'Replay / cache r0', severity:'HIGH', source:'SAT-PI-01'},
  {id:'IMG-043', cor:'BP-0043', seq:43, captured:'14:24:00', started:'14:24:02', received:'14:24:06', verification:210, disposition:'QUARANTINED', finding:'Digest mismatch', severity:'WARNING', source:'SAT-PI-01'},
  {id:'IMG-044', cor:'BP-0044', seq:44, captured:'14:32:00', started:'14:32:02', received:'14:32:06', verification:240, disposition:'ACCEPTED', finding:'None', severity:'INFO', source:'SAT-PI-01'},
];
export const last = images[3];
export const events = [
  {at:'14:32:00.000',source:'SAT',level:'INFO',name:'IMAGE_CAPTURED',image:'IMG-044',cor:'BP-0044',message:'Demo capture created / source SAT-PI-01'},
  {at:'14:32:01.000',source:'SAT',level:'INFO',name:'IMAGE_AUTHENTICATED',image:'IMG-044',cor:'BP-0044',message:'Demo authentication evidence prepared'},
  {at:'14:32:02.000',source:'TCP',level:'INFO',name:'TRANSFER_STARTED',image:'IMG-044',cor:'BP-0044',message:'2,097,152 bytes → ground-demo:5000'},
  {at:'14:32:06.000',source:'GROUND',level:'INFO',name:'IMAGE_RECEIVED',image:'IMG-044',cor:'BP-0044',message:'2,097,152 bytes / sequence 44'},
  {at:'14:32:06.120',source:'DEFENSE',level:'INFO',name:'INTEGRITY_VERIFIED',image:'IMG-044',cor:'BP-0044',message:'Demo transport digest matched'},
  {at:'14:32:06.240',source:'DEFENSE',level:'INFO',name:'IMAGE_ACCEPTED',image:'IMG-044',cor:'BP-0044',message:'All required demo checks passed'},
];
export const alerts = [
 {id:'AL-003',image:'IMG-043',cor:'BP-0043',utc:'14:24:06.210',severity:'WARNING',type:'Payload integrity mismatch',gate:'Integrity',status:'PENDING',disposition:'QUARANTINED',evidence:'Received digest differs from expected digest',location:'q/IMG-043'},
 {id:'AL-002',image:'IMG-042',cor:'BP-0042',utc:'14:22:06.120',severity:'HIGH',type:'Replay token reused',gate:'Replay',status:'CLOSED',disposition:'REJECTED',evidence:'Seeded demo token r0 reused / seq 42',location:'rejected/IMG-042'},
 {id:'AL-001',image:'IMG-041',cor:'BP-0041',utc:'14:20:06.180',severity:'CRITICAL',type:'Invalid signature',gate:'Authenticity',status:'CLOSED',disposition:'REJECTED',evidence:'Invalid demo signature',location:'rejected/IMG-041'}
];
export const gates = [
 ['Transport integrity','PASS','Demo payload digest matched','Required'],
 ['Cryptographic authenticity','PASS','Simulated signature valid','Required'],
 ['Replay protection','PASS','Demo token t44 unseen','Required'],
 ['Freshness','PASS','6.000 s age / ≤ 30 s window','Required'],
 ['Completeness','PASS','2,097,152 expected = received','Required'],
 ['Content anomaly detection','INCONCLUSIVE','Not integrated / no model','Optional · no gating'],
];
export const timeline = [
 ['14:32:00.000','SAT','Capture','IMAGE_CAPTURED · IMG-044 · SAT-PI-01 / seq 44'],
 ['14:32:00.200','SAT','Preparation','Trusted original saved / optional processing bypassed'],
 ['14:32:01.000','SAT','Authentication','IMAGE_AUTHENTICATED · simulated envelope prepared'],
 ['14:32:02.000','TCP','Transmission','TRANSFER_STARTED · direct TCP / 2,097,152 bytes'],
 ['14:32:06.000','GROUND','Reception','IMAGE_RECEIVED · complete / 4.00 s transfer'],
 ['14:32:06.120','DEFENSE','Verification','INTEGRITY_VERIFIED · demo payload digest matched'],
 ['14:32:06.240','DEFENSE','Final verdict','IMAGE_ACCEPTED · 240 ms verification / no alerts'],
];

export const capabilities = [
 ['CPU / RAM / storage / uptime','— Unavailable','Adapter telemetry contract'],
 ['Temperature / Wi-Fi measurements','Not reported','Capability discovery'],
 ['Camera preview / original access','Not reported','Repository support + authorization'],
 ['TCP framing / signature scheme','Not reported','Protocol agreement'],
 ['Experimental relay','Not reported','Authorized telemetry required'],
];
export const config = [
 ['Monitoring backend / WebSocket','Not configured','Fixture events / no socket'],
 ['Satellite adapter','Integration required','pi-demo / SAT-PI-01'],
 ['Ground TCP destination','Not configured','ground-demo:5000'],
 ['Protocol / framing / signatures','Not reported','Simulated evidence only'],
 ['Replay / freshness policy','Integration required','Seed r0 / 30 s window'],
];
export const roles = [
 ['Observe mission / events','Allowed','Allowed','Allowed'],
 ['Capture / sender configuration','Allowed','Read only','Allowed'],
 ['Quarantine evidence / review','Read only','Allowed','Allowed'],
 ['Protected-original overwrite','Denied','Denied','Denied'],
 ['Integration / access management','Denied','Denied','Allowed'],
];
export const fixtureNotice = 'DEMO · Simulated telemetry / Fixed four-transfer fixture · 2026-11-03 · Not hardware telemetry';
