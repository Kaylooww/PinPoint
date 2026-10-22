# PinPoint — Design

Figma file: https://www.figma.com/design/dEpoBVGwqEwzOmYaKJC750 (file key dEpoBVGwqEwzOmYaKJC750)
Read it through the Figma MCP tools (see AGENTS.md).

## Frames (node ids)
| Frame | Light | Dark |
| Components | 3:2 | — |
| 01 Landing | 8:845 | — |
| 02 Sign In | 8:1110 | — |
| 03 Workspaces | 6:172 | 9:1242 |
| 04 Files | 6:435 | 9:1278 |
| 05 Ask | 7:542 | 9:1316 |
| 06 Citation Viewer | 7:748 | 9:1368 |
| 07 States | 9:971 | — |
| 08 Settings | 9:1023 | — |

## Feel
Calm, precise, trustworthy, premium, like a well-made legal pad. Lots of whitespace, few colors, no gradients, no robots or sparkles.

## Tokens (CSS variables; dark mode = .dark class on <html>; Figma variables use the same names)
| token | light | dark |
| --bg | #FAFAF9 | #0E0F12 |
| --surface | #FFFFFF | #16181D |
| --surface-muted | #F4F4F2 | #1D2026 |
| --border | #E7E5E1 | #2A2D35 |
| --text | #18181B | #ECECEF |
| --text-muted | #6B6B70 | #9A9CA5 |
| --accent | #4338CA | #8B9CFF |
| --accent-hover | #3730A3 | #A5B2FF |
| --accent-soft | #EEF0FF | rgba(139,156,255,0.14) |
| --on-accent | #FFFFFF | #0E0F12 |
| --highlight | #FDE68A | rgba(250,204,21,0.28) |
| --success | #15803D | #4ADE80 |
| --success-soft | #ECFDF3 | rgba(74,222,128,0.12) |
| --warning | #B45309 | #FBBF24 |
| --warning-soft | #FFF7ED | rgba(251,191,36,0.12) |
| --danger | #B91C1C | #F87171 |
| --danger-soft | #FEF2F2 | rgba(248,113,113,0.12) |

## Type
Inter for all UI: H1 24/32 semibold, H2 18/26 semibold, H3 15/22 semibold, body 14/22, small 13/20, label 12/16 medium, eyebrow 11/16 medium uppercase with wide tracking. Instrument Serif only for landing-page display text (hero 72, section 36) and document snippets.

## Layout
8pt grid. Radius: 8px for buttons and inputs, 12px for cards, full for pills. Shadow in light mode: 0 1px 2px rgba(0,0,0,0.04). No shadows in dark mode; use borders. App shell: 256px sidebar, main content padded 48px. Desktop 1440 is the target.

## Components (names match Figma)
Logo, Button (Primary, Secondary, Ghost), Field, Search Input, Status Badge (Ready, Parsing, Queued, Failed), Sidebar Item (Default, Active), Sidebar, File Row, Workspace Card, Citation Card, Answer Card, Theme Toggle (Light, Dark, System), Citation Panel.

## Signature detail
Citations use the highlight token like a highlighter on paper. Figma shows the crop as styled text, but in code it's the real crop image: frame it on --surface-muted with a soft --highlight tint behind or around it. Use the highlight token only for citations.
