import React from 'react'

const Navbar = () => {
  return (
    <nav className="bg-slate-200 px-6 py-6">
      <div className="mx-auto flex w-full max-w-[110rem] items-center justify-center">
        <div className="px-2 text-center">
          <h1 className="text-xl font-bold italic leading-tight text-slate-900 sm:text-2xl lg:text-3xl">
            KlinkPPI: Single Point of Access to Protein-Protein Interactions Across Databases
          </h1>
        </div>
      </div>
    </nav>
  )
}
export default Navbar
