import Link from './Link'
import { GITHUB_URL } from '../lib/site'

// The subtitle is the public tagline; change it here when the final title is chosen.
export const TAGLINE = 'Analysing Interaction Evidence and Gaps in Protein Sets'
const NAV = [['/', 'Search'], ['/tutorial', 'Tutorial'], ['/help', 'Help'], ['/web-services', 'Web services & Python API'], ['/license', 'License']]

const Navbar = ({ path = '/' }) => {
  return (
    <nav className="app-navbar px-4 py-4 sm:px-6">
      <div className="app-frame mx-auto flex w-full items-center gap-4">
        <a
          href="https://www.rappsilberlab.org/"
          target="_blank"
          rel="noreferrer"
          className="flex shrink-0 items-center"
          aria-label="Rappsilber Lab website"
        >
          <img
            src={`${import.meta.env.BASE_URL}RapLabTextLogo.png`} 
            alt="Rappsilber Lab"
            className="h-9 w-auto sm:h-11 lg:h-12"
          />
        </a>
        <div className="min-w-0 flex-1 text-center">
          <h1 className="text-base font-bold not-italic leading-tight text-slate-900 sm:text-xl lg:text-2xl xl:text-3xl">
            <Link to="/" className="app-title-link"><span className="app-title-mark">KlinkPPI</span><span className="hidden sm:inline">: {TAGLINE}</span></Link>
          </h1>
        </div>
      </div>
      <div className="app-frame mx-auto mt-3 flex w-full flex-wrap justify-center gap-1 app-nav-links" aria-label="Main">
        {NAV.map(([to, label]) => {
          const active = to === '/' ? path === '/' || path.startsWith('/results/') : path.startsWith(to)
          return <Link key={to} to={to} className={`app-nav-link${active ? ' active' : ''}`} aria-current={active ? 'page' : undefined}>{label}</Link>
        })}
        <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="app-nav-link">GitHub ↗</a>
      </div>
    </nav>
  )
}
export default Navbar
