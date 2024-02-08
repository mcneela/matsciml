from pymatgen.core.structure import Molecule
from pymatgen.core.composition import Element, Composition
from pymatgen.core.periodic_table import Specie
from mp_api.client import MPRester
with MPRester(api_key="JfGLblzDrmPjX59g5591vEkk5cFYhe0O") as mpr:
    data = mpr.materials.search(material_ids=["mp-559295"])
# carbon monoxide molecule
co = Molecule(["C", "O"], [[0.0, 0.0, 0.0], [0.0, 0.0, 1.2]])
print(co)
print(co.center_of_mass) # center of mass
site_0 = co[0]
print(site_0.coords)
print(site_0.specie)

carbon = Element("C")
print(f"C average ionic radius: {carbon.average_ionic_radius}")

# making an OH anion
oh_minus = Molecule(["O", "H"], [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], charge=-1)
print(oh_minus)


# al_ni6_n = Molecule.from_file("data/AlNi6N.xyz")
