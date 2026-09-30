/** Hero 地球合成层：星空 + 大气辉光地球 + 经纬网格 + 轨道光点。
 * 首页使用 HeroNetwork（商业感知网络）；本组件供其他页面 PageHero 复用。
 */
export function HeroGlobe() {
  return (
    <div className="hero-globe" aria-hidden="true">
      <div className="globe-stars" />
      <div className="globe-stars stars-2" />
      <div className="globe-sphere">
        <div className="globe-grid" />
        <div className="globe-continents" />
        <div className="globe-shine" />
      </div>
      <div className="globe-atmosphere" />
      <div className="orbit orbit-a"><i /><i /></div>
      <div className="orbit orbit-b"><i /><i /></div>
      <div className="orbit orbit-c"><i /></div>
    </div>
  )
}
