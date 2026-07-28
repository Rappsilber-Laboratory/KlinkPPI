import React from 'react'

const Navbar = () => {
  return (
    <nav className="border-b border-slate-300 bg-slate-200 px-4 py-4 sm:px-6">
      <div className="mx-auto flex w-full max-w-[110rem] items-center gap-4">
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
            className="h-10 w-auto sm:h-12"
          />
        </a>
        <div className="min-w-0 flex-1 text-center">
          <h1 className="text-lg font-bold italic leading-tight text-slate-900 sm:text-xl lg:text-3xl">
            KlinkPPI: Single Point of Access to Protein-Protein Interactions Across Databases
          </h1>
        </div>
      </div>
    </nav>
  )
}
export default Navbar
