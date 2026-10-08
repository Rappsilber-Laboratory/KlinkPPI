const Navbar = () => {
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
            <span className="app-title-mark">KlinkPPI</span><span className="hidden sm:inline">: Single Point of Access to Protein-Protein Interactions Across Databases</span>
          </h1>
        </div>
      </div>
    </nav>
  )
}
export default Navbar
