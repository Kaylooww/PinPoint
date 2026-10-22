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
  const [wide, setWide] = useState(false)
  const showImage = citation.crop_url && !failed

  if (showImage) {
    return (
      <div
        className={`flex bg-surface-muted ${
          size === 'card'
            ? 'h-[112px] items-center justify-start overflow-hidden p-3'
            : wide
              ? 'items-center justify-start overflow-x-auto p-5'
              : 'items-center justify-center p-5'
        }`}
      >
        {/* Crops are often wide, short paragraph strips: in a card, fit the height and show the
            start of the passage at a readable size; in the panel, very wide strips keep a readable height and scroll sideways. */}
        <img
          src={assetUrl(citation.crop_url!)}
          alt={`Source ${citation.number}: ${citation.file_name}, page ${citation.page}`}
          onError={() => setFailed(true)}
          onLoad={(e) => setWide(e.currentTarget.naturalWidth > 4 * e.currentTarget.naturalHeight)}
          className={`rounded-[4px] bg-surface ring-2 ring-highlight ${
            size === 'card'
              ? 'h-full w-auto max-w-none'
              : wide
                ? 'h-[112px] w-auto max-w-none border border-border'
                : 'max-h-[60vh] w-full border border-border object-contain'
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
