const GRADE_TONE: Record<string, string> = { S: 's', A: 'a', B: 'b', C: 'c', D: 'd' }

/** Opportunity 等级徽章（S/A/B/C/D）。 */
export function GradeChip({ grade }: { grade: string }) {
  return <span className={`grade-chip g-${GRADE_TONE[grade] || 'd'}`}>{grade}</span>
}

/** 证据来源可信度徽章（A/B/C/D）。 */
export function SourceGradeChip({ grade }: { grade: string }) {
  const labels: Record<string, string> = { A: 'A · 官方/权威', B: 'B · 权威平台', C: 'C · 公开平台', D: 'D · 待确认' }
  return <span className={`grade-chip g-${GRADE_TONE[grade] || 'd'}`} title={`来源可信度 ${labels[grade] || grade}`}>{labels[grade] || grade}</span>
}
