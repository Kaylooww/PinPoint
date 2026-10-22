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
  const [landscape, setLandscape] = useState(true)
  const showImage = citation.crop_url && !failed

  if (showImage) {
    // The whole crop is always visible: it scales down to fit (contain), never clipped.
    // Card: fits the card width and at most 160px tall. Panel: wide crops use the panel
    // width, tall ones (a receipt photo) fit 60% of the viewport height.
    return (
      <div className={`flex bg-surface-muted ${size === 'card' ? 'items-start justify-start p-3' : 'items-center justify-center p-5'}`}>
        <img
          src={assetUrl(citation.crop_url!)}
          alt={`Source ${citation.number}: ${citation.file_name}, page ${citation.page}`}
          onError={() => setFailed(true)}
          onLoad={(e) => setLandscape(e.currentTarget.naturalWidth >= e.currentTarget.naturalHeight)}
          className={`block h-auto rounded-[4px] bg-surface object-contain object-left-top ring-2 ring-highlight ${
            size === 'card'
              ? 'max-h-[160px] w-auto max-w-full'
              : landscape
                ? 'max-h-[60vh] w-full border border-border'
                : 'max-h-[60vh] w-auto max-w-full border border-border'
          }`}
        />
      </div>
    )
  }

  return (
    <div className={`bg-surface-muted ${size === 'card' ? 'h-[112px] overflow-hidden px-4 pt-4 pb-3.5' : 'p-5'}`}>
      <p className={`font-serif text-doc text-text ${size === 'card' ? 'line-clamp-3' : ''}`}>
        <mark className="rounded-[3px] bg-highlight box-decoration-clone px-1 text-text">{citation.excerpt || citation.text}</mark>
      </p>
    </div>
  )
}
