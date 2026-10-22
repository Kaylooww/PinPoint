import { useState } from 'react'
import { assetUrl } from '../lib/api'
import type { Citation } from '../lib/types'

type CropImageProps = {
  citation: Citation
  /** Max height of the image or text fallback. */
  size?: 'card' | 'panel'
}

// The proof snapshot: the real crop framed on --surface-muted with a soft --highlight edge.
// Falls back to the extracted text (Instrument Serif, highlighted) when there is no image.
export function CropImage({ citation, size = 'card' }: CropImageProps) {
  const [failed, setFailed] = useState(false)
  const showImage = citation.crop_url && !failed

  if (showImage) {
    return (
      <div className={`flex items-center justify-center bg-surface-muted ${size === 'card' ? 'h-[112px] p-3' : 'p-5'}`}>
        <img
          src={assetUrl(citation.crop_url!)}
          alt={`Source ${citation.number}: ${citation.file_name}, page ${citation.page}`}
          onError={() => setFailed(true)}
          className={`max-w-full rounded-[4px] bg-surface object-contain ring-2 ring-highlight ${
            size === 'card' ? 'max-h-full' : 'max-h-[60vh] border border-border'
          }`}
        />
      </div>
    )
  }

  return (
    <div className={`bg-surface-muted ${size === 'card' ? 'h-[112px] overflow-hidden px-4 pt-4 pb-3.5' : 'p-5'}`}>
      <p className={`font-serif text-doc text-text ${size === 'card' ? 'line-clamp-3' : ''}`}>
        <mark className="rounded-[3px] bg-highlight box-decoration-clone px-1 text-text">{citation.text}</mark>
      </p>
    </div>
  )
}
