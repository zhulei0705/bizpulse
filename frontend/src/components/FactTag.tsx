/** 事实 / AI推断 严格区分标签。
 * 事实：来自真实网页的原始记录；AI推断：系统或人工的推断假设，不得当作事实展示。
 */
export function FactTag({ value }: { value: 'FACT' | 'INFERENCE' | string }) {
  return value === 'FACT'
    ? <span className="fact-tag fact">事实</span>
    : <span className="fact-tag inference">AI推断</span>
}
