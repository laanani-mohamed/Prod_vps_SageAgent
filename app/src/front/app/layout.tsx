import type { Metadata } from 'next'
import { Inter, Manrope } from 'next/font/google'
import './globals.css'
import './verre.css'   // design « verre » ; retirer cette ligne pour revenir à l'ancien design

const inter = Inter({ subsets: ['latin'], variable: '--police-menu' })
const manrope = Manrope({ subsets: ['latin'] })   // texte des pages (maquettes), Inter pour le menu

export const metadata: Metadata = { title: 'ITBORD' }

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body className={`${manrope.className} ${inter.variable}`}>{children}</body>
    </html>
  )
}
