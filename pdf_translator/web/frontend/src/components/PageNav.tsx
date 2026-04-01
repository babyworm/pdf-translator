interface Props {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
}

export function PageNav({ currentPage, totalPages, onPageChange }: Props) {
  if (totalPages <= 0) return null

  return (
    <div className="flex items-center justify-center gap-1 py-1 bg-gray-900 border-b border-gray-800">
      <button onClick={() => onPageChange(1)} disabled={currentPage <= 1}
        className="px-1.5 py-0.5 text-xs bg-gray-800 hover:bg-gray-700 rounded disabled:opacity-30">
        &laquo;&laquo;
      </button>
      <button onClick={() => onPageChange(currentPage - 1)} disabled={currentPage <= 1}
        className="px-1.5 py-0.5 text-xs bg-gray-800 hover:bg-gray-700 rounded disabled:opacity-30">
        &laquo;
      </button>

      {/* Page number buttons - show up to 7 pages */}
      {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
        let page: number
        if (totalPages <= 7) {
          page = i + 1
        } else if (currentPage <= 4) {
          page = i + 1
        } else if (currentPage >= totalPages - 3) {
          page = totalPages - 6 + i
        } else {
          page = currentPage - 3 + i
        }
        return (
          <button key={page} onClick={() => onPageChange(page)}
            className={`px-2 py-0.5 text-xs rounded ${
              page === currentPage ? 'bg-indigo-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'
            }`}>
            {page}
          </button>
        )
      })}

      <button onClick={() => onPageChange(currentPage + 1)} disabled={currentPage >= totalPages}
        className="px-1.5 py-0.5 text-xs bg-gray-800 hover:bg-gray-700 rounded disabled:opacity-30">
        &raquo;
      </button>
      <button onClick={() => onPageChange(totalPages)} disabled={currentPage >= totalPages}
        className="px-1.5 py-0.5 text-xs bg-gray-800 hover:bg-gray-700 rounded disabled:opacity-30">
        &raquo;&raquo;
      </button>
    </div>
  )
}
