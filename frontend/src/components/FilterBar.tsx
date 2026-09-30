import { Search, SlidersHorizontal } from 'lucide-react'

export function FilterBar({ searchPlaceholder = '搜索企业、行业、机会或关键词…' }: {searchPlaceholder?: string}) {
  return (
    <div className="filter-bar">
      <div className="search-box"><Search size={17}/><input placeholder={searchPlaceholder}/></div>
      <button className="ghost-btn"><SlidersHorizontal size={16}/>高级筛选</button>
      <button className="ghost-btn">全部状态</button>
      <button className="ghost-btn">近30天</button>
    </div>
  )
}
